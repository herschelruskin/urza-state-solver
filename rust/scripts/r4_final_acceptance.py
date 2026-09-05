from pathlib import Path


def replace(path: str, old: str, new: str, count: int = 1) -> None:
    p = Path(path)
    text = p.read_text()
    found = text.count(old)
    if found < count:
        raise SystemExit(f"{path}: expected at least {count} occurrence(s), found {found}: {old[:160]!r}")
    p.write_text(text.replace(old, new, count))


# Freeze final R4 rules namespace.
replace(
    "rust/crates/urza-rules/src/lib.rs",
    'pub const RULES_VERSION: &str = "r4_terminal_acceptance_v5";',
    'pub const RULES_VERSION: &str = "r4_acceptance_v6";',
)

# Explicit accepted registry constants.
replace(
    "rust/crates/urza-cards/src/lib.rs",
    'pub const R1_CATALOG_DIGEST_BLAKE3: &str =\n    "4b39c7db7bfd2c6f68d7a49efa515cdffb2c6a9716022bc0b21eeec56754a983";\n',
    '''pub const R1_CATALOG_DIGEST_BLAKE3: &str =
    "4b39c7db7bfd2c6f68d7a49efa515cdffb2c6a9716022bc0b21eeec56754a983";
pub const R3_ACCEPTED_ACTIVE_IDENTITY_COUNT: usize = 32;
pub const R4_ACCEPTED_ACTIVE_IDENTITY_COUNT: usize = 47;
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
''',
)

replace(
    "rust/crates/urza-cards/src/lib.rs",
    '''    if database.supported_active_cards().len() != 32 {
        return Err(CatalogError::Invariant(
            "historical R3 database must remain exactly 32 active identities".to_owned(),
        ));
    }
''',
    '''    if database.supported_active_cards().len() != R3_ACCEPTED_ACTIVE_IDENTITY_COUNT {
        return Err(CatalogError::Invariant(format!(
            "historical R3 database must remain exactly {R3_ACCEPTED_ACTIVE_IDENTITY_COUNT} active identities"
        )));
    }
''',
)

replace(
    "rust/crates/urza-cards/src/lib.rs",
    '''pub fn validate_r4_database() -> Result<(), CatalogError> {
    let catalog = load_r1_catalog()?;
''',
    '''pub fn validate_r4_database() -> Result<(), CatalogError> {
    // R4 acceptance is cumulative: its audit must fail if an earlier accepted
    // catalog/database contract has drifted even when the standalone R4 count
    // would otherwise still look plausible.
    validate_r1_catalog()?;
    validate_r2_database()?;
    validate_r3_database()?;

    let catalog = load_r1_catalog()?;
''',
)

replace(
    "rust/crates/urza-cards/src/lib.rs",
    '''    if database.supported_active_cards().len() != 47 {
        return Err(CatalogError::Invariant(
            "current R4 database must expose exactly 47 active identities".to_owned(),
        ));
    }

    Ok(())
}
''',
    '''    let r4_supported: BTreeSet<_> = database.supported_active_cards().into_iter().collect();
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
''',
)

# CLI reports the full acceptance contract, including information/value schemas.
cli_cargo = Path("rust/crates/urza-cli/Cargo.toml")
cli_text = cli_cargo.read_text()
if 'urza-info = { path = "../urza-info" }' not in cli_text:
    cli_text = cli_text.replace(
        'urza-core = { path = "../urza-core" }\n',
        'urza-core = { path = "../urza-core" }\nurza-info = { path = "../urza-info" }\n',
        1,
    )
if 'urza-value = { path = "../urza-value" }' not in cli_text:
    cli_text = cli_text.replace(
        'urza-rules = { path = "../urza-rules" }\n',
        'urza-rules = { path = "../urza-rules" }\nurza-value = { path = "../urza-value" }\n',
        1,
    )
cli_cargo.write_text(cli_text)

