use std::error::Error;
use std::io;

use urza_cards::R4CardDatabase;
use urza_core::{PendingDecision, Phase, TrueState, Window};
use urza_info::observe;
use urza_mc::sample_hidden_world;
use urza_mulligan::{
    InterpretationCatalog, KeptHand, MulliganStage, bridge_kept_hand, draw_fresh_seven,
    load_commander_deck, r7_pilot_generation_config, sample_pregame_context,
};
use urza_policy::DeterministicPolicy;
use urza_policy_bridge::CandidateBridge;
use urza_rng::{LogicalEventId, WorldId};
use urza_rollout::{
    RolloutConfig, RolloutResult, RolloutStep, RolloutStop, replay_trace, rollout,
    rollout_with_logical_event_offset,
};
use urza_rules::{
    GameRngContext, RuleError, advance_automatic, apply_action_with_rng, detect_terminal_win,
};

const SEARCH_VERSION: &str = "post_r5_one_deviation_search_v1";

fn main() {
    if let Err(error) = run() {
        eprintln!("post-R5 one-deviation search failed: {error}");
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
            "usage: post-r5-one-deviation-search <opening-offset> <hidden-start> <hidden-count>; hidden-count must be positive",
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

    let rollout_config = RolloutConfig {
        root: generation.evaluation.rollout.root,
        world: WorldId(0),
        max_steps: generation.evaluation.rollout.rollout_max_steps,
    };

    println!("ONE_DEVIATION_SEARCH\t{SEARCH_VERSION}");
    println!(
        "SOURCE\tprofile={}\topening_world={}\tstage={stage:?}\tseat={}\tcaverns={}\thand={}",
        generation.profile_version,
        opening_world.0,
        kept.pregame.seat,
        kept.pregame.gemstone_caverns_eligible,
        hand_names.join("|"),
    );
    println!(
        "SCAN\troot={:?}\thidden_start={}\thidden_count={}\tmax_steps={}",
        rollout_config.root, hidden_start, hidden_count, rollout_config.max_steps,
    );

    let mut worlds_scanned = 0_u64;
    let mut decisions_scanned = 0_u64;
    let mut deviations_tested = 0_u64;
    let mut horizon_continuations = 0_u64;
    let mut max_baseline_trace = 0_usize;
    let mut max_candidates = 0_usize;

    for hidden_offset in 0..hidden_count {
        let hidden_world = WorldId(
            hidden_start
                .checked_add(hidden_offset)
                .ok_or_else(|| io::Error::other("hidden world overflow"))?,
        );
        let config = RolloutConfig {
            world: hidden_world,
            ..rollout_config
        };
        let exact = sample_hidden_world(opening.true_state(), config.root, hidden_world)?;
        let baseline = rollout(exact.clone(), &cards, &DeterministicPolicy, config)?;
        worlds_scanned = worlds_scanned.saturating_add(1);
        max_baseline_trace = max_baseline_trace.max(baseline.trace.len());

        match baseline.stop {
            RolloutStop::Terminal(family) => {
                println!(
                    "BASELINE_POSITIVE\topening_world={}\thidden_world={}\tfamily={family:?}\tturn={}\ttrace_len={}",
                    opening_world.0,
                    hidden_world.0,
                    baseline.final_information.turn,
                    baseline.trace.len(),
                );
                print_trace("BASELINE_TRACE", &baseline.trace, 0);
                return Ok(());
            }
            RolloutStop::Horizon => {}
            RolloutStop::StepLimit | RolloutStop::NoCandidate => {
                print_incomplete_baseline(opening_world, hidden_world, &baseline);
                return Err(Box::new(io::Error::other(format!(
                    "baseline world {} stopped incompletely at {:?}",
                    hidden_world.0, baseline.stop
                ))));
            }
        }

        for (position, baseline_step) in baseline.trace.iter().enumerate() {
            let prefix = &baseline.trace[..position];
            let mut decision_state = replay_trace(exact.clone(), &cards, config, prefix)?;
            if let Some(stop) = prepare_for_decision(&mut decision_state, &cards)? {
                return Err(Box::new(io::Error::other(format!(
                    "baseline replay stopped at decision {} before expected step: {:?}",
                    baseline_step.index, stop
                ))));
            }

            let bridge = CandidateBridge::build(&decision_state, &cards)?;
            let information = bridge.information();
            if information.turn != baseline_step.turn
                || information.phase != baseline_step.phase
                || information.window != baseline_step.window
            {
                return Err(Box::new(io::Error::other(format!(
                    "baseline replay decision drift at step {}: expected turn {} {:?}/{:?}, got turn {} {:?}/{:?}",
                    baseline_step.index,
                    baseline_step.turn,
                    baseline_step.phase,
                    baseline_step.window,
                    information.turn,
                    information.phase,
                    information.window,
                ))));
            }

            let baseline_matches = bridge
                .candidates()
                .iter()
                .filter(|candidate| {
                    candidate.class == baseline_step.class && candidate.key == baseline_step.key
                })
                .count();
            if baseline_matches != 1 {
                return Err(Box::new(io::Error::other(format!(
                    "expected one baseline semantic candidate at step {}, found {}",
                    baseline_step.index, baseline_matches
                ))));
            }

            decisions_scanned = decisions_scanned.saturating_add(1);
            max_candidates = max_candidates.max(bridge.candidates().len());

            for alternate in bridge.candidates().iter().filter(|candidate| {
                candidate.class != baseline_step.class || candidate.key != baseline_step.key
            }) {
                deviations_tested = deviations_tested.saturating_add(1);
                let action = bridge.resolved_action(alternate.token).ok_or_else(|| {
                    io::Error::other(format!(
                        "alternate token {:?} could not be resolved at step {}",
                        alternate.token, baseline_step.index
                    ))
                })?;
                let mut deviated_state = decision_state.clone();
                apply_action_with_rng(
                    &mut deviated_state,
                    &cards,
                    action,
                    GameRngContext {
                        root: config.root,
                        world: config.world,
                        logical_event: LogicalEventId(u64::from(baseline_step.index)),
                    },
                )?;

                let consumed = baseline_step
                    .index
                    .checked_add(1)
                    .ok_or_else(|| io::Error::other("step index overflow"))?;
                let continuation = rollout_with_logical_event_offset(
                    deviated_state,
                    &cards,
                    &DeterministicPolicy,
                    RolloutConfig {
                        max_steps: config.max_steps.saturating_sub(consumed),
                        ..config
                    },
                    u64::from(consumed),
                )?;

                match continuation.stop {
                    RolloutStop::Terminal(family) => {
                        println!(
                            "POSITIVE_ONE_DEVIATION\topening_world={}\thidden_world={}\tdecision_index={}\tbaseline_class={:?}\tbaseline_key={:?}\tforced_class={:?}\tforced_key={:?}\tfamily={family:?}\tturn={}\tbaseline_trace_len={}\tcontinuation_trace_len={}",
                            opening_world.0,
                            hidden_world.0,
                            baseline_step.index,
                            baseline_step.class,
                            baseline_step.key,
                            alternate.class,
                            alternate.key,
                            continuation.final_information.turn,
                            baseline.trace.len(),
                            continuation.trace.len(),
                        );
                        print_trace("TRACE_PREFIX", prefix, 0);
                        println!(
                            "TRACE_FORCED\tindex={}\tturn={}\tphase={:?}\twindow={:?}\tclass={:?}\tkey={:?}",
                            baseline_step.index,
                            information.turn,
                            information.phase,
                            information.window,
                            alternate.class,
                            alternate.key,
                        );
                        print_trace(
                            "TRACE_CONTINUATION",
                            &continuation.trace,
                            u64::from(consumed),
                        );
                        return Ok(());
                    }
                    RolloutStop::Horizon => {
                        horizon_continuations = horizon_continuations.saturating_add(1);
                    }
                    RolloutStop::StepLimit | RolloutStop::NoCandidate => {
                        println!(
                            "INCOMPLETE_ONE_DEVIATION\topening_world={}\thidden_world={}\tdecision_index={}\tbaseline_class={:?}\tbaseline_key={:?}\tforced_class={:?}\tforced_key={:?}\tstop={:?}\tturn={}\tcontinuation_trace_len={}",
                            opening_world.0,
                            hidden_world.0,
                            baseline_step.index,
                            baseline_step.class,
                            baseline_step.key,
                            alternate.class,
                            alternate.key,
                            continuation.stop,
                            continuation.final_information.turn,
                            continuation.trace.len(),
                        );
                        print_trace("TRACE_PREFIX", prefix, 0);
                        println!(
                            "TRACE_FORCED\tindex={}\tturn={}\tphase={:?}\twindow={:?}\tclass={:?}\tkey={:?}",
                            baseline_step.index,
                            information.turn,
                            information.phase,
                            information.window,
                            alternate.class,
                            alternate.key,
                        );
                        print_trace(
                            "TRACE_CONTINUATION",
                            &continuation.trace,
                            u64::from(consumed),
                        );
                        return Err(Box::new(io::Error::other(format!(
                            "one-deviation continuation stopped incompletely at {:?}",
                            continuation.stop
                        ))));
                    }
                }
            }
        }
    }

    println!(
        "NO_ONE_DEVIATION_POSITIVE\topening_world={}\tworlds_scanned={}\tdecisions_scanned={}\tdeviations_tested={}\thorizon_continuations={}\tmax_baseline_trace={}\tmax_candidates={}",
        opening_world.0,
        worlds_scanned,
        decisions_scanned,
        deviations_tested,
        horizon_continuations,
        max_baseline_trace,
        max_candidates,
    );
    Ok(())
}

fn prepare_for_decision(
    state: &mut TrueState,
    cards: &R4CardDatabase,
) -> Result<Option<RolloutStop>, Box<dyn Error>> {
    let information = observe(state)?;
    if let Some(family) = detect_terminal_win(&information, cards) {
        return Ok(Some(RolloutStop::Terminal(family)));
    }

    if needs_automatic_advance(state) {
        match advance_automatic(state, cards) {
            Ok(_) => {}
            Err(RuleError::HorizonReached) => return Ok(Some(RolloutStop::Horizon)),
            Err(error) => return Err(Box::new(error)),
        }
        let information = observe(state)?;
        if let Some(family) = detect_terminal_win(&information, cards) {
            return Ok(Some(RolloutStop::Terminal(family)));
        }
    }

    Ok(None)
}

fn needs_automatic_advance(state: &TrueState) -> bool {
    state.stack.is_empty()
        && matches!(state.pending, PendingDecision::None)
        && matches!(
            (state.phase, state.window),
            (Phase::OpponentCycle, Window::None) | (Phase::Untap, Window::None)
        )
}

fn print_incomplete_baseline(
    opening_world: WorldId,
    hidden_world: WorldId,
    result: &RolloutResult,
) {
    println!(
        "INCOMPLETE_BASELINE\topening_world={}\thidden_world={}\tstop={:?}\tturn={}\ttrace_len={}",
        opening_world.0,
        hidden_world.0,
        result.stop,
        result.final_information.turn,
        result.trace.len(),
    );
    print_trace("BASELINE_TRACE", &result.trace, 0);
}

fn print_trace(label: &str, trace: &[RolloutStep], logical_offset: u64) {
    for step in trace {
        println!(
            "{label}\tindex={}\tlogical_index={}\tturn={}\tphase={:?}\twindow={:?}\tclass={:?}\tkey={:?}",
            step.index,
            logical_offset.saturating_add(u64::from(step.index)),
            step.turn,
            step.phase,
            step.window,
            step.class,
            step.key,
        );
    }
}

fn parse_u64(value: Option<String>, name: &str) -> Result<u64, Box<dyn Error>> {
    value
        .ok_or_else(|| io::Error::other(format!("missing {name}")))?
        .parse::<u64>()
        .map_err(|error| Box::new(error) as Box<dyn Error>)
}
