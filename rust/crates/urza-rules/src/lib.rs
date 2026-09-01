#![forbid(unsafe_code)]

use thiserror::Error;
use urza_core::{
    BattlefieldZone, CardDefId, CommanderZone, CounterState, LibraryKnowledge, ManaPool, ObjectId,
    PendingDecision, PermanentMode, PermanentState, Phase, StackObject, StateValidationError,
    TrueLibrary, TrueState, Window,
};
use urza_rng::{
    EventOccurrence, EventType, LogicalEventId, RngCoordinate, RngDomain, RootSeed, WorldId,
};

pub const RULES_PHASE: &str = "R2";
pub const RULES_VERSION: &str = "r2_core_kernel_v1";
pub const HORIZON_TURN: u8 = 6;

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
    BasicIsland,
    ArtifactPermanent,
    UrzaCommander,
    UrzaConstructToken,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash)]
pub struct CardProfile {
    pub card: CardDefId,
    pub mana_cost: Option<ManaCost>,
    pub role: R2CardRole,
    pub is_artifact: bool,
    pub is_creature: bool,
}

pub trait CardDatabase {
    fn profile(&self, card: CardDefId) -> Option<CardProfile>;
    fn commander_card(&self) -> CardDefId;
    fn urza_construct_token_card(&self) -> CardDefId;
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum Action {
    PassPriority,
    PlayLand {
        card: CardDefId,
    },
    ActivateIslandMana {
        source: ObjectId,
    },
    ActivateUrzaArtifactMana {
        artifact: ObjectId,
    },
    CastFromHand {
        card: CardDefId,
        payment: ManaPayment,
    },
    CastCommander {
        payment: ManaPayment,
    },
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum RulesObservation {
    CardsDrawn(Vec<CardDefId>),
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
    #[error("R2 does not yet support the intrinsic mechanic for card {0:?}")]
    UnsupportedCardMechanic(CardDefId),
    #[error("R2 cannot resolve this stack object yet")]
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
    #[error("object {0:?} is not a supported Island mana source")]
    NotIslandSource(ObjectId),
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
}

pub fn apply_action<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    action: Action,
) -> Result<Transition, RuleError> {
    state.validate()?;
    let transition = match action {
        Action::PassPriority => pass_priority(state, cards)?,
        Action::PlayLand { card } => {
            play_land(state, cards, card)?;
            Transition::default()
        }
        Action::ActivateIslandMana { source } => {
            activate_island_mana(state, cards, source)?;
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
        Action::CastCommander { payment } => {
            cast_commander(state, cards, payment)?;
            Transition::default()
        }
    };
    state.validate()?;
    Ok(transition)
}

pub fn advance_phase(state: &mut TrueState) -> Result<Transition, RuleError> {
    state.validate()?;
    ensure_no_pending_decision(state)?;
    if !state.stack.is_empty() {
        return Err(RuleError::IllegalTiming);
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
                permanent.tapped = false;
                permanent.summoning_sick = false;
            }
            state.battlefield = BattlefieldZone::new(permanents);
            state.phase = Phase::Upkeep;
            state.window = Window::Priority;
        }
        Phase::Upkeep => {
            state.phase = Phase::Draw;
            state.window = Window::Priority;
            let drawn = draw_cards(state, 1)?;
            transition
                .observations
                .push(RulesObservation::CardsDrawn(drawn));
        }
        Phase::Draw => {
            state.phase = Phase::PrecombatMain;
            state.window = Window::Priority;
        }
        Phase::PrecombatMain => {
            state.phase = Phase::EndStep;
            state.window = Window::Priority;
        }
        Phase::EndStep => {
            state.phase = Phase::OpponentCycle;
            state.window = Window::None;
        }
        Phase::OpponentCycle => {
            if state.turn >= HORIZON_TURN {
                return Err(RuleError::HorizonReached);
            }
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
    LibrarySearchObservation { candidates }
}

fn pass_priority<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
) -> Result<Transition, RuleError> {
    ensure_priority(state)?;
    ensure_no_pending_decision(state)?;

    if state.stack.is_empty() {
        return advance_phase(state);
    }

    resolve_top_stack_object(state, cards)?;
    Ok(Transition::default())
}

fn play_land<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    card: CardDefId,
) -> Result<(), RuleError> {
    ensure_sorcery_window(state)?;
    if state.land_played_this_turn {
        return Err(RuleError::LandAlreadyPlayed);
    }

    let profile = card_profile(cards, card)?;
    if profile.role != R2CardRole::BasicIsland {
        return Err(RuleError::UnsupportedCardMechanic(card));
    }
    if !state.hand.cards().contains(&card) {
        return Err(RuleError::CardNotInHand(card));
    }

    let object_id = next_object_id(state)?;
    let removed = state.hand.remove_one(card);
    debug_assert!(removed);
    insert_permanent(
        state,
        PermanentState {
            object_id,
            card,
            tapped: false,
            summoning_sick: false,
            token: false,
            counters: CounterState::default(),
            mode: PermanentMode::Normal,
            attached_to: None,
            granted_ability: None,
        },
    );
    state.land_played_this_turn = true;
    Ok(())
}

