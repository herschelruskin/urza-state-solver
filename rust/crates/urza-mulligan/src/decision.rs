use std::cmp::Ordering;
use std::collections::HashMap;
use std::fmt;

use urza_cards::R4CardDatabase;
use urza_core::CardDefId;
use urza_mc::{MonteCarloConfig, MonteCarloError, MonteCarloResult, evaluate};
use urza_policy::{DeterministicPolicy, POLICY_VERSION};
use urza_rng::{RootSeed, WorldId};
use urza_rules::HORIZON_TURN;
use urza_value::WinDistribution;

use crate::{
    BottomSubset, CommanderDeck, KeptHand, MulliganError, MulliganStage, MulliganState,
    OpeningError, PregameContext, bridge_kept_hand, draw_fresh_seven, enumerate_bottom_subsets,
};

pub const MULLIGAN_DECISION_VERSION: &str = "r6_keep_vs_mull_dp_v1";
pub const MULLIGAN_OBJECTIVE_VERSION: &str = "r6_normalized_win_by_horizon_v1";
pub const DEFAULT_MULLIGAN_ENVIRONMENT_VERSION: &str = "r6_goldfish_opening_v1";

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MulliganEvaluationConfig {
    pub rollout: MonteCarloConfig,
    pub continuation_root: RootSeed,
    pub first_future_world: WorldId,
    pub future_hand_samples: u32,
    pub environment_version: String,
}

impl Default for MulliganEvaluationConfig {
    fn default() -> Self {
        Self {
            rollout: MonteCarloConfig::default(),
            continuation_root: RootSeed::from_u64(0x5236_434f_4e54_0001),
            first_future_world: WorldId(0),
            future_hand_samples: 32,
            environment_version: DEFAULT_MULLIGAN_ENVIRONMENT_VERSION.to_owned(),
        }
    }
}

impl MulliganEvaluationConfig {
    fn validate(&self) -> Result<(), MulliganEvaluationError> {
        if self.rollout.samples == 0 {
            return Err(MulliganEvaluationError::InvalidConfig(
                "rollout.samples must be at least one",
            ));
        }
        if self.rollout.rollout_max_steps == 0 {
            return Err(MulliganEvaluationError::InvalidConfig(
                "rollout.rollout_max_steps must be at least one",
            ));
        }
        if self.future_hand_samples == 0 {
            return Err(MulliganEvaluationError::InvalidConfig(
                "future_hand_samples must be at least one",
            ));
        }
        Ok(())
    }
}

/// Exact normalized R6 value derived only from accepted R5 Monte-Carlo outcomes.
///
/// The denominator is the number of equally weighted outcome units. Nested
/// continuation values scale integer outcome counts rather than using floating
/// point, so deterministic keep/mull identity is platform-independent.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ExactWinRate {
    pub denominator: u128,
    pub t1_through_t6: [u128; 6],
    pub losses: u128,
}

impl ExactWinRate {
    pub fn from_distribution(
        distribution: &WinDistribution,
    ) -> Result<Self, MulliganEvaluationError> {
        let mut turns = [0_u128; 6];
        for (target, source) in turns.iter_mut().zip(distribution.t1_through_t6) {
            *target = u128::from(source);
        }
        let losses = u128::from(distribution.losses);
        let denominator = turns
            .iter()
            .try_fold(losses, |total, wins| total.checked_add(*wins))
            .ok_or(MulliganEvaluationError::ArithmeticOverflow(
                "win-distribution denominator",
            ))?;
        if denominator == 0 {
            return Err(MulliganEvaluationError::InvalidConfig(
                "value distribution contains no outcomes",
            ));
        }
        Ok(Self {
            denominator,
            t1_through_t6: turns,
            losses,
        })
    }

    pub fn total_wins(&self) -> Result<u128, MulliganEvaluationError> {
        self.t1_through_t6
            .iter()
            .try_fold(0_u128, |total, wins| total.checked_add(*wins))
            .ok_or(MulliganEvaluationError::ArithmeticOverflow("total wins"))
    }

