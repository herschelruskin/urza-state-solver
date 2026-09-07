use std::error::Error;
use std::io;

use urza_cards::R4CardDatabase;
use urza_mc::sample_hidden_world;
use urza_mulligan::{
    InterpretationCatalog, KeptHand, MulliganStage, bridge_kept_hand, draw_fresh_seven,
    load_commander_deck, r7_pilot_generation_config, sample_pregame_context,
};
use urza_policy::DeterministicPolicy;
use urza_rng::WorldId;
use urza_rollout::{RolloutConfig, RolloutStop, rollout};

const SEARCH_VERSION: &str = "post_r7_positive_natural_search_v1";

fn main() {
    if let Err(error) = run() {
        eprintln!("post-r7 positive natural search failed: {error}");
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
            "usage: post-r7-positive-natural-search <opening-offset> <hidden-start> <hidden-count>; hidden-count must be positive",
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
    let interpretation = InterpretationCatalog::load()?;
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
        hand: hand.clone(),
        known_bottom: Vec::new(),
        pregame: sample_pregame_context(generation.opening_root, opening_world),
    };
    let opening = bridge_kept_hand(&kept, &deck, generation.opening_root, opening_world)?;
    let hand_names = hand
        .iter()
        .map(|card| {
            interpretation
                .card(*card)
                .map(|metadata| metadata.deck_name.as_str())
                .ok_or_else(|| io::Error::other(format!("unknown card id {}", card.0)))
        })
        .collect::<Result<Vec<_>, _>>()?;

    println!("POSITIVE_NATURAL_SEARCH\t{SEARCH_VERSION}");
    println!(
        "SOURCE\tprofile={}\topening_world={}\tstage={stage:?}\tseat={}\tcaverns={}\thand={}",
        generation.profile_version,
        opening_world.0,
        kept.pregame.seat,
        kept.pregame.gemstone_caverns_eligible,
        hand_names.join("|"),
    );
    println!(
        "R5_SCAN\troot={:?}\thidden_start={}\thidden_count={}\tmax_steps={}",
        generation.evaluation.rollout.root,
        hidden_start,
        hidden_count,
        generation.evaluation.rollout.rollout_max_steps,
    );

    let mut horizons = 0_u64;
    let mut step_limits = 0_u64;
    let mut no_candidates = 0_u64;
    let mut max_trace_len = 0_usize;

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
        max_trace_len = max_trace_len.max(result.trace.len());

        match result.stop {
            RolloutStop::Terminal(family) => {
                println!(
                    "POSITIVE\topening_world={}\thidden_world={}\tfamily={family:?}\tturn={}\ttrace_len={}",
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
            RolloutStop::Horizon => horizons = horizons.saturating_add(1),
            RolloutStop::StepLimit => step_limits = step_limits.saturating_add(1),
            RolloutStop::NoCandidate => no_candidates = no_candidates.saturating_add(1),
        }
    }

    println!(
        "NO_POSITIVE\topening_world={}\tscanned={}\thorizon={}\tstep_limit={}\tno_candidate={}\tmax_trace_len={}",
        opening_world.0, hidden_count, horizons, step_limits, no_candidates, max_trace_len,
    );
    Ok(())
}

fn parse_u64(value: Option<String>, name: &str) -> Result<u64, Box<dyn Error>> {
    value
        .ok_or_else(|| io::Error::other(format!("missing {name}")))?
        .parse::<u64>()
        .map_err(|error| Box::new(error) as Box<dyn Error>)
}
