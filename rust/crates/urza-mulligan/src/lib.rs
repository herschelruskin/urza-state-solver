#![forbid(unsafe_code)]

use std::collections::BTreeMap;
use std::fmt;

/// R0 preserves the London-mulligan crate boundary without implementing policy.
pub const FOUNDATION_PHASE: &str = "R0";
pub const MULLIGAN_ENGINE_PHASE: &str = "R6";
pub const MULLIGAN_ENGINE_VERSION: &str = "r6_sequential_london_v1";
pub const OPENING_HAND_SIZE: usize = 7;
pub const EXPERIMENTAL_KEEP_FLOOR: u8 = 3;

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
}

/// Pregame facts that are legitimately visible before the mulligan decision.
///
/// Batch simulation should sample these facts before creating a `MulliganState`.
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

/// Exact number of legal unordered bottom subsets at one R6 stage.
pub const fn bottom_subset_count(stage: MulliganStage) -> usize {
    match stage {
        MulliganStage::InitialSeven | MulliganStage::FreeSeven => 1,
        MulliganStage::Six => 7,
        MulliganStage::Five => 21,
        MulliganStage::Four | MulliganStage::Three => 35,
    }
}

/// Enumerate every legal unordered bottom subset for the current seven.
///
/// Indices are emitted in ascending order. The enumeration is exhaustive: R6
/// never hides a bottom package behind beam search in deep/single-hand mode.
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
            Self::DuplicateBottomIndex { index } => {
                write!(formatter, "bottom index {index} was selected more than once")
            }
            Self::ExperimentalFloorReached => write!(
                formatter,
                "the experimental keep-3 policy floor forbids another mulligan"
            ),
        }
    }
}

impl std::error::Error for MulliganError {}

/// The only hand visible to the mulligan policy at the current stage.
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

    /// Resolve one sequential keep/mulligan decision.
    ///
    /// A future-seven generator is intentionally lazy: it is not invoked for a
    /// keep decision, so an unrevealed future hand cannot affect that choice.
    pub fn resolve<F>(
        self,
        decision: MulliganDecision,
        draw_fresh_seven: F,
    ) -> Result<MulliganResolution<C>, MulliganError>
    where
        F: FnOnce(MulliganStage, PregameContext) -> Vec<C>,
    {
        match decision {
            MulliganDecision::Keep { bottom_indices } => self
                .keep(&bottom_indices)
                .map(MulliganResolution::Kept),
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
        assert_eq!(
            MulliganStage::InitialSeven.next(),
            Some(MulliganStage::FreeSeven)
        );
        assert_eq!(MulliganStage::FreeSeven.next(), Some(MulliganStage::Six));
        assert_eq!(MulliganStage::Four.next(), Some(MulliganStage::Three));
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
                assert!(
                    subset
                        .indices()
                        .iter()
                        .all(|index| *index < OPENING_HAND_SIZE)
                );
            }
        }
    }

    #[test]
    fn keep_canonicalizes_hand_and_known_bottom_without_hidden_future_input() {
        let state = MulliganState::at_stage(
            MulliganStage::Four,
            vec![6_u8, 1, 5, 2, 4, 3, 0],
            pregame(),
        )
        .unwrap();
        let kept = state.keep(&[6, 4, 1]).unwrap();

        assert_eq!(kept.hand, vec![2, 3, 5, 6]);
        assert_eq!(kept.known_bottom, vec![0, 1, 4]);
        assert_eq!(kept.stage, MulliganStage::Four);
        assert_eq!(kept.pregame, pregame());
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
    fn mulligan_generates_exactly_one_fresh_seven_after_the_decision() {
        let state = MulliganState::initial(vec![0_u8; OPENING_HAND_SIZE], pregame()).unwrap();
        let calls = Cell::new(0_u8);
        let resolution = state
            .resolve(MulliganDecision::Mulligan, |stage, context| {
                calls.set(calls.get() + 1);
                assert_eq!(stage, MulliganStage::FreeSeven);
                assert_eq!(context, pregame());
                vec![1_u8, 2, 3, 4, 5, 6, 7]
            })
            .unwrap();

        assert_eq!(calls.get(), 1);
        let MulliganResolution::Continue(next) = resolution else {
            panic!("mulligan must continue to a fresh seven");
        };
        assert_eq!(next.stage(), MulliganStage::FreeSeven);
        assert_eq!(next.current_seven(), &[1, 2, 3, 4, 5, 6, 7]);
        assert_eq!(next.pregame(), pregame());
    }

    #[test]
    fn experimental_floor_blocks_further_mulligan_without_generating_a_hand() {
        let state = MulliganState::at_stage(
            MulliganStage::Three,
            vec![0_u8; OPENING_HAND_SIZE],
            pregame(),
        )
        .unwrap();
        let generator_called = Cell::new(false);
        let error = state
            .mulligan(|_, _| {
                generator_called.set(true);
                vec![1; OPENING_HAND_SIZE]
            })
            .unwrap_err();
        assert_eq!(error, MulliganError::ExperimentalFloorReached);
        assert!(!generator_called.get());
    }

    #[test]
    fn malformed_bottom_choices_are_rejected() {
        let wrong_count = MulliganState::at_stage(
            MulliganStage::Five,
            vec![0_u8; OPENING_HAND_SIZE],
            pregame(),
        )
        .unwrap()
        .keep(&[0])
        .unwrap_err();
        assert_eq!(
            wrong_count,
            MulliganError::WrongBottomCount {
                expected: 2,
                actual: 1
            }
        );

        let duplicate = MulliganState::at_stage(
            MulliganStage::Five,
            vec![0_u8; OPENING_HAND_SIZE],
            pregame(),
        )
        .unwrap()
        .keep(&[2, 2])
        .unwrap_err();
        assert_eq!(duplicate, MulliganError::DuplicateBottomIndex { index: 2 });

        let out_of_range = MulliganState::at_stage(
            MulliganStage::Five,
            vec![0_u8; OPENING_HAND_SIZE],
            pregame(),
        )
        .unwrap()
        .keep(&[0, 7])
        .unwrap_err();
        assert_eq!(
            out_of_range,
            MulliganError::BottomIndexOutOfRange { index: 7 }
        );
    }

    #[test]
    fn continuation_cache_identity_excludes_rejected_hand_identity() {
        let key = MulliganContinuationKey {
            deck_version: "deck-a".into(),
            stage: MulliganStage::Six,
            pregame: pregame(),
            policy_version: "policy-a".into(),
            objective_version: "win-by-t6".into(),
            horizon: 6,
            environment_version: "goldfish-a".into(),
        };
        let rejected_a = MulliganState::at_stage(
            MulliganStage::FreeSeven,
            vec![0_u8, 1, 2, 3, 4, 5, 6],
            pregame(),
        )
        .unwrap();
        let rejected_b = MulliganState::at_stage(
            MulliganStage::FreeSeven,
            vec![10_u8, 11, 12, 13, 14, 15, 16],
            pregame(),
        )
        .unwrap();
        assert_ne!(rejected_a.current_seven(), rejected_b.current_seven());

        let mut cache = MulliganContinuationCache::default();
        assert!(cache.insert(key.clone(), 42_u32).is_none());
        assert_eq!(cache.get(&key), Some(&42));
        assert_eq!(cache.len(), 1);
    }
}
