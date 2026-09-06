use urza_rng::{RootSeed, WorldId};

use crate::{
    CorpusGenerationConfig, DEFAULT_MULLIGAN_ENVIRONMENT_VERSION, MulliganEvaluationConfig,
};

pub const R7_TEACHER_PROFILE_VERSION: &str = "r7_teacher_256_worlds_16x8_v1";
pub const R7_TEACHER_WORLD_COUNT: u32 = 256;
pub const R7_TEACHER_ROLLOUT_SAMPLES: u32 = 16;
pub const R7_TEACHER_FUTURE_HAND_SAMPLES: u32 = 8;

/// Materially higher-budget R7 teacher corpus configuration.
///
/// Relative to the 16-world 1x1 pilot this expands opening coverage by 16x,
/// uses 16 R5 hidden-world outcomes for every legal keep package, and samples
/// 8 fresh future hands at every R6 continuation stage. The continuation cache
/// preserves the accepted R6 future-invariance contract while amortizing those
/// continuation values across opening worlds with the same pregame context.
pub fn r7_teacher_generation_config() -> CorpusGenerationConfig {
    CorpusGenerationConfig {
        profile_version: R7_TEACHER_PROFILE_VERSION.to_owned(),
        opening_root: RootSeed::from_u64(0x5237_5445_4143_4801),
        first_world: WorldId(500_000),
        world_count: R7_TEACHER_WORLD_COUNT,
        evaluation: MulliganEvaluationConfig {
            rollout: urza_mc::MonteCarloConfig {
                root: RootSeed::from_u64(0x5237_524f_4c4c_0003),
                first_world: WorldId(600_000),
                samples: R7_TEACHER_ROLLOUT_SAMPLES,
                rollout_max_steps: 4096,
            },
            continuation_root: RootSeed::from_u64(0x5237_434f_4e54_0003),
            first_future_world: WorldId(700_000),
            future_hand_samples: R7_TEACHER_FUTURE_HAND_SAMPLES,
            environment_version: DEFAULT_MULLIGAN_ENVIRONMENT_VERSION.to_owned(),
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn teacher_profile_is_materially_larger_than_the_pilot_budget() {
        let config = r7_teacher_generation_config();
        assert_eq!(config.profile_version, R7_TEACHER_PROFILE_VERSION);
        assert_eq!(config.world_count, 256);
        assert_eq!(config.evaluation.rollout.samples, 16);
        assert_eq!(config.evaluation.future_hand_samples, 8);
        assert_eq!(config.evaluation.rollout.rollout_max_steps, 4096);
    }
}
