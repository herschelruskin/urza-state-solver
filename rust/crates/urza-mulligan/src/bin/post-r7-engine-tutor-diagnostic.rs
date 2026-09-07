use std::collections::BTreeMap;
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
use urza_policy::{DeterministicPolicy, PolicyActionClass};
use urza_policy_bridge::CandidateBridge;
use urza_rng::WorldId;
use urza_rollout::{RolloutConfig, RolloutStop, replay_trace, rollout};
use urza_rules::{RuleError, advance_automatic, detect_terminal_win};

const DIAGNOSTIC_VERSION: &str = "post_r7_engine_tutor_diagnostic_v1";
const KIND_CHOOSE_SEARCH_TARGET: u16 = 28;
const ENGINES: [&str; 5] = [
    "The Reality Chip",
    "Forensic Gadgeteer",
    "The One Ring",
    "Fortune Teller's Talent",
    "Uthros Research Craft",
];

#[derive(Debug, Default, Clone)]
struct EngineStats {
    visible_decisions: u64,
    candidate_decisions: u64,
    selected_decisions: u64,
    cast_candidate_decisions: u64,
    cast_selected: u64,
    activation_candidate_decisions: u64,
    activation_selected: u64,
    tutor_target_candidate_decisions: u64,
    tutor_target_selected: u64,
}

#[derive(Debug, Default, Clone)]
struct TutorStats {
    resolutions: u64,
    fail_to_find: u64,
    real_target: u64,
    candidate_targets: u64,
    selected_targets: BTreeMap<String, u64>,
}

