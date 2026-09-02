#![forbid(unsafe_code)]

use std::collections::BTreeSet;

use thiserror::Error;
use urza_core::{
    AbilityId, BattlefieldZone, CardDefId, CardFace, CommanderZone, CounterState, DelayedEvent,
    GenericCost, LibraryKnowledge, ManaPool, ObjectId, PendingDecision, PermanentMode,
    PermanentState, PermissionId, Phase, SourceRef, StackObject, StateValidationError, TrueLibrary,
    TrueState, Window,
};
use urza_info::{
    CanonicalObjectId, InformationState, ObservedPendingDecision, resolve_canonical_object,
    resolve_permission_slot,
};
use urza_rng::{
    EventOccurrence, EventType, LogicalEventId, RngCoordinate, RngDomain, RootSeed, WorldId,
};

pub const RULES_PHASE: &str = "R4";
pub const R2_RULES_VERSION: &str = "r2_core_kernel_v2";
pub const R3_RULES_VERSION: &str = "r3_search_complete_v4";
pub const RULES_VERSION: &str = "r4_engine_start_v1";
pub const HORIZON_TURN: u8 = 6;
pub const RNG_EVENT_SEARCH_SHUFFLE: EventType = EventType(0x0301);
pub const ABILITY_REPURPOSING_BAY_SEARCH: AbilityId = AbilityId(0x0301);
pub const ABILITY_TOP_LOOK: AbilityId = AbilityId(0x0302);
pub const ABILITY_TOP_DRAW: AbilityId = AbilityId(0x0303);
pub const ABILITY_URZA_SPIN: AbilityId = AbilityId(0x0304);
pub const ABILITY_SAGA_CHAPTER_I: AbilityId = AbilityId(0x0305);
pub const ABILITY_SAGA_CHAPTER_II: AbilityId = AbilityId(0x0306);
pub const ABILITY_SAGA_CHAPTER_III: AbilityId = AbilityId(0x0307);
pub const ABILITY_TEZZERET_MINUS_THREE: AbilityId = AbilityId(0x0308);
pub const ABILITY_NATIVE_ARTIFACT_UNTAP: AbilityId = AbilityId(0x0401);
pub const RNG_EVENT_URZA_SPIN_SHUFFLE: EventType = EventType(0x0302);

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct ManaCost {
    pub white: u16,
    pub blue: u16,
    pub black: u16,
    pub red: u16,
    pub green: u16,
    pub colorless: u16,
    pub generic: u16,
}

impl ManaCost {
    pub fn parse_scryfall(input: &str) -> Result<Self, ManaCostParseError> {
        if input.is_empty() {
            return Ok(Self::default());
        }

        let mut cost = Self::default();
        let mut rest = input;
        while !rest.is_empty() {
            if !rest.starts_with('{') {
                return Err(ManaCostParseError::Malformed(input.to_owned()));
            }
            let Some(close) = rest.find('}') else {
                return Err(ManaCostParseError::Malformed(input.to_owned()));
            };
            let symbol = &rest[1..close];
            rest = &rest[close + 1..];

            match symbol {
                "W" => add_one(&mut cost.white)?,
                "U" => add_one(&mut cost.blue)?,
                "B" => add_one(&mut cost.black)?,
                "R" => add_one(&mut cost.red)?,
                "G" => add_one(&mut cost.green)?,
                "C" => add_one(&mut cost.colorless)?,
                _ => {
                    if let Ok(generic) = symbol.parse::<u16>() {
                        cost.generic = cost
                            .generic
                            .checked_add(generic)
                            .ok_or(ManaCostParseError::Overflow)?;
                    } else {
                        return Err(ManaCostParseError::UnsupportedSymbol(symbol.to_owned()));
                    }
                }
            }
        }
        Ok(cost)
    }

    pub fn with_additional_generic(self, extra: u16) -> Result<Self, RuleError> {
        Ok(Self {
            generic: self
                .generic
                .checked_add(extra)
                .ok_or(RuleError::ArithmeticOverflow)?,
            ..self
        })
    }

    fn required_total(self) -> u32 {
        u32::from(self.white)
            + u32::from(self.blue)
            + u32::from(self.black)
            + u32::from(self.red)
            + u32::from(self.green)
            + u32::from(self.colorless)
            + u32::from(self.generic)
    }

    fn required_colored(self) -> [u16; 6] {
        [
            self.white,
            self.blue,
            self.black,
            self.red,
            self.green,
            self.colorless,
        ]
    }
}

fn add_one(value: &mut u16) -> Result<(), ManaCostParseError> {
    *value = value.checked_add(1).ok_or(ManaCostParseError::Overflow)?;
    Ok(())
}

#[derive(Debug, Clone, Error, PartialEq, Eq)]
pub enum ManaCostParseError {
    #[error("malformed mana-cost string {0:?}")]
    Malformed(String),
    #[error("unsupported mana symbol {0:?}")]
    UnsupportedSymbol(String),
    #[error("mana cost exceeds u16 storage")]
    Overflow,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct ManaPayment {
    pub white: u16,
    pub blue: u16,
    pub black: u16,
    pub red: u16,
    pub green: u16,
    pub colorless: u16,
}

impl ManaPayment {
    fn amounts(self) -> [u16; 6] {
        [
            self.white,
            self.blue,
            self.black,
            self.red,
            self.green,
            self.colorless,
        ]
    }

    fn total(self) -> u32 {
        self.amounts().into_iter().map(u32::from).sum()
    }

    pub fn satisfies(self, cost: ManaCost) -> bool {
        let paid = self.amounts();
        let required = cost.required_colored();
        paid.iter()
            .zip(required)
            .all(|(paid_amount, required_amount)| *paid_amount >= required_amount)
            && self.total() == cost.required_total()
    }

    pub fn is_available_from(self, pool: ManaPool) -> bool {
        self.white <= pool.white
            && self.blue <= pool.blue
            && self.black <= pool.black
            && self.red <= pool.red
            && self.green <= pool.green
            && self.colorless <= pool.colorless
    }
}

pub fn enumerate_payments(pool: ManaPool, cost: ManaCost) -> Vec<ManaPayment> {
    let available = [
        pool.white,
        pool.blue,
        pool.black,
        pool.red,
        pool.green,
        pool.colorless,
    ];
    let required = cost.required_colored();

    if required
        .iter()
        .zip(available)
        .any(|(required_amount, available_amount)| *required_amount > available_amount)
    {
        return Vec::new();
    }

    let residual = std::array::from_fn(|index| available[index] - required[index]);
    let mut allocation = [0_u16; 6];
    let mut out = Vec::new();
    enumerate_generic_allocations(
        0,
        cost.generic,
        &residual,
        &required,
        &mut allocation,
        &mut out,
    );
    out
}

fn enumerate_generic_allocations(
    index: usize,
    remaining: u16,
    residual: &[u16; 6],
    required: &[u16; 6],
    allocation: &mut [u16; 6],
    out: &mut Vec<ManaPayment>,
) {
    if index == residual.len() {
        if remaining == 0 {
            out.push(ManaPayment {
                white: required[0] + allocation[0],
                blue: required[1] + allocation[1],
                black: required[2] + allocation[2],
                red: required[3] + allocation[3],
                green: required[4] + allocation[4],
                colorless: required[5] + allocation[5],
            });
        }
        return;
    }

    let maximum = residual[index].min(remaining);
    for amount in 0..=maximum {
        allocation[index] = amount;
        enumerate_generic_allocations(
            index + 1,
            remaining - amount,
            residual,
            required,
            allocation,
            out,
        );
    }
    allocation[index] = 0;
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash)]
pub enum R2CardRole {
    #[default]
    Unsupported,
    Land,
    ArtifactPermanent,
    CreaturePermanent,
    PlaneswalkerPermanent,
    SearchSpell,
    UrzaCommander,
    UrzaConstructToken,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash)]
pub enum LandEntryRule {
    #[default]
    None,
    Untapped,
    PayLifeOrTapped {
        life: u8,
    },
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash)]
pub enum LandEntryChoice {
    #[default]
    Default,
    PayLife,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash)]
pub enum ManaAbility {
    #[default]
    None,
    TapForBlue,
    TapForColorless(u16),
    TapForBlueAndDamage {
        damage: u16,
    },
    TapForColorlessAndDamage {
        mana: u16,
        damage: u16,
    },
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash)]
pub struct SearchClassFlags {
    pub spellseeker: bool,
    pub merchant_scroll: bool,
    pub mystical_tutor: bool,
    pub saga_iii: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum SimpleTutorKind {
    Spellseeker,
    MerchantScroll,
    MysticalTutor,
}

impl SimpleTutorKind {
    fn destination(self) -> SearchDestination {
        match self {
            Self::Spellseeker | Self::MerchantScroll => SearchDestination::Hand,
            Self::MysticalTutor => SearchDestination::LibraryTop,
        }
    }

    fn instant_speed(self) -> bool {
        matches!(self, Self::MysticalTutor)
    }
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash)]
pub enum SpecialSearchKind {
    #[default]
    None,
    Whir,
    Reshape,
    TransmuteArtifact,
    RepurposingBay,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash)]
pub enum EngineKind {
    #[default]
    None,
    BasaltMonolith,
    GrimMonolith,
    ForensicGadgeteer,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash)]
pub enum UtilityKind {
    #[default]
    None,
    SenseisDiviningTop,
    UrzasSaga,
    TezzeretCruelCaptain,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum SearchDestination {
    Hand,
    LibraryTop,
    Battlefield,
    Graveyard,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash)]
pub struct CardProfile {
    pub card: CardDefId,
    pub mana_cost: Option<ManaCost>,
    pub mana_value: u16,
    pub role: R2CardRole,
    pub battlefield_face: CardFace,
    pub land_entry: LandEntryRule,
    pub mana_ability: ManaAbility,
    pub search_classes: SearchClassFlags,
    pub simple_tutor: Option<SimpleTutorKind>,
    pub special_search: SpecialSearchKind,
    pub utility: UtilityKind,
    pub engine: EngineKind,
    pub native_untap_generic: Option<u16>,
    pub artifact_activation_reduction: u16,
    pub skip_normal_untap: bool,
    pub starting_loyalty: i16,
    pub is_artifact: bool,
    pub is_creature: bool,
}

pub trait CardDatabase {
    fn profile(&self, card: CardDefId) -> Option<CardProfile>;
    fn commander_card(&self) -> CardDefId;
    fn urza_construct_token_card(&self) -> CardDefId;
}

#[derive(Debug, Clone, Copy)]
pub struct GameRngContext {
    pub root: RootSeed,
    pub world: WorldId,
    pub logical_event: LogicalEventId,
}

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub enum Action {
    PassPriority,
    PlayLand {
        card: CardDefId,
        entry: LandEntryChoice,
    },
    ActivateManaAbility {
        source: ObjectId,
    },
    ActivateNativeArtifactUntap {
        source: ObjectId,
        payment: ManaPayment,
    },
    ActivateUrzaArtifactMana {
        artifact: ObjectId,
    },
    CastFromHand {
        card: CardDefId,
        payment: ManaPayment,
    },
    CastWhir {
        card: CardDefId,
        x_value: u16,
        payment: ManaPayment,
        improvise_sources: Vec<ObjectId>,
    },
    CastReshape {
        card: CardDefId,
        x_value: u16,
        sacrifice: ObjectId,
        payment: ManaPayment,
    },
    ActivateRepurposingBay {
        source: ObjectId,
        sacrifice: ObjectId,
        payment: ManaPayment,
    },
    ActivateTopLook {
        source: ObjectId,
        payment: ManaPayment,
    },
    ActivateTopDraw {
        source: ObjectId,
    },
    ActivateUrzaSpin {
        source: ObjectId,
        payment: ManaPayment,
    },
    ActivateTezzeretMinusThree {
        source: ObjectId,
    },
    PlayUrzaPermission {
        permission_slot: u16,
        face: CardFace,
    },
    CastCommander {
        payment: ManaPayment,
    },
    ChooseTransmuteSacrifice {
        artifact: CanonicalObjectId,
    },
    ChooseSearchTarget {
        target: Option<CardDefId>,
    },
    PayTransmuteDifference {
        payment: Option<ManaPayment>,
    },
    ChooseTopOrder {
        order: Vec<CardDefId>,
    },
    ChooseScry {
        top: Vec<CardDefId>,
        bottom: Vec<CardDefId>,
    },
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum RulesObservation {
    CardsDrawn(Vec<CardDefId>),
    PermanentEntered {
        card: CardDefId,
        face: CardFace,
        token: bool,
    },
    SearchAvailable {
        source: CardDefId,
        candidates: Vec<CardDefId>,
        may_fail: bool,
    },
    SearchCompleted {
        source: CardDefId,
        target: Option<CardDefId>,
        destination: SearchDestination,
    },
    TopCardsObserved {
        source: CardDefId,
        cards: Vec<CardDefId>,
    },
    ScryCardsObserved {
        source: CardDefId,
        cards: Vec<CardDefId>,
    },
    UrzaCardExiled {
        card: CardDefId,
    },
}

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct Transition {
    pub observations: Vec<RulesObservation>,
}

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct LibrarySearchObservation {
    /// Search choices are deliberately sorted by card identity so exact hidden
    /// library order cannot leak through candidate ordering.
    pub candidates: Vec<CardDefId>,
}

#[derive(Debug, Error, PartialEq, Eq)]
pub enum RuleError {
    #[error("cannot execute rules on an invalid state: {0}")]
    InvalidState(#[from] StateValidationError),
    #[error("unknown card definition {0:?}")]
    UnknownCard(CardDefId),
    #[error("current milestone does not yet support the intrinsic mechanic for card {0:?}")]
    UnsupportedCardMechanic(CardDefId),
    #[error("current milestone cannot resolve this stack object yet")]
    UnsupportedStackObject,
    #[error("action is not legal in the current phase/window")]
    IllegalTiming,
    #[error("a contingent decision is pending")]
    PendingDecisionActive,
    #[error("card {0:?} is not in hand")]
    CardNotInHand(CardDefId),
    #[error("the land play for this turn has already been used")]
    LandAlreadyPlayed,
    #[error("object {0:?} is not on the battlefield")]
    MissingPermanent(ObjectId),
    #[error("object {0:?} is already tapped")]
    PermanentTapped(ObjectId),
    #[error("object {0:?} does not have an R2-supported intrinsic mana ability")]
    NotManaSource(ObjectId),
    #[error("land-entry choice is not legal for card {0:?}")]
    InvalidLandEntryChoice(CardDefId),
    #[error("cannot pay {required} life from life total {available}")]
    InsufficientLife { required: u16, available: u16 },
    #[error("object {0:?} is not an artifact")]
    NotArtifact(ObjectId),
    #[error("Urza is not on the battlefield")]
    UrzaNotOnBattlefield,
    #[error("mana payment is not legal for the requested cost")]
    InvalidManaPayment,
    #[error("commander is not in the command zone")]
    CommanderNotInCommandZone,
    #[error("commander state is inconsistent with a hand cast")]
    CommanderNotInHand,
    #[error("draw attempted from an empty library")]
    DrawFromEmptyLibrary,
    #[error("the T1-T6 horizon has ended")]
    HorizonReached,
    #[error("physical object id space is exhausted")]
    ObjectIdExhausted,
    #[error("RNG occurrence space is exhausted")]
    RngOccurrenceExhausted,
    #[error("numeric rules state overflow")]
    ArithmeticOverflow,
    #[error("this action requires an explicit game RNG context")]
    MissingGameRngContext,
    #[error("no simple-tutor target decision is pending")]
    NoTutorDecisionPending,
    #[error("card {0:?} is not a legal target for the pending search")]
    InvalidSearchTarget(CardDefId),
    #[error("the requested search action does not match the pending decision")]
    SearchDecisionMismatch,
    #[error("object {0:?} cannot be used more than once for the same cost")]
    DuplicateCostObject(ObjectId),
    #[error("too many improvise sources were supplied for X={x_value}")]
    ExcessImprovise { x_value: u16 },
    #[error("object {0:?} is not a legal sacrifice for this effect")]
    InvalidSacrifice(ObjectId),
    #[error("object {0:?} has an incoming attachment; this sacrifice interaction is deferred")]
    AttachedSacrificeDeferred(ObjectId),
    #[error("the Repurposing Bay source and sacrificed artifact must be different objects")]
    BayCannotSacrificeSelf,
    #[error("no permanent corresponds to observed canonical object {0:?}")]
    MissingCanonicalPermanent(CanonicalObjectId),
    #[error("no Transmute Artifact difference-payment decision is pending")]
    NoTransmutePaymentPending,
    #[error("the requested top/scry ordering is not a permutation of the observed cards")]
    InvalidObservedCardOrdering,
    #[error("permission slot {0} does not exist")]
    MissingPermissionSlot(u16),
    #[error("the requested card face is not supported by this permission")]
    InvalidPermissionFace,
    #[error("the selected permission card is no longer in exile")]
    PermissionCardNotInExile,
}

pub fn apply_action<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    action: Action,
) -> Result<Transition, RuleError> {
    apply_action_internal(state, cards, action, None)
}

pub fn apply_action_with_rng<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    action: Action,
    rng: GameRngContext,
) -> Result<Transition, RuleError> {
    apply_action_internal(state, cards, action, Some(rng))
}

