use std::error::Error;
use std::io;

use urza_cards::CurrentCardDatabase;
use urza_core::{CardDefId, PendingDecision, Phase, TrueState, Window};
use urza_info::{CanonicalObjectId, InformationState, observe};
use urza_mc::sample_hidden_world;
use urza_mulligan::{
    KeptHand, MulliganStage, bridge_kept_hand, draw_fresh_seven, load_commander_deck,
    r7_pilot_generation_config, sample_pregame_context,
};
use urza_policy::{StrategicPolicy, StrategicPolicyConfig, TerminalRecipe};
use urza_policy_bridge::CandidateBridge;
use urza_rng::WorldId;
use urza_rollout::{RolloutConfig, RolloutStop, replay_trace, rollout_with_selector};
use urza_rules::{
    ABILITY_ARTIFICERS_ASSISTANT_SCRY, ABILITY_UTHROS_ARTIFACT_DRAW, RuleError,
    advance_automatic, detect_terminal_win,
};

const VERSION: &str = "post_r7_strategic_source_diagnostic_v1";
const KIND_URZA_ARTIFACT_MANA: u16 = 5;
const KIND_TOP_LOOK: u16 = 15;
const KIND_TOP_DRAW: u16 = 16;
const KIND_REALITY_CHIP_RECONFIGURE: u16 = 19;
const KIND_FTT_LEVEL: u16 = 21;
const KIND_ONE_RING_DRAW: u16 = 35;
const KIND_UTHROS_STATION: u16 = 36;
const KIND_CLUE_DRAW: u16 = 37;

#[derive(Debug, Default)]
struct Stats {
    worlds: u64,
    terminals: u64,
    decisions: u64,
    top_battlefield_decisions: u64,
    top_look_candidate_decisions: u64,
    top_look_selected: u64,
    top_urza_mana_candidate_decisions: u64,
    top_urza_mana_selected: u64,
    top_mana_selected_without_live_look: u64,
    ftt_battlefield_decisions: u64,
    ftt_level_candidate_decisions: u64,
    ftt_level_selected: u64,
    ring_draw_candidate_decisions: u64,
    ring_draw_selected: u64,
    uthros_station_candidate_decisions: u64,
    uthros_station_selected: u64,
}

