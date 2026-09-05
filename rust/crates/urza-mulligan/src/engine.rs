use std::collections::BTreeMap;
use std::fmt;

use urza_cards::{load_r1_catalog, r1_catalog_digest_hex};
use urza_core::{
    CardDefId, CardZone, CommanderState, CommanderZone, LibraryKnowledge, Phase, TrueLibrary,
    TrueState, Window,
};
use urza_info::{InformationState, observe};
use urza_rng::{
    CoordinateStream, EventOccurrence, EventType, LogicalEventId, RngCoordinate, RngDomain,
    RootSeed, WorldId, shuffle,
};

/// R0 preserved the London-mulligan crate boundary without implementing policy.
pub const FOUNDATION_PHASE: &str = "R0";
pub const MULLIGAN_ENGINE_PHASE: &str = "R6";
pub const MULLIGAN_ENGINE_VERSION: &str = "r6_sequential_london_v2";
pub const OPENING_RUNTIME_VERSION: &str = "r6_opening_state_v1";
pub const OPENING_HAND_SIZE: usize = 7;
pub const COMMANDER_MAIN_DECK_SIZE: usize = 99;
pub const COMMANDER_PLAYER_COUNT: u8 = 4;
pub const EXPERIMENTAL_KEEP_FLOOR: u8 = 3;
pub const OPENING_HAND_EVENT_TYPE: EventType = EventType(0x0601);
pub const PREGAME_SEAT_EVENT_TYPE: EventType = EventType(0x0602);

/// Sequential Commander/London mulligan stages used by the R6 policy model.
///
/// `Three` is an experimental simulation floor. It is not a Magic rules floor.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum MulliganStage {
    InitialSeven,
    FreeSeven,
    Six,
    Five,
    Four,
    Three,
}

impl MulliganStage {
    pub const ALL: [Self; 6] = [
        Self::InitialSeven,
        Self::FreeSeven,
        Self::Six,
        Self::Five,
        Self::Four,
        Self::Three,
    ];

    pub const fn kept_cards(self) -> usize {
        match self {
            Self::InitialSeven | Self::FreeSeven => 7,
            Self::Six => 6,
            Self::Five => 5,
            Self::Four => 4,
            Self::Three => 3,
        }
    }

    pub const fn bottom_count(self) -> usize {
        OPENING_HAND_SIZE - self.kept_cards()
    }

    pub const fn next(self) -> Option<Self> {
        match self {
            Self::InitialSeven => Some(Self::FreeSeven),
            Self::FreeSeven => Some(Self::Six),
            Self::Six => Some(Self::Five),
            Self::Five => Some(Self::Four),
            Self::Four => Some(Self::Three),
            Self::Three => None,
        }
    }

    const fn rng_ordinal(self) -> u64 {
        match self {
            Self::InitialSeven => 0,
            Self::FreeSeven => 1,
            Self::Six => 2,
            Self::Five => 3,
            Self::Four => 4,
            Self::Three => 5,
        }
    }
}

/// Pregame facts legitimately visible before a mulligan decision.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct PregameContext {
    pub seat: u8,
    pub gemstone_caverns_eligible: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct BottomSubset {
    indices: Vec<usize>,
}

impl BottomSubset {
    pub fn indices(&self) -> &[usize] {
        &self.indices
    }
}

pub const fn bottom_subset_count(stage: MulliganStage) -> usize {
    match stage {
        MulliganStage::InitialSeven | MulliganStage::FreeSeven => 1,
        MulliganStage::Six => 7,
        MulliganStage::Five => 21,
        MulliganStage::Four | MulliganStage::Three => 35,
    }
}

/// Enumerate every legal unordered London-bottom subset for the current seven.
pub fn enumerate_bottom_subsets(stage: MulliganStage) -> Vec<BottomSubset> {
    let bottom_count = stage.bottom_count();
    if bottom_count == 0 {
        return vec![BottomSubset {
            indices: Vec::new(),
        }];
    }

    let mut subsets = Vec::with_capacity(bottom_subset_count(stage));
    let mut current = Vec::with_capacity(bottom_count);
    push_bottom_combinations(0, bottom_count, &mut current, &mut subsets);
    debug_assert_eq!(subsets.len(), bottom_subset_count(stage));
    subsets
}