fn apply_action_internal<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    action: Action,
    rng: Option<GameRngContext>,
) -> Result<Transition, RuleError> {
    state.validate()?;
    let transition = match action {
        Action::PassPriority => pass_priority(state, cards, rng)?,
        Action::PlayLand { card, entry } => play_land(state, cards, card, entry)?,
        Action::ActivateManaAbility { source } => {
            activate_mana_ability(state, cards, source)?;
            Transition::default()
        }
        Action::ActivateNativeArtifactUntap { source, payment } => {
            activate_native_artifact_untap(state, cards, source, payment)?;
            Transition::default()
        }
        Action::ActivateUrzaArtifactMana { artifact } => {
            activate_urza_artifact_mana(state, cards, artifact)?;
            Transition::default()
        }
        Action::CastFromHand { card, payment } => {
            cast_from_hand(state, cards, card, payment)?;
            Transition::default()
        }
        Action::CastWhir {
            card,
            x_value,
            payment,
            improvise_sources,
        } => {
            cast_whir(state, cards, card, x_value, payment, &improvise_sources)?;
            Transition::default()
        }
        Action::CastReshape {
            card,
            x_value,
            sacrifice,
            payment,
        } => {
            cast_reshape(state, cards, card, x_value, sacrifice, payment)?;
            Transition::default()
        }
        Action::ActivateRepurposingBay {
            source,
            sacrifice,
            payment,
        } => {
            activate_repurposing_bay(state, cards, source, sacrifice, payment)?;
            Transition::default()
        }
        Action::ActivateTopLook { source, payment } => {
            activate_top_look(state, cards, source, payment)?;
            Transition::default()
        }
        Action::ActivateTopDraw { source } => {
            activate_top_draw(state, cards, source)?;
            Transition::default()
        }
        Action::ActivateUrzaSpin { source, payment } => {
            activate_urza_spin(state, cards, source, payment)?;
            Transition::default()
        }
        Action::ActivateTezzeretMinusThree { source } => {
            activate_tezzeret_minus_three(state, cards, source)?;
            Transition::default()
        }
        Action::PlayUrzaPermission {
            permission_slot,
            face,
        } => play_urza_permission(state, cards, permission_slot, face)?,
        Action::CastCommander { payment } => {
            cast_commander(state, cards, payment)?;
            Transition::default()
        }
        Action::ChooseTransmuteSacrifice { artifact } => {
            choose_transmute_sacrifice(state, cards, artifact)?
        }
        Action::ChooseSearchTarget { target } => choose_search_target(
            state,
            cards,
            target,
            rng.ok_or(RuleError::MissingGameRngContext)?,
        )?,
        Action::PayTransmuteDifference { payment } => {
            pay_transmute_difference(state, cards, payment)?
        }
        Action::ChooseTopOrder { order } => choose_top_order(state, order)?,
        Action::ChooseScry { top, bottom } => choose_scry(state, top, bottom)?,
    };
    state.validate()?;
    Ok(transition)
}

pub fn legal_contingent_actions<D: CardDatabase>(
    information: &InformationState,
    cards: &D,
) -> Vec<Action> {
    match &information.pending {
        ObservedPendingDecision::TutorTarget { source } => {
            let Some(profile) = cards.profile(source.card) else {
                return Vec::new();
            };
            let Some(kind) = profile.simple_tutor else {
                return Vec::new();
            };
            search_actions_from_information(information, cards, |profile| match kind {
                SimpleTutorKind::Spellseeker => profile.search_classes.spellseeker,
                SimpleTutorKind::MerchantScroll => profile.search_classes.merchant_scroll,
                SimpleTutorKind::MysticalTutor => profile.search_classes.mystical_tutor,
            })
        }
        ObservedPendingDecision::WhirTarget { x_value, .. }
        | ObservedPendingDecision::ReshapeTarget { x_value, .. } => {
            let x_value = *x_value;
            search_actions_from_information(information, cards, |profile| {
                profile.is_artifact && profile.mana_value <= x_value
            })
        }
        ObservedPendingDecision::TransmuteTarget { .. } => {
            search_actions_from_information(information, cards, |profile| profile.is_artifact)
        }
        ObservedPendingDecision::BayTarget {
            sacrificed_mana_value,
            ..
        } => {
            let Some(target_mana_value) = sacrificed_mana_value.checked_add(1) else {
                return vec![Action::ChooseSearchTarget { target: None }];
            };
            search_actions_from_information(information, cards, |profile| {
                profile.is_artifact && profile.mana_value == target_mana_value
            })
        }
        ObservedPendingDecision::SagaTarget { .. } => {
            search_actions_from_information(information, cards, |profile| {
                profile.search_classes.saga_iii
            })
        }
        ObservedPendingDecision::TezzeretTarget { .. } => {
            search_actions_from_information(information, cards, |profile| {
                profile.is_artifact && profile.mana_value <= 1
            })
        }
        ObservedPendingDecision::TransmuteSacrifice { .. } => {
            let mut seen = BTreeSet::new();
            information
                .battlefield
                .iter()
                .filter(|permanent| {
                    cards
                        .profile(permanent.card)
                        .is_some_and(|profile| profile.is_artifact)
                })
                .filter_map(|permanent| {
                    seen.insert(permanent.canonical_id).then_some(
                        Action::ChooseTransmuteSacrifice {
                            artifact: permanent.canonical_id,
                        },
                    )
                })
                .collect()
        }
        ObservedPendingDecision::TransmuteDifferencePayment { difference, .. } => {
            let cost = ManaCost {
                generic: difference.0,
                ..ManaCost::default()
            };
            let mut actions: Vec<_> = enumerate_payments(information.mana, cost)
                .into_iter()
                .map(|payment| Action::PayTransmuteDifference {
                    payment: Some(payment),
                })
                .collect();
            actions.push(Action::PayTransmuteDifference { payment: None });
            actions
        }
        ObservedPendingDecision::TopReorder { cards, .. } => unique_permutations(cards)
            .into_iter()
            .map(|order| Action::ChooseTopOrder { order })
            .collect(),
        ObservedPendingDecision::ScryChoice { looked_at, .. } => {
            let mut actions = Vec::new();
            for order in unique_permutations(looked_at) {
                for top_count in 0..=order.len() {
                    let action = Action::ChooseScry {
                        top: order[..top_count].to_vec(),
                        bottom: order[top_count..].to_vec(),
                    };
                    if !actions.contains(&action) {
                        actions.push(action);
                    }
                }
            }
            actions
        }
        _ => Vec::new(),
    }
}

fn search_actions_from_information<D, F>(
    information: &InformationState,
    cards: &D,
    mut eligible: F,
) -> Vec<Action>
where
    D: CardDatabase,
    F: FnMut(CardProfile) -> bool,
{
    let mut library_cards = Vec::new();
    for count in &information.library.remaining_counts {
        if count.count > 0 {
            library_cards.push(count.card);
        }
    }
    library_cards.extend(information.library.known_top.iter().copied());
    library_cards.extend(information.library.known_bottom.iter().copied());
    library_cards.sort_unstable();
    library_cards.dedup();

    let mut actions: Vec<_> = library_cards
        .into_iter()
        .filter(|card| cards.profile(*card).is_some_and(&mut eligible))
        .map(|target| Action::ChooseSearchTarget {
            target: Some(target),
        })
        .collect();
    actions.push(Action::ChooseSearchTarget { target: None });
    actions
}

pub fn advance_phase<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
) -> Result<Transition, RuleError> {
    state.validate()?;
    ensure_no_pending_decision(state)?;
    if !state.stack.is_empty() {
        return Err(RuleError::IllegalTiming);
    }

    if state.phase == Phase::OpponentCycle && state.turn >= HORIZON_TURN {
        return Err(RuleError::HorizonReached);
    }

    state.mana = ManaPool::default();
    let mut transition = Transition::default();

    match state.phase {
        Phase::Untap => {
            if state.turn == 0 {
                state.turn = 1;
            }
            state.land_played_this_turn = false;
            state.spell_cast_this_turn = false;

            let mut permanents = state.battlefield.permanents().to_vec();
            for permanent in &mut permanents {
                let skip_normal_untap = cards
                    .profile(permanent.card)
                    .is_some_and(|profile| profile.skip_normal_untap);
                if !skip_normal_untap {
                    permanent.tapped = false;
                }
                permanent.summoning_sick = false;
            }
            state.battlefield = BattlefieldZone::new(permanents);
            state.phase = Phase::Upkeep;
            state.window = Window::Priority;
        }
        Phase::Upkeep => {
            let drawn = draw_cards(state, 1)?;
            state.phase = Phase::Draw;
            state.window = Window::Priority;
            transition
                .observations
                .push(RulesObservation::CardsDrawn(drawn));
        }
        Phase::Draw => {
            advance_saga_lore(state)?;
            state.phase = Phase::PrecombatMain;
            state.window = Window::Priority;
        }
        Phase::PrecombatMain => {
            state.phase = Phase::EndStep;
            state.window = Window::Priority;
        }
        Phase::EndStep => {
            expire_urza_permissions(state);
            state.phase = Phase::OpponentCycle;
            state.window = Window::None;
        }
        Phase::OpponentCycle => {
            state.turn = state
                .turn
                .checked_add(1)
                .ok_or(RuleError::ArithmeticOverflow)?;
            state.phase = Phase::Untap;
            state.window = Window::None;
        }
    }

    state.validate()?;
    Ok(transition)
}

pub fn advance_automatic<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
) -> Result<Transition, RuleError> {
    state.validate()?;
    ensure_no_pending_decision(state)?;
    if !state.stack.is_empty() {
        return Err(RuleError::IllegalTiming);
    }

    let mut transition = Transition::default();
    while let (Phase::OpponentCycle, Window::None) | (Phase::Untap, Window::None) =
        (state.phase, state.window)
    {
        let next = advance_phase(state, cards)?;
        transition.observations.extend(next.observations);
    }

    state.validate()?;
    Ok(transition)
}

pub fn draw_cards(state: &mut TrueState, count: usize) -> Result<Vec<CardDefId>, RuleError> {
    if state.library.cards().len() < count {
        return Err(RuleError::DrawFromEmptyLibrary);
    }

    let mut drawn = Vec::with_capacity(count);
    for _ in 0..count {
        let old_cards = state.library.cards();
        let old_len = old_cards.len();
        let card = old_cards[0];
        let mut knowledge = state.library.knowledge();

        if knowledge.known_top > 0 {
            knowledge.known_top -= 1;
        } else if usize::from(knowledge.known_bottom) == old_len {
            knowledge.known_bottom -= 1;
        }

        state.library = TrueLibrary::new(old_cards[1..].to_vec(), knowledge)?;
        state.hand.insert(card);
        drawn.push(card);
    }
    Ok(drawn)
}

pub fn shuffle_library(
    state: &mut TrueState,
    root: RootSeed,
    world: WorldId,
    event_type: EventType,
    logical_event: LogicalEventId,
    concrete_fingerprint: [u8; 16],
) -> Result<EventOccurrence, RuleError> {
    let occurrence = EventOccurrence(state.rng_occurrence_cursor);
    let next_occurrence = state
        .rng_occurrence_cursor
        .checked_add(1)
        .ok_or(RuleError::RngOccurrenceExhausted)?;

    let coordinate = RngCoordinate {
        domain: RngDomain::Game,
        world,
        event_type,
        logical_event,
        occurrence,
        concrete_fingerprint,
    };
    urza_rng::shuffle(state.library.cards_mut(), root, coordinate);
    state.library.set_knowledge(LibraryKnowledge::default())?;
    state.rng_occurrence_cursor = next_occurrence;
    Ok(occurrence)
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum WinFamily {
    BasaltGadgeteer,
}

impl WinFamily {
    pub fn label(self) -> &'static str {
        match self {
            Self::BasaltGadgeteer => "Basalt + Gadgeteer",
        }
    }
}

pub fn detect_terminal_win<D: CardDatabase>(
    information: &InformationState,
    cards: &D,
) -> Option<WinFamily> {
    if !information.stack.is_empty()
        || !matches!(information.pending, ObservedPendingDecision::None)
    {
        return None;
    }

    let urza_present = information.battlefield.iter().any(|permanent| {
        cards
            .profile(permanent.card)
            .is_some_and(|profile| profile.role == R2CardRole::UrzaCommander)
    });
    if !urza_present {
        return None;
    }

    let gadgeteer_present = information.battlefield.iter().any(|permanent| {
        cards.profile(permanent.card).is_some_and(|profile| {
            profile.engine == EngineKind::ForensicGadgeteer
        })
    });
    let ready_basalt = information.battlefield.iter().any(|permanent| {
        !permanent.tapped
            && cards.profile(permanent.card).is_some_and(|profile| {
                profile.engine == EngineKind::BasaltMonolith
            })
    });

    (gadgeteer_present && ready_basalt).then_some(WinFamily::BasaltGadgeteer)
}

pub fn observe_library_search<F>(state: &TrueState, mut eligible: F) -> LibrarySearchObservation
where
    F: FnMut(CardDefId) -> bool,
{
    let mut candidates: Vec<_> = state
        .library
        .cards()
        .iter()
        .copied()
        .filter(|card| eligible(*card))
        .collect();
    candidates.sort_unstable();
    candidates.dedup();
    LibrarySearchObservation { candidates }
}

fn pass_priority<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    rng: Option<GameRngContext>,
) -> Result<Transition, RuleError> {
    ensure_priority(state)?;
    ensure_no_pending_decision(state)?;

    if state.stack.is_empty() {
        return advance_phase(state, cards);
    }

    resolve_top_stack_object(state, cards, rng)
}

fn play_land<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    card: CardDefId,
    entry: LandEntryChoice,
) -> Result<Transition, RuleError> {
    ensure_sorcery_window(state)?;
    if state.land_played_this_turn {
        return Err(RuleError::LandAlreadyPlayed);
    }

    let profile = card_profile(cards, card)?;
    if profile.role != R2CardRole::Land {
        return Err(RuleError::UnsupportedCardMechanic(card));
    }
    if !state.hand.cards().contains(&card) {
        return Err(RuleError::CardNotInHand(card));
    }

    let object_id = next_object_id(state)?;
    let tapped = match profile.land_entry {
        LandEntryRule::Untapped => {
            if entry != LandEntryChoice::Default {
                return Err(RuleError::InvalidLandEntryChoice(card));
            }
            false
        }
        LandEntryRule::PayLifeOrTapped { life } => match entry {
            LandEntryChoice::Default => true,
            LandEntryChoice::PayLife => {
                let life = u16::from(life);
                if state.life < life {
                    return Err(RuleError::InsufficientLife {
                        required: life,
                        available: state.life,
                    });
                }
                state.life -= life;
                false
            }
        },
        LandEntryRule::None => return Err(RuleError::UnsupportedCardMechanic(card)),
    };

    let removed = state.hand.remove_one(card);
    debug_assert!(removed);
    let saga = profile.utility == UtilityKind::UrzasSaga;
    insert_permanent(
        state,
        PermanentState {
            object_id,
            card,
            face: profile.battlefield_face,
            tapped,
            summoning_sick: false,
            token: false,
            counters: if saga {
                CounterState {
                    lore: 1,
                    ..CounterState::default()
                }
            } else {
                CounterState::default()
            },
            mode: if saga {
                PermanentMode::UrzasSaga
            } else {
                PermanentMode::Normal
            },
            attached_to: None,
            granted_ability: None,
        },
    );
    if saga {
        state.stack.push(StackObject::ControlledTrigger {
            source: SourceRef {
                object_id: Some(object_id),
                card,
            },
            ability: ABILITY_SAGA_CHAPTER_I,
        });
    }
    state.land_played_this_turn = true;
    Ok(Transition {
        observations: vec![RulesObservation::PermanentEntered {
            card,
            face: profile.battlefield_face,
            token: false,
        }],
    })
}

fn activate_mana_ability<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    source: ObjectId,
) -> Result<(), RuleError> {
    ensure_mana_activation_window(state)?;

    let permanent = battlefield_permanent(state, source)?.clone();
    if permanent.tapped {
        return Err(RuleError::PermanentTapped(source));
    }
    let profile = card_profile(cards, permanent.card)?;
    let ability = if profile.mana_ability != ManaAbility::None {
        profile.mana_ability
    } else if permanent.granted_ability == Some(urza_core::GrantedAbility::SagaColorlessMana) {
        ManaAbility::TapForColorless(1)
    } else {
        ManaAbility::None
    };
    if ability == ManaAbility::None {
        return Err(RuleError::NotManaSource(source));
    }

    let mut mana = state.mana;
    let mut life = state.life;
    match ability {
        ManaAbility::None => unreachable!("checked above"),
        ManaAbility::TapForBlue => add_blue(&mut mana, 1)?,
        ManaAbility::TapForColorless(amount) => add_colorless(&mut mana, amount)?,
        ManaAbility::TapForBlueAndDamage { damage } => {
            add_blue(&mut mana, 1)?;
            life = life.saturating_sub(damage);
        }
        ManaAbility::TapForColorlessAndDamage {
            mana: amount,
            damage,
        } => {
            add_colorless(&mut mana, amount)?;
            life = life.saturating_sub(damage);
        }
    }

    set_tapped(state, source)?;
    state.mana = mana;
    state.life = life;
    Ok(())
}

fn activate_native_artifact_untap<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    source: ObjectId,
    payment: ManaPayment,
) -> Result<(), RuleError> {
    ensure_priority(state)?;
    ensure_no_pending_decision(state)?;

    let permanent = battlefield_permanent(state, source)?.clone();
    let profile = card_profile(cards, permanent.card)?;
    if !profile.is_artifact {
        return Err(RuleError::NotArtifact(source));
    }
    let base_generic = profile
        .native_untap_generic
        .ok_or(RuleError::UnsupportedCardMechanic(permanent.card))?;
    let cost = reduced_artifact_activation_cost(state, cards, source, base_generic)?;
    validate_payment(state.mana, payment, cost)?;

    spend_payment(&mut state.mana, payment);
    state.stack.push(StackObject::ActivatedAbility {
        source: SourceRef {
            object_id: Some(source),
            card: permanent.card,
        },
        ability: ABILITY_NATIVE_ARTIFACT_UNTAP,
        parameter: None,
    });
    state.window = Window::Priority;
    Ok(())
}

fn activate_urza_artifact_mana<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    artifact: ObjectId,
) -> Result<(), RuleError> {
    ensure_mana_activation_window(state)?;

    let urza_present = state
        .battlefield
        .permanents()
        .iter()
        .any(|permanent| permanent.card == cards.commander_card());
    if !urza_present {
        return Err(RuleError::UrzaNotOnBattlefield);
    }

    let permanent = battlefield_permanent(state, artifact)?.clone();
    if permanent.tapped {
        return Err(RuleError::PermanentTapped(artifact));
    }
    if !card_profile(cards, permanent.card)?.is_artifact {
        return Err(RuleError::NotArtifact(artifact));
    }

    let blue = state
        .mana
        .blue
        .checked_add(1)
        .ok_or(RuleError::ArithmeticOverflow)?;
    set_tapped(state, artifact)?;
    state.mana.blue = blue;
    Ok(())
}