fn main() {
    if let Err(error) = run() {
        eprintln!("post-R7 strategic source diagnostic failed: {error}");
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
            "usage: post-r7-strategic-source-diagnostic <opening-offset> <hidden-start> <hidden-count>",
        )));
    }

    let generation = r7_pilot_generation_config();
    let deck = load_commander_deck()?;
    let cards = CurrentCardDatabase::load()?;
    let policy = strategic_policy(&cards)?;
    let top = cards.card_id_by_name("Sensei's Divining Top")?;
    let ftt = cards.card_id_by_name("Fortune Teller's Talent")?;

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
    let mut stats = Stats::default();

    println!("STRATEGIC_SOURCE_DIAGNOSTIC\t{VERSION}");
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
        let strategic = rollout_with_selector(exact.clone(), &cards, &policy, config)?;
        if matches!(
            strategic.stop,
            RolloutStop::StepLimit | RolloutStop::NoCandidate
        ) {
            return Err(Box::new(io::Error::other(format!(
                "strategic hidden world {} stopped incompletely at {:?}",
                hidden_world.0, strategic.stop
            ))));
        }
        stats.worlds += 1;
        stats.terminals += u64::from(matches!(strategic.stop, RolloutStop::Terminal(_)));

        for (position, step) in strategic.trace.iter().enumerate() {
            stats.decisions += 1;
            let mut decision_state =
                replay_trace(exact.clone(), &cards, config, &strategic.trace[..position])?;
            if let Some(stop) = prepare_for_decision(&mut decision_state, &cards)? {
                return Err(Box::new(io::Error::other(format!(
                    "replay stopped at hidden world {} decision {} before expected action: {stop:?}",
                    hidden_world.0, step.index
                ))));
            }
            let bridge = CandidateBridge::build(&decision_state, &cards)?;
            let information = bridge.information();
            let top_sources = canonical_sources_for_card(information, top);
            let top_on_battlefield = !top_sources.is_empty();
            if top_on_battlefield {
                stats.top_battlefield_decisions += 1;
            }
            let top_look_candidate = bridge.candidates().iter().any(|candidate| {
                candidate.key.kind == KIND_TOP_LOOK
                    && candidate
                        .key
                        .source
                        .is_some_and(|source| top_sources.contains(&source))
            });
            let top_mana_candidate = bridge.candidates().iter().any(|candidate| {
                candidate.key.kind == KIND_URZA_ARTIFACT_MANA
                    && candidate
                        .key
                        .source
                        .is_some_and(|source| top_sources.contains(&source))
            });
            if top_look_candidate {
                stats.top_look_candidate_decisions += 1;
            }
            if top_mana_candidate {
                stats.top_urza_mana_candidate_decisions += 1;
            }
            let top_look_selected = step.key.kind == KIND_TOP_LOOK
                && step
                    .key
                    .source
                    .is_some_and(|source| top_sources.contains(&source));
            if top_look_selected {
                stats.top_look_selected += 1;
            }
            let top_mana_selected = step.key.kind == KIND_URZA_ARTIFACT_MANA
                && step
                    .key
                    .source
                    .is_some_and(|source| top_sources.contains(&source));
            if top_mana_selected {
                stats.top_urza_mana_selected += 1;
                if !top_look_candidate {
                    stats.top_mana_selected_without_live_look += 1;
                }
                let source_kinds = bridge
                    .candidates()
                    .iter()
                    .filter(|candidate| {
                        candidate
                            .key
                            .source
                            .is_some_and(|source| top_sources.contains(&source))
                    })
                    .map(|candidate| candidate.key.kind.to_string())
                    .collect::<Vec<_>>()
                    .join(",");
                println!(
                    "TOP_MANA_EVENT\topening={}\thidden={}\tindex={}\tturn={}\tphase={:?}\tmana={:?}\tknown_top={}\tlook_candidate={}\tsource_kinds={}",
                    opening_offset,
                    hidden_world.0,
                    step.index,
                    step.turn,
                    information.phase,
                    information.mana,
                    information.library.known_top.len(),
                    top_look_candidate,
                    source_kinds,
                );
            }

            if information.battlefield.iter().any(|permanent| permanent.card == ftt) {
                stats.ftt_battlefield_decisions += 1;
            }
            let ftt_level_candidate = bridge
                .candidates()
                .iter()
                .any(|candidate| candidate.key.kind == KIND_FTT_LEVEL);
            if ftt_level_candidate {
                stats.ftt_level_candidate_decisions += 1;
            }
            if step.key.kind == KIND_FTT_LEVEL {
                stats.ftt_level_selected += 1;
            }
            if bridge
                .candidates()
                .iter()
                .any(|candidate| candidate.key.kind == KIND_ONE_RING_DRAW)
            {
                stats.ring_draw_candidate_decisions += 1;
            }
            if step.key.kind == KIND_ONE_RING_DRAW {
                stats.ring_draw_selected += 1;
            }
            if bridge
                .candidates()
                .iter()
                .any(|candidate| candidate.key.kind == KIND_UTHROS_STATION)
            {
                stats.uthros_station_candidate_decisions += 1;
            }
            if step.key.kind == KIND_UTHROS_STATION {
                stats.uthros_station_selected += 1;
            }
        }
    }

    println!(
        "SUMMARY\topening={}\tworlds={}\tterminals={}\tdecisions={}\ttop_battlefield={}\ttop_look_candidates={}\ttop_look_selected={}\ttop_mana_candidates={}\ttop_mana_selected={}\ttop_mana_without_live_look={}\tftt_battlefield={}\tftt_level_candidates={}\tftt_level_selected={}\tring_draw_candidates={}\tring_draw_selected={}\tuthros_station_candidates={}\tuthros_station_selected={}",
        opening_offset,
        stats.worlds,
        stats.terminals,
        stats.decisions,
        stats.top_battlefield_decisions,
        stats.top_look_candidate_decisions,
        stats.top_look_selected,
        stats.top_urza_mana_candidate_decisions,
        stats.top_urza_mana_selected,
        stats.top_mana_selected_without_live_look,
        stats.ftt_battlefield_decisions,
        stats.ftt_level_candidate_decisions,
        stats.ftt_level_selected,
        stats.ring_draw_candidate_decisions,
        stats.ring_draw_selected,
        stats.uthros_station_candidate_decisions,
        stats.uthros_station_selected,
    );
    Ok(())
}

fn canonical_sources_for_card(
    information: &InformationState,
    card: CardDefId,
) -> Vec<CanonicalObjectId> {
    information
        .battlefield
        .iter()
        .filter(|permanent| permanent.card == card)
        .map(|permanent| permanent.canonical_id)
        .collect()
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
        config.card_values.insert(cards.card_id_by_name(name)?, value);
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
    config.stack_intervention_kind_values.insert(KIND_TOP_LOOK, 220);
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
        vec!["Sensei's Divining Top", "Forensic Gadgeteer", "Grinding Station"],
        vec!["Sensei's Divining Top", "Forensic Gadgeteer", "Battered Golem"],
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

fn prepare_for_decision(
    state: &mut TrueState,
    cards: &CurrentCardDatabase,
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

fn parse_u64(value: Option<String>, name: &str) -> Result<u64, Box<dyn Error>> {
    value
        .ok_or_else(|| io::Error::other(format!("missing {name}")))?
        .parse::<u64>()
        .map_err(|error| Box::new(error) as Box<dyn Error>)
}