fn push_bottom_combinations(
    start: usize,
    remaining: usize,
    current: &mut Vec<usize>,
    output: &mut Vec<BottomSubset>,
) {
    if remaining == 0 {
        output.push(BottomSubset {
            indices: current.clone(),
        });
        return;
    }

    let last_start = OPENING_HAND_SIZE - remaining;
    for index in start..=last_start {
        current.push(index);
        push_bottom_combinations(index + 1, remaining - 1, current, output);
        current.pop();
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum MulliganError {
    InvalidSevenSize { actual: usize },
    WrongBottomCount { expected: usize, actual: usize },
    BottomIndexOutOfRange { index: usize },
    DuplicateBottomIndex { index: usize },
    ExperimentalFloorReached,
}

impl fmt::Display for MulliganError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InvalidSevenSize { actual } => write!(
                formatter,
                "mulligan stages require a fresh seven, got {actual} cards"
            ),
            Self::WrongBottomCount { expected, actual } => write!(
                formatter,
                "mulligan stage requires exactly {expected} bottom cards, got {actual}"
            ),
            Self::BottomIndexOutOfRange { index } => write!(
                formatter,
                "bottom index {index} is outside the seven-card opening hand"
            ),
            Self::DuplicateBottomIndex { index } => write!(
                formatter,
                "bottom index {index} was selected more than once"
            ),
            Self::ExperimentalFloorReached => write!(
                formatter,
                "the experimental keep-3 policy floor forbids another mulligan"
            ),
        }
    }
}

impl std::error::Error for MulliganError {}

/// The only hand visible to mulligan policy at the current stage.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MulliganState<C> {
    stage: MulliganStage,
    current_seven: Vec<C>,
    pregame: PregameContext,
}

impl<C> MulliganState<C> {
    pub fn initial(current_seven: Vec<C>, pregame: PregameContext) -> Result<Self, MulliganError> {
        Self::at_stage(MulliganStage::InitialSeven, current_seven, pregame)
    }

    pub fn at_stage(
        stage: MulliganStage,
        current_seven: Vec<C>,
        pregame: PregameContext,
    ) -> Result<Self, MulliganError> {
        if current_seven.len() != OPENING_HAND_SIZE {
            return Err(MulliganError::InvalidSevenSize {
                actual: current_seven.len(),
            });
        }
        Ok(Self {
            stage,
            current_seven,
            pregame,
        })
    }

    pub const fn stage(&self) -> MulliganStage {
        self.stage
    }

    pub fn current_seven(&self) -> &[C] {
        &self.current_seven
    }

    pub const fn pregame(&self) -> PregameContext {
        self.pregame
    }

    /// Reject the current seven and only then request the next fresh seven.
    ///
    /// The generator receives stage/pregame facts, never the rejected hand.
    pub fn mulligan<F>(self, draw_fresh_seven: F) -> Result<Self, MulliganError>
    where
        F: FnOnce(MulliganStage, PregameContext) -> Vec<C>,
    {
        let next_stage = self
            .stage
            .next()
            .ok_or(MulliganError::ExperimentalFloorReached)?;
        let next_seven = draw_fresh_seven(next_stage, self.pregame);
        Self::at_stage(next_stage, next_seven, self.pregame)
    }
}

