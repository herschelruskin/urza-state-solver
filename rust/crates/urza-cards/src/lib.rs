#![forbid(unsafe_code)]

use std::collections::{BTreeMap, BTreeSet};

use serde::Deserialize;
use thiserror::Error;
use urza_core::CardDefId;

const CATALOG_JSON: &str = include_str!(concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../../data/card_catalog.r0.json"
));
const COVERAGE_JSON: &str = include_str!(concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../../data/card_coverage.r0.json"
));
const DECKLIST: &str = include_str!(concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../../../decklist.txt"
));

#[derive(Debug, Clone, Deserialize, PartialEq, Eq)]
pub struct CardCatalog {
    pub schema_version: u16,
    pub catalog_version: String,
    pub metadata_scope: String,
    pub source_branch: String,
    pub source_decklist_blob_sha: String,
    pub cards: Vec<CardCatalogEntry>,
}

#[derive(Debug, Clone, Deserialize, PartialEq, Eq)]
pub struct CardCatalogEntry {
    pub id: u16,
    pub name: String,
    pub deck_count: u8,
    pub commander: bool,
}

impl CardCatalogEntry {
    pub fn card_def_id(&self) -> CardDefId {
        CardDefId(self.id)
    }
}

#[derive(Debug, Clone, Deserialize, PartialEq, Eq)]
pub struct CoverageRegistry {
    pub schema_version: u16,
    pub coverage_version: String,
    pub entries: Vec<CoverageEntry>,
}

#[derive(Debug, Clone, Deserialize, PartialEq, Eq)]
pub struct CoverageEntry {
    pub card_id: u16,
    pub status: CoverageStatus,
    pub reason: Option<String>,
}

#[derive(Debug, Clone, Copy, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum CoverageStatus {
    RulesActive,
    PrimitiveActive,
    EnvironmentDeferred,
    PolicyOnly,
    IntentionallyUnmodeled,
}

#[derive(Debug, Error, PartialEq, Eq)]
pub enum CatalogError {
    #[error("invalid embedded JSON: {0}")]
    InvalidJson(String),
    #[error("catalog invariant failed: {0}")]
    Invariant(String),
}

pub fn load_catalog() -> Result<CardCatalog, CatalogError> {
    serde_json::from_str(CATALOG_JSON).map_err(|e| CatalogError::InvalidJson(e.to_string()))
}

pub fn load_coverage() -> Result<CoverageRegistry, CatalogError> {
    serde_json::from_str(COVERAGE_JSON).map_err(|e| CatalogError::InvalidJson(e.to_string()))
}

pub fn catalog_digest_hex() -> String {
    blake3::hash(CATALOG_JSON.as_bytes()).to_hex().to_string()
}

pub fn validate_catalog_and_coverage() -> Result<(), CatalogError> {
    let catalog = load_catalog()?;
    let coverage = load_coverage()?;

    if catalog.cards.len() != 95 {
        return Err(CatalogError::Invariant(format!(
            "expected 95 distinct active names including commander, got {}",
            catalog.cards.len()
        )));
    }

    let mut ids = BTreeSet::new();
    let mut names = BTreeSet::new();
    for card in &catalog.cards {
        if !ids.insert(card.id) {
            return Err(CatalogError::Invariant(format!(
                "duplicate card id {}",
                card.id
            )));
        }
        if !names.insert(card.name.clone()) {
            return Err(CatalogError::Invariant(format!(
                "duplicate card name {}",
                card.name
            )));
        }
    }

    let commanders: Vec<_> = catalog.cards.iter().filter(|c| c.commander).collect();
    if commanders.len() != 1 || commanders[0].name != "Urza, Lord High Artificer" {
        return Err(CatalogError::Invariant(
            "expected exactly Urza as commander".to_owned(),
        ));
    }

    let noncommander_count: u16 = catalog
        .cards
        .iter()
        .filter(|c| !c.commander)
        .map(|c| u16::from(c.deck_count))
        .sum();
    if noncommander_count != 99 {
        return Err(CatalogError::Invariant(format!(
            "expected 99 noncommander cards, got {noncommander_count}"
        )));
    }

    let deck_counts = parse_decklist(DECKLIST)?;
    let catalog_counts: BTreeMap<_, _> = catalog
        .cards
        .iter()
        .map(|c| (c.name.clone(), c.deck_count))
        .collect();
    if deck_counts != catalog_counts {
        return Err(CatalogError::Invariant(
            "catalog identity/counts do not match decklist.txt".to_owned(),
        ));
    }

    if coverage.entries.len() != catalog.cards.len() {
        return Err(CatalogError::Invariant(format!(
            "coverage has {} entries for {} catalog cards",
            coverage.entries.len(),
            catalog.cards.len()
        )));
    }

    let mut covered = BTreeSet::new();
    for entry in &coverage.entries {
        if !ids.contains(&entry.card_id) {
            return Err(CatalogError::Invariant(format!(
                "coverage references unknown card id {}",
                entry.card_id
            )));
        }
        if !covered.insert(entry.card_id) {
            return Err(CatalogError::Invariant(format!(
                "duplicate coverage classification for card id {}",
                entry.card_id
            )));
        }
        if entry.status == CoverageStatus::IntentionallyUnmodeled
            && entry.reason.as_deref().unwrap_or_default().is_empty()
        {
            return Err(CatalogError::Invariant(format!(
                "INTENTIONALLY_UNMODELED card id {} must include a reason",
                entry.card_id
            )));
        }
    }

    if covered != ids {
        return Err(CatalogError::Invariant(
            "one or more active cards lack an explicit coverage status".to_owned(),
        ));
    }

    Ok(())
}

fn parse_decklist(input: &str) -> Result<BTreeMap<String, u8>, CatalogError> {
    let mut out = BTreeMap::new();
    for (index, raw) in input.lines().enumerate() {
        let line = raw.trim();
        if line.is_empty() {
            continue;
        }
        let (count, name) = line.split_once(' ').ok_or_else(|| {
            CatalogError::Invariant(format!("malformed decklist line {}", index + 1))
        })?;
        let count = count.parse::<u8>().map_err(|_| {
            CatalogError::Invariant(format!("invalid count on decklist line {}", index + 1))
        })?;
        if out.insert(name.to_owned(), count).is_some() {
            return Err(CatalogError::Invariant(format!(
                "duplicate decklist name {name}"
            )));
        }
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn active_deck_catalog_and_coverage_are_total() {
        validate_catalog_and_coverage().unwrap();
    }

    #[test]
    fn r0_does_not_falsely_claim_rules_coverage() {
        let coverage = load_coverage().unwrap();
        assert!(coverage.entries.iter().all(|entry| {
            entry.status == CoverageStatus::IntentionallyUnmodeled
                && entry
                    .reason
                    .as_deref()
                    .is_some_and(|reason| !reason.is_empty())
        }));
    }

    #[test]
    fn catalog_ids_are_dense_and_deterministic() {
        let catalog = load_catalog().unwrap();
        for (expected, card) in catalog.cards.iter().enumerate() {
            assert_eq!(card.id as usize, expected);
        }
    }
}