replace(
    "rust/crates/urza-cli/src/main.rs",
    '''    R2CardDatabase, R3CardDatabase, R4CardDatabase, URZA_CONSTRUCT_TOKEN_CARD_ID,
    catalog_digest_hex, load_catalog, load_coverage, load_r1_catalog, r1_catalog_digest_hex,
    validate_catalog_and_coverage, validate_r1_catalog, validate_r2_database, validate_r3_database,
    validate_r4_database,
''',
    '''    R2CardDatabase, R3CardDatabase, R3_ACCEPTED_ACTIVE_IDENTITY_COUNT, R4CardDatabase,
    R4_ACCEPTED_ACTIVE_IDENTITY_COUNT, R4_ONLY_ACTIVE_NAMES, URZA_CONSTRUCT_TOKEN_CARD_ID,
    catalog_digest_hex, load_catalog, load_coverage, load_r1_catalog, r1_catalog_digest_hex,
    validate_catalog_and_coverage, validate_r1_catalog, validate_r2_database, validate_r3_database,
    validate_r4_database,
''',
)
replace(
    "rust/crates/urza-cli/src/main.rs",
    'use urza_core::{MODEL_VERSION, R2_MODEL_VERSION, R3_MODEL_VERSION, TrueState};\n',
    'use urza_core::{MODEL_VERSION, R2_MODEL_VERSION, R3_MODEL_VERSION, TrueState};\nuse urza_info::INFORMATION_SCHEMA_VERSION;\n',
)
replace(
    "rust/crates/urza-cli/src/main.rs",
    '''use urza_rules::{
    HORIZON_TURN, R2_RULES_VERSION, R2CardRole, R3_RULES_VERSION, RULES_VERSION, WinFamily,
};
''',
    '''use urza_rules::{
    HORIZON_TURN, R2_RULES_VERSION, R2CardRole, R3_RULES_VERSION, RULES_VERSION, WinFamily,
};
use urza_value::VALUE_KEY_SCHEMA_VERSION;
''',
)

old_report = '''    let terminal_families: Vec<_> = WinFamily::ALL.into_iter().map(WinFamily::label).collect();
    let terminal_family_count = terminal_families.len();

    let report = json!({
        "phase": "R4-terminal-acceptance",
        "rules_version": RULES_VERSION,
        "model_version": MODEL_VERSION,
        "horizon_turn": HORIZON_TURN,
        "supported_active_card_identities": supported_names.len(),
        "supported_active_names": supported_names,
        "active_engine_primitives": [
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
            "Sewer-veillance Cam"
        ],
        "terminal_family_count": terminal_family_count,
        "terminal_families": terminal_families,
        "terminal_detection_boundary": "public InformationState only; exact attachments/modes/grants preserved; stack and pending decisions block terminal recognition; Cage blocks library-cast families; hidden library order and raw ObjectId identity are irrelevant",
        "scope": "R4 terminal-family acceptance hardened across all 13 audited families; remaining deferred card text is outside these accepted terminal witnesses"
    });
'''
new_report = '''    let terminal_families: Vec<_> = WinFamily::ALL.into_iter().map(WinFamily::label).collect();
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
'''
replace("rust/crates/urza-cli/src/main.rs", old_report, new_report)

# ValueKey final acceptance tests need the value crate directly.
cards_cargo = Path("rust/crates/urza-cards/Cargo.toml")
cards_text = cards_cargo.read_text()
if 'urza-value = { path = "../urza-value" }' not in cards_text:
    cards_text = cards_text.replace(
        '[dev-dependencies]\nurza-info = { path = "../urza-info" }\n',
        '[dev-dependencies]\nurza-info = { path = "../urza-info" }\nurza-value = { path = "../urza-value" }\n',
        1,
    )
cards_cargo.write_text(cards_text)

