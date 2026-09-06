use std::error::Error;

use urza_cards::R4CardDatabase;
use urza_mc::{compare_root_actions, evaluate};
use urza_policy::DeterministicPolicy;
use urza_rng::{RootSeed, WorldId};
use urza_rules::{Action, advance_automatic, apply_action};

use urza_mulligan::{
    InterpretationCatalog, TeacherSearchConfig, bridge_kept_hand, evaluate_teacher,
    load_commander_deck, r7_teacher_generation_config, start_mulligan_game,
};

const PROBE_WORLDS: [u64; 2] = [500_089, 500_140];
const TEACHER_SAMPLE_ROOT: u64 = 0x5237_5649_4142_4c45;

fn main() {
    if let Err(error) = run() {
        eprintln!("r7-viability failed: {error}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), Box<dyn Error>> {
    let deck = load_commander_deck()?;
    let cards = R4CardDatabase::load()?;
    let interpretation = InterpretationCatalog::load()?;
    let policy = DeterministicPolicy;
    let config = r7_teacher_generation_config();

    println!("R7_VIABILITY\tr7_teacher_policy_viability_v3");
    println!("PROFILE\t{}", config.profile_version);
    println!("ROLLOUT_SAMPLES\t{}", config.evaluation.rollout.samples);
    println!("TEACHER_BOUND\tsamples=2\tchoice_depth=3\tsteps=10\tcandidate_cap=8");

    for (probe_index, world_value) in PROBE_WORLDS.into_iter().enumerate() {
        let world = WorldId(world_value);
        let opening = start_mulligan_game(&deck, config.opening_root, world)?;
        let visible = opening
            .current_seven()
            .iter()
            .map(|card| {
                interpretation
                    .card(*card)
                    .map(|metadata| metadata.deck_name.as_str())
                    .unwrap_or("<unknown>")
            })
            .collect::<Vec<_>>()
            .join("|");
        let kept = opening.clone().keep(&[])?;
        let bridge = bridge_kept_hand(&kept, &deck, config.opening_root, world)?;

        let baseline = evaluate(
            bridge.true_state(),
            &cards,
            &policy,
            config.evaluation.rollout,
        )?;

        // This one-step comparison is retained as the explicit diagnostic that
        // motivated the R7 teacher: after choosing one main-phase root action,
        // continuation immediately falls back to the structural R5 selector.
        let mut first_main = bridge.true_state().clone();
        advance_automatic(&mut first_main, &cards)?;
        apply_action(&mut first_main, &cards, Action::PassPriority)?;
        apply_action(&mut first_main, &cards, Action::PassPriority)?;
        let roots = compare_root_actions(&first_main, &cards, &policy, config.evaluation.rollout)?;
        let winning_root_actions = roots
            .evaluations
            .iter()
            .filter(|evaluation| evaluation.result.wins() > 0)
            .count();
        let best_root_wins = roots
            .evaluations
            .iter()
            .map(|evaluation| evaluation.result.wins())
            .max()
            .unwrap_or(0);

        let teacher = evaluate_teacher(
            bridge.true_state(),
            &cards,
            TeacherSearchConfig {
                root: RootSeed::from_u64(TEACHER_SAMPLE_ROOT),
                first_world: WorldId(800_000 + u64::try_from(probe_index)? * 16),
                samples: 2,
                max_choice_depth: 3,
                max_teacher_steps: 10,
                max_candidates_per_group: 8,
                leaf_rollout_max_steps: 4096,
            },
        )?;

        println!(
            "PROBE\tworld={}\tseat={}\tcaverns={}\thand={}\tbaseline_wins={}/{}\tone_step_root_actions={}\tone_step_winning_roots={}\tone_step_best={}/{}\tteacher_wins={}/{}\tteacher_groups={}\tteacher_actions={}\tteacher_forced={}\tteacher_truncated={}\tteacher_leaves={}\tteacher_splits={}\tteacher_max_full={}\tteacher_max_retained={}",
            world_value,
            opening.pregame().seat,
            opening.pregame().gemstone_caverns_eligible,
            visible,
            baseline.wins(),
            baseline.samples(),
            roots.evaluations.len(),
            winning_root_actions,
            best_root_wins,
            roots.worlds.len(),
            teacher.score.total_wins,
            teacher.stats.sampled_worlds,
            teacher.stats.public_groups_evaluated,
            teacher.stats.public_actions_evaluated,
            teacher.stats.forced_public_steps,
            teacher.stats.truncated_public_groups,
            teacher.stats.leaf_rollouts,
            teacher.stats.observation_splits,
            teacher.stats.max_full_candidate_count,
            teacher.stats.max_retained_candidate_count,
        );
    }

    Ok(())
}
