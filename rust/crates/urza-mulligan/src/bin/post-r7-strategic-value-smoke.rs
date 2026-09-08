use std::error::Error;
use std::io;

use urza_cards::CurrentCardDatabase;
use urza_mc::sample_hidden_world;
use urza_mulligan::{
    KeptHand, MulliganStage, bridge_kept_hand, draw_fresh_seven, load_commander_deck,
    r7_pilot_generation_config, sample_pregame_context,
};
use urza_policy::{DeterministicPolicy, StrategicPolicy, StrategicPolicyConfig, TerminalRecipe};
use urza_rng::WorldId;
use urza_rollout::{RolloutConfig, RolloutStop, rollout, rollout_with_selector};
use urza_rules::{ABILITY_ARTIFICERS_ASSISTANT_SCRY, ABILITY_UTHROS_ARTIFACT_DRAW};

const VERSION: &str = "post_r7_strategic_value_smoke_v2_resource_aware";
const KIND_TOP_LOOK: u16 = 15;
const KIND_TOP_DRAW: u16 = 16;
const KIND_REALITY_CHIP_RECONFIGURE: u16 = 19;
const KIND_FTT_LEVEL: u16 = 21;
const KIND_ONE_RING_DRAW: u16 = 35;
const KIND_UTHROS_STATION: u16 = 36;
const KIND_CLUE_DRAW: u16 = 37;
const KIND_TRIGGER_ORDER: u16 = 38;
const KIND_SEARCH_TARGET: u16 = 28;

fn main() {
    if let Err(error) = run() {
        eprintln!("post-R7 strategic value smoke failed: {error}");
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
            "usage: post-r7-strategic-value-smoke <opening-offset> <hidden-start> <hidden-count>",
        )));
    }

    let generation = r7_pilot_generation_config();
    let deck = load_commander_deck()?;
    let cards = CurrentCardDatabase::load()?;
    let policy = strategic_policy(&cards)?;
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
        hand,
        known_bottom: Vec::new(),
        pregame: sample_pregame_context(generation.opening_root, opening_world),
    };
    let opening = bridge_kept_hand(&kept, &deck, generation.opening_root, opening_world)?;

    let mut baseline_terminals = 0_u64;
    let mut strategic_terminals = 0_u64;
    let mut strategic_decisions = 0_u64;
    let mut top_looks = 0_u64;
    let mut tutor_targets = 0_u64;
    let mut trigger_orders = 0_u64;

    for hidden_offset in 0..hidden_count {
        let hidden_world = WorldId(
            hidden_start
                .checked_add(hidden_offset)
                .ok_or_else(|| io::Error::other("hidden world overflow"))?,
        );
        let config = RolloutConfig {
            root: generation.evaluation.rollout.root,
            world: hidden_world,
            max_steps: generation.evaluation.rollout.rollout_max_steps,
        };
        let exact = sample_hidden_world(opening.true_state(), config.root, hidden_world)?;
        let baseline = rollout(exact.clone(), &cards, &DeterministicPolicy, config)?;
        if matches!(
            baseline.stop,
            RolloutStop::StepLimit | RolloutStop::NoCandidate
        ) {
            return Err(Box::new(io::Error::other(format!(
                "baseline hidden world {} stopped incompletely at {:?}",
                hidden_world.0, baseline.stop
            ))));
        }
        baseline_terminals += u64::from(matches!(baseline.stop, RolloutStop::Terminal(_)));

        let strategic = rollout_with_selector(exact, &cards, &policy, config)?;
        if matches!(
            strategic.stop,
            RolloutStop::StepLimit | RolloutStop::NoCandidate
        ) {
            return Err(Box::new(io::Error::other(format!(
                "strategic hidden world {} stopped incompletely at {:?}",
                hidden_world.0, strategic.stop
            ))));
        }
        strategic_terminals += u64::from(matches!(strategic.stop, RolloutStop::Terminal(_)));
        strategic_decisions = strategic_decisions
            .saturating_add(u64::try_from(strategic.trace.len()).unwrap_or(u64::MAX));
        for step in strategic.trace {
            top_looks += u64::from(step.key.kind == KIND_TOP_LOOK);
            tutor_targets +=
                u64::from(step.key.kind == KIND_SEARCH_TARGET && step.key.card.is_some());
            trigger_orders += u64::from(step.key.kind == KIND_TRIGGER_ORDER);
        }
    }

    println!("STRATEGIC_VALUE_SMOKE\t{VERSION}");
    println!(
        "SUMMARY\topening={}\tworlds={}\tbaseline_terminals={}\tstrategic_terminals={}\tstrategic_decisions={}\ttop_looks={}\ttutor_targets={}\ttrigger_orders={}",
        opening_offset,
        hidden_count,
        baseline_terminals,
        strategic_terminals,
        strategic_decisions,
        top_looks,
        tutor_targets,
        trigger_orders,
    );
    Ok(())
}

