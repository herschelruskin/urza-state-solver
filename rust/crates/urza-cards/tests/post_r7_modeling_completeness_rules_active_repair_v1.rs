use urza_cards::CurrentCardDatabase;
use urza_core::{
    BattlefieldZone, CardZone, CounterState, DelayedEvent, ManaPool, ObjectId, PendingDecision,
    PermanentMode, PermanentState, Phase, StackObject, TrueLibrary, TrueState, Window,
};
use urza_info::observe;
use urza_rules::{
    ABILITY_ARTIFICERS_ASSISTANT_SCRY, ABILITY_FLOODCALLER_UNTAP, Action, EngineKind, ManaPayment,
    R2CardRole, UtilityKind, advance_phase, apply_action,
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
            urza_info::resolve_canonical_object(state, permanent.canonical_id).unwrap()
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
    assert_eq!(
        cards.profile(chrome).unwrap().engine,
        EngineKind::ChromeDome
    );

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
    let battered_target = canonical_for(&power_state, ObjectId(2));
    apply_action(
        &mut power_state,
        &cards,
        Action::ActivateUthrosStation {
            source: ObjectId(3),
            creature: battered_target,
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
    let copy_target = canonical_for(&copy_state, ObjectId(11));
    apply_action(
        &mut copy_state,
        &cards,
        Action::ActivateChromeDome {
            source: ObjectId(10),
            target: copy_target,
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
    let sacrifice_target = canonical_for(&sacrifice_state, ObjectId(2));
    apply_action(
        &mut sacrifice_state,
        &cards,
        Action::ActivateGrindingStation {
            source: ObjectId(1),
            sacrifice: sacrifice_target,
        },
    )
    .unwrap();
    assert!(
        sacrifice_state
            .graveyard
            .cards()
            .contains(&card(&cards, "Basalt Monolith"))
    );
    assert!(
        sacrifice_state
            .graveyard
            .cards()
            .contains(&card(&cards, "Power Artifact"))
    );

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
        let grant_target = canonical_for(&state, ObjectId(11));
        apply_action(
            &mut state,
            &cards,
            Action::CastTargetedFromHand {
                card: card(&cards, spell),
                target: grant_target,
                payment,
            },
        )
        .unwrap();
        apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        let bounce_target = canonical_for(&state, ObjectId(12));
        apply_action(
            &mut state,
            &cards,
            Action::ActivateGrantedKnackBounce {
                source: ObjectId(11),
                target: bounce_target,
            },
        )
        .unwrap();
        apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        assert!(
            state
                .hand
                .cards()
                .contains(&card(&cards, "Basalt Monolith"))
        );
        assert!(
            state
                .graveyard
                .cards()
                .contains(&card(&cards, "Power Artifact"))
        );
    }
}
