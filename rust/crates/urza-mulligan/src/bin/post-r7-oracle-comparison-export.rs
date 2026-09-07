use std::error::Error;
use std::io;

use urza_cards::R4CardDatabase;
use urza_core::{CardDefId, PendingDecision, Phase, TrueState, Window};
use urza_info::observe;
use urza_mc::sample_hidden_world;
use urza_mulligan::{
    InterpretationCatalog, KeptHand, MulliganStage, bridge_kept_hand, draw_fresh_seven,
    load_commander_deck, r7_pilot_generation_config, sample_pregame_context,
};
use urza_policy::DeterministicPolicy;
use urza_policy_bridge::CandidateBridge;
use urza_rng::WorldId;
use urza_rollout::{RolloutConfig, RolloutStop, replay_trace, rollout};
use urza_rules::{RuleError, advance_automatic, detect_terminal_win};

const EXPORT_VERSION: &str = "post_r7_oracle_comparison_export_v2_opportunities";
const KIND_CHOOSE_SEARCH_TARGET: u16 = 28;

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

    for (position, step) in baseline.trace.iter().enumerate() {
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

        let mut decision_state =
            replay_trace(exact.clone(), &cards, config, &baseline.trace[..position])?;
        if let Some(stop) = prepare_for_decision(&mut decision_state, &cards)? {
            return Err(Box::new(io::Error::other(format!(
                "comparison replay stopped at decision {} before expected action: {stop:?}",
                step.index
            ))));
        }
        let bridge = CandidateBridge::build(&decision_state, &cards)?;
        let selected_matches = bridge
            .candidates()
            .iter()
            .filter(|candidate| candidate.class == step.class && candidate.key == step.key)
            .count();
        if selected_matches != 1 {
            return Err(Box::new(io::Error::other(format!(
                "expected exactly one selected candidate at decision {}, found {selected_matches}",
                step.index
            ))));
        }

        let engine_candidates = bridge
            .candidates()
            .iter()
            .filter_map(|candidate| {
                candidate.key.card.and_then(|candidate_card| {
                    card_name(&interpretation, candidate_card)
                        .ok()
                        .filter(|name| is_engine_name(name))
                        .map(|name| (candidate, name))
                })
            })
            .collect::<Vec<_>>();
        if !engine_candidates.is_empty() {
            let selected_engine = is_engine_name(card);
            println!(
                "ENGINE_OPPORTUNITY\tindex={}\tturn={}\tselected_class={:?}\tselected_kind={}\tselected_card={}\tselected_engine={}\tcandidate_count={}",
                step.index,
                step.turn,
                step.class,
                step.key.kind,
                card,
                selected_engine,
                engine_candidates.len(),
            );
            for (candidate, name) in engine_candidates {
                println!(
                    "ENGINE_CANDIDATE\tindex={}\tclass={:?}\tkind={}\tcard={}\tselected={}",
                    step.index,
                    candidate.class,
                    candidate.key.kind,
                    name,
                    candidate.class == step.class && candidate.key == step.key,
                );
            }
        }

        let tutor_candidates = bridge
            .candidates()
            .iter()
            .filter(|candidate| candidate.key.kind == KIND_CHOOSE_SEARCH_TARGET)
            .collect::<Vec<_>>();
        if !tutor_candidates.is_empty() {
            let source_name = decision_state
                .pending
                .source()
                .map(|source| card_name(&interpretation, source.card))
                .transpose()?
                .unwrap_or("-");
            let selected_target = step
                .key
                .card
                .map(|target| card_name(&interpretation, target))
                .transpose()?
                .unwrap_or("NONE");
            println!(
                "TUTOR_OPPORTUNITY\tindex={}\tturn={}\tsource={}\tselected_target={}\tcandidate_count={}",
                step.index,
                step.turn,
                source_name,
                selected_target,
                tutor_candidates.len(),
            );
            for candidate in tutor_candidates {
                let target = candidate
                    .key
                    .card
                    .map(|target| card_name(&interpretation, target))
                    .transpose()?
                    .unwrap_or("NONE");
                println!(
                    "TUTOR_CANDIDATE\tindex={}\ttarget={}\tselected={}",
                    step.index,
                    target,
                    candidate.class == step.class && candidate.key == step.key,
                );
            }
        }
    }

    Ok(())
}

fn prepare_for_decision(
    state: &mut TrueState,
    cards: &R4CardDatabase,
) -> Result<Option<RolloutStop>, Box<dyn Error>> {
    let information = observe(state)?;
    if let Some(family) = detect_terminal_win(&information, cards) {
        return Ok(Some(RolloutStop::Terminal(family)));
    }

    if needs_automatic_advance(state) {
        match advance_automatic(state, cards) {
            Ok(_) => {}
            Err(RuleError::HorizonReached) => return Ok(Some(RolloutStop::Horizon)),
            Err(error) => return Err(Box::new(error)),
        }
        let information = observe(state)?;
        if let Some(family) = detect_terminal_win(&information, cards) {
            return Ok(Some(RolloutStop::Terminal(family)));
        }
    }

    Ok(None)
}

fn needs_automatic_advance(state: &TrueState) -> bool {
    state.stack.is_empty()
        && matches!(state.pending, PendingDecision::None)
        && matches!(
            (state.phase, state.window),
            (Phase::OpponentCycle, Window::None) | (Phase::Untap, Window::None)
        )
}

fn is_engine_name(name: &str) -> bool {
    matches!(
        name,
        "The Reality Chip"
            | "Forensic Gadgeteer"
            | "The One Ring"
            | "Fortune Teller's Talent"
            | "Uthros Research Craft"
            | "Sensei's Divining Top"
    )
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
    text.parse::<u64>().map_err(|error| {
        Box::new(io::Error::other(format!(
            "invalid {name} {text:?}: {error}"
        ))) as _
    })
}