# Final broader acceptance integration tests.
test_path = Path("rust/crates/urza-cards/tests/r4_final_acceptance.rs")
test_path.write_text(r'''use std::collections::{BTreeMap, BTreeSet};

use urza_cards::{
    CoverageStatus, R3CardDatabase, R3_ACCEPTED_ACTIVE_IDENTITY_COUNT, R4CardDatabase,
    R4_ACCEPTED_ACTIVE_IDENTITY_COUNT, R4_ONLY_ACTIVE_NAMES, load_coverage, load_r1_catalog,
    validate_r4_database,
};
use urza_core::{
    BattlefieldZone, CardDefId, CardZone, CommanderState, CommanderZone, CounterState,
    DelayedEvent, GrantedAbility, ManaPool, ObjectId, PendingDecision, PermanentMode,
    PermanentState, Phase, R3_MODEL_VERSION, TrueLibrary, TrueState, Window, MODEL_VERSION,
};
use urza_info::{
    INFORMATION_SCHEMA_VERSION, R3_INFORMATION_SCHEMA_VERSION, observe,
};
use urza_rules::{
    Action, ManaPayment, R2CardRole, RULES_VERSION, UtilityKind, WinFamily, apply_action,
    legal_contingent_actions,
};
use urza_value::{R3_VALUE_KEY_SCHEMA_VERSION, VALUE_KEY_SCHEMA_VERSION, ValueKey};

fn card(cards: &R4CardDatabase, name: &str) -> CardDefId {
    cards.card_id_by_name(name).unwrap()
}

fn permanent(cards: &R4CardDatabase, object: u32, name: &str) -> PermanentState {
    let card = card(cards, name);
    let profile = cards.profile(card).unwrap();
    let mode = match profile.utility {
        UtilityKind::RealityChip => PermanentMode::RealityChipCreature,
        UtilityKind::FortuneTellersTalent => PermanentMode::FortuneTellersTalentLevel1,
        _ => PermanentMode::Normal,
    };
    PermanentState {
        object_id: ObjectId(object),
        card,
        face: profile.battlefield_face,
        tapped: false,
        summoning_sick: false,
        token: false,
        counters: CounterState {
            loyalty: profile.starting_loyalty,
            ..CounterState::default()
        },
        mode,
        attached_to: None,
        granted_ability: None,
    }
}

fn named(cards: &R4CardDatabase, names: &[&str]) -> Vec<CardDefId> {
    names.iter().map(|name| card(cards, name)).collect()
}

fn state(
    cards: &R4CardDatabase,
    permanents: Vec<PermanentState>,
    hand: &[&str],
    library: &[&str],
    mana: ManaPool,
) -> TrueState {
    let urza_present = permanents.iter().any(|permanent| {
        cards
            .profile(permanent.card)
            .is_some_and(|profile| profile.role == R2CardRole::UrzaCommander)
    });
    let state = TrueState {
        turn: 4,
        phase: Phase::PrecombatMain,
        window: Window::Priority,
        hand: CardZone::new(named(cards, hand)),
        library: TrueLibrary::unknown(named(cards, library)),
        battlefield: BattlefieldZone::new(permanents),
        mana,
        commander: CommanderState {
            zone: if urza_present {
                CommanderZone::Battlefield
            } else {
                CommanderZone::CommandZone
            },
            command_zone_casts: u8::from(urza_present),
        },
        ..TrueState::default()
    };
    state.validate().unwrap();
    state
}

fn payment_and_pool(cards: &R4CardDatabase, name: &str) -> (ManaPayment, ManaPool) {
    let cost = cards.profile(card(cards, name)).unwrap().mana_cost.unwrap();
    let payment = ManaPayment {
        white: cost.white,
        blue: cost.blue,
        black: cost.black,
        red: cost.red,
        green: cost.green,
        colorless: cost.colorless + cost.generic,
    };
    let pool = ManaPool {
        white: payment.white,
        blue: payment.blue,
        black: payment.black,
        red: payment.red,
        green: payment.green,
        colorless: payment.colorless,
    };
    (payment, pool)
}

fn key(state: &TrueState) -> ValueKey {
    ValueKey::try_from_information(&observe(state).unwrap()).unwrap()
}

#[test]
fn r4_is_the_exact_audited_extension_of_frozen_r3() {
    validate_r4_database().unwrap();
    let r3 = R3CardDatabase::load().unwrap();
    let r4 = R4CardDatabase::load().unwrap();
    let r3_ids: BTreeSet<_> = r3.supported_active_cards().into_iter().collect();
    let r4_ids: BTreeSet<_> = r4.supported_active_cards().into_iter().collect();

    assert_eq!(r3_ids.len(), R3_ACCEPTED_ACTIVE_IDENTITY_COUNT);
    assert_eq!(r4_ids.len(), R4_ACCEPTED_ACTIVE_IDENTITY_COUNT);
    assert!(r3_ids.is_subset(&r4_ids));

    let expected: BTreeSet<_> = R4_ONLY_ACTIVE_NAMES
        .into_iter()
        .map(|name| r4.card_id_by_name(name).unwrap())
        .collect();
    let actual: BTreeSet<_> = r4_ids.difference(&r3_ids).copied().collect();
    assert_eq!(actual, expected);

    let coverage = load_coverage().unwrap();
    let coverage_by_id: BTreeMap<_, _> = coverage
        .entries
        .iter()
        .map(|entry| (entry.card_id, entry))
        .collect();
    for name in R4_ONLY_ACTIVE_NAMES {
        let id = r4.card_id_by_name(name).unwrap();
        let entry = coverage_by_id[&id.0];
        assert!(
            matches!(
                entry.status,
                CoverageStatus::PrimitiveActive | CoverageStatus::RulesActive
            ),
            "{name} must remain explicitly active at R4 acceptance"
        );
        assert!(
            entry.reason.as_deref().unwrap_or_default().contains("R4"),
            "{name} must retain an R4-specific coverage reason"
        );
    }

    let catalog = load_r1_catalog().unwrap();
    assert_eq!(catalog.cards.len() - r4_ids.len(), 48);
}

#[test]
fn r4_final_namespaces_are_frozen_and_distinct_from_r3() {
    assert_eq!(RULES_VERSION, "r4_acceptance_v6");
    assert_eq!(MODEL_VERSION, "urza_model_r4c_2026_09_04");
    assert_eq!(INFORMATION_SCHEMA_VERSION, "information_state_v7_r4");
    assert_eq!(VALUE_KEY_SCHEMA_VERSION, "value_key_v7_r4");
    assert_ne!(MODEL_VERSION, R3_MODEL_VERSION);
    assert_ne!(INFORMATION_SCHEMA_VERSION, R3_INFORMATION_SCHEMA_VERSION);
    assert_ne!(VALUE_KEY_SCHEMA_VERSION, R3_VALUE_KEY_SCHEMA_VERSION);
    assert_eq!(WinFamily::ALL.len(), 13);
}

#[test]
fn r4_recurrence_state_reaches_information_and_value_identity() {
    let cards = R4CardDatabase::load().unwrap();
    let urza = permanent(&cards, 1, "Urza, Lord High Artificer");
    let golem = permanent(&cards, 2, "Battered Golem");
    let chrome = permanent(&cards, 3, "Chrome Dome");
    let base = state(
        &cards,
        vec![urza, golem, chrome],
        &[],
        &["Island", "Sol Ring"],
        ManaPool::default(),
    );

    let mut granted = base.clone();
    let mut permanents = granted.battlefield.permanents().to_vec();
    permanents
        .iter_mut()
        .find(|permanent| permanent.card == card(&cards, "Battered Golem"))
        .unwrap()
        .granted_ability = Some(GrantedAbility::KnackBounceUntilEndOfTurn);
    granted.battlefield = BattlefieldZone::new(permanents);
    assert_ne!(observe(&base).unwrap(), observe(&granted).unwrap());
    assert_ne!(key(&base), key(&granted));

    let mut delayed = base.clone();
    let chrome_permanent = delayed
        .battlefield
        .permanents()
        .iter()
        .find(|permanent| permanent.card == card(&cards, "Chrome Dome"))
        .unwrap()
        .clone();
    delayed.delayed_events.push(DelayedEvent::ChromeCopySacrifice {
        object: chrome_permanent.object_id,
        card: chrome_permanent.card,
        due_turn: delayed.turn,
    });
    delayed.validate().unwrap();
    assert_ne!(observe(&base).unwrap(), observe(&delayed).unwrap());
    assert_ne!(key(&base), key(&delayed));
}

#[test]
fn r4_preserves_hidden_order_noninterference_at_the_value_boundary() {
    let cards = R4CardDatabase::load().unwrap();
    let battlefield = vec![
        permanent(&cards, 1, "Urza, Lord High Artificer"),
        permanent(&cards, 2, "Chrome Dome"),
        permanent(&cards, 3, "Battered Golem"),
    ];
    let a = state(
        &cards,
        battlefield.clone(),
        &[],
        &["Island", "Sol Ring", "Tormod's Crypt"],
        ManaPool::default(),
    );
    let b = state(
        &cards,
        battlefield,
        &[],
        &["Tormod's Crypt", "Island", "Sol Ring"],
        ManaPool::default(),
    );

    assert_eq!(observe(&a).unwrap(), observe(&b).unwrap());
    assert_eq!(key(&a), key(&b));
}

#[test]
fn r4_specific_contingent_decisions_are_exposed_as_public_actions() {
    let cards = R4CardDatabase::load().unwrap();

    // Top look: stack resolution must expose a reorder decision rather than
    // allowing execution code to choose from true hidden order.
    let mut top_state = state(
        &cards,
        vec![permanent(&cards, 10, "Sensei's Divining Top")],
        &[],
        &["Island", "Sol Ring", "Tormod's Crypt"],
        ManaPool {
            colorless: 1,
            ..ManaPool::default()
        },
    );
    apply_action(
        &mut top_state,
        &cards,
        Action::ActivateTopLook {
            source: ObjectId(10),
            payment: ManaPayment {
                colorless: 1,
                ..ManaPayment::default()
            },
        },
    )
    .unwrap();
    apply_action(&mut top_state, &cards, Action::PassPriority).unwrap();
    assert!(matches!(top_state.pending, PendingDecision::TopReorder { .. }));
    let top_actions = legal_contingent_actions(&observe(&top_state).unwrap(), &cards);
    assert!(!top_actions.is_empty());
    assert!(
        top_actions
            .iter()
            .all(|action| matches!(action, Action::ChooseTopOrder { .. }))
    );
    apply_action(&mut top_state, &cards, top_actions[0].clone()).unwrap();
    assert!(matches!(top_state.pending, PendingDecision::None));

    // Artifact entry: a tapped Station's may-untap trigger must become a
    // public yes/no decision after the trigger resolves.
    let mut station = permanent(&cards, 20, "Grinding Station");
    station.tapped = true;
    let mut station_state = state(
        &cards,
        vec![station],
        &["Tormod's Crypt"],
        &[],
        ManaPool::default(),
    );
    apply_action(
        &mut station_state,
        &cards,
        Action::CastFromHand {
            card: card(&cards, "Tormod's Crypt"),
            payment: ManaPayment::default(),
        },
    )
    .unwrap();
    apply_action(&mut station_state, &cards, Action::PassPriority).unwrap();
    apply_action(&mut station_state, &cards, Action::PassPriority).unwrap();
    assert!(matches!(
        station_state.pending,
        PendingDecision::ProducerUntapChoice { .. }
    ));
    let station_actions = legal_contingent_actions(&observe(&station_state).unwrap(), &cards);
    assert_eq!(station_actions.len(), 2);
    assert!(station_actions.iter().any(|action| matches!(
        action,
        Action::ChooseProducerUntap { untap: true }
    )));
    assert!(station_actions.iter().any(|action| matches!(
        action,
        Action::ChooseProducerUntap { untap: false }
    )));

    // Cam entry: target and effect are each factored through public contingent
    // choices, proving the final R4 trigger path is solver-visible.
    let creature = permanent(&cards, 30, "Spellseeker");
    let (cam_payment, cam_pool) = payment_and_pool(&cards, "Sewer-veillance Cam");
    let mut cam_state = state(
        &cards,
        vec![creature],
        &["Sewer-veillance Cam"],
        &[],
        cam_pool,
    );
    apply_action(
        &mut cam_state,
        &cards,
        Action::CastFromHand {
            card: card(&cards, "Sewer-veillance Cam"),
            payment: cam_payment,
        },
    )
    .unwrap();
    apply_action(&mut cam_state, &cards, Action::PassPriority).unwrap();
    apply_action(&mut cam_state, &cards, Action::PassPriority).unwrap();
    assert!(matches!(cam_state.pending, PendingDecision::CamTarget { .. }));
    let target_actions = legal_contingent_actions(&observe(&cam_state).unwrap(), &cards);
    let target = target_actions
        .into_iter()
        .find(|action| matches!(action, Action::ChooseCamTarget { .. }))
        .unwrap();
    apply_action(&mut cam_state, &cards, target).unwrap();
    apply_action(&mut cam_state, &cards, Action::PassPriority).unwrap();
    assert!(matches!(cam_state.pending, PendingDecision::CamEffect { .. }));
    let effect_actions = legal_contingent_actions(&observe(&cam_state).unwrap(), &cards);
    assert!(effect_actions.iter().any(|action| matches!(
        action,
        Action::ChooseCamEffect {
            choice: urza_rules::CamEffectChoice::Decline
        }
    )));
    let decline = effect_actions
        .into_iter()
        .find(|action| matches!(
            action,
            Action::ChooseCamEffect {
                choice: urza_rules::CamEffectChoice::Decline
            }
        ))
        .unwrap();
    apply_action(&mut cam_state, &cards, decline).unwrap();
    assert!(matches!(cam_state.pending, PendingDecision::None));
}
''')

