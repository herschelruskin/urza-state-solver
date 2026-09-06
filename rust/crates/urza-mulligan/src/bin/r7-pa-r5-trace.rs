use std::collections::BTreeMap;
use std::error::Error;

use urza_cards::R4CardDatabase;
use urza_mulligan::{
    R7_SIGNAL_BOUNDARY_FIRST_WORLD, R7_SIGNAL_BOUNDARY_R5_ROOT_SEED, R7_SIGNAL_BOUNDARY_VERSION,
    build_signal_boundary_cases,
};
use urza_policy::{DeterministicPolicy, PolicyActionClass};
use urza_rng::{RootSeed, WorldId};
use urza_rollout::{DEFAULT_MAX_STEPS, RolloutConfig, rollout};

const CASE_NAME: &str = "pa-basalt-two-hand";
const EDGE_ACTIONS: usize = 20;
const TOP_SEMANTIC_KEYS: usize = 30;

fn main() {
    if let Err(error) = run() {
        eprintln!("r7-pa-r5-trace failed: {error}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), Box<dyn Error>> {
    let cards = R4CardDatabase::load()?;
    let cases = build_signal_boundary_cases(&cards)?;
    let (index, case) = cases
        .into_iter()
        .enumerate()
        .find(|(_, case)| case.case_name == CASE_NAME)
        .ok_or_else(|| std::io::Error::other("missing PA two-hand boundary case"))?;
    case.state.validate()?;

    let world_offset = u64::try_from(index)?;
    let world = WorldId(
        R7_SIGNAL_BOUNDARY_FIRST_WORLD
            .0
            .checked_add(world_offset)
            .ok_or_else(|| std::io::Error::other("R7 boundary world id overflow"))?,
    );
    let policy = DeterministicPolicy;
    let result = rollout(
        case.state,
        &cards,
        &policy,
        RolloutConfig {
            root: RootSeed::from_u64(R7_SIGNAL_BOUNDARY_R5_ROOT_SEED),
            world,
            max_steps: DEFAULT_MAX_STEPS,
        },
    )?;

    println!("R7_PA_R5_TRACE\t{}", R7_SIGNAL_BOUNDARY_VERSION);
    println!(
        "TRACE_BUDGET\tcase={}\tcase_index={}\tworld={}\tmax_steps={}",
        CASE_NAME, index, world.0, DEFAULT_MAX_STEPS
    );
    println!(
        "TRACE_RESULT\tstop={:?}\tsteps={}\tturn={}\tphase={:?}\twindow={:?}\thand={}\tbattlefield={}\tstack={}\tmana={:?}\tpending={:?}",
        result.stop,
        result.trace.len(),
        result.final_state.turn,
        result.final_state.phase,
        result.final_state.window,
        result.final_state.hand.len(),
        result.final_state.battlefield.len(),
        result.final_state.stack.len(),
        result.final_state.mana,
        result.final_state.pending.kind()
    );

    let mut class_counts: BTreeMap<PolicyActionClass, usize> = BTreeMap::new();
    let mut transition_counts: BTreeMap<(PolicyActionClass, PolicyActionClass), usize> =
        BTreeMap::new();
    let mut semantic_counts: BTreeMap<String, usize> = BTreeMap::new();

    for step in &result.trace {
        *class_counts.entry(step.class).or_default() += 1;
        let semantic = format!(
            "class={:?},kind={},card={:?},source={:?},target={:?},parameter={:?},secondary={},detail={:?}",
            step.class,
            step.key.kind,
            step.key.card,
            step.key.source,
            step.key.target,
            step.key.parameter,
            step.key.secondary,
            step.key.detail
        );
        *semantic_counts.entry(semantic).or_default() += 1;
    }

    for pair in result.trace.windows(2) {
        *transition_counts
            .entry((pair[0].class, pair[1].class))
            .or_default() += 1;
    }

    for (class, count) in class_counts {
        println!("TRACE_CLASS_COUNT\tclass={class:?}\tcount={count}");
    }
    for ((from, to), count) in transition_counts {
        println!("TRACE_TRANSITION_COUNT\tfrom={from:?}\tto={to:?}\tcount={count}");
    }

    let mut semantic_counts: Vec<_> = semantic_counts.into_iter().collect();
    semantic_counts.sort_by(|left, right| {
        right
            .1
            .cmp(&left.1)
            .then_with(|| left.0.cmp(&right.0))
    });
    for (rank, (semantic, count)) in semantic_counts
        .into_iter()
        .take(TOP_SEMANTIC_KEYS)
        .enumerate()
    {
        println!(
            "TRACE_SEMANTIC_COUNT\trank={}\tcount={}\t{}",
            rank + 1,
            count,
            semantic
        );
    }

    for step in result.trace.iter().take(EDGE_ACTIONS) {
        println!(
            "TRACE_HEAD\tindex={}\tturn={}\tphase={:?}\twindow={:?}\tclass={:?}\tkey={:?}",
            step.index, step.turn, step.phase, step.window, step.class, step.key
        );
    }
    let tail_start = result.trace.len().saturating_sub(EDGE_ACTIONS);
    for step in &result.trace[tail_start..] {
        println!(
            "TRACE_TAIL\tindex={}\tturn={}\tphase={:?}\twindow={:?}\tclass={:?}\tkey={:?}",
            step.index, step.turn, step.phase, step.window, step.class, step.key
        );
    }

    for permanent in result.final_state.battlefield.permanents() {
        println!(
            "TRACE_FINAL_PERMANENT\tobject={:?}\tcard={:?}\ttapped={}\tattached_to={:?}\tmode={:?}",
            permanent.object_id,
            permanent.card,
            permanent.tapped,
            permanent.attached_to,
            permanent.mode
        );
    }
    println!("TRACE_FINAL_HAND\tcards={:?}", result.final_state.hand.cards());

    Ok(())
}
