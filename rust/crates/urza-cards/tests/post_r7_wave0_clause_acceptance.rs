use urza_cards::CurrentCardDatabase;
use urza_core::{
    BattlefieldZone, CardZone, CounterState, GrantedAbility, LibraryKnowledge, ManaPool, ObjectId,
    PermanentMode, PermanentState, Phase, StackObject, TrueLibrary, TrueState, Window,
};
use urza_info::observe;
use urza_rules::{
    ABILITY_ARTIFICERS_ASSISTANT_SCRY, ABILITY_FLOODCALLER_UNTAP, Action, CardDatabase,
    LandEntryChoice, ManaPayment, UtilityKind, advance_phase, apply_action,
};

fn card(cards: &CurrentCardDatabase, name: &str) -> urza_core::CardDefId {
    cards.card_id_by_name(name).unwrap()
}

fn permanent(
    cards: &CurrentCardDatabase,
    object: u32,
    name: &str,
    tapped: bool,
    summoning_sick: bool,
) -> PermanentState {
    let id = card(cards, name);
    let profile = cards.profile(id).unwrap();
    PermanentState {
        object_id: ObjectId(object),
        card: id,
        face: profile.battlefield_face,
        tapped,
        summoning_sick,
        token: false,
        counters: CounterState::default(),
        mode: match profile.utility {
            UtilityKind::RealityChip => PermanentMode::RealityChipCreature,
            UtilityKind::UthrosResearchCraft => PermanentMode::UthrosStation,
            _ => PermanentMode::Normal,
        },
        attached_to: None,
        granted_ability: None,
    }
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
            urza_info::resolve_canonical_object(state, permanent.canonical_id).unwrap()
                == Some(wanted)
        })
        .unwrap()
        .canonical_id
}

#[test]
fn artificers_assistant_historic_clause_is_total_for_the_pinned_deck() {
    let cards = CurrentCardDatabase::load().unwrap();
    let assistant = card(&cards, "Artificer's Assistant");
    let crypt = card(&cards, "Tormod's Crypt");
    let scroll = card(&cards, "Merchant Scroll");
    let saga = card(&cards, "Urza's Saga");
    let tezz = card(&cards, "Tezzeret, Cruel Captain");

    assert!(cards.is_historic_spell(crypt));
    assert!(cards.is_historic_spell(saga));
    assert!(cards.is_historic_spell(tezz));
    assert!(!cards.is_historic_spell(scroll));

    let mut artifact_cast = TrueState {
        turn: 1,
        phase: Phase::PrecombatMain,
        window: Window::Priority,
        hand: CardZone::new(vec![crypt]),
        battlefield: BattlefieldZone::new(vec![permanent(
            &cards,
            1,
            "Artificer's Assistant",
            false,
            false,
        )]),
        ..TrueState::default()
    };
    apply_action(
        &mut artifact_cast,
        &cards,
        Action::CastFromHand {
            card: crypt,
            payment: ManaPayment::default(),
        },
    )
    .unwrap();
    assert!(artifact_cast.stack.iter().any(|object| matches!(
        object,
        StackObject::ControlledTrigger {
            ability: ABILITY_ARTIFICERS_ASSISTANT_SCRY,
            ..
        }
    )));

    let scroll_payment = payment_for(&cards, "Merchant Scroll");
    let mut nonhistoric_cast = TrueState {
        turn: 1,
        phase: Phase::PrecombatMain,
        window: Window::Priority,
        hand: CardZone::new(vec![scroll]),
        battlefield: BattlefieldZone::new(vec![permanent(
            &cards,
            2,
            "Artificer's Assistant",
            false,
            false,
        )]),
        mana: pool_for(scroll_payment),
        ..TrueState::default()
    };
    apply_action(
        &mut nonhistoric_cast,
        &cards,
        Action::CastFromHand {
            card: scroll,
            payment: scroll_payment,
        },
    )
    .unwrap();
    assert!(!nonhistoric_cast.stack.iter().any(|object| matches!(
        object,
        StackObject::ControlledTrigger {
            ability: ABILITY_ARTIFICERS_ASSISTANT_SCRY,
            ..
        }
    )));

    let mut saga_play = TrueState {
        turn: 1,
        phase: Phase::PrecombatMain,
        window: Window::Priority,
        hand: CardZone::new(vec![saga]),
        battlefield: BattlefieldZone::new(vec![permanent(
            &cards,
            3,
            "Artificer's Assistant",
            false,
            false,
        )]),
        ..TrueState::default()
    };
    apply_action(
        &mut saga_play,
        &cards,
        Action::PlayLand {
            card: saga,
            entry: LandEntryChoice::Default,
        },
    )
    .unwrap();
    assert!(!saga_play.stack.iter().any(|object| matches!(
        object,
        StackObject::ControlledTrigger {
            ability: ABILITY_ARTIFICERS_ASSISTANT_SCRY,
            ..
        }
    )));

    assert_eq!(cards.printed_power(assistant), Some(1));
}