# Human-readable acceptance checkpoint.
Path("rust/R4_ACCEPTANCE.md").write_text(r'''# R4 acceptance

## Status

R4 is accepted and closed once the validation gate below is green. This milestone freezes the rules-engine surface needed before deterministic R5 policy work begins; it does **not** claim that all 95 active card identities have complete Oracle text implemented.

## Accepted surface

R4 is an exact extension of the frozen R3 database:

- R3 accepted active identities: **32**;
- R4 accepted active identities: **47**;
- R4-only active identities: **15**;
- audited terminal families: **13**.

The exact R4-only extension is:

1. Basalt Monolith;
2. Grim Monolith;
3. Forensic Gadgeteer;
4. Power Artifact;
5. The Reality Chip;
6. Fortune Teller's Talent;
7. Grafdigger's Cage;
8. Grinding Station;
9. Battered Golem;
10. Chrome Dome;
11. Mana Vault;
12. Banishing Knack;
13. Retraction Helix;
14. Valley Floodcaller;
15. Sewer-veillance Cam.

The R4 validator checks this **set exactly**, not merely the total count, and requires an R4-specific coverage reason for every R4-only identity. The R4 audit is cumulative: R1 catalog, R2 database, and frozen R3 database validation are prerequisites of the R4 validator itself.

## Terminal-family gate

All 13 audited families have:

- a real-catalog positive witness;
- an executable final-step witness through the public rules transition API;
- a one-factor near miss;
- Urza-presence and unresolved-stack rejection;
- raw ObjectId renaming invariance;
- hidden-library permutation invariance where library order is not public;
- Grafdigger's Cage rejection for the Top/library-cast families.

Terminal recognition consumes `InformationState`, never `TrueState` hidden order.

## Decision / information boundary

R4-specific contingent decisions are accepted only when the policy-visible action surface can continue them from public information. Final acceptance exercises:

- Sensei's Divining Top reorder choices;
- Grinding Station / Battered Golem artifact-entry may-untap choices;
- Sewer-veillance Cam target selection and tap/untap/decline effect choice.

Ordinary action enumeration/ranking is intentionally **not** added here. R4 exposes typed execution actions and contingent public choices; deterministic policy construction and rollout selection remain R5 work.

## State / information / value contract

Final R4 namespaces are frozen as:

- rules: `r4_acceptance_v6`;
- model: `urza_model_r4c_2026_09_04`;
- information: `information_state_v7_r4`;
- ValueKey: `value_key_v7_r4`.

No final-acceptance state field was added. The acceptance tests instead verify that recurrence-relevant public state already introduced by R4—temporary granted abilities and Chrome Dome delayed sacrifice events—survives `TrueState -> InformationState -> ValueKey`, while unknown hidden-library permutations still merge.

## Coverage / deferred boundary

The active deck still contains **48 identities** whose R4 profile is `Unsupported`; each remains explicitly `INTENTIONALLY_UNMODELED` in the coverage registry. In addition, some of the 47 active identities are deliberately `PRIMITIVE_ACTIVE` and retain coverage-listed card text outside the accepted R4 engine surface.

Examples deliberately outside this R4 gate include Mana Vault upkeep/draw-step details, Sewer-veillance Cam sacrifice-draw text, Valley Floodcaller flash/combat sizing, Grafdigger's Cage effects beyond the accepted library-cast interaction, and older R2/R3 primitives whose unrelated activated/channel/combat text remains deferred. Those mechanics are not silently approximated.

## Acceptance validation

The closure gate is:

```text
cargo metadata --locked --format-version 1 --no-deps
cargo fmt --all -- --check
cargo clippy --locked --workspace --all-targets --all-features -- -D warnings
cargo test --locked --workspace --all-targets
cargo check --locked --workspace --benches
cargo run --locked -p urza-cli -- r0-audit
cargo run --locked -p urza-cli -- r1-audit
cargo run --locked -p urza-cli -- r2-audit
cargo run --locked -p urza-cli -- r3-audit
cargo run --locked -p urza-cli -- r4-audit
```

R5 must start from a commit for which all of these commands pass. R5 may consume the accepted typed rules/information/value surface, but must not weaken hidden-information boundaries or reintroduce Python gameplay implementation structures.
''')

