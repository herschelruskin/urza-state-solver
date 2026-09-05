#![forbid(unsafe_code)]

use thiserror::Error;
use urza_core::{PendingDecision, Phase, TrueState, Window};
use urza_info::{InformationState, ObservationError, observe};
use urza_policy::{
    ActionToken, DeterministicPolicy, PolicyActionClass, PolicyError, PolicyPublicKey,
};
use urza_policy_bridge::{BridgeError, CandidateBridge};
use urza_rng::{LogicalEventId, RootSeed, WorldId};
use urza_rules::{
    CardDatabase, GameRngContext, RuleError, WinFamily, advance_automatic, apply_action_with_rng,
    detect_terminal_win,
};

pub const ROLLOUT_VERSION: &str = "r5_deterministic_rollout_v1";
pub const DEFAULT_MAX_STEPS: u32 = 4096;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct RolloutConfig {
    pub root: RootSeed,
    pub world: WorldId,
    pub max_steps: u32,
}

impl Default for RolloutConfig {
    fn default() -> Self {
        Self {
            root: RootSeed::from_u64(0x5235_524f_4c4c_4f55),
            world: WorldId(0),
            max_steps: DEFAULT_MAX_STEPS,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum RolloutStop {
    Terminal(WinFamily),
    Horizon,
    StepLimit,
    NoCandidate,
}

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct RolloutStep {
    pub index: u32,
    pub turn: u8,
    pub phase: Phase,
    pub window: Window,
    pub class: PolicyActionClass,
    pub key: PolicyPublicKey,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RolloutResult {
    pub final_state: TrueState,
    pub final_information: InformationState,
    pub stop: RolloutStop,
    pub trace: Vec<RolloutStep>,
}

#[derive(Debug, Error)]
pub enum RolloutError {
    #[error(transparent)]
    Bridge(#[from] BridgeError),
    #[error(transparent)]
    Policy(#[from] PolicyError),
    #[error(transparent)]
    Observation(#[from] ObservationError),
    #[error(transparent)]
    Rules(#[from] RuleError),
    #[error("selected decision-local token {0:?} could not be resolved")]
    MissingResolvedAction(ActionToken),
    #[error("rollout trace exceeded u32 step indexing")]
    StepIndexOverflow,
    #[error("rollout logical event id overflow")]
    LogicalEventOverflow,
    #[error("replay trace step {position} declares index {declared}")]
    ReplayStepIndexMismatch { position: u32, declared: u32 },
    #[error("replay stopped before trace step {index}: {stop:?}")]
    ReplayStoppedEarly { index: u32, stop: RolloutStop },
    #[error(
        "replay public decision point mismatch at step {index}: expected turn {expected_turn} {expected_phase:?}/{expected_window:?}, got turn {actual_turn} {actual_phase:?}/{actual_window:?}"
    )]
    ReplayDecisionPointMismatch {
        index: u32,
        expected_turn: u8,
        expected_phase: Phase,
        expected_window: Window,
        actual_turn: u8,
        actual_phase: Phase,
        actual_window: Window,
    },
    #[error("replay semantic candidate is missing at step {0}")]
    ReplayCandidateMissing(u32),
    #[error("replay semantic candidate is ambiguous at step {0}")]
    ReplayCandidateAmbiguous(u32),
}

pub fn rollout<D: CardDatabase>(
    initial: TrueState,
    cards: &D,
    policy: &DeterministicPolicy,
    config: RolloutConfig,
) -> Result<RolloutResult, RolloutError> {
    rollout_with_logical_event_offset(initial, cards, policy, config, 0)
}

pub fn rollout_with_logical_event_offset<D: CardDatabase>(
    initial: TrueState,
    cards: &D,
    policy: &DeterministicPolicy,
    config: RolloutConfig,
    logical_event_offset: u64,
) -> Result<RolloutResult, RolloutError> {
    let mut state = initial;
    let mut trace = Vec::new();

    loop {
        if let Some(stop) = prepare_for_policy(&mut state, cards)? {
            return finish(state, stop, trace);
        }

        if trace.len() >= config.max_steps as usize {
            return finish(state, RolloutStop::StepLimit, trace);
        }

        let bridge = CandidateBridge::build(&state, cards)?;
        let Some(token) = policy.choose(bridge.information(), bridge.candidates())? else {
            return finish(state, RolloutStop::NoCandidate, trace);
        };
        let selected = bridge
            .candidates()
            .iter()
            .find(|candidate| candidate.token == token)
            .cloned()
            .ok_or(RolloutError::MissingResolvedAction(token))?;
        let action = bridge
            .resolved_action(token)
            .ok_or(RolloutError::MissingResolvedAction(token))?;
        let index = u32::try_from(trace.len()).map_err(|_| RolloutError::StepIndexOverflow)?;

        trace.push(RolloutStep {
            index,
            turn: bridge.information().turn,
            phase: bridge.information().phase,
            window: bridge.information().window,
            class: selected.class,
            key: selected.key,
        });

        execute(
            &mut state,
            cards,
            action,
            config,
            logical_event_id(logical_event_offset, index)?,
        )?;
    }
}

pub fn replay_trace<D: CardDatabase>(
    initial: TrueState,
    cards: &D,
    config: RolloutConfig,
    trace: &[RolloutStep],
) -> Result<TrueState, RolloutError> {
    let mut state = initial;

    for (position, expected) in trace.iter().enumerate() {
        let index = u32::try_from(position).map_err(|_| RolloutError::StepIndexOverflow)?;
        if expected.index != index {
            return Err(RolloutError::ReplayStepIndexMismatch {
                position: index,
                declared: expected.index,
            });
        }

        if let Some(stop) = prepare_for_policy(&mut state, cards)? {
            return Err(RolloutError::ReplayStoppedEarly { index, stop });
        }

        let bridge = CandidateBridge::build(&state, cards)?;
        let information = bridge.information();
        if information.turn != expected.turn
            || information.phase != expected.phase
            || information.window != expected.window
        {
            return Err(RolloutError::ReplayDecisionPointMismatch {
                index,
                expected_turn: expected.turn,
                expected_phase: expected.phase,
                expected_window: expected.window,
                actual_turn: information.turn,
                actual_phase: information.phase,
                actual_window: information.window,
            });
        }

        let mut matching = bridge
            .candidates()
            .iter()
            .filter(|candidate| candidate.class == expected.class && candidate.key == expected.key);
        let Some(candidate) = matching.next() else {
            return Err(RolloutError::ReplayCandidateMissing(index));
        };
        if matching.next().is_some() {
            return Err(RolloutError::ReplayCandidateAmbiguous(index));
        }
        let action = bridge
            .resolved_action(candidate.token)
            .ok_or(RolloutError::MissingResolvedAction(candidate.token))?;
        execute(
            &mut state,
            cards,
            action,
            config,
            LogicalEventId(u64::from(index)),
        )?;
    }

    Ok(state)
}

fn prepare_for_policy<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
) -> Result<Option<RolloutStop>, RolloutError> {
    let information = observe(state)?;
    if let Some(family) = detect_terminal_win(&information, cards) {
        return Ok(Some(RolloutStop::Terminal(family)));
    }

    if needs_automatic_advance(state) {
        match advance_automatic(state, cards) {
            Ok(_) => {}
            Err(RuleError::HorizonReached) => return Ok(Some(RolloutStop::Horizon)),
            Err(error) => return Err(error.into()),
        }

        let information = observe(state)?;
        if let Some(family) = detect_terminal_win(&information, cards) {
            return Ok(Some(RolloutStop::Terminal(family)));
        }
    }

    Ok(None)
}

fn needs_automatic_advance(state: &TrueState) -> bool {
    state.stack.is_empty()
        && matches!(state.pending, PendingDecision::None)
        && matches!(
            (state.phase, state.window),
            (Phase::OpponentCycle, Window::None) | (Phase::Untap, Window::None)
        )
}

fn logical_event_id(offset: u64, index: u32) -> Result<LogicalEventId, RolloutError> {
    offset
        .checked_add(u64::from(index))
        .map(LogicalEventId)
        .ok_or(RolloutError::LogicalEventOverflow)
}

fn execute<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    action: urza_rules::Action,
    config: RolloutConfig,
    logical_event: LogicalEventId,
) -> Result<(), RolloutError> {
    apply_action_with_rng(
        state,
        cards,
        action,
        GameRngContext {
            root: config.root,
            world: config.world,
            logical_event,
        },
    )?;
    Ok(())
}

fn finish(
    state: TrueState,
    stop: RolloutStop,
    trace: Vec<RolloutStep>,
) -> Result<RolloutResult, RolloutError> {
    let final_information = observe(&state)?;
    Ok(RolloutResult {
        final_state: state,
        final_information,
        stop,
        trace,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use urza_cards::R4CardDatabase;
    use urza_core::{
        BattlefieldZone, CardFace, CommanderZone, CounterState, LibraryKnowledge, ObjectId,
        PendingDecision, PermanentMode, PermanentState, SourceRef, StackObject, TrueLibrary,
    };

    fn cards() -> R4CardDatabase {
        R4CardDatabase::load().expect("R4 database")
    }

    fn config(max_steps: u32) -> RolloutConfig {
        RolloutConfig {
            root: RootSeed::from_u64(0x524f_4c4c_4f55_5401),
            world: WorldId(7),
            max_steps,
        }
    }

    fn base_state(cards: &R4CardDatabase, turn: u8) -> TrueState {
        let island = cards.card_id_by_name("Island").expect("Island");
        TrueState {
            turn,
            phase: Phase::PrecombatMain,
            window: Window::Priority,
            library: TrueLibrary::new(vec![island], LibraryKnowledge::default())
                .expect("valid library"),
            ..TrueState::default()
        }
    }

    fn permanent(object: u32, card: urza_core::CardDefId) -> PermanentState {
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
    fn terminal_state_stops_before_policy_action() {
        let cards = cards();
        let urza = cards
            .card_id_by_name("Urza, Lord High Artificer")
            .expect("Urza");
        let basalt = cards.card_id_by_name("Basalt Monolith").expect("Basalt");
        let power = cards
            .card_id_by_name("Power Artifact")
            .expect("Power Artifact");
        let mut state = base_state(&cards, 2);
        state.commander.zone = CommanderZone::Battlefield;
        let mut aura = permanent(30, power);
        aura.attached_to = Some(ObjectId(20));
        state.battlefield =
            BattlefieldZone::new(vec![permanent(10, urza), permanent(20, basalt), aura]);

        let result = rollout(state, &cards, &DeterministicPolicy, config(16)).unwrap();
        assert_eq!(
            result.stop,
            RolloutStop::Terminal(WinFamily::PowerArtifactBasalt)
        );
        assert!(result.trace.is_empty());
    }

    #[test]
    fn pass_only_state_crosses_phases_and_stops_at_horizon() {
        let cards = cards();
        let state = base_state(&cards, urza_rules::HORIZON_TURN);
        let result = rollout(state, &cards, &DeterministicPolicy, config(16)).unwrap();

        assert_eq!(result.stop, RolloutStop::Horizon);
        assert_eq!(result.trace.len(), 2);
        assert!(
            result
                .trace
                .iter()
                .all(|step| step.class == PolicyActionClass::PassPriority)
        );
        assert_eq!(result.final_state.phase, Phase::OpponentCycle);
    }

    #[test]
    fn stack_resolution_rebuilds_candidates_until_horizon() {
        let cards = cards();
        let crypt = cards
            .card_id_by_name("Tormod's Crypt")
            .expect("Tormod's Crypt");
        let mut state = base_state(&cards, urza_rules::HORIZON_TURN);
        state.stack.push(StackObject::Spell {
            object_id: ObjectId(900),
            card: crypt,
            x_value: None,
        });

        let result = rollout(state, &cards, &DeterministicPolicy, config(16)).unwrap();
        assert_eq!(result.stop, RolloutStop::Horizon);
        assert!(result.trace.len() >= 3);
        assert_eq!(result.trace[0].class, PolicyActionClass::PassPriority);
        assert!(
            result
                .final_state
                .battlefield
                .permanents()
                .iter()
                .any(|permanent| permanent.card == crypt)
        );
    }

    #[test]
    fn same_seed_and_world_replay_random_search_exactly() {
        let cards = cards();
        let spellseeker = cards.card_id_by_name("Spellseeker").expect("Spellseeker");
        let knack = cards
            .card_id_by_name("Banishing Knack")
            .expect("Banishing Knack");
        let helix = cards
            .card_id_by_name("Retraction Helix")
            .expect("Retraction Helix");
        let mystical = cards
            .card_id_by_name("Mystical Tutor")
            .expect("Mystical Tutor");
        let island = cards.card_id_by_name("Island").expect("Island");
        let mut state = base_state(&cards, 2);
        state.window = Window::PostObservation;
        state.library = TrueLibrary::new(
            vec![knack, helix, mystical, island],
            LibraryKnowledge::default(),
        )
        .expect("valid hidden library");
        state.battlefield = BattlefieldZone::new(vec![permanent(77, spellseeker)]);
        state.pending = PendingDecision::TutorTarget {
            source: SourceRef {
                object_id: Some(ObjectId(77)),
                card: spellseeker,
            },
        };

        let cfg = config(1);
        let left = rollout(state.clone(), &cards, &DeterministicPolicy, cfg).unwrap();
        let right = rollout(state.clone(), &cards, &DeterministicPolicy, cfg).unwrap();
        assert_eq!(left, right);
        assert_eq!(left.stop, RolloutStop::StepLimit);
        assert_eq!(left.trace.len(), 1);
        assert_eq!(left.trace[0].class, PolicyActionClass::ContingentDecision);
        assert!(left.final_state.rng_occurrence_cursor > state.rng_occurrence_cursor);

        let replayed = replay_trace(state, &cards, cfg, &left.trace).unwrap();
        assert_eq!(replayed, left.final_state);
    }

    #[test]
    fn raw_object_id_renaming_preserves_public_multistep_trace() {
        let cards = cards();
        let cage = cards
            .card_id_by_name("Grafdigger's Cage")
            .expect("Grafdigger's Cage");
        let mut left_state = base_state(&cards, urza_rules::HORIZON_TURN);
        left_state.battlefield = BattlefieldZone::new(vec![permanent(3, cage)]);
        let mut right_state = base_state(&cards, urza_rules::HORIZON_TURN);
        right_state.battlefield = BattlefieldZone::new(vec![permanent(30_003, cage)]);

        let cfg = config(16);
        let left = rollout(left_state.clone(), &cards, &DeterministicPolicy, cfg).unwrap();
        let right = rollout(right_state.clone(), &cards, &DeterministicPolicy, cfg).unwrap();

        assert_eq!(left.stop, right.stop);
        assert_eq!(left.trace, right.trace);
        assert_eq!(left.final_information, right.final_information);

        let replayed = replay_trace(right_state, &cards, cfg, &left.trace).unwrap();
        assert_eq!(observe(&replayed).unwrap(), right.final_information);
    }

    #[test]
    fn semantic_trace_detects_replay_drift() {
        let cards = cards();
        let state = base_state(&cards, urza_rules::HORIZON_TURN);
        let result = rollout(state.clone(), &cards, &DeterministicPolicy, config(16)).unwrap();
        let mut trace = result.trace.clone();
        trace[0].key.kind = u16::MAX;

        assert!(matches!(
            replay_trace(state, &cards, config(16), &trace),
            Err(RolloutError::ReplayCandidateMissing(0))
        ));
    }
}
