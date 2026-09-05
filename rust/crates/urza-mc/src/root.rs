use thiserror::Error;
use urza_core::TrueState;
use urza_policy::{DeterministicPolicy, PolicyActionClass, PolicyPublicKey};
use urza_policy_bridge::{BridgeError, CandidateBridge};
use urza_rng::{LogicalEventId, RootSeed, WorldId};
use urza_rollout::{
    RolloutConfig, RolloutError, RolloutResult, RolloutStop, rollout_with_logical_event_offset,
};
use urza_rules::{
    CardDatabase, GameRngContext, HORIZON_TURN, RuleError, WinFamily, apply_action_with_rng,
    detect_terminal_win,
};
use urza_value::{WinByHorizonScore, WinDistribution};

use crate::{
    FamilyWinCount, MonteCarloConfig, MonteCarloError, MonteCarloResult, SampleOutcome,
    WorldOutcome, sample_hidden_world,
};

pub const ROOT_ACTION_EVAL_VERSION: &str = "r5_root_action_value_v1";

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct RootActionKey {
    pub class: PolicyActionClass,
    pub key: PolicyPublicKey,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RootActionEvaluation {
    pub action: RootActionKey,
    pub value: WinByHorizonScore,
    pub result: MonteCarloResult,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RootActionComparison {
    pub worlds: Vec<WorldId>,
    pub evaluations: Vec<RootActionEvaluation>,
    pub selected: RootActionKey,
}

#[derive(Debug, Error)]
pub enum RootActionError {
    #[error(transparent)]
    MonteCarlo(#[from] MonteCarloError),
    #[error(transparent)]
    Bridge(#[from] BridgeError),
    #[error("root-action comparison requires at least one legal public candidate")]
    NoCandidates,
    #[error("root-action comparison requires a positive total rollout step budget")]
    ZeroStepBudget,
    #[error(
        "root-action comparison is unnecessary because the public state is already terminal: {0:?}"
    )]
    AlreadyTerminal(WinFamily),
    #[error("sampled world {world:?} exposed a different public root candidate set")]
    CandidateSetDrift { world: WorldId },
    #[error("sampled world {world:?} is missing root action {action:?}")]
    MissingRootAction {
        world: WorldId,
        action: RootActionKey,
    },
    #[error("sampled world {world:?} exposed root action {action:?} more than once")]
    AmbiguousRootAction {
        world: WorldId,
        action: RootActionKey,
    },
    #[error(
        "sampled world {world:?} could not resolve root action {action:?} to an exact execution action"
    )]
    MissingResolvedRootAction {
        world: WorldId,
        action: RootActionKey,
    },
    #[error("root action failed in sampled world {world:?}: {source}")]
    RootActionApply {
        world: WorldId,
        #[source]
        source: RuleError,
    },
    #[error("continuation rollout failed in sampled world {world:?}: {source}")]
    WorldRollout {
        world: WorldId,
        #[source]
        source: RolloutError,
    },
    #[error("sampled world {world:?} stopped incompletely at {stop:?}")]
    IncompleteWorld { world: WorldId, stop: RolloutStop },
    #[error("sampled world {world:?} reached a terminal win on out-of-horizon turn {turn}")]
    TerminalOutsideHorizon { world: WorldId, turn: u8 },
    #[error("root plus continuation trace length exceeded u32")]
    TraceLengthOverflow,
    #[error("root-action aggregate counter overflow")]
    CounterOverflow,
}

pub fn compare_root_actions<D: CardDatabase>(
    template: &TrueState,
    cards: &D,
    continuation_policy: &DeterministicPolicy,
    config: MonteCarloConfig,
) -> Result<RootActionComparison, RootActionError> {
    if config.samples == 0 {
        return Err(MonteCarloError::NoSamples.into());
    }
    let mut worlds = Vec::with_capacity(config.samples as usize);
    for offset in 0..config.samples {
        let value = config
            .first_world
            .0
            .checked_add(u64::from(offset))
            .ok_or(MonteCarloError::WorldIdOverflow)?;
        worlds.push(WorldId(value));
    }
    compare_root_actions_world_ids(
        template,
        cards,
        continuation_policy,
        config.root,
        config.rollout_max_steps,
        &worlds,
    )
}