fn activate_top_look<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    source: ObjectId,
    payment: ManaPayment,
) -> Result<(), RuleError> {
    ensure_priority(state)?;
    ensure_no_pending_decision(state)?;
    let card = battlefield_permanent(state, source)?.card;
    let profile = card_profile(cards, card)?;
    if profile.utility != UtilityKind::SenseisDiviningTop {
        return Err(RuleError::UnsupportedCardMechanic(card));
    }
    let cost = reduced_artifact_activation_cost(state, cards, source, 1)?;
    validate_payment(state.mana, payment, cost)?;
    spend_payment(&mut state.mana, payment);
    state.stack.push(StackObject::ActivatedAbility {
        source: SourceRef {
            object_id: Some(source),
            card,
        },
        ability: ABILITY_TOP_LOOK,
        parameter: None,
    });
    state.window = Window::Priority;
    Ok(())
}

fn activate_top_draw<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    source: ObjectId,
) -> Result<(), RuleError> {
    ensure_priority(state)?;
    ensure_no_pending_decision(state)?;
    let permanent = battlefield_permanent(state, source)?.clone();
    let profile = card_profile(cards, permanent.card)?;
    if profile.utility != UtilityKind::SenseisDiviningTop {
        return Err(RuleError::UnsupportedCardMechanic(permanent.card));
    }
    if permanent.tapped {
        return Err(RuleError::PermanentTapped(source));
    }
    set_tapped(state, source)?;
    state.stack.push(StackObject::ActivatedAbility {
        source: SourceRef {
            object_id: Some(source),
            card: permanent.card,
        },
        ability: ABILITY_TOP_DRAW,
        parameter: None,
    });
    state.window = Window::Priority;
    Ok(())
}

fn activate_urza_spin<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    source: ObjectId,
    payment: ManaPayment,
) -> Result<(), RuleError> {
    ensure_priority(state)?;
    ensure_no_pending_decision(state)?;
    let card = battlefield_permanent(state, source)?.card;
    if card != cards.commander_card() {
        return Err(RuleError::UrzaNotOnBattlefield);
    }
    let cost = ManaCost {
        generic: 5,
        ..ManaCost::default()
    };
    validate_payment(state.mana, payment, cost)?;
    spend_payment(&mut state.mana, payment);
    state.stack.push(StackObject::ActivatedAbility {
        source: SourceRef {
            object_id: Some(source),
            card,
        },
        ability: ABILITY_URZA_SPIN,
        parameter: None,
    });
    state.window = Window::Priority;
    Ok(())
}

fn activate_tezzeret_minus_three<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    source: ObjectId,
) -> Result<(), RuleError> {
    ensure_sorcery_window(state)?;
    let permanent = battlefield_permanent(state, source)?.clone();
    let profile = card_profile(cards, permanent.card)?;
    if profile.utility != UtilityKind::TezzeretCruelCaptain {
        return Err(RuleError::UnsupportedCardMechanic(permanent.card));
    }
    if permanent.counters.loyalty < 3 {
        return Err(RuleError::IllegalTiming);
    }

    let mut permanents = state.battlefield.permanents().to_vec();
    let live = permanents
        .iter_mut()
        .find(|candidate| candidate.object_id == source)
        .ok_or(RuleError::MissingPermanent(source))?;
    live.counters.loyalty -= 3;
    state.battlefield = BattlefieldZone::new(permanents);
    state.stack.push(StackObject::ActivatedAbility {
        source: SourceRef {
            object_id: Some(source),
            card: permanent.card,
        },
        ability: ABILITY_TEZZERET_MINUS_THREE,
        parameter: None,
    });
    state.window = Window::Priority;
    Ok(())
}

fn play_urza_permission<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    permission_slot: u16,
    face: CardFace,
) -> Result<Transition, RuleError> {
    let permission_id = resolve_permission_slot(state, permission_slot)
        .map_err(|error| match error {
            urza_info::ObservationError::InvalidState(error) => RuleError::InvalidState(error),
        })?
        .ok_or(RuleError::MissingPermissionSlot(permission_slot))?;
    let permission = state
        .urza_permissions
        .iter()
        .find(|permission| permission.permission_id == permission_id)
        .cloned()
        .ok_or(RuleError::MissingPermissionSlot(permission_slot))?;
    if permission.expires_turn < state.turn {
        return Err(RuleError::MissingPermissionSlot(permission_slot));
    }
    if !state.exile.cards().contains(&permission.card) {
        return Err(RuleError::PermissionCardNotInExile);
    }
    let profile = card_profile(cards, permission.card)?;

    if profile.role == R2CardRole::Land {
        ensure_sorcery_window(state)?;
        if state.land_played_this_turn {
            return Err(RuleError::LandAlreadyPlayed);
        }
        if face != profile.battlefield_face {
            return Err(RuleError::InvalidPermissionFace);
        }
        let object_id = next_object_id(state)?;
        let removed = state.exile.remove_one(permission.card);
        debug_assert!(removed);
        let saga = profile.utility == UtilityKind::UrzasSaga;
        insert_permanent(
            state,
            PermanentState {
                object_id,
                card: permission.card,
                face,
                tapped: false,
                summoning_sick: false,
                token: false,
                counters: if saga {
                    CounterState {
                        lore: 1,
                        ..CounterState::default()
                    }
                } else {
                    CounterState::default()
                },
                mode: if saga {
                    PermanentMode::UrzasSaga
                } else {
                    PermanentMode::Normal
                },
                attached_to: None,
                granted_ability: None,
            },
        );
        if saga {
            state.stack.push(StackObject::ControlledTrigger {
                source: SourceRef {
                    object_id: Some(object_id),
                    card: permission.card,
                },
                ability: ABILITY_SAGA_CHAPTER_I,
            });
        }
        state.land_played_this_turn = true;
        consume_permission(state, permission_id);
        return Ok(Transition {
            observations: vec![RulesObservation::PermanentEntered {
                card: permission.card,
                face,
                token: false,
            }],
        });
    }

    if face != CardFace::Front {
        return Err(RuleError::InvalidPermissionFace);
    }
    match profile.role {
        R2CardRole::ArtifactPermanent
        | R2CardRole::CreaturePermanent
        | R2CardRole::PlaneswalkerPermanent => ensure_sorcery_window(state)?,
        R2CardRole::SearchSpell => {
            let instant = profile
                .simple_tutor
                .is_some_and(SimpleTutorKind::instant_speed)
                || profile.special_search == SpecialSearchKind::Whir;
            if instant {
                ensure_priority(state)?;
                ensure_no_pending_decision(state)?;
            } else {
                ensure_sorcery_window(state)?;
            }
            if profile.special_search == SpecialSearchKind::Reshape {
                return Err(RuleError::UnsupportedCardMechanic(permission.card));
            }
        }
        _ => return Err(RuleError::UnsupportedCardMechanic(permission.card)),
    }

    let object_id = next_object_id(state)?;
    let removed = state.exile.remove_one(permission.card);
    debug_assert!(removed);
    state.stack.push(StackObject::Spell {
        object_id,
        card: permission.card,
        x_value: matches!(
            profile.special_search,
            SpecialSearchKind::Whir | SpecialSearchKind::Reshape
        )
        .then_some(0),
    });
    state.spell_cast_this_turn = true;
    state.window = Window::Priority;
    consume_permission(state, permission_id);
    Ok(Transition::default())
}

fn cast_from_hand<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    card: CardDefId,
    payment: ManaPayment,
) -> Result<(), RuleError> {
    let profile = card_profile(cards, card)?;
    match profile.role {
        R2CardRole::SearchSpell => match profile.special_search {
            SpecialSearchKind::None => {
                let kind = profile
                    .simple_tutor
                    .ok_or(RuleError::UnsupportedCardMechanic(card))?;
                if kind.instant_speed() {
                    ensure_priority(state)?;
                    ensure_no_pending_decision(state)?;
                } else {
                    ensure_sorcery_window(state)?;
                }
            }
            SpecialSearchKind::TransmuteArtifact => ensure_sorcery_window(state)?,
            SpecialSearchKind::Whir | SpecialSearchKind::Reshape => {
                return Err(RuleError::UnsupportedCardMechanic(card));
            }
            SpecialSearchKind::RepurposingBay => {
                return Err(RuleError::UnsupportedCardMechanic(card));
            }
        },
        R2CardRole::ArtifactPermanent
        | R2CardRole::CreaturePermanent
        | R2CardRole::PlaneswalkerPermanent
        | R2CardRole::UrzaCommander => ensure_sorcery_window(state)?,
        _ => return Err(RuleError::UnsupportedCardMechanic(card)),
    }

    cast_paid_spell(state, cards, card, payment, None)
}

fn cast_whir<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    card: CardDefId,
    x_value: u16,
    payment: ManaPayment,
    improvise_sources: &[ObjectId],
) -> Result<(), RuleError> {
    ensure_priority(state)?;
    ensure_no_pending_decision(state)?;
    let profile = card_profile(cards, card)?;
    if profile.role != R2CardRole::SearchSpell || profile.special_search != SpecialSearchKind::Whir
    {
        return Err(RuleError::UnsupportedCardMechanic(card));
    }
    if !state.hand.cards().contains(&card) {
        return Err(RuleError::CardNotInHand(card));
    }

    let mut unique = BTreeSet::new();
    for source in improvise_sources {
        if !unique.insert(*source) {
            return Err(RuleError::DuplicateCostObject(*source));
        }
        let permanent = battlefield_permanent(state, *source)?;
        if permanent.tapped || !card_profile(cards, permanent.card)?.is_artifact {
            return Err(RuleError::InvalidSacrifice(*source));
        }
    }
    let improvise_count =
        u16::try_from(improvise_sources.len()).map_err(|_| RuleError::ArithmeticOverflow)?;
    let Some(remaining_x) = x_value.checked_sub(improvise_count) else {
        return Err(RuleError::ExcessImprovise { x_value });
    };
    let cost = ManaCost {
        blue: 3,
        generic: remaining_x,
        ..ManaCost::default()
    };
    validate_payment(state.mana, payment, cost)?;
    let object_id = next_object_id(state)?;

    spend_payment(&mut state.mana, payment);
    for source in improvise_sources {
        set_tapped(state, *source)?;
    }
    let removed = state.hand.remove_one(card);
    debug_assert!(removed);
    state.stack.push(StackObject::Spell {
        object_id,
        card,
        x_value: Some(x_value),
    });
    state.spell_cast_this_turn = true;
    state.window = Window::Priority;
    Ok(())
}

fn cast_reshape<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    card: CardDefId,
    x_value: u16,
    sacrifice: ObjectId,
    payment: ManaPayment,
) -> Result<(), RuleError> {
    ensure_sorcery_window(state)?;
    let profile = card_profile(cards, card)?;
    if profile.role != R2CardRole::SearchSpell
        || profile.special_search != SpecialSearchKind::Reshape
    {
        return Err(RuleError::UnsupportedCardMechanic(card));
    }
    if !state.hand.cards().contains(&card) {
        return Err(RuleError::CardNotInHand(card));
    }
    validate_sacrifice_artifact(state, cards, sacrifice)?;
    let cost = ManaCost {
        blue: 2,
        generic: x_value,
        ..ManaCost::default()
    };
    validate_payment(state.mana, payment, cost)?;
    let object_id = next_object_id(state)?;

    spend_payment(&mut state.mana, payment);
    sacrifice_artifact(state, sacrifice)?;
    let removed = state.hand.remove_one(card);
    debug_assert!(removed);
    state.stack.push(StackObject::Spell {
        object_id,
        card,
        x_value: Some(x_value),
    });
    state.spell_cast_this_turn = true;
    state.window = Window::Priority;
    Ok(())
}

fn activate_repurposing_bay<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    source: ObjectId,
    sacrifice: ObjectId,
    payment: ManaPayment,
) -> Result<(), RuleError> {
    ensure_sorcery_window(state)?;
    if source == sacrifice {
        return Err(RuleError::BayCannotSacrificeSelf);
    }
    let bay = battlefield_permanent(state, source)?.clone();
    if bay.tapped {
        return Err(RuleError::PermanentTapped(source));
    }
    let bay_profile = card_profile(cards, bay.card)?;
    if bay_profile.special_search != SpecialSearchKind::RepurposingBay {
        return Err(RuleError::UnsupportedCardMechanic(bay.card));
    }
    let sacrificed = validate_sacrifice_artifact(state, cards, sacrifice)?;
    let cost = reduced_artifact_activation_cost(state, cards, source, 2)?;
    validate_payment(state.mana, payment, cost)?;

    spend_payment(&mut state.mana, payment);
    set_tapped(state, source)?;
    sacrifice_artifact(state, sacrifice)?;
    state.stack.push(StackObject::ActivatedAbility {
        source: SourceRef {
            object_id: Some(source),
            card: bay.card,
        },
        ability: ABILITY_REPURPOSING_BAY_SEARCH,
        parameter: Some(sacrificed.mana_value),
    });
    state.window = Window::Priority;
    Ok(())
}

fn cast_paid_spell<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    card: CardDefId,
    payment: ManaPayment,
    x_value: Option<u16>,
) -> Result<(), RuleError> {
    let profile = card_profile(cards, card)?;
    if !state.hand.cards().contains(&card) {
        return Err(RuleError::CardNotInHand(card));
    }
    if card == cards.commander_card() && state.commander.zone != CommanderZone::Hand {
        return Err(RuleError::CommanderNotInHand);
    }
    let Some(cost) = profile.mana_cost else {
        return Err(RuleError::UnsupportedCardMechanic(card));
    };

    validate_payment(state.mana, payment, cost)?;
    let object_id = next_object_id(state)?;
    spend_payment(&mut state.mana, payment);
    let removed = state.hand.remove_one(card);
    debug_assert!(removed);

    state.stack.push(StackObject::Spell {
        object_id,
        card,
        x_value,
    });
    state.spell_cast_this_turn = true;
    state.window = Window::Priority;
    if card == cards.commander_card() {
        state.commander.zone = CommanderZone::Stack;
    }
    Ok(())
}

fn cast_commander<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    payment: ManaPayment,
) -> Result<(), RuleError> {
    ensure_sorcery_window(state)?;
    if state.commander.zone != CommanderZone::CommandZone {
        return Err(RuleError::CommanderNotInCommandZone);
    }

    let commander = cards.commander_card();
    let profile = card_profile(cards, commander)?;
    if profile.role != R2CardRole::UrzaCommander {
        return Err(RuleError::UnsupportedCardMechanic(commander));
    }
    let Some(base_cost) = profile.mana_cost else {
        return Err(RuleError::UnsupportedCardMechanic(commander));
    };
    let tax = u16::from(state.commander.command_zone_casts)
        .checked_mul(2)
        .ok_or(RuleError::ArithmeticOverflow)?;
    let cost = base_cost.with_additional_generic(tax)?;

    validate_payment(state.mana, payment, cost)?;
    let object_id = next_object_id(state)?;
    let next_cast_count = state
        .commander
        .command_zone_casts
        .checked_add(1)
        .ok_or(RuleError::ArithmeticOverflow)?;

    spend_payment(&mut state.mana, payment);
    state.stack.push(StackObject::Spell {
        object_id,
        card: commander,
        x_value: None,
    });
    state.commander.zone = CommanderZone::Stack;
    state.commander.command_zone_casts = next_cast_count;
    state.spell_cast_this_turn = true;
    state.window = Window::Priority;
    Ok(())
}

fn resolve_top_stack_object<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    rng: Option<GameRngContext>,
) -> Result<Transition, RuleError> {
    let Some(top) = state.stack.last().cloned() else {
        return Ok(Transition::default());
    };

    match top {
        StackObject::Spell {
            object_id,
            card,
            x_value,
        } => resolve_spell(state, cards, object_id, card, x_value),
        StackObject::ActivatedAbility {
            source,
            ability,
            parameter,
        } if ability == ABILITY_REPURPOSING_BAY_SEARCH => {
            let Some(sacrificed_mana_value) = parameter else {
                return Err(RuleError::UnsupportedStackObject);
            };
            state.stack.pop();
            stage_parameterized_search(
                state,
                cards,
                PendingDecision::BayTarget {
                    source,
                    sacrificed_mana_value,
                },
            )
        }
        StackObject::ActivatedAbility {
            source,
            ability: ABILITY_TOP_LOOK,
            ..
        } => {
            state.stack.pop();
            stage_top_reorder(state, source)
        }
        StackObject::ActivatedAbility {
            source,
            ability: ABILITY_TOP_DRAW,
            ..
        } => {
            state.stack.pop();
            resolve_top_draw(state, source)
        }
        StackObject::ActivatedAbility {
            source,
            ability: ABILITY_URZA_SPIN,
            ..
        } => {
            let rng = rng.ok_or(RuleError::MissingGameRngContext)?;
            state.stack.pop();
            resolve_urza_spin(state, source, rng)
        }
        StackObject::ControlledTrigger {
            source,
            ability: ABILITY_SAGA_CHAPTER_I,
        } => {
            state.stack.pop();
            resolve_saga_chapter_i(state, source)
        }
        StackObject::ControlledTrigger {
            source,
            ability: ABILITY_SAGA_CHAPTER_II,
        } => {
            state.stack.pop();
            resolve_saga_chapter_ii(state, cards, source)
        }
        StackObject::ControlledTrigger {
            source,
            ability: ABILITY_SAGA_CHAPTER_III,
        } => {
            state.stack.pop();
            stage_parameterized_search(state, cards, PendingDecision::SagaTarget { source })
        }
        StackObject::ActivatedAbility {
            source,
            ability: ABILITY_TEZZERET_MINUS_THREE,
            ..
        } => {
            state.stack.pop();
            stage_parameterized_search(state, cards, PendingDecision::TezzeretTarget { source })
        }
        StackObject::ActivatedAbility {
            source,
            ability: ABILITY_NATIVE_ARTIFACT_UNTAP,
            ..
        } => {
            state.stack.pop();
            if let Some(object_id) = source.object_id
                && state
                    .battlefield
                    .get(object_id)
                    .is_some_and(|permanent| permanent.card == source.card)
            {
                set_untapped(state, object_id)?;
            }
            state.window = Window::Priority;
            Ok(Transition::default())
        }
        StackObject::ControlledTrigger { .. } | StackObject::ActivatedAbility { .. } => {
            Err(RuleError::UnsupportedStackObject)
        }
    }
}

