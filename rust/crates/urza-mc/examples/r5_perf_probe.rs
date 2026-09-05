use std::time::{Duration, Instant};

use urza_cards::{R4CardDatabase, load_r1_catalog, r1_catalog_digest_hex};
use urza_core::{CardDefId, CardZone, ManaPool, Phase, TrueLibrary, TrueState, Window};
use urza_mc::{
    AdaptiveRootConfig, AdaptiveSearchStats, InMemoryRootOutcomeCache, MonteCarloConfig,
    NoopRootOutcomeCache, compare_root_actions, compare_root_actions_adaptive,
    current_r5_evaluation_namespace,
};
use urza_policy::DeterministicPolicy;
use urza_policy_bridge::CandidateBridge;
use urza_rng::{RootSeed, WorldId};

const SAMPLES: u32 = 8;
const ROLLOUT_MAX_STEPS: u32 = 2048;
const FIRST_WORLD: WorldId = WorldId(0x5000);
const ROOT_SEED_U64: u64 = 0x5235_5045_5246_0001;
const ENVIRONMENT_VERSION: &str = "r5_perf_probe_v1";

struct ProbeCase {
    name: &'static str,
    hand: [&'static str; 7],
    mana: ManaPool,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let cards = R4CardDatabase::load()?;
    let catalog_digest = r1_catalog_digest_hex();
    let policy = DeterministicPolicy;

    let cases = [
        ProbeCase {
            name: "opening_combo_seven",
            hand: [
                "Island",
                "Ancient Tomb",
                "Basalt Monolith",
                "Power Artifact",
                "Forensic Gadgeteer",
                "Sensei's Divining Top",
                "The Reality Chip",
            ],
            mana: ManaPool::default(),
        },
        ProbeCase {
            name: "resource_tutor_seven",
            hand: [
                "Island",
                "Whir of Invention",
                "Reshape",
                "Transmute Artifact",
                "Spellseeker",
                "Mystical Tutor",
                "Merchant Scroll",
            ],
            mana: ManaPool {
                blue: 3,
                colorless: 3,
                ..ManaPool::default()
            },
        },
        ProbeCase {
            name: "resource_artifact_seven",
            hand: [
                "Mana Vault",
                "Sol Ring",
                "Grim Monolith",
                "Basalt Monolith",
                "Voltaic Key",
                "Sensei's Divining Top",
                "Grinding Station",
            ],
            mana: ManaPool {
                blue: 2,
                colorless: 4,
                ..ManaPool::default()
            },
        },
    ];

    println!(
        "case\troots\tfixed_ms\tadaptive_cold_ms\tadaptive_warm_ms\tadaptive_normal_ms\tnormal_used_samples\tnormal_stop\trequests\trollouts\trollout_steps\twarm_hits\twarm_rollouts\twarm_avoided_steps"
    );

    for case in cases {
        let state = build_state(&cards, &case.hand, case.mana)?;
        let roots = CandidateBridge::build(&state, &cards)?.candidates().len();
        let root = RootSeed::from_u64(ROOT_SEED_U64);

        let fixed_config = MonteCarloConfig {
            root,
            first_world: FIRST_WORLD,
            samples: SAMPLES,
            rollout_max_steps: ROLLOUT_MAX_STEPS,
        };
        let (fixed_elapsed, fixed) = timed(|| compare_root_actions(&state, &cards, &policy, fixed_config))?;

        let full_adaptive_config = AdaptiveRootConfig {
            root,
            first_world: FIRST_WORLD,
            min_samples: SAMPLES,
            max_samples: SAMPLES,
            batch_size: SAMPLES,
            rollout_max_steps: ROLLOUT_MAX_STEPS,
            evaluation_namespace: current_r5_evaluation_namespace(
                catalog_digest.clone(),
                ENVIRONMENT_VERSION,
                ROLLOUT_MAX_STEPS,
            ),
        };
        let mut cache = InMemoryRootOutcomeCache::default();
        let (cold_elapsed, cold) = timed(|| {
            compare_root_actions_adaptive(
                &state,
                &cards,
                &policy,
                &full_adaptive_config,
                &mut cache,
            )
        })?;
        assert_eq!(cold.comparison, fixed, "full adaptive parity for {}", case.name);

        let (warm_elapsed, warm) = timed(|| {
            compare_root_actions_adaptive(
                &state,
                &cards,
                &policy,
                &full_adaptive_config,
                &mut cache,
            )
        })?;
        assert_eq!(warm.comparison, fixed, "warm cache parity for {}", case.name);
        assert_eq!(warm.stats.cache_misses, 0, "warm cache miss for {}", case.name);
        assert_eq!(warm.stats.root_world_rollouts, 0, "warm rollout for {}", case.name);

        let normal_config = AdaptiveRootConfig {
            min_samples: 2,
            batch_size: 2,
            ..full_adaptive_config.clone()
        };
        let mut noop = NoopRootOutcomeCache;
        let (normal_elapsed, normal) = timed(|| {
            compare_root_actions_adaptive(&state, &cards, &policy, &normal_config, &mut noop)
        })?;

        print_row(
            case.name,
            roots,
            fixed_elapsed,
            cold_elapsed,
            warm_elapsed,
            normal_elapsed,
            normal.used_samples(),
            &format!("{:?}", normal.stop_reason),
            &cold.stats,
            &warm.stats,
        );
    }

    Ok(())
}

fn build_state(
    cards: &R4CardDatabase,
    hand_names: &[&str],
    mana: ManaPool,
) -> Result<TrueState, Box<dyn std::error::Error>> {
    let catalog = load_r1_catalog()?;
    let mut library = Vec::new();
    for card in catalog.cards.iter().filter(|card| !card.commander) {
        for _ in 0..card.deck_count {
            library.push(CardDefId(card.id));
        }
    }

    let mut hand = Vec::with_capacity(hand_names.len());
    for name in hand_names {
        let card = cards.card_id_by_name(name)?;
        let index = library
            .iter()
            .position(|candidate| *candidate == card)
            .ok_or_else(|| format!("benchmark hand card {name} is not available in the deck"))?;
        library.remove(index);
        hand.push(card);
    }

    let state = TrueState {
        turn: 1,
        phase: Phase::PrecombatMain,
        window: Window::Priority,
        library: TrueLibrary::unknown(library),
        hand: CardZone::new(hand),
        mana,
        ..TrueState::default()
    };
    state.validate()?;
    Ok(state)
}

fn timed<T, E>(f: impl FnOnce() -> Result<T, E>) -> Result<(Duration, T), E> {
    let start = Instant::now();
    let value = f()?;
    Ok((start.elapsed(), value))
}

#[allow(clippy::too_many_arguments)]
fn print_row(
    name: &str,
    roots: usize,
    fixed: Duration,
    cold: Duration,
    warm: Duration,
    normal: Duration,
    normal_used_samples: usize,
    normal_stop: &str,
    cold_stats: &AdaptiveSearchStats,
    warm_stats: &AdaptiveSearchStats,
) {
    println!(
        "{}\t{}\t{:.3}\t{:.3}\t{:.3}\t{:.3}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}",
        name,
        roots,
        millis(fixed),
        millis(cold),
        millis(warm),
        millis(normal),
        normal_used_samples,
        normal_stop,
        cold_stats.root_world_requests,
        cold_stats.root_world_rollouts,
        cold_stats.rollout_steps_executed,
        warm_stats.cache_hits,
        warm_stats.root_world_rollouts,
        warm_stats.rollout_steps_avoided_by_cache,
    );
}

fn millis(duration: Duration) -> f64 {
    duration.as_secs_f64() * 1000.0
}
