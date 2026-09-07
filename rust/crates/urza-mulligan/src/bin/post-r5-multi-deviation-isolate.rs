use std::error::Error;

use urza_cards::R4CardDatabase;
use urza_mc::sample_hidden_world;
use urza_mulligan::{
    KeptHand, MulliganStage, bridge_kept_hand, draw_fresh_seven, load_commander_deck,
    r7_pilot_generation_config, sample_pregame_context,
};
use urza_policy::{DeterministicPolicy, PolicyActionClass, PolicyPublicKey};
use urza_policy_bridge::CandidateBridge;
use urza_rng::WorldId;
use urza_rollout::{
    ForcedSemanticAction, RolloutConfig, RolloutStop, rollout_with_forced_semantic_actions,
};

const OPENING_OFFSET: u64 = 1;
const HIDDEN_WORLD: u64 = 245323;

fn main() {
    if let Err(error) = run() {
        eprintln!("multi-deviation isolation failed: {error}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), Box<dyn Error>> {
    let generation = r7_pilot_generation_config();
    let deck = load_commander_deck()?;
    let cards = R4CardDatabase::load()?;
    let opening_world = WorldId(generation.first_world.0 + OPENING_OFFSET);
    let stage = MulliganStage::InitialSeven;
    let hand = draw_fresh_seven(&deck, generation.opening_root, opening_world, stage);
    let kept = KeptHand {
        stage,
        hand,
        known_bottom: Vec::new(),
        pregame: sample_pregame_context(generation.opening_root, opening_world),
    };
    let opening = bridge_kept_hand(&kept, &deck, generation.opening_root, opening_world)?;
    let hidden_world = WorldId(HIDDEN_WORLD);
    let config = RolloutConfig {
        root: generation.evaluation.rollout.root,
        world: hidden_world,
        max_steps: generation.evaluation.rollout.rollout_max_steps,
    };
    let exact = sample_hidden_world(opening.true_state(), config.root, hidden_world)?;
    let pass_key = PolicyPublicKey {
        kind: 1,
        ..PolicyPublicKey::default()
    };
    let forced = [
        ForcedSemanticAction {
            index: 40,
            class: PolicyActionClass::PassPriority,
            key: pass_key.clone(),
        },
        ForcedSemanticAction {
            index: 41,
            class: PolicyActionClass::PassPriority,
            key: pass_key,
        },
    ];

    let result = rollout_with_forced_semantic_actions(
        exact,
        &cards,
        &DeterministicPolicy,
        config,
        &forced,
    )?;
    println!(
        "ISOLATE_RESULT\topening_world={}\thidden_world={}\tstop={:?}\tturn={}\tphase={:?}\twindow={:?}\tpending={:?}\tstack_len={}\ttrace_len={}",
        opening_world.0,
        hidden_world.0,
        result.stop,
        result.final_information.turn,
        result.final_information.phase,
        result.final_information.window,
        result.final_information.pending,
        result.final_information.stack.len(),
        result.trace.len(),
    );
    if result.stop != RolloutStop::NoCandidate {
        return Err(format!("expected NoCandidate, got {:?}", result.stop).into());
    }

    let bridge = CandidateBridge::build(&result.final_state, &cards)?;
    println!("RAW_BRIDGE\tcandidates={}", bridge.candidates().len());
    for candidate in bridge.candidates() {
        println!(
            "RAW_CANDIDATE\ttoken={:?}\tclass={:?}\tkey={:?}",
            candidate.token, candidate.class, candidate.key
        );
    }
    let raw_choice = DeterministicPolicy.choose(bridge.information(), bridge.candidates())?;
    println!("RAW_POLICY_CHOICE\t{raw_choice:?}");
    println!("FINAL_STATE\t{:?}", result.final_state);
    Ok(())
}