fn resolve_spell<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    object_id: ObjectId,
    card: CardDefId,
    x_value: Option<u16>,
) -> Result<Transition, RuleError> {
    let profile = card_profile(cards, card)?;
    if !matches!(
        profile.role,
        R2CardRole::ArtifactPermanent
            | R2CardRole::CreaturePermanent
            | R2CardRole::PlaneswalkerPermanent
            | R2CardRole::SearchSpell
            | R2CardRole::UrzaCommander
    ) {
        return Err(RuleError::UnsupportedCardMechanic(card));
    }

    if profile.role == R2CardRole::SearchSpell {
        state.stack.pop();
        state.window = Window::Resolving;
        state.graveyard.insert(card);
        let source = SourceRef {
            object_id: None,
            card,
        };
        if profile.simple_tutor.is_some() {
            return stage_simple_tutor(state, cards, source);
        }
        return match profile.special_search {
            SpecialSearchKind::Whir => {
                let x_value = x_value.ok_or(RuleError::UnsupportedStackObject)?;
                stage_parameterized_search(
                    state,
                    cards,
                    PendingDecision::WhirTarget { source, x_value },
                )
            }
            SpecialSearchKind::Reshape => {
                let x_value = x_value.ok_or(RuleError::UnsupportedStackObject)?;
                stage_parameterized_search(
                    state,
                    cards,
                    PendingDecision::ReshapeTarget { source, x_value },
                )
            }
            SpecialSearchKind::TransmuteArtifact => {
                state.pending = PendingDecision::TransmuteSacrifice { source };
                state.window = Window::Resolving;
                Ok(Transition::default())
            }
            SpecialSearchKind::None | SpecialSearchKind::RepurposingBay => {
                Err(RuleError::UnsupportedCardMechanic(card))
            }
        };
    }

    let construct = if profile.role == R2CardRole::UrzaCommander {
        let construct_id = next_object_id(state)?;
        let construct_card = cards.urza_construct_token_card();
        let construct_profile = card_profile(cards, construct_card)?;
        if construct_profile.role != R2CardRole::UrzaConstructToken
            || !construct_profile.is_artifact
            || !construct_profile.is_creature
        {
            return Err(RuleError::UnsupportedCardMechanic(construct_card));
        }
        Some((construct_id, construct_card, construct_profile))
    } else {
        None
    };

    state.stack.pop();
    state.window = Window::Resolving;
    insert_permanent(
        state,
        PermanentState {
            object_id,
            card,
            face: profile.battlefield_face,
            tapped: false,
            summoning_sick: profile.is_creature,
            token: false,
            counters: CounterState {
                loyalty: profile.starting_loyalty,
                ..CounterState::default()
            },
            mode: PermanentMode::Normal,
            attached_to: None,
            granted_ability: None,
        },
    );

    let mut observations = vec![RulesObservation::PermanentEntered {
        card,
        face: profile.battlefield_face,
        token: false,
    }];

    if let Some((construct_id, construct_card, construct_profile)) = construct {
        state.commander.zone = CommanderZone::Battlefield;
        insert_permanent(
            state,
            PermanentState {
                object_id: construct_id,
                card: construct_card,
                face: construct_profile.battlefield_face,
                tapped: false,
                summoning_sick: true,
                token: true,
                counters: CounterState::default(),
                mode: PermanentMode::Normal,
                attached_to: None,
                granted_ability: None,
            },
        );
        observations.push(RulesObservation::PermanentEntered {
            card: construct_card,
            face: construct_profile.battlefield_face,
            token: true,
        });
    }

    if profile.simple_tutor.is_some() {
        let staged = stage_simple_tutor(
            state,
            cards,
            SourceRef {
                object_id: Some(object_id),
                card,
            },
        )?;
        observations.extend(staged.observations);
    } else {
        state.window = Window::Priority;
    }

    Ok(Transition { observations })
}

fn advance_saga_lore(state: &mut TrueState) -> Result<(), RuleError> {
    let mut permanents = state.battlefield.permanents().to_vec();
    let mut triggers = Vec::new();
    for permanent in &mut permanents {
        if permanent.mode != PermanentMode::UrzasSaga {
            continue;
        }
        permanent.counters.lore = permanent
            .counters
            .lore
            .checked_add(1)
            .ok_or(RuleError::ArithmeticOverflow)?;
        let ability = match permanent.counters.lore {
            2 => Some(ABILITY_SAGA_CHAPTER_II),
            3 => Some(ABILITY_SAGA_CHAPTER_III),
            _ => None,
        };
        if let Some(ability) = ability {
            triggers.push(StackObject::ControlledTrigger {
                source: SourceRef {
                    object_id: Some(permanent.object_id),
                    card: permanent.card,
                },
                ability,
            });
        }
    }
    state.battlefield = BattlefieldZone::new(permanents);
    state.stack.extend(triggers);
    Ok(())
}

fn resolve_saga_chapter_i(
    state: &mut TrueState,
    source: SourceRef,
) -> Result<Transition, RuleError> {
    if let Some(object_id) = source.object_id
        && state.battlefield.get(object_id).is_some()
    {
        let mut permanents = state.battlefield.permanents().to_vec();
        if let Some(saga) = permanents
            .iter_mut()
            .find(|permanent| permanent.object_id == object_id)
        {
            saga.granted_ability = Some(urza_core::GrantedAbility::SagaColorlessMana);
        }
        state.battlefield = BattlefieldZone::new(permanents);
    }
    state.window = Window::Priority;
    Ok(Transition::default())
}

fn resolve_saga_chapter_ii<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    _source: SourceRef,
) -> Result<Transition, RuleError> {
    let construct = cards.urza_construct_token_card();
    let profile = card_profile(cards, construct)?;
    let object_id = next_object_id(state)?;
    insert_permanent(
        state,
        PermanentState {
            object_id,
            card: construct,
            face: profile.battlefield_face,
            tapped: false,
            summoning_sick: true,
            token: true,
            counters: CounterState::default(),
            mode: PermanentMode::Normal,
            attached_to: None,
            granted_ability: None,
        },
    );
    state.window = Window::Priority;
    Ok(Transition {
        observations: vec![RulesObservation::PermanentEntered {
            card: construct,
            face: profile.battlefield_face,
            token: true,
        }],
    })
}

fn sacrifice_saga_after_final_chapter(
    state: &mut TrueState,
    source: SourceRef,
) -> Result<(), RuleError> {
    let Some(object_id) = source.object_id else {
        return Ok(());
    };
    let Some(permanent) = state.battlefield.get(object_id) else {
        return Ok(());
    };
    if permanent.card != source.card || permanent.mode != PermanentMode::UrzasSaga {
        return Ok(());
    }
    let mut permanents = state.battlefield.permanents().to_vec();
    let index = permanents
        .iter()
        .position(|candidate| candidate.object_id == object_id)
        .ok_or(RuleError::MissingPermanent(object_id))?;
    let saga = permanents.remove(index);
    state.battlefield = BattlefieldZone::new(permanents);
    if !saga.token {
        state.graveyard.insert(saga.card);
    }
    Ok(())
}

fn stage_top_reorder(state: &mut TrueState, source: SourceRef) -> Result<Transition, RuleError> {
    let count = state.library.cards().len().min(3);
    let cards = state.library.cards()[..count].to_vec();
    mark_known_top(state, count)?;
    state.pending = PendingDecision::TopReorder {
        source,
        cards: cards.clone(),
    };
    state.window = Window::PostObservation;
    Ok(Transition {
        observations: vec![RulesObservation::TopCardsObserved {
            source: source.card,
            cards,
        }],
    })
}

pub fn stage_scry(
    state: &mut TrueState,
    source: SourceRef,
    count: usize,
) -> Result<Transition, RuleError> {
    state.validate()?;
    ensure_no_pending_decision(state)?;
    let count = count.min(state.library.cards().len());
    let looked_at = state.library.cards()[..count].to_vec();
    mark_known_top(state, count)?;
    state.pending = PendingDecision::ScryChoice {
        source,
        looked_at: looked_at.clone(),
    };
    state.window = Window::PostObservation;
    state.validate()?;
    Ok(Transition {
        observations: vec![RulesObservation::ScryCardsObserved {
            source: source.card,
            cards: looked_at,
        }],
    })
}

fn mark_known_top(state: &mut TrueState, count: usize) -> Result<(), RuleError> {
    let old = state.library.knowledge();
    let len = state.library.cards().len();
    let known_top = u8::try_from(count).map_err(|_| RuleError::ArithmeticOverflow)?;
    let remaining = len.saturating_sub(count);
    let known_bottom = old
        .known_bottom
        .min(u8::try_from(remaining).map_err(|_| RuleError::ArithmeticOverflow)?);
    state.library.set_knowledge(LibraryKnowledge {
        known_top,
        known_bottom,
    })?;
    Ok(())
}

fn choose_top_order(state: &mut TrueState, order: Vec<CardDefId>) -> Result<Transition, RuleError> {
    if state.window != Window::PostObservation {
        return Err(RuleError::SearchDecisionMismatch);
    }
    let PendingDecision::TopReorder { cards, .. } = state.pending.clone() else {
        return Err(RuleError::SearchDecisionMismatch);
    };
    if !same_multiset(&cards, &order) {
        return Err(RuleError::InvalidObservedCardOrdering);
    }
    let count = cards.len();
    let mut library = order;
    library.extend_from_slice(&state.library.cards()[count..]);
    let bottom = state.library.knowledge().known_bottom;
    state.library = TrueLibrary::new(
        library,
        LibraryKnowledge {
            known_top: u8::try_from(count).map_err(|_| RuleError::ArithmeticOverflow)?,
            known_bottom: bottom,
        },
    )?;
    state.pending = PendingDecision::None;
    state.window = Window::Priority;
    Ok(Transition::default())
}

fn choose_scry(
    state: &mut TrueState,
    top: Vec<CardDefId>,
    bottom: Vec<CardDefId>,
) -> Result<Transition, RuleError> {
    if state.window != Window::PostObservation {
        return Err(RuleError::SearchDecisionMismatch);
    }
    let PendingDecision::ScryChoice { looked_at, .. } = state.pending.clone() else {
        return Err(RuleError::SearchDecisionMismatch);
    };
    let mut proposed = top.clone();
    proposed.extend(bottom.iter().copied());
    if !same_multiset(&looked_at, &proposed) {
        return Err(RuleError::InvalidObservedCardOrdering);
    }

    let count = looked_at.len();
    let old_bottom = usize::from(state.library.knowledge().known_bottom);
    let remaining_old_bottom = old_bottom.min(state.library.cards().len().saturating_sub(count));
    let middle = state.library.cards()[count..].to_vec();
    let mut library = top.clone();
    library.extend(middle);
    library.extend(bottom.iter().copied());
    let known_bottom = remaining_old_bottom
        .checked_add(bottom.len())
        .ok_or(RuleError::ArithmeticOverflow)?;
    state.library = TrueLibrary::new(
        library,
        LibraryKnowledge {
            known_top: u8::try_from(top.len()).map_err(|_| RuleError::ArithmeticOverflow)?,
            known_bottom: u8::try_from(known_bottom).map_err(|_| RuleError::ArithmeticOverflow)?,
        },
    )?;
    state.pending = PendingDecision::None;
    state.window = Window::Priority;
    Ok(Transition::default())
}

fn resolve_top_draw(state: &mut TrueState, source: SourceRef) -> Result<Transition, RuleError> {
    let drawn = draw_cards(state, 1)?;
    let mut observations = vec![RulesObservation::CardsDrawn(drawn)];
    if let Some(object_id) = source.object_id
        && state.battlefield.get(object_id).is_some()
    {
        remove_permanent_to_library_top(state, object_id)?;
    }
    state.window = Window::Priority;
    observations.shrink_to_fit();
    Ok(Transition { observations })
}

fn resolve_urza_spin(
    state: &mut TrueState,
    source: SourceRef,
    rng: GameRngContext,
) -> Result<Transition, RuleError> {
    let fingerprint = library_fingerprint(state.library.cards());
    shuffle_library(
        state,
        rng.root,
        rng.world,
        RNG_EVENT_URZA_SPIN_SHUFFLE,
        rng.logical_event,
        fingerprint,
    )?;
    if state.library.cards().is_empty() {
        state.window = Window::Priority;
        return Ok(Transition::default());
    }

    let card = state.library.cards()[0];
    state.library = TrueLibrary::unknown(state.library.cards()[1..].to_vec());
    state.exile.insert(card);
    let permission_id = next_permission_id(state)?;
    state.urza_permissions.push(urza_core::UrzaPermission {
        permission_id,
        card,
        expires_turn: state.turn,
        free_cast: true,
        source,
    });
    state.delayed_events.push(DelayedEvent::PermissionExpiry {
        permission: permission_id,
        due_turn: state.turn,
    });
    state.window = Window::Priority;
    Ok(Transition {
        observations: vec![RulesObservation::UrzaCardExiled { card }],
    })
}

fn remove_permanent_to_library_top(
    state: &mut TrueState,
    object_id: ObjectId,
) -> Result<(), RuleError> {
    let mut permanents = state.battlefield.permanents().to_vec();
    let Some(index) = permanents
        .iter()
        .position(|permanent| permanent.object_id == object_id)
    else {
        return Ok(());
    };
    let permanent = permanents.remove(index);
    state.battlefield = BattlefieldZone::new(permanents);
    if permanent.token {
        return Ok(());
    }
    let mut library = Vec::with_capacity(state.library.cards().len() + 1);
    library.push(permanent.card);
    library.extend_from_slice(state.library.cards());
    let old = state.library.knowledge();
    state.library = TrueLibrary::new(
        library,
        LibraryKnowledge {
            known_top: old
                .known_top
                .checked_add(1)
                .ok_or(RuleError::ArithmeticOverflow)?,
            known_bottom: old.known_bottom,
        },
    )?;
    Ok(())
}

fn same_multiset(left: &[CardDefId], right: &[CardDefId]) -> bool {
    if left.len() != right.len() {
        return false;
    }
    let mut left = left.to_vec();
    let mut right = right.to_vec();
    left.sort_unstable();
    right.sort_unstable();
    left == right
}

fn unique_permutations(cards: &[CardDefId]) -> Vec<Vec<CardDefId>> {
    fn visit(
        prefix: &mut Vec<CardDefId>,
        rest: &mut Vec<CardDefId>,
        out: &mut Vec<Vec<CardDefId>>,
    ) {
        if rest.is_empty() {
            if !out.contains(prefix) {
                out.push(prefix.clone());
            }
            return;
        }
        for index in 0..rest.len() {
            let card = rest.remove(index);
            prefix.push(card);
            visit(prefix, rest, out);
            prefix.pop();
            rest.insert(index, card);
        }
    }

    let mut out = Vec::new();
    visit(&mut Vec::new(), &mut cards.to_vec(), &mut out);
    out
}

fn next_permission_id(state: &TrueState) -> Result<PermissionId, RuleError> {
    state
        .urza_permissions
        .iter()
        .map(|permission| permission.permission_id.0)
        .max()
        .unwrap_or(0)
        .checked_add(1)
        .map(PermissionId)
        .ok_or(RuleError::ArithmeticOverflow)
}

fn consume_permission(state: &mut TrueState, permission_id: PermissionId) {
    state
        .urza_permissions
        .retain(|permission| permission.permission_id != permission_id);
    state.delayed_events.retain(|event| {
        !matches!(
            event,
            DelayedEvent::PermissionExpiry { permission, .. } if *permission == permission_id
        )
    });
}

fn expire_urza_permissions(state: &mut TrueState) {
    let expired: BTreeSet<_> = state
        .urza_permissions
        .iter()
        .filter(|permission| permission.expires_turn <= state.turn)
        .map(|permission| permission.permission_id)
        .collect();
    state
        .urza_permissions
        .retain(|permission| !expired.contains(&permission.permission_id));
    state.delayed_events.retain(|event| {
        !matches!(
            event,
            DelayedEvent::PermissionExpiry { permission, due_turn }
                if *due_turn <= state.turn && expired.contains(permission)
        )
    });
}

fn stage_simple_tutor<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    source: SourceRef,
) -> Result<Transition, RuleError> {
    let pending = PendingDecision::TutorTarget { source };
    let candidates = pending_search_candidates(state, cards, &pending);
    state.pending = pending;
    state.window = Window::PostObservation;
    Ok(Transition {
        observations: vec![RulesObservation::SearchAvailable {
            source: source.card,
            candidates,
            may_fail: true,
        }],
    })
}

fn stage_parameterized_search<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    pending: PendingDecision,
) -> Result<Transition, RuleError> {
    let source = pending.source().ok_or(RuleError::SearchDecisionMismatch)?;
    let candidates = pending_search_candidates(state, cards, &pending);
    state.pending = pending;
    state.window = Window::PostObservation;
    Ok(Transition {
        observations: vec![RulesObservation::SearchAvailable {
            source: source.card,
            candidates,
            may_fail: true,
        }],
    })
}

fn pending_search_candidates<D: CardDatabase>(
    state: &TrueState,
    cards: &D,
    pending: &PendingDecision,
) -> Vec<CardDefId> {
    observe_library_search(state, |card| search_target_eligible(cards, pending, card)).candidates
}

fn search_target_eligible<D: CardDatabase>(
    cards: &D,
    pending: &PendingDecision,
    card: CardDefId,
) -> bool {
    let Some(profile) = cards.profile(card) else {
        return false;
    };
    match pending {
        PendingDecision::TutorTarget { source } => {
            let Some(source_profile) = cards.profile(source.card) else {
                return false;
            };
            let Some(kind) = source_profile.simple_tutor else {
                return false;
            };
            match kind {
                SimpleTutorKind::Spellseeker => profile.search_classes.spellseeker,
                SimpleTutorKind::MerchantScroll => profile.search_classes.merchant_scroll,
                SimpleTutorKind::MysticalTutor => profile.search_classes.mystical_tutor,
            }
        }
        PendingDecision::WhirTarget { x_value, .. }
        | PendingDecision::ReshapeTarget { x_value, .. } => {
            profile.is_artifact && profile.mana_value <= *x_value
        }
        PendingDecision::TransmuteTarget { .. } => profile.is_artifact,
        PendingDecision::BayTarget {
            sacrificed_mana_value,
            ..
        } => sacrificed_mana_value
            .checked_add(1)
            .is_some_and(|target_mana_value| {
                profile.is_artifact && profile.mana_value == target_mana_value
            }),
        PendingDecision::SagaTarget { .. } => profile.search_classes.saga_iii,
        PendingDecision::TezzeretTarget { .. } => profile.is_artifact && profile.mana_value <= 1,
        _ => false,
    }
}