#[test]
fn chrome_dome_other_another_copy_haste_and_characteristics_are_exact() {
    let cards = CurrentCardDatabase::load().unwrap();
    let mut power_state = TrueState {
        turn: 1,
        phase: Phase::PrecombatMain,
        window: Window::Priority,
        battlefield: BattlefieldZone::new(vec![
            permanent(&cards, 10, "Chrome Dome", false, false),
            permanent(&cards, 11, "Battered Golem", false, false),
            permanent(&cards, 12, "Uthros Research Craft", false, false),
        ]),
        ..TrueState::default()
    };
    let chrome_target = canonical_for(&power_state, ObjectId(10));
    apply_action(
        &mut power_state,
        &cards,
        Action::ActivateUthrosStation {
            source: ObjectId(12),
            creature: chrome_target,
        },
    )
    .unwrap();
    apply_action(&mut power_state, &cards, Action::PassPriority).unwrap();
    assert_eq!(
        power_state
            .battlefield
            .get(ObjectId(12))
            .unwrap()
            .counters
            .charge,
        1,
        "Chrome Dome must not apply its 'other artifact creatures' bonus to itself"
    );

    let mut copy_state = TrueState {
        turn: 1,
        phase: Phase::PrecombatMain,
        window: Window::Priority,
        battlefield: BattlefieldZone::new(vec![
            permanent(&cards, 20, "Chrome Dome", false, false),
            permanent(&cards, 21, "Mana Vault", false, false),
        ]),
        mana: ManaPool {
            colorless: 5,
            ..ManaPool::default()
        },
        ..TrueState::default()
    };
    let self_target = canonical_for(&copy_state, ObjectId(20));
    assert!(
        apply_action(
            &mut copy_state,
            &cards,
            Action::ActivateChromeDome {
                source: ObjectId(20),
                target: self_target,
                payment: ManaPayment {
                    colorless: 5,
                    ..ManaPayment::default()
                },
            },
        )
        .is_err(),
        "Chrome Dome says another target artifact"
    );

    let vault_target = canonical_for(&copy_state, ObjectId(21));
    apply_action(
        &mut copy_state,
        &cards,
        Action::ActivateChromeDome {
            source: ObjectId(20),
            target: vault_target,
            payment: ManaPayment {
                colorless: 5,
                ..ManaPayment::default()
            },
        },
    )
    .unwrap();
    apply_action(&mut copy_state, &cards, Action::PassPriority).unwrap();
    let copied_vault = copy_state
        .battlefield
        .permanents()
        .iter()
        .find(|permanent| permanent.card == card(&cards, "Mana Vault") && permanent.token)
        .unwrap()
        .object_id;
    assert!(
        !copy_state
            .battlefield
            .get(copied_vault)
            .unwrap()
            .summoning_sick
    );
    apply_action(
        &mut copy_state,
        &cards,
        Action::ActivateManaAbility {
            source: copied_vault,
        },
    )
    .unwrap();
    assert_eq!(copy_state.mana.colorless, 3);
    assert!(copy_state.delayed_events.iter().any(|event| matches!(
        event,
        urza_core::DelayedEvent::ChromeCopySacrifice { object, .. } if *object == copied_vault
    )));
}

