use std::collections::HashMap;

use thiserror::Error;
use urza_core::{MODEL_VERSION, TrueState};
use urza_info::INFORMATION_SCHEMA_VERSION;
use urza_policy::{DeterministicPolicy, POLICY_VERSION};
use urza_policy_bridge::{CANDIDATE_BRIDGE_VERSION, CandidateBridge};
use urza_rng::{RNG_SCHEME_VERSION, RootSeed, WorldId};
use urza_rollout::ROLLOUT_VERSION;
use urza_rules::{CardDatabase, HORIZON_TURN, RULES_VERSION, detect_terminal_win};
use urza_value::{
    EvaluationNamespace, Objective, VALUE_KEY_SCHEMA_VERSION, ValueKey, ValueKeyError,
    WinByHorizonScore,
};

use crate::root::{
    ROOT_ACTION_EVAL_VERSION, RootActionComparison, RootActionError, RootActionEvaluation,
    RootActionKey, canonical_worlds, empty_result, evaluate_sampled_root_world,
    public_root_actions, record_outcome,
};
use crate::{MONTE_CARLO_VERSION, MonteCarloError, WorldOutcome, sample_hidden_world};

pub const ADAPTIVE_ROOT_EVAL_VERSION: &str = "r5_exact_adaptive_root_eval_v1";
pub const ROOT_WORLD_CACHE_VERSION: &str = "r5_root_world_outcome_cache_v1";

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AdaptiveRootConfig {
    pub root: RootSeed,
    pub first_world: WorldId,
    pub min_samples: u32,
    pub max_samples: u32,
    pub batch_size: u32,
    pub rollout_max_steps: u32,
    pub evaluation_namespace: EvaluationNamespace,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum AdaptiveStopReason {
    ExactFullBudgetRankingCertified,
    MaxSamples,
}

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct AdaptiveSearchStats {
    pub candidate_roots: u32,
    pub worlds_consumed: u32,
    pub sampled_worlds: u32,
    pub batches: u32,
    pub root_world_requests: u64,
    pub cache_hits: u64,
    pub cache_misses: u64,
    pub root_world_rollouts: u64,
    pub rollout_steps_executed: u64,
    pub rollout_steps_avoided_by_cache: u64,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AdaptiveRootActionComparison {
    /// Exact values over `comparison.worlds`. After an early stop these are a
    /// strict prefix of the configured full budget, while the ranking below is
    /// certified for the complete configured budget.
    pub comparison: RootActionComparison,
    pub certified_full_budget_ranking: Vec<RootActionKey>,
    pub stop_reason: AdaptiveStopReason,
    pub max_samples: u32,
    pub stats: AdaptiveSearchStats,
}

impl AdaptiveRootActionComparison {
    pub fn used_samples(&self) -> usize {
        self.comparison.worlds.len()
    }

    pub fn stopped_early(&self) -> bool {
        self.stop_reason == AdaptiveStopReason::ExactFullBudgetRankingCertified
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct RootWorldCacheKey {
    pub cache_version: &'static str,
    pub state: ValueKey,
    pub evaluation: EvaluationNamespace,
    pub root_seed: RootSeed,
    pub action: RootActionKey,
    pub world: WorldId,
}

pub trait RootOutcomeCache {
    fn get(&mut self, key: &RootWorldCacheKey) -> Option<WorldOutcome>;
    fn insert(&mut self, key: RootWorldCacheKey, outcome: WorldOutcome);
}

#[derive(Debug, Default)]
pub struct NoopRootOutcomeCache;

impl RootOutcomeCache for NoopRootOutcomeCache {
    fn get(&mut self, _key: &RootWorldCacheKey) -> Option<WorldOutcome> {
        None
    }

    fn insert(&mut self, _key: RootWorldCacheKey, _outcome: WorldOutcome) {}
}

#[derive(Debug, Default)]
pub struct InMemoryRootOutcomeCache {
    entries: HashMap<RootWorldCacheKey, WorldOutcome>,
}

impl InMemoryRootOutcomeCache {
    pub fn len(&self) -> usize {
        self.entries.len()
    }

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    pub fn clear(&mut self) {
        self.entries.clear();
    }
}

impl RootOutcomeCache for InMemoryRootOutcomeCache {
    fn get(&mut self, key: &RootWorldCacheKey) -> Option<WorldOutcome> {
        self.entries.get(key).copied()
    }

    fn insert(&mut self, key: RootWorldCacheKey, outcome: WorldOutcome) {
        self.entries.insert(key, outcome);
    }
}

#[derive(Debug, Error)]
pub enum AdaptiveRootError {
    #[error(transparent)]
    RootAction(#[from] RootActionError),
    #[error(transparent)]
    ValueKey(#[from] ValueKeyError),
    #[error("adaptive root evaluation requires min_samples >= 1")]
    ZeroMinimumSamples,
    #[error("adaptive root evaluation requires max_samples >= min_samples")]
    InvalidMaximumSamples,
    #[error("adaptive root evaluation requires batch_size >= 1")]
    ZeroBatchSize,
    #[error("adaptive root evaluation namespace mismatch: {0}")]
    NamespaceMismatch(&'static str),
    #[error("cached root-world outcome declares {actual:?}, expected {expected:?}")]
    CacheWorldMismatch { expected: WorldId, actual: WorldId },
    #[error("adaptive optimistic score overflow")]
    ScoreOverflow,
}

/// Construct the complete namespace required for R5 root-world cache safety.
///
/// `catalog_digest` and `environment_version` are caller inputs because the
/// generic `CardDatabase` execution trait intentionally exposes neither.
pub fn current_r5_evaluation_namespace(
    catalog_digest: impl Into<String>,
    environment_version: impl Into<String>,
    rollout_budget: u32,
) -> EvaluationNamespace {
    EvaluationNamespace {
        rules_version: RULES_VERSION.to_owned(),
        catalog_digest: catalog_digest.into(),
        model_version: MODEL_VERSION.to_owned(),
        policy_version: POLICY_VERSION.to_owned(),
        value_key_schema_version: VALUE_KEY_SCHEMA_VERSION.to_owned(),
        objective: Objective::WinByHorizon,
        horizon: HORIZON_TURN,
        environment_version: environment_version.into(),
        rng_scheme_version: RNG_SCHEME_VERSION.to_owned(),
        sample_namespace: expected_sample_namespace(),
        rollout_budget,
        continuation_identity: expected_continuation_identity(),
    }
}

pub fn compare_root_actions_adaptive<D: CardDatabase, C: RootOutcomeCache>(
    template: &TrueState,
    cards: &D,
    continuation_policy: &DeterministicPolicy,
    config: &AdaptiveRootConfig,
    cache: &mut C,
) -> Result<AdaptiveRootActionComparison, AdaptiveRootError> {
    if config.min_samples == 0 {
        return Err(AdaptiveRootError::ZeroMinimumSamples);
    }
    if config.max_samples < config.min_samples {
        return Err(AdaptiveRootError::InvalidMaximumSamples);
    }
    if config.batch_size == 0 {
        return Err(AdaptiveRootError::ZeroBatchSize);
    }

    let mut worlds = Vec::with_capacity(config.max_samples as usize);
    for offset in 0..config.max_samples {
        let world = config
            .first_world
            .0
            .checked_add(u64::from(offset))
            .ok_or_else(|| {
                AdaptiveRootError::RootAction(RootActionError::MonteCarlo(
                    MonteCarloError::WorldIdOverflow,
                ))
            })?;
        worlds.push(WorldId(world));
    }

    compare_root_actions_adaptive_world_ids(
        template,
        cards,
        continuation_policy,
        config.root,
        config.rollout_max_steps,
        config.min_samples,
        config.batch_size,
        &config.evaluation_namespace,
        &worlds,
        cache,
    )
}

#[allow(clippy::too_many_arguments)]
pub fn compare_root_actions_adaptive_world_ids<D: CardDatabase, C: RootOutcomeCache>(
    template: &TrueState,
    cards: &D,
    continuation_policy: &DeterministicPolicy,
    root: RootSeed,
    rollout_max_steps: u32,
    min_samples: u32,
    batch_size: u32,
    evaluation_namespace: &EvaluationNamespace,
    world_ids: &[WorldId],
    cache: &mut C,
) -> Result<AdaptiveRootActionComparison, AdaptiveRootError> {
    if min_samples == 0 {
        return Err(AdaptiveRootError::ZeroMinimumSamples);
    }
    if batch_size == 0 {
        return Err(AdaptiveRootError::ZeroBatchSize);
    }
    if rollout_max_steps == 0 {
        return Err(RootActionError::ZeroStepBudget.into());
    }
    validate_namespace(evaluation_namespace, rollout_max_steps)?;

    let worlds = canonical_worlds(world_ids)?;
    let max_samples =
        u32::try_from(worlds.len()).map_err(|_| AdaptiveRootError::InvalidMaximumSamples)?;
    if min_samples > max_samples {
        return Err(AdaptiveRootError::InvalidMaximumSamples);
    }

    let template_bridge = CandidateBridge::build(template, cards)?;
    if let Some(family) = detect_terminal_win(template_bridge.information(), cards) {
        return Err(RootActionError::AlreadyTerminal(family).into());
    }
    let roots = public_root_actions(&template_bridge);
    if roots.is_empty() {
        return Err(RootActionError::NoCandidates.into());
    }
    let state_key = ValueKey::try_from_information(template_bridge.information())?;

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
    let batch_size = usize::try_from(batch_size).expect("u32 fits usize");
    let mut stop_reason = AdaptiveStopReason::MaxSamples;
    let mut certified_ranking = Vec::new();

    'batches: for batch in worlds.chunks(batch_size) {
        stats.batches = stats.batches.saturating_add(1);
        for world in batch {
            let root_count = u64::try_from(roots.len()).unwrap_or(u64::MAX);
            stats.root_world_requests = stats.root_world_requests.saturating_add(root_count);

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
            let mut outcomes = Vec::with_capacity(roots.len());
            let mut missing = Vec::new();
            for (index, key) in keys.iter().enumerate() {
                if let Some(outcome) = cache.get(key) {
                    if outcome.world != *world {
                        return Err(AdaptiveRootError::CacheWorldMismatch {
                            expected: *world,
                            actual: outcome.world,
                        });
                    }
                    stats.cache_hits = stats.cache_hits.saturating_add(1);
                    stats.rollout_steps_avoided_by_cache = stats
                        .rollout_steps_avoided_by_cache
                        .saturating_add(u64::from(outcome.rollout_steps));
                    outcomes.push(Some(outcome));
                } else {
                    stats.cache_misses = stats.cache_misses.saturating_add(1);
                    outcomes.push(None);
                    missing.push(index);
                }
            }

            if !missing.is_empty() {
                let sampled = sample_hidden_world(template, root, *world)?;
                stats.sampled_worlds = stats.sampled_worlds.saturating_add(1);
                let sampled_bridge = CandidateBridge::build(&sampled, cards)?;
                if public_root_actions(&sampled_bridge) != roots {
                    return Err(RootActionError::CandidateSetDrift { world: *world }.into());
                }

                for index in missing {
                    let outcome = evaluate_sampled_root_world(
                        &sampled,
                        &sampled_bridge,
                        cards,
                        continuation_policy,
                        root,
                        rollout_max_steps,
                        *world,
                        &roots[index],
                    )?;
                    stats.root_world_rollouts = stats.root_world_rollouts.saturating_add(1);
                    stats.rollout_steps_executed = stats
                        .rollout_steps_executed
                        .saturating_add(u64::from(outcome.rollout_steps));
                    cache.insert(keys[index].clone(), outcome);
                    outcomes[index] = Some(outcome);
                }
            }

            for (evaluation, outcome) in evaluations.iter_mut().zip(outcomes) {
                record_outcome(
                    &mut evaluation.result,
                    outcome.expect("every root-world outcome is present"),
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
) -> Result<bool, AdaptiveRootError> {
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
) -> Result<WinByHorizonScore, AdaptiveRootError> {
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
) -> Result<(), AdaptiveRootError> {
    macro_rules! require {
        ($condition:expr, $field:literal) => {
            if !$condition {
                return Err(AdaptiveRootError::NamespaceMismatch($field));
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
        namespace.sample_namespace == expected_sample_namespace(),
        "sample_namespace"
    );
    require!(namespace.rollout_budget == rollout_budget, "rollout_budget");
    require!(
        namespace.continuation_identity == expected_continuation_identity(),
        "continuation_identity"
    );
    Ok(())
}

fn expected_sample_namespace() -> String {
    format!("{INFORMATION_SCHEMA_VERSION}|{MONTE_CARLO_VERSION}")
}

fn expected_continuation_identity() -> String {
    format!("{CANDIDATE_BRIDGE_VERSION}|{ROLLOUT_VERSION}|{ROOT_ACTION_EVAL_VERSION}")
}

#[cfg(test)]
mod tests {
    use super::*;
    use urza_cards::R4CardDatabase;
    use urza_core::{CardZone, Phase, TrueLibrary, Window};
    use urza_rules::WinFamily;

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

    fn config(max_samples: u32, environment: &str) -> AdaptiveRootConfig {
        AdaptiveRootConfig {
            root: RootSeed::from_u64(0x4144_4150_545f_5235),
            first_world: WorldId(40),
            min_samples: 1,
            max_samples,
            batch_size: 1,
            rollout_max_steps: 12,
            evaluation_namespace: current_r5_evaluation_namespace(
                "test-r4-catalog-digest",
                environment,
                12,
            ),
        }
    }

    #[test]
    fn adaptive_max_budget_matches_fixed_reference_exactly() {
        let cards = cards();
        let island = cards.card_id_by_name("Island").expect("Island");
        let crypt = cards.card_id_by_name("Tormod's Crypt").expect("Crypt");
        let state = state_with_land_choice(&cards, vec![island, crypt]);
        let cfg = config(3, "test-goldfish-v1");
        let fixed = crate::root::compare_root_actions_world_ids(
            &state,
            &cards,
            &DeterministicPolicy,
            cfg.root,
            cfg.rollout_max_steps,
            &[WorldId(40), WorldId(41), WorldId(42)],
        )
        .unwrap();
        let mut cache = NoopRootOutcomeCache;
        let adaptive = compare_root_actions_adaptive(
            &state,
            &cards,
            &DeterministicPolicy,
            &cfg,
            &mut cache,
        )
        .unwrap();
        assert_eq!(adaptive.stop_reason, AdaptiveStopReason::MaxSamples);
        assert_eq!(adaptive.comparison, fixed);
    }

    #[test]
    fn second_identical_search_is_served_entirely_from_cache() {
        let cards = cards();
        let island = cards.card_id_by_name("Island").expect("Island");
        let crypt = cards.card_id_by_name("Tormod's Crypt").expect("Crypt");
        let state = state_with_land_choice(&cards, vec![island, crypt]);
        let cfg = config(3, "test-goldfish-v1");
        let mut cache = InMemoryRootOutcomeCache::default();
        let first = compare_root_actions_adaptive(
            &state,
            &cards,
            &DeterministicPolicy,
            &cfg,
            &mut cache,
        )
        .unwrap();
        assert!(first.stats.cache_misses > 0);
        assert!(first.stats.root_world_rollouts > 0);

        let second = compare_root_actions_adaptive(
            &state,
            &cards,
            &DeterministicPolicy,
            &cfg,
            &mut cache,
        )
        .unwrap();
        assert_eq!(first.comparison, second.comparison);
        assert_eq!(second.stats.cache_misses, 0);
        assert_eq!(second.stats.root_world_rollouts, 0);
        assert_eq!(second.stats.sampled_worlds, 0);
        assert_eq!(second.stats.cache_hits, second.stats.root_world_requests);
    }

    #[test]
    fn hidden_order_equivalent_template_reuses_public_value_cache() {
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
        let cfg = config(3, "test-goldfish-v1");
        let mut cache = InMemoryRootOutcomeCache::default();
        let left_result = compare_root_actions_adaptive(
            &left,
            &cards,
            &DeterministicPolicy,
            &cfg,
            &mut cache,
        )
        .unwrap();
        let right_result = compare_root_actions_adaptive(
            &right,
            &cards,
            &DeterministicPolicy,
            &cfg,
            &mut cache,
        )
        .unwrap();
        assert_eq!(left_result.comparison, right_result.comparison);
        assert_eq!(right_result.stats.cache_misses, 0);
        assert_eq!(right_result.stats.sampled_worlds, 0);
    }

    #[test]
    fn namespace_and_root_seed_changes_cannot_alias_cache_entries() {
        let cards = cards();
        let island = cards.card_id_by_name("Island").expect("Island");
        let state = state_with_land_choice(&cards, vec![island]);
        let cfg = config(2, "env-a");
        let mut cache = InMemoryRootOutcomeCache::default();
        compare_root_actions_adaptive(
            &state,
            &cards,
            &DeterministicPolicy,
            &cfg,
            &mut cache,
        )
        .unwrap();

        let mut changed_namespace = config(2, "env-b");
        let result = compare_root_actions_adaptive(
            &state,
            &cards,
            &DeterministicPolicy,
            &changed_namespace,
            &mut cache,
        )
        .unwrap();
        assert_eq!(result.stats.cache_hits, 0);

        changed_namespace.root = RootSeed::from_u64(999);
        let result = compare_root_actions_adaptive(
            &state,
            &cards,
            &DeterministicPolicy,
            &changed_namespace,
            &mut cache,
        )
        .unwrap();
        assert_eq!(result.stats.cache_hits, 0);
    }

    #[test]
    fn exact_certificate_stops_early_and_matches_full_budget_ranking() {
        let cards = cards();
        let island = cards.card_id_by_name("Island").expect("Island");
        let state = state_with_land_choice(&cards, vec![island]);
        let mut early_cfg = config(8, "synthetic-cache-v1");
        let bridge = CandidateBridge::build(&state, &cards).unwrap();
        let roots = public_root_actions(&bridge);
        assert!(roots.len() >= 2);
        let state_key = ValueKey::try_from_information(bridge.information()).unwrap();
        let mut cache = InMemoryRootOutcomeCache::default();

        for offset in 0..early_cfg.max_samples {
            let world = WorldId(early_cfg.first_world.0 + u64::from(offset));
            for (index, action) in roots.iter().enumerate() {
                let outcome = if index == 0 {
                    crate::SampleOutcome::Win {
                        family: WinFamily::PowerArtifactBasalt,
                        turn: 1,
                    }
                } else {
                    crate::SampleOutcome::LossByHorizon
                };
                cache.insert(
                    RootWorldCacheKey {
                        cache_version: ROOT_WORLD_CACHE_VERSION,
                        state: state_key.clone(),
                        evaluation: early_cfg.evaluation_namespace.clone(),
                        root_seed: early_cfg.root,
                        action: action.clone(),
                        world,
                    },
                    WorldOutcome {
                        world,
                        outcome,
                        rollout_steps: 1,
                    },
                );
            }
        }

        let early = compare_root_actions_adaptive(
            &state,
            &cards,
            &DeterministicPolicy,
            &early_cfg,
            &mut cache,
        )
        .unwrap();
        assert!(early.stopped_early());
        assert!(early.used_samples() < early_cfg.max_samples as usize);

        early_cfg.min_samples = early_cfg.max_samples;
        let full = compare_root_actions_adaptive(
            &state,
            &cards,
            &DeterministicPolicy,
            &early_cfg,
            &mut cache,
        )
        .unwrap();
        assert_eq!(full.stop_reason, AdaptiveStopReason::MaxSamples);
        assert_eq!(early.comparison.selected, full.comparison.selected);
        assert_eq!(
            early.certified_full_budget_ranking,
            full.certified_full_budget_ranking
        );
    }

    #[test]
    fn invalid_namespace_is_rejected_before_cache_access() {
        let cards = cards();
        let island = cards.card_id_by_name("Island").expect("Island");
        let state = state_with_land_choice(&cards, vec![island]);
        let mut cfg = config(2, "test-goldfish-v1");
        cfg.evaluation_namespace.policy_version = "wrong-policy".to_owned();
        let mut cache = InMemoryRootOutcomeCache::default();
        let error = compare_root_actions_adaptive(
            &state,
            &cards,
            &DeterministicPolicy,
            &cfg,
            &mut cache,
        )
        .unwrap_err();
        assert!(matches!(
            error,
            AdaptiveRootError::NamespaceMismatch("policy_version")
        ));
        assert!(cache.is_empty());
    }
}