fn strategic_policy(cards: &CurrentCardDatabase) -> Result<StrategicPolicy, Box<dyn Error>> {
    let mut config = StrategicPolicyConfig::default();
    for (name, value) in [
        ("Sensei's Divining Top", 130),
        ("The Reality Chip", 125),
        ("Fortune Teller's Talent", 120),
        ("Forensic Gadgeteer", 120),
        ("The One Ring", 115),
        ("Uthros Research Craft", 110),
        ("Power Artifact", 135),
        ("Basalt Monolith", 130),
        ("Grim Monolith", 125),
        ("Grinding Station", 115),
        ("Battered Golem", 105),
        ("Chrome Dome", 100),
        ("Mana Vault", 100),
        ("Banishing Knack", 105),
        ("Retraction Helix", 105),
        ("Sewer-veillance Cam", 100),
        ("Spellseeker", 90),
        ("Merchant Scroll", 90),
        ("Mystical Tutor", 95),
        ("Whir of Invention", 105),
        ("Reshape", 105),
        ("Transmute Artifact", 115),
        ("Repurposing Bay", 100),
        ("Urza's Saga", 105),
        ("Tezzeret, Cruel Captain", 100),
    ] {
        config
            .card_values
            .insert(cards.card_id_by_name(name)?, value);
    }

    config.action_kind_values.extend([
        (KIND_TOP_LOOK, 70),
        (KIND_TOP_DRAW, 110),
        (KIND_REALITY_CHIP_RECONFIGURE, 100),
        (KIND_FTT_LEVEL, 90),
        (KIND_ONE_RING_DRAW, 140),
        (KIND_UTHROS_STATION, 60),
        (KIND_CLUE_DRAW, 45),
    ]);
    config
        .stack_intervention_kind_values
        .insert(KIND_TOP_LOOK, 220);
    config.stack_intervention_trigger_abilities.extend([
        ABILITY_ARTIFICERS_ASSISTANT_SCRY,
        ABILITY_UTHROS_ARTIFACT_DRAW,
    ]);
    config.assistant_scry_ability = Some(ABILITY_ARTIFICERS_ASSISTANT_SCRY);
    config.uthros_draw_ability = Some(ABILITY_UTHROS_ARTIFACT_DRAW);
    config.library_look_kind = Some(KIND_TOP_LOOK);

    for names in [
        vec!["Power Artifact", "Basalt Monolith"],
        vec!["Power Artifact", "Grim Monolith"],
        vec!["Sensei's Divining Top", "The Reality Chip"],
        vec!["Sensei's Divining Top", "Fortune Teller's Talent"],
        vec![
            "Sensei's Divining Top",
            "Forensic Gadgeteer",
            "Grinding Station",
        ],
        vec![
            "Sensei's Divining Top",
            "Forensic Gadgeteer",
            "Battered Golem",
        ],
        vec!["Banishing Knack", "Battered Golem", "Sewer-veillance Cam"],
        vec!["Retraction Helix", "Battered Golem", "Sewer-veillance Cam"],
    ] {
        let required = names
            .into_iter()
            .map(|name| cards.card_id_by_name(name))
            .collect::<Result<Vec<_>, _>>()?;
        config.terminal_recipes.push(TerminalRecipe::new(required));
    }

    Ok(StrategicPolicy::new(config))
}

fn parse_u64(value: Option<String>, name: &str) -> Result<u64, Box<dyn Error>> {
    value
        .ok_or_else(|| io::Error::other(format!("missing {name}")))?
        .parse::<u64>()
        .map_err(|error| Box::new(error) as Box<dyn Error>)
}
