#![forbid(unsafe_code)]

use std::collections::{BTreeMap, BTreeSet};

use serde::Deserialize;
use thiserror::Error;
use urza_core::{CardDefId, CardFace};

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
pub const R1_CATALOG_DIGEST_BLAKE3: &str =
    "4b39c7db7bfd2c6f68d7a49efa515cdffb2c6a9716022bc0b21eeec56754a983";
pub const R3_ACCEPTED_ACTIVE_IDENTITY_COUNT: usize = 32;
pub const R4_ACCEPTED_ACTIVE_IDENTITY_COUNT: usize = 47;
pub const POST_R7_ACCEPTED_ACTIVE_IDENTITY_COUNT: usize = 52;
pub const POST_R7_CARD_DATABASE_VERSION: &str =
    "post_r7_modeling_completeness_v2_rules_active_repair";
pub const R4_ONLY_ACTIVE_NAMES: [&str; 15] = [
    "Basalt Monolith",
    "Grim Monolith",
    "Forensic Gadgeteer",
    "Power Artifact",
    "The Reality Chip",
    "Fortune Teller's Talent",
    "Grafdigger's Cage",
    "Grinding Station",
    "Battered Golem",
    "Chrome Dome",
    "Mana Vault",
    "Banishing Knack",
    "Retraction Helix",
    "Valley Floodcaller",
    "Sewer-veillance Cam",
];

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
    blake3::hash(CATALOG_R0_JSON.as_bytes())
        .to_hex()
        .to_string()
}