fn choose_transmute_sacrifice<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    canonical: CanonicalObjectId,
) -> Result<Transition, RuleError> {
    if state.window != Window::Resolving {
        return Err(RuleError::SearchDecisionMismatch);
    }
    let PendingDecision::TransmuteSacrifice { source } = state.pending.clone() else {
        return Err(RuleError::SearchDecisionMismatch);
    };
    let artifact = resolve_canonical_object(state, canonical)
        .map_err(|error| match error {
            urza_info::ObservationError::InvalidState(error) => RuleError::InvalidState(error),
        })?
        .ok_or(RuleError::MissingCanonicalPermanent(canonical))?;
    let sacrificed = validate_sacrifice_artifact(state, cards, artifact)?;

    sacrifice_artifact(state, artifact)?;
    stage_parameterized_search(
        state,
        cards,
        PendingDecision::TransmuteTarget {
            source,
            sacrificed_mana_value: sacrificed.mana_value,
        },
    )
}

fn choose_search_target<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    target: Option<CardDefId>,
    rng: GameRngContext,
) -> Result<Transition, RuleError> {
    if state.window != Window::PostObservation {
        return Err(RuleError::SearchDecisionMismatch);
    }
    let pending = state.pending.clone();
    if !matches!(
        pending,
        PendingDecision::TutorTarget { .. }
            | PendingDecision::WhirTarget { .. }
            | PendingDecision::ReshapeTarget { .. }
            | PendingDecision::TransmuteTarget { .. }
            | PendingDecision::BayTarget { .. }
            | PendingDecision::SagaTarget { .. }
            | PendingDecision::TezzeretTarget { .. }
    ) {
        return Err(RuleError::SearchDecisionMismatch);
    }

    let candidates = pending_search_candidates(state, cards, &pending);
    if let Some(target) = target
        && candidates.binary_search(&target).is_err()
    {
        return Err(RuleError::InvalidSearchTarget(target));
    }

    let source = pending.source().ok_or(RuleError::SearchDecisionMismatch)?;
    let shuffled_remainder = consume_shared_search_shuffle(state, target, rng)?;

    match pending {
        PendingDecision::TutorTarget { .. } => {
            let profile = card_profile(cards, source.card)?;
            let kind = profile
                .simple_tutor
                .ok_or(RuleError::UnsupportedCardMechanic(source.card))?;
            complete_simple_tutor(state, cards, source, kind, target, shuffled_remainder)
        }
        PendingDecision::WhirTarget { .. }
        | PendingDecision::ReshapeTarget { .. }
        | PendingDecision::BayTarget { .. } => {
            complete_battlefield_search(state, cards, source, target, shuffled_remainder)
        }
        PendingDecision::SagaTarget { .. } => {
            let result =
                complete_battlefield_search(state, cards, source, target, shuffled_remainder)?;
            sacrifice_saga_after_final_chapter(state, source)?;
            Ok(result)
        }
        PendingDecision::TezzeretTarget { .. } => {
            state.library = TrueLibrary::unknown(shuffled_remainder);
            if let Some(target) = target {
                state.hand.insert(target);
            }
            state.pending = PendingDecision::None;
            state.window = Window::Priority;
            Ok(Transition {
                observations: vec![RulesObservation::SearchCompleted {
                    source: source.card,
                    target,
                    destination: SearchDestination::Hand,
                }],
            })
        }
        PendingDecision::TransmuteTarget {
            sacrificed_mana_value,
            ..
        } => {
            state.library = TrueLibrary::unknown(shuffled_remainder);
            let Some(target) = target else {
                state.pending = PendingDecision::None;
                state.window = Window::Priority;
                return Ok(Transition {
                    observations: vec![RulesObservation::SearchCompleted {
                        source: source.card,
                        target: None,
                        destination: SearchDestination::Battlefield,
                    }],
                });
            };
            let target_profile = card_profile(cards, target)?;
            if target_profile.mana_value <= sacrificed_mana_value {
                let entered = put_card_onto_battlefield(state, cards, target)?;
                state.pending = PendingDecision::None;
                state.window = Window::Priority;
                Ok(Transition {
                    observations: vec![
                        RulesObservation::SearchCompleted {
                            source: source.card,
                            target: Some(target),
                            destination: SearchDestination::Battlefield,
                        },
                        entered,
                    ],
                })
            } else {
                let difference = target_profile
                    .mana_value
                    .checked_sub(sacrificed_mana_value)
                    .ok_or(RuleError::ArithmeticOverflow)?;
                state.pending = PendingDecision::TransmuteDifferencePayment {
                    source,
                    target,
                    difference: GenericCost(difference),
                };
                state.window = Window::Resolving;
                Ok(Transition::default())
            }
        }
        _ => Err(RuleError::SearchDecisionMismatch),
    }
}

fn complete_simple_tutor<D: CardDatabase>(
    state: &mut TrueState,
    _cards: &D,
    source: SourceRef,
    kind: SimpleTutorKind,
    target: Option<CardDefId>,
    shuffled_remainder: Vec<CardDefId>,
) -> Result<Transition, RuleError> {
    match (kind.destination(), target) {
        (SearchDestination::Hand, Some(target)) => {
            state.library = TrueLibrary::unknown(shuffled_remainder);
            state.hand.insert(target);
        }
        (SearchDestination::Hand, None) => {
            state.library = TrueLibrary::unknown(shuffled_remainder);
        }
        (SearchDestination::LibraryTop, Some(target)) => {
            let mut library = Vec::with_capacity(shuffled_remainder.len() + 1);
            library.push(target);
            library.extend(shuffled_remainder);
            state.library = TrueLibrary::new(
                library,
                LibraryKnowledge {
                    known_top: 1,
                    known_bottom: 0,
                },
            )?;
        }
        (SearchDestination::LibraryTop, None) => {
            state.library = TrueLibrary::unknown(shuffled_remainder);
        }
        (SearchDestination::Battlefield | SearchDestination::Graveyard, _) => {
            return Err(RuleError::SearchDecisionMismatch);
        }
    }

    state.pending = PendingDecision::None;
    state.window = Window::Priority;
    Ok(Transition {
        observations: vec![RulesObservation::SearchCompleted {
            source: source.card,
            target,
            destination: kind.destination(),
        }],
    })
}

fn complete_battlefield_search<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    source: SourceRef,
    target: Option<CardDefId>,
    shuffled_remainder: Vec<CardDefId>,
) -> Result<Transition, RuleError> {
    state.library = TrueLibrary::unknown(shuffled_remainder);
    state.pending = PendingDecision::None;
    state.window = Window::Priority;
    let mut observations = vec![RulesObservation::SearchCompleted {
        source: source.card,
        target,
        destination: SearchDestination::Battlefield,
    }];
    if let Some(target) = target {
        observations.push(put_card_onto_battlefield(state, cards, target)?);
    }
    Ok(Transition { observations })
}

fn pay_transmute_difference<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    payment: Option<ManaPayment>,
) -> Result<Transition, RuleError> {
    if state.window != Window::Resolving {
        return Err(RuleError::NoTransmutePaymentPending);
    }
    let PendingDecision::TransmuteDifferencePayment {
        source,
        target,
        difference,
    } = state.pending.clone()
    else {
        return Err(RuleError::NoTransmutePaymentPending);
    };

    let destination;
    let mut observations = Vec::new();
    if let Some(payment) = payment {
        let cost = ManaCost {
            generic: difference.0,
            ..ManaCost::default()
        };
        validate_payment(state.mana, payment, cost)?;
        let object_id = next_object_id(state)?;
        spend_payment(&mut state.mana, payment);
        let entered = put_card_onto_battlefield_with_id(state, cards, target, object_id)?;
        destination = SearchDestination::Battlefield;
        observations.push(entered);
    } else {
        state.graveyard.insert(target);
        destination = SearchDestination::Graveyard;
    }

    state.pending = PendingDecision::None;
    state.window = Window::Priority;
    observations.insert(
        0,
        RulesObservation::SearchCompleted {
            source: source.card,
            target: Some(target),
            destination,
        },
    );
    Ok(Transition { observations })
}

fn consume_shared_search_shuffle(
    state: &mut TrueState,
    target: Option<CardDefId>,
    rng: GameRngContext,
) -> Result<Vec<CardDefId>, RuleError> {
    let pre_target_cards = state.library.cards().to_vec();
    let pre_target_fingerprint = library_fingerprint(&pre_target_cards);
    let occurrence = EventOccurrence(state.rng_occurrence_cursor);
    let next_occurrence = state
        .rng_occurrence_cursor
        .checked_add(1)
        .ok_or(RuleError::RngOccurrenceExhausted)?;
    let coordinate = RngCoordinate {
        domain: RngDomain::Game,
        world: rng.world,
        event_type: RNG_EVENT_SEARCH_SHUFFLE,
        logical_event: rng.logical_event,
        occurrence,
        concrete_fingerprint: pre_target_fingerprint,
    };

    let mut shared_ranking = pre_target_cards;
    urza_rng::shuffle(&mut shared_ranking, rng.root, coordinate);
    if let Some(target) = target {
        let position = shared_ranking
            .iter()
            .position(|card| *card == target)
            .ok_or(RuleError::InvalidSearchTarget(target))?;
        shared_ranking.remove(position);
    }
    state.rng_occurrence_cursor = next_occurrence;
    Ok(shared_ranking)
}

fn library_fingerprint(cards: &[CardDefId]) -> [u8; 16] {
    let mut hasher = blake3::Hasher::new();
    hasher.update(b"r3-search-pre-target-library-v1");
    for card in cards {
        hasher.update(&card.0.to_le_bytes());
    }
    let digest = hasher.finalize();
    let mut fingerprint = [0_u8; 16];
    fingerprint.copy_from_slice(&digest.as_bytes()[..16]);
    fingerprint
}

fn validate_sacrifice_artifact<D: CardDatabase>(
    state: &TrueState,
    cards: &D,
    object: ObjectId,
) -> Result<CardProfile, RuleError> {
    let permanent = battlefield_permanent(state, object)?;
    let profile = card_profile(cards, permanent.card)?;
    if !profile.is_artifact {
        return Err(RuleError::InvalidSacrifice(object));
    }
    if state
        .battlefield
        .permanents()
        .iter()
        .any(|candidate| candidate.attached_to == Some(object))
    {
        return Err(RuleError::AttachedSacrificeDeferred(object));
    }
    Ok(profile)
}

fn sacrifice_artifact(state: &mut TrueState, object: ObjectId) -> Result<(), RuleError> {
    let mut permanents = state.battlefield.permanents().to_vec();
    let Some(index) = permanents
        .iter()
        .position(|permanent| permanent.object_id == object)
    else {
        return Err(RuleError::MissingPermanent(object));
    };
    let permanent = permanents.remove(index);
    state.battlefield = BattlefieldZone::new(permanents);
    if !permanent.token {
        state.graveyard.insert(permanent.card);
    }
    state.delayed_events.retain(|event| {
        !matches!(
            event,
            DelayedEvent::ChromeCopySacrifice {
                object: delayed,
                ..
            } if *delayed == object
        )
    });
    Ok(())
}

fn put_card_onto_battlefield<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    card: CardDefId,
) -> Result<RulesObservation, RuleError> {
    let object_id = next_object_id(state)?;
    put_card_onto_battlefield_with_id(state, cards, card, object_id)
}

fn put_card_onto_battlefield_with_id<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    card: CardDefId,
    object_id: ObjectId,
) -> Result<RulesObservation, RuleError> {
    let profile = card_profile(cards, card)?;
    insert_permanent(
        state,
        PermanentState {
            object_id,
            card,
            face: profile.battlefield_face,
            tapped: false,
            summoning_sick: profile.is_creature,
            token: false,
            counters: CounterState {
                loyalty: profile.starting_loyalty,
                ..CounterState::default()
            },
            mode: PermanentMode::Normal,
            attached_to: None,
            granted_ability: None,
        },
    );
    Ok(RulesObservation::PermanentEntered {
        card,
        face: profile.battlefield_face,
        token: false,
    })
}

fn ensure_mana_activation_window(state: &TrueState) -> Result<(), RuleError> {
    match (&state.pending, state.window) {
        (PendingDecision::None, Window::Priority)
        | (PendingDecision::TransmuteDifferencePayment { .. }, Window::Resolving) => Ok(()),
        _ => Err(RuleError::IllegalTiming),
    }
}

fn ensure_priority(state: &TrueState) -> Result<(), RuleError> {
    if state.window == Window::Priority {
        Ok(())
    } else {
        Err(RuleError::IllegalTiming)
    }
}

fn ensure_sorcery_window(state: &TrueState) -> Result<(), RuleError> {
    ensure_priority(state)?;
    ensure_no_pending_decision(state)?;
    if state.phase != Phase::PrecombatMain || !state.stack.is_empty() {
        return Err(RuleError::IllegalTiming);
    }
    Ok(())
}

fn ensure_no_pending_decision(state: &TrueState) -> Result<(), RuleError> {
    if matches!(state.pending, PendingDecision::None) {
        Ok(())
    } else {
        Err(RuleError::PendingDecisionActive)
    }
}

fn validate_payment(pool: ManaPool, payment: ManaPayment, cost: ManaCost) -> Result<(), RuleError> {
    if payment.satisfies(cost) && payment.is_available_from(pool) {
        Ok(())
    } else {
        Err(RuleError::InvalidManaPayment)
    }
}

fn reduced_artifact_activation_cost<D: CardDatabase>(
    state: &TrueState,
    cards: &D,
    source: ObjectId,
    base_generic: u16,
) -> Result<ManaCost, RuleError> {
    let source_permanent = battlefield_permanent(state, source)?;
    if !card_profile(cards, source_permanent.card)?.is_artifact {
        return Err(RuleError::NotArtifact(source));
    }

    let mut reduction = 0_u16;
    for permanent in state.battlefield.permanents() {
        let profile = card_profile(cards, permanent.card)?;
        reduction = reduction
            .checked_add(profile.artifact_activation_reduction)
            .ok_or(RuleError::ArithmeticOverflow)?;
    }

    let generic = if reduction == 0 || base_generic == 0 {
        base_generic
    } else {
        base_generic.saturating_sub(reduction).max(1)
    };
    Ok(ManaCost {
        generic,
        ..ManaCost::default()
    })
}

fn add_blue(pool: &mut ManaPool, amount: u16) -> Result<(), RuleError> {
    pool.blue = pool
        .blue
        .checked_add(amount)
        .ok_or(RuleError::ArithmeticOverflow)?;
    Ok(())
}

fn add_colorless(pool: &mut ManaPool, amount: u16) -> Result<(), RuleError> {
    pool.colorless = pool
        .colorless
        .checked_add(amount)
        .ok_or(RuleError::ArithmeticOverflow)?;
    Ok(())
}

fn spend_payment(pool: &mut ManaPool, payment: ManaPayment) {
    pool.white -= payment.white;
    pool.blue -= payment.blue;
    pool.black -= payment.black;
    pool.red -= payment.red;
    pool.green -= payment.green;
    pool.colorless -= payment.colorless;
}

fn card_profile<D: CardDatabase>(cards: &D, card: CardDefId) -> Result<CardProfile, RuleError> {
    cards.profile(card).ok_or(RuleError::UnknownCard(card))
}

fn battlefield_permanent(
    state: &TrueState,
    object_id: ObjectId,
) -> Result<&PermanentState, RuleError> {
    state
        .battlefield
        .get(object_id)
        .ok_or(RuleError::MissingPermanent(object_id))
}

fn set_tapped(state: &mut TrueState, object_id: ObjectId) -> Result<(), RuleError> {
    set_permanent_tapped(state, object_id, true)
}

fn set_untapped(state: &mut TrueState, object_id: ObjectId) -> Result<(), RuleError> {
    set_permanent_tapped(state, object_id, false)
}

fn set_permanent_tapped(
    state: &mut TrueState,
    object_id: ObjectId,
    tapped: bool,
) -> Result<(), RuleError> {
    let mut permanents = state.battlefield.permanents().to_vec();
    let Some(permanent) = permanents
        .iter_mut()
        .find(|permanent| permanent.object_id == object_id)
    else {
        return Err(RuleError::MissingPermanent(object_id));
    };
    permanent.tapped = tapped;
    state.battlefield = BattlefieldZone::new(permanents);
    Ok(())
}

fn insert_permanent(state: &mut TrueState, permanent: PermanentState) {
    let mut permanents = state.battlefield.permanents().to_vec();
    permanents.push(permanent);
    state.battlefield = BattlefieldZone::new(permanents);
}

fn next_object_id(state: &TrueState) -> Result<ObjectId, RuleError> {
    let battlefield_max = state
        .battlefield
        .permanents()
        .iter()
        .map(|permanent| permanent.object_id.0)
        .max();
    let stack_max = state
        .stack
        .iter()
        .filter_map(|object| match object {
            StackObject::Spell { object_id, .. } => Some(object_id.0),
            StackObject::ControlledTrigger { .. } | StackObject::ActivatedAbility { .. } => None,
        })
        .max();
    let current_max = battlefield_max
        .into_iter()
        .chain(stack_max)
        .max()
        .unwrap_or(0);
    current_max
        .checked_add(1)
        .map(ObjectId)
        .ok_or(RuleError::ObjectIdExhausted)
}

#[cfg(test)]
mod tests {
    use std::collections::BTreeMap;

    use super::*;
    use urza_core::{CardZone, CommanderState};

    const ISLAND: CardDefId = CardDefId(1);
    const SOL_RING: CardDefId = CardDefId(2);
    const URZA: CardDefId = CardDefId(3);
    const CONSTRUCT: CardDefId = CardDefId(4);
    const ANCIENT_TOMB: CardDefId = CardDefId(5);
    const MDFC_LAND: CardDefId = CardDefId(6);
    const KEY: CardDefId = CardDefId(7);
    const MYSTICAL: CardDefId = CardDefId(8);
    const SPELLSEEKER: CardDefId = CardDefId(9);
    const TARGET_A: CardDefId = CardDefId(10);
    const TARGET_B: CardDefId = CardDefId(11);
    const TARGET_C: CardDefId = CardDefId(12);
    const WHIR: CardDefId = CardDefId(13);
    const RESHAPE: CardDefId = CardDefId(14);
    const TRANSMUTE: CardDefId = CardDefId(15);
    const BAY: CardDefId = CardDefId(16);
    const ARTIFACT_MV2: CardDefId = CardDefId(17);
    const ARTIFACT_MV3: CardDefId = CardDefId(18);
    const TOP: CardDefId = CardDefId(19);
    const SAGA: CardDefId = CardDefId(20);
    const TEZZERET: CardDefId = CardDefId(21);
    const ARTIFACT_MV0: CardDefId = CardDefId(22);
    const ARTIFACT_X_MV0: CardDefId = CardDefId(23);
    const BASALT: CardDefId = CardDefId(24);
    const GRIM: CardDefId = CardDefId(25);
    const GADGETEER: CardDefId = CardDefId(26);

