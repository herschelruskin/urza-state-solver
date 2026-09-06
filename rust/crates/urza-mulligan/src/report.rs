use std::cmp::Ordering;
use std::fmt;

use urza_core::CardDefId;
use urza_policy::POLICY_VERSION;
use urza_rules::HORIZON_TURN;

use crate::{
    ExactWinRate, ExactWinRateGap, KeepPackageEvaluation, MulliganChoice,
    MulliganDecisionEvaluation, MulliganEvaluationConfig, MulliganEvaluationError, MulliganStage,
    MulliganState, ObjectivePreference, PregameContext,
};

pub const MULLIGAN_REPORT_VERSION: &str = "r6_mulligan_report_v1";
pub const MULLIGAN_UNCERTAINTY_VERSION: &str = "r6_finite_sample_resolution_v1";
pub const MULLIGAN_CONFIDENCE_CONTRACT: &str = "confidence labels describe the exact finite sampled aggregate only; they are not probabilistic confidence intervals and never participate in policy identity";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct RationalProbability {
    pub numerator: u128,
    pub denominator: u128,
}

impl RationalProbability {
    pub fn as_f64(self) -> f64 {
        if self.denominator == 0 {
            return 0.0;
        }
        self.numerator as f64 / self.denominator as f64
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CumulativeWinProbabilities {
    /// Exact sampled P(win by T1), P(win by T2), ..., P(win by T6).
    pub t1_through_t6: [RationalProbability; 6],
}

impl CumulativeWinProbabilities {
    fn from_value(value: &ExactWinRate) -> Result<Self, MulliganEvaluationError> {
        let mut cumulative = 0_u128;
        let mut by_turn = [RationalProbability {
            numerator: 0,
            denominator: value.denominator,
        }; 6];
        for (index, exact_turn_wins) in value.t1_through_t6.iter().enumerate() {
            cumulative = cumulative.checked_add(*exact_turn_wins).ok_or(
                MulliganEvaluationError::ArithmeticOverflow("report cumulative exact-turn wins"),
            )?;
            by_turn[index] = RationalProbability {
                numerator: cumulative,
                denominator: value.denominator,
            };
        }
        Ok(Self {
            t1_through_t6: by_turn,
        })
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FiniteSampleSource {
    R5HiddenWorldOutcomeUnits,
    NestedFutureHandAndR5OutcomeUnits,
}

/// Honest uncertainty metadata for the deterministic sampled value.
///
/// Recursive mull-again values reuse child continuation estimates, so treating
/// every aggregated outcome unit as an independent Bernoulli trial would make a
/// conventional confidence interval misleading. R6 therefore reports the exact
/// finite-sample resolution and its source rather than fabricating independence.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct FiniteSampleUncertainty {
    pub source: FiniteSampleSource,
    pub outcome_units: u128,
    pub one_outcome_resolution: RationalProbability,
}

impl FiniteSampleUncertainty {
    fn new(source: FiniteSampleSource, outcome_units: u128) -> Self {
        Self {
            source,
            outcome_units,
            one_outcome_resolution: RationalProbability {
                numerator: 1,
                denominator: outcome_units,
            },
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SampledDecisionConfidence {
    /// The experimental keep-3 floor leaves no legal mull-again alternative.
    ForcedKeepAtExperimentalFloor,
    /// Keep and mull-again are exactly tied under the current sampled objective.
    ExactSampleTie,
    /// The selected action strictly leads under the current finite sampled objective.
    ExactSamplePreference,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ReportedKeepPackage {
    pub bottom_indices: Vec<usize>,
    pub kept_hand: Vec<CardDefId>,
    pub known_bottom: Vec<CardDefId>,
    pub exact_value: ExactWinRate,
    pub win_by_turn: CumulativeWinProbabilities,
    pub uncertainty: FiniteSampleUncertainty,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ReportedContinuation {
    pub stage: MulliganStage,
    pub sampled_hands: u32,
    pub keep_decisions: u32,
    pub mulligan_decisions: u32,
    pub exact_value: ExactWinRate,
    pub win_by_turn: CumulativeWinProbabilities,
    pub uncertainty: FiniteSampleUncertainty,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MulliganReport {
    pub report_version: &'static str,
    pub uncertainty_version: &'static str,
    pub confidence_contract: &'static str,
    pub stage: MulliganStage,
    pub mulligan_depth: u8,
    pub current_seven: Vec<CardDefId>,
    /// Present only when this report is for the initial seven.
    pub starting_seven: Option<Vec<CardDefId>>,
    pub pregame: PregameContext,
    pub policy_version: &'static str,
    pub horizon: u8,
    pub environment_version: String,
    pub best_keep: ReportedKeepPackage,
    pub mull_again: Option<ReportedContinuation>,
    pub selected: MulliganChoice,
    pub objective_preference: ObjectivePreference,
    pub primary_win_rate_gap: Option<ExactWinRateGap>,
    pub sampled_decision_confidence: SampledDecisionConfidence,
    /// Every non-selected legal bottom package, ranked by the same objective.
    pub alternate_bottoms: Vec<ReportedKeepPackage>,
}

/// Build the stable R6 result/report surface from one completed decision evaluation.
///
/// Report construction is read-only and cannot affect keep/mull identity.
pub fn build_mulligan_report(
    state: &MulliganState<CardDefId>,
    evaluation: &MulliganDecisionEvaluation,
    config: &MulliganEvaluationConfig,
) -> Result<MulliganReport, MulliganEvaluationError> {
    let ranking = ranked_keep_indices(&evaluation.keep_packages)?;
    let best_keep = reported_keep(evaluation.best_keep())?;
    let mut alternate_bottoms = Vec::with_capacity(evaluation.keep_packages.len().saturating_sub(1));
    for index in ranking {
        if index != evaluation.best_keep_index {
            alternate_bottoms.push(reported_keep(&evaluation.keep_packages[index])?);
        }
    }

    let mull_again = evaluation
        .mull_again
        .as_ref()
        .map(|continuation| {
            Ok(ReportedContinuation {
                stage: continuation.stage,
                sampled_hands: continuation.sampled_hands,
                keep_decisions: continuation.keep_decisions,
                mulligan_decisions: continuation.mulligan_decisions,
                exact_value: continuation.value.clone(),
                win_by_turn: CumulativeWinProbabilities::from_value(&continuation.value)?,
                uncertainty: FiniteSampleUncertainty::new(
                    FiniteSampleSource::NestedFutureHandAndR5OutcomeUnits,
                    continuation.value.denominator,
                ),
            })
        })
        .transpose()?;

    let sampled_decision_confidence = match evaluation.mull_again {
        None => SampledDecisionConfidence::ForcedKeepAtExperimentalFloor,
        Some(_) if evaluation.objective_preference == ObjectivePreference::Equal => {
            SampledDecisionConfidence::ExactSampleTie
        }
        Some(_) => SampledDecisionConfidence::ExactSamplePreference,
    };

    Ok(MulliganReport {
        report_version: MULLIGAN_REPORT_VERSION,
        uncertainty_version: MULLIGAN_UNCERTAINTY_VERSION,
        confidence_contract: MULLIGAN_CONFIDENCE_CONTRACT,
        stage: state.stage(),
        mulligan_depth: stage_depth(state.stage()),
        current_seven: state.current_seven().to_vec(),
        starting_seven: (state.stage() == MulliganStage::InitialSeven)
            .then(|| state.current_seven().to_vec()),
        pregame: state.pregame(),
        policy_version: POLICY_VERSION,
        horizon: HORIZON_TURN,
        environment_version: config.environment_version.clone(),
        best_keep,
        mull_again,
        selected: evaluation.selected.clone(),
        objective_preference: evaluation.objective_preference,
        primary_win_rate_gap: evaluation.primary_win_rate_gap,
        sampled_decision_confidence,
        alternate_bottoms,
    })
}

fn reported_keep(
    package: &KeepPackageEvaluation,
) -> Result<ReportedKeepPackage, MulliganEvaluationError> {
    Ok(ReportedKeepPackage {
        bottom_indices: package.bottom_indices.clone(),
        kept_hand: package.kept_hand.clone(),
        known_bottom: package.known_bottom.clone(),
        exact_value: package.value.clone(),
        win_by_turn: CumulativeWinProbabilities::from_value(&package.value)?,
        uncertainty: FiniteSampleUncertainty::new(
            FiniteSampleSource::R5HiddenWorldOutcomeUnits,
            package.value.denominator,
        ),
    })
}

fn ranked_keep_indices(
    packages: &[KeepPackageEvaluation],
) -> Result<Vec<usize>, MulliganEvaluationError> {
    let mut ranking: Vec<usize> = Vec::with_capacity(packages.len());
    for candidate in 0..packages.len() {
        let mut insert_at = ranking.len();
        for (position, current) in ranking.iter().enumerate() {
            let ordering = packages[candidate]
                .value
                .objective_cmp(&packages[*current].value)?;
            if ordering == Ordering::Greater
                || (ordering == Ordering::Equal
                    && packages[candidate].bottom_indices < packages[*current].bottom_indices)
            {
                insert_at = position;
                break;
            }
        }
        ranking.insert(insert_at, candidate);
    }
    Ok(ranking)
}

const fn stage_depth(stage: MulliganStage) -> u8 {
    match stage {
        MulliganStage::InitialSeven => 0,
        MulliganStage::FreeSeven => 1,
        MulliganStage::Six => 2,
        MulliganStage::Five => 3,
        MulliganStage::Four => 4,
        MulliganStage::Three => 5,
    }
}

impl fmt::Display for MulliganReport {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        writeln!(
            formatter,
            "R6 mulligan report: stage={:?} depth={} seat={} caverns_eligible={}",
            self.stage,
            self.mulligan_depth,
            self.pregame.seat,
            self.pregame.gemstone_caverns_eligible
        )?;
        writeln!(formatter, "current seven: {:?}", self.current_seven)?;
        writeln!(
            formatter,
            "best keep: bottom={:?} hand={:?} known_bottom={:?}",
            self.best_keep.bottom_indices, self.best_keep.kept_hand, self.best_keep.known_bottom
        )?;
        write!(formatter, "P(win by T1..T6):")?;
        for probability in self.best_keep.win_by_turn.t1_through_t6 {
            write!(
                formatter,
                " {}/{}",
                probability.numerator, probability.denominator
            )?;
        }
        writeln!(formatter)?;
        writeln!(
            formatter,
            "selected={:?} sampled_confidence={:?} alternatives={}",
            self.selected,
            self.sampled_decision_confidence,
            self.alternate_bottoms.len()
        )?;
        if let Some(gap) = self.primary_win_rate_gap {
            writeln!(
                formatter,
                "primary win-rate gap: {:?} {}/{}",
                gap.direction, gap.numerator, gap.denominator
            )?;
        }
        if let Some(continuation) = &self.mull_again {
            writeln!(
                formatter,
                "mull-again: stage={:?} sampled_hands={} keep={} mull={} resolution=1/{}",
                continuation.stage,
                continuation.sampled_hands,
                continuation.keep_decisions,
                continuation.mulligan_decisions,
                continuation.uncertainty.outcome_units
            )?;
        }
        write!(formatter, "{}", self.confidence_contract)
    }
}

#[cfg(test)]
mod tests {
    use urza_mc::MonteCarloResult;
    use urza_rng::{RootSeed, WorldId};

    use super::*;
    use crate::{ContinuationEvaluation, ExactWinRateGap, WinRateGapDirection};

    fn package(bottom: Vec<usize>, wins: [u128; 6], losses: u128) -> KeepPackageEvaluation {
        let denominator = wins.iter().copied().sum::<u128>() + losses;
        KeepPackageEvaluation {
            bottom_indices: bottom.clone(),
            kept_hand: vec![CardDefId(1), CardDefId(2), CardDefId(3)],
            known_bottom: bottom
                .iter()
                .map(|index| CardDefId(u16::try_from(*index + 10).unwrap()))
                .collect(),
            value: ExactWinRate {
                denominator,
                t1_through_t6: wins,
                losses,
            },
            result: MonteCarloResult {
                outcomes: Vec::new(),
                win_distribution: Default::default(),
                family_wins: Vec::new(),
            },
        }
    }

    #[test]
    fn report_exposes_cumulative_probabilities_resolution_gap_and_all_alternates() {
        let pregame = PregameContext {
            seat: 2,
            gemstone_caverns_eligible: true,
        };
        let state = MulliganState::at_stage(
            MulliganStage::Three,
            (1_u16..=7).map(CardDefId).collect(),
            pregame,
        )
        .unwrap();
        let keep_packages = vec![
            package(vec![0, 1, 2, 3], [1, 1, 0, 0, 0, 0], 2),
            package(vec![0, 1, 2, 4], [0, 1, 0, 0, 0, 0], 3),
            package(vec![0, 1, 2, 5], [1, 0, 0, 0, 0, 0], 3),
        ];
        let evaluation = MulliganDecisionEvaluation {
            stage: MulliganStage::Three,
            pregame,
            keep_packages,
            best_keep_index: 0,
            mull_again: Some(ContinuationEvaluation {
                stage: MulliganStage::Three,
                sampled_hands: 2,
                value: ExactWinRate {
                    denominator: 8,
                    t1_through_t6: [2, 1, 0, 0, 0, 0],
                    losses: 5,
                },
                keep_decisions: 1,
                mulligan_decisions: 1,
            }),
            objective_preference: ObjectivePreference::Keep,
            primary_win_rate_gap: Some(ExactWinRateGap {
                direction: WinRateGapDirection::KeepHigher,
                numerator: 4,
                denominator: 32,
            }),
            selected: MulliganChoice::Keep {
                bottom_indices: vec![0, 1, 2, 3],
            },
        };
        let config = MulliganEvaluationConfig {
            rollout: urza_mc::MonteCarloConfig {
                root: RootSeed::from_u64(1),
                first_world: WorldId(0),
                samples: 4,
                rollout_max_steps: 1,
            },
            continuation_root: RootSeed::from_u64(2),
            first_future_world: WorldId(10),
            future_hand_samples: 2,
            environment_version: "report-test".to_owned(),
        };

        let report = build_mulligan_report(&state, &evaluation, &config).unwrap();
        assert_eq!(report.mulligan_depth, 5);
        assert_eq!(report.starting_seven, None);
        assert_eq!(report.best_keep.win_by_turn.t1_through_t6[0].numerator, 1);
        assert_eq!(report.best_keep.win_by_turn.t1_through_t6[1].numerator, 2);
        assert_eq!(report.best_keep.uncertainty.one_outcome_resolution.denominator, 4);
        assert_eq!(report.alternate_bottoms.len(), 2);
        assert_eq!(report.alternate_bottoms[0].bottom_indices, vec![0, 1, 2, 5]);
        assert_eq!(
            report.sampled_decision_confidence,
            SampledDecisionConfidence::ExactSamplePreference
        );
        assert!(report.to_string().contains("P(win by T1..T6)"));
        assert!(report.to_string().contains(MULLIGAN_CONFIDENCE_CONTRACT));
    }

    #[test]
    fn initial_report_preserves_starting_seven() {
        let pregame = PregameContext {
            seat: 1,
            gemstone_caverns_eligible: false,
        };
        let seven: Vec<_> = (20_u16..=26).map(CardDefId).collect();
        let state = MulliganState::initial(seven.clone(), pregame).unwrap();
        let keep = package(Vec::new(), [0, 0, 1, 0, 0, 0], 0);
        let evaluation = MulliganDecisionEvaluation {
            stage: MulliganStage::InitialSeven,
            pregame,
            keep_packages: vec![keep],
            best_keep_index: 0,
            mull_again: None,
            objective_preference: ObjectivePreference::Keep,
            primary_win_rate_gap: None,
            selected: MulliganChoice::Keep {
                bottom_indices: Vec::new(),
            },
        };
        let config = MulliganEvaluationConfig::default();
        let report = build_mulligan_report(&state, &evaluation, &config).unwrap();
        assert_eq!(report.starting_seven, Some(seven));
    }
}