# Update the workspace landing page to reflect current milestone state.
Path("rust/README.md").write_text(r'''# Urza Simulator Rust rebuild

This workspace is the clean-room, non-oracle Rust rebuild. Python remains in the repository as a regression witness and fixture source, not as the normative architecture or rules source.

Milestone status:

- R0 foundation: accepted;
- R1 catalog/state/information foundation: accepted;
- R2 core sequencing primitives: accepted;
- R3 staged search/top/permission mechanics: accepted;
- R4 engine interactions and 13-family terminal catalog: accepted;
- R5 deterministic policy/rollout work: next.

R4 closes with 47 active card identities, an exact 15-card extension over frozen R3, while unsupported identities and deferred primitive text remain explicitly classified rather than approximated. See `R4_ACCEPTANCE.md` for the boundary.

Foundation/acceptance commands:

    cargo fmt --all -- --check
    cargo clippy --locked --workspace --all-targets --all-features -- -D warnings
    cargo test --locked --workspace --all-targets
    cargo check --locked --workspace --benches
    cargo run --locked -p urza-cli -- r0-audit
    cargo run --locked -p urza-cli -- r1-audit
    cargo run --locked -p urza-cli -- r2-audit
    cargo run --locked -p urza-cli -- r3-audit
    cargo run --locked -p urza-cli -- r4-audit
''')

