from pathlib import Path


def replace_exact(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one match in {path}, found {count}: {old[:80]!r}")
    file.write_text(text.replace(old, new, 1))


RULES = "rust/crates/urza-rules/src/lib.rs"
CARDS = "rust/crates/urza-cards/src/lib.rs"
REGISTRY = "rust/data/goldfish_model_gate.v1.tsv"

replace_exact(
    RULES,
    'pub const POST_R7_RULES_VERSION: &str = "post_r7_card_advantage_v4_assistant_scry_order";',
    'pub const POST_R7_RULES_VERSION: &str = "post_r7_modeling_completeness_v1_fast_mana";',
)

replace_exact(
    RULES,
    """pub enum ManaAbility {
    #[default]
    None,
    TapForBlue,
    TapForColorless(u16),
    TapForBlueAndDamage {
        damage: u16,
    },
    TapForColorlessAndDamage {
        mana: u16,
        damage: u16,
    },
}""",
    """pub enum ManaAbility {
    #[default]
    None,
    TapForBlue,
    TapForColorless(u16),
    TapForBlueAndDamage {
        damage: u16,
    },
    TapForColorlessAndDamage {
        mana: u16,
        damage: u16,
    },
    /// In the pinned mono-blue goldfish model, an unrestricted any-color mana
    /// choice projects losslessly to blue. The completeness fixture audits all
    /// active card/face mana costs and fails if a non-blue colored symbol enters.
    TapSacrificeForBlue,
    /// Mox Opal's any-color choice under metalcraft, projected to blue under
    /// the same pinned-deck invariant.
    MetalcraftTapForBlue,
}""",
)

replace_exact(
    RULES,
    """    let mut mana = state.mana;
    let mut life = state.life;
    match ability {
        ManaAbility::None => unreachable!(\"checked above\"),
        ManaAbility::TapForBlue => add_blue(&mut mana, 1)?,
        ManaAbility::TapForColorless(amount) => add_colorless(&mut mana, amount)?,
        ManaAbility::TapForBlueAndDamage { damage } => {
            add_blue(&mut mana, 1)?;
            life = life.saturating_sub(damage);
        }
        ManaAbility::TapForColorlessAndDamage {
            mana: amount,
            damage,
        } => {
            add_colorless(&mut mana, amount)?;
            life = life.saturating_sub(damage);
        }
    }

    set_tapped(state, source)?;
    state.mana = mana;
    state.life = life;
    Ok(())""",
    """    let mut mana = state.mana;
    let mut life = state.life;
    let mut sacrifice_source = false;
    match ability {
        ManaAbility::None => unreachable!(\"checked above\"),
        ManaAbility::TapForBlue => add_blue(&mut mana, 1)?,
        ManaAbility::TapForColorless(amount) => add_colorless(&mut mana, amount)?,
        ManaAbility::TapForBlueAndDamage { damage } => {
            add_blue(&mut mana, 1)?;
            life = life.saturating_sub(damage);
        }
        ManaAbility::TapForColorlessAndDamage {
            mana: amount,
            damage,
        } => {
            add_colorless(&mut mana, amount)?;
            life = life.saturating_sub(damage);
        }
        ManaAbility::TapSacrificeForBlue => {
            add_blue(&mut mana, 1)?;
            sacrifice_source = true;
        }
        ManaAbility::MetalcraftTapForBlue => {
            let artifact_count = state
                .battlefield
                .permanents()
                .iter()
                .filter(|candidate| {
                    cards
                        .profile(candidate.card)
                        .is_some_and(|candidate_profile| candidate_profile.is_artifact)
                })
                .count();
            if artifact_count < 3 {
                return Err(RuleError::NotManaSource(source));
            }
            add_blue(&mut mana, 1)?;
        }
    }

    if sacrifice_source {
        sacrifice_artifact(state, source)?;
    } else {
        set_tapped(state, source)?;
    }
    state.mana = mana;
    state.life = life;
    Ok(())""",
)

replace_exact(
    CARDS,
    "pub const POST_R7_ACCEPTED_ACTIVE_IDENTITY_COUNT: usize = 50;",
    "pub const POST_R7_ACCEPTED_ACTIVE_IDENTITY_COUNT: usize = 52;",
)
replace_exact(
    CARDS,
    'pub const POST_R7_CARD_DATABASE_VERSION: &str = "post_r7_card_advantage_v3_assistant_scry_order";',
    'pub const POST_R7_CARD_DATABASE_VERSION: &str = "post_r7_modeling_completeness_v1_fast_mana";',
)

replace_exact(
    CARDS,
    """        assistant_profile.role = urza_rules::R2CardRole::CreaturePermanent;
        assistant_profile.utility = urza_rules::UtilityKind::ArtificersAssistant;
        assistant_profile.is_creature = true;

        let catalog = load_r1_catalog()?;""",
    """        assistant_profile.role = urza_rules::R2CardRole::CreaturePermanent;
        assistant_profile.utility = urza_rules::UtilityKind::ArtificersAssistant;
        assistant_profile.is_creature = true;

        let lotus = card_id_by_name_from_r1(\"Lotus Petal\")?;
        let lotus_profile = cards.get_mut(&lotus).ok_or_else(|| {
            CatalogError::Invariant(\"missing post-R7 Lotus Petal profile\".to_owned())
        })?;
        lotus_profile.role = urza_rules::R2CardRole::ArtifactPermanent;
        lotus_profile.mana_cost = Some(urza_rules::ManaCost::default());
        lotus_profile.mana_ability = urza_rules::ManaAbility::TapSacrificeForBlue;
        lotus_profile.is_artifact = true;

        let mox_opal = card_id_by_name_from_r1(\"Mox Opal\")?;
        let mox_opal_profile = cards.get_mut(&mox_opal).ok_or_else(|| {
            CatalogError::Invariant(\"missing post-R7 Mox Opal profile\".to_owned())
        })?;
        mox_opal_profile.role = urza_rules::R2CardRole::ArtifactPermanent;
        mox_opal_profile.mana_cost = Some(urza_rules::ManaCost::default());
        mox_opal_profile.mana_ability = urza_rules::ManaAbility::MetalcraftTapForBlue;
        mox_opal_profile.is_artifact = true;

        let catalog = load_r1_catalog()?;""",
)

replace_exact(
    CARDS,
    """    let ring = card_id_by_name_from_r1(\"The One Ring\")?;
    let uthros = card_id_by_name_from_r1(\"Uthros Research Craft\")?;
    let assistant = card_id_by_name_from_r1(\"Artificer's Assistant\")?;
    if added != BTreeSet::from([ring, uthros, assistant]) {
        return Err(CatalogError::Invariant(format!(
            \"post-R7 current surface must add exactly Ring, Uthros, and Artificer's Assistant, got {added:?}\"
        )));
    }""",
    """    let ring = card_id_by_name_from_r1(\"The One Ring\")?;
    let uthros = card_id_by_name_from_r1(\"Uthros Research Craft\")?;
    let assistant = card_id_by_name_from_r1(\"Artificer's Assistant\")?;
    let lotus = card_id_by_name_from_r1(\"Lotus Petal\")?;
    let mox_opal = card_id_by_name_from_r1(\"Mox Opal\")?;
    if added != BTreeSet::from([ring, uthros, assistant, lotus, mox_opal]) {
        return Err(CatalogError::Invariant(format!(
            \"post-R7 current surface must add exactly Ring, Uthros, Artificer's Assistant, Lotus Petal, and Mox Opal, got {added:?}\"
        )));
    }""",
)

replace_exact(
    REGISTRY,
    "Lotus Petal\tIMPLEMENTATION_REQUIRED\tCurrent post-R7 database does not expose a playable rules role for this active deck identity; goldfish-relevant Oracle clauses and legal own-side actions must be classified and implemented or explicitly exempted.",
    "Lotus Petal\tCOMPLETE\tGoldfish-complete: zero-mana artifact cast and {T}, sacrifice mana ability are executable; unrestricted any-color production is projected to blue only under a fixture that audits the pinned deck for non-blue colored costs.",
)
replace_exact(
    REGISTRY,
    "Mox Opal\tIMPLEMENTATION_REQUIRED\tCurrent post-R7 database does not expose a playable rules role for this active deck identity; goldfish-relevant Oracle clauses and legal own-side actions must be classified and implemented or explicitly exempted.",
    "Mox Opal\tCOMPLETE\tGoldfish-complete: zero-mana legendary artifact cast, public three-artifact metalcraft legality, and tap-for-mana are executable; any-color production uses the audited mono-blue projection.",
)
