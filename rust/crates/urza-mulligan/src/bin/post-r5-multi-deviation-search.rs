use std::collections::HashSet;
use std::collections::hash_map::DefaultHasher;
use std::error::Error;
use std::hash::{Hash, Hasher};
use std::io;

use urza_cards::R4CardDatabase;
use urza_core::{PendingDecision, Phase, TrueState, Window};
use urza_info::observe;
use urza_mc::sample_hidden_world;
use urza_mulligan::{
    InterpretationCatalog, KeptHand, MulliganStage, bridge_kept_hand, draw_fresh_seven,
    load_commander_deck, r7_pilot_generation_config, sample_pregame_context,
};
use urza_policy::{DeterministicPolicy, PolicyActionClass, PolicyPublicKey};
use urza_policy_bridge::CandidateBridge;
use urza_rng::WorldId;
use urza_rollout::{
    ForcedSemanticAction, RolloutConfig, RolloutResult, RolloutStep, RolloutStop, replay_trace,
    rollout, rollout_with_forced_semantic_actions,
};
use urza_rules::{RuleError, advance_automatic, detect_terminal_win};

const SEARCH_VERSION: &str = "post_r5_multi_deviation_search_v1_exact_liveness";

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
struct ProbeKey {
    state: TrueState,
    prefix_len: usize,
    prefix_hash_a: u64,
    prefix_hash_b: u64,
    class: PolicyActionClass,
    key: PolicyPublicKey,
}

#[derive(Debug, Default)]
struct SearchStats {
    decisions_scanned: Vec<u64>,
    deviations_tested: Vec<u64>,
    horizon_continuations: Vec<u64>,
    deduplicated_probes: Vec<u64>,
    max_trace: usize,
    max_candidates: usize,
}

impl SearchStats {
    fn new(max_deviations: usize) -> Self {
        let slots = max_deviations.saturating_add(1);
        Self {
            decisions_scanned: vec![0; slots],
            deviations_tested: vec![0; slots],
            horizon_continuations: vec![0; slots],
            deduplicated_probes: vec![0; slots],
            max_trace: 0,
            max_candidates: 0,
        }
    }
}

#[derive(Debug, Clone)]
struct Branch {
    forced: Vec<ForcedSemanticAction>,
    trace: Vec<RolloutStep>,
}