impl<C: Ord> MulliganState<C> {
    /// Keep the current seven after validating the exact London-bottom count.
    ///
    /// Hand and bottom cards are sorted into canonical card order. This avoids
    /// meaningless bottom-order branching until a reachable rule makes bottom
    /// order strategically relevant.
    pub fn keep(self, bottom_indices: &[usize]) -> Result<KeptHand<C>, MulliganError> {
        validate_bottom_indices(self.stage, bottom_indices)?;
        let mut selected = bottom_indices.to_vec();
        selected.sort_unstable();

        let mut hand = Vec::with_capacity(self.stage.kept_cards());
        let mut known_bottom = Vec::with_capacity(self.stage.bottom_count());
        let mut selected_cursor = 0;
        for (index, card) in self.current_seven.into_iter().enumerate() {
            if selected.get(selected_cursor) == Some(&index) {
                known_bottom.push(card);
                selected_cursor += 1;
            } else {
                hand.push(card);
            }
        }
        hand.sort_unstable();
        known_bottom.sort_unstable();

        Ok(KeptHand {
            stage: self.stage,
            hand,
            known_bottom,
            pregame: self.pregame,
        })
    }

    pub fn resolve<F>(
        self,
        decision: MulliganDecision,
        draw_fresh_seven: F,
    ) -> Result<MulliganResolution<C>, MulliganError>
    where
        F: FnOnce(MulliganStage, PregameContext) -> Vec<C>,
    {
        match decision {
            MulliganDecision::Keep { bottom_indices } => {
                self.keep(&bottom_indices).map(MulliganResolution::Kept)
            }
            MulliganDecision::Mulligan => self
                .mulligan(draw_fresh_seven)
                .map(MulliganResolution::Continue),
        }
    }
}

