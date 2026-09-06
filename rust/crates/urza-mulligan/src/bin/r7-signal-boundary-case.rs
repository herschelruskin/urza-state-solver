use std::env;
use std::error::Error;

use urza_cards::R4CardDatabase;
use urza_core::TrueState;
use urza_info::observe;
use urza_mc::{MonteCarloConfig, MonteCarloError, evaluate};
use urza_mulligan::{
    R7_SIGNAL_BOUNDARY_BOUNDARY, R7_SIGNAL_BOUNDARY_FIRST_WORLD, R7_SIGNAL_BOUNDARY_R5_ROOT_SEED,
    R7_SIGNAL_BOUNDARY_R5_SAMPLES, R7_SIGNAL_BOUNDARY_STATE_VERSION,
    R7_SIGNAL_BOUNDARY_TEACHER_CANDIDATES, R7_SIGNAL_BOUNDARY_TEACHER_ROOT_SEED,
    R7_SIGNAL_BOUNDARY_TEACHER_SAMPLES, R7_SIGNAL_BOUNDARY_TEACHER_STEPS,
    R7_SIGNAL_BOUNDARY_VERSION, TeacherSearchConfig, TeacherSearchError,
    build_signal_boundary_cases, evaluate_teacher,
};
use urza_policy::DeterministicPolicy;
use urza_rng::{RootSeed, WorldId};
use urza_rules::{R2CardRole, WinFamily, detect_terminal_win};

#[derive(Debug)]
struct TeacherProbe {
    value: String,
    status: String,
    groups: String,
    actions: String,
    truncated: String,
    incomplete_branches: String,
}

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

    let (r5_value, r5_status) = match evaluate(
        &case.state,
        &cards,
        &policy,
        MonteCarloConfig {
            root: RootSeed::from_u64(R7_SIGNAL_BOUNDARY_R5_ROOT_SEED),
            first_world: world,
            samples: R7_SIGNAL_BOUNDARY_R5_SAMPLES,
            rollout_max_steps: urza_rollout::DEFAULT_MAX_STEPS,
        },
    ) {
        Ok(result) => (
            format!("{}/{}", result.wins(), result.samples()),
            String::from("complete"),
        ),
        Err(MonteCarloError::IncompleteWorld { stop, .. }) => {
            (String::from("NA"), format!("incomplete:{stop:?}"))
        }
        Err(error) => return Err(Box::new(error)),
    };

    let d0 = teacher_probe(&case.state, &cards, world, 0)?;
    let d1 = teacher_probe(&case.state, &cards, world, 1)?;
    let d2 = teacher_probe(&case.state, &cards, world, 2)?;

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
        "BOUNDARY_ROW\tcase={}\tfamily={}\ttier={}\tentry_terminal={}\tunsupported={}\thand={}\tbattlefield={}\tstack={}\tr5={}\tr5_status={}\tteacher_d0={}\td0_status={}\tteacher_d1={}\td1_status={}\tteacher_d2={}\td2_status={}\td0_groups={}\td1_groups={}\td2_groups={}\td0_actions={}\td1_actions={}\td2_actions={}\td0_truncated={}\td1_truncated={}\td2_truncated={}\td0_incomplete={}\td1_incomplete={}\td2_incomplete={}",
        case.case_name,
        case.family.label(),
        case.tier.label(),
        entry_terminal.map_or("none", WinFamily::label),
        unsupported,
        case.state.hand.len(),
        case.state.battlefield.len(),
        case.state.stack.len(),
        r5_value,
        r5_status,
        d0.value,
        d0.status,
        d1.value,
        d1.status,
        d2.value,
        d2.status,
        d0.groups,
        d1.groups,
        d2.groups,
        d0.actions,
        d1.actions,
        d2.actions,
        d0.truncated,
        d1.truncated,
        d2.truncated,
        d0.incomplete_branches,
        d1.incomplete_branches,
        d2.incomplete_branches
    );
    Ok(())
}

fn teacher_probe(
    state: &TrueState,
    cards: &R4CardDatabase,
    world: WorldId,
    depth: u8,
) -> Result<TeacherProbe, Box<dyn Error>> {
    match evaluate_teacher(
        state,
        cards,
        TeacherSearchConfig {
            root: RootSeed::from_u64(R7_SIGNAL_BOUNDARY_TEACHER_ROOT_SEED),
            first_world: world,
            samples: R7_SIGNAL_BOUNDARY_TEACHER_SAMPLES,
            max_choice_depth: depth,
            max_teacher_steps: R7_SIGNAL_BOUNDARY_TEACHER_STEPS,
            max_candidates_per_group: R7_SIGNAL_BOUNDARY_TEACHER_CANDIDATES,
            leaf_rollout_max_steps: urza_rollout::DEFAULT_MAX_STEPS,
        },
    ) {
        Ok(result) => Ok(TeacherProbe {
            value: format!(
                "{}/{}",
                result.score.total_wins, result.stats.sampled_worlds
            ),
            status: String::from("complete"),
            groups: result.stats.public_groups_evaluated.to_string(),
            actions: result.stats.public_actions_evaluated.to_string(),
            truncated: result.stats.truncated_public_groups.to_string(),
            incomplete_branches: result.stats.incomplete_candidate_branches.to_string(),
        }),
        Err(TeacherSearchError::IncompleteLeaf { stop, .. }) => Ok(incomplete_teacher_probe(
            format!("incomplete-leaf:{stop:?}"),
        )),
        Err(TeacherSearchError::AllCandidateBranchesIncomplete { candidate_count }) => Ok(
            incomplete_teacher_probe(format!("incomplete:all-candidates:{candidate_count}")),
        ),
        Err(error) => Err(Box::new(error)),
    }
}

fn incomplete_teacher_probe(status: String) -> TeacherProbe {
    TeacherProbe {
        value: String::from("NA"),
        status,
        groups: String::from("NA"),
        actions: String::from("NA"),
        truncated: String::from("NA"),
        incomplete_branches: String::from("NA"),
    }
}
