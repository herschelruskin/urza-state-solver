use std::error::Error;
use std::fmt;

use urza_cards::R4CardDatabase;
use urza_policy::{DeterministicPolicy, POLICY_VERSION};
use urza_rng::{RNG_SCHEME_VERSION, RootSeed, WorldId};
use urza_rules::HORIZON_TURN;

use crate::{
    DEFAULT_MULLIGAN_ENVIRONMENT_VERSION, EVALUATED_HAND_CORPUS_VERSION, EXPERIMENTAL_KEEP_FLOOR,
    EvaluatedHandCorpus, EvaluatedHandSampleId, InterpretationCatalog, MULLIGAN_DECISION_VERSION,
    MULLIGAN_OBJECTIVE_VERSION, MulliganChoice, MulliganDecisionCache, MulliganError,
    MulliganEvaluationConfig, MulliganEvaluationError, MulliganStage, OpeningError,
    build_mulligan_report, evaluate_mulligan_decision, load_commander_deck, start_mulligan_game,
    take_mulligan,
};

pub const CORPUS_GENERATOR_VERSION: &str = "r7_sequential_r6_corpus_v1";
pub const R7_SMOKE_PROFILE_VERSION: &str = "r7_smoke_2_worlds_1x1_v1";
pub const R7_PILOT_PROFILE_VERSION: &str = "r7_pilot_16_worlds_1x1_v1";

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CorpusGenerationConfig {
    pub profile_version: String,
    pub opening_root: RootSeed,
    pub first_world: WorldId,
    pub world_count: u32,
    pub evaluation: MulliganEvaluationConfig,
}

pub fn r7_smoke_generation_config() -> CorpusGenerationConfig {
    CorpusGenerationConfig {
        profile_version: R7_SMOKE_PROFILE_VERSION.to_owned(),
        opening_root: RootSeed::from_u64(0x5237_534d_4f4b_4501),
        first_world: WorldId(70_000),
        world_count: 2,
        evaluation: MulliganEvaluationConfig {
            rollout: urza_mc::MonteCarloConfig {
                root: RootSeed::from_u64(0x5237_524f_4c4c_0001),
                first_world: WorldId(80_000),
                samples: 1,
                rollout_max_steps: 4096,
            },
            continuation_root: RootSeed::from_u64(0x5237_434f_4e54_0001),
            first_future_world: WorldId(90_000),
            future_hand_samples: 1,
            environment_version: DEFAULT_MULLIGAN_ENVIRONMENT_VERSION.to_owned(),
        },
    }
}

