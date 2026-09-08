use std::collections::BTreeMap;
use std::error::Error;

use urza_cards::{CurrentCardDatabase, CoverageStatus, load_coverage, load_r1_catalog};
use urza_rules::R2CardRole;

fn main() {
    if let Err(error) = run() {
        eprintln!("post-R7 card model coverage audit failed: {error}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), Box<dyn Error>> {
    let catalog = load_r1_catalog()?;
    let coverage = load_coverage()?;
    let database = CurrentCardDatabase::load()?;
    let coverage_by_id = coverage
        .entries
        .into_iter()
        .map(|entry| (entry.card_id, entry))
        .collect::<BTreeMap<_, _>>();

    let mut supported = 0_usize;
    let mut unsupported = 0_usize;
    let mut rules_active = 0_usize;
    let mut primitive_active = 0_usize;
    let mut environment_deferred = 0_usize;
    let mut policy_only = 0_usize;
    let mut intentionally_unmodeled = 0_usize;

    println!("CARD_MODEL_COVERAGE_AUDIT\tpost_r7_current_database_v1");
    println!("CARD\tid\tname\tcommander\tcoverage\truntime_supported\trole\tengine\tutility\tsimple_tutor\tspecial_search\tspell_effect\treason");

    for card in &catalog.cards {
        let entry = coverage_by_id
            .get(&card.id)
            .ok_or_else(|| format!("missing coverage entry for id {}", card.id))?;
        match entry.status {
            CoverageStatus::RulesActive => rules_active += 1,
            CoverageStatus::PrimitiveActive => primitive_active += 1,
            CoverageStatus::EnvironmentDeferred => environment_deferred += 1,
            CoverageStatus::PolicyOnly => policy_only += 1,
            CoverageStatus::IntentionallyUnmodeled => intentionally_unmodeled += 1,
        }

        let profile = database
            .profile(card.card_def_id())
            .ok_or_else(|| format!("missing current database profile for {}", card.deck_name))?;
        let runtime_supported = profile.role != R2CardRole::Unsupported;
        if runtime_supported {
            supported += 1;
        } else {
            unsupported += 1;
        }

        let reason = entry
            .reason
            .as_deref()
            .unwrap_or("")
            .replace('\t', " ")
            .replace('\n', " ");
        println!(
            "CARD\t{}\t{}\t{}\t{:?}\t{}\t{:?}\t{:?}\t{:?}\t{:?}\t{:?}\t{:?}\t{}",
            card.id,
            card.deck_name,
            card.commander,
            entry.status,
            runtime_supported,
            profile.role,
            profile.engine,
            profile.utility,
            profile.simple_tutor,
            profile.special_search,
            profile.spell_effect,
            reason,
        );
    }

    println!(
        "SUMMARY\tidentities={}\tsupported={}\tunsupported={}\trules_active={}\tprimitive_active={}\tenvironment_deferred={}\tpolicy_only={}\tintentionally_unmodeled={}",
        catalog.cards.len(),
        supported,
        unsupported,
        rules_active,
        primitive_active,
        environment_deferred,
        policy_only,
        intentionally_unmodeled,
    );
    Ok(())
}