#[test]
fn valley_floodcaller_flash_and_tribal_trigger_clauses_are_exact() {
    let cards = CurrentCardDatabase::load().unwrap();
    let scroll = card(&cards, "Merchant Scroll");
    let scroll_payment = payment_for(&cards, "Merchant Scroll");
    let mut state = TrueState {
        turn: 1,
        phase: Phase::EndStep,
        window: Window::Priority,
        hand: CardZone::new(vec![scroll]),
        battlefield: BattlefieldZone::new(vec![
            permanent(&cards, 30, "Valley Floodcaller", true, false),
            permanent(&cards, 31, "Artificer's Assistant", true, false),
            permanent(&cards, 32, "Battered Golem", true, false),
        ]),
        mana: pool_for(scroll_payment),
        ..TrueState::default()
    };
    apply_action(
        &mut state,
        &cards,
        Action::CastFromHand {
            card: scroll,
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
    for object in [ObjectId(30), ObjectId(31)] {
        let permanent = state.battlefield.get(object).unwrap();
        assert!(!permanent.tapped);
        assert_eq!(permanent.counters.temporary_power_boost, 1);
    }
    let golem = state.battlefield.get(ObjectId(32)).unwrap();
    assert!(golem.tapped);
    assert_eq!(golem.counters.temporary_power_boost, 0);

    let mut chip = permanent(&cards, 40, "The Reality Chip", false, false);
    chip.mode = PermanentMode::RealityChipAttached;
    chip.attached_to = Some(ObjectId(41));
    let mut top_cast = TrueState {
        turn: 1,
        phase: Phase::EndStep,
        window: Window::Priority,
        library: TrueLibrary::new(
            vec![scroll],
            LibraryKnowledge {
                known_top: 1,
                known_bottom: 0,
            },
        )
        .unwrap(),
        battlefield: BattlefieldZone::new(vec![
            permanent(&cards, 39, "Valley Floodcaller", false, false),
            chip,
            permanent(&cards, 41, "Battered Golem", false, false),
        ]),
        mana: pool_for(scroll_payment),
        ..TrueState::default()
    };
    apply_action(
        &mut top_cast,
        &cards,
        Action::CastLibraryTop {
            card: scroll,
            payment: scroll_payment,
        },
    )
    .unwrap();

    let sol_ring = card(&cards, "Sol Ring");
    let mut cleanup = TrueState {
        turn: 1,
        phase: Phase::EndStep,
        window: Window::Priority,
        hand: CardZone::new(vec![sol_ring]),
        battlefield: BattlefieldZone::new(vec![permanent(
            &cards,
            70,
            "Valley Floodcaller",
            true,
            false,
        )]),
        mana: ManaPool {
            colorless: 1,
            ..ManaPool::default()
        },
        ..TrueState::default()
    };
    apply_action(
        &mut cleanup,
        &cards,
        Action::CastFromHand {
            card: sol_ring,
            payment: ManaPayment {
                colorless: 1,
                ..ManaPayment::default()
            },
        },
    )
    .unwrap();
    apply_action(&mut cleanup, &cards, Action::PassPriority).unwrap();
    assert_eq!(
        cleanup
            .battlefield
            .get(ObjectId(70))
            .unwrap()
            .counters
            .temporary_power_boost,
        1
    );
    apply_action(&mut cleanup, &cards, Action::PassPriority).unwrap();
    advance_phase(&mut cleanup, &cards).unwrap();
    assert_eq!(
        cleanup
            .battlefield
            .get(ObjectId(70))
            .unwrap()
            .counters
            .temporary_power_boost,
        0
    );
}

#[test]
fn knack_and_helix_grants_obey_tap_readiness_nonland_targeting_and_eot_expiry() {
    let cards = CurrentCardDatabase::load().unwrap();

    for spell_name in ["Banishing Knack", "Retraction Helix"] {
        let spell = card(&cards, spell_name);
        let payment = payment_for(&cards, spell_name);
        let mut sick_state = TrueState {
            turn: 1,
            phase: Phase::PrecombatMain,
            window: Window::Priority,
            hand: CardZone::new(vec![spell]),
            battlefield: BattlefieldZone::new(vec![
                permanent(&cards, 50, "Battered Golem", false, true),
                permanent(&cards, 51, "Basalt Monolith", false, false),
            ]),
            mana: pool_for(payment),
            ..TrueState::default()
        };
        let creature = canonical_for(&sick_state, ObjectId(50));
        apply_action(
            &mut sick_state,
            &cards,
            Action::CastTargetedFromHand {
                card: spell,
                target: creature,
                payment,
            },
        )
        .unwrap();
        apply_action(&mut sick_state, &cards, Action::PassPriority).unwrap();
        let basalt = canonical_for(&sick_state, ObjectId(51));
        assert!(
            apply_action(
                &mut sick_state,
                &cards,
                Action::ActivateGrantedKnackBounce {
                    source: ObjectId(50),
                    target: basalt,
                },
            )
            .is_err(),
            "the granted tap ability must respect summoning sickness"
        );

        let mut ready_state = TrueState {
            turn: 1,
            phase: Phase::EndStep,
            window: Window::Priority,
            hand: CardZone::new(vec![spell]),
            battlefield: BattlefieldZone::new(vec![
                permanent(&cards, 60, "Battered Golem", false, false),
                permanent(&cards, 61, "Basalt Monolith", false, false),
                permanent(&cards, 62, "Island", false, false),
            ]),
            mana: pool_for(payment),
            ..TrueState::default()
        };
        let creature = canonical_for(&ready_state, ObjectId(60));
        apply_action(
            &mut ready_state,
            &cards,
            Action::CastTargetedFromHand {
                card: spell,
                target: creature,
                payment,
            },
        )
        .unwrap();
        apply_action(&mut ready_state, &cards, Action::PassPriority).unwrap();
        assert_eq!(
            ready_state
                .battlefield
                .get(ObjectId(60))
                .unwrap()
                .granted_ability,
            Some(GrantedAbility::KnackBounceUntilEndOfTurn)
        );
        let island = canonical_for(&ready_state, ObjectId(62));
        assert!(
            apply_action(
                &mut ready_state,
                &cards,
                Action::ActivateGrantedKnackBounce {
                    source: ObjectId(60),
                    target: island,
                },
            )
            .is_err(),
            "the granted ability can target only nonland permanents"
        );

        advance_phase(&mut ready_state, &cards).unwrap();
        assert_eq!(
            ready_state
                .battlefield
                .get(ObjectId(60))
                .unwrap()
                .granted_ability,
            None
        );
    }
}
