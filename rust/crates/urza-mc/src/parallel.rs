use std::thread;

use thiserror::Error;
use urza_core::{MODEL_VERSION, TrueState};
use urza_info::INFORMATION_SCHEMA_VERSION;
use urza_policy::{DeterministicPolicy, POLICY_VERSION};
use urza_policy_bridge::{CANDIDATE_BRIDGE_VERSION, CandidateBridge};
use urza_rng::{RNG_SCHEME_VERSION, RootSeed, WorldId};
use urza_rollout::ROLLOUT_VERSION;
use urza_rules::{CardDatabase, HORIZON_TURN, RULES_VERSION, detect_terminal_win};
use urza_value::{
    EvaluationNamespace, Objective, VALUE_KEY_SCHEMA_VERSION, ValueKey, WinByHorizonScore,
};

use crate::adaptive::{
    AdaptiveRootActionComparison, AdaptiveRootConfig, AdaptiveRootError, AdaptiveSearchStats,
    AdaptiveStopReason, ROOT_WORLD_CACHE_VERSION, RootOutcomeCache, RootWorldCacheKey,
};
use crate::root::{
    ROOT_ACTION_EVAL_VERSION, RootActionComparison, RootActionError, RootActionEvaluation,
    RootActionKey, canonical_worlds, empty_result, evaluate_sampled_root_world,
    public_root_actions, record_outcome,
};
use crate::{
    MONTE_CARLO_VERSION, MonteCarloConfig, MonteCarloError, WorldOutcome, sample_hidden_world,
};

pub const PARALLEL_ROOT_EVAL_VERSION: &str = "r5_parallel_root_world_v1";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ParallelRootConfig {
    pub workers: usize,
}

impl Default for ParallelRootConfig {
    fn default() -> Self {
        Self {
            workers: thread::available_parallelism().map_or(1, usize::from),
        }
    }
}

