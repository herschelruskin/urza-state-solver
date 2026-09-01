use serde_json::json;
use urza_cards::{
    R2CardDatabase, R3CardDatabase, URZA_CONSTRUCT_TOKEN_CARD_ID, catalog_digest_hex, load_catalog,
    load_coverage, load_r1_catalog, r1_catalog_digest_hex, validate_catalog_and_coverage,
    validate_r1_catalog, validate_r2_database, validate_r3_database,
};
use urza_cli::hand25_fixture;
use urza_core::{MODEL_VERSION, TrueState};
use urza_rng::RNG_SCHEME_VERSION;
use urza_rules::{HORIZON_TURN, R2_RULES_VERSION, R2CardRole, RULES_VERSION};

fn main() {
    let command = std::env::args().nth(1).unwrap_or_else(|| "help".to_owned());
    match command.as_str() {
        "r0-audit" => run_r0_audit(),
        "r1-audit" => run_r1_audit(),
        "r2-audit" => run_r2_audit(),
        "r3-audit" => run_r3_audit(),
        _ => {
            eprintln!("usage: urza-cli <r0-audit|r1-audit|r2-audit|r3-audit>");
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
        "model_version": MODEL_VERSION,
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
        "phase": "R3-start",
        "rules_version": RULES_VERSION,
        "model_version": MODEL_VERSION,
        "horizon_turn": HORIZON_TURN,
        "supported_active_card_identities": supported_names.len(),
        "supported_active_names": supported_names,
        "staged_simple_tutors": simple_tutors,
        "decision_boundary": "commit -> search observation -> target/no-find -> shared pre-target shuffle",
        "scope": "initial R3 staged-search foundation; Whir/Reshape/Transmute/Bay/Saga/Tezzeret/Top/scry/Urza spin remain to broaden",
    });

    println!(
        "{}",
        serde_json::to_string_pretty(&report).expect("serializable R3 audit report")
    );
}
