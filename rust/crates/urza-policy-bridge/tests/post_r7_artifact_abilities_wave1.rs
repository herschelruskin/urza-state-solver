use urza_cards::CurrentCardDatabase;
use urza_core::{
    BattlefieldZone, CounterState, ManaPool, ObjectId, PermanentMode, PermanentState, Phase,
    TrueState, Window,
};
use urza_policy_bridge::CandidateBridge;
use urza_rules::{Action, CardDatabase};

fn card(cards: &CurrentCardDatabase, name: &str) -> urza_core::CardDefId {
    cards.card_id_by_name(name).unwrap()
}

fn permanent(
    cards: &CurrentCardDatabase,
    object: u32,
    name: &str,
    tapped: bool,
) -> PermanentState {
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

#[test]
fn cam_draw_two_is_solver_visible_at_its_reduced_artifact_activation_cost() {
    let cards = CurrentCardDatabase::load().unwrap();
    let state = TrueState {
        turn: 1,
        phase: Phase::PrecombatMain,
        window: Window::Priority,
        battlefield: BattlefieldZone::new(vec![
            permanent(&cards, 1, "Sewer-veillance Cam", false),
            permanent(&cards, 2, "Forensic Gadgeteer", false),
        ]),
        mana: ManaPool {
            blue: 1,
            colorless: 2,
            ..ManaPool::default()
        },
        ..TrueState::default()
    };
    let bridge = CandidateBridge::build(&state, &cards).unwrap();
    assert!(bridge.candidates().iter().any(|candidate| {
        matches!(
            bridge.resolve(candidate.token),
            Some(Action::ActivateCamDrawTwo {
                source: ObjectId(1),
                ..
            })
        )
    }));
}

#[test]
fn key_untap_target_choice_is_solver_visible() {
    let cards = CurrentCardDatabase::load().unwrap();
    let state = TrueState {
        turn: 1,
        phase: Phase::PrecombatMain,
        window: Window::Priority,
        battlefield: BattlefieldZone::new(vec![
            permanent(&cards, 10, "Manifold Key", false),
            permanent(&cards, 11, "Mana Vault", true),
        ]),
        mana: ManaPool {
            colorless: 1,
            ..ManaPool::default()
        },
        ..TrueState::default()
    };
    let bridge = CandidateBridge::build(&state, &cards).unwrap();
    assert!(bridge.candidates().iter().any(|candidate| {
        matches!(
            bridge.resolve(candidate.token),
            Some(Action::ActivateKeyUntap {
                source: ObjectId(10),
                ..
            })
        )
    }));
}
