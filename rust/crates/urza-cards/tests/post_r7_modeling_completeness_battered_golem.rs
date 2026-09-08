use urza_cards::CurrentCardDatabase;
use urza_core::{
    BattlefieldZone, CardZone, CounterState, ManaPool, ObjectId, PendingDecision, PermanentMode,
    PermanentState, Phase, StackObject, TrueLibrary, TrueState, Window,
};
use urza_rules::{
    ABILITY_ARTIFACT_ENTRY_UNTAP, Action, EngineKind, ManaCost, ManaPayment, R2CardRole,
    advance_phase, apply_action,
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
    mana: ManaPool,
) -> TrueState {
    let state = TrueState {
        turn: 1,
        phase: Phase::PrecombatMain,
        window: Window::Priority,
        hand: CardZone::new(hand.iter().map(|name| card(cards, name)).collect()),
        library: TrueLibrary::unknown(Vec::new()),
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
fn battered_golem_profile_and_normal_untap_restriction_are_executable() {
    let cards = CurrentCardDatabase::load().unwrap();
    let golem = card(&cards, "Battered Golem");
    let profile = cards.profile(golem).unwrap();
    assert_eq!(profile.role, R2CardRole::CreaturePermanent);
    assert_eq!(profile.engine, EngineKind::BatteredGolem);
    assert!(profile.is_artifact);
    assert!(profile.is_creature);
    assert!(profile.skip_normal_untap);
    assert_eq!(
        profile.mana_cost,
        Some(ManaCost {
            generic: 3,
            ..ManaCost::default()
        })
    );

    let mut state = state_with(
        &cards,
        vec![permanent(&cards, 1, "Battered Golem", true)],
        &[],
        ManaPool::default(),
    );
    state.turn = 2;
    state.phase = Phase::Untap;
    state.window = Window::None;
    state.validate().unwrap();
    advance_phase(&mut state, &cards).unwrap();
    assert_eq!(state.phase, Phase::Upkeep);
    assert!(state.battlefield.get(ObjectId(1)).unwrap().tapped);
}

#[test]
fn artifact_entry_creates_the_optional_battered_golem_untap_choice() {
    let cards = CurrentCardDatabase::load().unwrap();
    let mut state = state_with(
        &cards,
        vec![permanent(&cards, 1, "Battered Golem", true)],
        &["Tormod's Crypt"],
        ManaPool::default(),
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
    apply_action(&mut state, &cards, Action::PassPriority).unwrap();
    assert!(matches!(
        state.stack.last(),
        Some(StackObject::ControlledTrigger {
            ability: ABILITY_ARTIFACT_ENTRY_UNTAP,
            ..
        })
    ));
    apply_action(&mut state, &cards, Action::PassPriority).unwrap();
    assert!(matches!(
        state.pending,
        PendingDecision::ProducerUntapChoice { .. }
    ));

    let mut decline = state.clone();
    apply_action(
        &mut decline,
        &cards,
        Action::ChooseProducerUntap { untap: false },
    )
    .unwrap();
    assert!(decline.battlefield.get(ObjectId(1)).unwrap().tapped);

    apply_action(
        &mut state,
        &cards,
        Action::ChooseProducerUntap { untap: true },
    )
    .unwrap();
    assert!(!state.battlefield.get(ObjectId(1)).unwrap().tapped);
}

#[test]
fn nonartifact_entry_does_not_trigger_battered_golem() {
    let cards = CurrentCardDatabase::load().unwrap();
    let payment = payment_for(&cards, "Forensic Gadgeteer");
    let mut state = state_with(
        &cards,
        vec![permanent(&cards, 1, "Battered Golem", true)],
        &["Forensic Gadgeteer"],
        pool_for(payment),
    );
    apply_action(
        &mut state,
        &cards,
        Action::CastFromHand {
            card: card(&cards, "Forensic Gadgeteer"),
            payment,
        },
    )
    .unwrap();
    apply_action(&mut state, &cards, Action::PassPriority).unwrap();
    assert!(state.stack.is_empty());
    assert!(matches!(state.pending, PendingDecision::None));
    assert!(state.battlefield.get(ObjectId(1)).unwrap().tapped);
}

#[test]
fn battered_golem_itself_casts_and_enters_as_an_artifact_creature() {
    let cards = CurrentCardDatabase::load().unwrap();
    let payment = payment_for(&cards, "Battered Golem");
    let mut state = state_with(&cards, Vec::new(), &["Battered Golem"], pool_for(payment));
    apply_action(
        &mut state,
        &cards,
        Action::CastFromHand {
            card: card(&cards, "Battered Golem"),
            payment,
        },
    )
    .unwrap();
    apply_action(&mut state, &cards, Action::PassPriority).unwrap();
    let golem = state
        .battlefield
        .permanents()
        .iter()
        .find(|permanent| permanent.card == card(&cards, "Battered Golem"))
        .unwrap();
    assert!(!golem.tapped);
    assert!(matches!(
        state.stack.last(),
        Some(StackObject::ControlledTrigger {
            ability: ABILITY_ARTIFACT_ENTRY_UNTAP,
            ..
        })
    ));
    apply_action(&mut state, &cards, Action::PassPriority).unwrap();
    assert!(matches!(state.pending, PendingDecision::None));
}