fn main() {
    if let Err(error) = run() {
        eprintln!("post-R7 engine/tutor diagnostic failed: {error}");
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
            "usage: post-r7-engine-tutor-diagnostic <opening-offset> <hidden-start> <hidden-count>; hidden-count must be positive",
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
    let kept = KeptHand {
        stage,
        hand: hand.clone(),
        known_bottom: Vec::new(),
        pregame: sample_pregame_context(generation.opening_root, opening_world),
    };
    let opening = bridge_kept_hand(&kept, &deck, generation.opening_root, opening_world)?;

    let mut engine_stats = ENGINES
        .into_iter()
        .map(|name| (name.to_owned(), EngineStats::default()))
        .collect::<BTreeMap<_, _>>();
    let mut tutor_stats = BTreeMap::<String, TutorStats>::new();
    let mut worlds = 0_u64;
    let mut total_decisions = 0_u64;
    let mut terminal_worlds = 0_u64;

    println!("ENGINE_TUTOR_DIAGNOSTIC\t{DIAGNOSTIC_VERSION}");
    println!(
        "SOURCE\topening_offset={opening_offset}\topening_world={}\thidden_start={hidden_start}\thidden_count={hidden_count}\tseat={}\tcaverns={}",
        opening_world.0, kept.pregame.seat, kept.pregame.gemstone_caverns_eligible,
    );
    println!(
        "OPENING_HAND\t{}",
        hand.iter()
            .map(|card| card_name(&interpretation, *card))
            .collect::<Result<Vec<_>, _>>()?
            .join("|")
    );

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
        worlds = worlds.saturating_add(1);
        if matches!(baseline.stop, RolloutStop::Terminal(_)) {
            terminal_worlds = terminal_worlds.saturating_add(1);
        }
        if matches!(
            baseline.stop,
            RolloutStop::StepLimit | RolloutStop::NoCandidate
        ) {
            return Err(Box::new(io::Error::other(format!(
                "baseline hidden world {} stopped incompletely at {:?}",
                hidden_world.0, baseline.stop
            ))));
        }

        for (position, step) in baseline.trace.iter().enumerate() {
            total_decisions = total_decisions.saturating_add(1);
            let mut decision_state =
                replay_trace(exact.clone(), &cards, config, &baseline.trace[..position])?;
            if let Some(stop) = prepare_for_decision(&mut decision_state, &cards)? {
                return Err(Box::new(io::Error::other(format!(
                    "replay stopped at hidden world {} decision {} before expected action: {stop:?}",
                    hidden_world.0, step.index
                ))));
            }
            let bridge = CandidateBridge::build(&decision_state, &cards)?;
            let information = bridge.information();

            for engine in ENGINES {
                let visible =
                    information.hand.iter().any(|card| {
                        card_name(&interpretation, *card).is_ok_and(|name| name == engine)
                    }) || information.battlefield.iter().any(|permanent| {
                        card_name(&interpretation, permanent.card).is_ok_and(|name| name == engine)
                    }) || information.library.known_top.iter().any(|card| {
                        card_name(&interpretation, *card).is_ok_and(|name| name == engine)
                    });
                if visible {
                    engine_stats
                        .get_mut(engine)
                        .expect("engine stats initialized")
                        .visible_decisions += 1;
                }

                let candidates = bridge
                    .candidates()
                    .iter()
                    .filter(|candidate| {
                        candidate.key.card.is_some_and(|card| {
                            card_name(&interpretation, card).is_ok_and(|name| name == engine)
                        })
                    })
                    .collect::<Vec<_>>();
                if candidates.is_empty() {
                    continue;
                }

                let stats = engine_stats
                    .get_mut(engine)
                    .expect("engine stats initialized");
                stats.candidate_decisions += 1;
                let selected_engine = step.key.card.is_some_and(|card| {
                    card_name(&interpretation, card).is_ok_and(|name| name == engine)
                });
                if selected_engine {
                    stats.selected_decisions += 1;
                }

                let cast_candidate = candidates
                    .iter()
                    .any(|candidate| candidate.class == PolicyActionClass::CastSpell);
                if cast_candidate {
                    stats.cast_candidate_decisions += 1;
                    if selected_engine && step.class == PolicyActionClass::CastSpell {
                        stats.cast_selected += 1;
                    }
                }
                let activation_candidate = candidates
                    .iter()
                    .any(|candidate| candidate.class == PolicyActionClass::ActivateAbility);
                if activation_candidate {
                    stats.activation_candidate_decisions += 1;
                    if selected_engine && step.class == PolicyActionClass::ActivateAbility {
                        stats.activation_selected += 1;
                    }
                }
                let tutor_target_candidate = candidates.iter().any(|candidate| {
                    candidate.class == PolicyActionClass::ContingentDecision
                        && candidate.key.kind == KIND_CHOOSE_SEARCH_TARGET
                });
                if tutor_target_candidate {
                    stats.tutor_target_candidate_decisions += 1;
                    if selected_engine
                        && step.class == PolicyActionClass::ContingentDecision
                        && step.key.kind == KIND_CHOOSE_SEARCH_TARGET
                    {
                        stats.tutor_target_selected += 1;
                    }
                }
            }

            let tutor_candidates = bridge
                .candidates()
                .iter()
                .filter(|candidate| candidate.key.kind == KIND_CHOOSE_SEARCH_TARGET)
                .collect::<Vec<_>>();
            if !tutor_candidates.is_empty() {
                let source = decision_state
                    .pending
                    .source()
                    .map(|source| card_name(&interpretation, source.card))
                    .transpose()?
                    .unwrap_or("-")
                    .to_owned();
                let selected = step
                    .key
                    .card
                    .map(|target| card_name(&interpretation, target))
                    .transpose()?
                    .map(str::to_owned);
                let stats = tutor_stats.entry(source.clone()).or_default();
                stats.resolutions += 1;
                stats.candidate_targets = stats
                    .candidate_targets
                    .saturating_add(u64::try_from(tutor_candidates.len()).unwrap_or(u64::MAX));
                match selected.as_deref() {
                    Some(target) => {
                        stats.real_target += 1;
                        *stats.selected_targets.entry(target.to_owned()).or_default() += 1;
                    }
                    None => stats.fail_to_find += 1,
                }
                println!(
                    "TUTOR_EVENT\thidden_world={}\tindex={}\tturn={}\tsource={}\tselected={}\tcandidates={}",
                    hidden_world.0,
                    step.index,
                    step.turn,
                    source,
                    selected.as_deref().unwrap_or("NONE"),
                    tutor_candidates.len(),
                );
            }
        }
    }

    println!(
        "SUMMARY\tworlds={}\tdecisions={}\tterminal_worlds={}",
        worlds, total_decisions, terminal_worlds
    );
    for engine in ENGINES {
        let stats = &engine_stats[engine];
        println!(
            "ENGINE_SUMMARY\tengine={}\tvisible_decisions={}\tcandidate_decisions={}\tselected_decisions={}\tcast_candidate_decisions={}\tcast_selected={}\tactivation_candidate_decisions={}\tactivation_selected={}\ttutor_target_candidate_decisions={}\ttutor_target_selected={}",
            engine,
            stats.visible_decisions,
            stats.candidate_decisions,
            stats.selected_decisions,
            stats.cast_candidate_decisions,
            stats.cast_selected,
            stats.activation_candidate_decisions,
            stats.activation_selected,
            stats.tutor_target_candidate_decisions,
            stats.tutor_target_selected,
        );
    }
    for (source, stats) in tutor_stats {
        let targets = stats
            .selected_targets
            .into_iter()
            .map(|(target, count)| format!("{target}:{count}"))
            .collect::<Vec<_>>()
            .join("|");
        println!(
            "TUTOR_SUMMARY\tsource={}\tresolutions={}\tfail_to_find={}\treal_target={}\tcandidate_targets={}\tselected_targets={}",
            source,
            stats.resolutions,
            stats.fail_to_find,
            stats.real_target,
            stats.candidate_targets,
            targets,
        );
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
