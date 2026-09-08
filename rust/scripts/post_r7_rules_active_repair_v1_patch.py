from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_once(path: str, old: str, new: str) -> None:
    file = ROOT / path
    text = file.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one match in {path}, got {count}: {old[:100]!r}")
    file.write_text(text.replace(old, new, 1))


def write(path: str, content: str) -> None:
    file = ROOT / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(content)


# Version the post-R7 behavior change explicitly.
replace_once(
    "rust/crates/urza-rules/src/lib.rs",
    'pub const POST_R7_RULES_VERSION: &str = "post_r7_modeling_completeness_v1_fast_mana";',
    'pub const POST_R7_RULES_VERSION: &str = "post_r7_modeling_completeness_v2_rules_active_repair";',
)
replace_once(
    "rust/crates/urza-cards/src/lib.rs",
    'pub const POST_R7_CARD_DATABASE_VERSION: &str = "post_r7_modeling_completeness_v1_fast_mana";',
    'pub const POST_R7_CARD_DATABASE_VERSION: &str = "post_r7_modeling_completeness_v2_rules_active_repair";',
)
replace_once(
    "rust/crates/urza-policy-bridge/src/lib.rs",
    'pub const CANDIDATE_BRIDGE_VERSION: &str = "post_r7_public_candidate_bridge_v4_trigger_order";',
    'pub const CANDIDATE_BRIDGE_VERSION: &str = "post_r7_public_candidate_bridge_v5_modeling_repair";',
)

# Floodcaller pumps are end-of-turn continuous state, not permanent +1/+1 counters.
replace_once(
    "rust/crates/urza-core/src/state.rs",
    "pub struct CounterState {\n    pub plus_one_plus_one: u16,\n    pub charge: u16,",
    "pub struct CounterState {\n    pub plus_one_plus_one: u16,\n    #[serde(default)]\n    pub temporary_power_boost: u16,\n    pub charge: u16,",
)

# Artificer's Assistant is a Bird and therefore participates in Floodcaller.
replace_once(
    "rust/crates/urza-cards/src/lib.rs",
    "        assistant_profile.role = urza_rules::R2CardRole::CreaturePermanent;\n        assistant_profile.utility = urza_rules::UtilityKind::ArtificersAssistant;\n        assistant_profile.is_creature = true;",
    "        assistant_profile.role = urza_rules::R2CardRole::CreaturePermanent;\n        assistant_profile.utility = urza_rules::UtilityKind::ArtificersAssistant;\n        assistant_profile.floodcaller_untap_eligible = true;\n        assistant_profile.is_creature = true;",
)

# Valley Floodcaller: its own Flash plus noncreature-spells-as-flash permission.
replace_once(
    "rust/crates/urza-rules/src/lib.rs",
    "fn ensure_sorcery_window(state: &TrueState) -> Result<(), RuleError> {\n    ensure_priority(state)?;\n    ensure_no_pending_decision(state)?;\n    if state.phase != Phase::PrecombatMain || !state.stack.is_empty() {\n        return Err(RuleError::IllegalTiming);\n    }\n    Ok(())\n}\n",
    "fn ensure_sorcery_window(state: &TrueState) -> Result<(), RuleError> {\n    ensure_priority(state)?;\n    ensure_no_pending_decision(state)?;\n    if state.phase != Phase::PrecombatMain || !state.stack.is_empty() {\n        return Err(RuleError::IllegalTiming);\n    }\n    Ok(())\n}\n\nfn has_valley_floodcaller<D: CardDatabase>(state: &TrueState, cards: &D) -> bool {\n    state.battlefield.permanents().iter().any(|permanent| {\n        cards\n            .profile(permanent.card)\n            .is_some_and(|profile| profile.engine == EngineKind::ValleyFloodcaller)\n    })\n}\n\nfn ensure_spell_cast_window<D: CardDatabase>(\n    state: &TrueState,\n    cards: &D,\n    profile: CardProfile,\n) -> Result<(), RuleError> {\n    let intrinsic_flash = profile.engine == EngineKind::ValleyFloodcaller\n        || profile.utility == UtilityKind::SewerVeillanceCam;\n    let floodcaller_permission = !profile.is_creature && has_valley_floodcaller(state, cards);\n    if intrinsic_flash || floodcaller_permission {\n        ensure_priority(state)?;\n        ensure_no_pending_decision(state)\n    } else {\n        ensure_sorcery_window(state)\n    }\n}\n",
)