    #[derive(Default)]
    struct TestCards {
        profiles: BTreeMap<CardDefId, CardProfile>,
    }

    impl TestCards {
        fn r2() -> Self {
            let mut profiles = BTreeMap::new();
            profiles.insert(
                ISLAND,
                CardProfile {
                    card: ISLAND,
                    role: R2CardRole::Land,
                    battlefield_face: CardFace::Front,
                    land_entry: LandEntryRule::Untapped,
                    mana_ability: ManaAbility::TapForBlue,
                    ..CardProfile::default()
                },
            );
            profiles.insert(
                SOL_RING,
                CardProfile {
                    card: SOL_RING,
                    mana_cost: Some(ManaCost {
                        generic: 1,
                        ..ManaCost::default()
                    }),
                    role: R2CardRole::ArtifactPermanent,
                    battlefield_face: CardFace::Front,
                    mana_ability: ManaAbility::TapForColorless(2),
                    is_artifact: true,
                    ..CardProfile::default()
                },
            );
            profiles.insert(
                URZA,
                CardProfile {
                    card: URZA,
                    mana_cost: Some(ManaCost {
                        blue: 2,
                        generic: 2,
                        ..ManaCost::default()
                    }),
                    role: R2CardRole::UrzaCommander,
                    battlefield_face: CardFace::Front,
                    is_creature: true,
                    ..CardProfile::default()
                },
            );
            profiles.insert(
                CONSTRUCT,
                CardProfile {
                    card: CONSTRUCT,
                    role: R2CardRole::UrzaConstructToken,
                    battlefield_face: CardFace::Front,
                    is_artifact: true,
                    is_creature: true,
                    ..CardProfile::default()
                },
            );
            profiles.insert(
                ANCIENT_TOMB,
                CardProfile {
                    card: ANCIENT_TOMB,
                    role: R2CardRole::Land,
                    battlefield_face: CardFace::Front,
                    land_entry: LandEntryRule::Untapped,
                    mana_ability: ManaAbility::TapForColorlessAndDamage { mana: 2, damage: 2 },
                    ..CardProfile::default()
                },
            );
            profiles.insert(
                MDFC_LAND,
                CardProfile {
                    card: MDFC_LAND,
                    role: R2CardRole::Land,
                    battlefield_face: CardFace::Back,
                    land_entry: LandEntryRule::PayLifeOrTapped { life: 3 },
                    mana_ability: ManaAbility::TapForBlue,
                    ..CardProfile::default()
                },
            );
            profiles.insert(
                KEY,
                CardProfile {
                    card: KEY,
                    mana_cost: Some(ManaCost {
                        generic: 1,
                        ..ManaCost::default()
                    }),
                    mana_value: 1,
                    role: R2CardRole::ArtifactPermanent,
                    battlefield_face: CardFace::Front,
                    is_artifact: true,
                    ..CardProfile::default()
                },
            );
            Self { profiles }
        }
    }

    impl TestCards {
        fn r3() -> Self {
            let mut cards = Self::r2();
            cards.profiles.insert(
                MYSTICAL,
                CardProfile {
                    card: MYSTICAL,
                    mana_cost: Some(ManaCost {
                        blue: 1,
                        ..ManaCost::default()
                    }),
                    mana_value: 1,
                    role: R2CardRole::SearchSpell,
                    simple_tutor: Some(SimpleTutorKind::MysticalTutor),
                    ..CardProfile::default()
                },
            );
            cards.profiles.insert(
                SPELLSEEKER,
                CardProfile {
                    card: SPELLSEEKER,
                    mana_cost: Some(ManaCost {
                        blue: 1,
                        generic: 2,
                        ..ManaCost::default()
                    }),
                    mana_value: 3,
                    role: R2CardRole::CreaturePermanent,
                    battlefield_face: CardFace::Front,
                    simple_tutor: Some(SimpleTutorKind::Spellseeker),
                    is_creature: true,
                    ..CardProfile::default()
                },
            );
            for target in [TARGET_A, TARGET_B, TARGET_C] {
                cards.profiles.insert(
                    target,
                    CardProfile {
                        card: target,
                        mana_value: 1,
                        search_classes: SearchClassFlags {
                            spellseeker: true,
                            merchant_scroll: true,
                            mystical_tutor: true,
                            ..SearchClassFlags::default()
                        },
                        ..CardProfile::default()
                    },
                );
            }
            cards.profiles.insert(
                WHIR,
                CardProfile {
                    card: WHIR,
                    mana_cost: Some(ManaCost {
                        blue: 3,
                        ..ManaCost::default()
                    }),
                    mana_value: 3,
                    role: R2CardRole::SearchSpell,
                    special_search: SpecialSearchKind::Whir,
                    ..CardProfile::default()
                },
            );
            cards.profiles.insert(
                RESHAPE,
                CardProfile {
                    card: RESHAPE,
                    mana_cost: Some(ManaCost {
                        blue: 2,
                        ..ManaCost::default()
                    }),
                    mana_value: 2,
                    role: R2CardRole::SearchSpell,
                    special_search: SpecialSearchKind::Reshape,
                    ..CardProfile::default()
                },
            );
            cards.profiles.insert(
                TRANSMUTE,
                CardProfile {
                    card: TRANSMUTE,
                    mana_cost: Some(ManaCost {
                        blue: 2,
                        ..ManaCost::default()
                    }),
                    mana_value: 2,
                    role: R2CardRole::SearchSpell,
                    special_search: SpecialSearchKind::TransmuteArtifact,
                    ..CardProfile::default()
                },
            );
            cards.profiles.insert(
                BAY,
                CardProfile {
                    card: BAY,
                    mana_cost: Some(ManaCost {
                        blue: 1,
                        generic: 2,
                        ..ManaCost::default()
                    }),
                    mana_value: 3,
                    role: R2CardRole::ArtifactPermanent,
                    battlefield_face: CardFace::Front,
                    special_search: SpecialSearchKind::RepurposingBay,
                    is_artifact: true,
                    ..CardProfile::default()
                },
            );
            cards.profiles.insert(
                ARTIFACT_MV2,
                CardProfile {
                    card: ARTIFACT_MV2,
                    mana_value: 2,
                    role: R2CardRole::ArtifactPermanent,
                    battlefield_face: CardFace::Front,
                    is_artifact: true,
                    ..CardProfile::default()
                },
            );
            cards.profiles.insert(
                ARTIFACT_MV3,
                CardProfile {
                    card: ARTIFACT_MV3,
                    mana_value: 3,
                    role: R2CardRole::ArtifactPermanent,
                    battlefield_face: CardFace::Front,
                    is_artifact: true,
                    ..CardProfile::default()
                },
            );
            cards.profiles.insert(
                TOP,
                CardProfile {
                    card: TOP,
                    mana_cost: Some(ManaCost {
                        generic: 1,
                        ..ManaCost::default()
                    }),
                    mana_value: 1,
                    role: R2CardRole::ArtifactPermanent,
                    battlefield_face: CardFace::Front,
                    utility: UtilityKind::SenseisDiviningTop,
                    is_artifact: true,
                    search_classes: SearchClassFlags {
                        saga_iii: true,
                        ..SearchClassFlags::default()
                    },
                    ..CardProfile::default()
                },
            );
            cards.profiles.insert(
                SAGA,
                CardProfile {
                    card: SAGA,
                    role: R2CardRole::Land,
                    battlefield_face: CardFace::Front,
                    land_entry: LandEntryRule::Untapped,
                    utility: UtilityKind::UrzasSaga,
                    ..CardProfile::default()
                },
            );
            cards.profiles.insert(
                TEZZERET,
                CardProfile {
                    card: TEZZERET,
                    mana_cost: Some(ManaCost {
                        generic: 3,
                        ..ManaCost::default()
                    }),
                    mana_value: 3,
                    role: R2CardRole::PlaneswalkerPermanent,
                    battlefield_face: CardFace::Front,
                    utility: UtilityKind::TezzeretCruelCaptain,
                    starting_loyalty: 4,
                    ..CardProfile::default()
                },
            );
            cards.profiles.insert(
                ARTIFACT_MV0,
                CardProfile {
                    card: ARTIFACT_MV0,
                    mana_cost: Some(ManaCost::default()),
                    mana_value: 0,
                    role: R2CardRole::ArtifactPermanent,
                    battlefield_face: CardFace::Front,
                    search_classes: SearchClassFlags {
                        saga_iii: true,
                        ..SearchClassFlags::default()
                    },
                    is_artifact: true,
                    ..CardProfile::default()
                },
            );
            cards.profiles.insert(
                ARTIFACT_X_MV0,
                CardProfile {
                    card: ARTIFACT_X_MV0,
                    mana_value: 0,
                    role: R2CardRole::ArtifactPermanent,
                    battlefield_face: CardFace::Front,
                    is_artifact: true,
                    ..CardProfile::default()
                },
            );
            cards
        }
    }

    impl TestCards {
        fn r4() -> Self {
            let mut cards = Self::r3();
            cards.profiles.insert(
                BASALT,
                CardProfile {
                    card: BASALT,
                    mana_cost: Some(ManaCost {
                        generic: 3,
                        ..ManaCost::default()
                    }),
                    mana_value: 3,
                    role: R2CardRole::ArtifactPermanent,
                    battlefield_face: CardFace::Front,
                    mana_ability: ManaAbility::TapForColorless(3),
                    engine: EngineKind::BasaltMonolith,
                    native_untap_generic: Some(3),
                    skip_normal_untap: true,
                    is_artifact: true,
                    ..CardProfile::default()
                },
            );
            cards.profiles.insert(
                GRIM,
                CardProfile {
                    card: GRIM,
                    mana_cost: Some(ManaCost {
                        generic: 2,
                        ..ManaCost::default()
                    }),
                    mana_value: 2,
                    role: R2CardRole::ArtifactPermanent,
                    battlefield_face: CardFace::Front,
                    mana_ability: ManaAbility::TapForColorless(3),
                    engine: EngineKind::GrimMonolith,
                    native_untap_generic: Some(4),
                    skip_normal_untap: true,
                    is_artifact: true,
                    ..CardProfile::default()
                },
            );
            cards.profiles.insert(
                GADGETEER,
                CardProfile {
                    card: GADGETEER,
                    mana_cost: Some(ManaCost {
                        blue: 1,
                        generic: 2,
                        ..ManaCost::default()
                    }),
                    mana_value: 3,
                    role: R2CardRole::CreaturePermanent,
                    battlefield_face: CardFace::Front,
                    engine: EngineKind::ForensicGadgeteer,
                    artifact_activation_reduction: 1,
                    is_creature: true,
                    ..CardProfile::default()
                },
            );
            cards
        }
    }

    impl CardDatabase for TestCards {
        fn profile(&self, card: CardDefId) -> Option<CardProfile> {
            self.profiles.get(&card).copied()
        }

        fn commander_card(&self) -> CardDefId {
            URZA
        }

        fn urza_construct_token_card(&self) -> CardDefId {
            CONSTRUCT
        }
    }

    fn object_for(state: &TrueState, card: CardDefId) -> ObjectId {
        state
            .battlefield
            .permanents()
            .iter()
            .find(|permanent| permanent.card == card)
            .expect("expected permanent")
            .object_id
    }

    #[test]
    fn mana_cost_parser_and_payment_enumeration_preserve_resource_choices() {
        let cost = ManaCost::parse_scryfall("{2}{U}{U}").unwrap();
        assert_eq!(
            cost,
            ManaCost {
                blue: 2,
                generic: 2,
                ..ManaCost::default()
            }
        );
        assert!(matches!(
            ManaCost::parse_scryfall("{X}{U}"),
            Err(ManaCostParseError::UnsupportedSymbol(symbol)) if symbol == "X"
        ));

        let pool = ManaPool {
            blue: 4,
            colorless: 2,
            ..ManaPool::default()
        };
        let payments = enumerate_payments(pool, cost);
        assert_eq!(payments.len(), 3);
        assert!(payments.iter().all(|payment| payment.satisfies(cost)));
        assert!(
            payments
                .iter()
                .any(|payment| payment.blue == 2 && payment.colorless == 2)
        );
        assert!(
            payments
                .iter()
                .any(|payment| payment.blue == 4 && payment.colorless == 0)
        );
    }

    #[test]
    fn search_observation_is_order_invariant_and_collapses_identical_targets() {
        let a = TrueState {
            library: TrueLibrary::unknown(vec![
                CardDefId(9),
                CardDefId(2),
                CardDefId(2),
                CardDefId(4),
            ]),
            ..TrueState::default()
        };
        let b = TrueState {
            library: TrueLibrary::unknown(vec![
                CardDefId(4),
                CardDefId(2),
                CardDefId(9),
                CardDefId(2),
            ]),
            ..TrueState::default()
        };

        let observe_even =
            |state: &TrueState| observe_library_search(state, |card| card.0 % 2 == 0);
        assert_eq!(observe_even(&a), observe_even(&b));
        assert_eq!(
            observe_even(&a).candidates,
            vec![CardDefId(2), CardDefId(4)]
        );
    }

    #[test]
    fn draw_updates_known_top_and_all_known_bottom() {
        let mut known_top = TrueState {
            library: TrueLibrary::new(
                vec![CardDefId(1), CardDefId(2), CardDefId(3)],
                LibraryKnowledge {
                    known_top: 2,
                    known_bottom: 0,
                },
            )
            .unwrap(),
            ..TrueState::default()
        };
        assert_eq!(draw_cards(&mut known_top, 1).unwrap(), vec![CardDefId(1)]);
        assert_eq!(known_top.library.knowledge().known_top, 1);

        let mut all_known_from_bottom = TrueState {
            library: TrueLibrary::new(
                vec![CardDefId(1), CardDefId(2)],
                LibraryKnowledge {
                    known_top: 0,
                    known_bottom: 2,
                },
            )
            .unwrap(),
            ..TrueState::default()
        };
        draw_cards(&mut all_known_from_bottom, 1).unwrap();
        assert_eq!(all_known_from_bottom.library.knowledge().known_bottom, 1);
    }

    #[test]
    fn shuffle_clears_knowledge_and_consumes_exactly_one_occurrence() {
        let mut first = TrueState {
            library: TrueLibrary::new(
                (0..16).map(CardDefId).collect(),
                LibraryKnowledge {
                    known_top: 2,
                    known_bottom: 2,
                },
            )
            .unwrap(),
            ..TrueState::default()
        };
        let mut second = first.clone();
        let root = RootSeed::from_u64(77);

        let occurrence = shuffle_library(
            &mut first,
            root,
            WorldId(3),
            EventType(11),
            LogicalEventId(9),
            [5; 16],
        )
        .unwrap();
        shuffle_library(
            &mut second,
            root,
            WorldId(3),
            EventType(11),
            LogicalEventId(9),
            [5; 16],
        )
        .unwrap();

        assert_eq!(occurrence, EventOccurrence(0));
        assert_eq!(first.rng_occurrence_cursor, 1);
        assert_eq!(first.library.knowledge(), LibraryKnowledge::default());
        assert_eq!(first.library.cards(), second.library.cards());
    }

    #[test]
    fn mdfc_land_face_and_life_entry_choice_are_explicit_state() {
        let cards = TestCards::r2();
        let mut tapped = TrueState {
            turn: 1,
            phase: Phase::PrecombatMain,
            window: Window::Priority,
            hand: CardZone::new(vec![MDFC_LAND]),
            ..TrueState::default()
        };
        apply_action(
            &mut tapped,
            &cards,
            Action::PlayLand {
                card: MDFC_LAND,
                entry: LandEntryChoice::Default,
            },
        )
        .unwrap();
        let permanent = tapped
            .battlefield
            .get(object_for(&tapped, MDFC_LAND))
            .unwrap();
        assert_eq!(permanent.face, CardFace::Back);
        assert!(permanent.tapped);
        assert_eq!(tapped.life, 40);

        let mut paid = TrueState {
            turn: 1,
            phase: Phase::PrecombatMain,
            window: Window::Priority,
            hand: CardZone::new(vec![MDFC_LAND]),
            ..TrueState::default()
        };
        apply_action(
            &mut paid,
            &cards,
            Action::PlayLand {
                card: MDFC_LAND,
                entry: LandEntryChoice::PayLife,
            },
        )
        .unwrap();
        let permanent = paid.battlefield.get(object_for(&paid, MDFC_LAND)).unwrap();
        assert_eq!(permanent.face, CardFace::Back);
        assert!(!permanent.tapped);
        assert_eq!(paid.life, 37);
    }

    #[test]
    fn intrinsic_mana_sources_track_tapping_and_self_damage() {
        let cards = TestCards::r2();
        let mut state = TrueState {
            turn: 1,
            phase: Phase::PrecombatMain,
            window: Window::Priority,
            hand: CardZone::new(vec![ANCIENT_TOMB]),
            ..TrueState::default()
        };
        apply_action(
            &mut state,
            &cards,
            Action::PlayLand {
                card: ANCIENT_TOMB,
                entry: LandEntryChoice::Default,
            },
        )
        .unwrap();
        let tomb = object_for(&state, ANCIENT_TOMB);
        apply_action(
            &mut state,
            &cards,
            Action::ActivateManaAbility { source: tomb },
        )
        .unwrap();
        assert_eq!(state.mana.colorless, 2);
        assert_eq!(state.life, 38);
        assert!(state.battlefield.get(tomb).unwrap().tapped);
    }