fn validate_bottom_indices(
    stage: MulliganStage,
    bottom_indices: &[usize],
) -> Result<(), MulliganError> {
    let expected = stage.bottom_count();
    if bottom_indices.len() != expected {
        return Err(MulliganError::WrongBottomCount {
            expected,
            actual: bottom_indices.len(),
        });
    }

    let mut normalized = bottom_indices.to_vec();
    normalized.sort_unstable();
    for &index in &normalized {
        if index >= OPENING_HAND_SIZE {
            return Err(MulliganError::BottomIndexOutOfRange { index });
        }
    }
    for pair in normalized.windows(2) {
        if pair[0] == pair[1] {
            return Err(MulliganError::DuplicateBottomIndex { index: pair[0] });
        }
    }
    Ok(())
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum MulliganDecision {
    Keep { bottom_indices: Vec<usize> },
    Mulligan,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum MulliganResolution<C> {
    Kept(KeptHand<C>),
    Continue(MulliganState<C>),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct KeptHand<C> {
    pub stage: MulliganStage,
    pub hand: Vec<C>,
    /// Canonical known-bottom order carried forward from the London keep.
    pub known_bottom: Vec<C>,
    pub pregame: PregameContext,
}

/// Identity for the value of taking another mulligan before the next seven is
/// generated. Rejected-hand identity is deliberately absent.
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct MulliganContinuationKey {
    pub deck_version: String,
    pub stage: MulliganStage,
    pub pregame: PregameContext,
    pub policy_version: String,
    pub objective_version: String,
    pub horizon: u8,
    pub environment_version: String,
}

#[derive(Debug, Clone)]
pub struct MulliganContinuationCache<V> {
    entries: BTreeMap<MulliganContinuationKey, V>,
}

impl<V> Default for MulliganContinuationCache<V> {
    fn default() -> Self {
        Self {
            entries: BTreeMap::new(),
        }
    }
}

impl<V> MulliganContinuationCache<V> {
    pub fn get(&self, key: &MulliganContinuationKey) -> Option<&V> {
        self.entries.get(key)
    }

    pub fn insert(&mut self, key: MulliganContinuationKey, value: V) -> Option<V> {
        self.entries.insert(key, value)
    }

    pub fn len(&self) -> usize {
        self.entries.len()
    }

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CommanderDeck {
    commander: CardDefId,
    main_deck: Vec<CardDefId>,
    deck_version: String,
    fingerprint: [u8; 16],
}

impl CommanderDeck {
    pub fn commander(&self) -> CardDefId {
        self.commander
    }

    pub fn main_deck(&self) -> &[CardDefId] {
        &self.main_deck
    }

    pub fn deck_version(&self) -> &str {
        &self.deck_version
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum OpeningError {
    Catalog(String),
    MissingCommander,
    MultipleCommanders,
    InvalidCommanderCount { actual: u8 },
    InvalidMainDeckSize { actual: usize },
    InvalidKeptHandSize { expected: usize, actual: usize },
    InvalidKnownBottomSize { expected: usize, actual: usize },
    KeptPackageDoesNotMatchSampledSeven,
    Mulligan(MulliganError),
    State(String),
    Observation(String),
}

impl fmt::Display for OpeningError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Catalog(error) => write!(formatter, "catalog error: {error}"),
            Self::MissingCommander => write!(formatter, "Commander deck has no commander"),
            Self::MultipleCommanders => write!(formatter, "Commander deck has multiple commanders"),
            Self::InvalidCommanderCount { actual } => write!(
                formatter,
                "Commander entry must have deck_count=1, got {actual}"
            ),
            Self::InvalidMainDeckSize { actual } => write!(
                formatter,
                "Commander main deck must contain 99 cards, got {actual}"
            ),
            Self::InvalidKeptHandSize { expected, actual } => write!(
                formatter,
                "kept hand has {actual} cards, expected {expected} for this mulligan stage"
            ),
            Self::InvalidKnownBottomSize { expected, actual } => write!(
                formatter,
                "known bottom has {actual} cards, expected {expected} for this mulligan stage"
            ),
            Self::KeptPackageDoesNotMatchSampledSeven => write!(
                formatter,
                "kept hand plus London bottoms do not match the sampled seven for this root/world/stage"
            ),
            Self::Mulligan(error) => write!(formatter, "mulligan error: {error}"),
            Self::State(error) => write!(formatter, "opening state error: {error}"),
            Self::Observation(error) => write!(formatter, "opening observation error: {error}"),
        }
    }
}

impl std::error::Error for OpeningError {}

impl From<MulliganError> for OpeningError {
    fn from(value: MulliganError) -> Self {
        Self::Mulligan(value)
    }
}

/// Load the audited Commander deck as exactly 99 library cards plus Urza.
pub fn load_commander_deck() -> Result<CommanderDeck, OpeningError> {
    let catalog = load_r1_catalog().map_err(|error| OpeningError::Catalog(error.to_string()))?;
    let digest = r1_catalog_digest_hex();
    let fingerprint = digest_fingerprint(&digest);
    let deck_version = format!("{}:{digest}", catalog.catalog_version);

    let mut commander = None;
    let mut main_deck = Vec::with_capacity(COMMANDER_MAIN_DECK_SIZE);
    for card in catalog.cards {
        if card.commander {
            if card.deck_count != 1 {
                return Err(OpeningError::InvalidCommanderCount {
                    actual: card.deck_count,
                });
            }
            if commander.replace(card.card_def_id()).is_some() {
                return Err(OpeningError::MultipleCommanders);
            }
        } else {
            for _ in 0..card.deck_count {
                main_deck.push(card.card_def_id());
            }
        }
    }
    main_deck.sort_unstable();

    if main_deck.len() != COMMANDER_MAIN_DECK_SIZE {
        return Err(OpeningError::InvalidMainDeckSize {
            actual: main_deck.len(),
        });
    }

    Ok(CommanderDeck {
        commander: commander.ok_or(OpeningError::MissingCommander)?,
        main_deck,
        deck_version,
        fingerprint,
    })
}

/// Sample visible multiplayer seat facts once, before mulligan policy sees a hand.
pub fn sample_pregame_context(root: RootSeed, world: WorldId) -> PregameContext {
    let mut stream = CoordinateStream::new(root, pregame_coordinate(world));
    let seat = u8::try_from(stream.uniform_below(u64::from(COMMANDER_PLAYER_COUNT)) + 1)
        .expect("four-player seat fits in u8");
    PregameContext {
        seat,
        gemstone_caverns_eligible: seat != 1,
    }
}

/// Deterministically sample only the visible fresh seven for one stage.
///
/// The exact remainder is intentionally not returned to the mulligan policy.
pub fn draw_fresh_seven(
    deck: &CommanderDeck,
    root: RootSeed,
    world: WorldId,
    stage: MulliganStage,
) -> Vec<CardDefId> {
    let shuffled = shuffled_main_deck(deck, root, world, stage);
    shuffled[..OPENING_HAND_SIZE].to_vec()
}

/// Start one sequential mulligan episode with pregame facts fixed first.
pub fn start_mulligan_game(
    deck: &CommanderDeck,
    root: RootSeed,
    world: WorldId,
) -> Result<MulliganState<CardDefId>, OpeningError> {
    let pregame = sample_pregame_context(root, world);
    let seven = draw_fresh_seven(deck, root, world, MulliganStage::InitialSeven);
    MulliganState::initial(seven, pregame).map_err(OpeningError::from)
}

/// Take one actual mulligan using the accepted Game-domain coordinate RNG.
pub fn take_mulligan(
    state: MulliganState<CardDefId>,
    deck: &CommanderDeck,
    root: RootSeed,
    world: WorldId,
) -> Result<MulliganState<CardDefId>, MulliganError> {
    state.mulligan(|stage, _| draw_fresh_seven(deck, root, world, stage))
}

/// Execution-side opening state plus its legal-information projection.
///
/// Policies should receive `information()`, not `true_state()`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct OpeningStateBridge {
    true_state: TrueState,
    information: InformationState,
    stage: MulliganStage,
    pregame: PregameContext,
}

impl OpeningStateBridge {
    pub fn true_state(&self) -> &TrueState {
        &self.true_state
    }

    pub fn information(&self) -> &InformationState {
        &self.information
    }

    pub const fn stage(&self) -> MulliganStage {
        self.stage
    }

    pub const fn pregame(&self) -> PregameContext {
        self.pregame
    }

    pub fn into_true_state(self) -> TrueState {
        self.true_state
    }
}

/// Bridge a kept London hand into the accepted exact execution state and the
/// accepted information state without exposing the sampled unknown middle.
pub fn bridge_kept_hand(
    kept: &KeptHand<CardDefId>,
    deck: &CommanderDeck,
    root: RootSeed,
    world: WorldId,
) -> Result<OpeningStateBridge, OpeningError> {
    if kept.hand.len() != kept.stage.kept_cards() {
        return Err(OpeningError::InvalidKeptHandSize {
            expected: kept.stage.kept_cards(),
            actual: kept.hand.len(),
        });
    }
    if kept.known_bottom.len() != kept.stage.bottom_count() {
        return Err(OpeningError::InvalidKnownBottomSize {
            expected: kept.stage.bottom_count(),
            actual: kept.known_bottom.len(),
        });
    }

    let shuffled = shuffled_main_deck(deck, root, world, kept.stage);
    let mut sampled_seven = shuffled[..OPENING_HAND_SIZE].to_vec();
    sampled_seven.sort_unstable();

    let mut kept_package = kept.hand.clone();
    kept_package.extend(kept.known_bottom.iter().copied());
    kept_package.sort_unstable();
    if kept_package != sampled_seven {
        return Err(OpeningError::KeptPackageDoesNotMatchSampledSeven);
    }

    let mut library_cards = shuffled[OPENING_HAND_SIZE..].to_vec();
    library_cards.extend(kept.known_bottom.iter().copied());
    let known_bottom =
        u8::try_from(kept.known_bottom.len()).expect("London bottom count is at most four");
    let library = TrueLibrary::new(
        library_cards,
        LibraryKnowledge {
            known_top: 0,
            known_bottom,
        },
    )
    .map_err(|error| OpeningError::State(error.to_string()))?;

    let state = TrueState {
        turn: 1,
        phase: Phase::Untap,
        window: Window::None,
        library,
        hand: CardZone::new(kept.hand.clone()),
        commander: CommanderState {
            zone: CommanderZone::CommandZone,
            command_zone_casts: 0,
        },
        ..TrueState::default()
    };
    state
        .validate()
        .map_err(|error| OpeningError::State(error.to_string()))?;
    let information =
        observe(&state).map_err(|error| OpeningError::Observation(error.to_string()))?;

    Ok(OpeningStateBridge {
        true_state: state,
        information,
        stage: kept.stage,
        pregame: kept.pregame,
    })
}

fn shuffled_main_deck(
    deck: &CommanderDeck,
    root: RootSeed,
    world: WorldId,
    stage: MulliganStage,
) -> Vec<CardDefId> {
    let mut cards = deck.main_deck.clone();
    shuffle(&mut cards, root, opening_coordinate(deck, world, stage));
    cards
}

fn opening_coordinate(
    deck: &CommanderDeck,
    world: WorldId,
    stage: MulliganStage,
) -> RngCoordinate {
    RngCoordinate {
        domain: RngDomain::Game,
        world,
        event_type: OPENING_HAND_EVENT_TYPE,
        logical_event: LogicalEventId(stage.rng_ordinal()),
        occurrence: EventOccurrence(0),
        concrete_fingerprint: deck.fingerprint,
    }
}

fn pregame_coordinate(world: WorldId) -> RngCoordinate {
    RngCoordinate {
        domain: RngDomain::Environment,
        world,
        event_type: PREGAME_SEAT_EVENT_TYPE,
        logical_event: LogicalEventId(0),
        occurrence: EventOccurrence(0),
        concrete_fingerprint: *b"r6-pregame-seat!",
    }
}

fn digest_fingerprint(digest: &str) -> [u8; 16] {
    let bytes = digest.as_bytes();
    let mut fingerprint = [0_u8; 16];
    for (index, output) in fingerprint.iter_mut().enumerate() {
        *output = (hex_nibble(bytes[index * 2]) << 4) | hex_nibble(bytes[index * 2 + 1]);
    }
    fingerprint
}

fn hex_nibble(byte: u8) -> u8 {
    match byte {
        b'0'..=b'9' => byte - b'0',
        b'a'..=b'f' => byte - b'a' + 10,
        b'A'..=b'F' => byte - b'A' + 10,
        _ => 0,
    }
}

#[cfg(test)]
mod tests {
    use std::cell::Cell;
    use std::collections::BTreeSet;

    use super::*;

    fn pregame() -> PregameContext {
        PregameContext {
            seat: 3,
            gemstone_caverns_eligible: true,
        }
    }

    fn deck() -> CommanderDeck {
        load_commander_deck().expect("audited Commander deck")
    }

    fn root() -> RootSeed {
        RootSeed::from_u64(0x5236_4d55_4c4c_0002)
    }

    #[test]
    fn commander_stage_schedule_has_one_free_seven_and_experimental_keep_three_floor() {
        let expected = [
            (MulliganStage::InitialSeven, 7, 0),
            (MulliganStage::FreeSeven, 7, 0),
            (MulliganStage::Six, 6, 1),
            (MulliganStage::Five, 5, 2),
            (MulliganStage::Four, 4, 3),
            (MulliganStage::Three, 3, 4),
        ];
        for (stage, kept, bottomed) in expected {
            assert_eq!(stage.kept_cards(), kept);
            assert_eq!(stage.bottom_count(), bottomed);
        }
        assert_eq!(MulliganStage::Three.next(), None);
        assert_eq!(EXPERIMENTAL_KEEP_FLOOR, 3);
    }

    #[test]
    fn exact_bottom_enumeration_accounts_for_every_legal_subset() {
        let expected = [
            (MulliganStage::InitialSeven, 1),
            (MulliganStage::FreeSeven, 1),
            (MulliganStage::Six, 7),
            (MulliganStage::Five, 21),
            (MulliganStage::Four, 35),
            (MulliganStage::Three, 35),
        ];

        for (stage, count) in expected {
            let subsets = enumerate_bottom_subsets(stage);
            assert_eq!(subsets.len(), count);
            assert_eq!(bottom_subset_count(stage), count);
            assert_eq!(
                subsets.iter().cloned().collect::<BTreeSet<_>>().len(),
                count
            );
            for subset in subsets {
                assert_eq!(subset.indices().len(), stage.bottom_count());
                assert!(subset.indices().windows(2).all(|pair| pair[0] < pair[1]));
            }
        }
    }

    #[test]
    fn keep_path_never_generates_or_observes_the_next_seven() {
        let state = MulliganState::at_stage(
            MulliganStage::Five,
            vec![0_u8, 1, 2, 3, 4, 5, 6],
            pregame(),
        )
        .unwrap();
        let generator_called = Cell::new(false);

        let resolution = state
            .resolve(
                MulliganDecision::Keep {
                    bottom_indices: vec![0, 6],
                },
                |_, _| {
                    generator_called.set(true);
                    vec![99; OPENING_HAND_SIZE]
                },
            )
            .unwrap();

        assert!(!generator_called.get());
        assert!(matches!(resolution, MulliganResolution::Kept(_)));
    }

    #[test]
    fn rejected_hand_identity_is_absent_from_continuation_cache_key() {
        let key = MulliganContinuationKey {
            deck_version: "deck-a".into(),
            stage: MulliganStage::Six,
            pregame: pregame(),
            policy_version: "policy-a".into(),
            objective_version: "win-by-t6".into(),
            horizon: 6,
            environment_version: "goldfish-a".into(),
        };
        let mut cache = MulliganContinuationCache::default();
        assert!(cache.insert(key.clone(), 42_u32).is_none());
        assert_eq!(cache.get(&key), Some(&42));
    }

    #[test]
    fn audited_deck_is_ninety_nine_plus_urza() {
        let deck = deck();
        assert_eq!(deck.main_deck().len(), COMMANDER_MAIN_DECK_SIZE);
        assert!(!deck.main_deck().contains(&deck.commander()));
        assert!(!deck.deck_version().is_empty());
    }

    #[test]
    fn pregame_seat_is_sampled_before_hands_and_caverns_fact_is_visible() {
        let mut saw_first = false;
        let mut saw_later = false;
        for world in 0..128 {
            let context = sample_pregame_context(root(), WorldId(world));
            assert!((1..=COMMANDER_PLAYER_COUNT).contains(&context.seat));
            assert_eq!(context.gemstone_caverns_eligible, context.seat != 1);
            saw_first |= context.seat == 1;
            saw_later |= context.seat != 1;
        }
        assert!(saw_first && saw_later);
    }

    #[test]
    fn pregame_and_opening_hand_use_separate_rng_domains() {
        let deck = deck();
        let world = WorldId(17);
        assert_eq!(pregame_coordinate(world).domain, RngDomain::Environment);
        assert_eq!(
            opening_coordinate(&deck, world, MulliganStage::InitialSeven).domain,
            RngDomain::Game
        );
        assert_ne!(
            pregame_coordinate(world).event_type,
            opening_coordinate(&deck, world, MulliganStage::InitialSeven).event_type
        );
    }

    #[test]
    fn stage_coordinates_make_fresh_sevens_replayable_without_future_generation() {
        let deck = deck();
        let world = WorldId(9);
        for stage in MulliganStage::ALL {
            let first = draw_fresh_seven(&deck, root(), world, stage);
            let second = draw_fresh_seven(&deck, root(), world, stage);
            assert_eq!(first, second);
            assert_eq!(first.len(), OPENING_HAND_SIZE);
        }
        assert_ne!(
            opening_coordinate(&deck, world, MulliganStage::InitialSeven),
            opening_coordinate(&deck, world, MulliganStage::FreeSeven)
        );
    }

    #[test]
    fn pregame_context_remains_fixed_through_sequential_mulligans() {
        let deck = deck();
        let world = WorldId(44);
        let initial = start_mulligan_game(&deck, root(), world).unwrap();
        let pregame = initial.pregame();
        let free = take_mulligan(initial, &deck, root(), world).unwrap();
        let six = take_mulligan(free, &deck, root(), world).unwrap();
        assert_eq!(six.stage(), MulliganStage::Six);
        assert_eq!(six.pregame(), pregame);
    }

    #[test]
    fn bridge_keeps_commander_outside_ninety_nine_and_carries_known_bottom() {
        let deck = deck();
        let world = WorldId(55);
        let state = MulliganState::at_stage(
            MulliganStage::Five,
            draw_fresh_seven(&deck, root(), world, MulliganStage::Five),
            pregame(),
        )
        .unwrap();
        let kept = state.keep(&[0, 6]).unwrap();
        let bridge = bridge_kept_hand(&kept, &deck, root(), world).unwrap();

        assert_eq!(bridge.true_state().turn, 1);
        assert_eq!(bridge.true_state().phase, Phase::Untap);
        assert_eq!(bridge.true_state().window, Window::None);
        assert_eq!(
            bridge.true_state().commander.zone,
            CommanderZone::CommandZone
        );
        assert_eq!(
            bridge.true_state().hand.len(),
            MulliganStage::Five.kept_cards()
        );
        assert_eq!(
            bridge.true_state().library.cards().len(),
            COMMANDER_MAIN_DECK_SIZE - MulliganStage::Five.kept_cards()
        );
        assert_eq!(
            bridge.true_state().library.known_bottom(),
            kept.known_bottom.as_slice()
        );
        assert_eq!(bridge.information().hand, kept.hand);
        assert_eq!(bridge.information().library.known_bottom, kept.known_bottom);
        assert_eq!(bridge.pregame(), pregame());
    }

    #[test]
    fn information_projection_hides_exact_unknown_middle_order() {
        let deck = deck();
        let world = WorldId(77);
        let state = MulliganState::at_stage(
            MulliganStage::Six,
            draw_fresh_seven(&deck, root(), world, MulliganStage::Six),
            pregame(),
        )
        .unwrap();
        let kept = state.keep(&[0]).unwrap();
        let bridge = bridge_kept_hand(&kept, &deck, root(), world).unwrap();

        let original = bridge.true_state();
        let mut permuted_cards = original.library.cards().to_vec();
        let unknown_len = permuted_cards.len() - original.library.known_bottom().len();
        permuted_cards[..unknown_len].reverse();
        let mut permuted = original.clone();
        permuted.library = TrueLibrary::new(permuted_cards, original.library.knowledge()).unwrap();

        assert_ne!(permuted.library.cards(), original.library.cards());
        assert_eq!(observe(&permuted).unwrap(), bridge.information().clone());
    }

    #[test]
    fn bridge_rejects_kept_package_from_a_different_sampled_stage() {
        let deck = deck();
        let world = WorldId(88);
        let state = MulliganState::at_stage(
            MulliganStage::Six,
            draw_fresh_seven(&deck, root(), world, MulliganStage::Six),
            pregame(),
        )
        .unwrap();
        let mut kept = state.keep(&[0]).unwrap();
        kept.hand[0] = CardDefId(u16::MAX);
        assert_eq!(
            bridge_kept_hand(&kept, &deck, root(), world),
            Err(OpeningError::KeptPackageDoesNotMatchSampledSeven)
        );
    }

    #[test]
    fn canonical_bottom_selection_is_preserved_for_bridge_identity() {
        let deck = deck();
        let world = WorldId(99);
        let seven = draw_fresh_seven(&deck, root(), world, MulliganStage::Four);
        let kept = MulliganState::at_stage(MulliganStage::Four, seven, pregame())
            .unwrap()
            .keep(&[6, 2, 4])
            .unwrap();
        assert!(kept.hand.windows(2).all(|pair| pair[0] <= pair[1]));
        assert!(
            kept.known_bottom
                .windows(2)
                .all(|pair| pair[0] <= pair[1])
        );
        let bridge = bridge_kept_hand(&kept, &deck, root(), world).unwrap();
        assert_eq!(
            bridge.true_state().library.known_bottom(),
            kept.known_bottom.as_slice()
        );
    }
}