replace_once(
    "rust/crates/urza-rules/src/lib.rs",
    "                if kind.instant_speed() {\n                    ensure_priority(state)?;\n                    ensure_no_pending_decision(state)?;\n                } else {\n                    ensure_sorcery_window(state)?;\n                }\n            }\n            SpecialSearchKind::TransmuteArtifact => ensure_sorcery_window(state)?,",
    "                if kind.instant_speed() {\n                    ensure_priority(state)?;\n                    ensure_no_pending_decision(state)?;\n                } else {\n                    ensure_spell_cast_window(state, cards, profile)?;\n                }\n            }\n            SpecialSearchKind::TransmuteArtifact => ensure_spell_cast_window(state, cards, profile)?,",
)
replace_once(
    "rust/crates/urza-rules/src/lib.rs",
    "        R2CardRole::ArtifactPermanent\n        | R2CardRole::CreaturePermanent\n        | R2CardRole::PlaneswalkerPermanent\n        | R2CardRole::UrzaCommander => ensure_sorcery_window(state)?,\n        R2CardRole::EnchantmentPermanent => {\n            if profile.aura_target != AuraTargetKind::None {\n                return Err(RuleError::UnsupportedCardMechanic(card));\n            }\n            ensure_sorcery_window(state)?;\n        }",
    "        R2CardRole::ArtifactPermanent\n        | R2CardRole::CreaturePermanent\n        | R2CardRole::PlaneswalkerPermanent\n        | R2CardRole::UrzaCommander => ensure_spell_cast_window(state, cards, profile)?,\n        R2CardRole::EnchantmentPermanent => {\n            if profile.aura_target != AuraTargetKind::None {\n                return Err(RuleError::UnsupportedCardMechanic(card));\n            }\n            ensure_spell_cast_window(state, cards, profile)?;\n        }",
)
replace_once(
    "rust/crates/urza-rules/src/lib.rs",
    "fn cast_aura_from_hand<D: CardDatabase>(\n    state: &mut TrueState,\n    cards: &D,\n    card: CardDefId,\n    target: CanonicalObjectId,\n    payment: ManaPayment,\n) -> Result<(), RuleError> {\n    ensure_sorcery_window(state)?;\n    let profile = card_profile(cards, card)?;",
    "fn cast_aura_from_hand<D: CardDatabase>(\n    state: &mut TrueState,\n    cards: &D,\n    card: CardDefId,\n    target: CanonicalObjectId,\n    payment: ManaPayment,\n) -> Result<(), RuleError> {\n    let profile = card_profile(cards, card)?;\n    ensure_spell_cast_window(state, cards, profile)?;",
)
replace_once(
    "rust/crates/urza-rules/src/lib.rs",
    "fn cast_reshape<D: CardDatabase>(\n    state: &mut TrueState,\n    cards: &D,\n    card: CardDefId,\n    x_value: u16,\n    sacrifice: ObjectId,\n    payment: ManaPayment,\n) -> Result<(), RuleError> {\n    ensure_sorcery_window(state)?;\n    let profile = card_profile(cards, card)?;",
    "fn cast_reshape<D: CardDatabase>(\n    state: &mut TrueState,\n    cards: &D,\n    card: CardDefId,\n    x_value: u16,\n    sacrifice: ObjectId,\n    payment: ManaPayment,\n) -> Result<(), RuleError> {\n    let profile = card_profile(cards, card)?;\n    ensure_spell_cast_window(state, cards, profile)?;",
)

# Library-top casting gets the same Floodcaller permission (the real ruling applies in any zone).
replace_once(
    "rust/crates/urza-rules/src/lib.rs",
    "        R2CardRole::ArtifactPermanent\n        | R2CardRole::CreaturePermanent\n        | R2CardRole::EnchantmentPermanent\n        | R2CardRole::PlaneswalkerPermanent => ensure_sorcery_window(state)?,\n        R2CardRole::SearchSpell => {\n            let instant = profile\n                .simple_tutor\n                .is_some_and(SimpleTutorKind::instant_speed)\n                || profile.special_search == SpecialSearchKind::Whir;\n            if instant {\n                ensure_priority(state)?;\n                ensure_no_pending_decision(state)?;\n            } else {\n                ensure_sorcery_window(state)?;\n            }",
    "        R2CardRole::ArtifactPermanent\n        | R2CardRole::CreaturePermanent\n        | R2CardRole::EnchantmentPermanent\n        | R2CardRole::PlaneswalkerPermanent => ensure_spell_cast_window(state, cards, profile)?,\n        R2CardRole::SearchSpell => {\n            let instant = profile\n                .simple_tutor\n                .is_some_and(SimpleTutorKind::instant_speed)\n                || profile.special_search == SpecialSearchKind::Whir;\n            if instant {\n                ensure_priority(state)?;\n                ensure_no_pending_decision(state)?;\n            } else {\n                ensure_spell_cast_window(state, cards, profile)?;\n            }",
)