    pub fn objective_cmp(&self, other: &Self) -> Result<Ordering, MulliganEvaluationError> {
        let total = compare_fraction(
            self.total_wins()?,
            self.denominator,
            other.total_wins()?,
            other.denominator,
        )?;
        if total != Ordering::Equal {
            return Ok(total);
        }
        for index in 0..self.t1_through_t6.len() {
            let turn = compare_fraction(
                self.t1_through_t6[index],
                self.denominator,
                other.t1_through_t6[index],
                other.denominator,
            )?;
            if turn != Ordering::Equal {
                return Ok(turn);
            }
        }
        Ok(Ordering::Equal)
    }

    fn scaled_to(&self, denominator: u128) -> Result<Self, MulliganEvaluationError> {
        if denominator % self.denominator != 0 {
            return Err(MulliganEvaluationError::IncompatibleDenominator {
                source: self.denominator,
                target: denominator,
            });
        }
        let factor = denominator / self.denominator;
        let mut turns = [0_u128; 6];
        for (target, source) in turns.iter_mut().zip(self.t1_through_t6) {
            *target =
                source
                    .checked_mul(factor)
                    .ok_or(MulliganEvaluationError::ArithmeticOverflow(
                        "scaled exact-turn wins",
                    ))?;
        }
        let losses = self
            .losses
            .checked_mul(factor)
            .ok_or(MulliganEvaluationError::ArithmeticOverflow("scaled losses"))?;
        Ok(Self {
            denominator,
            t1_through_t6: turns,
            losses,
        })
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ObjectivePreference {
    Keep,
    Equal,
    Mulligan,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum WinRateGapDirection {
    KeepHigher,
    Equal,
    MulliganHigher,
}

/// Exact primary-objective gap. `numerator / denominator` is the absolute
/// difference in total win rate; `direction` says which side is higher.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ExactWinRateGap {
    pub direction: WinRateGapDirection,
    pub numerator: u128,
    pub denominator: u128,
}

impl ExactWinRateGap {
    fn between(
        keep: &ExactWinRate,
        mulligan: &ExactWinRate,
    ) -> Result<Self, MulliganEvaluationError> {
        let keep_cross = keep.total_wins()?.checked_mul(mulligan.denominator).ok_or(
            MulliganEvaluationError::ArithmeticOverflow("keep win-rate cross product"),
        )?;
        let mulligan_cross = mulligan.total_wins()?.checked_mul(keep.denominator).ok_or(
            MulliganEvaluationError::ArithmeticOverflow("mulligan win-rate cross product"),
        )?;
        let denominator = keep.denominator.checked_mul(mulligan.denominator).ok_or(
            MulliganEvaluationError::ArithmeticOverflow("win-rate gap denominator"),
        )?;

        let (direction, numerator) = match keep_cross.cmp(&mulligan_cross) {
            Ordering::Greater => (WinRateGapDirection::KeepHigher, keep_cross - mulligan_cross),
            Ordering::Equal => (WinRateGapDirection::Equal, 0),
            Ordering::Less => (
                WinRateGapDirection::MulliganHigher,
                mulligan_cross - keep_cross,
            ),
        };
        Ok(Self {
            direction,
            numerator,
            denominator,
        })
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct KeepPackageEvaluation {
    pub bottom_indices: Vec<usize>,
    pub kept_hand: Vec<CardDefId>,
    pub known_bottom: Vec<CardDefId>,
    pub value: ExactWinRate,
    pub result: MonteCarloResult,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ContinuationEvaluation {
    /// Fresh-seven stage whose expected optimal value is represented.
    pub stage: MulliganStage,
    pub sampled_hands: u32,
    pub value: ExactWinRate,
    pub keep_decisions: u32,
    pub mulligan_decisions: u32,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum MulliganChoice {
    Keep { bottom_indices: Vec<usize> },
    Mulligan,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MulliganDecisionEvaluation {
    pub stage: MulliganStage,
    pub pregame: PregameContext,
    pub keep_packages: Vec<KeepPackageEvaluation>,
    pub best_keep_index: usize,
    pub mull_again: Option<ContinuationEvaluation>,
    pub objective_preference: ObjectivePreference,
    pub primary_win_rate_gap: Option<ExactWinRateGap>,
    pub selected: MulliganChoice,
}

impl MulliganDecisionEvaluation {
    pub fn best_keep(&self) -> &KeepPackageEvaluation {
        &self.keep_packages[self.best_keep_index]
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
struct DecisionContinuationCacheKey {
    deck_version: String,
    stage: MulliganStage,
    pregame: PregameContext,
    decision_version: &'static str,
    policy_version: &'static str,
    objective_version: &'static str,
    horizon: u8,
    environment_version: String,
    continuation_root: RootSeed,
    first_future_world: WorldId,
    future_hand_samples: u32,
    rollout_root: RootSeed,
    rollout_first_world: WorldId,
    rollout_samples: u32,
    rollout_max_steps: u32,
}

#[derive(Debug, Default)]
pub struct MulliganDecisionCache {
    entries: HashMap<DecisionContinuationCacheKey, ContinuationEvaluation>,
    hits: u64,
    misses: u64,
}

impl MulliganDecisionCache {
    pub fn len(&self) -> usize {
        self.entries.len()
    }

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    pub fn hits(&self) -> u64 {
        self.hits
    }

    pub fn misses(&self) -> u64 {
        self.misses
    }

    pub fn clear(&mut self) {
        self.entries.clear();
        self.hits = 0;
        self.misses = 0;
    }

    fn get(&mut self, key: &DecisionContinuationCacheKey) -> Option<ContinuationEvaluation> {
        let value = self.entries.get(key).cloned();
        if value.is_some() {
            self.hits = self.hits.saturating_add(1);
        } else {
            self.misses = self.misses.saturating_add(1);
        }
        value
    }

    fn insert(&mut self, key: DecisionContinuationCacheKey, value: ContinuationEvaluation) {
        self.entries.insert(key, value);
    }
}

#[derive(Debug)]
pub enum MulliganEvaluationError {
    InvalidConfig(&'static str),
    Opening(OpeningError),
    Mulligan(MulliganError),
    MonteCarlo(MonteCarloError),
    NoKeepPackages,
    FutureWorldOverflow,
    ArithmeticOverflow(&'static str),
    IncompatibleDenominator { source: u128, target: u128 },
    UnexpectedRolloutSampleCount { expected: u128, actual: u128 },
}

impl fmt::Display for MulliganEvaluationError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InvalidConfig(message) => {
                write!(formatter, "invalid mulligan evaluation config: {message}")
            }
            Self::Opening(error) => write!(formatter, "opening-state bridge failed: {error}"),
            Self::Mulligan(error) => write!(formatter, "mulligan state failed: {error}"),
            Self::MonteCarlo(error) => {
                write!(formatter, "R5 continuation evaluation failed: {error}")
            }
            Self::NoKeepPackages => {
                write!(formatter, "mulligan stage exposed no legal keep package")
            }
            Self::FutureWorldOverflow => {
                write!(formatter, "future-hand world id range overflowed u64")
            }
            Self::ArithmeticOverflow(context) => {
                write!(
                    formatter,
                    "exact mulligan value arithmetic overflow: {context}"
                )
            }
            Self::IncompatibleDenominator { source, target } => write!(
                formatter,
                "cannot scale exact mulligan value denominator {source} to {target}"
            ),
            Self::UnexpectedRolloutSampleCount { expected, actual } => write!(
                formatter,
                "R5 evaluator returned {actual} outcomes, expected exactly {expected}"
            ),
        }
    }
}

impl std::error::Error for MulliganEvaluationError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Opening(error) => Some(error),
            Self::Mulligan(error) => Some(error),
            Self::MonteCarlo(error) => Some(error),
            _ => None,
        }
    }
}

impl From<OpeningError> for MulliganEvaluationError {
    fn from(value: OpeningError) -> Self {
        Self::Opening(value)
    }
}

impl From<MulliganError> for MulliganEvaluationError {
    fn from(value: MulliganError) -> Self {
        Self::Mulligan(value)
    }
}

impl From<MonteCarloError> for MulliganEvaluationError {
    fn from(value: MonteCarloError) -> Self {
        Self::MonteCarlo(value)
    }
}

/// Exhaustively value every legal London-bottom package for the visible seven.
///
/// Every package uses the same accepted R5 Monte-Carlo configuration. No legal
/// bottom package is beam-pruned.
pub fn evaluate_keep_packages(
    state: &MulliganState<CardDefId>,
    deck: &CommanderDeck,
    opening_root: RootSeed,
    opening_world: WorldId,
    cards: &R4CardDatabase,
    policy: &DeterministicPolicy,
    config: &MulliganEvaluationConfig,
) -> Result<Vec<KeepPackageEvaluation>, MulliganEvaluationError> {
    config.validate()?;
    let subsets = enumerate_bottom_subsets(state.stage());
    let mut evaluations = Vec::with_capacity(subsets.len());
    for subset in subsets {
        evaluations.push(evaluate_keep_package(
            state,
            subset,
            deck,
            opening_root,
            opening_world,
            cards,
            policy,
            config,
        )?);
    }
    Ok(evaluations)
}

/// Compute the expected optimal value of taking another mulligan.
///
/// This API intentionally accepts stage/pregame/configuration but no rejected
/// hand and no actual next-seven world. The value is therefore structurally
/// incapable of depending on the rejected seven or an unrevealed next seven.
pub fn evaluate_mull_again(
    current_stage: MulliganStage,
    pregame: PregameContext,
    deck: &CommanderDeck,
    cards: &R4CardDatabase,
    policy: &DeterministicPolicy,
    config: &MulliganEvaluationConfig,
    cache: &mut MulliganDecisionCache,
) -> Result<Option<ContinuationEvaluation>, MulliganEvaluationError> {
    config.validate()?;
    let Some(next_stage) = current_stage.next() else {
        return Ok(None);
    };
    evaluate_continuation(next_stage, pregame, deck, cards, policy, config, cache).map(Some)
}

/// Compare the best exhaustive keep package against cached expected mull-again
/// continuation value under the same normalized WinByHorizon objective.
///
/// Exact objective ties keep the current hand; the objective is indifferent and
/// this deterministic tie rule avoids an otherwise pointless extra mulligan.
pub fn evaluate_mulligan_decision(
    state: &MulliganState<CardDefId>,
    deck: &CommanderDeck,
    opening_root: RootSeed,
    opening_world: WorldId,
    cards: &R4CardDatabase,
    policy: &DeterministicPolicy,
    config: &MulliganEvaluationConfig,
    cache: &mut MulliganDecisionCache,
) -> Result<MulliganDecisionEvaluation, MulliganEvaluationError> {
    config.validate()?;
    let keep_packages = evaluate_keep_packages(
        state,
        deck,
        opening_root,
        opening_world,
        cards,
        policy,
        config,
    )?;
    let best_keep_index = best_keep_index(&keep_packages)?;
    let best_keep = &keep_packages[best_keep_index];
    let mull_again = evaluate_mull_again(
        state.stage(),
        state.pregame(),
        deck,
        cards,
        policy,
        config,
        cache,
    )?;

    let (objective_preference, primary_win_rate_gap, selected) = match &mull_again {
        None => (
            ObjectivePreference::Keep,
            None,
            MulliganChoice::Keep {
                bottom_indices: best_keep.bottom_indices.clone(),
            },
        ),
        Some(continuation) => {
            let ordering = best_keep.value.objective_cmp(&continuation.value)?;
            let preference = match ordering {
                Ordering::Greater => ObjectivePreference::Keep,
                Ordering::Equal => ObjectivePreference::Equal,
                Ordering::Less => ObjectivePreference::Mulligan,
            };
            let gap = ExactWinRateGap::between(&best_keep.value, &continuation.value)?;
            let selected = if ordering == Ordering::Less {
                MulliganChoice::Mulligan
            } else {
                MulliganChoice::Keep {
                    bottom_indices: best_keep.bottom_indices.clone(),
                }
            };
            (preference, Some(gap), selected)
        }
    };

    Ok(MulliganDecisionEvaluation {
        stage: state.stage(),
        pregame: state.pregame(),
        keep_packages,
        best_keep_index,
        mull_again,
        objective_preference,
        primary_win_rate_gap,
        selected,
    })
}

#[allow(clippy::too_many_arguments)]
fn evaluate_keep_package(
    state: &MulliganState<CardDefId>,
    subset: BottomSubset,
    deck: &CommanderDeck,
    opening_root: RootSeed,
    opening_world: WorldId,
    cards: &R4CardDatabase,
    policy: &DeterministicPolicy,
    config: &MulliganEvaluationConfig,
) -> Result<KeepPackageEvaluation, MulliganEvaluationError> {
    let kept = state.clone().keep(subset.indices())?;
    evaluate_kept_hand(
        kept,
        subset.indices().to_vec(),
        deck,
        opening_root,
        opening_world,
        cards,
        policy,
        config,
    )
}

#[allow(clippy::too_many_arguments)]
fn evaluate_kept_hand(
    kept: KeptHand<CardDefId>,
    bottom_indices: Vec<usize>,
    deck: &CommanderDeck,
    opening_root: RootSeed,
    opening_world: WorldId,
    cards: &R4CardDatabase,
    policy: &DeterministicPolicy,
    config: &MulliganEvaluationConfig,
) -> Result<KeepPackageEvaluation, MulliganEvaluationError> {
    let bridge = bridge_kept_hand(&kept, deck, opening_root, opening_world)?;
    let result = evaluate(bridge.true_state(), cards, policy, config.rollout)?;
    let value = ExactWinRate::from_distribution(&result.win_distribution)?;
    let expected = u128::from(config.rollout.samples);
    if value.denominator != expected {
        return Err(MulliganEvaluationError::UnexpectedRolloutSampleCount {
            expected,
            actual: value.denominator,
        });
    }

    Ok(KeepPackageEvaluation {
        bottom_indices,
        kept_hand: kept.hand,
        known_bottom: kept.known_bottom,
        value,
        result,
    })
}

fn best_keep_index(
    evaluations: &[KeepPackageEvaluation],
) -> Result<usize, MulliganEvaluationError> {
    let Some((mut best_index, mut best)) = evaluations.iter().enumerate().next() else {
        return Err(MulliganEvaluationError::NoKeepPackages);
    };

    for (index, candidate) in evaluations.iter().enumerate().skip(1) {
        let ordering = candidate.value.objective_cmp(&best.value)?;
        if ordering == Ordering::Greater
            || (ordering == Ordering::Equal && candidate.bottom_indices < best.bottom_indices)
        {
            best_index = index;
            best = candidate;
        }
    }
    Ok(best_index)
}

fn evaluate_continuation(
    stage: MulliganStage,
    pregame: PregameContext,
    deck: &CommanderDeck,
    cards: &R4CardDatabase,
    policy: &DeterministicPolicy,
    config: &MulliganEvaluationConfig,
    cache: &mut MulliganDecisionCache,
) -> Result<ContinuationEvaluation, MulliganEvaluationError> {
    let key = continuation_cache_key(stage, pregame, deck, config);
    if let Some(cached) = cache.get(&key) {
        return Ok(cached);
    }

    let child = match stage.next() {
        Some(next) => Some(evaluate_continuation(
            next, pregame, deck, cards, policy, config, cache,
        )?),
        None => None,
    };
    let per_hand_denominator = child
        .as_ref()
        .map_or(u128::from(config.rollout.samples), |value| {
            value.value.denominator
        });

    let mut turn_totals = [0_u128; 6];
    let mut loss_total = 0_u128;
    let mut keep_decisions = 0_u32;
    let mut mulligan_decisions = 0_u32;

    for offset in 0..config.future_hand_samples {
        let world = future_world(config.first_future_world, offset)?;
        let seven = draw_fresh_seven(deck, config.continuation_root, world, stage);
        let state = MulliganState::at_stage(stage, seven, pregame)?;
        let packages = evaluate_keep_packages(
            &state,
            deck,
            config.continuation_root,
            world,
            cards,
            policy,
            config,
        )?;
        let best_index = best_keep_index(&packages)?;
        let best_keep = &packages[best_index];

        let selected = match &child {
            Some(continuation)
                if best_keep.value.objective_cmp(&continuation.value)? == Ordering::Less =>
            {
                mulligan_decisions = mulligan_decisions.saturating_add(1);
                continuation.value.clone()
            }
            _ => {
                keep_decisions = keep_decisions.saturating_add(1);
                best_keep.value.clone()
            }
        };
        let scaled = selected.scaled_to(per_hand_denominator)?;
        for (total, value) in turn_totals.iter_mut().zip(scaled.t1_through_t6) {
            *total =
                total
                    .checked_add(value)
                    .ok_or(MulliganEvaluationError::ArithmeticOverflow(
                        "continuation exact-turn aggregate",
                    ))?;
        }
        loss_total = loss_total.checked_add(scaled.losses).ok_or(
            MulliganEvaluationError::ArithmeticOverflow("continuation loss aggregate"),
        )?;
    }

    let denominator = per_hand_denominator
        .checked_mul(u128::from(config.future_hand_samples))
        .ok_or(MulliganEvaluationError::ArithmeticOverflow(
            "continuation denominator",
        ))?;
    let value = ExactWinRate {
        denominator,
        t1_through_t6: turn_totals,
        losses: loss_total,
    };
    let represented = value.total_wins()?.checked_add(value.losses).ok_or(
        MulliganEvaluationError::ArithmeticOverflow("continuation represented outcomes"),
    )?;
    if represented != value.denominator {
        return Err(MulliganEvaluationError::ArithmeticOverflow(
            "continuation outcome accounting drift",
        ));
    }

    let evaluation = ContinuationEvaluation {
        stage,
        sampled_hands: config.future_hand_samples,
        value,
        keep_decisions,
        mulligan_decisions,
    };
    cache.insert(key, evaluation.clone());
    Ok(evaluation)
}

fn continuation_cache_key(
    stage: MulliganStage,
    pregame: PregameContext,
    deck: &CommanderDeck,
    config: &MulliganEvaluationConfig,
) -> DecisionContinuationCacheKey {
    DecisionContinuationCacheKey {
        deck_version: deck.deck_version().to_owned(),
        stage,
        pregame,
        decision_version: MULLIGAN_DECISION_VERSION,
        policy_version: POLICY_VERSION,
        objective_version: MULLIGAN_OBJECTIVE_VERSION,
        horizon: HORIZON_TURN,
        environment_version: config.environment_version.clone(),
        continuation_root: config.continuation_root,
        first_future_world: config.first_future_world,
        future_hand_samples: config.future_hand_samples,
        rollout_root: config.rollout.root,
        rollout_first_world: config.rollout.first_world,
        rollout_samples: config.rollout.samples,
        rollout_max_steps: config.rollout.rollout_max_steps,
    }
}

fn future_world(first: WorldId, offset: u32) -> Result<WorldId, MulliganEvaluationError> {
    first
        .0
        .checked_add(u64::from(offset))
        .map(WorldId)
        .ok_or(MulliganEvaluationError::FutureWorldOverflow)
}

fn compare_fraction(
    left_numerator: u128,
    left_denominator: u128,
    right_numerator: u128,
    right_denominator: u128,
) -> Result<Ordering, MulliganEvaluationError> {
    let left = left_numerator.checked_mul(right_denominator).ok_or(
        MulliganEvaluationError::ArithmeticOverflow("fraction comparison left cross product"),
    )?;
    let right = right_numerator.checked_mul(left_denominator).ok_or(
        MulliganEvaluationError::ArithmeticOverflow("fraction comparison right cross product"),
    )?;
    Ok(left.cmp(&right))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{load_commander_deck, start_mulligan_game};

    fn tiny_config() -> MulliganEvaluationConfig {
        MulliganEvaluationConfig {
            rollout: MonteCarloConfig {
                root: RootSeed::from_u64(0x5236_5641_4c55_0001),
                first_world: WorldId(700),
                samples: 1,
                rollout_max_steps: 4096,
            },
            continuation_root: RootSeed::from_u64(0x5236_434f_4e54_0002),
            first_future_world: WorldId(900),
            future_hand_samples: 1,
            environment_version: "r6-test-goldfish".to_owned(),
        }
    }

    #[test]
    fn exact_value_comparison_normalizes_different_sample_counts() {
        let half = ExactWinRate {
            denominator: 2,
            t1_through_t6: [0, 1, 0, 0, 0, 0],
            losses: 1,
        };
        let same_half_later = ExactWinRate {
            denominator: 4,
            t1_through_t6: [0, 0, 2, 0, 0, 0],
            losses: 2,
        };
        let better = ExactWinRate {
            denominator: 4,
            t1_through_t6: [0, 3, 0, 0, 0, 0],
            losses: 1,
        };

        assert_eq!(
            half.objective_cmp(&same_half_later).unwrap(),
            Ordering::Greater
        );
        assert_eq!(better.objective_cmp(&half).unwrap(), Ordering::Greater);
    }

    #[test]
    fn exact_primary_gap_is_rational_and_directional() {
        let keep = ExactWinRate {
            denominator: 4,
            t1_through_t6: [1, 1, 0, 0, 0, 0],
            losses: 2,
        };
        let mull = ExactWinRate {
            denominator: 2,
            t1_through_t6: [0, 1, 0, 0, 0, 0],
            losses: 1,
        };
        let equal = ExactWinRateGap::between(&keep, &mull).unwrap();
        assert_eq!(equal.direction, WinRateGapDirection::Equal);
        assert_eq!(equal.numerator, 0);

        let stronger = ExactWinRate {
            denominator: 4,
            t1_through_t6: [3, 0, 0, 0, 0, 0],
            losses: 1,
        };
        let gap = ExactWinRateGap::between(&stronger, &mull).unwrap();
        assert_eq!(gap.direction, WinRateGapDirection::KeepHigher);
        assert_eq!(gap.numerator, 2);
        assert_eq!(gap.denominator, 8);
    }

    #[test]
    fn real_r5_evaluator_values_the_visible_initial_keep_package() {
        let deck = load_commander_deck().unwrap();
        let cards = R4CardDatabase::load().unwrap();
        let policy = DeterministicPolicy;
        let root = RootSeed::from_u64(0x5236_5445_5354_0001);
        let world = WorldId(41);
        let state = start_mulligan_game(&deck, root, world).unwrap();
        let packages =
            evaluate_keep_packages(&state, &deck, root, world, &cards, &policy, &tiny_config())
                .unwrap();

        assert_eq!(packages.len(), 1);
        assert!(packages[0].bottom_indices.is_empty());
        assert_eq!(packages[0].result.samples(), 1);
        assert_eq!(packages[0].value.denominator, 1);
    }

    #[test]
    fn continuation_cache_identity_has_no_rejected_hand_or_actual_next_world() {
        let deck = load_commander_deck().unwrap();
        let config = tiny_config();
        let pregame = PregameContext {
            seat: 2,
            gemstone_caverns_eligible: true,
        };
        let key = continuation_cache_key(MulliganStage::Three, pregame, &deck, &config);

        assert_eq!(key.stage, MulliganStage::Three);
        assert_eq!(key.pregame, pregame);
        assert_eq!(key.first_future_world, config.first_future_world);
        assert_eq!(key.future_hand_samples, config.future_hand_samples);
    }

    #[test]
    fn scaling_preserves_exact_outcome_accounting() {
        let value = ExactWinRate {
            denominator: 3,
            t1_through_t6: [1, 0, 1, 0, 0, 0],
            losses: 1,
        };
        let scaled = value.scaled_to(12).unwrap();
        assert_eq!(scaled.t1_through_t6, [4, 0, 4, 0, 0, 0]);
        assert_eq!(scaled.losses, 4);
        assert_eq!(scaled.denominator, 12);
    }
}
