use std::cmp::Ordering;
use std::collections::{BTreeMap, btree_map::Entry};
use std::error::Error;
use std::fmt;

use urza_rng::{RNG_SCHEME_VERSION, RootSeed, WorldId};

use crate::{
    EVALUATED_HAND_RECORD_VERSION, EvaluatedHandRecord, HAND_FEATURE_SCHEMA_VERSION,
    HandFeatureVector, INTERPRETATION_ONLY_CONTRACT, INTERPRETATION_ROLE_VERSION,
    InterpretationCatalog, InterpretationError, MULLIGAN_REPORT_VERSION, MulliganChoice,
    MulliganReport, MulliganStage, SampledDecisionConfidence,
};

pub const EVALUATED_HAND_CORPUS_VERSION: &str = "r7_evaluated_hand_corpus_v1";
pub const FEATURE_NORMALIZATION_VERSION: &str = "r7_per_card_milli_v1";
pub const FEATURE_DISTANCE_VERSION: &str = "r7_unweighted_l1_v1";
pub const UNLABELED_GROUPING_VERSION: &str = "r7_stage_single_link_v1";
pub const NORMALIZED_FEATURE_SCALE: u16 = 1_000;
pub const DISTANCE_AXIS_COUNT: usize = 15;
pub const MAX_FEATURE_DISTANCE_MILLI: u32 =
    NORMALIZED_FEATURE_SCALE as u32 * DISTANCE_AXIS_COUNT as u32;

/// Axis order is part of the versioned distance contract.
///
/// `r4_rules_supported_count` is deliberately omitted because it is exactly
/// redundant with `unmodeled_by_r4_count` for a valid feature vector.
pub const DISTANCE_AXIS_NAMES: [&str; DISTANCE_AXIS_COUNT] = [
    "land_capable",
    "artifact",
    "creature",
    "instant",
    "sorcery",
    "modal_dfc",
    "x_cost",
    "recognized_mana_source",
    "recognized_blue_mana_source",
    "recognized_multi_mana_source",
    "recognized_search_source",
    "recognized_engine_piece",
    "recognized_utility_piece",
    "recognized_targeted_effect",
    "unmodeled_by_r4",
];

/// Reproducible identity for one evaluated current-seven decision.
///
/// The sample identity records actual opening-game provenance. It is downstream
/// dataset identity only and is never a policy/value/cache key.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct EvaluatedHandSampleId {
    pub opening_root: RootSeed,
    pub opening_world: WorldId,
    pub stage: MulliganStage,
}

impl EvaluatedHandSampleId {
    pub const fn new(opening_root: RootSeed, opening_world: WorldId, stage: MulliganStage) -> Self {
        Self {
            opening_root,
            opening_world,
            stage,
        }
    }
}

impl Ord for EvaluatedHandSampleId {
    fn cmp(&self, other: &Self) -> Ordering {
        self.opening_root
            .0
            .cmp(&other.opening_root.0)
            .then_with(|| self.opening_world.0.cmp(&other.opening_world.0))
            .then_with(|| self.stage.cmp(&other.stage))
    }
}

impl PartialOrd for EvaluatedHandSampleId {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct EvaluatedHandCorpusConfiguration {
    pub record_version: &'static str,
    pub role_metadata_version: &'static str,
    pub feature_schema_version: &'static str,
    pub source_report_version: &'static str,
    pub policy_version: &'static str,
    pub horizon: u8,
    pub environment_version: String,
}

impl EvaluatedHandCorpusConfiguration {
    fn from_record(record: &EvaluatedHandRecord) -> Self {
        Self {
            record_version: record.record_version,
            role_metadata_version: record.role_metadata_version,
            feature_schema_version: record.feature_schema_version,
            source_report_version: record.source_report_version,
            policy_version: record.policy_version,
            horizon: record.horizon,
            environment_version: record.environment_version.clone(),
        }
    }
}

/// Deterministically ordered, configuration-homogeneous R7 teacher corpus.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct EvaluatedHandCorpus {
    pub corpus_version: &'static str,
    pub rng_scheme_version: &'static str,
    configuration: Option<EvaluatedHandCorpusConfiguration>,
    entries: BTreeMap<EvaluatedHandSampleId, EvaluatedHandRecord>,
}