# Urza free-cast permissions are also casts from a non-hand zone and obey Floodcaller.
replace_once(
    "rust/crates/urza-rules/src/lib.rs",
    "    match profile.role {\n        R2CardRole::ArtifactPermanent\n        | R2CardRole::CreaturePermanent\n        | R2CardRole::PlaneswalkerPermanent => ensure_sorcery_window(state)?,\n        R2CardRole::EnchantmentPermanent => {\n            if profile.aura_target != AuraTargetKind::None {\n                return Err(RuleError::UnsupportedCardMechanic(permission.card));\n            }\n            ensure_sorcery_window(state)?;\n        }",
    "    match profile.role {\n        R2CardRole::ArtifactPermanent\n        | R2CardRole::CreaturePermanent\n        | R2CardRole::PlaneswalkerPermanent => ensure_spell_cast_window(state, cards, profile)?,\n        R2CardRole::EnchantmentPermanent => {\n            if profile.aura_target != AuraTargetKind::None {\n                return Err(RuleError::UnsupportedCardMechanic(permission.card));\n            }\n            ensure_spell_cast_window(state, cards, profile)?;\n        }",
)
replace_once(
    "rust/crates/urza-rules/src/lib.rs",
    "            if instant {\n                ensure_priority(state)?;\n                ensure_no_pending_decision(state)?;\n            } else {\n                ensure_sorcery_window(state)?;\n            }\n            if profile.special_search == SpecialSearchKind::Reshape {",
    "            if instant {\n                ensure_priority(state)?;\n                ensure_no_pending_decision(state)?;\n            } else {\n                ensure_spell_cast_window(state, cards, profile)?;\n            }\n            if profile.special_search == SpecialSearchKind::Reshape {",
)
replace_once(
    "rust/crates/urza-rules/src/lib.rs",
    "    if profile.role != R2CardRole::EnchantmentPermanent\n        || profile.aura_target == AuraTargetKind::None\n    {\n        return Err(RuleError::UnsupportedCardMechanic(permission.card));\n    }\n    ensure_sorcery_window(state)?;",
    "    if profile.role != R2CardRole::EnchantmentPermanent\n        || profile.aura_target == AuraTargetKind::None\n    {\n        return Err(RuleError::UnsupportedCardMechanic(permission.card));\n    }\n    ensure_spell_cast_window(state, cards, profile)?;",
)

# Floodcaller trigger now applies the +1/+1-until-EOT as well as the untap.
replace_once(
    "rust/crates/urza-rules/src/lib.rs",
    "        if cards\n            .profile(permanent.card)\n            .is_some_and(|profile| profile.floodcaller_untap_eligible)\n        {\n            permanent.tapped = false;\n        }",
    "        if cards\n            .profile(permanent.card)\n            .is_some_and(|profile| profile.floodcaller_untap_eligible)\n        {\n            permanent.tapped = false;\n            permanent.counters.temporary_power_boost = permanent\n                .counters\n                .temporary_power_boost\n                .checked_add(1)\n                .ok_or(RuleError::ArithmeticOverflow)?;\n        }",
)
replace_once(
    "rust/crates/urza-rules/src/lib.rs",
    "    for permanent in &mut permanents {\n        if permanent.granted_ability == Some(urza_core::GrantedAbility::KnackBounceUntilEndOfTurn) {\n            permanent.granted_ability = None;\n        }\n    }",
    "    for permanent in &mut permanents {\n        if permanent.granted_ability == Some(urza_core::GrantedAbility::KnackBounceUntilEndOfTurn) {\n            permanent.granted_ability = None;\n        }\n        permanent.counters.temporary_power_boost = 0;\n    }",
)

# Creature power observes both Chrome Dome's static +1/+0 and Floodcaller's temporary pump.
replace_once(
    "rust/crates/urza-rules/src/lib.rs",
    "    let counters = i16::try_from(permanent.counters.plus_one_plus_one)\n        .map_err(|_| RuleError::ArithmeticOverflow)?;\n    base.checked_add(counters)\n        .ok_or(RuleError::ArithmeticOverflow)\n}",
    "    let counters = i16::try_from(permanent.counters.plus_one_plus_one)\n        .map_err(|_| RuleError::ArithmeticOverflow)?;\n    let temporary = i16::try_from(permanent.counters.temporary_power_boost)\n        .map_err(|_| RuleError::ArithmeticOverflow)?;\n    let target_profile = card_profile(cards, permanent.card)?;\n    let chrome_boost = if target_profile.is_artifact && target_profile.is_creature {\n        state\n            .battlefield\n            .permanents()\n            .iter()\n            .filter(|candidate| {\n                candidate.object_id != permanent.object_id\n                    && cards\n                        .profile(candidate.card)\n                        .is_some_and(|profile| profile.engine == EngineKind::ChromeDome)\n            })\n            .count()\n    } else {\n        0\n    };\n    let chrome_boost = i16::try_from(chrome_boost).map_err(|_| RuleError::ArithmeticOverflow)?;\n    base.checked_add(counters)\n        .and_then(|power| power.checked_add(temporary))\n        .and_then(|power| power.checked_add(chrome_boost))\n        .ok_or(RuleError::ArithmeticOverflow)\n}",
)

# Chrome Dome's copy token explicitly gains haste; summoning-sickness is the execution abstraction.
replace_once(
    "rust/crates/urza-rules/src/lib.rs",
    "            tapped: false,\n            summoning_sick: profile.is_creature,\n            token: true,",
    "            tapped: false,\n            // Chrome Dome explicitly gives the copy haste. Combat is outside the\n            // goldfish model; clearing summoning sickness is the exact execution\n            // consequence needed for tap abilities.\n            summoning_sick: false,\n            token: true,",
)