pub fn compare_root_actions_world_ids<D: CardDatabase>(
    template: &TrueState,
    cards: &D,
    continuation_policy: &DeterministicPolicy,
    root: RootSeed,
    rollout_max_steps: u32,
    world_ids: &[WorldId],
) -> Result<RootActionComparison, RootActionError> {
    if rollout_max_steps == 0 {
        return Err(RootActionError::ZeroStepBudget);
    }
    let worlds = canonical_worlds(world_ids)?;
    let template_bridge = CandidateBridge::build(template, cards)?;
    if let Some(family) = detect_terminal_win(template_bridge.information(), cards) {
        return Err(RootActionError::AlreadyTerminal(family));
    }

    let roots = public_root_actions(&template_bridge);
    if roots.is_empty() {
        return Err(RootActionError::NoCandidates);
    }

    let mut evaluations: Vec<_> = roots
        .iter()
        .cloned()
        .map(|action| RootActionEvaluation {
            action,
            value: WinByHorizonScore::default(),
            result: empty_result(),
        })
        .collect();

    for world in &worlds {
        let sampled = sample_hidden_world(template, root, *world)?;
        let sampled_bridge = CandidateBridge::build(&sampled, cards)?;
        if public_root_actions(&sampled_bridge) != roots {
            return Err(RootActionError::CandidateSetDrift { world: *world });
        }

        for evaluation in &mut evaluations {
            let outcome = evaluate_sampled_root_world(
                &sampled,
                &sampled_bridge,
                cards,
                continuation_policy,
                root,
                rollout_max_steps,
                *world,
                &evaluation.action,
            )?;
            record_outcome(&mut evaluation.result, outcome)?;
        }
    }

    for evaluation in &mut evaluations {
        evaluation.value = WinByHorizonScore::from(&evaluation.result.win_distribution);
    }

    // `evaluations` is already in ascending public semantic action order.
    // Strictly-better value replaces the incumbent; exact value ties keep
    // the first (therefore smallest) public root-action key.
    let mut selected = evaluations[0].action.clone();
    let mut best_value = evaluations[0].value;
    for evaluation in evaluations.iter().skip(1) {
        if evaluation.value > best_value {
            best_value = evaluation.value;
            selected = evaluation.action.clone();
        }
    }

    Ok(RootActionComparison {
        worlds,
        evaluations,
        selected,
    })
}

pub(crate) fn canonical_worlds(world_ids: &[WorldId]) -> Result<Vec<WorldId>, RootActionError> {
    if world_ids.is_empty() {
        return Err(MonteCarloError::NoSamples.into());
    }
    let mut worlds = world_ids.to_vec();
    worlds.sort_unstable_by_key(|world| world.0);
    for pair in worlds.windows(2) {
        if pair[0] == pair[1] {
            return Err(MonteCarloError::DuplicateWorld(pair[0]).into());
        }
    }
    Ok(worlds)
}

pub(crate) fn public_root_actions(bridge: &CandidateBridge) -> Vec<RootActionKey> {
    let mut roots: Vec<_> = bridge
        .candidates()
        .iter()
        .map(|candidate| RootActionKey {
            class: candidate.class,
            key: candidate.key.clone(),
        })
        .collect();
    roots.sort_unstable();
    roots.dedup();
    roots
}

fn resolve_root_action(
    bridge: &CandidateBridge,
    root: &RootActionKey,
    world: WorldId,
) -> Result<urza_rules::Action, RootActionError> {
    let mut matches = bridge
        .candidates()
        .iter()
        .filter(|candidate| candidate.class == root.class && candidate.key == root.key);
    let Some(candidate) = matches.next() else {
        return Err(RootActionError::MissingRootAction {
            world,
            action: root.clone(),
        });
    };
    if matches.next().is_some() {
        return Err(RootActionError::AmbiguousRootAction {
            world,
            action: root.clone(),
        });
    }
    bridge.resolved_action(candidate.token).ok_or_else(|| {
        RootActionError::MissingResolvedRootAction {
            world,
            action: root.clone(),
        }
    })
}

#[allow(clippy::too_many_arguments)]
pub(crate) fn evaluate_sampled_root_world<D: CardDatabase>(
    sampled: &TrueState,
    sampled_bridge: &CandidateBridge,
    cards: &D,
    continuation_policy: &DeterministicPolicy,
    root: RootSeed,
    rollout_max_steps: u32,
    world: WorldId,
    root_action: &RootActionKey,
) -> Result<WorldOutcome, RootActionError> {
    let action = resolve_root_action(sampled_bridge, root_action, world)?;
    let mut branch = sampled.clone();
    apply_action_with_rng(
        &mut branch,
        cards,
        action,
        GameRngContext {
            root,
            world,
            logical_event: LogicalEventId(0),
        },
    )
    .map_err(|source| RootActionError::RootActionApply { world, source })?;

    let continuation = rollout_with_logical_event_offset(
        branch,
        cards,
        continuation_policy,
        RolloutConfig {
            root,
            world,
            max_steps: rollout_max_steps - 1,
        },
        1,
    )
    .map_err(|source| RootActionError::WorldRollout { world, source })?;
    world_outcome(world, continuation)
}

