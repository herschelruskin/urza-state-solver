use std::collections::BTreeMap;
use std::error::Error;
use std::fmt;

use urza_cards::{R4CardDatabase, load_r1_catalog, validate_r4_database};
use urza_core::CardDefId;
use urza_rules::{
    EngineKind, ManaAbility, R2CardRole, SpecialSearchKind, SpellEffectKind, UtilityKind,
};

use crate::{
    ExactWinRate, ExactWinRateGap, MulliganChoice, MulliganReport, MulliganStage,
    ObjectivePreference, PregameContext, SampledDecisionConfidence,
};

pub const ARCHETYPE_PHASE: &str = "R7";
pub const ARCHETYPE_LAYER_VERSION: &str = "r7_hand_interpretation_v1";
pub const INTERPRETATION_ROLE_VERSION: &str = "r7_card_roles_v1";
pub const HAND_FEATURE_SCHEMA_VERSION: &str = "r7_hand_features_v1";
pub const EVALUATED_HAND_RECORD_VERSION: &str = "r7_evaluated_hand_record_v1";
pub const INTERPRETATION_ONLY_CONTRACT: &str = "R7 consumes completed R6 evaluations for explanation/data only; R7 roles, features, clusters, labels, and distances must not participate in R6/R5 value, policy, RNG, or cache identity";

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct InterpretationRoleFlags {
    /// The printed identity has at least one land face. This deliberately says
    /// land-capable rather than assuming a modal DFC is always played as a land.
    pub land_capable: bool,
    pub artifact: bool,
    pub creature: bool,
    pub instant: bool,
    pub sorcery: bool,
    pub modal_dfc: bool,
    pub x_cost: bool,
    /// These recognized strategic roles are derived only from the already
    /// accepted R4 CardProfile. Unsupported cards are not guessed into roles.
    pub recognized_mana_source: bool,
    pub recognized_blue_mana_source: bool,
    pub recognized_multi_mana_source: bool,
    pub recognized_search_source: bool,
    pub recognized_engine_piece: bool,
    pub recognized_utility_piece: bool,
    pub recognized_targeted_effect: bool,
    pub r4_rules_supported: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CardInterpretationMetadata {
    pub card: CardDefId,
    pub deck_name: String,
    pub roles: InterpretationRoleFlags,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct InterpretationCatalog {
    pub version: &'static str,
    cards: BTreeMap<CardDefId, CardInterpretationMetadata>,
}

impl InterpretationCatalog {
    pub fn load() -> Result<Self, InterpretationError> {
        validate_r4_database().map_err(InterpretationError::catalog)?;
        let catalog = load_r1_catalog().map_err(InterpretationError::catalog)?;
        let r4 = R4CardDatabase::load().map_err(InterpretationError::catalog)?;
        let mut cards = BTreeMap::new();

        for card in catalog.cards {
            let card_id = card.card_def_id();
            let profile = r4
                .profile(card_id)
                .ok_or(InterpretationError::MissingAcceptedProfile(card_id))?;
            let (recognized_mana_source, recognized_blue_mana_source, recognized_multi_mana_source) =
                mana_roles(profile.mana_ability);
            let recognized_search_source = profile.simple_tutor.is_some()
                || profile.special_search != SpecialSearchKind::None
                || matches!(
                    profile.utility,
                    UtilityKind::UrzasSaga | UtilityKind::TezzeretCruelCaptain
                );

            let metadata = CardInterpretationMetadata {
                card: card_id,
                deck_name: card.deck_name,
                roles: InterpretationRoleFlags {
                    land_capable: card.feature_flags.is_land,
                    artifact: card.feature_flags.is_artifact,
                    creature: card.feature_flags.is_creature,
                    instant: card.feature_flags.is_instant,
                    sorcery: card.feature_flags.is_sorcery,
                    modal_dfc: card.feature_flags.is_modal_dfc,
                    x_cost: card.feature_flags.has_x_cost,
                    recognized_mana_source,
                    recognized_blue_mana_source,
                    recognized_multi_mana_source,
                    recognized_search_source,
                    recognized_engine_piece: profile.engine != EngineKind::None,
                    recognized_utility_piece: profile.utility != UtilityKind::None,
                    recognized_targeted_effect: profile.spell_effect != SpellEffectKind::None,
                    r4_rules_supported: profile.role != R2CardRole::Unsupported,
                },
            };
            cards.insert(card_id, metadata);
        }

        Ok(Self {
            version: INTERPRETATION_ROLE_VERSION,
            cards,
        })
    }

    pub fn len(&self) -> usize {
        self.cards.len()
    }

    pub fn is_empty(&self) -> bool {
        self.cards.is_empty()
    }

    pub fn card(&self, card: CardDefId) -> Option<&CardInterpretationMetadata> {
        self.cards.get(&card)
    }

    pub fn features_for_cards(
        &self,
        cards: &[CardDefId],
    ) -> Result<HandFeatureVector, InterpretationError> {
        let card_count = u16::try_from(cards.len())
            .map_err(|_| InterpretationError::TooManyCards(cards.len()))?;
        let mut features = HandFeatureVector {
            card_count,
            ..HandFeatureVector::default()
        };

        for card in cards {
            let roles = self
                .card(*card)
                .ok_or(InterpretationError::UnknownCard(*card))?
                .roles;
            features.land_capable_count += u16::from(roles.land_capable);
            features.artifact_count += u16::from(roles.artifact);
            features.creature_count += u16::from(roles.creature);
            features.instant_count += u16::from(roles.instant);
            features.sorcery_count += u16::from(roles.sorcery);
            features.modal_dfc_count += u16::from(roles.modal_dfc);
            features.x_cost_count += u16::from(roles.x_cost);
            features.recognized_mana_source_count += u16::from(roles.recognized_mana_source);
            features.recognized_blue_mana_source_count +=
                u16::from(roles.recognized_blue_mana_source);
            features.recognized_multi_mana_source_count +=
                u16::from(roles.recognized_multi_mana_source);
            features.recognized_search_source_count += u16::from(roles.recognized_search_source);
            features.recognized_engine_piece_count += u16::from(roles.recognized_engine_piece);
            features.recognized_utility_piece_count += u16::from(roles.recognized_utility_piece);
            features.recognized_targeted_effect_count +=
                u16::from(roles.recognized_targeted_effect);
            features.r4_rules_supported_count += u16::from(roles.r4_rules_supported);
        }
        features.unmodeled_by_r4_count = features
            .card_count
            .checked_sub(features.r4_rules_supported_count)
            .expect("supported cards cannot exceed total cards");
        Ok(features)
    }

    /// Convert a completed R6 report into an R7 training/analysis record.
    ///
    /// The direction is intentionally one-way: features are computed only from
    /// card identities and frozen interpretation metadata. Recommendation/value
    /// fields are copied afterward as teacher labels and cannot affect features.
    pub fn evaluated_hand_record(
        &self,
        report: &MulliganReport,
    ) -> Result<EvaluatedHandRecord, InterpretationError> {
        let current_features = self.features_for_cards(&report.current_seven)?;
        let recommended_keep_features = self.features_for_cards(&report.best_keep.kept_hand)?;

        Ok(EvaluatedHandRecord {
            record_version: EVALUATED_HAND_RECORD_VERSION,
            role_metadata_version: self.version,
            feature_schema_version: HAND_FEATURE_SCHEMA_VERSION,
            interpretation_contract: INTERPRETATION_ONLY_CONTRACT,
            source_report_version: report.report_version,
            stage: report.stage,
            mulligan_depth: report.mulligan_depth,
            pregame: report.pregame,
            policy_version: report.policy_version,
            horizon: report.horizon,
            environment_version: report.environment_version.clone(),
            current_seven: report.current_seven.clone(),
            current_features,
            recommended_kept_hand: report.best_keep.kept_hand.clone(),
            recommended_keep_features,
            recommended_action: report.selected.clone(),
            best_keep_value: report.best_keep.exact_value.clone(),
            mull_again_value: report
                .mull_again
                .as_ref()
                .map(|continuation| continuation.exact_value.clone()),
            objective_preference: report.objective_preference,
            primary_win_rate_gap: report.primary_win_rate_gap,
            sampled_decision_confidence: report.sampled_decision_confidence,
        })
    }
}

fn mana_roles(ability: ManaAbility) -> (bool, bool, bool) {
    match ability {
        ManaAbility::None => (false, false, false),
        ManaAbility::TapForBlue => (true, true, false),
        ManaAbility::TapForColorless(amount) => (true, false, amount >= 2),
        ManaAbility::TapForBlueAndDamage { .. } => (true, true, false),
        ManaAbility::TapForColorlessAndDamage { mana, .. } => (true, false, mana >= 2),
    }
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct HandFeatureVector {
    pub card_count: u16,
    pub land_capable_count: u16,
    pub artifact_count: u16,
    pub creature_count: u16,
    pub instant_count: u16,
    pub sorcery_count: u16,
    pub modal_dfc_count: u16,
    pub x_cost_count: u16,
    pub recognized_mana_source_count: u16,
    pub recognized_blue_mana_source_count: u16,
    pub recognized_multi_mana_source_count: u16,
    pub recognized_search_source_count: u16,
    pub recognized_engine_piece_count: u16,
    pub recognized_utility_piece_count: u16,
    pub recognized_targeted_effect_count: u16,
    pub r4_rules_supported_count: u16,
    pub unmodeled_by_r4_count: u16,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct EvaluatedHandRecord {
    pub record_version: &'static str,
    pub role_metadata_version: &'static str,
    pub feature_schema_version: &'static str,
    pub interpretation_contract: &'static str,
    pub source_report_version: &'static str,
    pub stage: MulliganStage,
    pub mulligan_depth: u8,
    pub pregame: PregameContext,
    pub policy_version: &'static str,
    pub horizon: u8,
    pub environment_version: String,
    pub current_seven: Vec<CardDefId>,
    pub current_features: HandFeatureVector,
    pub recommended_kept_hand: Vec<CardDefId>,
    pub recommended_keep_features: HandFeatureVector,
    pub recommended_action: MulliganChoice,
    pub best_keep_value: ExactWinRate,
    pub mull_again_value: Option<ExactWinRate>,
    pub objective_preference: ObjectivePreference,
    pub primary_win_rate_gap: Option<ExactWinRateGap>,
    pub sampled_decision_confidence: SampledDecisionConfidence,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum InterpretationError {
    Catalog(String),
    MissingAcceptedProfile(CardDefId),
    UnknownCard(CardDefId),
    TooManyCards(usize),
}

impl InterpretationError {
    fn catalog(error: impl fmt::Display) -> Self {
        Self::Catalog(error.to_string())
    }
}

impl fmt::Display for InterpretationError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Catalog(error) => write!(formatter, "interpretation catalog error: {error}"),
            Self::MissingAcceptedProfile(card) => {
                write!(formatter, "accepted R4 profile missing for card {}", card.0)
            }
            Self::UnknownCard(card) => write!(formatter, "unknown interpretation card {}", card.0),
            Self::TooManyCards(count) => write!(formatter, "hand feature input too large: {count}"),
        }
    }
}

impl Error for InterpretationError {}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn interpretation_metadata_is_total_and_versioned_over_the_audited_catalog() {
        let catalog = InterpretationCatalog::load().unwrap();
        assert_eq!(catalog.version, INTERPRETATION_ROLE_VERSION);
        assert_eq!(catalog.len(), 95);
        assert!(!catalog.is_empty());
    }

    #[test]
    fn interpretation_roles_are_derived_from_frozen_metadata_without_guessing_unsupported_rules() {
        let interpretation = InterpretationCatalog::load().unwrap();
        let cards = R4CardDatabase::load().unwrap();

        let island = interpretation
            .card(cards.card_id_by_name("Island").unwrap())
            .unwrap();
        assert!(island.roles.land_capable);
        assert!(island.roles.recognized_mana_source);
        assert!(island.roles.recognized_blue_mana_source);

        let sol_ring = interpretation
            .card(cards.card_id_by_name("Sol Ring").unwrap())
            .unwrap();
        assert!(sol_ring.roles.artifact);
        assert!(sol_ring.roles.recognized_multi_mana_source);

        let spellseeker = interpretation
            .card(cards.card_id_by_name("Spellseeker").unwrap())
            .unwrap();
        assert!(spellseeker.roles.recognized_search_source);

        let basalt = interpretation
            .card(cards.card_id_by_name("Basalt Monolith").unwrap())
            .unwrap();
        assert!(basalt.roles.recognized_engine_piece);
        assert!(basalt.roles.recognized_multi_mana_source);

        let pact = interpretation
            .card(cards.card_id_by_name("Pact of Negation").unwrap())
            .unwrap();
        assert!(pact.roles.instant);
        assert!(!pact.roles.r4_rules_supported);
        assert!(!pact.roles.recognized_engine_piece);
        assert!(!pact.roles.recognized_search_source);
    }

    #[test]
    fn hand_features_depend_only_on_cards_not_teacher_values_or_recommendations() {
        let interpretation = InterpretationCatalog::load().unwrap();
        let cards = R4CardDatabase::load().unwrap();
        let hand = [
            cards.card_id_by_name("Island").unwrap(),
            cards.card_id_by_name("Ancient Tomb").unwrap(),
            cards.card_id_by_name("Sol Ring").unwrap(),
            cards.card_id_by_name("Spellseeker").unwrap(),
            cards.card_id_by_name("Basalt Monolith").unwrap(),
            cards.card_id_by_name("Pact of Negation").unwrap(),
            cards.card_id_by_name("Sea Gate Restoration").unwrap(),
        ];

        let first = interpretation.features_for_cards(&hand).unwrap();
        let second = interpretation.features_for_cards(&hand).unwrap();
        assert_eq!(first, second);
        assert_eq!(first.card_count, 7);
        assert_eq!(first.land_capable_count, 3);
        assert_eq!(first.recognized_search_source_count, 1);
        assert!(first.recognized_multi_mana_source_count >= 3);
        assert!(first.unmodeled_by_r4_count >= 1);
        assert_eq!(ARCHETYPE_PHASE, "R7");
        assert_eq!(ARCHETYPE_LAYER_VERSION, "r7_hand_interpretation_v1");
    }
}