# Attached permanents do not make sacrifice/bounce illegal. The common lifecycle already knows
# how to detach Reality Chip and put ordinary attached Auras into the graveyard.
replace_once(
    "rust/crates/urza-rules/src/lib.rs",
    "    if state\n        .battlefield\n        .permanents()\n        .iter()\n        .any(|candidate| candidate.attached_to == Some(object))\n    {\n        return Err(RuleError::AttachedSacrificeDeferred(object));\n    }\n    Ok(profile)",
    "    Ok(profile)",
)
replace_once(
    "rust/crates/urza-rules/src/lib.rs",
    "    if state\n        .battlefield\n        .permanents()\n        .iter()\n        .any(|permanent| permanent.attached_to == Some(target_id))\n    {\n        return Err(RuleError::AttachedBounceDeferred(target_id));\n    }\n    set_tapped(state, source)?;",
    "    set_tapped(state, source)?;",
)
replace_once(
    "rust/crates/urza-rules/src/lib.rs",
    "    let removed = permanents.remove(index);\n    state.battlefield = BattlefieldZone::new(permanents);\n    state.delayed_events.retain(|event| {\n        !matches!(event, DelayedEvent::ChromeCopySacrifice { object, .. } if *object == object_id)\n    });\n    if !removed.token {\n        state.hand.insert(removed.card);\n    }",
    "    let removed = permanents.remove(index);\n    for candidate in &mut permanents {\n        if candidate.attached_to == Some(object_id)\n            && candidate.mode == PermanentMode::RealityChipAttached\n        {\n            candidate.mode = PermanentMode::RealityChipCreature;\n            candidate.attached_to = None;\n        }\n    }\n    let mut attached_non_token_cards = Vec::new();\n    permanents.retain(|candidate| {\n        if candidate.attached_to == Some(object_id) {\n            if !candidate.token {\n                attached_non_token_cards.push(candidate.card);\n            }\n            false\n        } else {\n            true\n        }\n    });\n    state.battlefield = BattlefieldZone::new(permanents);\n    for card in attached_non_token_cards {\n        state.graveyard.insert(card);\n    }\n    state.delayed_events.retain(|event| {\n        !matches!(event, DelayedEvent::ChromeCopySacrifice { object, .. } if *object == object_id)\n    });\n    if !removed.token {\n        state.hand.insert(removed.card);\n    }",
)

# Gadgeteer reduces Clue's artifact activated ability as well; legal-action filtering keeps the
# bridge public and exact without duplicating the reduction formula there.
replace_once(
    "rust/crates/urza-rules/src/lib.rs",
    "    let cost = ManaCost {\n        generic: 2,\n        ..ManaCost::default()\n    };\n    validate_payment(state.mana, payment, cost)?;\n\n    // Mana payment and sacrifice are activation costs.",
    "    let cost = reduced_artifact_activation_cost(state, cards, source, 2)?;\n    validate_payment(state.mana, payment, cost)?;\n\n    // Mana payment and sacrifice are activation costs.",
)
replace_once(
    "rust/crates/urza-policy-bridge/src/lib.rs",
    "        if cards.clue_token_card() == Some(class.card) {\n            for payment in enumerate_payments(\n                information.mana,\n                ManaCost {\n                    generic: 2,\n                    ..ManaCost::default()\n                },\n            ) {\n                actions.push(Action::ActivateClueDraw {\n                    source: representative,\n                    payment,\n                });\n            }\n        }",
    "        if cards.clue_token_card() == Some(class.card) {\n            for payment in &all_payments {\n                actions.push(Action::ActivateClueDraw {\n                    source: representative,\n                    payment: *payment,\n                });\n            }\n        }",
)

# Tighten the earlier Gadgeteer fixture to the newly audited cross-card cost.
replace_once(
    "rust/crates/urza-cards/tests/post_r7_modeling_completeness_forensic_gadgeteer.rs",
    "    state.mana = ManaPool {\n        colorless: 2,\n        ..ManaPool::default()\n    };\n    apply_action(\n        &mut state,\n        &cards,\n        Action::ActivateClueDraw {\n            source: clue,\n            payment: ManaPayment {\n                colorless: 2,\n                ..ManaPayment::default()\n            },\n        },\n    )",
    "    state.mana = ManaPool {\n        colorless: 1,\n        ..ManaPool::default()\n    };\n    apply_action(\n        &mut state,\n        &cards,\n        Action::ActivateClueDraw {\n            source: clue,\n            payment: ManaPayment {\n                colorless: 1,\n                ..ManaPayment::default()\n            },\n        },\n    )",
)