pub fn r1_catalog_digest_hex() -> String {
    blake3::hash(CATALOG_R1_JSON.as_bytes())
        .to_hex()
        .to_string()
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

pub fn validate_r1_catalog() -> Result<(), CatalogError> {
    validate_catalog_and_coverage()?;
    let r0 = load_catalog()?;
    let r1 = load_r1_catalog()?;

    let digest = r1_catalog_digest_hex();
    if digest != R1_CATALOG_DIGEST_BLAKE3 {
        return Err(CatalogError::Invariant(format!(
            "R1 catalog digest drift: expected {R1_CATALOG_DIGEST_BLAKE3}, got {digest}"
        )));
    }

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
        card.faces
            .iter()
            .map(|face| face.type_line.as_str())
            .collect()
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
        && value.chars().enumerate().all(|(index, ch)| match index {
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

pub const URZA_CONSTRUCT_TOKEN_CARD_ID: CardDefId = CardDefId(95);
pub const CLUE_TOKEN_CARD_ID: CardDefId = CardDefId(96);

#[derive(Debug, Clone)]
pub struct R2CardDatabase {
    cards: BTreeMap<CardDefId, urza_rules::CardProfile>,
}

impl R2CardDatabase {
    pub fn load() -> Result<Self, CatalogError> {
        let catalog = load_r1_catalog()?;
        let mut cards = BTreeMap::new();

        for card in catalog.cards {
            let (role, battlefield_face, land_entry, mana_ability) =
                r2_primitive_shape(card.deck_name.as_str());

            let mana_cost = if role == urza_rules::R2CardRole::Land {
                None
            } else {
                match urza_rules::ManaCost::parse_scryfall(&card.mana_cost) {
                    Ok(cost) => Some(cost),
                    Err(_) if role == urza_rules::R2CardRole::Unsupported => None,
                    Err(error) => {
                        return Err(CatalogError::Invariant(format!(
                            "R2 mana-cost parse failed for {}: {error}",
                            card.deck_name
                        )));
                    }
                }
            };

            cards.insert(
                CardDefId(card.id),
                urza_rules::CardProfile {
                    card: CardDefId(card.id),
                    mana_cost,
                    mana_value: card.mana_value,
                    role,
                    battlefield_face,
                    land_entry,
                    mana_ability,
                    search_classes: urza_rules::SearchClassFlags {
                        spellseeker: (card.feature_flags.is_instant
                            || card.feature_flags.is_sorcery)
                            && card.mana_value <= 2,
                        // The pinned active deck is mono-blue; every instant
                        // card in this catalog is blue. If future card-swap
                        // catalogs break that invariant, pin color metadata
                        // before extending this index.
                        merchant_scroll: card.feature_flags.is_instant,
                        mystical_tutor: card.feature_flags.is_instant
                            || card.feature_flags.is_sorcery,
                        saga_iii: card.feature_flags.is_artifact
                            && matches!(card.mana_cost.as_str(), "{0}" | "{1}"),
                    },
                    simple_tutor: None,
                    special_search: urza_rules::SpecialSearchKind::None,
                    utility: urza_rules::UtilityKind::None,
                    engine: urza_rules::EngineKind::None,
                    aura_target: urza_rules::AuraTargetKind::None,
                    spell_effect: urza_rules::SpellEffectKind::None,
                    native_untap_generic: None,
                    artifact_activation_reduction: 0,
                    attached_artifact_activation_reduction: 0,
                    top_loop_producer: false,
                    floodcaller_untap_eligible: false,
                    skip_normal_untap: false,
                    starting_loyalty: 0,
                    is_artifact: card.feature_flags.is_artifact,
                    is_creature: card.feature_flags.is_creature,
                },
            );
        }

        cards.insert(
            URZA_CONSTRUCT_TOKEN_CARD_ID,
            urza_rules::CardProfile {
                card: URZA_CONSTRUCT_TOKEN_CARD_ID,
                mana_cost: None,
                mana_value: 0,
                role: urza_rules::R2CardRole::UrzaConstructToken,
                battlefield_face: CardFace::Front,
                land_entry: urza_rules::LandEntryRule::None,
                mana_ability: urza_rules::ManaAbility::None,
                search_classes: urza_rules::SearchClassFlags::default(),
                simple_tutor: None,
                special_search: urza_rules::SpecialSearchKind::None,
                utility: urza_rules::UtilityKind::None,
                engine: urza_rules::EngineKind::None,
                aura_target: urza_rules::AuraTargetKind::None,
                spell_effect: urza_rules::SpellEffectKind::None,
                native_untap_generic: None,
                artifact_activation_reduction: 0,
                attached_artifact_activation_reduction: 0,
                top_loop_producer: false,
                floodcaller_untap_eligible: false,
                skip_normal_untap: false,
                starting_loyalty: 0,
                is_artifact: true,
                is_creature: true,
            },
        );

        Ok(Self { cards })
    }

    pub fn profile(&self, card: CardDefId) -> Option<urza_rules::CardProfile> {
        self.cards.get(&card).copied()
    }

    pub fn card_id_by_name(&self, name: &str) -> Result<CardDefId, CatalogError> {
        let catalog = load_r1_catalog()?;
        catalog
            .cards
            .iter()
            .find(|card| card.deck_name == name)
            .map(|card| CardDefId(card.id))
            .ok_or_else(|| CatalogError::Invariant(format!("unknown active card name {name}")))
    }

    pub fn supported_active_cards(&self) -> Vec<CardDefId> {
        self.cards
            .iter()
            .filter_map(|(card, profile)| {
                (card.0 < URZA_CONSTRUCT_TOKEN_CARD_ID.0
                    && profile.role != urza_rules::R2CardRole::Unsupported)
                    .then_some(*card)
            })
            .collect()
    }
}

impl urza_rules::CardDatabase for R2CardDatabase {
    fn profile(&self, card: CardDefId) -> Option<urza_rules::CardProfile> {
        self.profile(card)
    }

    fn commander_card(&self) -> CardDefId {
        self.cards
            .values()
            .find(|profile| profile.role == urza_rules::R2CardRole::UrzaCommander)
            .map(|profile| profile.card)
            .expect("validated R2 database contains Urza")
    }

    fn urza_construct_token_card(&self) -> CardDefId {
        URZA_CONSTRUCT_TOKEN_CARD_ID
    }
}

#[derive(Debug, Clone)]
pub struct R3CardDatabase {
    cards: BTreeMap<CardDefId, urza_rules::CardProfile>,
}

impl R3CardDatabase {
    pub fn load() -> Result<Self, CatalogError> {
        let mut cards = R2CardDatabase::load()?.cards;

        for (name, role, tutor) in [
            (
                "Spellseeker",
                urza_rules::R2CardRole::CreaturePermanent,
                urza_rules::SimpleTutorKind::Spellseeker,
            ),
            (
                "Merchant Scroll",
                urza_rules::R2CardRole::SearchSpell,
                urza_rules::SimpleTutorKind::MerchantScroll,
            ),
            (
                "Mystical Tutor",
                urza_rules::R2CardRole::SearchSpell,
                urza_rules::SimpleTutorKind::MysticalTutor,
            ),
        ] {
            let card = card_id_by_name_from_r1(name)?;
            let profile = cards
                .get_mut(&card)
                .ok_or_else(|| CatalogError::Invariant(format!("missing R3 profile for {name}")))?;
            profile.role = role;
            profile.simple_tutor = Some(tutor);
        }

        for (name, kind, base_cost) in [
            (
                "Whir of Invention",
                urza_rules::SpecialSearchKind::Whir,
                urza_rules::ManaCost {
                    blue: 3,
                    ..urza_rules::ManaCost::default()
                },
            ),
            (
                "Reshape",
                urza_rules::SpecialSearchKind::Reshape,
                urza_rules::ManaCost {
                    blue: 2,
                    ..urza_rules::ManaCost::default()
                },
            ),
            (
                "Transmute Artifact",
                urza_rules::SpecialSearchKind::TransmuteArtifact,
                urza_rules::ManaCost {
                    blue: 2,
                    ..urza_rules::ManaCost::default()
                },
            ),
        ] {
            let card = card_id_by_name_from_r1(name)?;
            let profile = cards
                .get_mut(&card)
                .ok_or_else(|| CatalogError::Invariant(format!("missing R3 profile for {name}")))?;
            profile.role = urza_rules::R2CardRole::SearchSpell;
            profile.special_search = kind;
            profile.mana_cost = Some(base_cost);
        }

        let bay = card_id_by_name_from_r1("Repurposing Bay")?;
        let bay_profile = cards.get_mut(&bay).ok_or_else(|| {
            CatalogError::Invariant("missing R3 Repurposing Bay profile".to_owned())
        })?;
        bay_profile.role = urza_rules::R2CardRole::ArtifactPermanent;
        bay_profile.special_search = urza_rules::SpecialSearchKind::RepurposingBay;

        let top = card_id_by_name_from_r1("Sensei's Divining Top")?;
        let top_profile = cards.get_mut(&top).ok_or_else(|| {
            CatalogError::Invariant("missing R3 Sensei's Divining Top profile".to_owned())
        })?;
        top_profile.role = urza_rules::R2CardRole::ArtifactPermanent;
        top_profile.utility = urza_rules::UtilityKind::SenseisDiviningTop;

        let saga = card_id_by_name_from_r1("Urza's Saga")?;
        let saga_profile = cards
            .get_mut(&saga)
            .ok_or_else(|| CatalogError::Invariant("missing R3 Urza's Saga profile".to_owned()))?;
        saga_profile.role = urza_rules::R2CardRole::Land;
        saga_profile.battlefield_face = CardFace::Front;
        saga_profile.land_entry = urza_rules::LandEntryRule::Untapped;
        saga_profile.mana_ability = urza_rules::ManaAbility::None;
        saga_profile.utility = urza_rules::UtilityKind::UrzasSaga;

        let tezzeret = card_id_by_name_from_r1("Tezzeret, Cruel Captain")?;
        let tezzeret_profile = cards
            .get_mut(&tezzeret)
            .ok_or_else(|| CatalogError::Invariant("missing R3 Tezzeret profile".to_owned()))?;
        tezzeret_profile.role = urza_rules::R2CardRole::PlaneswalkerPermanent;
        tezzeret_profile.utility = urza_rules::UtilityKind::TezzeretCruelCaptain;
        tezzeret_profile.starting_loyalty = 4;

        Ok(Self { cards })
    }

    pub fn profile(&self, card: CardDefId) -> Option<urza_rules::CardProfile> {
        self.cards.get(&card).copied()
    }

    pub fn card_id_by_name(&self, name: &str) -> Result<CardDefId, CatalogError> {
        card_id_by_name_from_r1(name)
    }

    pub fn supported_active_cards(&self) -> Vec<CardDefId> {
        self.cards
            .iter()
            .filter_map(|(card, profile)| {
                (card.0 < URZA_CONSTRUCT_TOKEN_CARD_ID.0
                    && profile.role != urza_rules::R2CardRole::Unsupported)
                    .then_some(*card)
            })
            .collect()
    }
}

impl urza_rules::CardDatabase for R3CardDatabase {
    fn profile(&self, card: CardDefId) -> Option<urza_rules::CardProfile> {
        self.profile(card)
    }

    fn commander_card(&self) -> CardDefId {
        self.cards
            .values()
            .find(|profile| profile.role == urza_rules::R2CardRole::UrzaCommander)
            .map(|profile| profile.card)
            .expect("validated R3 database contains Urza")
    }

    fn urza_construct_token_card(&self) -> CardDefId {
        URZA_CONSTRUCT_TOKEN_CARD_ID
    }
}

#[derive(Debug, Clone)]
pub struct R4CardDatabase {
    cards: BTreeMap<CardDefId, urza_rules::CardProfile>,
}

impl R4CardDatabase {
    pub fn load() -> Result<Self, CatalogError> {
        let mut cards = R3CardDatabase::load()?.cards;

        for (name, engine, untap_cost) in [
            (
                "Basalt Monolith",
                urza_rules::EngineKind::BasaltMonolith,
                3_u16,
            ),
            ("Grim Monolith", urza_rules::EngineKind::GrimMonolith, 4_u16),
        ] {
            let card = card_id_by_name_from_r1(name)?;
            let profile = cards
                .get_mut(&card)
                .ok_or_else(|| CatalogError::Invariant(format!("missing R4 profile for {name}")))?;
            profile.role = urza_rules::R2CardRole::ArtifactPermanent;
            profile.engine = engine;
            profile.mana_ability = urza_rules::ManaAbility::TapForColorless(3);
            profile.native_untap_generic = Some(untap_cost);
            profile.skip_normal_untap = true;
        }

        let gadgeteer = card_id_by_name_from_r1("Forensic Gadgeteer")?;
        let gadgeteer_profile = cards.get_mut(&gadgeteer).ok_or_else(|| {
            CatalogError::Invariant("missing R4 Forensic Gadgeteer profile".to_owned())
        })?;
        gadgeteer_profile.role = urza_rules::R2CardRole::CreaturePermanent;
        gadgeteer_profile.engine = urza_rules::EngineKind::ForensicGadgeteer;
        gadgeteer_profile.artifact_activation_reduction = 1;
        gadgeteer_profile.top_loop_producer = true;

        let power_artifact = card_id_by_name_from_r1("Power Artifact")?;
        let power_artifact_profile = cards.get_mut(&power_artifact).ok_or_else(|| {
            CatalogError::Invariant("missing R4 Power Artifact profile".to_owned())
        })?;
        power_artifact_profile.role = urza_rules::R2CardRole::EnchantmentPermanent;
        power_artifact_profile.engine = urza_rules::EngineKind::PowerArtifact;
        power_artifact_profile.aura_target = urza_rules::AuraTargetKind::Artifact;
        power_artifact_profile.attached_artifact_activation_reduction = 2;

        let reality_chip = card_id_by_name_from_r1("The Reality Chip")?;
        let reality_chip_profile = cards
            .get_mut(&reality_chip)
            .ok_or_else(|| CatalogError::Invariant("missing R4 Reality Chip profile".to_owned()))?;
        reality_chip_profile.role = urza_rules::R2CardRole::CreaturePermanent;
        reality_chip_profile.utility = urza_rules::UtilityKind::RealityChip;

        let ftt = card_id_by_name_from_r1("Fortune Teller's Talent")?;
        let ftt_profile = cards
            .get_mut(&ftt)
            .ok_or_else(|| CatalogError::Invariant("missing R4 FTT profile".to_owned()))?;
        ftt_profile.role = urza_rules::R2CardRole::EnchantmentPermanent;
        ftt_profile.utility = urza_rules::UtilityKind::FortuneTellersTalent;

        let cage = card_id_by_name_from_r1("Grafdigger's Cage")?;
        let cage_profile = cards
            .get_mut(&cage)
            .ok_or_else(|| CatalogError::Invariant("missing R4 Cage profile".to_owned()))?;
        cage_profile.role = urza_rules::R2CardRole::ArtifactPermanent;
        cage_profile.utility = urza_rules::UtilityKind::GrafdiggersCage;

        let station = card_id_by_name_from_r1("Grinding Station")?;
        let station_profile = cards
            .get_mut(&station)
            .ok_or_else(|| CatalogError::Invariant("missing R4 Station profile".to_owned()))?;
        station_profile.role = urza_rules::R2CardRole::ArtifactPermanent;
        station_profile.engine = urza_rules::EngineKind::GrindingStation;
        station_profile.top_loop_producer = true;

        let golem = card_id_by_name_from_r1("Battered Golem")?;
        let golem_profile = cards
            .get_mut(&golem)
            .ok_or_else(|| CatalogError::Invariant("missing R4 Golem profile".to_owned()))?;
        golem_profile.role = urza_rules::R2CardRole::CreaturePermanent;
        golem_profile.engine = urza_rules::EngineKind::BatteredGolem;
        golem_profile.top_loop_producer = true;
        golem_profile.skip_normal_untap = true;

        let chrome = card_id_by_name_from_r1("Chrome Dome")?;
        let chrome_profile = cards
            .get_mut(&chrome)
            .ok_or_else(|| CatalogError::Invariant("missing R4 Chrome Dome profile".to_owned()))?;
        chrome_profile.role = urza_rules::R2CardRole::CreaturePermanent;
        chrome_profile.engine = urza_rules::EngineKind::ChromeDome;

        let vault = card_id_by_name_from_r1("Mana Vault")?;
        let vault_profile = cards
            .get_mut(&vault)
            .ok_or_else(|| CatalogError::Invariant("missing R4 Mana Vault profile".to_owned()))?;
        vault_profile.role = urza_rules::R2CardRole::ArtifactPermanent;
        vault_profile.engine = urza_rules::EngineKind::ManaVault;
        vault_profile.mana_ability = urza_rules::ManaAbility::TapForColorless(3);
        vault_profile.skip_normal_untap = true;

        for name in ["Banishing Knack", "Retraction Helix"] {
            let card = card_id_by_name_from_r1(name)?;
            let profile = cards
                .get_mut(&card)
                .ok_or_else(|| CatalogError::Invariant(format!("missing R4 profile for {name}")))?;
            profile.role = urza_rules::R2CardRole::TargetedEffectSpell;
            profile.spell_effect = urza_rules::SpellEffectKind::KnackBounceGrant;
        }

        let floodcaller = card_id_by_name_from_r1("Valley Floodcaller")?;
        let floodcaller_profile = cards.get_mut(&floodcaller).ok_or_else(|| {
            CatalogError::Invariant("missing R4 Valley Floodcaller profile".to_owned())
        })?;
        floodcaller_profile.role = urza_rules::R2CardRole::CreaturePermanent;
        floodcaller_profile.engine = urza_rules::EngineKind::ValleyFloodcaller;
        floodcaller_profile.floodcaller_untap_eligible = true;

        let cam = card_id_by_name_from_r1("Sewer-veillance Cam")?;
        let cam_profile = cards
            .get_mut(&cam)
            .ok_or_else(|| CatalogError::Invariant("missing R4 Cam profile".to_owned()))?;
        cam_profile.role = urza_rules::R2CardRole::ArtifactPermanent;
        cam_profile.utility = urza_rules::UtilityKind::SewerVeillanceCam;

        cards.insert(
            CLUE_TOKEN_CARD_ID,
            urza_rules::CardProfile {
                card: CLUE_TOKEN_CARD_ID,
                mana_cost: None,
                mana_value: 0,
                role: urza_rules::R2CardRole::ArtifactPermanent,
                battlefield_face: CardFace::Front,
                is_artifact: true,
                ..urza_rules::CardProfile::default()
            },
        );

        Ok(Self { cards })
    }

    pub fn profile(&self, card: CardDefId) -> Option<urza_rules::CardProfile> {
        self.cards.get(&card).copied()
    }

    pub fn card_id_by_name(&self, name: &str) -> Result<CardDefId, CatalogError> {
        card_id_by_name_from_r1(name)
    }

    pub fn supported_active_cards(&self) -> Vec<CardDefId> {
        self.cards
            .iter()
            .filter_map(|(card, profile)| {
                (card.0 < URZA_CONSTRUCT_TOKEN_CARD_ID.0
                    && profile.role != urza_rules::R2CardRole::Unsupported)
                    .then_some(*card)
            })
            .collect()
    }
}

impl urza_rules::CardDatabase for R4CardDatabase {
    fn profile(&self, card: CardDefId) -> Option<urza_rules::CardProfile> {
        self.profile(card)
    }

    fn commander_card(&self) -> CardDefId {
        self.cards
            .values()
            .find(|profile| profile.role == urza_rules::R2CardRole::UrzaCommander)
            .map(|profile| profile.card)
            .expect("validated R4 database contains Urza")
    }

    fn urza_construct_token_card(&self) -> CardDefId {
        URZA_CONSTRUCT_TOKEN_CARD_ID
    }

    fn clue_token_card(&self) -> Option<CardDefId> {
        Some(CLUE_TOKEN_CARD_ID)
    }
}

#[derive(Debug, Clone)]
pub struct PostR7CardDatabase {
    cards: BTreeMap<CardDefId, urza_rules::CardProfile>,
    printed_powers: BTreeMap<CardDefId, i16>,
    historic_cards: BTreeSet<CardDefId>,
}

pub type CurrentCardDatabase = PostR7CardDatabase;

impl PostR7CardDatabase {
    pub fn load() -> Result<Self, CatalogError> {
        let mut cards = R4CardDatabase::load()?.cards;
        let ring = card_id_by_name_from_r1("The One Ring")?;
        let profile = cards.get_mut(&ring).ok_or_else(|| {
            CatalogError::Invariant("missing post-R7 One Ring profile".to_owned())
        })?;
        profile.role = urza_rules::R2CardRole::ArtifactPermanent;
        profile.utility = urza_rules::UtilityKind::TheOneRing;
        profile.is_artifact = true;

        let uthros = card_id_by_name_from_r1("Uthros Research Craft")?;
        let uthros_profile = cards.get_mut(&uthros).ok_or_else(|| {
            CatalogError::Invariant("missing post-R7 Uthros Research Craft profile".to_owned())
        })?;
        uthros_profile.role = urza_rules::R2CardRole::ArtifactPermanent;
        uthros_profile.utility = urza_rules::UtilityKind::UthrosResearchCraft;
        uthros_profile.is_artifact = true;

        let assistant = card_id_by_name_from_r1("Artificer's Assistant")?;
        let assistant_profile = cards.get_mut(&assistant).ok_or_else(|| {
            CatalogError::Invariant("missing post-R7 Artificer's Assistant profile".to_owned())
        })?;
        assistant_profile.role = urza_rules::R2CardRole::CreaturePermanent;
        assistant_profile.utility = urza_rules::UtilityKind::ArtificersAssistant;
        assistant_profile.floodcaller_untap_eligible = true;
        assistant_profile.is_creature = true;

        let lotus = card_id_by_name_from_r1("Lotus Petal")?;
        let lotus_profile = cards.get_mut(&lotus).ok_or_else(|| {
            CatalogError::Invariant("missing post-R7 Lotus Petal profile".to_owned())
        })?;
        lotus_profile.role = urza_rules::R2CardRole::ArtifactPermanent;
        lotus_profile.mana_cost = Some(urza_rules::ManaCost::default());
        lotus_profile.mana_ability = urza_rules::ManaAbility::TapSacrificeForBlue;
        lotus_profile.is_artifact = true;

        let mox_opal = card_id_by_name_from_r1("Mox Opal")?;
        let mox_opal_profile = cards.get_mut(&mox_opal).ok_or_else(|| {
            CatalogError::Invariant("missing post-R7 Mox Opal profile".to_owned())
        })?;
        mox_opal_profile.role = urza_rules::R2CardRole::ArtifactPermanent;
        mox_opal_profile.mana_cost = Some(urza_rules::ManaCost::default());
        mox_opal_profile.mana_ability = urza_rules::ManaAbility::MetalcraftTapForBlue;
        mox_opal_profile.is_artifact = true;

        let catalog = load_r1_catalog()?;
        let historic_cards = catalog
            .cards
            .iter()
            .filter(|card| metadata_is_historic(card))
            .map(|card| CardDefId(card.id))
            .collect::<BTreeSet<_>>();

        // Public printed powers used by Station. Keeping this table in the
        // current database avoids mutating the frozen R1 metadata schema/digest.
        // Dynamic Construct power is computed by urza-rules instead.
        let mut printed_powers = BTreeMap::new();
        for (name, power) in [
            ("Artificer's Assistant", 1_i16),
            ("Battered Golem", 3),
            ("Chrome Dome", 1),
            ("Faerie Mastermind", 2),
            ("Forensic Gadgeteer", 2),
            ("Hope of Ghirapur", 1),
            ("Hydroelectric Specimen", 1),
            ("Spellseeker", 1),
            ("Spellskite", 0),
            ("The Reality Chip", 0),
            ("Urza, Lord High Artificer", 1),
            ("Valley Floodcaller", 2),
        ] {
            printed_powers.insert(card_id_by_name_from_r1(name)?, power);
        }
        Ok(Self {
            cards,
            printed_powers,
            historic_cards,
        })
    }

    pub fn profile(&self, card: CardDefId) -> Option<urza_rules::CardProfile> {
        self.cards.get(&card).copied()
    }

    pub fn card_id_by_name(&self, name: &str) -> Result<CardDefId, CatalogError> {
        card_id_by_name_from_r1(name)
    }

    pub fn supported_active_cards(&self) -> Vec<CardDefId> {
        self.cards
            .iter()
            .filter_map(|(card, profile)| {
                (card.0 < URZA_CONSTRUCT_TOKEN_CARD_ID.0
                    && profile.role != urza_rules::R2CardRole::Unsupported)
                    .then_some(*card)
            })
            .collect()
    }

    pub fn printed_power(&self, card: CardDefId) -> Option<i16> {
        self.printed_powers.get(&card).copied()
    }
}

impl urza_rules::CardDatabase for PostR7CardDatabase {
    fn profile(&self, card: CardDefId) -> Option<urza_rules::CardProfile> {
        self.profile(card)
    }

    fn commander_card(&self) -> CardDefId {
        self.cards
            .values()
            .find(|profile| profile.role == urza_rules::R2CardRole::UrzaCommander)
            .map(|profile| profile.card)
            .expect("validated post-R7 database contains Urza")
    }

    fn urza_construct_token_card(&self) -> CardDefId {
        URZA_CONSTRUCT_TOKEN_CARD_ID
    }

    fn clue_token_card(&self) -> Option<CardDefId> {
        Some(CLUE_TOKEN_CARD_ID)
    }

    fn printed_power(&self, card: CardDefId) -> Option<i16> {
        self.printed_power(card)
    }

    fn is_historic_spell(&self, card: CardDefId) -> bool {
        self.historic_cards.contains(&card)
    }
}

fn metadata_is_historic(card: &R1CardMetadata) -> bool {
    if card.feature_flags.is_artifact {
        return true;
    }
    let historic_type_line = |line: &str| {
        line.split(|ch: char| ch.is_whitespace() || ch == '—' || ch == '/')
            .any(|word| matches!(word, "Legendary" | "Saga"))
    };
    historic_type_line(&card.type_line)
        || card
            .faces
            .iter()
            .any(|face| historic_type_line(&face.type_line))
}

fn card_id_by_name_from_r1(name: &str) -> Result<CardDefId, CatalogError> {
    let catalog = load_r1_catalog()?;
    catalog
        .cards
        .iter()
        .find(|card| card.deck_name == name)
        .map(|card| CardDefId(card.id))
        .ok_or_else(|| CatalogError::Invariant(format!("unknown active card name {name}")))
}

pub fn validate_r3_database() -> Result<(), CatalogError> {
    let catalog = load_r1_catalog()?;
    let coverage = load_coverage()?;
    let database = R3CardDatabase::load()?;
    let coverage_by_id: BTreeMap<_, _> = coverage
        .entries
        .iter()
        .map(|entry| (entry.card_id, entry.status))
        .collect();

    for card in &catalog.cards {
        let profile = database.profile(CardDefId(card.id)).ok_or_else(|| {
            CatalogError::Invariant(format!("missing R3 profile for {}", card.deck_name))
        })?;
        let status = *coverage_by_id.get(&card.id).ok_or_else(|| {
            CatalogError::Invariant(format!("missing coverage for {}", card.deck_name))
        })?;

        if profile.role != urza_rules::R2CardRole::Unsupported
            && !matches!(
                status,
                CoverageStatus::PrimitiveActive | CoverageStatus::RulesActive
            )
        {
            return Err(CatalogError::Invariant(format!(
                "{} has an R3-visible rules primitive but coverage says {:?}",
                card.deck_name, status
            )));
        }
    }

    if database.supported_active_cards().len() != R3_ACCEPTED_ACTIVE_IDENTITY_COUNT {
        return Err(CatalogError::Invariant(format!(
            "historical R3 database must remain exactly {R3_ACCEPTED_ACTIVE_IDENTITY_COUNT} active identities"
        )));
    }

    Ok(())
}

pub fn validate_r4_database() -> Result<(), CatalogError> {
    // R4 acceptance is cumulative: its audit must fail if an earlier accepted
    // catalog/database contract has drifted even when the standalone R4 count
    // would otherwise still look plausible.
    validate_r1_catalog()?;
    validate_r2_database()?;
    validate_r3_database()?;

    let catalog = load_r1_catalog()?;
    let coverage = load_coverage()?;
    let database = R4CardDatabase::load()?;
    let coverage_by_id: BTreeMap<_, _> = coverage
        .entries
        .iter()
        .map(|entry| (entry.card_id, entry.status))
        .collect();

    for card in &catalog.cards {
        let profile = database.profile(CardDefId(card.id)).ok_or_else(|| {
            CatalogError::Invariant(format!("missing R4 profile for {}", card.deck_name))
        })?;
        let status = *coverage_by_id.get(&card.id).ok_or_else(|| {
            CatalogError::Invariant(format!("missing coverage for {}", card.deck_name))
        })?;

        if profile.role != urza_rules::R2CardRole::Unsupported
            && !matches!(
                status,
                CoverageStatus::PrimitiveActive | CoverageStatus::RulesActive
            )
        {
            return Err(CatalogError::Invariant(format!(
                "{} has an R4-visible rules primitive but coverage says {:?}",
                card.deck_name, status
            )));
        }
    }

    let r4_supported: BTreeSet<_> = database.supported_active_cards().into_iter().collect();
    if r4_supported.len() != R4_ACCEPTED_ACTIVE_IDENTITY_COUNT {
        return Err(CatalogError::Invariant(format!(
            "accepted R4 database must expose exactly {R4_ACCEPTED_ACTIVE_IDENTITY_COUNT} active identities"
        )));
    }

    let r3_database = R3CardDatabase::load()?;
    let r3_supported: BTreeSet<_> = r3_database.supported_active_cards().into_iter().collect();
    if !r3_supported.is_subset(&r4_supported) {
        return Err(CatalogError::Invariant(
            "accepted R4 database must be a strict extension of the frozen R3 surface".to_owned(),
        ));
    }

    let actual_r4_only: BTreeSet<_> = r4_supported.difference(&r3_supported).copied().collect();
    let mut expected_r4_only = BTreeSet::new();
    for name in R4_ONLY_ACTIVE_NAMES {
        let card = card_id_by_name_from_r1(name)?;
        expected_r4_only.insert(card);
        let coverage_entry = coverage
            .entries
            .iter()
            .find(|entry| entry.card_id == card.0)
            .ok_or_else(|| CatalogError::Invariant(format!("missing R4 coverage for {name}")))?;
        if !coverage_entry
            .reason
            .as_deref()
            .unwrap_or_default()
            .contains("R4")
        {
            return Err(CatalogError::Invariant(format!(
                "accepted R4-only card {name} must carry an R4-specific coverage reason"
            )));
        }
    }
    if actual_r4_only != expected_r4_only {
        return Err(CatalogError::Invariant(format!(
            "R4-only active identity set drift: expected {expected_r4_only:?}, got {actual_r4_only:?}"
        )));
    }

    Ok(())
}

pub fn validate_post_r7_database() -> Result<(), CatalogError> {
    validate_r4_database()?;
    let coverage = load_coverage()?;
    let database = PostR7CardDatabase::load()?;
    let supported: BTreeSet<_> = database.supported_active_cards().into_iter().collect();
    if supported.len() != POST_R7_ACCEPTED_ACTIVE_IDENTITY_COUNT {
        return Err(CatalogError::Invariant(format!(
            "post-R7 database must expose exactly {POST_R7_ACCEPTED_ACTIVE_IDENTITY_COUNT} active identities"
        )));
    }

    let r4 = R4CardDatabase::load()?;
    let r4_supported: BTreeSet<_> = r4.supported_active_cards().into_iter().collect();
    if !r4_supported.is_subset(&supported) {
        return Err(CatalogError::Invariant(
            "post-R7 database must extend the frozen R4 surface".to_owned(),
        ));
    }
    let added: BTreeSet<_> = supported.difference(&r4_supported).copied().collect();
    let ring = card_id_by_name_from_r1("The One Ring")?;
    let uthros = card_id_by_name_from_r1("Uthros Research Craft")?;
    let assistant = card_id_by_name_from_r1("Artificer's Assistant")?;
    let lotus = card_id_by_name_from_r1("Lotus Petal")?;
    let mox_opal = card_id_by_name_from_r1("Mox Opal")?;
    if added != BTreeSet::from([ring, uthros, assistant, lotus, mox_opal]) {
        return Err(CatalogError::Invariant(format!(
            "post-R7 current surface must add exactly Ring, Uthros, Artificer's Assistant, Lotus Petal, and Mox Opal, got {added:?}"
        )));
    }
    let ring_coverage = coverage
        .entries
        .iter()
        .find(|entry| entry.card_id == ring.0)
        .ok_or_else(|| CatalogError::Invariant("missing One Ring coverage entry".to_owned()))?;
    if !matches!(
        ring_coverage.status,
        CoverageStatus::PrimitiveActive | CoverageStatus::RulesActive
    ) {
        return Err(CatalogError::Invariant(
            "The One Ring must be active in post-R7 coverage".to_owned(),
        ));
    }
    let uthros_coverage = coverage
        .entries
        .iter()
        .find(|entry| entry.card_id == uthros.0)
        .ok_or_else(|| CatalogError::Invariant("missing Uthros coverage entry".to_owned()))?;
    if !matches!(
        uthros_coverage.status,
        CoverageStatus::PrimitiveActive | CoverageStatus::RulesActive
    ) {
        return Err(CatalogError::Invariant(
            "Uthros Research Craft must be active in post-R7 coverage".to_owned(),
        ));
    }
    let assistant_coverage = coverage
        .entries
        .iter()
        .find(|entry| entry.card_id == assistant.0)
        .ok_or_else(|| {
            CatalogError::Invariant("missing Artificer's Assistant coverage entry".to_owned())
        })?;
    if !matches!(
        assistant_coverage.status,
        CoverageStatus::PrimitiveActive | CoverageStatus::RulesActive
    ) {
        return Err(CatalogError::Invariant(
            "Artificer's Assistant must be active in post-R7 coverage".to_owned(),
        ));
    }
    Ok(())
}

fn r2_primitive_shape(
    name: &str,
) -> (
    urza_rules::R2CardRole,
    CardFace,
    urza_rules::LandEntryRule,
    urza_rules::ManaAbility,
) {
    use urza_rules::{LandEntryRule, ManaAbility, R2CardRole};

    match name {
        "Ancient Tomb" => (
            R2CardRole::Land,
            CardFace::Front,
            LandEntryRule::Untapped,
            ManaAbility::TapForColorlessAndDamage { mana: 2, damage: 2 },
        ),
        "Cephalid Coliseum" => (
            R2CardRole::Land,
            CardFace::Front,
            LandEntryRule::Untapped,
            ManaAbility::TapForBlueAndDamage { damage: 1 },
        ),
        "Crystal Vein" => (
            R2CardRole::Land,
            CardFace::Front,
            LandEntryRule::Untapped,
            ManaAbility::TapForColorless(1),
        ),
        "Hydroelectric Specimen" | "Sea Gate Restoration" | "Sink into Stupor" => (
            R2CardRole::Land,
            CardFace::Back,
            LandEntryRule::PayLifeOrTapped { life: 3 },
            ManaAbility::TapForBlue,
        ),
        "Island"
        | "Minamo, School at Water's Edge"
        | "Oboro, Palace in the Clouds"
        | "Otawara, Soaring City"
        | "Seat of the Synod" => (
            R2CardRole::Land,
            CardFace::Front,
            LandEntryRule::Untapped,
            ManaAbility::TapForBlue,
        ),
        "Sol Ring" => (
            R2CardRole::ArtifactPermanent,
            CardFace::Front,
            LandEntryRule::None,
            ManaAbility::TapForColorless(2),
        ),
        "Aether Spellbomb" | "Codex Shredder" | "Hope of Ghirapur" | "Manifold Key"
        | "Mishra's Bauble" | "Tormod's Crypt" | "Urza's Bauble" | "Voltaic Key"
        | "Welding Jar" => (
            R2CardRole::ArtifactPermanent,
            CardFace::Front,
            LandEntryRule::None,
            ManaAbility::None,
        ),
        "Urza, Lord High Artificer" => (
            R2CardRole::UrzaCommander,
            CardFace::Front,
            LandEntryRule::None,
            ManaAbility::None,
        ),
        _ => (
            R2CardRole::Unsupported,
            CardFace::Front,
            LandEntryRule::None,
            ManaAbility::None,
        ),
    }
}

pub fn validate_r2_database() -> Result<(), CatalogError> {
    let catalog = load_r1_catalog()?;
    let coverage = load_coverage()?;
    let database = R2CardDatabase::load()?;

    let coverage_by_id: BTreeMap<_, _> = coverage
        .entries
        .iter()
        .map(|entry| (entry.card_id, entry.status))
        .collect();

    for card in &catalog.cards {
        let profile = database.profile(CardDefId(card.id)).ok_or_else(|| {
            CatalogError::Invariant(format!("missing R2 profile for {}", card.deck_name))
        })?;
        let status = *coverage_by_id.get(&card.id).ok_or_else(|| {
            CatalogError::Invariant(format!("missing coverage for {}", card.deck_name))
        })?;

        if profile.role != urza_rules::R2CardRole::Unsupported
            && !matches!(
                status,
                CoverageStatus::PrimitiveActive | CoverageStatus::RulesActive
            )
        {
            return Err(CatalogError::Invariant(format!(
                "{} has an R2 primitive but coverage says {:?}",
                card.deck_name, status
            )));
        }
    }

    if catalog
        .cards
        .iter()
        .any(|card| CardDefId(card.id) == URZA_CONSTRUCT_TOKEN_CARD_ID)
    {
        return Err(CatalogError::Invariant(
            "synthetic Construct token collided with active-card catalog".to_owned(),
        ));
    }

    let construct = database
        .profile(URZA_CONSTRUCT_TOKEN_CARD_ID)
        .ok_or_else(|| CatalogError::Invariant("missing synthetic Construct profile".to_owned()))?;
    if construct.role != urza_rules::R2CardRole::UrzaConstructToken
        || !construct.is_artifact
        || !construct.is_creature
    {
        return Err(CatalogError::Invariant(
            "synthetic Construct profile is malformed".to_owned(),
        ));
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use urza_core::{
        CardZone, CommanderState, CommanderZone, ManaPool, ObjectId, Phase, TrueLibrary, TrueState,
        Window,
    };
    use urza_rules::{
        Action, LandEntryChoice, ManaPayment, R2CardRole, RulesObservation, SimpleTutorKind,
        advance_automatic, apply_action,
    };

    fn object_for(state: &TrueState, card: CardDefId) -> ObjectId {
        state
            .battlefield
            .permanents()
            .iter()
            .find(|permanent| permanent.card == card)
            .expect("expected permanent")
            .object_id
    }

    #[test]
    fn active_deck_catalog_and_coverage_are_total() {
        validate_catalog_and_coverage().unwrap();
    }

    #[test]
    fn r0_catalog_digest_is_explicitly_pinned() {
        assert_eq!(catalog_digest_hex(), R0_CATALOG_DIGEST_BLAKE3);
    }

    #[test]
    fn r1_catalog_is_total_pinned_and_syntactically_self_consistent() {
        validate_r1_catalog().unwrap();
        assert_eq!(r1_catalog_digest_hex(), R1_CATALOG_DIGEST_BLAKE3);
    }

    #[test]
    fn post_r7_priority_card_text_hashes_are_explicitly_pinned() {
        let catalog = load_r1_catalog().unwrap();
        // These digests correspond to the exact pinned Oracle text documented
        // in POST_R7_TEXT_SCRY_STACK_VALIDATION.md. They are deliberately
        // checked without changing the frozen R1 metadata schema.
        for (name, expected) in [
            (
                "Artificer's Assistant",
                "4500992939e68bf5d0e9ccaae34745d9b5493891717d983002967d79a4d583f6",
            ),
            (
                "Faerie Mastermind",
                "9057053fb56b1a7734ce8ae12241f7eb15814d48df0cd2dc3b13e4994333a438",
            ),
            (
                "Mystic Remora",
                "4c1b24efecbfc96ef5aa572d00c124322ce5f061349ecbec21e3a0676021a00b",
            ),
            (
                "Rhystic Study",
                "b01edb4edf239cd0b4116ab58ea2fb90152ed9b83b068b6ea34ccbe8d67fd03c",
            ),
        ] {
            let card = catalog
                .cards
                .iter()
                .find(|card| card.deck_name == name)
                .unwrap();
            assert_eq!(
                card.oracle_text_sha256, expected,
                "Oracle text drift for {name}"
            );
            assert_ne!(
                card.oracle_text_sha256,
                "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "{name} must not have empty Oracle text"
            );
        }
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

    #[test]
    fn r2_database_and_coverage_are_bidirectionally_consistent() {
        validate_r2_database().unwrap();
        let r2 = R2CardDatabase::load().unwrap();
        assert_eq!(r2.supported_active_cards().len(), 22);
    }

    #[test]
    fn r2_mdfc_land_primitives_use_back_face_and_life_choice() {
        let r2 = R2CardDatabase::load().unwrap();
        for name in [
            "Hydroelectric Specimen",
            "Sea Gate Restoration",
            "Sink into Stupor",
        ] {
            let card = r2.card_id_by_name(name).unwrap();
            let profile = r2.profile(card).unwrap();
            assert_eq!(profile.role, R2CardRole::Land);
            assert_eq!(profile.battlefield_face, CardFace::Back);
            assert_eq!(
                profile.land_entry,
                urza_rules::LandEntryRule::PayLifeOrTapped { life: 3 }
            );
            assert_eq!(profile.mana_ability, urza_rules::ManaAbility::TapForBlue);
        }
    }

    #[test]
    fn r2_real_catalog_acceptance_trajectory_matches_audited_witness_semantics() {
        let cards = R2CardDatabase::load().unwrap();
        let island = cards.card_id_by_name("Island").unwrap();
        let sol_ring = cards.card_id_by_name("Sol Ring").unwrap();
        let urza = cards.card_id_by_name("Urza, Lord High Artificer").unwrap();

        let mut state = TrueState {
            turn: 1,
            phase: Phase::PrecombatMain,
            window: Window::Priority,
            library: TrueLibrary::unknown(vec![island]),
            hand: CardZone::new(vec![island, sol_ring]),
            commander: CommanderState {
                zone: CommanderZone::CommandZone,
                command_zone_casts: 0,
            },
            ..TrueState::default()
        };

        apply_action(
            &mut state,
            &cards,
            Action::PlayLand {
                card: island,
                entry: LandEntryChoice::Default,
            },
        )
        .unwrap();
        let first_island = object_for(&state, island);
        apply_action(
            &mut state,
            &cards,
            Action::ActivateManaAbility {
                source: first_island,
            },
        )
        .unwrap();
        apply_action(
            &mut state,
            &cards,
            Action::CastFromHand {
                card: sol_ring,
                payment: ManaPayment {
                    blue: 1,
                    ..ManaPayment::default()
                },
            },
        )
        .unwrap();

        assert_eq!(state.stack.len(), 1);
        assert!(
            state
                .battlefield
                .permanents()
                .iter()
                .all(|p| p.card != sol_ring)
        );
        let resolution = apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        assert_eq!(
            resolution.observations,
            vec![RulesObservation::PermanentEntered {
                card: sol_ring,
                face: CardFace::Front,
                token: false,
            }]
        );

        let sol_ring_object = object_for(&state, sol_ring);
        apply_action(
            &mut state,
            &cards,
            Action::ActivateManaAbility {
                source: sol_ring_object,
            },
        )
        .unwrap();
        assert_eq!(
            state.mana,
            ManaPool {
                colorless: 2,
                ..ManaPool::default()
            }
        );

        apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        advance_automatic(&mut state, &cards).unwrap();
        assert_eq!(state.turn, 2);
        assert_eq!(state.phase, Phase::Upkeep);

        let natural_draw = apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        assert_eq!(
            natural_draw.observations,
            vec![RulesObservation::CardsDrawn(vec![island])]
        );
        assert_eq!(state.hand.cards(), &[island]);
        assert!(state.library.cards().is_empty());

        apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        assert_eq!(state.phase, Phase::PrecombatMain);
        apply_action(
            &mut state,
            &cards,
            Action::PlayLand {
                card: island,
                entry: LandEntryChoice::Default,
            },
        )
        .unwrap();

        let islands: Vec<_> = state
            .battlefield
            .permanents()
            .iter()
            .filter(|permanent| permanent.card == island)
            .map(|permanent| permanent.object_id)
            .collect();
        assert_eq!(islands.len(), 2);
        for source in islands {
            apply_action(&mut state, &cards, Action::ActivateManaAbility { source }).unwrap();
        }
        apply_action(
            &mut state,
            &cards,
            Action::ActivateManaAbility {
                source: sol_ring_object,
            },
        )
        .unwrap();

        apply_action(
            &mut state,
            &cards,
            Action::CastCommander {
                payment: ManaPayment {
                    blue: 2,
                    colorless: 2,
                    ..ManaPayment::default()
                },
            },
        )
        .unwrap();
        assert_eq!(state.commander.zone, CommanderZone::Stack);

        let urza_resolution = apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        assert_eq!(state.commander.zone, CommanderZone::Battlefield);
        assert_eq!(state.commander.command_zone_casts, 1);
        assert_eq!(
            urza_resolution.observations,
            vec![
                RulesObservation::PermanentEntered {
                    card: urza,
                    face: CardFace::Front,
                    token: false,
                },
                RulesObservation::PermanentEntered {
                    card: URZA_CONSTRUCT_TOKEN_CARD_ID,
                    face: CardFace::Front,
                    token: true,
                },
            ]
        );

        let construct = object_for(&state, URZA_CONSTRUCT_TOKEN_CARD_ID);
        apply_action(
            &mut state,
            &cards,
            Action::ActivateUrzaArtifactMana {
                artifact: construct,
            },
        )
        .unwrap();
        assert_eq!(state.mana.blue, 1);
        assert!(state.battlefield.get(construct).unwrap().tapped);
    }

    #[test]
    fn catalog_ids_are_dense_and_deterministic() {
        let catalog = load_catalog().unwrap();
        for (expected, card) in catalog.cards.iter().enumerate() {
            assert_eq!(card.id as usize, expected);
        }
    }

    #[test]
    fn r3_simple_tutor_registry_extends_r2_without_reclassifying_later_mechanics() {
        validate_r3_database().unwrap();
        let r3 = R3CardDatabase::load().unwrap();
        assert_eq!(r3.supported_active_cards().len(), 32);

        let spellseeker = r3.card_id_by_name("Spellseeker").unwrap();
        let merchant = r3.card_id_by_name("Merchant Scroll").unwrap();
        let mystical = r3.card_id_by_name("Mystical Tutor").unwrap();

        assert_eq!(
            r3.profile(spellseeker).unwrap().simple_tutor,
            Some(SimpleTutorKind::Spellseeker)
        );
        assert_eq!(
            r3.profile(spellseeker).unwrap().role,
            R2CardRole::CreaturePermanent
        );
        assert_eq!(
            r3.profile(merchant).unwrap().simple_tutor,
            Some(SimpleTutorKind::MerchantScroll)
        );
        assert_eq!(r3.profile(merchant).unwrap().role, R2CardRole::SearchSpell);
        assert_eq!(
            r3.profile(mystical).unwrap().simple_tutor,
            Some(SimpleTutorKind::MysticalTutor)
        );
        assert_eq!(r3.profile(mystical).unwrap().role, R2CardRole::SearchSpell);
    }

    #[test]
    fn pinned_search_class_indexes_capture_simple_tutor_constraints() {
        let r3 = R3CardDatabase::load().unwrap();
        let pact = r3.card_id_by_name("Pact of Negation").unwrap();
        let whir = r3.card_id_by_name("Whir of Invention").unwrap();
        let merchant = r3.card_id_by_name("Merchant Scroll").unwrap();
        let sol_ring = r3.card_id_by_name("Sol Ring").unwrap();

        let pact_profile = r3.profile(pact).unwrap();
        assert!(pact_profile.search_classes.spellseeker);
        assert!(pact_profile.search_classes.merchant_scroll);
        assert!(pact_profile.search_classes.mystical_tutor);

        let whir_profile = r3.profile(whir).unwrap();
        assert!(!whir_profile.search_classes.spellseeker);
        assert!(whir_profile.search_classes.merchant_scroll);
        assert!(whir_profile.search_classes.mystical_tutor);

        let merchant_profile = r3.profile(merchant).unwrap();
        assert!(merchant_profile.search_classes.spellseeker);
        assert!(!merchant_profile.search_classes.merchant_scroll);
        assert!(merchant_profile.search_classes.mystical_tutor);

        let sol_ring_profile = r3.profile(sol_ring).unwrap();
        assert!(!sol_ring_profile.search_classes.spellseeker);
        assert!(!sol_ring_profile.search_classes.merchant_scroll);
        assert!(!sol_ring_profile.search_classes.mystical_tutor);
        assert!(sol_ring_profile.search_classes.saga_iii);
    }

    #[test]
    fn r3_advanced_search_registry_carries_x_and_activation_mechanics() {
        let r3 = R3CardDatabase::load().unwrap();
        for (name, expected) in [
            ("Whir of Invention", urza_rules::SpecialSearchKind::Whir),
            ("Reshape", urza_rules::SpecialSearchKind::Reshape),
            (
                "Transmute Artifact",
                urza_rules::SpecialSearchKind::TransmuteArtifact,
            ),
            (
                "Repurposing Bay",
                urza_rules::SpecialSearchKind::RepurposingBay,
            ),
        ] {
            let card = r3.card_id_by_name(name).unwrap();
            assert_eq!(r3.profile(card).unwrap().special_search, expected);
        }

        let whir = r3.card_id_by_name("Whir of Invention").unwrap();
        assert_eq!(
            r3.profile(whir).unwrap().mana_cost,
            Some(urza_rules::ManaCost {
                blue: 3,
                ..urza_rules::ManaCost::default()
            })
        );
        let reshape = r3.card_id_by_name("Reshape").unwrap();
        assert_eq!(
            r3.profile(reshape).unwrap().mana_cost,
            Some(urza_rules::ManaCost {
                blue: 2,
                ..urza_rules::ManaCost::default()
            })
        );
    }

    #[test]
    fn r3_top_registry_activates_top_without_reclassifying_other_artifacts() {
        let r3 = R3CardDatabase::load().unwrap();
        let top = r3.card_id_by_name("Sensei's Divining Top").unwrap();
        let key = r3.card_id_by_name("Voltaic Key").unwrap();
        assert_eq!(
            r3.profile(top).unwrap().utility,
            urza_rules::UtilityKind::SenseisDiviningTop
        );
        assert_eq!(
            r3.profile(key).unwrap().utility,
            urza_rules::UtilityKind::None
        );
    }

    #[test]
    fn r3_saga_and_tezzeret_registry_encode_exact_search_constraints() {
        let r3 = R3CardDatabase::load().unwrap();
        let saga = r3.card_id_by_name("Urza's Saga").unwrap();
        let tezzeret = r3.card_id_by_name("Tezzeret, Cruel Captain").unwrap();
        let top = r3.card_id_by_name("Sensei's Divining Top").unwrap();
        let chalice = r3.card_id_by_name("Everflowing Chalice").unwrap();
        let bay = r3.card_id_by_name("Repurposing Bay").unwrap();

        assert_eq!(
            r3.profile(saga).unwrap().utility,
            urza_rules::UtilityKind::UrzasSaga
        );
        assert_eq!(r3.profile(saga).unwrap().role, R2CardRole::Land);
        assert_eq!(
            r3.profile(tezzeret).unwrap().utility,
            urza_rules::UtilityKind::TezzeretCruelCaptain
        );
        assert_eq!(r3.profile(tezzeret).unwrap().starting_loyalty, 4);
        assert!(r3.profile(top).unwrap().search_classes.saga_iii);
        assert!(
            r3.profile(chalice).unwrap().search_classes.saga_iii,
            "Everflowing Chalice is printed exactly {{0}} and is a legal Saga III target"
        );
        assert!(
            !r3.profile(bay).unwrap().search_classes.saga_iii,
            "an artifact outside printed {{0}}/{{1}} must not enter the Saga III class"
        );
    }

    #[test]
    fn r4_database_activates_monoliths_and_gadgeteer_without_mutating_r3_surface() {
        validate_r4_database().unwrap();
        let r3 = R3CardDatabase::load().unwrap();
        let r4 = R4CardDatabase::load().unwrap();
        assert_eq!(r3.supported_active_cards().len(), 32);
        assert_eq!(r4.supported_active_cards().len(), 47);

        let basalt = r4.card_id_by_name("Basalt Monolith").unwrap();
        let grim = r4.card_id_by_name("Grim Monolith").unwrap();
        let gadgeteer = r4.card_id_by_name("Forensic Gadgeteer").unwrap();
        let power_artifact = r4.card_id_by_name("Power Artifact").unwrap();
        let reality_chip = r4.card_id_by_name("The Reality Chip").unwrap();
        let ftt = r4.card_id_by_name("Fortune Teller's Talent").unwrap();
        let cage = r4.card_id_by_name("Grafdigger's Cage").unwrap();
        let station = r4.card_id_by_name("Grinding Station").unwrap();
        let golem = r4.card_id_by_name("Battered Golem").unwrap();

        let basalt_profile = r4.profile(basalt).unwrap();
        assert_eq!(
            basalt_profile.engine,
            urza_rules::EngineKind::BasaltMonolith
        );
        assert_eq!(
            basalt_profile.mana_ability,
            urza_rules::ManaAbility::TapForColorless(3)
        );
        assert_eq!(basalt_profile.native_untap_generic, Some(3));
        assert!(basalt_profile.skip_normal_untap);

        let grim_profile = r4.profile(grim).unwrap();
        assert_eq!(grim_profile.engine, urza_rules::EngineKind::GrimMonolith);
        assert_eq!(grim_profile.native_untap_generic, Some(4));
        assert!(grim_profile.skip_normal_untap);

        let gadgeteer_profile = r4.profile(gadgeteer).unwrap();
        assert_eq!(
            gadgeteer_profile.engine,
            urza_rules::EngineKind::ForensicGadgeteer
        );
        assert_eq!(gadgeteer_profile.artifact_activation_reduction, 1);

        let power_artifact_profile = r4.profile(power_artifact).unwrap();
        assert_eq!(
            power_artifact_profile.role,
            R2CardRole::EnchantmentPermanent
        );
        assert_eq!(
            power_artifact_profile.engine,
            urza_rules::EngineKind::PowerArtifact
        );
        assert_eq!(
            power_artifact_profile.aura_target,
            urza_rules::AuraTargetKind::Artifact
        );
        assert_eq!(
            power_artifact_profile.attached_artifact_activation_reduction,
            2
        );

        assert_eq!(
            r4.profile(reality_chip).unwrap().utility,
            urza_rules::UtilityKind::RealityChip
        );
        assert_eq!(
            r4.profile(ftt).unwrap().utility,
            urza_rules::UtilityKind::FortuneTellersTalent
        );
        assert_eq!(
            r4.profile(cage).unwrap().utility,
            urza_rules::UtilityKind::GrafdiggersCage
        );
        assert_eq!(
            r4.profile(station).unwrap().engine,
            urza_rules::EngineKind::GrindingStation
        );
        assert!(r4.profile(station).unwrap().top_loop_producer);
        assert_eq!(
            r4.profile(golem).unwrap().engine,
            urza_rules::EngineKind::BatteredGolem
        );
        assert!(r4.profile(golem).unwrap().top_loop_producer);
        assert!(r4.profile(golem).unwrap().skip_normal_untap);
        assert!(r4.profile(gadgeteer).unwrap().top_loop_producer);

        assert_eq!(
            r3.profile(basalt).unwrap().role,
            R2CardRole::Unsupported,
            "R3 historical surface must remain frozen"
        );
    }
}

#[cfg(test)]
mod post_r7_database_tests {
    use super::*;

    #[test]
    fn post_r7_database_extends_frozen_r4_with_ring_and_uthros() {
        validate_post_r7_database().unwrap();
        let r4 = R4CardDatabase::load().unwrap();
        let current = PostR7CardDatabase::load().unwrap();
        assert_eq!(r4.supported_active_cards().len(), 47);
        assert_eq!(current.supported_active_cards().len(), 50);
        let assistant = current.card_id_by_name("Artificer's Assistant").unwrap();
        assert_eq!(
            current.profile(assistant).unwrap().utility,
            urza_rules::UtilityKind::ArtificersAssistant
        );
        let ring = current.card_id_by_name("The One Ring").unwrap();
        assert_eq!(
            r4.profile(ring).unwrap().role,
            urza_rules::R2CardRole::Unsupported
        );
        let profile = current.profile(ring).unwrap();
        assert_eq!(profile.role, urza_rules::R2CardRole::ArtifactPermanent);
        assert_eq!(profile.utility, urza_rules::UtilityKind::TheOneRing);
        assert!(profile.is_artifact);
        assert_eq!(profile.mana_value, 4);

        let uthros = current.card_id_by_name("Uthros Research Craft").unwrap();
        assert_eq!(
            r4.profile(uthros).unwrap().role,
            urza_rules::R2CardRole::Unsupported
        );
        let uthros_profile = current.profile(uthros).unwrap();
        assert_eq!(
            uthros_profile.role,
            urza_rules::R2CardRole::ArtifactPermanent
        );
        assert_eq!(
            uthros_profile.utility,
            urza_rules::UtilityKind::UthrosResearchCraft
        );
        assert!(uthros_profile.is_artifact);
        assert_eq!(uthros_profile.mana_value, 3);
        let gadgeteer = current.card_id_by_name("Forensic Gadgeteer").unwrap();
        assert_eq!(current.printed_power(gadgeteer), Some(2));
    }
}