pub(crate) fn empty_result() -> MonteCarloResult {
    MonteCarloResult {
        outcomes: Vec::new(),
        win_distribution: WinDistribution::default(),
        family_wins: WinFamily::ALL
            .into_iter()
            .map(|family| FamilyWinCount { family, wins: 0 })
            .collect(),
    }
}

pub(crate) fn record_outcome(
    aggregate: &mut MonteCarloResult,
    outcome: WorldOutcome,
) -> Result<(), RootActionError> {
    match outcome.outcome {
        SampleOutcome::Win { family, turn } => {
            if !(1..=HORIZON_TURN).contains(&turn) {
                return Err(RootActionError::TerminalOutsideHorizon {
                    world: outcome.world,
                    turn,
                });
            }
            let bucket = usize::from(turn - 1);
            aggregate.win_distribution.t1_through_t6[bucket] =
                aggregate.win_distribution.t1_through_t6[bucket]
                    .checked_add(1)
                    .ok_or(RootActionError::CounterOverflow)?;
            let entry = aggregate
                .family_wins
                .iter_mut()
                .find(|entry| entry.family == family)
                .expect("WinFamily::ALL contains every terminal family");
            entry.wins = entry
                .wins
                .checked_add(1)
                .ok_or(RootActionError::CounterOverflow)?;
        }
        SampleOutcome::LossByHorizon => {
            aggregate.win_distribution.losses = aggregate
                .win_distribution
                .losses
                .checked_add(1)
                .ok_or(RootActionError::CounterOverflow)?;
        }
    }
    aggregate.outcomes.push(outcome);
    Ok(())
}