# Promote only identities whose full currently-relevant surface is closed in this tranche.
registry = ROOT / "rust/data/goldfish_model_gate.v1.tsv"
lines = registry.read_text().splitlines()
rationales = {
    "Artificer's Assistant": "Goldfish-complete: normal creature casting and exact historic-spell scry 1 are executable, historic classification comes from pinned public type-line metadata, simultaneous controlled triggers expose public TriggerOrder, and the Bird subtype now participates in Valley Floodcaller's pump/untap. Flying is combat-only and therefore explicitly irrelevant to this no-combat goldfish environment.",
    "Chrome Dome": "Goldfish-complete: normal artifact-creature casting, the other-artifact-creature +1/+0 static effect, five-mana copy activation, copied-token haste, artifact-entry interactions, and next-end-step sacrifice are executable. Dedicated repair fixtures prove the static power through Uthros and prove a copied creature may immediately use tap abilities via the haste abstraction.",
    "Valley Floodcaller": "Goldfish-complete: normal creature casting, intrinsic flash, casting noncreature spells as though they had flash from supported zones, and the noncreature-cast trigger are executable. The trigger untaps and gives +1/+1 until end of turn to the active deck's Bird/Otter permanents, including Artificer's Assistant and Floodcaller itself, with temporary power cleared at end of turn.",
}
out = [lines[0]]
seen = set()
for line in lines[1:]:
    name, disposition, rationale = line.split("\t", 2)
    if name in rationales:
        if disposition != "AUDIT_REQUIRED":
            raise SystemExit(f"unexpected pre-repair disposition for {name}: {disposition}")
        disposition = "COMPLETE"
        rationale = rationales[name]
        seen.add(name)
    out.append("\t".join((name, disposition, rationale)))
if seen != set(rationales):
    raise SystemExit(f"registry promotion mismatch: {seen!r}")
registry.write_text("\n".join(out) + "\n")

replace_once(
    "rust/crates/urza-mulligan/src/bin/post-r7-modeling-completeness-gate.rs",
    "        assert_eq!(audit.count(Disposition::AuditRequired), 41);\n        assert_eq!(audit.count(Disposition::ImplementationRequired), 40);\n        assert_eq!(audit.count(Disposition::EnvironmentSplitRequired), 3);\n        assert_eq!(audit.count(Disposition::Complete), 11);\n        assert_eq!(audit.resolved(), 11);\n        assert_eq!(audit.unresolved(), 84);",
    "        assert_eq!(audit.count(Disposition::AuditRequired), 38);\n        assert_eq!(audit.count(Disposition::ImplementationRequired), 40);\n        assert_eq!(audit.count(Disposition::EnvironmentSplitRequired), 3);\n        assert_eq!(audit.count(Disposition::Complete), 14);\n        assert_eq!(audit.resolved(), 14);\n        assert_eq!(audit.unresolved(), 81);",
)

