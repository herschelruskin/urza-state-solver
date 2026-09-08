use urza_cards::CurrentCardDatabase;
use urza_core::{
    BattlefieldZone, CardZone, CounterState, ManaPool, ObjectId, PermanentMode, PermanentState,
    Phase, TrueLibrary, TrueState, Window,
};
use urza_policy::PolicyActionClass;
use urza_policy_bridge::CandidateBridge;
use urza_rules::{Action, ManaPayment, apply_action};

fn card(cards: &CurrentCardDatabase, name: &str) -> urza_core::CardDefId {
    cards.card_id_by_name(name).unwrap()
}

fn permanent(
    cards: &CurrentCardDatabase,
    object: u32,
    name: &str,
    tapped: bool,
) -> PermanentState {
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
) -> TrueState {
    let state = TrueState {
        turn: 1,
        phase: Phase::PrecombatMain,
        window: Window::Priority,
        hand: CardZone::new(hand.iter().map(|name| card(cards, name)).collect()),
        library: TrueLibrary::unknown(Vec::new()),
        battlefield: BattlefieldZone::new(permanents),
        mana: ManaPool::default(),
        ..TrueState::default()
    };
    state.validate().unwrap();
    state
}

#[test]
fn battered_golem_artifact_entry_choice_is_public_and_solver_visible() {
    let cards = CurrentCardDatabase::load().unwrap();
    let crypt = card(&cards, "Tormod's Crypt");
    let mut state = state_with(
        &cards,
        vec![permanent(&cards, 1, "Battered Golem", true)],
        &["Tormod's Crypt"],
    );

    let cast_bridge = CandidateBridge::build(&state, &cards).unwrap();
    let cast = cast_bridge
        .candidates()
        .iter()
        .find_map(|candidate| match cast_bridge.resolve(candidate.token) {
            Some(Action::CastFromHand { card, payment })
                if *card == crypt && *payment == ManaPayment::default() =>
            {
                cast_bridge.resolved_action(candidate.token)
            }
            _ => None,
        })
        .unwrap();
    apply_action(&mut state, &cards, cast).unwrap();
    apply_action(&mut state, &cards, Action::PassPriority).unwrap();
    apply_action(&mut state, &cards, Action::PassPriority).unwrap();

    let choice_bridge = CandidateBridge::build(&state, &cards).unwrap();
    assert_eq!(choice_bridge.candidates().len(), 2);
    assert!(
        choice_bridge
            .candidates()
            .iter()
            .all(|candidate| candidate.class == PolicyActionClass::ContingentDecision)
    );
    assert!(choice_bridge.candidates().iter().any(|candidate| {
        matches!(
            choice_bridge.resolve(candidate.token),
            Some(Action::ChooseProducerUntap { untap: true })
        )
    }));
    assert!(choice_bridge.candidates().iter().any(|candidate| {
        matches!(
            choice_bridge.resolve(candidate.token),
            Some(Action::ChooseProducerUntap { untap: false })
        )
    }));
}

#[test]
fn battered_golem_decline_and_accept_candidates_resolve_to_distinct_public_actions() {
    let cards = CurrentCardDatabase::load().unwrap();
    let mut state = state_with(
        &cards,
        vec![permanent(&cards, 1, "Battered Golem", true)],
        &["Tormod's Crypt"],
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
    apply_action(&mut state, &cards, Action::PassPriority).unwrap();

    let bridge = CandidateBridge::build(&state, &cards).unwrap();
    let accept = bridge
        .candidates()
        .iter()
        .find(|candidate| {
            matches!(
                bridge.resolve(candidate.token),
                Some(Action::ChooseProducerUntap { untap: true })
            )
        })
        .unwrap();
    let decline = bridge
        .candidates()
        .iter()
        .find(|candidate| {
            matches!(
                bridge.resolve(candidate.token),
                Some(Action::ChooseProducerUntap { untap: false })
            )
        })
        .unwrap();
    assert_ne!(accept.key, decline.key);

    let mut accepted = state.clone();
    apply_action(
        &mut accepted,
        &cards,
        bridge.resolved_action(accept.token).unwrap(),
    )
    .unwrap();
    assert!(!accepted.battlefield.get(ObjectId(1)).unwrap().tapped);

    apply_action(
        &mut state,
        &cards,
        bridge.resolved_action(decline.token).unwrap(),
    )
    .unwrap();
    assert!(state.battlefield.get(ObjectId(1)).unwrap().tapped);
}
