use std::env;
use std::error::Error;
use std::io::{self, Write};
use std::time::Instant;

use urza_cards::R4CardDatabase;
use urza_info::observe;
use urza_mc::{MonteCarloConfig, MonteCarloError, evaluate};
use urza_mulligan::{
    POST_R7_REAL_STATE_BOUNDARY, POST_R7_REAL_STATE_BOUNDARY_VERSION,
    POST_R7_REAL_STATE_FIRST_PROBE_WORLD, POST_R7_REAL_STATE_R5_ROOT_SEED,
    POST_R7_REAL_STATE_R5_SAMPLES, POST_R7_REAL_STATE_SOURCE_VERSION,
    POST_R7_REAL_STATE_TEACHER_CANDIDATES, POST_R7_REAL_STATE_TEACHER_ROOT_SEED,
    POST_R7_REAL_STATE_TEACHER_SAMPLES, POST_R7_REAL_STATE_TEACHER_STEPS, TeacherSearchConfig,
    TeacherSearchError, build_post_r7_real_state_cases, evaluate_teacher,
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
    ceiling_pruned: String,
    cache_hits: String,
    cache_inserts: String,
}

fn main() {
    if let Err(error) = run() {
        eprintln!("post-r7-real-state-boundary failed: {error}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), Box<dyn Error>> {
    let mut args = env::args().skip(1);
    let tier_name = args.next().ok_or_else(|| {
        io::Error::other(
            "usage: post-r7-real-state-boundary <kept-opening|turn-1-main|turn-2-main|late-real-state> <r5|d0|d1|d2|d3>",
        )
    })?;
    let probe_name = args.next().ok_or_else(|| {
        io::Error::other(
            "usage: post-r7-real-state-boundary <kept-opening|turn-1-main|turn-2-main|late-real-state> <r5|d0|d1|d2|d3>",
        )
    })?;
    if args.next().is_some() {
        return Err(Box::new(io::Error::other(
            "usage: post-r7-real-state-boundary <kept-opening|turn-1-main|turn-2-main|late-real-state> <r5|d0|d1|d2|d3>",
        )));
    }

    let cards = R4CardDatabase::load()?;
    let cases = build_post_r7_real_state_cases(&cards)?;
    let (index, case) = cases
        .iter()
        .enumerate()
        .find(|(_, case)| case.tier.label() == tier_name)
        .ok_or_else(|| io::Error::other(format!("unknown post-R7 real-state tier: {tier_name}")))?;
    let world = WorldId(
        POST_R7_REAL_STATE_FIRST_PROBE_WORLD
            .0
            .checked_add(u64::try_from(index)?)
            .ok_or_else(|| io::Error::other("post-R7 probe world id overflow"))?,
    );
    let information = observe(&case.state)?;

    println!(
        "POST_R7_REAL_STATE_BOUNDARY\t{}",
        POST_R7_REAL_STATE_BOUNDARY_VERSION
    );
    println!("SOURCE_VERSION\t{}", POST_R7_REAL_STATE_SOURCE_VERSION);
    println!("BOUNDARY\t{}", POST_R7_REAL_STATE_BOUNDARY);
    println!(
        "SOURCE\ttier={}\topening_world={}\thidden_world={}\tprefix_actions={}\ttrace_actions={}\tstop={:?}",
        case.tier.label(),
        case.source_opening_world.0,
        case.source_hidden_world.0,
        case.source_action_prefix_len,
        case.source_trace_len,
        case.source_stop
    );
    println!(
        "STATE\ttier={}\tturn={}\tphase={:?}\twindow={:?}\thand={}\tbattlefield={}\tstack={}\tknown_top={}\tknown_bottom={}",
        case.tier.label(),
        information.turn,
        information.phase,
        information.window,
        case.state.hand.len(),
        case.state.battlefield.len(),
        case.state.stack.len(),
        information.library.known_top.len(),
        information.library.known_bottom.len()
    );
    println!(
        "BUDGET\ttier={}\tprobe={}\tprobe_world={}\tr5_samples={}\tteacher_samples={}\tteacher_steps={}\tteacher_candidates={}",
        case.tier.label(),
        probe_name,
        world.0,
        POST_R7_REAL_STATE_R5_SAMPLES,
        POST_R7_REAL_STATE_TEACHER_SAMPLES,
        POST_R7_REAL_STATE_TEACHER_STEPS,
        POST_R7_REAL_STATE_TEACHER_CANDIDATES
    );
    println!(
        "REAL_STATE_STAGE\ttier={}\tprobe={}\tphase=start",
        case.tier.label(),
        probe_name
    );
    io::stdout().flush()?;

    let started = Instant::now();
    match probe_name.as_str() {
        "r5" => {
            let (value, status) = match evaluate(
                &case.state,
                &cards,
                &DeterministicPolicy,
                MonteCarloConfig {
                    root: RootSeed::from_u64(POST_R7_REAL_STATE_R5_ROOT_SEED),
                    first_world: world,
                    samples: POST_R7_REAL_STATE_R5_SAMPLES,
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
                "REAL_STATE_RESULT\ttier={}\tprobe=r5\tvalue={}\tstatus={}\telapsed_ms={}",
                case.tier.label(),
                value,
                status,
                started.elapsed().as_millis()
            );
        }
        "d0" | "d1" | "d2" | "d3" => {
            let depth = probe_name
                .strip_prefix('d')
                .ok_or_else(|| io::Error::other(format!("unknown probe: {probe_name}")))?
                .parse::<u8>()?;
            let probe = teacher_probe(&case.state, &cards, world, depth)?;
            println!(
                "REAL_STATE_RESULT\ttier={}\tprobe={}\tvalue={}\tstatus={}\tgroups={}\tactions={}\ttruncated={}\tincomplete={}\tceiling_pruned={}\tcache_hits={}\tcache_inserts={}\telapsed_ms={}",
                case.tier.label(),
                probe_name,
                probe.value,
                probe.status,
                probe.groups,
                probe.actions,
                probe.truncated,
                probe.incomplete_branches,
                probe.ceiling_pruned,
                probe.cache_hits,
                probe.cache_inserts,
                started.elapsed().as_millis()
            );
        }
        _ => {
            return Err(Box::new(io::Error::other(format!(
                "unknown probe {probe_name}; expected r5, d0, d1, d2, or d3"
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
            root: RootSeed::from_u64(POST_R7_REAL_STATE_TEACHER_ROOT_SEED),
            first_world: world,
            samples: POST_R7_REAL_STATE_TEACHER_SAMPLES,
            max_choice_depth: depth,
            max_teacher_steps: POST_R7_REAL_STATE_TEACHER_STEPS,
            max_candidates_per_group: POST_R7_REAL_STATE_TEACHER_CANDIDATES,
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
            ceiling_pruned: result.stats.ceiling_pruned_public_actions.to_string(),
            cache_hits: result.stats.subtree_cache_hits.to_string(),
            cache_inserts: result.stats.subtree_cache_inserts.to_string(),
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
        ceiling_pruned: String::from("NA"),
        cache_hits: String::from("NA"),
        cache_inserts: String::from("NA"),
    }
}
