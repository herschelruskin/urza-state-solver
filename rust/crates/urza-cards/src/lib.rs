#![forbid(unsafe_code)]

use std::collections::{BTreeMap, BTreeSet};

use serde::Deserialize;
use thiserror::Error;
use urza_core::CardDefId;

const CATALOG_R0_JSON: &str = include_str!(concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../../data/card_catalog.r0.json"
));
const CATALOG_R1_JSON: &str = include_str!(concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../../data/card_catalog.r1.json"
));
const COVERAGE_JSON: &str = include_str!(concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../../data/card_coverage.r0.json"
));
const DECKLIST: &str = include_str!(concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../../../decklist.txt"
));

pub const R0_CATALOG_DIGEST_BLAKE3: &str =
    "2ef2f7dd52b72af46d24a0183096803ef9fb9d65524b9e77f7d87da4e2809f21";

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
pub struct R1CardCatalog {
    pub schema_version: u16,
    pub catalog_version: String,
    pub catalog_as_of_utc: String,
    pub source: R1CatalogSource,
    pub r0_catalog_digest_blake3: String,
    pub cards: Vec<R1CardMetadata>,
}

#[derive(Debug, Clone, Deserialize, PartialEq, Eq)]
pub struct R1CatalogSource {
    pub provider: String,
    pub bulk_api: String,
    pub bulk_type: String,
    pub bulk_id: String,
    pub bulk_updated_at: String,
    pub bulk_download_uri: String,
    pub bulk_file_sha256: String,
    pub content_type: Option<String>,
    pub content_encoding: Option<String>,
}

#[derive(Debug, Clone, Deserialize, PartialEq, Eq)]
pub struct R1CardMetadata {
    pub id: u16,
    pub deck_name: String,
    pub oracle_name: String,
    pub deck_count: u8,
    pub commander: bool,
    pub oracle_id: String,
    pub source_scryfall_id: String,
    pub layout: String,
    pub mana_cost: String,
    pub mana_value: u16,
    pub type_line: String,
    pub oracle_text_sha256: String,
    pub faces: Vec<R1CardFaceMetadata>,
    pub deck_face_index: Option<u8>,
    pub feature_flags: R1FeatureFlags,
}

impl R1CardMetadata {
    pub fn card_def_id(&self) -> CardDefId {
        CardDefId(self.id)
    }
}

#[derive(Debug, Clone, Deserialize, PartialEq, Eq)]
pub struct R1CardFaceMetadata {
    pub name: String,
    pub mana_cost: String,
    pub type_line: String,
}

#[derive(Debug, Clone, Deserialize, PartialEq, Eq)]
pub struct R1FeatureFlags {
    pub is_artifact: bool,
    pub is_creature: bool,
    pub is_enchantment: bool,
    pub is_instant: bool,
    pub is_land: bool,
    pub is_planeswalker: bool,
    pub is_sorcery: bool,
    pub is_multiface: bool,
    pub is_modal_dfc: bool,
    pub has_x_cost: bool,
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
    serde_json::from_str(CATALOG_R0_JSON).map_err(|e| CatalogError::InvalidJson(e.to_string()))
}

pub fn load_r1_catalog() -> Result<R1CardCatalog, CatalogError> {
    serde_json::from_str(CATALOG_R1_JSON).map_err(|e| CatalogError::InvalidJson(e.to_string()))
}

pub fn load_coverage() -> Result<CoverageRegistry, CatalogError> {
    serde_json::from_str(COVERAGE_JSON).map_err(|e| CatalogError::InvalidJson(e.to_string()))
}

pub fn catalog_digest_hex() -> String {
    blake3::hash(CATALOG_R0_JSON.as_bytes()).to_hex().to_string()
}

pub fn r1_catalog_digest_hex() -> String {
    blake3::hash(CATALOG_R1_JSON.as_bytes()).to_hex().to_string()
}

