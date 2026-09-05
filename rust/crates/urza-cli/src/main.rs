use serde_json::json;
use urza_cards::{
    R2CardDatabase, R3_ACCEPTED_ACTIVE_IDENTITY_COUNT, R3CardDatabase,
    R4_ACCEPTED_ACTIVE_IDENTITY_COUNT, R4_ONLY_ACTIVE_NAMES, R4CardDatabase,
    URZA_CONSTRUCT_TOKEN_CARD_ID, catalog_digest_hex, load_catalog, load_coverage, load_r1_catalog,
    r1_catalog_digest_hex, validate_catalog_and_coverage, validate_r1_catalog,
    validate_r2_database, validate_r3_database, validate_r4_database,
};
use urza_cli::hand25_fixture;
use urza_core::{MODEL_VERSION, R2_MODEL_VERSION, R3_MODEL_VERSION, TrueState};
use urza_info::INFORMATION_SCHEMA_VERSION;
use urza_mc::{
    ADAPTIVE_ROOT_EVAL_VERSION, MONTE_CARLO_VERSION, PARALLEL_ROOT_EVAL_VERSION,
    ROOT_ACTION_EVAL_VERSION, ROOT_WORLD_CACHE_VERSION,
};
use urza_policy::{POLICY_PHASE, POLICY_VERSION};
use urza_policy_bridge::{
    CANDIDATE_BRIDGE_VERSION, CONTINGENT_ACTION_FAMILY_COUNT, ORDINARY_ACTION_FAMILY_COUNT,
};
use urza_rng::RNG_SCHEME_VERSION;
use urza_rollout::ROLLOUT_VERSION;
use urza_rules::{
    HORIZON_TURN, R2_RULES_VERSION, R2CardRole, R3_RULES_VERSION, RULES_VERSION, WinFamily,
};
use urza_value::VALUE_KEY_SCHEMA_VERSION;

fn main() {
    let command = std::env::args().nth(1).unwrap_or_else(|| "help".to_owned());
    match command.as_str() {
        "r0-audit" => run_r0_audit(),
        "r1-audit" => run_r1_audit(),
        "r2-audit" => run_r2_audit(),
        "r3-audit" => run_r3_audit(),
        "r4-audit" => run_r4_audit(),
        "r5-audit" => run_r5_audit(),
        _ => {
            eprintln!("usage: urza-cli <r0-audit|r1-audit|r2-audit|r3-audit|r4-audit|r5-audit>");
            std::process::exit(2);
        }
    }
}

fn run_r0_audit() {
    validate_catalog_and_coverage().expect("R0 catalog/coverage invariants");
    let catalog = load_catalog().expect("embedded catalog");
    let coverage = load_coverage().expect("embedded coverage");
    let hand25 = hand25_fixture().expect("Hand 25 fixture");
    let noncommander_count: u16 = catalog
        .cards
        .iter()
        .filter(|card| !card.commander)
        .map(|card| u16::from(card.deck_count))
        .sum();

    let report = json!({
        "phase": "R0",
        "catalog_version": catalog.catalog_version,
        "catalog_digest_blake3": catalog_digest_hex(),
        "distinct_active_names_including_commander": catalog.cards.len(),
        "noncommander_deck_count": noncommander_count,
        "coverage_entries": coverage.entries.len(),
        "coverage_policy": "explicit per-card status; implementation coverage advances only with milestone rules fixtures",
        "default_our_life": TrueState::default().life,
        "rng_scheme": RNG_SCHEME_VERSION,
        "hand25": {
            "mulligan_count": hand25.mulligan_count,
            "keep_size": hand25.keep_size,
            "drawn_seven": hand25.drawn_seven,
        },
    });

    println!(
        "{}",
        serde_json::to_string_pretty(&report).expect("serializable audit report")
    );
}

fn run_r1_audit() {
    validate_r1_catalog().expect("R1 catalog invariants");
    let catalog = load_r1_catalog().expect("embedded R1 catalog");
    let multiface_count = catalog
        .cards
        .iter()
        .filter(|card| card.feature_flags.is_multiface)
        .count();

    let report = json!({
        "phase": "R1",
        "catalog_version": catalog.catalog_version,
        "catalog_digest_blake3": r1_catalog_digest_hex(),
        "catalog_as_of_utc": catalog.catalog_as_of_utc,
        "source_bulk_type": catalog.source.bulk_type,
        "source_bulk_updated_at": catalog.source.bulk_updated_at,
        "source_bulk_file_sha256": catalog.source.bulk_file_sha256,
        "active_card_identities": catalog.cards.len(),
        "multiface_cards": multiface_count,
        "full_oracle_text_stored": false,
        "oracle_text_integrity": "per-card SHA-256 digest",
    });

    println!(
        "{}",
        serde_json::to_string_pretty(&report).expect("serializable R1 audit report")
    );
}

