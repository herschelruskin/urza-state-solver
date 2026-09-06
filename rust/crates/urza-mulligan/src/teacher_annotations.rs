use std::collections::BTreeMap;
use std::error::Error;
use std::fmt;

use urza_cards::R4CardDatabase;
use urza_core::CardDefId;
use urza_rng::{RootSeed, WorldId};
use urza_rollout::RolloutStop;

use crate::{
    EvaluatedHandCorpus, EvaluatedHandSampleId, KeptHand, OpeningError, TeacherSearchConfig,
    TeacherSearchError, TeacherSearchResult, bridge_kept_hand, evaluate_teacher, load_commander_deck,
};

pub const R7_TEACHER_KEEP_ANNOTATION_VERSION: &str = "r7_teacher_keep_annotation_v1";
pub const R7_TEACHER_KEEP_ANNOTATION_BOUNDARY: &str =
    "R7 teacher annotations are a read-only sidecar over already-evaluated R6 corpus records. \
     For each record they evaluate only the R6-selected best keep package under the bounded public-\
     belief teacher. They do not re-rank London bottoms, evaluate the mull-again continuation, alter \
     the recorded R6 KEEP/MULL recommendation, feed interpretation features into gameplay, or \
     participate in R5/R6 cache or policy identity.";
pub const R7_TEACHER_SIDECAR_SMOKE_PROFILE_VERSION: &str = "r7_teacher_sidecar_smoke_1x2_v1";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TeacherKeepUnresolved {
    LeafStepLimit { world: WorldId },
    LeafNoCandidate { world: WorldId },
    AllCandidateBranchesIncomplete { candidate_count: usize },
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum TeacherKeepResolution {
    Resolved(TeacherSearchResult),
    Unresolved(TeacherKeepUnresolved),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TeacherKeepAnnotation {
    pub annotation_version: &'static str,
    pub boundary: &'static str,
    pub sample: EvaluatedHandSampleId,
    pub source_record_version: &'static str,
    pub source_policy_version: &'static str,
    pub source_recommended_action: crate::MulliganChoice,
    pub kept_hand: Vec<CardDefId>,
    pub known_bottom: Vec<CardDefId>,
    pub search_config: TeacherSearchConfig,
    pub resolution: TeacherKeepResolution,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct TeacherAnnotationStats {
    pub records_attempted: u32,
    pub resolved_records: u32,
    pub unresolved_records: u32,
    pub resolved_positive_records: u32,
    pub resolved_zero_records: u32,
    pub allocated_teacher_worlds: u64,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TeacherAnnotatedCorpus {
    pub annotation_version: &'static str,
    pub boundary: &'static str,
    pub source_corpus_version: &'static str,
    pub base_search_config: TeacherSearchConfig,
    pub stats: TeacherAnnotationStats,
    annotations: BTreeMap<EvaluatedHandSampleId, TeacherKeepAnnotation>,
}

impl TeacherAnnotatedCorpus {
    pub fn len(&self) -> usize {
        self.annotations.len()
    }

    pub fn is_empty(&self) -> bool {
        self.annotations.is_empty()
    }

    pub fn get(&self, sample: &EvaluatedHandSampleId) -> Option<&TeacherKeepAnnotation> {
        self.annotations.get(sample)
    }

    pub fn entries(
        &self,
    ) -> impl Iterator<Item = (&EvaluatedHandSampleId, &TeacherKeepAnnotation)> {
        self.annotations.iter()
    }
}

pub fn r7_teacher_sidecar_smoke_search_config() -> TeacherSearchConfig {
    TeacherSearchConfig {
        root: RootSeed::from_u64(0x5237_5349_4445_0001),
        first_world: WorldId(920_000),
        samples: 1,
        max_choice_depth: 2,
        max_teacher_steps: 6,
        max_candidates_per_group: 6,
        leaf_rollout_max_steps: 4096,
    }
}

/// Annotate each existing R6 corpus record with the bounded-teacher value of
/// that record's already-selected best keep package.
///
/// Teacher hidden-world ranges are deterministic and non-overlapping across
/// records: record ordinal `i` receives `[base + i*samples, base + (i+1)*samples)`.
pub fn annotate_r6_keep_packages(
    corpus: &EvaluatedHandCorpus,
    base_search_config: TeacherSearchConfig,
) -> Result<TeacherAnnotatedCorpus, TeacherAnnotationError> {
    if base_search_config.samples == 0 {
        return Err(TeacherAnnotationError::InvalidConfig(
            "teacher samples must be at least one",
        ));
    }

    let deck = load_commander_deck()?;
    let cards = R4CardDatabase::load()
        .map_err(|error| TeacherAnnotationError::Setup(format!("R4 card database failed: {error}")))?;
    let mut annotations = BTreeMap::new();
    let mut stats = TeacherAnnotationStats::default();

    for (ordinal, (sample, record)) in corpus.entries().enumerate() {
        let search_config = search_config_for_ordinal(base_search_config, ordinal)?;
        let known_bottom = derive_known_bottom(
            &record.current_seven,
            &record.recommended_kept_hand,
            record.stage.bottom_count(),
        )
        .map_err(|message| TeacherAnnotationError::InvalidKeepPackage {
            sample: *sample,
            message,
        })?;
        let kept = KeptHand {
            stage: record.stage,
            hand: record.recommended_kept_hand.clone(),
            known_bottom: known_bottom.clone(),
            pregame: record.pregame,
        };
        let bridge = bridge_kept_hand(&kept, &deck, sample.opening_root, sample.opening_world)?;

        let resolution = match evaluate_teacher(bridge.true_state(), &cards, search_config) {
            Ok(result) => {
                stats.resolved_records = stats.resolved_records.saturating_add(1);
                if result.score.total_wins == 0 {
                    stats.resolved_zero_records = stats.resolved_zero_records.saturating_add(1);
                } else {
                    stats.resolved_positive_records =
                        stats.resolved_positive_records.saturating_add(1);
                }
                TeacherKeepResolution::Resolved(result)
            }
            Err(TeacherSearchError::IncompleteLeaf { world, stop }) => {
                stats.unresolved_records = stats.unresolved_records.saturating_add(1);
                TeacherKeepResolution::Unresolved(match stop {
                    RolloutStop::StepLimit => TeacherKeepUnresolved::LeafStepLimit { world },
                    RolloutStop::NoCandidate => TeacherKeepUnresolved::LeafNoCandidate { world },
                    other => {
                        return Err(TeacherAnnotationError::UnexpectedIncompleteLeafStop {
                            sample: *sample,
                            world,
                            stop: other,
                        });
                    }
                })
            }
            Err(TeacherSearchError::AllCandidateBranchesIncomplete { candidate_count }) => {
                stats.unresolved_records = stats.unresolved_records.saturating_add(1);
                TeacherKeepResolution::Unresolved(
                    TeacherKeepUnresolved::AllCandidateBranchesIncomplete { candidate_count },
                )
            }
            Err(error) => {
                return Err(TeacherAnnotationError::Search {
                    sample: *sample,
                    error,
                });
            }
        };

        stats.records_attempted = stats.records_attempted.saturating_add(1);
        stats.allocated_teacher_worlds = stats
            .allocated_teacher_worlds
            .checked_add(u64::from(search_config.samples))
            .ok_or(TeacherAnnotationError::CounterOverflow)?;

        annotations.insert(
            *sample,
            TeacherKeepAnnotation {
                annotation_version: R7_TEACHER_KEEP_ANNOTATION_VERSION,
                boundary: R7_TEACHER_KEEP_ANNOTATION_BOUNDARY,
                sample: *sample,
                source_record_version: record.record_version,
                source_policy_version: record.policy_version,
                source_recommended_action: record.recommended_action.clone(),
                kept_hand: record.recommended_kept_hand.clone(),
                known_bottom,
                search_config,
                resolution,
            },
        );
    }

    Ok(TeacherAnnotatedCorpus {
        annotation_version: R7_TEACHER_KEEP_ANNOTATION_VERSION,
        boundary: R7_TEACHER_KEEP_ANNOTATION_BOUNDARY,
        source_corpus_version: corpus.corpus_version,
        base_search_config,
        stats,
        annotations,
    })
}

fn search_config_for_ordinal(
    base: TeacherSearchConfig,
    ordinal: usize,
) -> Result<TeacherSearchConfig, TeacherAnnotationError> {
    let ordinal = u64::try_from(ordinal).map_err(|_| TeacherAnnotationError::WorldRangeOverflow)?;
    let stride = u64::from(base.samples);
    let offset = ordinal
        .checked_mul(stride)
        .ok_or(TeacherAnnotationError::WorldRangeOverflow)?;
    let first_world = base
        .first_world
        .0
        .checked_add(offset)
        .map(WorldId)
        .ok_or(TeacherAnnotationError::WorldRangeOverflow)?;
    first_world
        .0
        .checked_add(stride.saturating_sub(1))
        .ok_or(TeacherAnnotationError::WorldRangeOverflow)?;
    Ok(TeacherSearchConfig {
        first_world,
        ..base
    })
}

fn derive_known_bottom(
    current_seven: &[CardDefId],
    recommended_keep: &[CardDefId],
    expected_bottom: usize,
) -> Result<Vec<CardDefId>, &'static str> {
    if current_seven.len() != crate::OPENING_HAND_SIZE {
        return Err("source current hand is not seven cards");
    }
    if recommended_keep.len() + expected_bottom != current_seven.len() {
        return Err("recommended keep size does not match stage bottom count");
    }

    let mut seven = current_seven.to_vec();
    let mut keep = recommended_keep.to_vec();
    seven.sort_unstable();
    keep.sort_unstable();

    let mut known_bottom = Vec::with_capacity(expected_bottom);
    let mut keep_cursor = 0;
    for card in seven {
        if keep.get(keep_cursor) == Some(&card) {
            keep_cursor += 1;
        } else {
            known_bottom.push(card);
        }
    }
    if keep_cursor != keep.len() || known_bottom.len() != expected_bottom {
        return Err("recommended keep is not a card multiset subset of current seven");
    }
    known_bottom.sort_unstable();
    Ok(known_bottom)
}

#[derive(Debug)]
pub enum TeacherAnnotationError {
    InvalidConfig(&'static str),
    WorldRangeOverflow,
    CounterOverflow,
    Setup(String),
    InvalidKeepPackage {
        sample: EvaluatedHandSampleId,
        message: &'static str,
    },
    UnexpectedIncompleteLeafStop {
        sample: EvaluatedHandSampleId,
        world: WorldId,
        stop: RolloutStop,
    },
    Opening(OpeningError),
    Search {
        sample: EvaluatedHandSampleId,
        error: TeacherSearchError,
    },
}

impl fmt::Display for TeacherAnnotationError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InvalidConfig(message) => write!(formatter, "invalid R7 teacher sidecar config: {message}"),
            Self::WorldRangeOverflow => write!(formatter, "R7 teacher sidecar world range overflowed u64"),
            Self::CounterOverflow => write!(formatter, "R7 teacher sidecar aggregate counter overflowed"),
            Self::Setup(message) => write!(formatter, "R7 teacher sidecar setup failed: {message}"),
            Self::InvalidKeepPackage { sample, message } => write!(
                formatter,
                "R7 teacher sidecar invalid keep package for {sample:?}: {message}"
            ),
            Self::UnexpectedIncompleteLeafStop { sample, world, stop } => write!(
                formatter,
                "R7 teacher sidecar saw unexpected incomplete stop {stop:?} for {sample:?} in {world:?}"
            ),
            Self::Opening(error) => write!(formatter, "R7 teacher sidecar opening bridge failed: {error}"),
            Self::Search { sample, error } => write!(
                formatter,
                "R7 teacher sidecar search failed for {sample:?}: {error}"
            ),
        }
    }
}

impl Error for TeacherAnnotationError {
    fn source(&self) -> Option<&(dyn Error + 'static)> {
        match self {
            Self::Opening(error) => Some(error),
            Self::Search { error, .. } => Some(error),
            _ => None,
        }
    }
}

impl From<OpeningError> for TeacherAnnotationError {
    fn from(value: OpeningError) -> Self {
        Self::Opening(value)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{generate_evaluated_hand_corpus, r7_smoke_generation_config};

    #[test]
    fn duplicate_cards_are_subtracted_as_a_multiset_when_reconstructing_bottoms() {
        let cards = R4CardDatabase::load().unwrap();
        let island = cards.card_id_by_name("Island").unwrap();
        let sol_ring = cards.card_id_by_name("Sol Ring").unwrap();
        let basalt = cards.card_id_by_name("Basalt Monolith").unwrap();
        let current = vec![island, sol_ring, island, basalt, island, sol_ring, island];
        let keep = vec![island, sol_ring, island, basalt, island, sol_ring];

        assert_eq!(derive_known_bottom(&current, &keep, 1).unwrap(), vec![island]);
    }

    #[test]
    fn sidecar_is_deterministic_and_cannot_mutate_r6_recommendations() {
        let mut generation_config = r7_smoke_generation_config();
        generation_config.world_count = 1;
        let generated = generate_evaluated_hand_corpus(&generation_config).unwrap();
        let before: Vec<_> = generated
            .corpus
            .entries()
            .map(|(sample, record)| (*sample, record.recommended_action.clone()))
            .collect();
        let base = r7_teacher_sidecar_smoke_search_config();

        let first = annotate_r6_keep_packages(&generated.corpus, base).unwrap();
        let second = annotate_r6_keep_packages(&generated.corpus, base).unwrap();

        assert_eq!(first, second);
        assert_eq!(first.len(), generated.corpus.len());
        assert_eq!(first.stats.records_attempted, 1);
        assert_eq!(first.stats.allocated_teacher_worlds, 1);
        assert_eq!(
            first.stats.resolved_records + first.stats.unresolved_records,
            first.stats.records_attempted
        );
        let after: Vec<_> = generated
            .corpus
            .entries()
            .map(|(sample, record)| (*sample, record.recommended_action.clone()))
            .collect();
        assert_eq!(before, after);

        let (_, annotation) = first.entries().next().unwrap();
        assert_eq!(annotation.annotation_version, R7_TEACHER_KEEP_ANNOTATION_VERSION);
        assert_eq!(annotation.search_config.first_world, base.first_world);
    }

    #[test]
    fn teacher_world_ranges_are_non_overlapping_and_deterministic() {
        let base = TeacherSearchConfig {
            samples: 3,
            first_world: WorldId(1_000),
            ..r7_teacher_sidecar_smoke_search_config()
        };
        assert_eq!(search_config_for_ordinal(base, 0).unwrap().first_world, WorldId(1_000));
        assert_eq!(search_config_for_ordinal(base, 1).unwrap().first_world, WorldId(1_003));
        assert_eq!(search_config_for_ordinal(base, 7).unwrap().first_world, WorldId(1_021));
    }
}
