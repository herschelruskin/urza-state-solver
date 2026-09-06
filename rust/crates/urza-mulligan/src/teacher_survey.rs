use std::error::Error;
use std::fmt;

use urza_rng::{RootSeed, WorldId};

use crate::{
    CorpusGenerationConfig, CorpusGenerationError, GeneratedEvaluatedHandCorpus, MulliganChoice,
    MulliganStage, TeacherAnnotatedCorpus, TeacherAnnotationError, TeacherKeepResolution,
    TeacherSearchConfig, annotate_r6_keep_packages, generate_evaluated_hand_corpus,
    r7_teacher_generation_config,
};

pub const R7_TEACHER_SIDECAR_SURVEY_VERSION: &str = "r7_teacher_sidecar_survey_v1";
pub const R7_TEACHER_SIDECAR_SURVEY_PROFILE_VERSION: &str =
    "r7_teacher_sidecar_survey_16w_r6_16x8_teacher_1x2_v1";
pub const R7_TEACHER_SIDECAR_SURVEY_FIRST_WORLD: WorldId = WorldId(500_080);
pub const R7_TEACHER_SIDECAR_SURVEY_WORLD_COUNT: u32 = 16;
pub const R7_TEACHER_SIDECAR_SURVEY_BOUNDARY: &str = "The R7 teacher sidecar survey is diagnostic evidence only. Its source corpus is a fixed \
     16-world slice of the accepted high-budget R6 teacher profile, while the bounded R7 teacher \
     evaluates only each source record's already-selected best keep package. A positive teacher \
     value on an R6 MULL record is a keep-side disagreement candidate, not a teacher mulligan \
     recommendation: no teacher mull-again continuation is evaluated here, and no survey result \
     can alter R6 policy, London-bottom ranking, cache identity, interpretation features, or \
     gameplay.";

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct TeacherSurveyStats {
    pub records: u32,
    pub source_keep_records: u32,
    pub source_mull_records: u32,
    pub resolved_records: u32,
    pub unresolved_records: u32,
    pub resolved_positive_records: u32,
    pub resolved_zero_records: u32,
    pub positive_on_source_keep: u32,
    pub positive_on_source_mull: u32,
    pub zero_on_source_keep: u32,
    pub zero_on_source_mull: u32,
    pub unresolved_source_keep: u32,
    pub unresolved_source_mull: u32,
    pub stage_records: [u32; 6],
    pub stage_positive: [u32; 6],
    pub stage_unresolved: [u32; 6],
    pub teacher_sampled_worlds: u64,
    pub public_groups_evaluated: u64,
    pub public_actions_evaluated: u64,
    pub forced_public_steps: u64,
    pub truncated_public_groups: u64,
    pub incomplete_candidate_branches: u64,
    pub leaf_rollouts: u64,
    pub observation_splits: u64,
    pub max_full_candidate_count: u32,
    pub max_retained_candidate_count: u32,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TeacherSidecarSurvey {
    pub survey_version: &'static str,
    pub profile_version: &'static str,
    pub boundary: &'static str,
    pub generated: GeneratedEvaluatedHandCorpus,
    pub annotated: TeacherAnnotatedCorpus,
    pub stats: TeacherSurveyStats,
}

pub fn r7_teacher_sidecar_survey_generation_config() -> CorpusGenerationConfig {
    let mut config = r7_teacher_generation_config();
    config.profile_version = R7_TEACHER_SIDECAR_SURVEY_PROFILE_VERSION.to_owned();
    config.first_world = R7_TEACHER_SIDECAR_SURVEY_FIRST_WORLD;
    config.world_count = R7_TEACHER_SIDECAR_SURVEY_WORLD_COUNT;
    config
}

pub fn r7_teacher_sidecar_survey_search_config() -> TeacherSearchConfig {
    TeacherSearchConfig {
        root: RootSeed::from_u64(0x5237_5355_5256_0001),
        first_world: WorldId(930_000),
        samples: 1,
        max_choice_depth: 2,
        max_teacher_steps: 6,
        max_candidates_per_group: 6,
        leaf_rollout_max_steps: 4096,
    }
}

pub fn run_r7_teacher_sidecar_survey() -> Result<TeacherSidecarSurvey, TeacherSurveyError> {
    let generated = generate_evaluated_hand_corpus(&r7_teacher_sidecar_survey_generation_config())?;
    let annotated =
        annotate_r6_keep_packages(&generated.corpus, r7_teacher_sidecar_survey_search_config())?;
    if generated.corpus.len() != annotated.len() {
        return Err(TeacherSurveyError::RecordCountDrift {
            source: generated.corpus.len(),
            annotated: annotated.len(),
        });
    }
    let stats = summarize_teacher_sidecar(&annotated)?;
    Ok(TeacherSidecarSurvey {
        survey_version: R7_TEACHER_SIDECAR_SURVEY_VERSION,
        profile_version: R7_TEACHER_SIDECAR_SURVEY_PROFILE_VERSION,
        boundary: R7_TEACHER_SIDECAR_SURVEY_BOUNDARY,
        generated,
        annotated,
        stats,
    })
}

pub fn summarize_teacher_sidecar(
    annotated: &TeacherAnnotatedCorpus,
) -> Result<TeacherSurveyStats, TeacherSurveyError> {
    let mut stats = TeacherSurveyStats::default();
    for (sample, annotation) in annotated.entries() {
        checked_add_u32(&mut stats.records, 1, "records")?;
        checked_add_u32(
            &mut stats.stage_records[stage_index(sample.stage)],
            1,
            "stage records",
        )?;
        let source_keep = matches!(
            annotation.source_recommended_action,
            MulliganChoice::Keep { .. }
        );
        if source_keep {
            checked_add_u32(&mut stats.source_keep_records, 1, "source keep records")?;
        } else {
            checked_add_u32(&mut stats.source_mull_records, 1, "source mull records")?;
        }

        match &annotation.resolution {
            TeacherKeepResolution::Resolved(result) => {
                checked_add_u32(&mut stats.resolved_records, 1, "resolved records")?;
                checked_add_u64(
                    &mut stats.teacher_sampled_worlds,
                    u64::from(result.stats.sampled_worlds),
                    "teacher sampled worlds",
                )?;
                checked_add_u64(
                    &mut stats.public_groups_evaluated,
                    result.stats.public_groups_evaluated,
                    "public groups",
                )?;
                checked_add_u64(
                    &mut stats.public_actions_evaluated,
                    result.stats.public_actions_evaluated,
                    "public actions",
                )?;
                checked_add_u64(
                    &mut stats.forced_public_steps,
                    result.stats.forced_public_steps,
                    "forced public steps",
                )?;
                checked_add_u64(
                    &mut stats.truncated_public_groups,
                    result.stats.truncated_public_groups,
                    "truncated public groups",
                )?;
                checked_add_u64(
                    &mut stats.incomplete_candidate_branches,
                    result.stats.incomplete_candidate_branches,
                    "incomplete candidate branches",
                )?;
                checked_add_u64(
                    &mut stats.leaf_rollouts,
                    result.stats.leaf_rollouts,
                    "leaf rollouts",
                )?;
                checked_add_u64(
                    &mut stats.observation_splits,
                    result.stats.observation_splits,
                    "observation splits",
                )?;
                stats.max_full_candidate_count = stats
                    .max_full_candidate_count
                    .max(result.stats.max_full_candidate_count);
                stats.max_retained_candidate_count = stats
                    .max_retained_candidate_count
                    .max(result.stats.max_retained_candidate_count);

                if result.score.total_wins == 0 {
                    checked_add_u32(&mut stats.resolved_zero_records, 1, "resolved zero records")?;
                    if source_keep {
                        checked_add_u32(&mut stats.zero_on_source_keep, 1, "zero on source keep")?;
                    } else {
                        checked_add_u32(&mut stats.zero_on_source_mull, 1, "zero on source mull")?;
                    }
                } else {
                    checked_add_u32(
                        &mut stats.resolved_positive_records,
                        1,
                        "resolved positive records",
                    )?;
                    checked_add_u32(
                        &mut stats.stage_positive[stage_index(sample.stage)],
                        1,
                        "stage positive",
                    )?;
                    if source_keep {
                        checked_add_u32(
                            &mut stats.positive_on_source_keep,
                            1,
                            "positive on source keep",
                        )?;
                    } else {
                        checked_add_u32(
                            &mut stats.positive_on_source_mull,
                            1,
                            "positive on source mull",
                        )?;
                    }
                }
            }
            TeacherKeepResolution::Unresolved(_) => {
                checked_add_u32(&mut stats.unresolved_records, 1, "unresolved records")?;
                checked_add_u32(
                    &mut stats.stage_unresolved[stage_index(sample.stage)],
                    1,
                    "stage unresolved",
                )?;
                if source_keep {
                    checked_add_u32(
                        &mut stats.unresolved_source_keep,
                        1,
                        "unresolved source keep",
                    )?;
                } else {
                    checked_add_u32(
                        &mut stats.unresolved_source_mull,
                        1,
                        "unresolved source mull",
                    )?;
                }
            }
        }
    }
    Ok(stats)
}

const fn stage_index(stage: MulliganStage) -> usize {
    match stage {
        MulliganStage::InitialSeven => 0,
        MulliganStage::FreeSeven => 1,
        MulliganStage::Six => 2,
        MulliganStage::Five => 3,
        MulliganStage::Four => 4,
        MulliganStage::Three => 5,
    }
}

fn checked_add_u32(
    target: &mut u32,
    value: u32,
    context: &'static str,
) -> Result<(), TeacherSurveyError> {
    *target = target
        .checked_add(value)
        .ok_or(TeacherSurveyError::CounterOverflow(context))?;
    Ok(())
}

fn checked_add_u64(
    target: &mut u64,
    value: u64,
    context: &'static str,
) -> Result<(), TeacherSurveyError> {
    *target = target
        .checked_add(value)
        .ok_or(TeacherSurveyError::CounterOverflow(context))?;
    Ok(())
}

#[derive(Debug)]
pub enum TeacherSurveyError {
    Generation(CorpusGenerationError),
    Annotation(TeacherAnnotationError),
    RecordCountDrift { source: usize, annotated: usize },
    CounterOverflow(&'static str),
}

impl fmt::Display for TeacherSurveyError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Generation(error) => {
                write!(formatter, "R7 teacher survey generation failed: {error}")
            }
            Self::Annotation(error) => {
                write!(formatter, "R7 teacher survey annotation failed: {error}")
            }
            Self::RecordCountDrift { source, annotated } => write!(
                formatter,
                "R7 teacher survey record count drifted: source={source}, annotated={annotated}"
            ),
            Self::CounterOverflow(context) => {
                write!(formatter, "R7 teacher survey counter overflow: {context}")
            }
        }
    }
}

