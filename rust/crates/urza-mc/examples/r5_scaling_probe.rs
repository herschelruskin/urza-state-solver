use std::time::{Duration, Instant};

use urza_cards::{R4CardDatabase, load_r1_catalog};
use urza_core::{CardDefId, CardZone, ManaPool, Phase, TrueLibrary, TrueState, Window};
use urza_mc::{
    ParallelRootConfig, RootActionError, compare_root_actions_world_ids,
    compare_root_actions_world_ids_parallel,
};
use urza_policy::DeterministicPolicy;
use urza_policy_bridge::CandidateBridge;
use urza_rng::{RootSeed, WorldId};

const ROLLOUT_MAX_STEPS: u32 = 4096;
const FIRST_WORLD: WorldId = WorldId(0x5000);
const ROOT_SEED_U64: u64 = 0x5235_5343_414c_4501;
const SAMPLE_BUDGETS: [usize; 3] = [32, 64, 256];
const WORKER_COUNTS: [usize; 4] = [1, 2, 4, 8];
const MAX_SCAN_ATTEMPTS: u64 = 4096;

struct ProbeCase {
    name: &'static str,
    hand: [&'static str; 7],
    mana: ManaPool,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let cards = R4CardDatabase::load()?;
    let policy = DeterministicPolicy;
    let available = std::thread::available_parallelism().map_or(1, usize::from);
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

    println!("available_parallelism\t{available}");
    println!("case\tsafe_worlds\tskipped_incomplete\tlast_world");
    println!("case\tsamples\troots\tjobs\tserial_ms\tworkers\tparallel_ms\tspeedup");

    for case in cases {
        let state = build_state(&cards, &case.hand, case.mana)?;
        let roots = CandidateBridge::build(&state, &cards)?.candidates().len();
        let root = RootSeed::from_u64(ROOT_SEED_U64);
        let (worlds, skipped) = select_complete_worlds(
            &state,
            &cards,
            &policy,
            root,
            *SAMPLE_BUDGETS.last().expect("sample budgets are nonempty"),
        )?;
        println!(
            "{}\t{}\t{}\t{}",
            case.name,
            worlds.len(),
            skipped,
            worlds.last().expect("selected worlds").0,
        );

        for samples in SAMPLE_BUDGETS {
            let selected_worlds = &worlds[..samples];
            let (serial_elapsed, serial) = timed(|| {
                compare_root_actions_world_ids(
                    &state,
                    &cards,
                    &policy,
                    root,
                    ROLLOUT_MAX_STEPS,
                    selected_worlds,
                )
            })?;
            for workers in WORKER_COUNTS {
                let (parallel_elapsed, parallel) = timed(|| {
                    compare_root_actions_world_ids_parallel(
                        &state,
                        &cards,
                        &policy,
                        root,
                        ROLLOUT_MAX_STEPS,
                        selected_worlds,
                        ParallelRootConfig { workers },
                    )
                })?;
                assert_eq!(
                    parallel, serial,
                    "serial/parallel parity for {} samples={} workers={}",
                    case.name, samples, workers
                );
                println!(
                    "{}\t{}\t{}\t{}\t{:.3}\t{}\t{:.3}\t{:.2}",
                    case.name,
                    samples,
                    roots,
                    roots.saturating_mul(samples),
                    millis(serial_elapsed),
                    workers,
                    millis(parallel_elapsed),
                    speedup(serial_elapsed, parallel_elapsed),
                );
            }
        }
    }

    Ok(())
}

fn select_complete_worlds(
    state: &TrueState,
    cards: &R4CardDatabase,
    policy: &DeterministicPolicy,
    root: RootSeed,
    target: usize,
) -> Result<(Vec<WorldId>, u64), Box<dyn std::error::Error>> {
    let mut worlds = Vec::with_capacity(target);
    let mut skipped = 0_u64;
    let mut offset = 0_u64;

    while worlds.len() < target {
        if offset >= MAX_SCAN_ATTEMPTS {
            return Err(format!(
                "only found {} complete worlds after {} attempts",
                worlds.len(),
                MAX_SCAN_ATTEMPTS
            )
            .into());
        }
        let world = WorldId(
            FIRST_WORLD
                .0
                .checked_add(offset)
                .ok_or("world id overflow in scaling probe")?,
        );
        offset += 1;
        match compare_root_actions_world_ids(
            state,
            cards,
            policy,
            root,
            ROLLOUT_MAX_STEPS,
            &[world],
        ) {
            Ok(_) => worlds.push(world),
            Err(RootActionError::IncompleteWorld { .. }) => skipped += 1,
            Err(error) => return Err(error.into()),
        }
    }

    Ok((worlds, skipped))
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

fn millis(duration: Duration) -> f64 {
    duration.as_secs_f64() * 1000.0
}

fn speedup(serial: Duration, parallel: Duration) -> f64 {
    serial.as_secs_f64() / parallel.as_secs_f64()
}
