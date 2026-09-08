use urza_cards::CurrentCardDatabase;
use urza_core::{
    BattlefieldZone, CardZone, CounterState, ManaPool, ObjectId, PermanentMode, PermanentState,
    Phase, StackObject, TrueLibrary, TrueState, Window,
};
use urza_rules::{
    ABILITY_GADGETEER_INVESTIGATE, Action, CardDatabase, EngineKind, ManaCost, ManaPayment,
    R2CardRole, UtilityKind, apply_action,
};

fn card(cards: &CurrentCardDatabase, name: &str) -> urza_core::CardDefId {
    cards.card_id_by_name(name).unwrap()
}

fn permanent(cards: &CurrentCardDatabase, object: u32, name: &str, tapped: bool) -> PermanentState {
    let card = card(cards, name);
    let profile = cards.profile(card).unwrap();
    PermanentState {
        object_id: ObjectId(object),
        card,
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

fn state_with(
    cards: &CurrentCardDatabase,
    permanents: Vec<PermanentState>,
    hand: &[&str],
    library: &[&str],
    mana: ManaPool,
) -> TrueState {
    let state = TrueState {
        turn: 1,
        phase: Phase::PrecombatMain,
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

#[test]
fn forensic_gadgeteer_profile_and_artifact_cast_investigate_are_executable() {
    let cards = CurrentCardDatabase::load().unwrap();
    let gadgeteer = card(&cards, "Forensic Gadgeteer");
    let profile = cards.profile(gadgeteer).unwrap();
    assert_eq!(profile.role, R2CardRole::CreaturePermanent);
    assert_eq!(profile.engine, EngineKind::ForensicGadgeteer);
    assert_eq!(profile.artifact_activation_reduction, 1);
    assert!(profile.is_creature);
    assert_eq!(
        profile.mana_cost,
        Some(ManaCost {
            blue: 1,
            generic: 2,
            ..ManaCost::default()
        })
    );

    let gadgeteer_payment = payment_for(&cards, "Forensic Gadgeteer");
    let mut state = state_with(
        &cards,
        Vec::new(),
        &["Forensic Gadgeteer", "Tormod's Crypt"],
        &["Island"],
        pool_for(gadgeteer_payment),
    );
    apply_action(
        &mut state,
        &cards,
        Action::CastFromHand {
            card: gadgeteer,
            payment: gadgeteer_payment,
        },
    )
    .unwrap();
    apply_action(&mut state, &cards, Action::PassPriority).unwrap();
    assert!(
        state
            .battlefield
            .permanents()
            .iter()
            .any(|permanent| permanent.card == gadgeteer)
    );

    let crypt = card(&cards, "Tormod's Crypt");
    apply_action(
        &mut state,
        &cards,
        Action::CastFromHand {
            card: crypt,
            payment: ManaPayment::default(),
        },
    )
    .unwrap();
    assert!(matches!(
        state.stack.last(),
        Some(StackObject::ControlledTrigger {
            ability: ABILITY_GADGETEER_INVESTIGATE,
            ..
        })
    ));

    apply_action(&mut state, &cards, Action::PassPriority).unwrap();
    let clue_card = cards.clue_token_card().unwrap();
    let clue = state
        .battlefield
        .permanents()
        .iter()
        .find(|permanent| permanent.card == clue_card)
        .unwrap()
        .object_id;
    assert!(state.battlefield.get(clue).unwrap().token);
    assert!(cards.profile(clue_card).unwrap().is_artifact);

    apply_action(&mut state, &cards, Action::PassPriority).unwrap();
    state.mana = ManaPool {
        colorless: 1,
        ..ManaPool::default()
    };
    apply_action(
        &mut state,
        &cards,
        Action::ActivateClueDraw {
            source: clue,
            payment: ManaPayment {
                colorless: 1,
                ..ManaPayment::default()
            },
        },
    )
    .unwrap();
    assert!(state.battlefield.get(clue).is_none());
    apply_action(&mut state, &cards, Action::PassPriority).unwrap();
    assert!(state.hand.cards().contains(&card(&cards, "Island")));
}

#[test]
fn forensic_gadgeteer_does_not_investigate_for_a_nonartifact_spell() {
    let cards = CurrentCardDatabase::load().unwrap();
    let spellseeker_payment = payment_for(&cards, "Spellseeker");
    let mut state = state_with(
        &cards,
        vec![permanent(&cards, 1, "Forensic Gadgeteer", false)],
        &["Spellseeker"],
        &[],
        pool_for(spellseeker_payment),
    );
    apply_action(
        &mut state,
        &cards,
        Action::CastFromHand {
            card: card(&cards, "Spellseeker"),
            payment: spellseeker_payment,
        },
    )
    .unwrap();
    assert_eq!(state.stack.len(), 1);
    assert!(matches!(
        state.stack.last(),
        Some(StackObject::Spell { .. })
    ));
}

#[test]
fn forensic_gadgeteer_reduces_artifact_activations_but_respects_the_one_mana_floor() {
    let cards = CurrentCardDatabase::load().unwrap();
    let mut basalt_state = state_with(
        &cards,
        vec![
            permanent(&cards, 1, "Basalt Monolith", true),
            permanent(&cards, 2, "Forensic Gadgeteer", false),
        ],
        &[],
        &[],
        ManaPool {
            colorless: 2,
            ..ManaPool::default()
        },
    );
    let basalt = ObjectId(1);
    let mut short = basalt_state.clone();
    short.mana.colorless = 1;
    assert!(
        apply_action(
            &mut short,
            &cards,
            Action::ActivateNativeArtifactUntap {
                source: basalt,
                payment: ManaPayment {
                    colorless: 1,
                    ..ManaPayment::default()
                },
            },
        )
        .is_err()
    );
    apply_action(
        &mut basalt_state,
        &cards,
        Action::ActivateNativeArtifactUntap {
            source: basalt,
            payment: ManaPayment {
                colorless: 2,
                ..ManaPayment::default()
            },
        },
    )
    .unwrap();
    apply_action(&mut basalt_state, &cards, Action::PassPriority).unwrap();
    assert!(!basalt_state.battlefield.get(basalt).unwrap().tapped);

    let mut top_state = state_with(
        &cards,
        vec![
            permanent(&cards, 10, "Sensei's Divining Top", false),
            permanent(&cards, 11, "Forensic Gadgeteer", false),
        ],
        &[],
        &["Island"],
        ManaPool {
            colorless: 1,
            ..ManaPool::default()
        },
    );
    let mut zero = top_state.clone();
    assert!(
        apply_action(
            &mut zero,
            &cards,
            Action::ActivateTopLook {
                source: ObjectId(10),
                payment: ManaPayment::default(),
            },
        )
        .is_err()
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
}

#[test]
fn forensic_gadgeteer_does_not_change_nonartifact_activation_costs() {
    let cards = CurrentCardDatabase::load().unwrap();
    let gadgeteer = cards.profile(card(&cards, "Forensic Gadgeteer")).unwrap();
    assert_eq!(gadgeteer.engine, EngineKind::ForensicGadgeteer);
    assert_ne!(gadgeteer.utility, UtilityKind::SenseisDiviningTop);
}