write(
    "rust/crates/urza-cards/tests/post_r7_modeling_completeness_rules_active_repair_v1.rs",
    r'''use urza_cards::CurrentCardDatabase;
use urza_core::{
    BattlefieldZone, CardZone, CounterState, DelayedEvent, ManaPool, ObjectId, PendingDecision,
    PermanentMode, PermanentState, Phase, StackObject, TrueLibrary, TrueState, Window,
};
use urza_info::observe;
use urza_rules::{
    ABILITY_ARTIFICERS_ASSISTANT_SCRY, ABILITY_FLOODCALLER_UNTAP, Action, CardDatabase,
    EngineKind, ManaPayment, R2CardRole, UtilityKind, advance_phase, apply_action,
};

fn card(cards: &CurrentCardDatabase, name: &str) -> urza_core::CardDefId {
    cards.card_id_by_name(name).unwrap()
}

fn permanent(cards: &CurrentCardDatabase, object: u32, name: &str, tapped: bool) -> PermanentState {
    let id = card(cards, name);
    let profile = cards.profile(id).unwrap();
    PermanentState {
        object_id: ObjectId(object),
        card: id,
        face: profile.battlefield_face,
        tapped,
        summoning_sick: false,
        token: false,
        counters: CounterState::default(),
        mode: match profile.utility {
            UtilityKind::UthrosResearchCraft => PermanentMode::UthrosStation,
            _ => PermanentMode::Normal,
        },
        attached_to: None,
        granted_ability: None,
    }
}

fn state_with(
    cards: &CurrentCardDatabase,
    permanents: Vec<PermanentState>,
    hand: &[&str],
    library: &[&str],
    mana: ManaPool,
    phase: Phase,
) -> TrueState {
    let state = TrueState {
        turn: 1,
        phase,
        window: Window::Priority,
        hand: CardZone::new(hand.iter().map(|name| card(cards, name)).collect()),
        library: TrueLibrary::unknown(library.iter().map(|name| card(cards, name)).collect()),
        battlefield: BattlefieldZone::new(permanents),
        mana,
        ..TrueState::default()
    };
    state.validate().unwrap();
    state
}

fn payment_for(cards: &CurrentCardDatabase, name: &str) -> ManaPayment {
    let cost = cards.profile(card(cards, name)).unwrap().mana_cost.unwrap();
    ManaPayment {
        white: cost.white,
        blue: cost.blue,
        black: cost.black,
        red: cost.red,
        green: cost.green,
        colorless: cost.colorless + cost.generic,
    }
}

fn pool_for(payment: ManaPayment) -> ManaPool {
    ManaPool {
        white: payment.white,
        blue: payment.blue,
        black: payment.black,
        red: payment.red,
        green: payment.green,
        colorless: payment.colorless,
    }
}

fn canonical_for(state: &TrueState, wanted: ObjectId) -> urza_info::CanonicalObjectId {
    observe(state)
        .unwrap()
        .battlefield
        .into_iter()
        .find(|permanent| {
            urza_info::resolve_canonical_object(state, permanent.canonical_id)
                .unwrap()
                == Some(wanted)
        })
        .unwrap()
        .canonical_id
}

#[test]
fn artificers_assistant_is_exact_historic_scry_and_a_floodcaller_bird() {
    let cards = CurrentCardDatabase::load().unwrap();
    let assistant = card(&cards, "Artificer's Assistant");
    let profile = cards.profile(assistant).unwrap();
    assert_eq!(profile.role, R2CardRole::CreaturePermanent);
    assert_eq!(profile.utility, UtilityKind::ArtificersAssistant);
    assert!(profile.floodcaller_untap_eligible);

    let mut state = state_with(
        &cards,
        vec![permanent(&cards, 1, "Artificer's Assistant", false)],
        &["Tormod's Crypt"],
        &["Island"],
        ManaPool::default(),
        Phase::PrecombatMain,
    );
    apply_action(
        &mut state,
        &cards,
        Action::CastFromHand {
            card: card(&cards, "Tormod's Crypt"),
            payment: ManaPayment::default(),
        },
    )
    .unwrap();
    assert!(matches!(
        state.stack.last(),
        Some(StackObject::ControlledTrigger {
            ability: ABILITY_ARTIFICERS_ASSISTANT_SCRY,
            ..
        })
    ));
    apply_action(&mut state, &cards, Action::PassPriority).unwrap();
    assert!(matches!(state.pending, PendingDecision::ScryChoice { .. }));
}

#[test]
fn chrome_dome_static_power_haste_and_delayed_sacrifice_are_executable() {
    let cards = CurrentCardDatabase::load().unwrap();
    let chrome = card(&cards, "Chrome Dome");
    assert_eq!(cards.profile(chrome).unwrap().engine, EngineKind::ChromeDome);

    let mut power_state = state_with(
        &cards,
        vec![
            permanent(&cards, 1, "Chrome Dome", false),
            permanent(&cards, 2, "Battered Golem", false),
            permanent(&cards, 3, "Uthros Research Craft", false),
        ],
        &[],
        &[],
        ManaPool::default(),
        Phase::PrecombatMain,
    );
    apply_action(
        &mut power_state,
        &cards,
        Action::ActivateUthrosStation {
            source: ObjectId(3),
            creature: canonical_for(&power_state, ObjectId(2)),
        },
    )
    .unwrap();
    apply_action(&mut power_state, &cards, Action::PassPriority).unwrap();
    assert_eq!(
        power_state
            .battlefield
            .get(ObjectId(3))
            .unwrap()
            .counters
            .charge,
        4,
        "Battered Golem is 3 power plus Chrome Dome's +1/+0"
    );

    let mut copy_state = state_with(
        &cards,
        vec![
            permanent(&cards, 10, "Chrome Dome", false),
            permanent(&cards, 11, "Battered Golem", false),
        ],
        &[],
        &[],
        ManaPool {
            colorless: 5,
            ..ManaPool::default()
        },
        Phase::PrecombatMain,
    );
    apply_action(
        &mut copy_state,
        &cards,
        Action::ActivateChromeDome {
            source: ObjectId(10),
            target: canonical_for(&copy_state, ObjectId(11)),
            payment: ManaPayment {
                colorless: 5,
                ..ManaPayment::default()
            },
        },
    )
    .unwrap();
    apply_action(&mut copy_state, &cards, Action::PassPriority).unwrap();
    let copied = copy_state
        .battlefield
        .permanents()
        .iter()
        .find(|permanent| permanent.card == card(&cards, "Battered Golem") && permanent.token)
        .unwrap();
    assert!(!copied.summoning_sick, "Chrome Dome gives the copy haste");
    assert!(copy_state.delayed_events.iter().any(|event| matches!(
        event,
        DelayedEvent::ChromeCopySacrifice { object, .. } if *object == copied.object_id
    )));
}

#[test]
fn valley_floodcaller_flash_permission_pump_untap_and_cleanup_are_executable() {
    let cards = CurrentCardDatabase::load().unwrap();
    let valley = card(&cards, "Valley Floodcaller");
    let profile = cards.profile(valley).unwrap();
    assert_eq!(profile.engine, EngineKind::ValleyFloodcaller);
    assert!(profile.floodcaller_untap_eligible);

    let valley_payment = payment_for(&cards, "Valley Floodcaller");
    let mut flash_self = state_with(
        &cards,
        Vec::new(),
        &["Valley Floodcaller"],
        &[],
        pool_for(valley_payment),
        Phase::EndStep,
    );
    apply_action(
        &mut flash_self,
        &cards,
        Action::CastFromHand {
            card: valley,
            payment: valley_payment,
        },
    )
    .unwrap();

    let scroll_payment = payment_for(&cards, "Merchant Scroll");
    let mut state = state_with(
        &cards,
        vec![
            permanent(&cards, 20, "Valley Floodcaller", true),
            permanent(&cards, 21, "Artificer's Assistant", true),
        ],
        &["Merchant Scroll"],
        &[],
        pool_for(scroll_payment),
        Phase::EndStep,
    );
    apply_action(
        &mut state,
        &cards,
        Action::CastFromHand {
            card: card(&cards, "Merchant Scroll"),
            payment: scroll_payment,
        },
    )
    .unwrap();
    assert!(matches!(
        state.stack.last(),
        Some(StackObject::ControlledTrigger {
            ability: ABILITY_FLOODCALLER_UNTAP,
            ..
        })
    ));
    apply_action(&mut state, &cards, Action::PassPriority).unwrap();
    for object in [ObjectId(20), ObjectId(21)] {
        let permanent = state.battlefield.get(object).unwrap();
        assert!(!permanent.tapped);
        assert_eq!(permanent.counters.temporary_power_boost, 1);
    }

    let seeker_payment = payment_for(&cards, "Spellseeker");
    let mut creature_at_end_step = state_with(
        &cards,
        vec![permanent(&cards, 30, "Valley Floodcaller", false)],
        &["Spellseeker"],
        &[],
        pool_for(seeker_payment),
        Phase::EndStep,
    );
    assert!(
        apply_action(
            &mut creature_at_end_step,
            &cards,
            Action::CastFromHand {
                card: card(&cards, "Spellseeker"),
                payment: seeker_payment,
            },
        )
        .is_err(),
        "Floodcaller does not grant flash to creature spells"
    );

    let mut cleanup = state_with(
        &cards,
        vec![permanent(&cards, 40, "Valley Floodcaller", false)],
        &[],
        &[],
        ManaPool::default(),
        Phase::EndStep,
    );
    let mut permanents = cleanup.battlefield.permanents().to_vec();
    permanents[0].counters.temporary_power_boost = 2;
    cleanup.battlefield = BattlefieldZone::new(permanents);
    advance_phase(&mut cleanup, &cards).unwrap();
    assert_eq!(
        cleanup
            .battlefield
            .get(ObjectId(40))
            .unwrap()
            .counters
            .temporary_power_boost,
        0
    );
}

#[test]
fn attached_artifacts_can_be_sacrificed_and_knack_bounce_cleans_up_attachments() {
    let cards = CurrentCardDatabase::load().unwrap();

    let mut power = permanent(&cards, 3, "Power Artifact", false);
    power.attached_to = Some(ObjectId(2));
    let mut sacrifice_state = state_with(
        &cards,
        vec![
            permanent(&cards, 1, "Grinding Station", false),
            permanent(&cards, 2, "Basalt Monolith", false),
            power,
        ],
        &[],
        &[],
        ManaPool::default(),
        Phase::PrecombatMain,
    );
    apply_action(
        &mut sacrifice_state,
        &cards,
        Action::ActivateGrindingStation {
            source: ObjectId(1),
            sacrifice: canonical_for(&sacrifice_state, ObjectId(2)),
        },
    )
    .unwrap();
    assert!(sacrifice_state.graveyard.cards().contains(&card(&cards, "Basalt Monolith")));
    assert!(sacrifice_state.graveyard.cards().contains(&card(&cards, "Power Artifact")));

    for spell in ["Banishing Knack", "Retraction Helix"] {
        let mut power = permanent(&cards, 13, "Power Artifact", false);
        power.attached_to = Some(ObjectId(12));
        let payment = payment_for(&cards, spell);
        let mut state = state_with(
            &cards,
            vec![
                permanent(&cards, 11, "Battered Golem", false),
                permanent(&cards, 12, "Basalt Monolith", false),
                power,
            ],
            &[spell],
            &[],
            pool_for(payment),
            Phase::PrecombatMain,
        );
        apply_action(
            &mut state,
            &cards,
            Action::CastTargetedFromHand {
                card: card(&cards, spell),
                target: canonical_for(&state, ObjectId(11)),
                payment,
            },
        )
        .unwrap();
        apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        apply_action(
            &mut state,
            &cards,
            Action::ActivateGrantedKnackBounce {
                source: ObjectId(11),
                target: canonical_for(&state, ObjectId(12)),
            },
        )
        .unwrap();
        apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        assert!(state.hand.cards().contains(&card(&cards, "Basalt Monolith")));
        assert!(state.graveyard.cards().contains(&card(&cards, "Power Artifact")));
    }
}
''',
)