fn run_r2_audit() {
    validate_r2_database().expect("R2 database/coverage invariants");
    let catalog = load_r1_catalog().expect("embedded R1 catalog");
    let database = R2CardDatabase::load().expect("R2 card database");
    let supported_names: Vec<_> = catalog
        .cards
        .iter()
        .filter(|card| {
            database
                .profile(urza_core::CardDefId(card.id))
                .is_some_and(|profile| profile.role != R2CardRole::Unsupported)
        })
        .map(|card| card.deck_name.as_str())
        .collect();

    let report = json!({
        "phase": "R2",
        "rules_version": R2_RULES_VERSION,
        "model_version": R2_MODEL_VERSION,
        "horizon_turn": HORIZON_TURN,
        "supported_active_card_identities": supported_names.len(),
        "supported_active_names": supported_names,
        "synthetic_construct_card_id": URZA_CONSTRUCT_TOKEN_CARD_ID.0,
        "scope": "core sequencing primitives only; later card mechanics remain explicitly deferred",
    });

    println!(
        "{}",
        serde_json::to_string_pretty(&report).expect("serializable R2 audit report")
    );
}

fn run_r3_audit() {
    validate_r3_database().expect("R3 database/coverage invariants");
    let catalog = load_r1_catalog().expect("embedded R1 catalog");
    let database = R3CardDatabase::load().expect("R3 card database");
    let supported_names: Vec<_> = catalog
        .cards
        .iter()
        .filter(|card| {
            database
                .profile(urza_core::CardDefId(card.id))
                .is_some_and(|profile| profile.role != R2CardRole::Unsupported)
        })
        .map(|card| card.deck_name.as_str())
        .collect();

    let simple_tutors: Vec<_> = ["Spellseeker", "Merchant Scroll", "Mystical Tutor"]
        .into_iter()
        .map(|name| {
            let card = database
                .card_id_by_name(name)
                .expect("R3 simple tutor is in active catalog");
            let profile = database.profile(card).expect("R3 simple tutor profile");
            json!({
                "name": name,
                "card_id": card.0,
                "kind": format!("{:?}", profile.simple_tutor.expect("simple tutor kind")),
            })
        })
        .collect();

    let report = json!({
        "phase": "R3",
        "rules_version": R3_RULES_VERSION,
        "model_version": R3_MODEL_VERSION,
        "horizon_turn": HORIZON_TURN,
        "supported_active_card_identities": supported_names.len(),
        "supported_active_names": supported_names,
        "staged_simple_tutors": simple_tutors,
        "decision_boundary": "commit -> search observation -> target/no-find -> shared pre-target shuffle",
        "scope": "R3 staged-search milestone surface complete: simple tutors, Whir/Reshape/Transmute/Bay, Saga III, Tezzeret -3, Top/scry, and Urza spin permission"
    });

    println!(
        "{}",
        serde_json::to_string_pretty(&report).expect("serializable R3 audit report")
    );
}

fn run_r4_audit() {
    validate_r4_database().expect("R4 database/coverage invariants");
    let catalog = load_r1_catalog().expect("embedded R1 catalog");
    let database = R4CardDatabase::load().expect("R4 card database");
    let supported_names: Vec<_> = catalog
        .cards
        .iter()
        .filter(|card| {
            database
                .profile(urza_core::CardDefId(card.id))
                .is_some_and(|profile| profile.role != R2CardRole::Unsupported)
        })
        .map(|card| card.deck_name.as_str())
        .collect();

    let terminal_families: Vec<_> = WinFamily::ALL.into_iter().map(WinFamily::label).collect();
    let terminal_family_count = terminal_families.len();
    let intentionally_unmodeled_active_identities = catalog.cards.len() - supported_names.len();

    let report = json!({
        "phase": "R4-accepted",
        "rules_version": RULES_VERSION,
        "model_version": MODEL_VERSION,
        "information_schema_version": INFORMATION_SCHEMA_VERSION,
        "value_key_schema_version": VALUE_KEY_SCHEMA_VERSION,
        "horizon_turn": HORIZON_TURN,
        "accepted_r3_active_card_identities": R3_ACCEPTED_ACTIVE_IDENTITY_COUNT,
        "accepted_r4_active_card_identities": R4_ACCEPTED_ACTIVE_IDENTITY_COUNT,
        "r4_only_active_card_identities": R4_ONLY_ACTIVE_NAMES.len(),
        "r4_only_active_names": R4_ONLY_ACTIVE_NAMES,
        "intentionally_unmodeled_active_identities": intentionally_unmodeled_active_identities,
        "supported_active_names": supported_names,
        "terminal_family_count": terminal_family_count,
        "terminal_families": terminal_families,
        "terminal_detection_boundary": "public InformationState only; exact attachments/modes/grants preserved; stack and pending decisions block terminal recognition; Cage blocks library-cast families; hidden library order and raw ObjectId identity are irrelevant",
        "policy_boundary": "R4 exposes typed execution actions and public contingent choices; ordinary action enumeration/ranking and rollout policy remain R5 work",
        "deferred_boundary": "unsupported active identities remain explicitly INTENTIONALLY_UNMODELED and active primitive cards may retain coverage-listed deferred text; R4 acceptance does not approximate those mechanics",
        "scope": "R4 engine/rules acceptance closed: exact 15-card extension over frozen R3, 47 active identities total, 13 terminal families, and frozen R4 model/information/value namespaces"
    });

    println!(
        "{}",
        serde_json::to_string_pretty(&report).expect("serializable R4 audit report")
    );
}

