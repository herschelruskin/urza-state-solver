use urza_cards::CurrentCardDatabase;
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
        battlefield: BattlefieldZone::new(vec![permanent(&cards, 1, "Valley Floodcaller", false)]),
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
