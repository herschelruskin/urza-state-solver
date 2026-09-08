use urza_cards::CurrentCardDatabase;
use urza_core::{
    BattlefieldZone, CardZone, CounterState, ManaPool, ObjectId, PermanentMode, PermanentState,
    Phase, TrueLibrary, TrueState, Window,
};
use urza_policy_bridge::CandidateBridge;
use urza_rules::{Action, CardDatabase, ManaPayment, apply_action};

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

fn has_payment_candidate<F>(bridge: &CandidateBridge, mut matches_action: F) -> bool
where
    F: FnMut(&Action) -> bool,
{
    bridge
        .candidates()
        .iter()
        .filter_map(|candidate| bridge.resolve(candidate.token))
        .any(&mut matches_action)
}

#[test]
fn gadgeteer_reduced_basalt_untap_and_top_floor_are_solver_visible() {
    let cards = CurrentCardDatabase::load().unwrap();
    let basalt_state = state_with(
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
    let basalt_bridge = CandidateBridge::build(&basalt_state, &cards).unwrap();
    assert!(has_payment_candidate(&basalt_bridge, |action| {
        matches!(
            action,
            Action::ActivateNativeArtifactUntap { source, payment }
                if *source == ObjectId(1)
                    && *payment == ManaPayment {
                        colorless: 2,
                        ..ManaPayment::default()
                    }
        )
    }));
    assert!(!has_payment_candidate(&basalt_bridge, |action| {
        matches!(
            action,
            Action::ActivateNativeArtifactUntap { source, payment }
                if *source == ObjectId(1) && payment.colorless < 2
        )
    }));

    let top_state = state_with(
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
    let top_bridge = CandidateBridge::build(&top_state, &cards).unwrap();
    assert!(has_payment_candidate(&top_bridge, |action| {
        matches!(
            action,
            Action::ActivateTopLook { source, payment }
                if *source == ObjectId(10)
                    && *payment == ManaPayment {
                        colorless: 1,
                        ..ManaPayment::default()
                    }
        )
    }));
    assert!(!has_payment_candidate(&top_bridge, |action| {
        matches!(
            action,
            Action::ActivateTopLook { source, payment }
                if *source == ObjectId(10) && *payment == ManaPayment::default()
        )
    }));
}

#[test]
fn gadgeteer_investigate_produces_a_solver_visible_clue_draw() {
    let cards = CurrentCardDatabase::load().unwrap();
    let crypt = card(&cards, "Tormod's Crypt");
    let mut state = state_with(
        &cards,
        vec![permanent(&cards, 1, "Forensic Gadgeteer", false)],
        &["Tormod's Crypt"],
        &["Island"],
        ManaPool::default(),
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

    let clue_card = cards.clue_token_card().unwrap();
    let clue = state
        .battlefield
        .permanents()
        .iter()
        .find(|permanent| permanent.card == clue_card)
        .unwrap()
        .object_id;
    state.mana = ManaPool {
        colorless: 2,
        ..ManaPool::default()
    };
    let clue_bridge = CandidateBridge::build(&state, &cards).unwrap();
    let draw = clue_bridge
        .candidates()
        .iter()
        .find_map(|candidate| match clue_bridge.resolve(candidate.token) {
            Some(Action::ActivateClueDraw { source, payment })
                if *source == clue
                    && *payment
                        == ManaPayment {
                            colorless: 2,
                            ..ManaPayment::default()
                        } =>
            {
                clue_bridge.resolved_action(candidate.token)
            }
            _ => None,
        })
        .unwrap();

    apply_action(&mut state, &cards, draw).unwrap();
    apply_action(&mut state, &cards, Action::PassPriority).unwrap();
    assert!(state.hand.cards().contains(&card(&cards, "Island")));
}
