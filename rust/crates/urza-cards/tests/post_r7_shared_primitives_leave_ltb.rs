use urza_cards::CurrentCardDatabase;
use urza_core::{
    BattlefieldZone, CardZone, CounterState, DelayedEvent, ManaPool, ObjectId, PendingDecision,
    PermanentMode, PermanentState, Phase, StackObject, TrueLibrary, TrueState, Window,
};
use urza_info::observe;
use urza_rules::{
    ABILITY_CAM_TAP_UNTAP, ABILITY_CLUE_DRAW, Action, CardDatabase, ManaPayment, UtilityKind,
    apply_action,
};

fn card(cards: &CurrentCardDatabase, name: &str) -> urza_core::CardDefId {
    cards.card_id_by_name(name).unwrap()
}

fn permanent(cards: &CurrentCardDatabase, object: u32, name: &str) -> PermanentState {
    let id = card(cards, name);
    let profile = cards.profile(id).unwrap();
    PermanentState {
        object_id: ObjectId(object),
        card: id,
        face: profile.battlefield_face,
        tapped: false,
        summoning_sick: false,
        token: false,
        counters: CounterState::default(),
        mode: match profile.utility {
            UtilityKind::RealityChip => PermanentMode::RealityChipCreature,
            _ => PermanentMode::Normal,
        },
        attached_to: None,
        granted_ability: None,
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

#[test]
fn attached_clue_sacrifice_uses_common_leave_cleanup() {
    let cards = CurrentCardDatabase::load().unwrap();
    let clue = cards.clue_token_card().unwrap();
    let clue_profile = cards.profile(clue).unwrap();
    let mut power = permanent(&cards, 2, "Power Artifact");
    power.attached_to = Some(ObjectId(1));
    let mut state = TrueState {
        turn: 1,
        phase: Phase::PrecombatMain,
        window: Window::Priority,
        library: TrueLibrary::unknown(vec![card(&cards, "Island")]),
        battlefield: BattlefieldZone::new(vec![
            PermanentState {
                object_id: ObjectId(1),
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
            power,
        ]),
        mana: ManaPool {
            colorless: 2,
            ..ManaPool::default()
        },
        ..TrueState::default()
    };
    state.validate().unwrap();

    apply_action(
        &mut state,
        &cards,
        Action::ActivateClueDraw {
            source: ObjectId(1),
            payment: ManaPayment {
                colorless: 2,
                ..ManaPayment::default()
            },
        },
    )
    .unwrap();

    assert!(state.battlefield.get(ObjectId(1)).is_none());
    assert!(state.battlefield.get(ObjectId(2)).is_none());
    assert!(
        state
            .graveyard
            .cards()
            .contains(&card(&cards, "Power Artifact"))
    );
    assert!(!state.graveyard.cards().contains(&clue));
    assert!(matches!(
        state.stack.last(),
        Some(StackObject::ActivatedAbility {
            ability: ABILITY_CLUE_DRAW,
            ..
        })
    ));

    apply_action(&mut state, &cards, Action::PassPriority).unwrap();
    assert!(state.hand.cards().contains(&card(&cards, "Island")));
}

#[test]
fn transmute_cam_ltb_is_typed_and_deferred_while_search_resolution_is_active() {
    let cards = CurrentCardDatabase::load().unwrap();
    let transmute = card(&cards, "Transmute Artifact");
    let cam = card(&cards, "Sewer-veillance Cam");
    let payment = payment_for(&cards, "Transmute Artifact");
    let mut state = TrueState {
        turn: 1,
        phase: Phase::PrecombatMain,
        window: Window::Priority,
        hand: CardZone::new(vec![transmute]),
        library: TrueLibrary::unknown(vec![card(&cards, "Tormod's Crypt")]),
        battlefield: BattlefieldZone::new(vec![
            permanent(&cards, 10, "Sewer-veillance Cam"),
            permanent(&cards, 11, "Battered Golem"),
        ]),
        mana: pool_for(payment),
        ..TrueState::default()
    };
    state.validate().unwrap();

    apply_action(
        &mut state,
        &cards,
        Action::CastFromHand {
            card: transmute,
            payment,
        },
    )
    .unwrap();
    apply_action(&mut state, &cards, Action::PassPriority).unwrap();
    assert!(matches!(
        state.pending,
        PendingDecision::TransmuteSacrifice { .. }
    ));

    let cam_target = canonical_for(&state, ObjectId(10));
    apply_action(
        &mut state,
        &cards,
        Action::ChooseTransmuteSacrifice {
            artifact: cam_target,
        },
    )
    .unwrap();

    assert!(matches!(state.pending, PendingDecision::TransmuteTarget { .. }));
    assert_eq!(state.window, Window::PostObservation);
    assert!(state.battlefield.get(ObjectId(10)).is_none());
    assert!(state.graveyard.cards().contains(&cam));
    assert!(!state.stack.iter().any(|object| matches!(
        object,
        StackObject::ControlledTrigger {
            ability: ABILITY_CAM_TAP_UNTAP,
            ..
        }
    )));
    assert!(state.delayed_events.iter().any(|event| matches!(
        event,
        DelayedEvent::DeferredControlledTrigger {
            ability: ABILITY_CAM_TAP_UNTAP,
            ..
        }
    )));
}