#[derive(Debug, Error)]
pub enum ParallelRootError {
    #[error(transparent)]
    RootAction(#[from] RootActionError),
    #[error(transparent)]
    Adaptive(#[from] AdaptiveRootError),
    #[error("parallel root evaluation requires at least one worker")]
    ZeroWorkers,
    #[error("parallel root evaluation worker panicked")]
    WorkerPanic,
}

struct PreparedWorld {
    world: WorldId,
    sampled: TrueState,
    bridge: CandidateBridge,
}

pub fn compare_root_actions_parallel<D: CardDatabase + Sync>(
    template: &TrueState,
    cards: &D,
    continuation_policy: &DeterministicPolicy,
    config: MonteCarloConfig,
    parallel: ParallelRootConfig,
) -> Result<RootActionComparison, ParallelRootError> {
    if config.samples == 0 {
        return Err(RootActionError::MonteCarlo(MonteCarloError::NoSamples).into());
    }
    let mut worlds = Vec::with_capacity(config.samples as usize);
    for offset in 0..config.samples {
        let value = config.first_world.0.checked_add(u64::from(offset)).ok_or(
            RootActionError::MonteCarlo(MonteCarloError::WorldIdOverflow),
        )?;
        worlds.push(WorldId(value));
    }
    compare_root_actions_world_ids_parallel(
        template,
        cards,
        continuation_policy,
        config.root,
        config.rollout_max_steps,
        &worlds,
        parallel,
    )
}

#[allow(clippy::too_many_arguments)]
pub fn compare_root_actions_world_ids_parallel<D: CardDatabase + Sync>(
    template: &TrueState,
    cards: &D,
    continuation_policy: &DeterministicPolicy,
    root: RootSeed,
    rollout_max_steps: u32,
    world_ids: &[WorldId],
    parallel: ParallelRootConfig,
) -> Result<RootActionComparison, ParallelRootError> {
    validate_workers(parallel)?;
    if rollout_max_steps == 0 {
        return Err(RootActionError::ZeroStepBudget.into());
    }

    let worlds = canonical_worlds(world_ids)?;
    let template_bridge =
        CandidateBridge::build(template, cards).map_err(RootActionError::Bridge)?;
    if let Some(family) = detect_terminal_win(template_bridge.information(), cards) {
        return Err(RootActionError::AlreadyTerminal(family).into());
    }
    let roots = public_root_actions(&template_bridge);
    if roots.is_empty() {
        return Err(RootActionError::NoCandidates.into());
    }

    let prepared = prepare_worlds(template, cards, root, &worlds, &roots)?;
    let jobs = all_jobs(prepared.len(), roots.len());
    let outcomes = evaluate_jobs_parallel(
        &prepared,
        &roots,
        &jobs,
        cards,
        continuation_policy,
        root,
        rollout_max_steps,
        parallel.workers,
    )?;

    let mut matrix = vec![vec![None; roots.len()]; worlds.len()];
    for (world_index, root_index, outcome) in outcomes {
        matrix[world_index][root_index] = Some(outcome);
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
    for row in matrix {
        for (evaluation, outcome) in evaluations.iter_mut().zip(row) {
            record_outcome(
                &mut evaluation.result,
                outcome.expect("every parallel root-world job completed"),
            )?;
        }
    }
    update_values(&mut evaluations);
    let selected = ranked_indices(&evaluations)[0];

    Ok(RootActionComparison {
        worlds,
        selected: evaluations[selected].action.clone(),
        evaluations,
    })
}

pub fn compare_root_actions_adaptive_parallel<D: CardDatabase + Sync, C: RootOutcomeCache>(
    template: &TrueState,
    cards: &D,
    continuation_policy: &DeterministicPolicy,
    config: &AdaptiveRootConfig,
    parallel: ParallelRootConfig,
    cache: &mut C,
) -> Result<AdaptiveRootActionComparison, ParallelRootError> {
    validate_workers(parallel)?;
    if config.min_samples == 0 {
        return Err(AdaptiveRootError::ZeroMinimumSamples.into());
    }
    if config.max_samples < config.min_samples {
        return Err(AdaptiveRootError::InvalidMaximumSamples.into());
    }
    if config.batch_size == 0 {
        return Err(AdaptiveRootError::ZeroBatchSize.into());
    }

    let mut worlds = Vec::with_capacity(config.max_samples as usize);
    for offset in 0..config.max_samples {
        let value = config.first_world.0.checked_add(u64::from(offset)).ok_or(
            RootActionError::MonteCarlo(MonteCarloError::WorldIdOverflow),
        )?;
        worlds.push(WorldId(value));
    }

    compare_root_actions_adaptive_world_ids_parallel(
        template,
        cards,
        continuation_policy,
        config.root,
        config.rollout_max_steps,
        config.min_samples,
        config.batch_size,
        &config.evaluation_namespace,
        &worlds,
        parallel,
        cache,
    )
}

#[allow(clippy::too_many_arguments)]
pub fn compare_root_actions_adaptive_world_ids_parallel<
    D: CardDatabase + Sync,
    C: RootOutcomeCache,
>(
    template: &TrueState,
    cards: &D,
    continuation_policy: &DeterministicPolicy,
    root: RootSeed,
    rollout_max_steps: u32,
    min_samples: u32,
    batch_size: u32,
    evaluation_namespace: &EvaluationNamespace,
    world_ids: &[WorldId],
    parallel: ParallelRootConfig,
    cache: &mut C,
) -> Result<AdaptiveRootActionComparison, ParallelRootError> {
    validate_workers(parallel)?;
    if min_samples == 0 {
        return Err(AdaptiveRootError::ZeroMinimumSamples.into());
    }
    if batch_size == 0 {
        return Err(AdaptiveRootError::ZeroBatchSize.into());
    }
    if rollout_max_steps == 0 {
        return Err(RootActionError::ZeroStepBudget.into());
    }
    validate_namespace(evaluation_namespace, rollout_max_steps)?;

    let worlds = canonical_worlds(world_ids)?;
    let max_samples = u32::try_from(worlds.len())
        .map_err(|_| ParallelRootError::Adaptive(AdaptiveRootError::InvalidMaximumSamples))?;
    if min_samples > max_samples {
        return Err(AdaptiveRootError::InvalidMaximumSamples.into());
    }

    let template_bridge =
        CandidateBridge::build(template, cards).map_err(RootActionError::Bridge)?;
    if let Some(family) = detect_terminal_win(template_bridge.information(), cards) {
        return Err(RootActionError::AlreadyTerminal(family).into());
    }
    let roots = public_root_actions(&template_bridge);
    if roots.is_empty() {
        return Err(RootActionError::NoCandidates.into());
    }
    let state_key = ValueKey::try_from_information(template_bridge.information())
        .map_err(AdaptiveRootError::ValueKey)?;

    let mut evaluations: Vec<_> = roots
        .iter()
        .cloned()
        .map(|action| RootActionEvaluation {
            action,
            value: WinByHorizonScore::default(),
            result: empty_result(),
        })
        .collect();
    let mut used_worlds = Vec::new();
    let mut stats = AdaptiveSearchStats {
        candidate_roots: u32::try_from(roots.len()).unwrap_or(u32::MAX),
        ..AdaptiveSearchStats::default()
    };
    let chunk = usize::try_from(batch_size).expect("u32 fits usize");
    let mut stop_reason = AdaptiveStopReason::MaxSamples;
    let mut certified_ranking = Vec::new();

    'batches: for batch in worlds.chunks(chunk) {
        stats.batches = stats.batches.saturating_add(1);
        let mut batch_outcomes = vec![vec![None; roots.len()]; batch.len()];
        let mut batch_keys = Vec::with_capacity(batch.len());
        let mut missing_by_world = vec![Vec::new(); batch.len()];

        for (world_index, world) in batch.iter().enumerate() {
            stats.root_world_requests = stats
                .root_world_requests
                .saturating_add(u64::try_from(roots.len()).unwrap_or(u64::MAX));
            let keys: Vec<_> = roots
                .iter()
                .cloned()
                .map(|action| RootWorldCacheKey {
                    cache_version: ROOT_WORLD_CACHE_VERSION,
                    state: state_key.clone(),
                    evaluation: evaluation_namespace.clone(),
                    root_seed: root,
                    action,
                    world: *world,
                })
                .collect();
            for (root_index, key) in keys.iter().enumerate() {
                if let Some(outcome) = cache.get(key) {
                    if outcome.world != *world {
                        return Err(AdaptiveRootError::CacheWorldMismatch {
                            expected: *world,
                            actual: outcome.world,
                        }
                        .into());
                    }
                    stats.cache_hits = stats.cache_hits.saturating_add(1);
                    stats.rollout_steps_avoided_by_cache = stats
                        .rollout_steps_avoided_by_cache
                        .saturating_add(u64::from(outcome.rollout_steps));
                    batch_outcomes[world_index][root_index] = Some(outcome);
                } else {
                    stats.cache_misses = stats.cache_misses.saturating_add(1);
                    missing_by_world[world_index].push(root_index);
                }
            }
            batch_keys.push(keys);
        }

        let mut prepared = Vec::new();
        let mut prepared_batch_indices = Vec::new();
        for (world_index, missing) in missing_by_world.iter().enumerate() {
            if missing.is_empty() {
                continue;
            }
            let world = batch[world_index];
            let sampled =
                sample_hidden_world(template, root, world).map_err(RootActionError::MonteCarlo)?;
            let bridge =
                CandidateBridge::build(&sampled, cards).map_err(RootActionError::Bridge)?;
            if public_root_actions(&bridge) != roots {
                return Err(RootActionError::CandidateSetDrift { world }.into());
            }
            stats.sampled_worlds = stats.sampled_worlds.saturating_add(1);
            prepared_batch_indices.push(world_index);
            prepared.push(PreparedWorld {
                world,
                sampled,
                bridge,
            });
        }

        let mut jobs = Vec::new();
        for (prepared_index, batch_index) in prepared_batch_indices.iter().copied().enumerate() {
            for root_index in &missing_by_world[batch_index] {
                jobs.push((prepared_index, *root_index));
            }
        }
        let computed = evaluate_jobs_parallel(
            &prepared,
            &roots,
            &jobs,
            cards,
            continuation_policy,
            root,
            rollout_max_steps,
            parallel.workers,
        )?;
        for (prepared_index, root_index, outcome) in computed {
            let batch_index = prepared_batch_indices[prepared_index];
            stats.root_world_rollouts = stats.root_world_rollouts.saturating_add(1);
            stats.rollout_steps_executed = stats
                .rollout_steps_executed
                .saturating_add(u64::from(outcome.rollout_steps));
            cache.insert(batch_keys[batch_index][root_index].clone(), outcome);
            batch_outcomes[batch_index][root_index] = Some(outcome);
        }

        for (world_index, world) in batch.iter().enumerate() {
            for (evaluation, outcome) in evaluations
                .iter_mut()
                .zip(batch_outcomes[world_index].iter().copied())
            {
                record_outcome(
                    &mut evaluation.result,
                    outcome.expect("every adaptive parallel root-world outcome is present"),
                )?;
            }
            used_worlds.push(*world);
            stats.worlds_consumed = stats.worlds_consumed.saturating_add(1);
        }

        update_values(&mut evaluations);
        let used = u32::try_from(used_worlds.len()).unwrap_or(u32::MAX);
        let remaining = max_samples.saturating_sub(used);
        if used >= min_samples && remaining > 0 {
            let ranking = ranked_indices(&evaluations);
            if exact_full_budget_ranking_certified(&evaluations, &ranking, remaining)? {
                certified_ranking = ranking
                    .into_iter()
                    .map(|index| evaluations[index].action.clone())
                    .collect();
                stop_reason = AdaptiveStopReason::ExactFullBudgetRankingCertified;
                break 'batches;
            }
        }
    }

    update_values(&mut evaluations);
    if certified_ranking.is_empty() {
        certified_ranking = ranked_indices(&evaluations)
            .into_iter()
            .map(|index| evaluations[index].action.clone())
            .collect();
    }
    let selected = certified_ranking
        .first()
        .expect("at least one root action")
        .clone();

    Ok(AdaptiveRootActionComparison {
        comparison: RootActionComparison {
            worlds: used_worlds,
            evaluations,
            selected,
        },
        certified_full_budget_ranking: certified_ranking,
        stop_reason,
        max_samples,
        stats,
    })
}

fn validate_workers(parallel: ParallelRootConfig) -> Result<(), ParallelRootError> {
    if parallel.workers == 0 {
        Err(ParallelRootError::ZeroWorkers)
    } else {
        Ok(())
    }
}

fn prepare_worlds<D: CardDatabase>(
    template: &TrueState,
    cards: &D,
    root: RootSeed,
    worlds: &[WorldId],
    roots: &[RootActionKey],
) -> Result<Vec<PreparedWorld>, RootActionError> {
    let mut prepared = Vec::with_capacity(worlds.len());
    for world in worlds {
        let sampled = sample_hidden_world(template, root, *world)?;
        let bridge = CandidateBridge::build(&sampled, cards)?;
        if public_root_actions(&bridge) != roots {
            return Err(RootActionError::CandidateSetDrift { world: *world });
        }
        prepared.push(PreparedWorld {
            world: *world,
            sampled,
            bridge,
        });
    }
    Ok(prepared)
}

fn all_jobs(worlds: usize, roots: usize) -> Vec<(usize, usize)> {
    let mut jobs = Vec::with_capacity(worlds.saturating_mul(roots));
    for world_index in 0..worlds {
        for root_index in 0..roots {
            jobs.push((world_index, root_index));
        }
    }
    jobs
}

#[allow(clippy::too_many_arguments)]
fn evaluate_jobs_parallel<D: CardDatabase + Sync>(
    prepared: &[PreparedWorld],
    roots: &[RootActionKey],
    jobs: &[(usize, usize)],
    cards: &D,
    continuation_policy: &DeterministicPolicy,
    root: RootSeed,
    rollout_max_steps: u32,
    workers: usize,
) -> Result<Vec<(usize, usize, WorldOutcome)>, ParallelRootError> {
    if jobs.is_empty() {
        return Ok(Vec::new());
    }
    let active_workers = workers.min(jobs.len());
    let chunk_size = jobs.len().div_ceil(active_workers);

    thread::scope(|scope| {
        let mut handles = Vec::new();
        for chunk in jobs.chunks(chunk_size) {
            handles.push(scope.spawn(move || {
                let mut completed = Vec::with_capacity(chunk.len());
                for &(world_index, root_index) in chunk {
                    let world = &prepared[world_index];
                    let outcome = evaluate_sampled_root_world(
                        &world.sampled,
                        &world.bridge,
                        cards,
                        continuation_policy,
                        root,
                        rollout_max_steps,
                        world.world,
                        &roots[root_index],
                    )?;
                    completed.push((world_index, root_index, outcome));
                }
                Ok::<_, RootActionError>(completed)
            }));
        }

        let mut completed = Vec::with_capacity(jobs.len());
        for handle in handles {
            let mut worker = handle
                .join()
                .map_err(|_| ParallelRootError::WorkerPanic)??;
            completed.append(&mut worker);
        }
        completed.sort_unstable_by_key(|(world_index, root_index, _)| (*world_index, *root_index));
        Ok(completed)
    })
}

fn update_values(evaluations: &mut [RootActionEvaluation]) {
    for evaluation in evaluations {
        evaluation.value = WinByHorizonScore::from(&evaluation.result.win_distribution);
    }
}

fn ranked_indices(evaluations: &[RootActionEvaluation]) -> Vec<usize> {
    let mut ranking: Vec<_> = (0..evaluations.len()).collect();
    ranking.sort_unstable_by(|left, right| {
        evaluations[*right]
            .value
            .cmp(&evaluations[*left].value)
            .then_with(|| evaluations[*left].action.cmp(&evaluations[*right].action))
    });
    ranking
}

fn exact_full_budget_ranking_certified(
    evaluations: &[RootActionEvaluation],
    ranking: &[usize],
    remaining: u32,
) -> Result<bool, ParallelRootError> {
    for pair in ranking.windows(2) {
        let higher = &evaluations[pair[0]];
        let lower = &evaluations[pair[1]];
        let optimistic_lower = optimistic_score(lower.value, remaining)?;
        if optimistic_lower > higher.value {
            return Ok(false);
        }
        if optimistic_lower == higher.value && lower.action < higher.action {
            return Ok(false);
        }
    }
    Ok(true)
}

fn optimistic_score(
    mut score: WinByHorizonScore,
    remaining: u32,
) -> Result<WinByHorizonScore, ParallelRootError> {
    score.total_wins = score
        .total_wins
        .checked_add(u64::from(remaining))
        .ok_or(AdaptiveRootError::ScoreOverflow)?;
    score.exact_turn_wins[0] = score.exact_turn_wins[0]
        .checked_add(remaining)
        .ok_or(AdaptiveRootError::ScoreOverflow)?;
    Ok(score)
}

fn validate_namespace(
    namespace: &EvaluationNamespace,
    rollout_budget: u32,
) -> Result<(), ParallelRootError> {
    macro_rules! require {
        ($condition:expr, $field:literal) => {
            if !$condition {
                return Err(AdaptiveRootError::NamespaceMismatch($field).into());
            }
        };
    }
    require!(namespace.rules_version == RULES_VERSION, "rules_version");
    require!(!namespace.catalog_digest.is_empty(), "catalog_digest");
    require!(namespace.model_version == MODEL_VERSION, "model_version");
    require!(namespace.policy_version == POLICY_VERSION, "policy_version");
    require!(
        namespace.value_key_schema_version == VALUE_KEY_SCHEMA_VERSION,
        "value_key_schema_version"
    );
    require!(namespace.objective == Objective::WinByHorizon, "objective");
    require!(namespace.horizon == HORIZON_TURN, "horizon");
    require!(
        !namespace.environment_version.is_empty(),
        "environment_version"
    );
    require!(
        namespace.rng_scheme_version == RNG_SCHEME_VERSION,
        "rng_scheme_version"
    );
    require!(
        namespace.sample_namespace == format!("{INFORMATION_SCHEMA_VERSION}|{MONTE_CARLO_VERSION}"),
        "sample_namespace"
    );
    require!(namespace.rollout_budget == rollout_budget, "rollout_budget");
    require!(
        namespace.continuation_identity
            == format!("{CANDIDATE_BRIDGE_VERSION}|{ROLLOUT_VERSION}|{ROOT_ACTION_EVAL_VERSION}"),
        "continuation_identity"
    );
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::adaptive::{
        InMemoryRootOutcomeCache, NoopRootOutcomeCache, compare_root_actions_adaptive,
        current_r5_evaluation_namespace,
    };
    use crate::root::{compare_root_actions_world_ids, public_root_actions};
    use urza_cards::R4CardDatabase;
    use urza_core::{CardZone, Phase, TrueLibrary, Window};

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

    fn adaptive_config() -> AdaptiveRootConfig {
        AdaptiveRootConfig {
            root: RootSeed::from_u64(0x5041_5241_4c4c_454c),
            first_world: WorldId(70),
            min_samples: 3,
            max_samples: 3,
            batch_size: 3,
            rollout_max_steps: 12,
            evaluation_namespace: current_r5_evaluation_namespace(
                "parallel-test-catalog",
                "parallel-test-env",
                12,
            ),
        }
    }

    #[test]
    fn parallel_fixed_matches_serial_for_multiple_worker_counts() {
        let cards = cards();
        let island = cards.card_id_by_name("Island").expect("Island");
        let crypt = cards.card_id_by_name("Tormod's Crypt").expect("Crypt");
        let state = state_with_land_choice(&cards, vec![island, crypt]);
        let worlds = [WorldId(3), WorldId(8), WorldId(13)];
        let root = RootSeed::from_u64(101);
        let serial =
            compare_root_actions_world_ids(&state, &cards, &DeterministicPolicy, root, 12, &worlds)
                .unwrap();

        for workers in [1, 2, 4, 32] {
            let parallel = compare_root_actions_world_ids_parallel(
                &state,
                &cards,
                &DeterministicPolicy,
                root,
                12,
                &worlds,
                ParallelRootConfig { workers },
            )
            .unwrap();
            assert_eq!(parallel, serial, "workers={workers}");
        }
    }

    #[test]
    fn parallel_fixed_is_world_order_independent() {
        let cards = cards();
        let island = cards.card_id_by_name("Island").expect("Island");
        let state = state_with_land_choice(&cards, vec![island]);
        let root = RootSeed::from_u64(102);
        let left = compare_root_actions_world_ids_parallel(
            &state,
            &cards,
            &DeterministicPolicy,
            root,
            12,
            &[WorldId(9), WorldId(2), WorldId(5)],
            ParallelRootConfig { workers: 3 },
        )
        .unwrap();
        let right = compare_root_actions_world_ids_parallel(
            &state,
            &cards,
            &DeterministicPolicy,
            root,
            12,
            &[WorldId(5), WorldId(9), WorldId(2)],
            ParallelRootConfig { workers: 2 },
        )
        .unwrap();
        assert_eq!(left, right);
    }

    #[test]
    fn parallel_fixed_ignores_template_hidden_order() {
        let cards = cards();
        let island = cards.card_id_by_name("Island").expect("Island");
        let crypt = cards.card_id_by_name("Tormod's Crypt").expect("Crypt");
        let basalt = cards.card_id_by_name("Basalt Monolith").expect("Basalt");
        let left = state_with_land_choice(&cards, vec![island, crypt, basalt]);
        let right = state_with_land_choice(&cards, vec![basalt, island, crypt]);
        let config = MonteCarloConfig {
            root: RootSeed::from_u64(103),
            first_world: WorldId(11),
            samples: 3,
            rollout_max_steps: 12,
        };
        let left_result = compare_root_actions_parallel(
            &left,
            &cards,
            &DeterministicPolicy,
            config,
            ParallelRootConfig { workers: 4 },
        )
        .unwrap();
        let right_result = compare_root_actions_parallel(
            &right,
            &cards,
            &DeterministicPolicy,
            config,
            ParallelRootConfig { workers: 2 },
        )
        .unwrap();
        assert_eq!(left_result, right_result);
    }

    #[test]
    fn parallel_adaptive_full_budget_matches_serial_exactly() {
        let cards = cards();
        let island = cards.card_id_by_name("Island").expect("Island");
        let crypt = cards.card_id_by_name("Tormod's Crypt").expect("Crypt");
        let state = state_with_land_choice(&cards, vec![island, crypt]);
        let config = adaptive_config();
        let mut serial_cache = NoopRootOutcomeCache;
        let serial = compare_root_actions_adaptive(
            &state,
            &cards,
            &DeterministicPolicy,
            &config,
            &mut serial_cache,
        )
        .unwrap();
        let mut parallel_cache = NoopRootOutcomeCache;
        let parallel = compare_root_actions_adaptive_parallel(
            &state,
            &cards,
            &DeterministicPolicy,
            &config,
            ParallelRootConfig { workers: 4 },
            &mut parallel_cache,
        )
        .unwrap();
        assert_eq!(parallel, serial);
    }

    #[test]
    fn serial_cache_entries_are_reused_by_parallel_evaluation() {
        let cards = cards();
        let island = cards.card_id_by_name("Island").expect("Island");
        let crypt = cards.card_id_by_name("Tormod's Crypt").expect("Crypt");
        let state = state_with_land_choice(&cards, vec![island, crypt]);
        let config = adaptive_config();
        let bridge = CandidateBridge::build(&state, &cards).unwrap();
        assert!(!public_root_actions(&bridge).is_empty());
        let mut cache = InMemoryRootOutcomeCache::default();
        let serial = compare_root_actions_adaptive(
            &state,
            &cards,
            &DeterministicPolicy,
            &config,
            &mut cache,
        )
        .unwrap();
        let parallel = compare_root_actions_adaptive_parallel(
            &state,
            &cards,
            &DeterministicPolicy,
            &config,
            ParallelRootConfig { workers: 4 },
            &mut cache,
        )
        .unwrap();
        assert_eq!(parallel.comparison, serial.comparison);
        assert_eq!(parallel.stats.cache_misses, 0);
        assert_eq!(parallel.stats.root_world_rollouts, 0);
        assert_eq!(parallel.stats.sampled_worlds, 0);
        assert_eq!(
            parallel.stats.cache_hits,
            parallel.stats.root_world_requests
        );
    }

    #[test]
    fn zero_workers_are_rejected_before_execution() {
        let cards = cards();
        let island = cards.card_id_by_name("Island").expect("Island");
        let state = state_with_land_choice(&cards, vec![island]);
        let error = compare_root_actions_parallel(
            &state,
            &cards,
            &DeterministicPolicy,
            MonteCarloConfig {
                root: RootSeed::from_u64(104),
                first_world: WorldId(0),
                samples: 1,
                rollout_max_steps: 12,
            },
            ParallelRootConfig { workers: 0 },
        )
        .unwrap_err();
        assert!(matches!(error, ParallelRootError::ZeroWorkers));
    }
}