fn main() {
    if let Err(error) = run() {
        eprintln!("post-R5 multi-deviation search failed: {error}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), Box<dyn Error>> {
    let mut args = std::env::args().skip(1);
    let opening_offset = parse_u64(args.next(), "opening-offset")?;
    let hidden_start = parse_u64(args.next(), "hidden-start")?;
    let hidden_count = parse_u64(args.next(), "hidden-count")?;
    let max_deviations = parse_usize(args.next(), "max-deviations")?;
    if args.next().is_some() || hidden_count == 0 || !(2..=3).contains(&max_deviations) {
        return Err(Box::new(io::Error::other(
            "usage: post-r5-multi-deviation-search <opening-offset> <hidden-start> <hidden-count> <max-deviations>; hidden-count must be positive and max-deviations must be 2 or 3",
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

    println!("MULTI_DEVIATION_SEARCH\t{SEARCH_VERSION}");
    println!(
        "SOURCE\tprofile={}\topening_world={}\tstage={stage:?}\tseat={}\tcaverns={}\thand={}",
        generation.profile_version,
        opening_world.0,
        kept.pregame.seat,
        kept.pregame.gemstone_caverns_eligible,
        hand_names.join("|"),
    );
    println!(
        "SCAN\troot={:?}\thidden_start={}\thidden_count={}\tmax_steps={}\tmax_deviations={}\tprefix_mode=full_rollout_liveness_preserved\tdedup=exact_state_plus_executed_prefix_fingerprint",
        rollout_config.root, hidden_start, hidden_count, rollout_config.max_steps, max_deviations,
    );

    let mut stats = SearchStats::new(max_deviations);
    let mut worlds_scanned = 0_u64;

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
        stats.max_trace = stats.max_trace.max(baseline.trace.len());

        match baseline.stop {
            RolloutStop::Terminal(family) => {
                println!(
                    "BASELINE_POSITIVE\topening_world={}\thidden_world={}\tfamily={family:?}\tturn={}\ttrace_len={}",
                    opening_world.0,
                    hidden_world.0,
                    baseline.final_information.turn,
                    baseline.trace.len(),
                );
                print_trace("BASELINE_TRACE", &baseline.trace);
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

        let branch = Branch {
            forced: Vec::new(),
            trace: baseline.trace,
        };
        let mut seen_by_depth = (0..=max_deviations)
            .map(|_| HashSet::<ProbeKey>::new())
            .collect::<Vec<_>>();
        let found = explore_branch(
            opening_world,
            hidden_world,
            &exact,
            &cards,
            config,
            &branch,
            max_deviations,
            &mut seen_by_depth,
            &mut stats,
        )?;
        if found {
            return Ok(());
        }
    }

    println!(
        "NO_MULTI_DEVIATION_POSITIVE\topening_world={}\tworlds_scanned={}\tmax_deviations={}\tmax_trace={}\tmax_candidates={}\tliveness_history=preserved",
        opening_world.0, worlds_scanned, max_deviations, stats.max_trace, stats.max_candidates,
    );
    for depth in 1..=max_deviations {
        println!(
            "DEPTH_SUMMARY\tdepth={}\tdecisions_scanned={}\tdeviations_tested={}\thorizon_continuations={}\tdeduplicated_probes={}",
            depth,
            stats.decisions_scanned[depth],
            stats.deviations_tested[depth],
            stats.horizon_continuations[depth],
            stats.deduplicated_probes[depth],
        );
    }
    Ok(())
}

#[allow(clippy::too_many_arguments)]
fn explore_branch(
    opening_world: WorldId,
    hidden_world: WorldId,
    exact: &TrueState,
    cards: &R4CardDatabase,
    config: RolloutConfig,
    branch: &Branch,
    max_deviations: usize,
    seen_by_depth: &mut [HashSet<ProbeKey>],
    stats: &mut SearchStats,
) -> Result<bool, Box<dyn Error>> {
    let current_depth = branch.forced.len();
    if current_depth >= max_deviations {
        return Ok(false);
    }
    let next_depth = current_depth.saturating_add(1);
    let start_position = branch
        .forced
        .last()
        .map_or(0_usize, |forced| forced.index as usize + 1);

    for position in start_position..branch.trace.len() {
        let selected_step = &branch.trace[position];
        let prefix = &branch.trace[..position];
        let mut decision_state = replay_trace(exact.clone(), cards, config, prefix)?;
        if let Some(stop) = prepare_for_decision(&mut decision_state, cards)? {
            return Err(Box::new(io::Error::other(format!(
                "branch replay stopped at decision {} before expected step: {:?}",
                selected_step.index, stop
            ))));
        }

        let bridge = CandidateBridge::build(&decision_state, cards)?;
        let information = bridge.information();
        if information.turn != selected_step.turn
            || information.phase != selected_step.phase
            || information.window != selected_step.window
        {
            return Err(Box::new(io::Error::other(format!(
                "branch replay decision drift at step {}: expected turn {} {:?}/{:?}, got turn {} {:?}/{:?}",
                selected_step.index,
                selected_step.turn,
                selected_step.phase,
                selected_step.window,
                information.turn,
                information.phase,
                information.window,
            ))));
        }

        let selected_matches = bridge
            .candidates()
            .iter()
            .filter(|candidate| {
                candidate.class == selected_step.class && candidate.key == selected_step.key
            })
            .count();
        if selected_matches != 1 {
            return Err(Box::new(io::Error::other(format!(
                "expected one selected semantic candidate at step {}, found {}",
                selected_step.index, selected_matches
            ))));
        }

        stats.decisions_scanned[next_depth] = stats.decisions_scanned[next_depth].saturating_add(1);
        stats.max_candidates = stats.max_candidates.max(bridge.candidates().len());
        let (prefix_hash_a, prefix_hash_b) = trace_fingerprint(prefix);

        for alternate in bridge.candidates().iter().filter(|candidate| {
            candidate.class != selected_step.class || candidate.key != selected_step.key
        }) {
            let probe_key = ProbeKey {
                state: decision_state.clone(),
                prefix_len: prefix.len(),
                prefix_hash_a,
                prefix_hash_b,
                class: alternate.class,
                key: alternate.key.clone(),
            };
            if !seen_by_depth[next_depth].insert(probe_key) {
                stats.deduplicated_probes[next_depth] =
                    stats.deduplicated_probes[next_depth].saturating_add(1);
                continue;
            }

            let mut forced = branch.forced.clone();
            forced.push(ForcedSemanticAction {
                index: selected_step.index,
                class: alternate.class,
                key: alternate.key.clone(),
            });
            stats.deviations_tested[next_depth] =
                stats.deviations_tested[next_depth].saturating_add(1);
            let deviated = rollout_with_forced_semantic_actions(
                exact.clone(),
                cards,
                &DeterministicPolicy,
                config,
                &forced,
            )?;
            stats.max_trace = stats.max_trace.max(deviated.trace.len());

            if deviated.trace.len() <= position || deviated.trace[..position] != *prefix {
                return Err(Box::new(io::Error::other(format!(
                    "forced rollout prefix drift at depth {next_depth} step {}",
                    selected_step.index
                ))));
            }
            let forced_step = &deviated.trace[position];
            if forced_step.index != selected_step.index
                || forced_step.turn != information.turn
                || forced_step.phase != information.phase
                || forced_step.window != information.window
                || forced_step.class != alternate.class
                || forced_step.key != alternate.key
            {
                return Err(Box::new(io::Error::other(format!(
                    "forced rollout did not apply requested depth {next_depth} semantic action at step {}",
                    selected_step.index
                ))));
            }

            match deviated.stop {
                RolloutStop::Terminal(family) => {
                    println!(
                        "POSITIVE_MULTI_DEVIATION\topening_world={}\thidden_world={}\tdepth={}\tfamily={family:?}\tturn={}\ttrace_len={}",
                        opening_world.0,
                        hidden_world.0,
                        next_depth,
                        deviated.final_information.turn,
                        deviated.trace.len(),
                    );
                    print_forced_plan(&forced);
                    print_trace("DEVIATED_TRACE", &deviated.trace);
                    return Ok(true);
                }
                RolloutStop::Horizon => {
                    stats.horizon_continuations[next_depth] =
                        stats.horizon_continuations[next_depth].saturating_add(1);
                    if next_depth < max_deviations {
                        let child = Branch {
                            forced,
                            trace: deviated.trace,
                        };
                        if explore_branch(
                            opening_world,
                            hidden_world,
                            exact,
                            cards,
                            config,
                            &child,
                            max_deviations,
                            seen_by_depth,
                            stats,
                        )? {
                            return Ok(true);
                        }
                    }
                }
                RolloutStop::StepLimit | RolloutStop::NoCandidate => {
                    println!(
                        "INCOMPLETE_MULTI_DEVIATION\topening_world={}\thidden_world={}\tdepth={}\tstop={:?}\tturn={}\ttrace_len={}",
                        opening_world.0,
                        hidden_world.0,
                        next_depth,
                        deviated.stop,
                        deviated.final_information.turn,
                        deviated.trace.len(),
                    );
                    print_forced_plan(&forced);
                    print_trace("DEVIATED_TRACE", &deviated.trace);
                    return Err(Box::new(io::Error::other(format!(
                        "depth {next_depth} rollout stopped incompletely at {:?}",
                        deviated.stop
                    ))));
                }
            }
        }
    }

    Ok(false)
}

fn trace_fingerprint(trace: &[RolloutStep]) -> (u64, u64) {
    let mut first = DefaultHasher::new();
    0x5a_u8.hash(&mut first);
    trace.hash(&mut first);
    let mut second = DefaultHasher::new();
    0xa5_u8.hash(&mut second);
    trace.hash(&mut second);
    (first.finish(), second.finish())
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
    print_trace("BASELINE_TRACE", &result.trace);
}

fn print_forced_plan(forced: &[ForcedSemanticAction]) {
    for (depth, action) in forced.iter().enumerate() {
        println!(
            "FORCED_PLAN\tdepth={}\tindex={}\tclass={:?}\tkey={:?}",
            depth.saturating_add(1),
            action.index,
            action.class,
            action.key,
        );
    }
}

fn print_trace(label: &str, trace: &[RolloutStep]) {
    for step in trace {
        println!(
            "{label}\tindex={}\tlogical_index={}\tturn={}\tphase={:?}\twindow={:?}\tclass={:?}\tkey={:?}",
            step.index, step.index, step.turn, step.phase, step.window, step.class, step.key,
        );
    }
}

fn parse_u64(value: Option<String>, name: &str) -> Result<u64, Box<dyn Error>> {
    value
        .ok_or_else(|| io::Error::other(format!("missing {name}")))?
        .parse::<u64>()
        .map_err(|error| Box::new(error) as Box<dyn Error>)
}

fn parse_usize(value: Option<String>, name: &str) -> Result<usize, Box<dyn Error>> {
    value
        .ok_or_else(|| io::Error::other(format!("missing {name}")))?
        .parse::<usize>()
        .map_err(|error| Box::new(error) as Box<dyn Error>)
}
