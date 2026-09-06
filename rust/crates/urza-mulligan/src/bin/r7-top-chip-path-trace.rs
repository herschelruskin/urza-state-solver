use std::collections::BTreeMap;
use std::error::Error;
use std::io;

use urza_cards::R4CardDatabase;
use urza_core::TrueState;
use urza_mc::sample_hidden_world;
use urza_mulligan::{
    R7_SIGNAL_BOUNDARY_FIRST_WORLD, R7_SIGNAL_BOUNDARY_TEACHER_CANDIDATES,
    R7_SIGNAL_BOUNDARY_TEACHER_ROOT_SEED, build_signal_boundary_cases,
};
use urza_policy::{DeterministicPolicy, PolicyActionClass, PolicyCandidate};
use urza_policy_bridge::CandidateBridge;
use urza_rng::{LogicalEventId, RootSeed, WorldId};
use urza_rollout::{DEFAULT_MAX_STEPS, RolloutConfig, rollout_with_logical_event_offset};
use urza_rules::{GameRngContext, apply_action_with_rng, detect_terminal_win};

const CASE_NAME: &str = "top-chip-two-hand";

fn main() {
    if let Err(error) = run() {
        eprintln!("r7-top-chip-path-trace failed: {error}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), Box<dyn Error>> {
    let cards = R4CardDatabase::load()?;
    let top = cards.card_id_by_name("Sensei's Divining Top")?;
    let gadgeteer = cards.card_id_by_name("Forensic Gadgeteer")?;
    let cases = build_signal_boundary_cases(&cards)?;
    let (index, case) = cases
        .into_iter()
        .enumerate()
        .find(|(_, case)| case.case_name == CASE_NAME)
        .ok_or_else(|| io::Error::other("missing Top Chip two-hand boundary case"))?;
    case.state.validate()?;

    let world = WorldId(
        R7_SIGNAL_BOUNDARY_FIRST_WORLD
            .0
            .checked_add(u64::try_from(index)?)
            .ok_or_else(|| io::Error::other("R7 boundary world id overflow"))?,
    );
    let root = RootSeed::from_u64(R7_SIGNAL_BOUNDARY_TEACHER_ROOT_SEED);
    let mut state = sample_hidden_world(&case.state, root, world)?;
    let mut logical_event = 0_u64;

    println!("R7_TOP_CHIP_PATH_TRACE\tv2");
    println!(
        "TRACE_BUDGET\tcase={}\tcase_index={}\tworld={}\tcandidate_cap={}\tleaf_steps={}",
        CASE_NAME, index, world.0, R7_SIGNAL_BOUNDARY_TEACHER_CANDIDATES, DEFAULT_MAX_STEPS
    );
    println!("PATH_PLAN\tcast-gadgeteer -> pass/resolve-gadgeteer -> cast-top -> frozen-r5-leaf");

    let (bridge, retained) = snapshot("root", &state, &cards)?;
    let Some(cast_gadgeteer) = retained
        .iter()
        .find(|candidate| {
            candidate.class == PolicyActionClass::CastSpell && candidate.key.card == Some(gadgeteer)
        })
        .cloned()
    else {
        println!("PATH_RESULT\tstatus=missing-retained-cast-gadgeteer-at-root");
        return Ok(());
    };
    apply_selected(
        "cast-gadgeteer",
        &mut state,
        &cards,
        root,
        world,
        &mut logical_event,
        &bridge,
        &cast_gadgeteer,
    )?;

    let (bridge, retained) = snapshot("after-cast-gadgeteer", &state, &cards)?;
    let Some(pass) = retained
        .iter()
        .find(|candidate| candidate.class == PolicyActionClass::PassPriority)
        .cloned()
    else {
        println!("PATH_RESULT\tstatus=missing-retained-pass-after-gadgeteer");
        return Ok(());
    };
    apply_selected(
        "pass-resolve-gadgeteer",
        &mut state,
        &cards,
        root,
        world,
        &mut logical_event,
        &bridge,
        &pass,
    )?;

    let (bridge, retained) = snapshot("after-resolve-gadgeteer", &state, &cards)?;
    let Some(cast_top) = retained
        .iter()
        .find(|candidate| {
            candidate.class == PolicyActionClass::CastSpell && candidate.key.card == Some(top)
        })
        .cloned()
    else {
        println!("PATH_RESULT\tstatus=missing-retained-cast-top");
        return Ok(());
    };
    apply_selected(
        "cast-top",
        &mut state,
        &cards,
        root,
        world,
        &mut logical_event,
        &bridge,
        &cast_top,
    )?;

    let before_leaf = CandidateBridge::build(&state, &cards)?;
    println!(
        "LEAF_START\tlogical_event={}\thand={}\tbattlefield={}\tstack={}\tcandidates={}",
        logical_event,
        state.hand.len(),
        state.battlefield.len(),
        state.stack.len(),
        before_leaf.candidates().len()
    );

    let result = rollout_with_logical_event_offset(
        state,
        &cards,
        &DeterministicPolicy,
        RolloutConfig {
            root,
            world,
            max_steps: DEFAULT_MAX_STEPS,
        },
        logical_event,
    )?;
    let terminal = detect_terminal_win(&result.final_information, &cards)
        .map(|family| family.label())
        .unwrap_or("none");
    println!(
        "PATH_RESULT\tstatus=complete\tstop={:?}\tsteps={}\tterminal={}\tturn={}\thand={}\tbattlefield={}\tstack={}",
        result.stop,
        result.trace.len(),
        terminal,
        result.final_state.turn,
        result.final_state.hand.len(),
        result.final_state.battlefield.len(),
        result.final_state.stack.len()
    );

    Ok(())
}

fn snapshot(
    label: &str,
    state: &TrueState,
    cards: &R4CardDatabase,
) -> Result<(CandidateBridge, Vec<PolicyCandidate>), Box<dyn Error>> {
    let bridge = CandidateBridge::build(state, cards)?;
    let retained =
        retain_bounded_candidates(bridge.candidates(), R7_SIGNAL_BOUNDARY_TEACHER_CANDIDATES);
    let mut full_classes = BTreeMap::<PolicyActionClass, usize>::new();
    let mut retained_classes = BTreeMap::<PolicyActionClass, usize>::new();
    for candidate in bridge.candidates() {
        *full_classes.entry(candidate.class).or_default() += 1;
    }
    for candidate in &retained {
        *retained_classes.entry(candidate.class).or_default() += 1;
    }
    println!(
        "CANDIDATE_SNAPSHOT\tlabel={}\tturn={}\tphase={:?}\twindow={:?}\thand={}\tbattlefield={}\tstack={}\tfull={}\tretained={}\tfull_classes={:?}\tretained_classes={:?}",
        label,
        state.turn,
        state.phase,
        state.window,
        state.hand.len(),
        state.battlefield.len(),
        state.stack.len(),
        bridge.candidates().len(),
        retained.len(),
        full_classes,
        retained_classes
    );
    for (index, candidate) in retained.iter().enumerate() {
        println!(
            "RETAINED\tlabel={}\trank={}\tclass={:?}\tkey={:?}",
            label,
            index + 1,
            candidate.class,
            candidate.key
        );
    }
    Ok((bridge, retained))
}

#[allow(clippy::too_many_arguments)]
fn apply_selected(
    label: &str,
    state: &mut TrueState,
    cards: &R4CardDatabase,
    root: RootSeed,
    world: WorldId,
    logical_event: &mut u64,
    bridge: &CandidateBridge,
    selected: &PolicyCandidate,
) -> Result<(), Box<dyn Error>> {
    let action = bridge
        .resolved_action(selected.token)
        .ok_or_else(|| io::Error::other("selected retained candidate could not resolve"))?;
    println!(
        "PATH_ACTION\tlabel={}\tlogical_event={}\tclass={:?}\tkey={:?}\taction={:?}",
        label, *logical_event, selected.class, selected.key, action
    );
    apply_action_with_rng(
        state,
        cards,
        action,
        GameRngContext {
            root,
            world,
            logical_event: LogicalEventId(*logical_event),
        },
    )?;
    *logical_event = logical_event
        .checked_add(1)
        .ok_or_else(|| io::Error::other("logical event overflow"))?;
    Ok(())
}

fn retain_bounded_candidates(candidates: &[PolicyCandidate], cap: usize) -> Vec<PolicyCandidate> {
    if candidates.len() <= cap {
        return candidates.to_vec();
    }

    let mut buckets: BTreeMap<PolicyActionClass, Vec<PolicyCandidate>> = BTreeMap::new();
    for candidate in candidates {
        buckets
            .entry(candidate.class)
            .or_default()
            .push(candidate.clone());
    }

    let classes: Vec<_> = buckets.keys().copied().collect();
    if classes.len() > cap {
        return evenly_spaced(candidates, cap);
    }

    let mut quotas: BTreeMap<PolicyActionClass, usize> =
        classes.iter().copied().map(|class| (class, 1)).collect();
    let mut remaining = cap - classes.len();
    while remaining > 0 {
        let mut progressed = false;
        for class in &classes {
            let current = quotas[class];
            let available = buckets[class].len();
            if current < available {
                quotas.insert(*class, current + 1);
                remaining -= 1;
                progressed = true;
                if remaining == 0 {
                    break;
                }
            }
        }
        if !progressed {
            break;
        }
    }

    let mut retained = Vec::new();
    for class in classes {
        retained.extend(evenly_spaced(&buckets[&class], quotas[&class]));
    }
    retained.sort_unstable_by(|left, right| {
        left.class
            .cmp(&right.class)
            .then_with(|| left.key.cmp(&right.key))
    });
    retained
}

fn evenly_spaced<T: Clone>(items: &[T], count: usize) -> Vec<T> {
    if count == items.len() {
        return items.to_vec();
    }
    if count == 1 {
        return vec![items[items.len() / 2].clone()];
    }

    let last = items.len() - 1;
    (0..count)
        .map(|index| items[index * last / (count - 1)].clone())
        .collect()
}