write(
    "rust/crates/urza-policy-bridge/tests/post_r7_modeling_completeness_rules_active_repair_v1.rs",
    r'''use urza_cards::CurrentCardDatabase;
use urza_core::{
    BattlefieldZone, CounterState, GrantedAbility, ManaPool, ObjectId, PermanentMode,
    PermanentState, Phase, TrueState, Window,
};
use urza_policy_bridge::CandidateBridge;
use urza_rules::{Action, CardDatabase, ManaPayment};

fn card(cards: &CurrentCardDatabase, name: &str) -> urza_core::CardDefId {
    cards.card_id_by_name(name).unwrap()
}

fn permanent(cards: &CurrentCardDatabase, object: u32, name: &str, tapped: bool) -> PermanentState {
    let id = card(cards, name);
    let profile = cards.profile(id).unwrap();
    PermanentState {
        object_id: ObjectId(object),
        card: id,
        face: profile.battlefield_face,
        tapped,
        summoning_sick: false,
        token: false,
        counters: CounterState::default(),
        mode: PermanentMode::Normal,
        attached_to: None,
        granted_ability: None,
    }
}

fn build(state: TrueState, cards: &CurrentCardDatabase) -> CandidateBridge {
    state.validate().unwrap();
    CandidateBridge::build(&state, cards).unwrap()
}

#[test]
fn floodcaller_flash_casts_are_public_candidates_but_creatures_remain_sorcery_timed() {
    let cards = CurrentCardDatabase::load().unwrap();
    let scroll = card(&cards, "Merchant Scroll");
    let seeker = card(&cards, "Spellseeker");
    let state = TrueState {
        turn: 1,
        phase: Phase::EndStep,
        window: Window::Priority,
        hand: vec![scroll, seeker].into(),
        battlefield: BattlefieldZone::new(vec![permanent(
            &cards,
            1,
            "Valley Floodcaller",
            false,
        )]),
        mana: ManaPool {
            blue: 4,
            ..ManaPool::default()
        },
        ..TrueState::default()
    };
    let bridge = build(state, &cards);
    let has_scroll = bridge.candidates().iter().any(|candidate| {
        matches!(
            bridge.resolve(candidate.token),
            Some(Action::CastFromHand { card, .. }) if *card == scroll
        )
    });
    let has_seeker = bridge.candidates().iter().any(|candidate| {
        matches!(
            bridge.resolve(candidate.token),
            Some(Action::CastFromHand { card, .. }) if *card == seeker
        )
    });
    assert!(has_scroll);
    assert!(!has_seeker);

    let valley = card(&cards, "Valley Floodcaller");
    let state = TrueState {
        turn: 1,
        phase: Phase::EndStep,
        window: Window::Priority,
        hand: vec![valley].into(),
        mana: ManaPool {
            blue: 1,
            colorless: 2,
            ..ManaPool::default()
        },
        ..TrueState::default()
    };
    let bridge = build(state, &cards);
    assert!(bridge.candidates().iter().any(|candidate| {
        matches!(
            bridge.resolve(candidate.token),
            Some(Action::CastFromHand { card, .. }) if *card == valley
        )
    }));
}

#[test]
fn gadgeteer_reduced_clue_draw_is_public_and_exact() {
    let cards = CurrentCardDatabase::load().unwrap();
    let clue = cards.clue_token_card().unwrap();
    let clue_profile = cards.profile(clue).unwrap();
    let state = TrueState {
        turn: 1,
        phase: Phase::PrecombatMain,
        window: Window::Priority,
        battlefield: BattlefieldZone::new(vec![
            permanent(&cards, 1, "Forensic Gadgeteer", false),
            PermanentState {
                object_id: ObjectId(2),
                card: clue,
                face: clue_profile.battlefield_face,
                tapped: false,
                summoning_sick: false,
                token: true,
                counters: CounterState::default(),
                mode: PermanentMode::Normal,
                attached_to: None,
                granted_ability: None,
            },
        ]),
        mana: ManaPool {
            colorless: 1,
            ..ManaPool::default()
        },
        ..TrueState::default()
    };
    let bridge = build(state, &cards);
    assert!(bridge.candidates().iter().any(|candidate| {
        matches!(
            bridge.resolve(candidate.token),
            Some(Action::ActivateClueDraw {
                source: ObjectId(2),
                payment: ManaPayment { colorless: 1, .. }
            })
        )
    }));
}

#[test]
fn knack_bounce_candidate_remains_visible_when_target_has_an_attachment() {
    let cards = CurrentCardDatabase::load().unwrap();
    let mut source = permanent(&cards, 1, "Battered Golem", false);
    source.granted_ability = Some(GrantedAbility::KnackBounceUntilEndOfTurn);
    let target = permanent(&cards, 2, "Basalt Monolith", false);
    let mut aura = permanent(&cards, 3, "Power Artifact", false);
    aura.attached_to = Some(ObjectId(2));
    let state = TrueState {
        turn: 1,
        phase: Phase::PrecombatMain,
        window: Window::Priority,
        battlefield: BattlefieldZone::new(vec![source, target, aura]),
        ..TrueState::default()
    };
    let bridge = build(state, &cards);
    assert!(bridge.candidates().iter().any(|candidate| {
        matches!(
            bridge.resolve(candidate.token),
            Some(Action::ActivateGrantedKnackBounce {
                source: ObjectId(1),
                ..
            })
        )
    }));
}
''',
)
