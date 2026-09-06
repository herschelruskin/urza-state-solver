#[cfg(test)]
mod tests {
    use urza_cards::R4CardDatabase;
    use urza_policy::DeterministicPolicy;
    use urza_rng::{RootSeed, WorldId};

    use crate::{
        MulliganDecisionCache, MulliganEvaluationConfig, MulliganStage, PregameContext,
        draw_fresh_seven, evaluate_mull_again, load_commander_deck,
    };

    #[test]
    fn keep_vs_mull_continuation_is_invariant_to_unrevealed_future_seven_realizations() {
        let deck = load_commander_deck().unwrap();
        let cards = R4CardDatabase::load().unwrap();
        let policy = DeterministicPolicy;
        let pregame = PregameContext {
            seat: 4,
            gemstone_caverns_eligible: true,
        };
        let config = MulliganEvaluationConfig {
            rollout: urza_mc::MonteCarloConfig {
                root: RootSeed::from_u64(0x5236_494e_5641_0001),
                first_world: WorldId(40_000),
                samples: 1,
                rollout_max_steps: 4096,
            },
            continuation_root: RootSeed::from_u64(0x5236_494e_5641_0002),
            first_future_world: WorldId(50_000),
            future_hand_samples: 1,
            environment_version: "r6-future-invariance".to_owned(),
        };

        // These are two distinct hypothetical next sevens that could exist in
        // latent worlds. Neither coordinate is part of the current decision or
        // continuation cache identity.
        let latent_a = draw_fresh_seven(
            &deck,
            RootSeed::from_u64(0xaaaa),
            WorldId(1),
            MulliganStage::Three,
        );
        let latent_b = draw_fresh_seven(
            &deck,
            RootSeed::from_u64(0xbbbb),
            WorldId(2),
            MulliganStage::Three,
        );
        assert_ne!(latent_a, latent_b);

        let mut cache = MulliganDecisionCache::default();
        let first = evaluate_mull_again(
            MulliganStage::Four,
            pregame,
            &deck,
            &cards,
            &policy,
            &config,
            &mut cache,
        )
        .unwrap()
        .expect("Four has a Three continuation");
        let hits_before = cache.hits();
        let second = evaluate_mull_again(
            MulliganStage::Four,
            pregame,
            &deck,
            &cards,
            &policy,
            &config,
            &mut cache,
        )
        .unwrap()
        .expect("Four has a Three continuation");

        assert_eq!(first, second);
        assert!(cache.hits() > hits_before);
        assert_eq!(first.stage, MulliganStage::Three);
    }
}