pub fn r7_pilot_generation_config() -> CorpusGenerationConfig {
    CorpusGenerationConfig {
        profile_version: R7_PILOT_PROFILE_VERSION.to_owned(),
        opening_root: RootSeed::from_u64(0x5237_5049_4c4f_5401),
        first_world: WorldId(100_000),
        world_count: 16,
        evaluation: MulliganEvaluationConfig {
            rollout: urza_mc::MonteCarloConfig {
                root: RootSeed::from_u64(0x5237_524f_4c4c_0002),
                first_world: WorldId(200_000),
                samples: 1,
                rollout_max_steps: 4096,
            },
            continuation_root: RootSeed::from_u64(0x5237_434f_4e54_0002),
            first_future_world: WorldId(300_000),
            future_hand_samples: 1,
            environment_version: DEFAULT_MULLIGAN_ENVIRONMENT_VERSION.to_owned(),
        },
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CorpusGenerationProvenance {
    pub generator_version: &'static str,
    pub profile_version: String,
    pub corpus_version: &'static str,
    pub deck_version: String,
    pub rng_scheme_version: &'static str,
    pub policy_version: &'static str,
    pub decision_version: &'static str,
    pub objective_version: &'static str,
    pub horizon: u8,
    pub experimental_keep_floor: u8,
    pub opening_root: RootSeed,
    pub first_world: WorldId,
    pub world_count: u32,
    pub evaluation: MulliganEvaluationConfig,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct CorpusGenerationStats {
    pub worlds_completed: u32,
    pub evaluated_decisions: u32,
    pub stage_decisions: [u32; 6],
    pub keep_decisions: u32,
    pub mulligan_decisions: u32,
    pub continuation_cache_hits: u64,
    pub continuation_cache_misses: u64,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct GeneratedEvaluatedHandCorpus {
    pub provenance: CorpusGenerationProvenance,
    pub stats: CorpusGenerationStats,
    pub corpus: EvaluatedHandCorpus,
}

pub fn generate_evaluated_hand_corpus(
    config: &CorpusGenerationConfig,
) -> Result<GeneratedEvaluatedHandCorpus, CorpusGenerationError> {
    if config.world_count == 0 {
        return Err(CorpusGenerationError::InvalidConfig(
            "world_count must be at least one",
        ));
    }
    let last_offset = u64::from(config.world_count - 1);
    config
        .first_world
        .0
        .checked_add(last_offset)
        .ok_or(CorpusGenerationError::WorldRangeOverflow)?;

    let deck = load_commander_deck()?;
    let cards = R4CardDatabase::load().map_err(|error| {
        CorpusGenerationError::Setup(format!("R4 card database failed: {error}"))
    })?;
    let interpretation = InterpretationCatalog::load().map_err(|error| {
        CorpusGenerationError::Setup(format!("interpretation catalog failed: {error}"))
    })?;
    let policy = DeterministicPolicy;
    let mut continuation_cache = MulliganDecisionCache::default();
    let mut corpus = EvaluatedHandCorpus::new();
    let mut stats = CorpusGenerationStats::default();

    for offset in 0..config.world_count {
        let world = WorldId(
            config
                .first_world
                .0
                .checked_add(u64::from(offset))
                .ok_or(CorpusGenerationError::WorldRangeOverflow)?,
        );
        let mut state = start_mulligan_game(&deck, config.opening_root, world)?;

        loop {
            let evaluation = evaluate_mulligan_decision(
                &state,
                &deck,
                config.opening_root,
                world,
                &cards,
                &policy,
                &config.evaluation,
                &mut continuation_cache,
            )?;
            let report = build_mulligan_report(&state, &evaluation, &config.evaluation)?;
            let stage = state.stage();
            corpus.insert_report(
                EvaluatedHandSampleId::new(config.opening_root, world, stage),
                &report,
                &interpretation,
            )?;

            stats.evaluated_decisions = stats.evaluated_decisions.saturating_add(1);
            stats.stage_decisions[stage_index(stage)] =
                stats.stage_decisions[stage_index(stage)].saturating_add(1);

            match report.selected {
                MulliganChoice::Keep { .. } => {
                    stats.keep_decisions = stats.keep_decisions.saturating_add(1);
                    break;
                }
                MulliganChoice::Mulligan => {
                    stats.mulligan_decisions = stats.mulligan_decisions.saturating_add(1);
                    state = take_mulligan(state, &deck, config.opening_root, world)?;
                }
            }
        }
        stats.worlds_completed = stats.worlds_completed.saturating_add(1);
    }

    stats.continuation_cache_hits = continuation_cache.hits();
    stats.continuation_cache_misses = continuation_cache.misses();

    Ok(GeneratedEvaluatedHandCorpus {
        provenance: CorpusGenerationProvenance {
            generator_version: CORPUS_GENERATOR_VERSION,
            profile_version: config.profile_version.clone(),
            corpus_version: EVALUATED_HAND_CORPUS_VERSION,
            deck_version: deck.deck_version().to_owned(),
            rng_scheme_version: RNG_SCHEME_VERSION,
            policy_version: POLICY_VERSION,
            decision_version: MULLIGAN_DECISION_VERSION,
            objective_version: MULLIGAN_OBJECTIVE_VERSION,
            horizon: HORIZON_TURN,
            experimental_keep_floor: EXPERIMENTAL_KEEP_FLOOR,
            opening_root: config.opening_root,
            first_world: config.first_world,
            world_count: config.world_count,
            evaluation: config.evaluation.clone(),
        },
        stats,
        corpus,
    })
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

#[derive(Debug)]
pub enum CorpusGenerationError {
    InvalidConfig(&'static str),
    WorldRangeOverflow,
    Setup(String),
    Opening(OpeningError),
    Evaluation(MulliganEvaluationError),
    Mulligan(MulliganError),
    Corpus(crate::CorpusError),
}

impl fmt::Display for CorpusGenerationError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InvalidConfig(message) => {
                write!(formatter, "invalid R7 corpus config: {message}")
            }
            Self::WorldRangeOverflow => write!(formatter, "R7 corpus world range overflowed u64"),
            Self::Setup(message) => write!(formatter, "R7 corpus setup failed: {message}"),
            Self::Opening(error) => write!(formatter, "R7 corpus opening failed: {error}"),
            Self::Evaluation(error) => write!(formatter, "R7 corpus R6 evaluation failed: {error}"),
            Self::Mulligan(error) => {
                write!(formatter, "R7 corpus mulligan transition failed: {error}")
            }
            Self::Corpus(error) => write!(formatter, "R7 corpus insertion failed: {error}"),
        }
    }
}

impl Error for CorpusGenerationError {
    fn source(&self) -> Option<&(dyn Error + 'static)> {
        match self {
            Self::Opening(error) => Some(error),
            Self::Evaluation(error) => Some(error),
            Self::Mulligan(error) => Some(error),
            Self::Corpus(error) => Some(error),
            _ => None,
        }
    }
}

impl From<OpeningError> for CorpusGenerationError {
    fn from(value: OpeningError) -> Self {
        Self::Opening(value)
    }
}

impl From<MulliganEvaluationError> for CorpusGenerationError {
    fn from(value: MulliganEvaluationError) -> Self {
        Self::Evaluation(value)
    }
}

impl From<MulliganError> for CorpusGenerationError {
    fn from(value: MulliganError) -> Self {
        Self::Mulligan(value)
    }
}

impl From<crate::CorpusError> for CorpusGenerationError {
    fn from(value: crate::CorpusError) -> Self {
        Self::Corpus(value)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::draw_fresh_seven;

    #[test]
    fn generated_smoke_corpus_uses_actual_sequential_r6_decisions() {
        let config = r7_smoke_generation_config();
        let generated = generate_evaluated_hand_corpus(&config).unwrap();
        let deck = load_commander_deck().unwrap();

        assert_eq!(generated.stats.worlds_completed, config.world_count);
        assert_eq!(
            usize::try_from(generated.stats.evaluated_decisions).unwrap(),
            generated.corpus.len()
        );
        assert_eq!(generated.stats.keep_decisions, config.world_count);
        assert_eq!(
            generated.stats.keep_decisions + generated.stats.mulligan_decisions,
            generated.stats.evaluated_decisions
        );
        assert_eq!(
            generated.provenance.generator_version,
            CORPUS_GENERATOR_VERSION
        );
        assert_eq!(generated.provenance.policy_version, POLICY_VERSION);

        for (sample, record) in generated.corpus.entries() {
            assert_eq!(sample.opening_root, config.opening_root);
            assert_eq!(record.stage, sample.stage);
            assert_eq!(
                record.current_seven,
                draw_fresh_seven(
                    &deck,
                    config.opening_root,
                    sample.opening_world,
                    sample.stage
                )
            );
        }
    }

    #[test]
    fn generated_world_paths_are_stage_prefixes_and_end_in_keep() {
        let config = r7_smoke_generation_config();
        let generated = generate_evaluated_hand_corpus(&config).unwrap();

        for offset in 0..config.world_count {
            let world = WorldId(config.first_world.0 + u64::from(offset));
            let decisions: Vec<_> = generated
                .corpus
                .entries()
                .filter(|(sample, _)| sample.opening_world == world)
                .map(|(sample, record)| (sample.stage, &record.recommended_action))
                .collect();
            assert!(!decisions.is_empty());
            assert_eq!(decisions[0].0, MulliganStage::InitialSeven);
            for pair in decisions.windows(2) {
                assert_eq!(pair[0].1, &MulliganChoice::Mulligan);
                assert_eq!(pair[0].0.next(), Some(pair[1].0));
            }
            assert!(matches!(
                decisions.last().unwrap().1,
                MulliganChoice::Keep { .. }
            ));
        }
    }

    #[test]
    fn zero_world_generation_is_rejected_before_setup() {
        let mut config = r7_smoke_generation_config();
        config.world_count = 0;
        assert!(matches!(
            generate_evaluated_hand_corpus(&config),
            Err(CorpusGenerationError::InvalidConfig(_))
        ));
    }
}