    #[test]
    fn r2_acceptance_trajectory_covers_turn_draw_land_artifact_stack_urza_and_mana() {
        let cards = TestCards::r2();
        let mut state = TrueState {
            turn: 1,
            phase: Phase::PrecombatMain,
            window: Window::Priority,
            library: TrueLibrary::unknown(vec![ISLAND]),
            hand: CardZone::new(vec![ISLAND, SOL_RING]),
            commander: CommanderState {
                zone: CommanderZone::CommandZone,
                command_zone_casts: 0,
            },
            ..TrueState::default()
        };

        apply_action(
            &mut state,
            &cards,
            Action::PlayLand {
                card: ISLAND,
                entry: LandEntryChoice::Default,
            },
        )
        .unwrap();
        let first_island = object_for(&state, ISLAND);
        apply_action(
            &mut state,
            &cards,
            Action::ActivateManaAbility {
                source: first_island,
            },
        )
        .unwrap();
        apply_action(
            &mut state,
            &cards,
            Action::CastFromHand {
                card: SOL_RING,
                payment: ManaPayment {
                    blue: 1,
                    ..ManaPayment::default()
                },
            },
        )
        .unwrap();
        assert_eq!(state.stack.len(), 1);
        assert!(
            state
                .battlefield
                .permanents()
                .iter()
                .all(|p| p.card != SOL_RING)
        );

        let resolved = apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        assert_eq!(
            resolved.observations,
            vec![RulesObservation::PermanentEntered {
                card: SOL_RING,
                face: CardFace::Front,
                token: false,
            }]
        );
        let sol_ring = object_for(&state, SOL_RING);
        apply_action(
            &mut state,
            &cards,
            Action::ActivateManaAbility { source: sol_ring },
        )
        .unwrap();
        assert_eq!(state.mana.colorless, 2);

        apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        assert_eq!(state.phase, Phase::OpponentCycle);
        assert_eq!(state.window, Window::None);

        advance_automatic(&mut state, &cards).unwrap();
        assert_eq!(state.turn, 2);
        assert_eq!(state.phase, Phase::Upkeep);
        assert_eq!(state.window, Window::Priority);
        assert!(!state.battlefield.get(first_island).unwrap().tapped);
        assert!(!state.battlefield.get(sol_ring).unwrap().tapped);

        let draw = apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        assert_eq!(
            draw.observations,
            vec![RulesObservation::CardsDrawn(vec![ISLAND])]
        );
        apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        assert_eq!(state.phase, Phase::PrecombatMain);

        apply_action(
            &mut state,
            &cards,
            Action::PlayLand {
                card: ISLAND,
                entry: LandEntryChoice::Default,
            },
        )
        .unwrap();
        let islands: Vec<_> = state
            .battlefield
            .permanents()
            .iter()
            .filter(|permanent| permanent.card == ISLAND)
            .map(|permanent| permanent.object_id)
            .collect();
        assert_eq!(islands.len(), 2);
        for island in islands {
            apply_action(
                &mut state,
                &cards,
                Action::ActivateManaAbility { source: island },
            )
            .unwrap();
        }
        apply_action(
            &mut state,
            &cards,
            Action::ActivateManaAbility { source: sol_ring },
        )
        .unwrap();
        assert_eq!(state.mana.blue, 2);
        assert_eq!(state.mana.colorless, 2);

        apply_action(
            &mut state,
            &cards,
            Action::CastCommander {
                payment: ManaPayment {
                    blue: 2,
                    colorless: 2,
                    ..ManaPayment::default()
                },
            },
        )
        .unwrap();
        let urza_resolution = apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        assert_eq!(
            urza_resolution.observations,
            vec![
                RulesObservation::PermanentEntered {
                    card: URZA,
                    face: CardFace::Front,
                    token: false,
                },
                RulesObservation::PermanentEntered {
                    card: CONSTRUCT,
                    face: CardFace::Front,
                    token: true,
                },
            ]
        );
        assert_eq!(state.commander.zone, CommanderZone::Battlefield);
        assert_eq!(state.commander.command_zone_casts, 1);

        let construct = object_for(&state, CONSTRUCT);
        assert!(state.battlefield.get(construct).unwrap().summoning_sick);
        apply_action(
            &mut state,
            &cards,
            Action::ActivateUrzaArtifactMana {
                artifact: construct,
            },
        )
        .unwrap();
        assert_eq!(state.mana.blue, 1);
        assert!(state.battlefield.get(construct).unwrap().tapped);
    }

    #[test]
    fn phase_progression_stops_after_turn_six_without_mutating_horizon_state() {
        let mut horizon = TrueState {
            turn: HORIZON_TURN,
            phase: Phase::OpponentCycle,
            window: Window::None,
            mana: ManaPool {
                blue: 1,
                ..ManaPool::default()
            },
            ..TrueState::default()
        };
        let before = horizon.clone();
        assert_eq!(
            advance_automatic(&mut horizon),
            Err(RuleError::HorizonReached)
        );
        assert_eq!(horizon, before);
    }

    #[test]
    fn staged_tutor_observation_is_hidden_order_invariant_and_policy_actions_use_information_only()
    {
        let cards = TestCards::r3();
        let build = |library: Vec<CardDefId>| TrueState {
            turn: 1,
            phase: Phase::PrecombatMain,
            window: Window::Priority,
            library: TrueLibrary::unknown(library),
            hand: CardZone::new(vec![MYSTICAL]),
            mana: ManaPool {
                blue: 1,
                ..ManaPool::default()
            },
            ..TrueState::default()
        };

        let mut left = build(vec![TARGET_A, KEY, TARGET_B, TARGET_C]);
        let mut right = build(vec![TARGET_C, TARGET_B, KEY, TARGET_A]);

        for state in [&mut left, &mut right] {
            apply_action(
                state,
                &cards,
                Action::CastFromHand {
                    card: MYSTICAL,
                    payment: ManaPayment {
                        blue: 1,
                        ..ManaPayment::default()
                    },
                },
            )
            .unwrap();
        }
        let left_observation = apply_action(&mut left, &cards, Action::PassPriority).unwrap();
        let right_observation = apply_action(&mut right, &cards, Action::PassPriority).unwrap();

        assert_eq!(left_observation, right_observation);
        assert_eq!(left.window, Window::PostObservation);
        assert!(matches!(left.pending, PendingDecision::TutorTarget { .. }));

        let left_info = urza_info::observe(&left).unwrap();
        let right_info = urza_info::observe(&right).unwrap();
        assert_eq!(left_info, right_info);
        assert_eq!(
            legal_contingent_actions(&left_info, &cards),
            legal_contingent_actions(&right_info, &cards)
        );
        assert_eq!(
            legal_contingent_actions(&left_info, &cards),
            vec![
                Action::ChooseSearchTarget {
                    target: Some(TARGET_A)
                },
                Action::ChooseSearchTarget {
                    target: Some(TARGET_B)
                },
                Action::ChooseSearchTarget {
                    target: Some(TARGET_C)
                },
                Action::ChooseSearchTarget { target: None },
            ]
        );
    }

    #[test]
    fn tutor_target_branches_delete_from_one_shared_pre_target_shuffle_ranking() {
        let cards = TestCards::r3();
        let mut base = TrueState {
            turn: 1,
            phase: Phase::PrecombatMain,
            window: Window::Priority,
            library: TrueLibrary::unknown(vec![
                TARGET_A, KEY, TARGET_B, TARGET_C, ISLAND, SOL_RING,
            ]),
            hand: CardZone::new(vec![MYSTICAL]),
            mana: ManaPool {
                blue: 1,
                ..ManaPool::default()
            },
            ..TrueState::default()
        };
        apply_action(
            &mut base,
            &cards,
            Action::CastFromHand {
                card: MYSTICAL,
                payment: ManaPayment {
                    blue: 1,
                    ..ManaPayment::default()
                },
            },
        )
        .unwrap();
        apply_action(&mut base, &cards, Action::PassPriority).unwrap();

        let mut choose_a = base.clone();
        let mut choose_b = base;
        let rng = GameRngContext {
            root: RootSeed::from_u64(31337),
            world: WorldId(2),
            logical_event: LogicalEventId(91),
        };
        apply_action_with_rng(
            &mut choose_a,
            &cards,
            Action::ChooseSearchTarget {
                target: Some(TARGET_A),
            },
            rng,
        )
        .unwrap();
        apply_action_with_rng(
            &mut choose_b,
            &cards,
            Action::ChooseSearchTarget {
                target: Some(TARGET_B),
            },
            rng,
        )
        .unwrap();

        assert_eq!(choose_a.library.known_top(), &[TARGET_A]);
        assert_eq!(choose_b.library.known_top(), &[TARGET_B]);
        assert_eq!(choose_a.rng_occurrence_cursor, 1);
        assert_eq!(choose_b.rng_occurrence_cursor, 1);

        let common_order = |state: &TrueState| {
            state
                .library
                .cards()
                .iter()
                .copied()
                .filter(|card| !matches!(*card, TARGET_A | TARGET_B))
                .collect::<Vec<_>>()
        };
        assert_eq!(common_order(&choose_a), common_order(&choose_b));
    }

    #[test]
    fn zero_target_tutor_has_one_forced_no_find_action_and_resolves_without_blocking() {
        let cards = TestCards::r3();
        let mut state = TrueState {
            turn: 1,
            phase: Phase::PrecombatMain,
            window: Window::Priority,
            library: TrueLibrary::unknown(vec![KEY, ISLAND, SOL_RING]),
            hand: CardZone::new(vec![MYSTICAL]),
            mana: ManaPool {
                blue: 1,
                ..ManaPool::default()
            },
            ..TrueState::default()
        };
        apply_action(
            &mut state,
            &cards,
            Action::CastFromHand {
                card: MYSTICAL,
                payment: ManaPayment {
                    blue: 1,
                    ..ManaPayment::default()
                },
            },
        )
        .unwrap();
        let observation = apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        assert_eq!(
            observation.observations,
            vec![RulesObservation::SearchAvailable {
                source: MYSTICAL,
                candidates: Vec::new(),
                may_fail: true,
            }]
        );

        let info = urza_info::observe(&state).unwrap();
        assert_eq!(
            legal_contingent_actions(&info, &cards),
            vec![Action::ChooseSearchTarget { target: None }]
        );
        apply_action_with_rng(
            &mut state,
            &cards,
            Action::ChooseSearchTarget { target: None },
            GameRngContext {
                root: RootSeed::from_u64(8),
                world: WorldId(0),
                logical_event: LogicalEventId(7),
            },
        )
        .unwrap();
        assert!(matches!(state.pending, PendingDecision::None));
        assert_eq!(state.window, Window::Priority);
        assert_eq!(state.rng_occurrence_cursor, 1);
    }

    #[test]
    fn spellseeker_enters_before_post_observation_tutor_choice() {
        let cards = TestCards::r3();
        let mut state = TrueState {
            turn: 1,
            phase: Phase::PrecombatMain,
            window: Window::Priority,
            library: TrueLibrary::unknown(vec![TARGET_A, KEY]),
            hand: CardZone::new(vec![SPELLSEEKER]),
            mana: ManaPool {
                blue: 1,
                colorless: 2,
                ..ManaPool::default()
            },
            ..TrueState::default()
        };
        apply_action(
            &mut state,
            &cards,
            Action::CastFromHand {
                card: SPELLSEEKER,
                payment: ManaPayment {
                    blue: 1,
                    colorless: 2,
                    ..ManaPayment::default()
                },
            },
        )
        .unwrap();
        let transition = apply_action(&mut state, &cards, Action::PassPriority).unwrap();

        assert!(
            state
                .battlefield
                .permanents()
                .iter()
                .any(|permanent| permanent.card == SPELLSEEKER)
        );
        assert_eq!(state.window, Window::PostObservation);
        assert!(matches!(
            state.pending,
            PendingDecision::TutorTarget {
                source: SourceRef {
                    object_id: Some(_),
                    card: SPELLSEEKER
                }
            }
        ));
        assert_eq!(
            transition.observations,
            vec![
                RulesObservation::PermanentEntered {
                    card: SPELLSEEKER,
                    face: CardFace::Front,
                    token: false,
                },
                RulesObservation::SearchAvailable {
                    source: SPELLSEEKER,
                    candidates: vec![TARGET_A],
                    may_fail: true,
                },
            ]
        );
    }

    fn artifact_permanent(object: u32, card: CardDefId) -> PermanentState {
        PermanentState {
            object_id: ObjectId(object),
            card,
            face: CardFace::Front,
            tapped: false,
            summoning_sick: false,
            token: false,
            counters: CounterState::default(),
            mode: PermanentMode::Normal,
            attached_to: None,
            granted_ability: None,
        }
    }

    #[test]
    fn whir_commits_x_and_improvise_before_search_observation() {
        let cards = TestCards::r3();
        let mut state = TrueState {
            turn: 1,
            phase: Phase::PrecombatMain,
            window: Window::Priority,
            library: TrueLibrary::unknown(vec![ARTIFACT_MV2, ARTIFACT_MV3, TARGET_A]),
            hand: CardZone::new(vec![WHIR]),
            battlefield: BattlefieldZone::new(vec![
                artifact_permanent(1, KEY),
                artifact_permanent(2, SOL_RING),
            ]),
            mana: ManaPool {
                blue: 3,
                ..ManaPool::default()
            },
            ..TrueState::default()
        };

        apply_action(
            &mut state,
            &cards,
            Action::CastWhir {
                card: WHIR,
                x_value: 2,
                payment: ManaPayment {
                    blue: 3,
                    ..ManaPayment::default()
                },
                improvise_sources: vec![ObjectId(1), ObjectId(2)],
            },
        )
        .unwrap();
        assert!(state.battlefield.get(ObjectId(1)).unwrap().tapped);
        assert!(state.battlefield.get(ObjectId(2)).unwrap().tapped);
        assert!(matches!(
            state.stack.last(),
            Some(StackObject::Spell {
                card: WHIR,
                x_value: Some(2),
                ..
            })
        ));

        let observation = apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        assert_eq!(
            observation.observations,
            vec![RulesObservation::SearchAvailable {
                source: WHIR,
                candidates: vec![ARTIFACT_MV2],
                may_fail: true,
            }]
        );
        assert!(matches!(
            state.pending,
            PendingDecision::WhirTarget { x_value: 2, .. }
        ));
    }

    #[test]
    fn reshape_sacrifices_as_casting_cost_then_stages_mv_bounded_search() {
        let cards = TestCards::r3();
        let mut state = TrueState {
            turn: 1,
            phase: Phase::PrecombatMain,
            window: Window::Priority,
            library: TrueLibrary::unknown(vec![ARTIFACT_MV2, ARTIFACT_MV3]),
            hand: CardZone::new(vec![RESHAPE]),
            battlefield: BattlefieldZone::new(vec![artifact_permanent(1, KEY)]),
            mana: ManaPool {
                blue: 2,
                colorless: 2,
                ..ManaPool::default()
            },
            ..TrueState::default()
        };

        apply_action(
            &mut state,
            &cards,
            Action::CastReshape {
                card: RESHAPE,
                x_value: 2,
                sacrifice: ObjectId(1),
                payment: ManaPayment {
                    blue: 2,
                    colorless: 2,
                    ..ManaPayment::default()
                },
            },
        )
        .unwrap();
        assert!(state.battlefield.get(ObjectId(1)).is_none());
        assert_eq!(state.graveyard.cards(), &[KEY]);

        let transition = apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        assert_eq!(
            transition.observations,
            vec![RulesObservation::SearchAvailable {
                source: RESHAPE,
                candidates: vec![ARTIFACT_MV2],
                may_fail: true,
            }]
        );
    }

    #[test]
    fn transmute_stages_sacrifice_search_and_difference_payment_with_mana_abilities() {
        let cards = TestCards::r3();
        let mut state = TrueState {
            turn: 1,
            phase: Phase::PrecombatMain,
            window: Window::Priority,
            library: TrueLibrary::unknown(vec![ARTIFACT_MV3, TARGET_A]),
            hand: CardZone::new(vec![TRANSMUTE]),
            battlefield: BattlefieldZone::new(vec![
                artifact_permanent(1, KEY),
                artifact_permanent(2, SOL_RING),
            ]),
            mana: ManaPool {
                blue: 2,
                ..ManaPool::default()
            },
            ..TrueState::default()
        };

        apply_action(
            &mut state,
            &cards,
            Action::CastFromHand {
                card: TRANSMUTE,
                payment: ManaPayment {
                    blue: 2,
                    ..ManaPayment::default()
                },
            },
        )
        .unwrap();
        apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        assert!(matches!(
            state.pending,
            PendingDecision::TransmuteSacrifice { .. }
        ));
        assert_eq!(state.window, Window::Resolving);

        let info = urza_info::observe(&state).unwrap();
        let sacrifice_action = legal_contingent_actions(&info, &cards)
            .into_iter()
            .find(|action| {
                matches!(
                    action,
                    Action::ChooseTransmuteSacrifice { artifact }
                        if *artifact == info
                            .battlefield
                            .iter()
                            .find(|permanent| permanent.card == KEY)
                            .unwrap()
                            .canonical_id
                )
            })
            .unwrap();
        apply_action(&mut state, &cards, sacrifice_action).unwrap();
        assert!(matches!(
            state.pending,
            PendingDecision::TransmuteTarget {
                sacrificed_mana_value: 1,
                ..
            }
        ));

        apply_action_with_rng(
            &mut state,
            &cards,
            Action::ChooseSearchTarget {
                target: Some(ARTIFACT_MV3),
            },
            GameRngContext {
                root: RootSeed::from_u64(99),
                world: WorldId(0),
                logical_event: LogicalEventId(41),
            },
        )
        .unwrap();
        assert!(matches!(
            state.pending,
            PendingDecision::TransmuteDifferencePayment {
                target: ARTIFACT_MV3,
                difference: GenericCost(2),
                ..
            }
        ));
        assert_eq!(state.window, Window::Resolving);

        apply_action(
            &mut state,
            &cards,
            Action::ActivateManaAbility {
                source: ObjectId(2),
            },
        )
        .unwrap();
        let completion = apply_action(
            &mut state,
            &cards,
            Action::PayTransmuteDifference {
                payment: Some(ManaPayment {
                    colorless: 2,
                    ..ManaPayment::default()
                }),
            },
        )
        .unwrap();
        assert!(
            state
                .battlefield
                .permanents()
                .iter()
                .any(|permanent| permanent.card == ARTIFACT_MV3)
        );
        assert_eq!(
            completion.observations[0],
            RulesObservation::SearchCompleted {
                source: TRANSMUTE,
                target: Some(ARTIFACT_MV3),
                destination: SearchDestination::Battlefield,
            }
        );
    }

