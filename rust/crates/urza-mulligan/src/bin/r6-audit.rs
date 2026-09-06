use urza_mulligan::{
    COMMANDER_MAIN_DECK_SIZE, EXPERIMENTAL_KEEP_FLOOR, MULLIGAN_CONFIDENCE_CONTRACT,
    MULLIGAN_DECISION_VERSION, MULLIGAN_ENGINE_VERSION, MULLIGAN_OBJECTIVE_VERSION,
    MULLIGAN_REPORT_VERSION, MULLIGAN_TRACE_VERSION, MULLIGAN_UNCERTAINTY_VERSION,
    MulliganDecision, MulliganStage, OPENING_RUNTIME_VERSION, bottom_subset_count,
    load_commander_deck, trace_mulligan_script,
};
use urza_rng::{RootSeed, WorldId};

fn main() {
    let deck = load_commander_deck().expect("R6 audited Commander deck");
    assert_eq!(deck.main_deck().len(), COMMANDER_MAIN_DECK_SIZE);
    assert!(!deck.main_deck().contains(&deck.commander()));
    assert_eq!(EXPERIMENTAL_KEEP_FLOOR, 3);

    let subset_counts: Vec<_> = MulliganStage::ALL
        .into_iter()
        .map(bottom_subset_count)
        .collect();
    assert_eq!(subset_counts, vec![1, 1, 7, 21, 35, 35]);

    let trace = trace_mulligan_script(
        &deck,
        RootSeed::from_u64(0x5236_4155_4449_0001),
        WorldId(6),
        &[
            MulliganDecision::Mulligan,
            MulliganDecision::Keep {
                bottom_indices: Vec::new(),
            },
        ],
    )
    .expect("R6 fixed-seed audit trace");
    assert_eq!(trace.generated_fresh_sevens, 1);
    assert_eq!(trace.kept.stage, MulliganStage::FreeSeven);

    println!("phase=R6-accepted");
    println!("mulligan_engine_version={MULLIGAN_ENGINE_VERSION}");
    println!("opening_runtime_version={OPENING_RUNTIME_VERSION}");
    println!("decision_version={MULLIGAN_DECISION_VERSION}");
    println!("objective_version={MULLIGAN_OBJECTIVE_VERSION}");
    println!("report_version={MULLIGAN_REPORT_VERSION}");
    println!("uncertainty_version={MULLIGAN_UNCERTAINTY_VERSION}");
    println!("trace_version={MULLIGAN_TRACE_VERSION}");
    println!("commander_main_deck_cards={}", deck.main_deck().len());
    println!("commander_plus_main_deck=1+{}", deck.main_deck().len());
    println!("bottom_subset_counts={subset_counts:?}");
    println!("experimental_keep_floor={EXPERIMENTAL_KEEP_FLOOR}");
    println!("fixed_seed_generated_fresh_sevens={}", trace.generated_fresh_sevens);
    println!("fixed_seed_kept_stage={:?}", trace.kept.stage);
    println!("confidence_contract={MULLIGAN_CONFIDENCE_CONTRACT}");
    println!("future_invariance=covered_by_r6_acceptance_tests");
    println!("brute_force_dp_oracle=covered_by_r6_acceptance_tests");
    println!("scope=sequential London mulligan policy/value/report acceptance only; no new R4 rules/card mechanics and no Python gameplay-policy port");
}