impl Default for EvaluatedHandCorpus {
    fn default() -> Self {
        Self::new()
    }
}

impl EvaluatedHandCorpus {
    pub fn new() -> Self {
        Self {
            corpus_version: EVALUATED_HAND_CORPUS_VERSION,
            rng_scheme_version: RNG_SCHEME_VERSION,
            configuration: None,
            entries: BTreeMap::new(),
        }
    }

    pub fn len(&self) -> usize {
        self.entries.len()
    }

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    pub fn configuration(&self) -> Option<&EvaluatedHandCorpusConfiguration> {
        self.configuration.as_ref()
    }

    pub fn get(&self, sample: EvaluatedHandSampleId) -> Option<&EvaluatedHandRecord> {
        self.entries.get(&sample)
    }

    pub fn entries(&self) -> impl Iterator<Item = (&EvaluatedHandSampleId, &EvaluatedHandRecord)> {
        self.entries.iter()
    }

    pub fn insert_report(
        &mut self,
        sample: EvaluatedHandSampleId,
        report: &MulliganReport,
        interpretation: &InterpretationCatalog,
    ) -> Result<(), CorpusError> {
        if sample.stage != report.stage {
            return Err(CorpusError::StageMismatch {
                sample_stage: sample.stage,
                record_stage: report.stage,
            });
        }
        let record = interpretation
            .evaluated_hand_record(report)
            .map_err(CorpusError::Interpretation)?;
        self.insert_record(sample, record, interpretation)
    }

    /// Insert an already materialized record while revalidating the version and
    /// feature boundary against the current interpretation catalog.
    pub fn insert_record(
        &mut self,
        sample: EvaluatedHandSampleId,
        record: EvaluatedHandRecord,
        interpretation: &InterpretationCatalog,
    ) -> Result<(), CorpusError> {
        validate_record(sample, &record, interpretation)?;
        if let Entry::Occupied(_) = self.entries.entry(sample) {
            return Err(CorpusError::DuplicateSample(sample));
        }

        let actual_configuration = EvaluatedHandCorpusConfiguration::from_record(&record);
        if let Some(expected) = &self.configuration {
            if expected != &actual_configuration {
                return Err(CorpusError::IncompatibleConfiguration {
                    expected: expected.clone(),
                    actual: actual_configuration,
                });
            }
        } else {
            self.configuration = Some(actual_configuration);
        }

        self.entries.insert(sample, record);
        Ok(())
    }

    /// Reference, transparent grouping pass for cluster inspection.
    ///
    /// Entries are connected when they are from the same mulligan stage and
    /// their normalized current-seven feature distance is at most the supplied
    /// radius. Connected components therefore implement deterministic
    /// single-link grouping. This is intentionally simple and inspectable; it
    /// is not a learned classifier and does not feed recommendations back into
    /// R6/R5.
    pub fn unlabeled_clusters(
        &self,
        config: UnlabeledGroupingConfig,
    ) -> Result<Vec<UnlabeledClusterSummary>, CorpusError> {
        if config.max_l1_milli > MAX_FEATURE_DISTANCE_MILLI {
            return Err(CorpusError::InvalidGroupingRadius(config.max_l1_milli));
        }

        let samples: Vec<_> = self
            .entries
            .iter()
            .map(|(sample, record)| {
                normalize_hand_features(&record.current_features)
                    .map(|features| (*sample, record, features))
            })
            .collect::<Result<_, _>>()?;
        let mut assigned = vec![false; samples.len()];
        let mut clusters = Vec::new();
        let mut start = 0_usize;

        while start < samples.len() {
            if assigned[start] {
                start += 1;
                continue;
            }

            assigned[start] = true;
            let mut component = vec![start];
            let mut cursor = 0_usize;
            while cursor < component.len() {
                let current = component[cursor];
                let current_stage = samples[current].1.stage;
                let current_features = samples[current].2;
                for (candidate, candidate_sample) in samples.iter().enumerate() {
                    if assigned[candidate] || candidate_sample.1.stage != current_stage {
                        continue;
                    }
                    if hand_feature_distance(current_features, candidate_sample.2).l1_milli
                        <= config.max_l1_milli
                    {
                        assigned[candidate] = true;
                        component.push(candidate);
                    }
                }
                cursor += 1;
            }
            component.sort_unstable();
            clusters.push(summarize_component(
                u32::try_from(clusters.len()).map_err(|_| CorpusError::TooManyClusters)?,
                &component,
                &samples,
            )?);
            start += 1;
        }

        Ok(clusters)
    }
}