    #[test]
    fn repurposing_bay_commits_costs_before_exact_mv_plus_one_search() {
        let cards = TestCards::r3();
        let mut state = TrueState {
            turn: 1,
            phase: Phase::PrecombatMain,
            window: Window::Priority,
            library: TrueLibrary::unknown(vec![ARTIFACT_MV2, ARTIFACT_MV3]),
            battlefield: BattlefieldZone::new(vec![
                artifact_permanent(1, BAY),
                artifact_permanent(2, ARTIFACT_MV2),
            ]),
            mana: ManaPool {
                colorless: 2,
                ..ManaPool::default()
            },
            ..TrueState::default()
        };

        apply_action(
            &mut state,
            &cards,
            Action::ActivateRepurposingBay {
                source: ObjectId(1),
                sacrifice: ObjectId(2),
                payment: ManaPayment {
                    colorless: 2,
                    ..ManaPayment::default()
                },
            },
        )
        .unwrap();
        assert!(state.battlefield.get(ObjectId(1)).unwrap().tapped);
        assert!(state.battlefield.get(ObjectId(2)).is_none());
        assert!(matches!(
            state.stack.last(),
            Some(StackObject::ActivatedAbility {
                ability: ABILITY_REPURPOSING_BAY_SEARCH,
                parameter: Some(2),
                ..
            })
        ));

        let transition = apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        assert_eq!(
            transition.observations,
            vec![RulesObservation::SearchAvailable {
                source: BAY,
                candidates: vec![ARTIFACT_MV3],
                may_fail: true,
            }]
        );

        let completion = apply_action_with_rng(
            &mut state,
            &cards,
            Action::ChooseSearchTarget {
                target: Some(ARTIFACT_MV3),
            },
            GameRngContext {
                root: RootSeed::from_u64(7),
                world: WorldId(1),
                logical_event: LogicalEventId(12),
            },
        )
        .unwrap();
        assert_eq!(
            completion.observations[0],
            RulesObservation::SearchCompleted {
                source: BAY,
                target: Some(ARTIFACT_MV3),
                destination: SearchDestination::Battlefield,
            }
        );
    }

    #[test]
    fn top_look_observes_then_factors_reorder_choice() {
        let cards = TestCards::r3();
        let mut state = TrueState {
            turn: 1,
            phase: Phase::PrecombatMain,
            window: Window::Priority,
            library: TrueLibrary::unknown(vec![TARGET_A, TARGET_B, TARGET_C, ISLAND]),
            battlefield: BattlefieldZone::new(vec![artifact_permanent(1, TOP)]),
            mana: ManaPool {
                colorless: 1,
                ..ManaPool::default()
            },
            ..TrueState::default()
        };
        apply_action(
            &mut state,
            &cards,
            Action::ActivateTopLook {
                source: ObjectId(1),
                payment: ManaPayment {
                    colorless: 1,
                    ..ManaPayment::default()
                },
            },
        )
        .unwrap();
        let observed = apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        assert_eq!(
            observed.observations,
            vec![RulesObservation::TopCardsObserved {
                source: TOP,
                cards: vec![TARGET_A, TARGET_B, TARGET_C],
            }]
        );
        let info = urza_info::observe(&state).unwrap();
        assert_eq!(legal_contingent_actions(&info, &cards).len(), 6);

        apply_action(
            &mut state,
            &cards,
            Action::ChooseTopOrder {
                order: vec![TARGET_C, TARGET_A, TARGET_B],
            },
        )
        .unwrap();
        assert_eq!(
            state.library.cards(),
            &[TARGET_C, TARGET_A, TARGET_B, ISLAND]
        );
        assert_eq!(state.library.knowledge().known_top, 3);
    }

    #[test]
    fn top_draw_is_atomic_draw_then_put_top_on_library() {
        let cards = TestCards::r3();
        let mut state = TrueState {
            turn: 1,
            phase: Phase::PrecombatMain,
            window: Window::Priority,
            library: TrueLibrary::unknown(vec![TARGET_A, TARGET_B]),
            battlefield: BattlefieldZone::new(vec![artifact_permanent(1, TOP)]),
            ..TrueState::default()
        };
        apply_action(
            &mut state,
            &cards,
            Action::ActivateTopDraw {
                source: ObjectId(1),
            },
        )
        .unwrap();
        let transition = apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        assert_eq!(
            transition.observations,
            vec![RulesObservation::CardsDrawn(vec![TARGET_A])]
        );
        assert_eq!(state.hand.cards(), &[TARGET_A]);
        assert_eq!(state.library.cards(), &[TOP, TARGET_B]);
        assert_eq!(state.library.known_top(), &[TOP]);
        assert!(state.battlefield.get(ObjectId(1)).is_none());
        assert!(matches!(state.pending, PendingDecision::None));
    }

    #[test]
    fn generic_scry_observes_before_top_bottom_choice() {
        let mut state = TrueState {
            turn: 1,
            phase: Phase::PrecombatMain,
            window: Window::Resolving,
            library: TrueLibrary::unknown(vec![TARGET_A, TARGET_B, TARGET_C]),
            ..TrueState::default()
        };
        let source = SourceRef {
            object_id: None,
            card: CardDefId(500),
        };
        let transition = stage_scry(&mut state, source, 2).unwrap();
        assert_eq!(
            transition.observations,
            vec![RulesObservation::ScryCardsObserved {
                source: CardDefId(500),
                cards: vec![TARGET_A, TARGET_B],
            }]
        );
        let info = urza_info::observe(&state).unwrap();
        assert!(!legal_contingent_actions(&info, &TestCards::r3()).is_empty());

        apply_action(
            &mut state,
            &TestCards::r3(),
            Action::ChooseScry {
                top: vec![TARGET_B],
                bottom: vec![TARGET_A],
            },
        )
        .unwrap();
        assert_eq!(state.library.cards(), &[TARGET_B, TARGET_C, TARGET_A]);
        assert_eq!(state.library.known_top(), &[TARGET_B]);
        assert_eq!(state.library.known_bottom(), &[TARGET_A]);
    }

    #[test]
    fn urza_spin_requires_rng_creates_persistent_permission_and_expires_at_eot() {
        let cards = TestCards::r3();
        let mut state = TrueState {
            turn: 2,
            phase: Phase::PrecombatMain,
            window: Window::Priority,
            library: TrueLibrary::unknown(vec![ISLAND, TARGET_A, TARGET_B]),
            battlefield: BattlefieldZone::new(vec![artifact_permanent(1, URZA)]),
            mana: ManaPool {
                colorless: 5,
                ..ManaPool::default()
            },
            ..TrueState::default()
        };
        apply_action(
            &mut state,
            &cards,
            Action::ActivateUrzaSpin {
                source: ObjectId(1),
                payment: ManaPayment {
                    colorless: 5,
                    ..ManaPayment::default()
                },
            },
        )
        .unwrap();
        assert_eq!(
            apply_action(&mut state, &cards, Action::PassPriority),
            Err(RuleError::MissingGameRngContext)
        );
        let transition = apply_action_with_rng(
            &mut state,
            &cards,
            Action::PassPriority,
            GameRngContext {
                root: RootSeed::from_u64(123),
                world: WorldId(4),
                logical_event: LogicalEventId(300),
            },
        )
        .unwrap();
        assert_eq!(state.urza_permissions.len(), 1);
        assert_eq!(state.exile.len(), 1);
        assert_eq!(state.rng_occurrence_cursor, 1);
        assert!(matches!(
            transition.observations.as_slice(),
            [RulesObservation::UrzaCardExiled { .. }]
        ));

        state.phase = Phase::EndStep;
        state.window = Window::Priority;
        apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        assert!(state.urza_permissions.is_empty());
        assert!(
            state
                .delayed_events
                .iter()
                .all(|event| !matches!(event, DelayedEvent::PermissionExpiry { .. }))
        );
    }

    #[test]
    fn urza_permission_can_play_an_exiled_land_face_without_revealing_future_order() {
        let cards = TestCards::r3();
        let mut state = TrueState {
            turn: 2,
            phase: Phase::PrecombatMain,
            window: Window::Priority,
            exile: CardZone::new(vec![MDFC_LAND]),
            urza_permissions: vec![urza_core::UrzaPermission {
                permission_id: PermissionId(7),
                card: MDFC_LAND,
                expires_turn: 2,
                free_cast: true,
                source: SourceRef {
                    object_id: None,
                    card: URZA,
                },
            }],
            delayed_events: vec![DelayedEvent::PermissionExpiry {
                permission: PermissionId(7),
                due_turn: 2,
            }],
            ..TrueState::default()
        };
        apply_action(
            &mut state,
            &cards,
            Action::PlayUrzaPermission {
                permission_slot: 0,
                face: CardFace::Back,
            },
        )
        .unwrap();
        let permanent = state
            .battlefield
            .permanents()
            .iter()
            .find(|permanent| permanent.card == MDFC_LAND)
            .unwrap();
        assert_eq!(permanent.face, CardFace::Back);
        assert!(state.urza_permissions.is_empty());
        assert!(state.exile.cards().is_empty());
    }

    #[test]
    fn saga_chapters_progress_and_final_search_uses_printed_cost_class_then_sacrifices() {
        let cards = TestCards::r3();
        let mut state = TrueState {
            turn: 1,
            phase: Phase::PrecombatMain,
            window: Window::Priority,
            library: TrueLibrary::unknown(vec![ARTIFACT_MV0, ARTIFACT_X_MV0, TOP]),
            hand: CardZone::new(vec![SAGA]),
            ..TrueState::default()
        };

        apply_action(
            &mut state,
            &cards,
            Action::PlayLand {
                card: SAGA,
                entry: LandEntryChoice::Default,
            },
        )
        .unwrap();
        let saga_object = object_for(&state, SAGA);
        assert_eq!(state.battlefield.get(saga_object).unwrap().counters.lore, 1);
        assert!(matches!(
            state.stack.last(),
            Some(StackObject::ControlledTrigger {
                ability: ABILITY_SAGA_CHAPTER_I,
                ..
            })
        ));
        apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        apply_action(
            &mut state,
            &cards,
            Action::ActivateManaAbility {
                source: saga_object,
            },
        )
        .unwrap();
        assert_eq!(state.mana.colorless, 1);

        state.phase = Phase::Draw;
        state.window = Window::Priority;
        apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        assert_eq!(state.battlefield.get(saga_object).unwrap().counters.lore, 2);
        let chapter_two = apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        assert!(matches!(
            chapter_two.observations.as_slice(),
            [RulesObservation::PermanentEntered { token: true, .. }]
        ));

        state.phase = Phase::Draw;
        state.window = Window::Priority;
        apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        assert_eq!(state.battlefield.get(saga_object).unwrap().counters.lore, 3);
        let search = apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        assert_eq!(
            search.observations,
            vec![RulesObservation::SearchAvailable {
                source: SAGA,
                candidates: vec![TOP, ARTIFACT_MV0],
                may_fail: true,
            }]
        );
        assert!(state.battlefield.get(saga_object).is_some());

        let completion = apply_action_with_rng(
            &mut state,
            &cards,
            Action::ChooseSearchTarget { target: Some(TOP) },
            GameRngContext {
                root: RootSeed::from_u64(88),
                world: WorldId(0),
                logical_event: LogicalEventId(700),
            },
        )
        .unwrap();
        assert!(completion.observations.iter().any(|observation| {
            matches!(
                observation,
                RulesObservation::PermanentEntered { card: TOP, .. }
            )
        }));
        assert!(state.battlefield.get(saga_object).is_none());
        assert!(state.graveyard.cards().contains(&SAGA));
    }

    #[test]
    fn tezzeret_minus_three_pays_loyalty_before_observing_mv_one_artifact_search() {
        let cards = TestCards::r3();
        let mut state = TrueState {
            turn: 1,
            phase: Phase::PrecombatMain,
            window: Window::Priority,
            library: TrueLibrary::unknown(vec![ARTIFACT_MV0, TOP, ARTIFACT_MV2]),
            hand: CardZone::new(vec![TEZZERET]),
            mana: ManaPool {
                colorless: 3,
                ..ManaPool::default()
            },
            ..TrueState::default()
        };
        apply_action(
            &mut state,
            &cards,
            Action::CastFromHand {
                card: TEZZERET,
                payment: ManaPayment {
                    colorless: 3,
                    ..ManaPayment::default()
                },
            },
        )
        .unwrap();
        apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        let tezzeret = object_for(&state, TEZZERET);
        assert_eq!(state.battlefield.get(tezzeret).unwrap().counters.loyalty, 4);

        apply_action(
            &mut state,
            &cards,
            Action::ActivateTezzeretMinusThree { source: tezzeret },
        )
        .unwrap();
        assert_eq!(state.battlefield.get(tezzeret).unwrap().counters.loyalty, 1);
        let search = apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        assert_eq!(
            search.observations,
            vec![RulesObservation::SearchAvailable {
                source: TEZZERET,
                candidates: vec![TOP, ARTIFACT_MV0],
                may_fail: true,
            }]
        );

        apply_action_with_rng(
            &mut state,
            &cards,
            Action::ChooseSearchTarget { target: Some(TOP) },
            GameRngContext {
                root: RootSeed::from_u64(99),
                world: WorldId(1),
                logical_event: LogicalEventId(701),
            },
        )
        .unwrap();
        assert!(state.hand.cards().contains(&TOP));
        assert!(!state.library.cards().contains(&TOP));
    }

    #[test]
    fn r4_monoliths_tap_for_three_skip_normal_untap_and_use_stack_for_native_untap() {
        let cards = TestCards::r4();
        let mut state = TrueState {
            turn: 2,
            phase: Phase::PrecombatMain,
            window: Window::Priority,
            battlefield: BattlefieldZone::new(vec![
                artifact_permanent(1, BASALT),
                artifact_permanent(2, GRIM),
                artifact_permanent(3, SOL_RING),
            ]),
            ..TrueState::default()
        };

        apply_action(
            &mut state,
            &cards,
            Action::ActivateManaAbility {
                source: ObjectId(1),
            },
        )
        .unwrap();
        assert_eq!(state.mana.colorless, 3);
        assert!(state.battlefield.get(ObjectId(1)).unwrap().tapped);

        apply_action(
            &mut state,
            &cards,
            Action::ActivateNativeArtifactUntap {
                source: ObjectId(1),
                payment: ManaPayment {
                    colorless: 3,
                    ..ManaPayment::default()
                },
            },
        )
        .unwrap();
        assert!(
            state.battlefield.get(ObjectId(1)).unwrap().tapped,
            "native untap uses the stack and has not resolved yet"
        );
        apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        assert!(!state.battlefield.get(ObjectId(1)).unwrap().tapped);

        let mut permanents = state.battlefield.permanents().to_vec();
        for permanent in &mut permanents {
            permanent.tapped = true;
        }
        state.battlefield = BattlefieldZone::new(permanents);
        state.phase = Phase::Untap;
        state.window = Window::None;
        advance_phase(&mut state, &cards).unwrap();

        assert!(state.battlefield.get(ObjectId(1)).unwrap().tapped);
        assert!(state.battlefield.get(ObjectId(2)).unwrap().tapped);
        assert!(!state.battlefield.get(ObjectId(3)).unwrap().tapped);
    }

    #[test]
    fn forensic_gadgeteer_reduces_artifact_activation_costs_with_one_mana_floor() {
        let cards = TestCards::r4();
        let mut state = TrueState {
            turn: 1,
            phase: Phase::PrecombatMain,
            window: Window::Priority,
            battlefield: BattlefieldZone::new(vec![
                artifact_permanent(1, BASALT),
                PermanentState {
                    object_id: ObjectId(2),
                    card: GADGETEER,
                    face: CardFace::Front,
                    tapped: false,
                    summoning_sick: true,
                    token: false,
                    counters: CounterState::default(),
                    mode: PermanentMode::Normal,
                    attached_to: None,
                    granted_ability: None,
                },
            ]),
            ..TrueState::default()
        };

        apply_action(
            &mut state,
            &cards,
            Action::ActivateManaAbility {
                source: ObjectId(1),
            },
        )
        .unwrap();
        assert_eq!(state.mana.colorless, 3);
        apply_action(
            &mut state,
            &cards,
            Action::ActivateNativeArtifactUntap {
                source: ObjectId(1),
                payment: ManaPayment {
                    colorless: 2,
                    ..ManaPayment::default()
                },
            },
        )
        .unwrap();
        assert_eq!(state.mana.colorless, 1);
        apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        apply_action(
            &mut state,
            &cards,
            Action::ActivateManaAbility {
                source: ObjectId(1),
            },
        )
        .unwrap();
        assert_eq!(
            state.mana.colorless, 4,
            "one Basalt/Gadgeteer cycle nets exactly one colorless"
        );

        let top_cost = reduced_artifact_activation_cost(&state, &cards, ObjectId(1), 1).unwrap();
        assert_eq!(top_cost.generic, 1, "reduction cannot cross the one-mana floor");
    }

    #[test]
    fn basalt_gadgeteer_terminal_requires_public_ready_engine_and_urza_context() {
        let cards = TestCards::r4();
        let make = |include_urza: bool, basalt_tapped: bool| {
            let mut permanents = vec![
                PermanentState {
                    object_id: ObjectId(1),
                    card: BASALT,
                    face: CardFace::Front,
                    tapped: basalt_tapped,
                    summoning_sick: false,
                    token: false,
                    counters: CounterState::default(),
                    mode: PermanentMode::Normal,
                    attached_to: None,
                    granted_ability: None,
                },
                PermanentState {
                    object_id: ObjectId(2),
                    card: GADGETEER,
                    face: CardFace::Front,
                    tapped: false,
                    summoning_sick: true,
                    token: false,
                    counters: CounterState::default(),
                    mode: PermanentMode::Normal,
                    attached_to: None,
                    granted_ability: None,
                },
            ];
            if include_urza {
                permanents.push(PermanentState {
                    object_id: ObjectId(3),
                    card: URZA,
                    face: CardFace::Front,
                    tapped: false,
                    summoning_sick: false,
                    token: false,
                    counters: CounterState::default(),
                    mode: PermanentMode::Normal,
                    attached_to: None,
                    granted_ability: None,
                });
            }
            let state = TrueState {
                turn: 4,
                phase: Phase::PrecombatMain,
                window: Window::Priority,
                battlefield: BattlefieldZone::new(permanents),
                ..TrueState::default()
            };
            urza_info::observe(&state).unwrap()
        };

        assert_eq!(
            detect_terminal_win(&make(true, false), &cards),
            Some(WinFamily::BasaltGadgeteer)
        );
        assert_eq!(detect_terminal_win(&make(false, false), &cards), None);
        assert_eq!(detect_terminal_win(&make(true, true), &cards), None);
    }

}