fn activate_island_mana<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    source: ObjectId,
) -> Result<(), RuleError> {
    ensure_priority(state)?;
    ensure_no_pending_decision(state)?;

    let permanent = battlefield_permanent(state, source)?.clone();
    if permanent.tapped {
        return Err(RuleError::PermanentTapped(source));
    }
    if card_profile(cards, permanent.card)?.role != R2CardRole::BasicIsland {
        return Err(RuleError::NotIslandSource(source));
    }

    set_tapped(state, source)?;
    state.mana.blue = state
        .mana
        .blue
        .checked_add(1)
        .ok_or(RuleError::ArithmeticOverflow)?;
    Ok(())
}

fn activate_urza_artifact_mana<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    artifact: ObjectId,
) -> Result<(), RuleError> {
    ensure_priority(state)?;
    ensure_no_pending_decision(state)?;

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

    set_tapped(state, artifact)?;
    state.mana.blue = state
        .mana
        .blue
        .checked_add(1)
        .ok_or(RuleError::ArithmeticOverflow)?;
    Ok(())
}

fn cast_from_hand<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    card: CardDefId,
    payment: ManaPayment,
) -> Result<(), RuleError> {
    ensure_sorcery_window(state)?;
    let profile = card_profile(cards, card)?;
    if !matches!(
        profile.role,
        R2CardRole::ArtifactPermanent | R2CardRole::UrzaCommander
    ) {
        return Err(RuleError::UnsupportedCardMechanic(card));
    }
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

    state.stack.push(StackObject::Spell { object_id, card });
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
) -> Result<(), RuleError> {
    let Some(top) = state.stack.last().cloned() else {
        return Ok(());
    };
    let StackObject::Spell { object_id, card } = top else {
        return Err(RuleError::UnsupportedStackObject);
    };

    let profile = card_profile(cards, card)?;
    if !matches!(
        profile.role,
        R2CardRole::ArtifactPermanent | R2CardRole::UrzaCommander
    ) {
        return Err(RuleError::UnsupportedCardMechanic(card));
    }

    let popped = state.stack.pop();
    debug_assert!(popped.is_some());
    state.window = Window::Resolving;

    insert_permanent(
        state,
        PermanentState {
            object_id,
            card,
            tapped: false,
            summoning_sick: profile.is_creature,
            token: false,
            counters: CounterState::default(),
            mode: PermanentMode::Normal,
            attached_to: None,
            granted_ability: None,
        },
    );

    if profile.role == R2CardRole::UrzaCommander {
        state.commander.zone = CommanderZone::Battlefield;
        let construct_id = next_object_id(state)?;
        let construct_card = cards.urza_construct_token_card();
        let construct_profile = card_profile(cards, construct_card)?;
        if construct_profile.role != R2CardRole::UrzaConstructToken
            || !construct_profile.is_artifact
            || !construct_profile.is_creature
        {
            return Err(RuleError::UnsupportedCardMechanic(construct_card));
        }
        insert_permanent(
            state,
            PermanentState {
                object_id: construct_id,
                card: construct_card,
                tapped: false,
                summoning_sick: true,
                token: true,
                counters: CounterState::default(),
                mode: PermanentMode::Normal,
                attached_to: None,
                granted_ability: None,
            },
        );
    }

    state.window = Window::Priority;
    Ok(())
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
    let mut permanents = state.battlefield.permanents().to_vec();
    let Some(permanent) = permanents
        .iter_mut()
        .find(|permanent| permanent.object_id == object_id)
    else {
        return Err(RuleError::MissingPermanent(object_id));
    };
    permanent.tapped = true;
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
    const KEY: CardDefId = CardDefId(2);
    const URZA: CardDefId = CardDefId(3);
    const CONSTRUCT: CardDefId = CardDefId(4);

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
                    mana_cost: None,
                    role: R2CardRole::BasicIsland,
                    is_artifact: false,
                    is_creature: false,
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
                    role: R2CardRole::ArtifactPermanent,
                    is_artifact: true,
                    is_creature: false,
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
                    is_artifact: false,
                    is_creature: true,
                },
            );
            profiles.insert(
                CONSTRUCT,
                CardProfile {
                    card: CONSTRUCT,
                    mana_cost: None,
                    role: R2CardRole::UrzaConstructToken,
                    is_artifact: true,
                    is_creature: true,
                },
            );
            Self { profiles }
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
    fn search_observation_never_exposes_hidden_library_order() {
        let a = TrueState {
            library: TrueLibrary::unknown(vec![
                CardDefId(9),
                CardDefId(2),
                CardDefId(7),
                CardDefId(4),
            ]),
            ..TrueState::default()
        };
        let b = TrueState {
            library: TrueLibrary::unknown(vec![
                CardDefId(4),
                CardDefId(7),
                CardDefId(2),
                CardDefId(9),
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
    fn draw_updates_known_top_and_all_known_bottom_without_leaking_order() {
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
    fn deterministic_r2_trajectory_covers_land_cast_stack_urza_and_artifact_mana() {
        let cards = TestCards::r2();
        let mut state = TrueState {
            turn: 1,
            phase: Phase::PrecombatMain,
            window: Window::Priority,
            hand: CardZone::new(vec![ISLAND, KEY]),
            commander: CommanderState {
                zone: CommanderZone::CommandZone,
                command_zone_casts: 0,
            },
            ..TrueState::default()
        };

        apply_action(&mut state, &cards, Action::PlayLand { card: ISLAND }).unwrap();
        let island = state
            .battlefield
            .permanents()
            .iter()
            .find(|permanent| permanent.card == ISLAND)
            .unwrap()
            .object_id;
        apply_action(
            &mut state,
            &cards,
            Action::ActivateIslandMana { source: island },
        )
        .unwrap();
        assert_eq!(state.mana.blue, 1);

        apply_action(
            &mut state,
            &cards,
            Action::CastFromHand {
                card: KEY,
                payment: ManaPayment {
                    blue: 1,
                    ..ManaPayment::default()
                },
            },
        )
        .unwrap();
        assert_eq!(state.stack.len(), 1);
        apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        assert!(
            state
                .battlefield
                .permanents()
                .iter()
                .any(|permanent| permanent.card == KEY)
        );

        state.mana = ManaPool {
            blue: 2,
            colorless: 2,
            ..ManaPool::default()
        };
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
        apply_action(&mut state, &cards, Action::PassPriority).unwrap();

        assert_eq!(state.commander.zone, CommanderZone::Battlefield);
        assert_eq!(state.commander.command_zone_casts, 1);
        assert!(
            state
                .battlefield
                .permanents()
                .iter()
                .any(|permanent| permanent.card == URZA)
        );
        let construct = state
            .battlefield
            .permanents()
            .iter()
            .find(|permanent| permanent.card == CONSTRUCT)
            .unwrap();
        assert!(construct.token);
        assert!(construct.summoning_sick);

        let key = state
            .battlefield
            .permanents()
            .iter()
            .find(|permanent| permanent.card == KEY)
            .unwrap()
            .object_id;
        apply_action(
            &mut state,
            &cards,
            Action::ActivateUrzaArtifactMana { artifact: key },
        )
        .unwrap();
        assert_eq!(state.mana.blue, 1);
        assert!(state.battlefield.get(key).unwrap().tapped);
    }

    #[test]
    fn phase_progression_draws_before_main_and_stops_after_turn_six() {
        let cards = TestCards::r2();
        let mut state = TrueState {
            turn: 1,
            phase: Phase::Upkeep,
            window: Window::Priority,
            library: TrueLibrary::unknown(vec![CardDefId(9), CardDefId(8)]),
            ..TrueState::default()
        };

        let transition = apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        assert_eq!(state.phase, Phase::Draw);
        assert_eq!(
            transition.observations,
            vec![RulesObservation::CardsDrawn(vec![CardDefId(9)])]
        );
        apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        assert_eq!(state.phase, Phase::PrecombatMain);

        let mut horizon = TrueState {
            turn: HORIZON_TURN,
            phase: Phase::OpponentCycle,
            window: Window::None,
            ..TrueState::default()
        };
        assert_eq!(advance_phase(&mut horizon), Err(RuleError::HorizonReached));
        assert_eq!(horizon.turn, HORIZON_TURN);
    }
}
