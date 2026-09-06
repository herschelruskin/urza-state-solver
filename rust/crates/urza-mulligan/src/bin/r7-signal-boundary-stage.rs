use std::env;
use std::error::Error;
use std::io::{self, Write};
use std::time::Instant;

use urza_cards::R4CardDatabase;
use urza_mc::{MonteCarloConfig, MonteCarloError, evaluate};
use urza_mulligan::{
    R7_SIGNAL_BOUNDARY_FIRST_WORLD, R7_SIGNAL_BOUNDARY_R5_ROOT_SEED,
    R7_SIGNAL_BOUNDARY_R5_SAMPLES, R7_SIGNAL_BOUNDARY_STATE_VERSION,
    R7_SIGNAL_BOUNDARY_TEACHER_CANDIDATES, R7_SIGNAL_BOUNDARY_TEACHER_ROOT_SEED,
    R7_SIGNAL_BOUNDARY_TEACHER_SAMPLES, R7_SIGNAL_BOUNDARY_TEACHER_STEPS,
    R7_SIGNAL_BOUNDARY_VERSION, TeacherSearchConfig, TeacherSearchError,
    build_signal_boundary_cases, evaluate_teacher,
};
use urza_policy::DeterministicPolicy;
use urza_rng::{RootSeed, WorldId};

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
        eprintln!("r7-signal-boundary-stage failed: {error}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), Box<dyn Error>> {
    let mut args = env::args().skip(1);
    let case_name = args.next().ok_or_else(|| {
        io::Error::other("usage: r7-signal-boundary-stage <case-name> <r5|d0|d1|d2>")
    })?;
    let stage = args.next().ok_or_else(|| {
        io::Error::other("usage: r7-signal-boundary-stage <case-name> <r5|d0|d1|d2>")
    })?;
    if args.next().is_some() {
        return Err(Box::new(io::Error::other(
            "usage: r7-signal-boundary-stage <case-name> <r5|d0|d1|d2>",
        )));
    }

    let cards = R4CardDatabase::load()?;
    let cases = build_signal_boundary_cases(&cards)?;
    let (index, case) = cases
        .into_iter()
        .enumerate()
        .find(|(_, case)| case.case_name == case_name)
        .ok_or_else(|| io::Error::other(format!("unknown R7 boundary case: {case_name}")))?;
    case.state.validate()?;

    let world_offset = u64::try_from(index)?;
    let world = WorldId(
        R7_SIGNAL_BOUNDARY_FIRST_WORLD
            .0
            .checked_add(world_offset)
            .ok_or_else(|| io::Error::other("R7 boundary world id overflow"))?,
    );

    println!("R7_SIGNAL_BOUNDARY\t{}", R7_SIGNAL_BOUNDARY_VERSION);
    println!("STATE_VERSION\t{}", R7_SIGNAL_BOUNDARY_STATE_VERSION);
    println!(
        "STAGE_BUDGET\tcase={}\tfamily={}\ttier={}\tstage={}\tcase_index={}\tworld={}\tr5_samples={}\tteacher_samples={}\tteacher_steps={}\tteacher_candidates={}",
        case.case_name,
        case.family.label(),
        case.tier.label(),
        stage,
        index,
        world.0,
        R7_SIGNAL_BOUNDARY_R5_SAMPLES,
        R7_SIGNAL_BOUNDARY_TEACHER_SAMPLES,
        R7_SIGNAL_BOUNDARY_TEACHER_STEPS,
        R7_SIGNAL_BOUNDARY_TEACHER_CANDIDATES
    );
    println!(
        "BOUNDARY_STAGE\tcase={}\tstage={}\tphase=start",
        case.case_name, stage
    );
    io::stdout().flush()?;

    let started = Instant::now();
    match stage.as_str() {
        "r5" => {
            let policy = DeterministicPolicy;
            let (value, status) = match evaluate(
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
            println!(
                "BOUNDARY_STAGE_RESULT\tcase={}\tstage=r5\tvalue={}\tstatus={}\telapsed_ms={}",
                case.case_name,
                value,
                status,
                started.elapsed().as_millis()
            );
        }
        "d0" | "d1" | "d2" => {
            let depth = stage
                .strip_prefix('d')
                .ok_or_else(|| io::Error::other(format!("unknown stage: {stage}")))?
                .parse::<u8>()?;
            let probe = teacher_probe(&case.state, &cards, world, depth)?;
            println!(
                "BOUNDARY_STAGE_RESULT\tcase={}\tstage={}\tvalue={}\tstatus={}\tgroups={}\tactions={}\ttruncated={}\tincomplete={}\telapsed_ms={}",
                case.case_name,
                stage,
                probe.value,
                probe.status,
                probe.groups,
                probe.actions,
                probe.truncated,
                probe.incomplete_branches,
                started.elapsed().as_millis()
            );
        }
        _ => {
            return Err(Box::new(io::Error::other(format!(
                "unknown stage {stage}; expected r5, d0, d1, or d2"
            ))));
        }
    }

    io::stdout().flush()?;
    Ok(())
}

fn teacher_probe(
    state: &urza_core::TrueState,
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
