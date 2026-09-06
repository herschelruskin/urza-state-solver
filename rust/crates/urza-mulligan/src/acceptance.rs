#[cfg(test)]
mod tests {
    use std::cmp::Ordering;

    use urza_cards::R4CardDatabase;
    use urza_policy::DeterministicPolicy;
    use urza_rng::{RootSeed, WorldId};

    use crate::{
        ExactWinRate, MulliganDecisionCache, MulliganEvaluationConfig, MulliganStage,
        MulliganState, PregameContext, draw_fresh_seven, evaluate_keep_packages,
        evaluate_mull_again, load_commander_deck,
    };

    fn oracle_config() -> MulliganEvaluationConfig {
        MulliganEvaluationConfig {
            rollout: urza_mc::MonteCarloConfig {
                root: RootSeed::from_u64(0x5236_4f52_4143_0001),
                first_world: WorldId(20_000),
                samples: 1,
                rollout_max_steps: 4096,
            },
            continuation_root: RootSeed::from_u64(0x5236_4f52_4143_0002),
            first_future_world: WorldId(30_000),
            future_hand_samples: 2,
            environment_version: "r6-bruteforce-toy-oracle".to_owned(),
        }
    }

    fn average_pair(left: &ExactWinRate, right: &ExactWinRate) -> ExactWinRate {
        assert_eq!(left.denominator, right.denominator);
        let mut turns = [0_u128; 6];
        for index in 0..turns.len() {
            turns[index] = left.t1_through_t6[index] + right.t1_through_t6[index];
        }
        ExactWinRate {
            denominator: left.denominator * 2,
            t1_through_t6: turns,
            losses: left.losses + right.losses,
        }
    }

    /// Independent brute-force acceptance oracle for the production continuation DP.
    ///
    /// The production call evaluates the value of mulliganing from Four to the
    /// experimental Three floor over two sampled future hands. Independently,
    /// this test reconstructs those same two legally revealed keep-3 hands,
    /// exhaustively evaluates all 35 bottom packages for each, then enumerates
    /// all 35 x 35 deterministic policies across the two hands. The best
    /// exhaustive policy must equal the production DP average-of-optima value.
    #[test]
    fn brute_force_two_hand_policy_oracle_agrees_with_r6_dp() {
        let deck = load_commander_deck().unwrap();
        let cards = R4CardDatabase::load().unwrap();
        let policy = DeterministicPolicy;
        let config = oracle_config();
        let pregame = PregameContext {
            seat: 3,
            gemstone_caverns_eligible: true,
        };

        let mut cache = MulliganDecisionCache::default();
        let production = evaluate_mull_again(
            MulliganStage::Four,
            pregame,
            &deck,
            &cards,
            &policy,
            &config,
            &mut cache,
        )
        .unwrap()
        .expect("Four has a keep-3 continuation");
        assert_eq!(production.stage, MulliganStage::Three);
        assert_eq!(production.sampled_hands, 2);
        assert_eq!(production.keep_decisions, 2);
        assert_eq!(production.mulligan_decisions, 0);

        let mut package_values = Vec::new();
        for offset in 0..2_u64 {
            let world = WorldId(config.first_future_world.0 + offset);
            let seven =
                draw_fresh_seven(&deck, config.continuation_root, world, MulliganStage::Three);
            let state = MulliganState::at_stage(MulliganStage::Three, seven, pregame).unwrap();
            let packages = evaluate_keep_packages(
                &state,
                &deck,
                config.continuation_root,
                world,
                &cards,
                &policy,
                &config,
            )
            .unwrap();
            assert_eq!(packages.len(), 35);
            package_values.push(
                packages
                    .into_iter()
                    .map(|package| package.value)
                    .collect::<Vec<_>>(),
            );
        }

        let mut brute_force_best: Option<ExactWinRate> = None;
        let mut policies_enumerated = 0_u32;
        for left in &package_values[0] {
            for right in &package_values[1] {
                policies_enumerated += 1;
                let candidate = average_pair(left, right);
                let replace = match &brute_force_best {
                    None => true,
                    Some(best) => candidate.objective_cmp(best).unwrap() == Ordering::Greater,
                };
                if replace {
                    brute_force_best = Some(candidate);
                }
            }
        }

        assert_eq!(policies_enumerated, 35 * 35);
        assert_eq!(
            brute_force_best.expect("at least one brute-force policy"),
            production.value
        );
    }
}
