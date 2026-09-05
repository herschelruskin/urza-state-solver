use std::collections::{BTreeMap, BTreeSet};

use urza_cards::{
    CoverageStatus, R3_ACCEPTED_ACTIVE_IDENTITY_COUNT, R3CardDatabase,
    R4_ACCEPTED_ACTIVE_IDENTITY_COUNT, R4_ONLY_ACTIVE_NAMES, R4CardDatabase, load_coverage,
    load_r1_catalog, validate_r4_database,
};
use urza_core::{
    BattlefieldZone, CardDefId, CardZone, CommanderState, CommanderZone, CounterState,
    DelayedEvent, GrantedAbility, MODEL_VERSION, ManaPool, ObjectId, PendingDecision,
    PermanentMode, PermanentState, Phase, R3_MODEL_VERSION, TrueLibrary, TrueState, Window,
};
use urza_info::{INFORMATION_SCHEMA_VERSION, R3_INFORMATION_SCHEMA_VERSION, observe};
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
    delayed
        .delayed_events
        .push(DelayedEvent::ChromeCopySacrifice {
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
    assert!(matches!(
        top_state.pending,
        PendingDecision::TopReorder { .. }
    ));
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
    assert!(
        station_actions
            .iter()
            .any(|action| matches!(action, Action::ChooseProducerUntap { untap: true }))
    );
    assert!(
        station_actions
            .iter()
            .any(|action| matches!(action, Action::ChooseProducerUntap { untap: false }))
    );

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
    assert!(matches!(
        cam_state.pending,
        PendingDecision::CamTarget { .. }
    ));
    let target_actions = legal_contingent_actions(&observe(&cam_state).unwrap(), &cards);
    let target = target_actions
        .into_iter()
        .find(|action| matches!(action, Action::ChooseCamTarget { .. }))
        .unwrap();
    apply_action(&mut cam_state, &cards, target).unwrap();
    apply_action(&mut cam_state, &cards, Action::PassPriority).unwrap();
    assert!(matches!(
        cam_state.pending,
        PendingDecision::CamEffect { .. }
    ));
    let effect_actions = legal_contingent_actions(&observe(&cam_state).unwrap(), &cards);
    assert!(effect_actions.iter().any(|action| matches!(
        action,
        Action::ChooseCamEffect {
            choice: urza_rules::CamEffectChoice::Decline
        }
    )));
    let decline = effect_actions
        .into_iter()
        .find(|action| {
            matches!(
                action,
                Action::ChooseCamEffect {
                    choice: urza_rules::CamEffectChoice::Decline
                }
            )
        })
        .unwrap();
    apply_action(&mut cam_state, &cards, decline).unwrap();
    assert!(matches!(cam_state.pending, PendingDecision::None));
}
