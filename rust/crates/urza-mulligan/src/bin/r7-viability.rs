use std::error::Error;

use urza_cards::R4CardDatabase;
use urza_mc::{compare_root_actions, evaluate};
use urza_policy::DeterministicPolicy;
use urza_rng::WorldId;

use urza_mulligan::{
    InterpretationCatalog, bridge_kept_hand, load_commander_deck, r7_teacher_generation_config,
    start_mulligan_game,
};

const PROBE_WORLDS: [u64; 2] = [500_089, 500_140];

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

    println!("R7_VIABILITY\tr7_teacher_policy_viability_v1");
    println!("PROFILE\t{}", config.profile_version);
    println!("ROLLOUT_SAMPLES\t{}", config.evaluation.rollout.samples);

    for world_value in PROBE_WORLDS {
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
        let roots = compare_root_actions(
            bridge.true_state(),
            &cards,
            &policy,
            config.evaluation.rollout,
        )?;
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
        let selected = roots
            .evaluations
            .iter()
            .find(|evaluation| evaluation.action == roots.selected)
            .expect("selected root is one of the evaluated roots");
        let selected_card = roots
            .selected
            .key
            .card
            .and_then(|card| interpretation.card(card))
            .map(|metadata| metadata.deck_name.as_str())
            .unwrap_or("-");

        println!(
            "PROBE\tworld={}\tseat={}\tcaverns={}\thand={}\tbaseline_wins={}/{}\troot_actions={}\twinning_root_actions={}\tbest_root_wins={}/{}\tselected_class={:?}\tselected_card={}\tselected_wins={}/{}",
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
            roots.selected.class,
            selected_card,
            selected.result.wins(),
            selected.result.samples()
        );
    }

    Ok(())
}
