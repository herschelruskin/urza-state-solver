use std::error::Error;
use std::io;

use urza_cards::R4CardDatabase;
use urza_mc::sample_hidden_world;
use urza_mulligan::{
    KeptHand, MulliganStage, bridge_kept_hand, draw_fresh_seven, load_commander_deck,
    r7_pilot_generation_config, sample_pregame_context,
};
use urza_policy::DeterministicPolicy;
use urza_rng::WorldId;
use urza_rollout::{RolloutConfig, RolloutStop, rollout};

const ISOLATE_VERSION: &str = "post_r7_step_limit_isolate_v1";

fn main() {
    if let Err(error) = run() {
        eprintln!("post-r7 StepLimit isolation failed: {error}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), Box<dyn Error>> {
    let mut args = std::env::args().skip(1);
    let opening_offset = parse_u64(args.next(), "opening-offset")?;
    let hidden_start = parse_u64(args.next(), "hidden-start")?;
    let hidden_count = parse_u64(args.next(), "hidden-count")?;
    if args.next().is_some() || hidden_count == 0 {
        return Err(Box::new(io::Error::other(
            "usage: post-r7-step-limit-isolate <opening-offset> <hidden-start> <hidden-count>; hidden-count must be positive",
        )));
    }

    let generation = r7_pilot_generation_config();
    if opening_offset >= u64::from(generation.world_count) {
        return Err(Box::new(io::Error::other(format!(
            "opening offset {opening_offset} is outside accepted pilot world count {}",
            generation.world_count
        ))));
    }

    let deck = load_commander_deck()?;
    let cards = R4CardDatabase::load()?;
    let opening_world = WorldId(
        generation
            .first_world
            .0
            .checked_add(opening_offset)
            .ok_or_else(|| io::Error::other("opening world overflow"))?,
    );
    let stage = MulliganStage::InitialSeven;
    let hand = draw_fresh_seven(&deck, generation.opening_root, opening_world, stage);
    let kept = KeptHand {
        stage,
        hand,
        known_bottom: Vec::new(),
        pregame: sample_pregame_context(generation.opening_root, opening_world),
    };
    let opening = bridge_kept_hand(&kept, &deck, generation.opening_root, opening_world)?;

    println!("STEP_LIMIT_ISOLATE\t{ISOLATE_VERSION}");
    println!(
        "SCAN\topening_world={}\thidden_start={}\thidden_count={}\tmax_steps={}",
        opening_world.0,
        hidden_start,
        hidden_count,
        generation.evaluation.rollout.rollout_max_steps,
    );

    for hidden_offset in 0..hidden_count {
        let hidden_world = WorldId(
            hidden_start
                .checked_add(hidden_offset)
                .ok_or_else(|| io::Error::other("hidden world overflow"))?,
        );
        let exact = sample_hidden_world(
            opening.true_state(),
            generation.evaluation.rollout.root,
            hidden_world,
        )?;
        let result = rollout(
            exact,
            &cards,
            &DeterministicPolicy,
            RolloutConfig {
                root: generation.evaluation.rollout.root,
                world: hidden_world,
                max_steps: generation.evaluation.rollout.rollout_max_steps,
            },
        )?;

        match result.stop {
            RolloutStop::StepLimit => {
                println!(
                    "STEP_LIMIT\topening_world={}\thidden_world={}\tturn={}\ttrace_len={}",
                    opening_world.0,
                    hidden_world.0,
                    result.final_information.turn,
                    result.trace.len(),
                );
                for step in &result.trace {
                    println!(
                        "TRACE\tindex={}\tturn={}\tphase={:?}\twindow={:?}\tclass={:?}\tkey={:?}",
                        step.index, step.turn, step.phase, step.window, step.class, step.key
                    );
                }
                return Ok(());
            }
            RolloutStop::Terminal(family) => {
                println!(
                    "TERMINAL_BEFORE_STEP_LIMIT\topening_world={}\thidden_world={}\tfamily={family:?}\tturn={}\ttrace_len={}",
                    opening_world.0,
                    hidden_world.0,
                    result.final_information.turn,
                    result.trace.len(),
                );
            }
            RolloutStop::Horizon | RolloutStop::NoCandidate => {}
        }
    }

    println!(
        "NO_STEP_LIMIT\topening_world={}\tscanned={}",
        opening_world.0, hidden_count
    );
    Ok(())
}

fn parse_u64(value: Option<String>, name: &str) -> Result<u64, Box<dyn Error>> {
    value
        .ok_or_else(|| io::Error::other(format!("missing {name}")))?
        .parse::<u64>()
        .map_err(|error| Box::new(error) as Box<dyn Error>)
}