# Development log closure entry. The workflow only commits this after the full gate is green.
log = Path("rust/DEVELOPMENT_LOG.md")
log.write_text(log.read_text().rstrip() + r'''

## 2026-09-04 — R4 final acceptance closed

Classification: RULE/MODEL acceptance audit plus real-catalog PARITY witnesses. No POLICY implementation and no Python gameplay-logic port.

The final broader R4 pass closes the milestone around the already implemented engine/recurrence surface rather than adding unrelated card breadth:

- freezes R4 as exactly 47 active identities, an exact 15-card extension over the frozen 32-identity R3 surface;
- strengthens `validate_r4_database` so R4 validation is cumulative over R1/R2/R3 and rejects identity-set substitution even when the total active count remains 47;
- requires every R4-only active identity to retain an R4-specific coverage reason;
- freezes the final rules namespace at `r4_acceptance_v6` while retaining the already-required R4c model / v7 information / v7 ValueKey schemas;
- extends the R4 audit to report the information and ValueKey namespaces, exact R4-only identity list, terminal count, policy boundary, and explicitly unmodeled remainder;
- adds final integration acceptance for exact R3->R4 registry extension, recurrence-state propagation through InformationState/ValueKey, hidden-order noninterference, and actual public contingent-choice reachability for Top, producer may-untap, and Cam target/effect decisions;
- records the full R4 acceptance boundary in `R4_ACCEPTANCE.md` and marks R5 deterministic policy/rollout work as the next milestone.

R4 acceptance deliberately does not convert the remaining 48 unsupported active identities into vanilla approximations, and does not claim full text for `PRIMITIVE_ACTIVE` cards whose coverage reason still names deferred behavior.

Validation: the closure commit is produced only after locked dependency metadata, rustfmt, strict all-target/all-feature Clippy, workspace/all-target tests, benchmark compilation, and R0-R4 audit commands all pass in the dedicated closure workflow. The ordinary Rust foundation workflow is then expected to revalidate the committed result.
''' + "\n")
