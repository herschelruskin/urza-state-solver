use serde_json::json;
use urza_cards::{catalog_digest_hex, load_catalog, load_coverage, validate_catalog_and_coverage};
use urza_cli::hand25_fixture;
use urza_core::TrueState;
use urza_rng::RNG_SCHEME_VERSION;

fn main() {
    let command = std::env::args().nth(1).unwrap_or_else(|| "help".to_owned());
    match command.as_str() {
        "r0-audit" => run_r0_audit(),
        _ => {
            eprintln!("usage: urza-cli r0-audit");
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
        "coverage_policy": "explicit; all R0 entries intentionally unmodeled until rules fixtures exist",
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
