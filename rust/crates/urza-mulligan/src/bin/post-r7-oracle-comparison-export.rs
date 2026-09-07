use std::error::Error;
use std::io;

use urza_cards::R4CardDatabase;
use urza_core::CardDefId;
use urza_mc::sample_hidden_world;
use urza_mulligan::{
    InterpretationCatalog, KeptHand, MulliganStage, bridge_kept_hand, draw_fresh_seven,
    load_commander_deck, r7_pilot_generation_config, sample_pregame_context,
};
use urza_policy::DeterministicPolicy;
use urza_rng::WorldId;
use urza_rollout::{RolloutConfig, rollout};

const EXPORT_VERSION: &str = "post_r7_oracle_comparison_export_v1";

fn main() {
    if let Err(error) = run() {
        eprintln!("post-R7 Oracle comparison export failed: {error}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), Box<dyn Error>> {
    let mut args = std::env::args().skip(1);
    let opening_offset = parse_u64(args.next(), "opening-offset")?;
    let hidden_world = parse_u64(args.next(), "hidden-world")?;
    if args.next().is_some() {
        return Err(Box::new(io::Error::other(
            "usage: post-r7-oracle-comparison-export <opening-offset> <hidden-world>",
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
    let pregame = sample_pregame_context(generation.opening_root, opening_world);
    let kept = KeptHand {
        stage,
        hand: hand.clone(),
        known_bottom: Vec::new(),
        pregame,
    };
    let opening = bridge_kept_hand(&kept, &deck, generation.opening_root, opening_world)?;

    let config = RolloutConfig {
        root: generation.evaluation.rollout.root,
        world: WorldId(hidden_world),
        max_steps: generation.evaluation.rollout.rollout_max_steps,
    };
    let exact = sample_hidden_world(opening.true_state(), config.root, config.world)?;
    let baseline = rollout(exact.clone(), &cards, &DeterministicPolicy, config)?;

    println!("ORACLE_COMPARISON_EXPORT\t{EXPORT_VERSION}");
    println!(
        "META\topening_offset={opening_offset}\topening_world={}\thidden_world={hidden_world}\tseat={}\tcaverns={}\tmax_steps={}",
        opening_world.0,
        kept.pregame.seat,
        kept.pregame.gemstone_caverns_eligible,
        config.max_steps,
    );

    let hand_names = hand
        .iter()
        .map(|card| card_name(&interpretation, *card))
        .collect::<Result<Vec<_>, _>>()?;
    println!("OPENING_HAND\t{}", hand_names.join("|"));

    let mut deck_order = hand.clone();
    deck_order.extend_from_slice(exact.library.cards());
    println!("DECK_ORDER_COUNT\t{}", deck_order.len());
    for (index, card) in deck_order.iter().enumerate() {
        println!("DECK_CARD\t{index}\t{}", card_name(&interpretation, *card)?);
    }

    println!(
        "RUST_RESULT\tstop={:?}\tturn={}\ttrace_len={}\thand_size={}\tbattlefield_size={}\tgraveyard_size={}\texile_size={}",
        baseline.stop,
        baseline.final_information.turn,
        baseline.trace.len(),
        baseline.final_information.hand.len(),
        baseline.final_information.battlefield.len(),
        baseline.final_information.graveyard.len(),
        baseline.final_information.exile.len(),
    );

    println!(
        "RUST_FINAL_HAND\t{}",
        names_for_cards(&interpretation, &baseline.final_information.hand)?.join("|")
    );
    let battlefield_cards = baseline
        .final_information
        .battlefield
        .iter()
        .map(|permanent| permanent.card)
        .collect::<Vec<_>>();
    println!(
        "RUST_FINAL_BATTLEFIELD\t{}",
        names_for_cards(&interpretation, &battlefield_cards)?.join("|")
    );
    println!(
        "RUST_FINAL_GRAVEYARD\t{}",
        names_for_cards(&interpretation, &baseline.final_information.graveyard)?.join("|")
    );
    println!(
        "RUST_FINAL_EXILE\t{}",
        names_for_cards(&interpretation, &baseline.final_information.exile)?.join("|")
    );

    for step in &baseline.trace {
        let card = step
            .key
            .card
            .map(|card| card_name(&interpretation, card))
            .transpose()?
            .unwrap_or("-");
        println!(
            "RUST_ACTION\tindex={}\tturn={}\tphase={:?}\twindow={:?}\tclass={:?}\tkind={}\tcard={}\tparameter={:?}\tsecondary={}\tdetail={:?}",
            step.index,
            step.turn,
            step.phase,
            step.window,
            step.class,
            step.key.kind,
            card,
            step.key.parameter,
            step.key.secondary,
            step.key.detail,
        );
    }

    Ok(())
}

fn names_for_cards<'a>(
    interpretation: &'a InterpretationCatalog,
    cards: &[CardDefId],
) -> Result<Vec<&'a str>, Box<dyn Error>> {
    cards
        .iter()
        .map(|card| card_name(interpretation, *card))
        .collect()
}

fn card_name(
    interpretation: &InterpretationCatalog,
    card: CardDefId,
) -> Result<&str, Box<dyn Error>> {
    interpretation
        .card(card)
        .map(|metadata| metadata.deck_name.as_str())
        .ok_or_else(|| {
            Box::new(io::Error::other(format!("unknown card id {}", card.0))) as Box<dyn Error>
        })
}

fn parse_u64(value: Option<String>, name: &str) -> Result<u64, Box<dyn Error>> {
    let text = value.ok_or_else(|| io::Error::other(format!("missing {name}")))?;
    text.parse::<u64>()
        .map_err(|error| Box::new(io::Error::other(format!("invalid {name} {text:?}: {error}"))) as _)
}