pub fn validate_catalog_and_coverage() -> Result<(), CatalogError> {
    let catalog = load_catalog()?;
    let coverage = load_coverage()?;

    let digest = catalog_digest_hex();
    if digest != R0_CATALOG_DIGEST_BLAKE3 {
        return Err(CatalogError::Invariant(format!(
            "R0 catalog digest drift: expected {R0_CATALOG_DIGEST_BLAKE3}, got {digest}"
        )));
    }

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
            return Err(CatalogError::Invariant(format!("duplicate card id {}", card.id)));
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

pub fn validate_r1_catalog() -> Result<(), CatalogError> {
    validate_catalog_and_coverage()?;
    let r0 = load_catalog()?;
    let r1 = load_r1_catalog()?;

    if r1.schema_version != 1 {
        return Err(CatalogError::Invariant(format!(
            "unexpected R1 catalog schema {}",
            r1.schema_version
        )));
    }
    if r1.r0_catalog_digest_blake3 != R0_CATALOG_DIGEST_BLAKE3 {
        return Err(CatalogError::Invariant(
            "R1 catalog does not point at the pinned R0 identity catalog".to_owned(),
        ));
    }
    if r1.catalog_as_of_utc != r1.source.bulk_updated_at {
        return Err(CatalogError::Invariant(
            "R1 catalog as-of time must equal the pinned bulk snapshot update time".to_owned(),
        ));
    }
    if r1.source.bulk_type != "default_cards" {
        return Err(CatalogError::Invariant(format!(
            "R1 catalog expected default_cards source, got {}",
            r1.source.bulk_type
        )));
    }
    if !is_hex_digest(&r1.source.bulk_file_sha256, 64) {
        return Err(CatalogError::Invariant(
            "R1 bulk file SHA-256 is malformed".to_owned(),
        ));
    }
    if r1.cards.len() != r0.cards.len() {
        return Err(CatalogError::Invariant(format!(
            "R1 catalog has {} cards for {} R0 identities",
            r1.cards.len(),
            r0.cards.len()
        )));
    }

    let mut oracle_ids = BTreeSet::new();
    for (expected_id, (r0_card, card)) in r0.cards.iter().zip(&r1.cards).enumerate() {
        if card.id as usize != expected_id || card.id != r0_card.id {
            return Err(CatalogError::Invariant(format!(
                "R1 CardDefId mismatch at position {expected_id}"
            )));
        }
        if card.deck_name != r0_card.name
            || card.deck_count != r0_card.deck_count
            || card.commander != r0_card.commander
        {
            return Err(CatalogError::Invariant(format!(
                "R1 identity/count mismatch for CardDefId {}",
                card.id
            )));
        }
        if !oracle_ids.insert(card.oracle_id.clone()) {
            return Err(CatalogError::Invariant(format!(
                "duplicate gameplay Oracle ID {}",
                card.oracle_id
            )));
        }
        if !is_uuid_like(&card.oracle_id) || !is_uuid_like(&card.source_scryfall_id) {
            return Err(CatalogError::Invariant(format!(
                "malformed external identity for {}",
                card.deck_name
            )));
        }
        if !is_hex_digest(&card.oracle_text_sha256, 64) {
            return Err(CatalogError::Invariant(format!(
                "malformed Oracle text digest for {}",
                card.deck_name
            )));
        }

        let face_index = card.deck_face_index.map(usize::from);
        if card.faces.is_empty() {
            if face_index.is_some() || card.oracle_name != card.deck_name {
                return Err(CatalogError::Invariant(format!(
                    "single-face identity mismatch for {}",
                    card.deck_name
                )));
            }
        } else {
            let Some(index) = face_index else {
                return Err(CatalogError::Invariant(format!(
                    "multiface card {} lacks deck_face_index",
                    card.deck_name
                )));
            };
            let Some(face) = card.faces.get(index) else {
                return Err(CatalogError::Invariant(format!(
                    "deck_face_index out of range for {}",
                    card.deck_name
                )));
            };
            if face.name != card.deck_name {
                return Err(CatalogError::Invariant(format!(
                    "matched deck face does not equal deck name for {}",
                    card.deck_name
                )));
            }
        }

        let expected_flags = derive_feature_flags(card);
        if expected_flags != card.feature_flags {
            return Err(CatalogError::Invariant(format!(
                "derived feature flags drift for {}",
                card.deck_name
            )));
        }
    }

    Ok(())
}

fn derive_feature_flags(card: &R1CardMetadata) -> R1FeatureFlags {
    let type_lines: Vec<&str> = if card.faces.is_empty() {
        vec![card.type_line.as_str()]
    } else {
        card.faces.iter().map(|face| face.type_line.as_str()).collect()
    };
    let contains_type = |needle: &str| {
        type_lines.iter().any(|line| {
            line.split(|ch: char| ch.is_whitespace() || ch == '—' || ch == '/')
                .any(|word| word == needle)
        })
    };
    let has_x_cost = if card.faces.is_empty() {
        card.mana_cost.contains("{X}")
    } else {
        card.faces.iter().any(|face| face.mana_cost.contains("{X}"))
    };

    R1FeatureFlags {
        is_artifact: contains_type("Artifact"),
        is_creature: contains_type("Creature"),
        is_enchantment: contains_type("Enchantment"),
        is_instant: contains_type("Instant"),
        is_land: contains_type("Land"),
        is_planeswalker: contains_type("Planeswalker"),
        is_sorcery: contains_type("Sorcery"),
        is_multiface: !card.faces.is_empty(),
        is_modal_dfc: card.layout == "modal_dfc",
        has_x_cost,
    }
}

fn is_hex_digest(value: &str, len: usize) -> bool {
    value.len() == len
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

fn is_uuid_like(value: &str) -> bool {
    value.len() == 36
        && value
            .chars()
            .enumerate()
            .all(|(index, ch)| match index {
                8 | 13 | 18 | 23 => ch == '-',
                _ => ch.is_ascii_hexdigit(),
            })
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
    fn r0_catalog_digest_is_explicitly_pinned() {
        assert_eq!(catalog_digest_hex(), R0_CATALOG_DIGEST_BLAKE3);
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

    #[test]
    fn r1_catalog_is_total_pinned_and_syntactically_self_consistent() {
        validate_r1_catalog().unwrap();
    }

    #[test]
    fn r1_catalog_tracks_the_three_active_modal_dfcs() {
        let catalog = load_r1_catalog().unwrap();
        let dfcs: Vec<_> = catalog
            .cards
            .iter()
            .filter(|card| card.feature_flags.is_modal_dfc)
            .map(|card| card.deck_name.as_str())
            .collect();
        assert_eq!(
            dfcs,
            vec![
                "Hydroelectric Specimen",
                "Sea Gate Restoration",
                "Sink into Stupor"
            ]
        );
    }
}