fn validate_record(
    sample: EvaluatedHandSampleId,
    record: &EvaluatedHandRecord,
    interpretation: &InterpretationCatalog,
) -> Result<(), CorpusError> {
    if sample.stage != record.stage {
        return Err(CorpusError::StageMismatch {
            sample_stage: sample.stage,
            record_stage: record.stage,
        });
    }
    if record.record_version != EVALUATED_HAND_RECORD_VERSION {
        return Err(CorpusError::UnexpectedVersion("record"));
    }
    if record.role_metadata_version != INTERPRETATION_ROLE_VERSION
        || record.role_metadata_version != interpretation.version
    {
        return Err(CorpusError::UnexpectedVersion("role metadata"));
    }
    if record.feature_schema_version != HAND_FEATURE_SCHEMA_VERSION {
        return Err(CorpusError::UnexpectedVersion("feature schema"));
    }
    if record.source_report_version != MULLIGAN_REPORT_VERSION {
        return Err(CorpusError::UnexpectedVersion("source report"));
    }
    if record.interpretation_contract != INTERPRETATION_ONLY_CONTRACT {
        return Err(CorpusError::UnexpectedVersion("interpretation contract"));
    }
    if record.current_seven.len() != 7 {
        return Err(CorpusError::InvalidCurrentSevenSize(
            record.current_seven.len(),
        ));
    }
    let expected_keep_size = record.stage.kept_cards();
    if record.recommended_kept_hand.len() != expected_keep_size {
        return Err(CorpusError::InvalidRecommendedKeepSize {
            stage: record.stage,
            expected: expected_keep_size,
            actual: record.recommended_kept_hand.len(),
        });
    }

    let current_features = interpretation
        .features_for_cards(&record.current_seven)
        .map_err(CorpusError::Interpretation)?;
    if current_features != record.current_features {
        return Err(CorpusError::FeatureDrift("current seven"));
    }
    let keep_features = interpretation
        .features_for_cards(&record.recommended_kept_hand)
        .map_err(CorpusError::Interpretation)?;
    if keep_features != record.recommended_keep_features {
        return Err(CorpusError::FeatureDrift("recommended keep"));
    }
    Ok(())
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct NormalizedHandFeatures {
    /// Per-card rates in thousandths, in `DISTANCE_AXIS_NAMES` order.
    pub per_card_milli: [u16; DISTANCE_AXIS_COUNT],
}

pub fn normalize_hand_features(
    features: &HandFeatureVector,
) -> Result<NormalizedHandFeatures, CorpusError> {
    if features.card_count == 0 {
        return Err(CorpusError::EmptyFeatureVector);
    }
    let covered = features
        .r4_rules_supported_count
        .checked_add(features.unmodeled_by_r4_count)
        .ok_or(CorpusError::InvalidCoverageCounts)?;
    if covered != features.card_count {
        return Err(CorpusError::InvalidCoverageCounts);
    }

    let counts = feature_counts(features);
    let mut normalized = [0_u16; DISTANCE_AXIS_COUNT];
    for (index, count) in counts.into_iter().enumerate() {
        if count > features.card_count {
            return Err(CorpusError::InvalidFeatureCount {
                axis: DISTANCE_AXIS_NAMES[index],
                count,
                card_count: features.card_count,
            });
        }
        let numerator = u32::from(count) * u32::from(NORMALIZED_FEATURE_SCALE)
            + u32::from(features.card_count / 2);
        normalized[index] = u16::try_from(numerator / u32::from(features.card_count))
            .expect("normalized feature cannot exceed scale");
    }
    Ok(NormalizedHandFeatures {
        per_card_milli: normalized,
    })
}

fn feature_counts(features: &HandFeatureVector) -> [u16; DISTANCE_AXIS_COUNT] {
    [
        features.land_capable_count,
        features.artifact_count,
        features.creature_count,
        features.instant_count,
        features.sorcery_count,
        features.modal_dfc_count,
        features.x_cost_count,
        features.recognized_mana_source_count,
        features.recognized_blue_mana_source_count,
        features.recognized_multi_mana_source_count,
        features.recognized_search_source_count,
        features.recognized_engine_piece_count,
        features.recognized_utility_piece_count,
        features.recognized_targeted_effect_count,
        features.unmodeled_by_r4_count,
    ]
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct FeatureDistance {
    pub l1_milli: u32,
    pub differing_axes: u8,
}

pub fn hand_feature_distance(
    left: NormalizedHandFeatures,
    right: NormalizedHandFeatures,
) -> FeatureDistance {
    let mut l1_milli = 0_u32;
    let mut differing_axes = 0_u8;
    for (left_axis, right_axis) in left.per_card_milli.into_iter().zip(right.per_card_milli) {
        let difference = left_axis.abs_diff(right_axis);
        l1_milli += u32::from(difference);
        differing_axes += u8::from(difference != 0);
    }
    FeatureDistance {
        l1_milli,
        differing_axes,
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct UnlabeledGroupingConfig {
    pub max_l1_milli: u32,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct UnlabeledClusterSummary {
    pub grouping_version: &'static str,
    pub feature_normalization_version: &'static str,
    pub feature_distance_version: &'static str,
    pub cluster_ordinal: u32,
    pub stage: MulliganStage,
    pub member_count: u32,
    pub members: Vec<EvaluatedHandSampleId>,
    pub medoid: EvaluatedHandSampleId,
    pub medoid_features: NormalizedHandFeatures,
    pub max_distance_to_medoid: FeatureDistance,
    pub keep_recommendations: u32,
    pub mulligan_recommendations: u32,
    pub exact_sample_ties: u32,
    pub forced_floor_decisions: u32,
}

fn summarize_component(
    cluster_ordinal: u32,
    component: &[usize],
    samples: &[(
        EvaluatedHandSampleId,
        &EvaluatedHandRecord,
        NormalizedHandFeatures,
    )],
) -> Result<UnlabeledClusterSummary, CorpusError> {
    let first = *component.first().ok_or(CorpusError::EmptyCluster)?;
    let stage = samples[first].1.stage;
    let medoid_index = component
        .iter()
        .copied()
        .min_by_key(|candidate| {
            let total_distance: u64 = component
                .iter()
                .copied()
                .map(|other| {
                    u64::from(
                        hand_feature_distance(samples[*candidate].2, samples[other].2).l1_milli,
                    )
                })
                .sum();
            (total_distance, samples[*candidate].0)
        })
        .ok_or(CorpusError::EmptyCluster)?;
    let medoid = samples[medoid_index].0;
    let medoid_features = samples[medoid_index].2;
    let max_distance_to_medoid = component
        .iter()
        .copied()
        .map(|member| hand_feature_distance(medoid_features, samples[member].2))
        .max_by_key(|distance| (distance.l1_milli, distance.differing_axes))
        .unwrap_or(FeatureDistance {
            l1_milli: 0,
            differing_axes: 0,
        });

    let mut keep_recommendations = 0_u32;
    let mut mulligan_recommendations = 0_u32;
    let mut exact_sample_ties = 0_u32;
    let mut forced_floor_decisions = 0_u32;
    let mut members = Vec::with_capacity(component.len());
    for member in component.iter().copied() {
        let (sample, record, _) = &samples[member];
        members.push(*sample);
        match record.recommended_action {
            MulliganChoice::Keep { .. } => keep_recommendations += 1,
            MulliganChoice::Mulligan => mulligan_recommendations += 1,
        }
        exact_sample_ties += u32::from(
            record.sampled_decision_confidence == SampledDecisionConfidence::ExactSampleTie,
        );
        forced_floor_decisions += u32::from(
            record.sampled_decision_confidence
                == SampledDecisionConfidence::ForcedKeepAtExperimentalFloor,
        );
    }

    Ok(UnlabeledClusterSummary {
        grouping_version: UNLABELED_GROUPING_VERSION,
        feature_normalization_version: FEATURE_NORMALIZATION_VERSION,
        feature_distance_version: FEATURE_DISTANCE_VERSION,
        cluster_ordinal,
        stage,
        member_count: u32::try_from(component.len()).map_err(|_| CorpusError::ClusterTooLarge)?,
        members,
        medoid,
        medoid_features,
        max_distance_to_medoid,
        keep_recommendations,
        mulligan_recommendations,
        exact_sample_ties,
        forced_floor_decisions,
    })
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum CorpusError {
    Interpretation(InterpretationError),
    StageMismatch {
        sample_stage: MulliganStage,
        record_stage: MulliganStage,
    },
    DuplicateSample(EvaluatedHandSampleId),
    UnexpectedVersion(&'static str),
    InvalidCurrentSevenSize(usize),
    InvalidRecommendedKeepSize {
        stage: MulliganStage,
        expected: usize,
        actual: usize,
    },
    FeatureDrift(&'static str),
    IncompatibleConfiguration {
        expected: EvaluatedHandCorpusConfiguration,
        actual: EvaluatedHandCorpusConfiguration,
    },
    EmptyFeatureVector,
    InvalidCoverageCounts,
    InvalidFeatureCount {
        axis: &'static str,
        count: u16,
        card_count: u16,
    },
    InvalidGroupingRadius(u32),
    EmptyCluster,
    ClusterTooLarge,
    TooManyClusters,
}

impl fmt::Display for CorpusError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Interpretation(error) => write!(formatter, "{error}"),
            Self::StageMismatch {
                sample_stage,
                record_stage,
            } => write!(
                formatter,
                "sample stage {sample_stage:?} does not match record stage {record_stage:?}"
            ),
            Self::DuplicateSample(sample) => write!(formatter, "duplicate sample {sample:?}"),
            Self::UnexpectedVersion(field) => write!(formatter, "unexpected {field} version"),
            Self::InvalidCurrentSevenSize(actual) => {
                write!(
                    formatter,
                    "current mulligan hand must contain seven cards, got {actual}"
                )
            }
            Self::InvalidRecommendedKeepSize {
                stage,
                expected,
                actual,
            } => write!(
                formatter,
                "stage {stage:?} keep must contain {expected} cards, got {actual}"
            ),
            Self::FeatureDrift(which) => {
                write!(
                    formatter,
                    "stored {which} features do not match card identities"
                )
            }
            Self::IncompatibleConfiguration { .. } => {
                write!(
                    formatter,
                    "corpus records must share one evaluation configuration"
                )
            }
            Self::EmptyFeatureVector => {
                write!(formatter, "cannot normalize an empty feature vector")
            }
            Self::InvalidCoverageCounts => write!(
                formatter,
                "R4-supported and unmodeled counts must partition the hand"
            ),
            Self::InvalidFeatureCount {
                axis,
                count,
                card_count,
            } => write!(
                formatter,
                "feature axis {axis} has count {count} above card count {card_count}"
            ),
            Self::InvalidGroupingRadius(radius) => write!(
                formatter,
                "grouping radius {radius} exceeds maximum feature distance {MAX_FEATURE_DISTANCE_MILLI}"
            ),
            Self::EmptyCluster => write!(formatter, "internal grouping produced an empty cluster"),
            Self::ClusterTooLarge => write!(formatter, "cluster member count exceeds u32"),
            Self::TooManyClusters => write!(formatter, "cluster count exceeds u32"),
        }
    }
}

impl Error for CorpusError {}

#[cfg(test)]
mod tests {
    use urza_cards::R4CardDatabase;
    use urza_core::CardDefId;

    use super::*;
    use crate::{ExactWinRate, ObjectivePreference, PregameContext};

    fn exact_loss() -> ExactWinRate {
        ExactWinRate {
            denominator: 1,
            t1_through_t6: [0; 6],
            losses: 1,
        }
    }

    fn record_for_cards(
        interpretation: &InterpretationCatalog,
        cards: Vec<CardDefId>,
        stage: MulliganStage,
        environment_version: &str,
        recommended_action: MulliganChoice,
    ) -> EvaluatedHandRecord {
        let features = interpretation.features_for_cards(&cards).unwrap();
        EvaluatedHandRecord {
            record_version: EVALUATED_HAND_RECORD_VERSION,
            role_metadata_version: INTERPRETATION_ROLE_VERSION,
            feature_schema_version: HAND_FEATURE_SCHEMA_VERSION,
            interpretation_contract: INTERPRETATION_ONLY_CONTRACT,
            source_report_version: MULLIGAN_REPORT_VERSION,
            stage,
            mulligan_depth: match stage {
                MulliganStage::InitialSeven => 0,
                MulliganStage::FreeSeven => 1,
                MulliganStage::Six => 2,
                MulliganStage::Five => 3,
                MulliganStage::Four => 4,
                MulliganStage::Three => 5,
            },
            pregame: PregameContext {
                seat: 1,
                gemstone_caverns_eligible: false,
            },
            policy_version: "test-policy",
            horizon: 6,
            environment_version: environment_version.to_owned(),
            current_seven: cards.clone(),
            current_features: features,
            recommended_kept_hand: cards,
            recommended_keep_features: features,
            recommended_action,
            best_keep_value: exact_loss(),
            mull_again_value: Some(exact_loss()),
            objective_preference: ObjectivePreference::Equal,
            primary_win_rate_gap: None,
            sampled_decision_confidence: SampledDecisionConfidence::ExactSampleTie,
        }
    }

    #[test]
    fn corpus_is_ordered_by_explicit_seed_world_stage_provenance() {
        let interpretation = InterpretationCatalog::load().unwrap();
        let cards = R4CardDatabase::load().unwrap();
        let island = cards.card_id_by_name("Island").unwrap();
        let record = record_for_cards(
            &interpretation,
            vec![island; 7],
            MulliganStage::InitialSeven,
            "corpus-test",
            MulliganChoice::Keep {
                bottom_indices: Vec::new(),
            },
        );
        let later = EvaluatedHandSampleId::new(
            RootSeed::from_u64(2),
            WorldId(0),
            MulliganStage::InitialSeven,
        );
        let earlier = EvaluatedHandSampleId::new(
            RootSeed::from_u64(1),
            WorldId(9),
            MulliganStage::InitialSeven,
        );
        let mut corpus = EvaluatedHandCorpus::new();
        corpus
            .insert_record(later, record.clone(), &interpretation)
            .unwrap();
        corpus
            .insert_record(earlier, record, &interpretation)
            .unwrap();

        let ordered: Vec<_> = corpus.entries().map(|(sample, _)| *sample).collect();
        let mut expected = vec![later, earlier];
        expected.sort();
        assert_eq!(ordered, expected);
        assert_eq!(corpus.rng_scheme_version, RNG_SCHEME_VERSION);
    }

    #[test]
    fn corpus_rejects_duplicate_samples_and_mixed_teacher_configurations() {
        let interpretation = InterpretationCatalog::load().unwrap();
        let cards = R4CardDatabase::load().unwrap();
        let island = cards.card_id_by_name("Island").unwrap();
        let sample = EvaluatedHandSampleId::new(
            RootSeed::from_u64(3),
            WorldId(4),
            MulliganStage::InitialSeven,
        );
        let first = record_for_cards(
            &interpretation,
            vec![island; 7],
            MulliganStage::InitialSeven,
            "environment-a",
            MulliganChoice::Keep {
                bottom_indices: Vec::new(),
            },
        );
        let second = record_for_cards(
            &interpretation,
            vec![island; 7],
            MulliganStage::InitialSeven,
            "environment-b",
            MulliganChoice::Keep {
                bottom_indices: Vec::new(),
            },
        );
        let mut corpus = EvaluatedHandCorpus::new();
        corpus
            .insert_record(sample, first.clone(), &interpretation)
            .unwrap();
        assert_eq!(
            corpus.insert_record(sample, first, &interpretation),
            Err(CorpusError::DuplicateSample(sample))
        );
        let other_sample = EvaluatedHandSampleId::new(
            RootSeed::from_u64(3),
            WorldId(5),
            MulliganStage::InitialSeven,
        );
        assert!(matches!(
            corpus.insert_record(other_sample, second, &interpretation),
            Err(CorpusError::IncompatibleConfiguration { .. })
        ));
    }

    #[test]
    fn per_card_integer_normalization_and_l1_distance_are_deterministic() {
        let features = HandFeatureVector {
            card_count: 7,
            land_capable_count: 3,
            r4_rules_supported_count: 6,
            unmodeled_by_r4_count: 1,
            ..HandFeatureVector::default()
        };
        let normalized = normalize_hand_features(&features).unwrap();
        assert_eq!(normalized.per_card_milli[0], 429);
        assert_eq!(normalized.per_card_milli[14], 143);

        let other = normalize_hand_features(&HandFeatureVector {
            card_count: 7,
            land_capable_count: 4,
            r4_rules_supported_count: 6,
            unmodeled_by_r4_count: 1,
            ..HandFeatureVector::default()
        })
        .unwrap();
        assert_eq!(hand_feature_distance(normalized, other).l1_milli, 142);
        assert_eq!(hand_feature_distance(other, normalized).l1_milli, 142);
        assert_eq!(DISTANCE_AXIS_NAMES.len(), DISTANCE_AXIS_COUNT);
    }

    #[test]
    fn transparent_single_link_grouping_is_stage_local_and_unlabeled() {
        let interpretation = InterpretationCatalog::load().unwrap();
        let cards = R4CardDatabase::load().unwrap();
        let island = cards.card_id_by_name("Island").unwrap();
        let tomb = cards.card_id_by_name("Ancient Tomb").unwrap();
        let pact = cards.card_id_by_name("Pact of Negation").unwrap();

        let all_islands = record_for_cards(
            &interpretation,
            vec![island; 7],
            MulliganStage::InitialSeven,
            "group-test",
            MulliganChoice::Keep {
                bottom_indices: Vec::new(),
            },
        );
        let mut six_islands_and_tomb = vec![island; 6];
        six_islands_and_tomb.push(tomb);
        let near = record_for_cards(
            &interpretation,
            six_islands_and_tomb,
            MulliganStage::InitialSeven,
            "group-test",
            MulliganChoice::Keep {
                bottom_indices: Vec::new(),
            },
        );
        let far = record_for_cards(
            &interpretation,
            vec![pact; 7],
            MulliganStage::InitialSeven,
            "group-test",
            MulliganChoice::Mulligan,
        );
        let same_shape_other_stage = record_for_cards(
            &interpretation,
            vec![island; 7],
            MulliganStage::FreeSeven,
            "group-test",
            MulliganChoice::Keep {
                bottom_indices: Vec::new(),
            },
        );

        let mut corpus = EvaluatedHandCorpus::new();
        for (world, stage, record) in [
            (0, MulliganStage::InitialSeven, all_islands),
            (1, MulliganStage::InitialSeven, near),
            (2, MulliganStage::InitialSeven, far),
            (3, MulliganStage::FreeSeven, same_shape_other_stage),
        ] {
            corpus
                .insert_record(
                    EvaluatedHandSampleId::new(RootSeed::from_u64(99), WorldId(world), stage),
                    record,
                    &interpretation,
                )
                .unwrap();
        }

        let clusters = corpus
            .unlabeled_clusters(UnlabeledGroupingConfig { max_l1_milli: 300 })
            .unwrap();
        assert_eq!(clusters.len(), 3);
        assert_eq!(clusters[0].stage, MulliganStage::InitialSeven);
        assert_eq!(clusters[0].member_count, 2);
        assert_eq!(clusters[0].keep_recommendations, 2);
        assert_eq!(clusters[0].mulligan_recommendations, 0);
        assert_eq!(clusters[1].member_count, 1);
        assert_eq!(clusters[1].mulligan_recommendations, 1);
        assert_eq!(clusters[2].stage, MulliganStage::FreeSeven);
        assert_eq!(clusters[2].member_count, 1);
        assert_eq!(clusters[0].grouping_version, UNLABELED_GROUPING_VERSION);
    }
}