impl Error for TeacherSurveyError {
    fn source(&self) -> Option<&(dyn Error + 'static)> {
        match self {
            Self::Generation(error) => Some(error),
            Self::Annotation(error) => Some(error),
            _ => None,
        }
    }
}

impl From<CorpusGenerationError> for TeacherSurveyError {
    fn from(value: CorpusGenerationError) -> Self {
        Self::Generation(value)
    }
}

impl From<TeacherAnnotationError> for TeacherSurveyError {
    fn from(value: TeacherAnnotationError) -> Self {
        Self::Annotation(value)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{
        R7_TEACHER_FUTURE_HAND_SAMPLES, R7_TEACHER_PROFILE_VERSION, R7_TEACHER_ROLLOUT_SAMPLES,
    };

    #[test]
    fn survey_source_is_an_exact_small_slice_of_the_high_budget_r6_teacher_profile() {
        let full = r7_teacher_generation_config();
        let survey = r7_teacher_sidecar_survey_generation_config();

        assert_eq!(
            survey.profile_version,
            R7_TEACHER_SIDECAR_SURVEY_PROFILE_VERSION
        );
        assert_ne!(survey.profile_version, R7_TEACHER_PROFILE_VERSION);
        assert_eq!(survey.opening_root, full.opening_root);
        assert_eq!(survey.first_world, WorldId(500_080));
        assert_eq!(survey.world_count, 16);
        assert_eq!(survey.evaluation, full.evaluation);
        assert_eq!(
            survey.evaluation.rollout.samples,
            R7_TEACHER_ROLLOUT_SAMPLES
        );
        assert_eq!(
            survey.evaluation.future_hand_samples,
            R7_TEACHER_FUTURE_HAND_SAMPLES
        );
    }

    #[test]
    fn survey_teacher_is_bounded_below_the_viability_probe_search() {
        let config = r7_teacher_sidecar_survey_search_config();
        assert_eq!(config.samples, 1);
        assert_eq!(config.max_choice_depth, 2);
        assert_eq!(config.max_teacher_steps, 6);
        assert_eq!(config.max_candidates_per_group, 6);
        assert_eq!(config.leaf_rollout_max_steps, 4096);
    }
}