fn run_r5_audit() {
    validate_r4_database().expect("accepted R4 database remains frozen for R5");

    let report = json!({
        "phase": "R5-parallel-scaling",
        "policy_phase": POLICY_PHASE,
        "policy_version": POLICY_VERSION,
        "candidate_bridge_version": CANDIDATE_BRIDGE_VERSION,
        "rollout_version": ROLLOUT_VERSION,
        "monte_carlo_version": MONTE_CARLO_VERSION,
        "root_action_eval_version": ROOT_ACTION_EVAL_VERSION,
        "adaptive_root_eval_version": ADAPTIVE_ROOT_EVAL_VERSION,
        "root_world_cache_version": ROOT_WORLD_CACHE_VERSION,
        "parallel_root_eval_version": PARALLEL_ROOT_EVAL_VERSION,
        "rules_version": RULES_VERSION,
        "model_version": MODEL_VERSION,
        "information_schema_version": INFORMATION_SCHEMA_VERSION,
        "value_key_schema_version": VALUE_KEY_SCHEMA_VERSION,
        "ordinary_action_families": ORDINARY_ACTION_FAMILY_COUNT,
        "contingent_action_families": CONTINGENT_ACTION_FAMILY_COUNT,
        "policy_input_boundary": "urza-policy still consumes only InformationState plus public PolicyCandidate records; hidden-world sampling and exact execution remain outside the policy crate",
        "bridge_contract": "all accepted R4 Action families remain collision-free public candidates with exact opaque-token round trip",
        "rollout_contract": "each sampled exact world is evaluated only through the accepted deterministic urza-rollout driver",
        "hidden_world_contract": "the exact template supplies execution scaffolding, but its unknown library order is discarded: the unknown middle is canonicalized as a public multiset and shuffled with an OuterHiddenWorld coordinate derived from public library belief plus WorldId",
        "monte_carlo_contract": "fixed world identities are evaluated independently, outcomes are returned in canonical WorldId order, terminal wins aggregate by T1-T6 and WinFamily, and only a true T6 horizon is counted as a loss",
        "rng_contract": "outer hidden-world sampling uses the OuterHiddenWorld domain; game randomness inside each rollout uses the existing Game domain with the same explicit root and sampled WorldId",
        "completion_contract": "StepLimit and NoCandidate are incomplete evaluations and fail either Monte Carlo or root-action comparison rather than being silently recorded as losses",
        "root_action_contract": "every legal public root candidate is forced on the same canonical sampled WorldId set; each sampled world remaps the public class+PolicyPublicKey to its exact execution Action before branching",
        "value_contract": "fixed-budget WinByHorizon ranking maximizes total terminal wins first, then exact-turn wins lexicographically T1 through T6; exact value ties keep the smallest public root semantic key",
        "root_rng_contract": "the forced root action uses Game logical event 0 and deterministic continuation begins at logical event 1, matching normal rollout sequencing without coordinate reuse",
        "adaptive_contract": "adaptive evaluation consumes common WorldIds in canonical batches and stops early only when the complete configured fixed-budget root ranking is mathematically unable to change under any remaining outcomes; this is exact finite-budget certification rather than a probabilistic confidence interval",
        "cache_contract": "root-world outcomes are keyed by canonical ValueKey, complete EvaluationNamespace, RootSeed, public RootActionKey, WorldId, and cache schema version; serial and parallel schedulers intentionally share the same cache identity because scheduling is non-semantic",
        "parallel_contract": "parallel workers dynamically claim independent prepared root/world jobs from a non-semantic atomic queue; workers never mutate the cache or aggregate values, RNG coordinates contain no thread identity, and both outcomes and typed failures are interpreted only after canonical job-index ordering so worker scheduling cannot change exact results or error precedence",
        "instrumentation_contract": "deterministic counters report worlds, root-world requests, cache hits/misses, actual rollouts, and executed/avoided rollout steps; serial and parallel adaptive paths preserve the same counters and instrumentation does not participate in value ranking or cache identity",
        "current_scope": "fixed-budget serial root evaluation remains the correctness oracle; exact adaptive ranking certification, shared root-world caching, deterministic cycle escape, and load-balanced deterministic parallel root/world execution are complete around it",
        "next_r5_work": "measure on larger core counts and production-sized workloads, then decide whether optional statistical stopping is worth adding only if serial parity, common-world pairing, RNG identity, strict incomplete semantics, and cache namespace safety remain exact",
    });

    println!(
        "{}",
        serde_json::to_string_pretty(&report).expect("serializable R5 audit report")
    );
}