fn world_outcome(world: WorldId, result: RolloutResult) -> Result<WorldOutcome, RootActionError> {
    let continuation_steps =
        u32::try_from(result.trace.len()).map_err(|_| RootActionError::TraceLengthOverflow)?;
    let rollout_steps = continuation_steps
        .checked_add(1)
        .ok_or(RootActionError::TraceLengthOverflow)?;

    let outcome = match result.stop {
        RolloutStop::Terminal(family) => {
            let turn = result.final_information.turn;
            if !(1..=HORIZON_TURN).contains(&turn) {
                return Err(RootActionError::TerminalOutsideHorizon { world, turn });
            }
            SampleOutcome::Win { family, turn }
        }
        RolloutStop::Horizon => SampleOutcome::LossByHorizon,
        stop @ (RolloutStop::StepLimit | RolloutStop::NoCandidate) => {
            return Err(RootActionError::IncompleteWorld { world, stop });
        }
    };

    Ok(WorldOutcome {
        world,
        outcome,
        rollout_steps,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use urza_cards::R4CardDatabase;
    use urza_core::{
        BattlefieldZone, CardFace, CardZone, CommanderZone, CounterState, ObjectId, PermanentMode,
        PermanentState, Phase, TrueLibrary, Window,
    };

    fn cards() -> R4CardDatabase {
        R4CardDatabase::load().expect("R4 database")
    }

    fn state_with_land_choice(
        cards: &R4CardDatabase,
        library: Vec<urza_core::CardDefId>,
    ) -> TrueState {
        let island = cards.card_id_by_name("Island").expect("Island");
        TrueState {
            turn: HORIZON_TURN,
            phase: Phase::PrecombatMain,
            window: Window::Priority,
            library: TrueLibrary::unknown(library),
            hand: CardZone::new(vec![island]),
            ..TrueState::default()
        }
    }

    fn config() -> MonteCarloConfig {
        MonteCarloConfig {
            root: RootSeed::from_u64(0x524f_4f54_5641_4c01),
            first_world: WorldId(20),
            samples: 3,
            rollout_max_steps: 12,
        }
    }

    #[test]
    fn every_root_action_uses_the_same_canonical_world_set() {
        let cards = cards();
        let island = cards.card_id_by_name("Island").expect("Island");
        let crypt = cards.card_id_by_name("Tormod's Crypt").expect("Crypt");
        let state = state_with_land_choice(&cards, vec![island, crypt]);
        let comparison =
            compare_root_actions(&state, &cards, &DeterministicPolicy, config()).unwrap();

        assert!(comparison.evaluations.len() >= 2);
        assert_eq!(
            comparison.worlds,
            vec![WorldId(20), WorldId(21), WorldId(22)]
        );
        for evaluation in &comparison.evaluations {
            assert_eq!(evaluation.result.samples(), comparison.worlds.len());
            assert_eq!(
                evaluation
                    .result
                    .outcomes
                    .iter()
                    .map(|outcome| outcome.world)
                    .collect::<Vec<_>>(),
                comparison.worlds
            );
        }
    }

    #[test]
    fn equal_values_use_smallest_public_semantic_root_key() {
        let cards = cards();
        let island = cards.card_id_by_name("Island").expect("Island");
        let state = state_with_land_choice(&cards, vec![island]);
        let comparison =
            compare_root_actions(&state, &cards, &DeterministicPolicy, config()).unwrap();
        let minimum = comparison
            .evaluations
            .iter()
            .map(|evaluation| evaluation.action.clone())
            .min()
            .unwrap();
        assert_eq!(comparison.selected, minimum);
    }

    #[test]
    fn root_comparison_is_world_enumeration_order_independent() {
        let cards = cards();
        let island = cards.card_id_by_name("Island").expect("Island");
        let crypt = cards.card_id_by_name("Tormod's Crypt").expect("Crypt");
        let state = state_with_land_choice(&cards, vec![island, crypt]);
        let root = RootSeed::from_u64(77);
        let forward = compare_root_actions_world_ids(
            &state,
            &cards,
            &DeterministicPolicy,
            root,
            12,
            &[WorldId(8), WorldId(2), WorldId(5)],
        )
        .unwrap();
        let reverse = compare_root_actions_world_ids(
            &state,
            &cards,
            &DeterministicPolicy,
            root,
            12,
            &[WorldId(5), WorldId(2), WorldId(8)],
        )
        .unwrap();
        assert_eq!(forward, reverse);
    }

    #[test]
    fn root_comparison_ignores_template_hidden_order() {
        let cards = cards();
        let island = cards.card_id_by_name("Island").expect("Island");
        let crypt = cards.card_id_by_name("Tormod's Crypt").expect("Crypt");
        let basalt = cards.card_id_by_name("Basalt Monolith").expect("Basalt");
        let left = state_with_land_choice(&cards, vec![island, crypt, basalt]);
        let right = state_with_land_choice(&cards, vec![basalt, island, crypt]);
        assert_eq!(
            urza_info::observe(&left).unwrap(),
            urza_info::observe(&right).unwrap()
        );

        let left_result =
            compare_root_actions(&left, &cards, &DeterministicPolicy, config()).unwrap();
        let right_result =
            compare_root_actions(&right, &cards, &DeterministicPolicy, config()).unwrap();
        assert_eq!(left_result, right_result);
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
    fn already_terminal_state_is_rejected_before_root_branching() {
        let cards = cards();
        let urza = cards
            .card_id_by_name("Urza, Lord High Artificer")
            .expect("Urza");
        let basalt = cards.card_id_by_name("Basalt Monolith").expect("Basalt");
        let power = cards
            .card_id_by_name("Power Artifact")
            .expect("Power Artifact");
        let island = cards.card_id_by_name("Island").expect("Island");
        let mut state = state_with_land_choice(&cards, vec![island]);
        state.commander.zone = CommanderZone::Battlefield;
        let mut aura = permanent(30, power);
        aura.attached_to = Some(ObjectId(20));
        state.battlefield =
            BattlefieldZone::new(vec![permanent(10, urza), permanent(20, basalt), aura]);

        let error =
            compare_root_actions(&state, &cards, &DeterministicPolicy, config()).unwrap_err();
        assert!(matches!(
            error,
            RootActionError::AlreadyTerminal(WinFamily::PowerArtifactBasalt)
        ));
    }

    #[test]
    fn zero_total_step_budget_is_rejected() {
        let cards = cards();
        let island = cards.card_id_by_name("Island").expect("Island");
        let state = state_with_land_choice(&cards, vec![island]);
        let error = compare_root_actions_world_ids(
            &state,
            &cards,
            &DeterministicPolicy,
            RootSeed::from_u64(1),
            0,
            &[WorldId(0)],
        )
        .unwrap_err();
        assert!(matches!(error, RootActionError::ZeroStepBudget));
    }
}
