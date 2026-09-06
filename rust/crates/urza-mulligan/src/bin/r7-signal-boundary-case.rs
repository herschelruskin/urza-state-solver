use std::env;
use std::error::Error;

use urza_cards::R4CardDatabase;
use urza_info::observe;
use urza_mc::{MonteCarloConfig, evaluate};
use urza_mulligan::{
    R7_SIGNAL_BOUNDARY_BOUNDARY, R7_SIGNAL_BOUNDARY_FIRST_WORLD, R7_SIGNAL_BOUNDARY_R5_ROOT_SEED,
    R7_SIGNAL_BOUNDARY_R5_SAMPLES, R7_SIGNAL_BOUNDARY_STATE_VERSION,
    R7_SIGNAL_BOUNDARY_TEACHER_CANDIDATES, R7_SIGNAL_BOUNDARY_TEACHER_ROOT_SEED,
    R7_SIGNAL_BOUNDARY_TEACHER_SAMPLES, R7_SIGNAL_BOUNDARY_TEACHER_STEPS,
    R7_SIGNAL_BOUNDARY_VERSION, TeacherSearchConfig, build_signal_boundary_cases, evaluate_teacher,
};
use urza_policy::DeterministicPolicy;
use urza_rng::{RootSeed, WorldId};
use urza_rules::{R2CardRole, WinFamily, detect_terminal_win};

fn main() {
    if let Err(error) = run() {
        eprintln!("r7-signal-boundary-case failed: {error}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), Box<dyn Error>> {
    let case_name = env::args()
        .nth(1)
        .ok_or_else(|| std::io::Error::other("usage: r7-signal-boundary-case <case-name>"))?;
    let cards = R4CardDatabase::load()?;
    let cases = build_signal_boundary_cases(&cards)?;
    let (index, case) = cases
        .into_iter()
        .enumerate()
        .find(|(_, case)| case.case_name == case_name)
        .ok_or_else(|| std::io::Error::other(format!("unknown R7 boundary case: {case_name}")))?;

    case.state.validate()?;
    let world_offset = u64::try_from(index)?;
    let world = WorldId(
        R7_SIGNAL_BOUNDARY_FIRST_WORLD
            .0
            .checked_add(world_offset)
            .ok_or_else(|| std::io::Error::other("R7 boundary world id overflow"))?,
    );
    let information = observe(&case.state)?;
    let entry_terminal = detect_terminal_win(&information, &cards);
    let policy = DeterministicPolicy;
    let r5 = evaluate(
        &case.state,
        &cards,
        &policy,
        MonteCarloConfig {
            root: RootSeed::from_u64(R7_SIGNAL_BOUNDARY_R5_ROOT_SEED),
            first_world: world,
            samples: R7_SIGNAL_BOUNDARY_R5_SAMPLES,
            rollout_max_steps: urza_rollout::DEFAULT_MAX_STEPS,
        },
    )?;

    let mut teacher = Vec::with_capacity(3);
    for depth in [0_u8, 1, 2] {
        teacher.push((
            depth,
            evaluate_teacher(
                &case.state,
                &cards,
                TeacherSearchConfig {
                    root: RootSeed::from_u64(R7_SIGNAL_BOUNDARY_TEACHER_ROOT_SEED),
                    first_world: world,
                    samples: R7_SIGNAL_BOUNDARY_TEACHER_SAMPLES,
                    max_choice_depth: depth,
                    max_teacher_steps: R7_SIGNAL_BOUNDARY_TEACHER_STEPS,
                    max_candidates_per_group: R7_SIGNAL_BOUNDARY_TEACHER_CANDIDATES,
                    leaf_rollout_max_steps: urza_rollout::DEFAULT_MAX_STEPS,
                },
            )?,
        ));
    }

    let d0 = &teacher[0].1;
    let d1 = &teacher[1].1;
    let d2 = &teacher[2].1;
    let unsupported = u32::try_from(
        case.involved_cards
            .iter()
            .filter(|card| {
                cards
                    .profile(**card)
                    .is_none_or(|profile| profile.role == R2CardRole::Unsupported)
            })
            .count(),
    )?;

    println!("R7_SIGNAL_BOUNDARY\t{}", R7_SIGNAL_BOUNDARY_VERSION);
    println!("STATE_VERSION\t{}", R7_SIGNAL_BOUNDARY_STATE_VERSION);
    println!("BOUNDARY\t{}", R7_SIGNAL_BOUNDARY_BOUNDARY);
    println!(
        "BUDGET\tcase={}\tcase_index={}\tworld={}\tr5_samples={}\tteacher_samples={}\tteacher_steps={}\tteacher_candidates={}\tteacher_depths=0,1,2",
        case.case_name,
        index,
        world.0,
        R7_SIGNAL_BOUNDARY_R5_SAMPLES,
        R7_SIGNAL_BOUNDARY_TEACHER_SAMPLES,
        R7_SIGNAL_BOUNDARY_TEACHER_STEPS,
        R7_SIGNAL_BOUNDARY_TEACHER_CANDIDATES
    );
    println!(
        "BOUNDARY_ROW\tcase={}\tfamily={}\ttier={}\tentry_terminal={}\tunsupported={}\thand={}\tbattlefield={}\tstack={}\tr5={}/{}\tteacher_d0={}/{}\tteacher_d1={}/{}\tteacher_d2={}/{}\td0_groups={}\td1_groups={}\td2_groups={}\td0_actions={}\td1_actions={}\td2_actions={}\td0_truncated={}\td1_truncated={}\td2_truncated={}\td0_incomplete={}\td1_incomplete={}\td2_incomplete={}",
        case.case_name,
        case.family.label(),
        case.tier.label(),
        entry_terminal.map_or("none", WinFamily::label),
        unsupported,
        case.state.hand.len(),
        case.state.battlefield.len(),
        case.state.stack.len(),
        r5.wins(),
        r5.samples(),
        d0.score.total_wins,
        d0.stats.sampled_worlds,
        d1.score.total_wins,
        d1.stats.sampled_worlds,
        d2.score.total_wins,
        d2.stats.sampled_worlds,
        d0.stats.public_groups_evaluated,
        d1.stats.public_groups_evaluated,
        d2.stats.public_groups_evaluated,
        d0.stats.public_actions_evaluated,
        d1.stats.public_actions_evaluated,
        d2.stats.public_actions_evaluated,
        d0.stats.truncated_public_groups,
        d1.stats.truncated_public_groups,
        d2.stats.truncated_public_groups,
        d0.stats.incomplete_candidate_branches,
        d1.stats.incomplete_candidate_branches,
        d2.stats.incomplete_candidate_branches
    );
    Ok(())
}
