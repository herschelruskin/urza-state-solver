use urza_cards::CurrentCardDatabase;
use urza_core::{
    BattlefieldZone, CounterState, ObjectId, PermanentMode, PermanentState, Phase, TrueState,
    Window,
};
use urza_policy::PolicyActionClass;
use urza_policy_bridge::CandidateBridge;
use urza_rules::Action;

fn card(cards: &CurrentCardDatabase, name: &str) -> urza_core::CardDefId {
    cards.card_id_by_name(name).unwrap()
}

fn permanent(
    cards: &CurrentCardDatabase,
    object: u32,
    name: &str,
) -> PermanentState {
    let card = card(cards, name);
    let profile = cards.profile(card).unwrap();
    PermanentState {
        object_id: ObjectId(object),
        card,
        face: profile.battlefield_face,
        tapped: false,
        summoning_sick: profile.is_creature,
        token: false,
        counters: CounterState::default(),
        mode: PermanentMode::Normal,
        attached_to: None,
        granted_ability: None,
    }
}

fn state_with(permanents: Vec<PermanentState>) -> TrueState {
    let state = TrueState {
        turn: 1,
        phase: Phase::PrecombatMain,
        window: Window::Priority,
        battlefield: BattlefieldZone::new(permanents),
        ..TrueState::default()
    };
    state.validate().unwrap();
    state
}

fn has_intrinsic_mana_candidate(
    bridge: &CandidateBridge,
    source_card: urza_core::CardDefId,
) -> bool {
    bridge.candidates().iter().any(|candidate| {
        candidate.class == PolicyActionClass::ProduceMana
            && candidate.key.card == Some(source_card)
            && matches!(
                bridge.resolve(candidate.token),
                Some(Action::ActivateManaAbility { .. })
            )
    })
}

#[test]
fn lotus_petal_is_exposed_as_a_public_mana_candidate() {
    let cards = CurrentCardDatabase::load().unwrap();
    let lotus = card(&cards, "Lotus Petal");
    let state = state_with(vec![permanent(&cards, 1, "Lotus Petal")]);
    let bridge = CandidateBridge::build(&state, &cards).unwrap();
    assert!(has_intrinsic_mana_candidate(&bridge, lotus));
}

#[test]
fn mox_opal_candidate_tracks_public_metalcraft_exactly() {
    let cards = CurrentCardDatabase::load().unwrap();
    let mox = card(&cards, "Mox Opal");

    let below = state_with(vec![
        permanent(&cards, 1, "Mox Opal"),
        permanent(&cards, 2, "Sol Ring"),
    ]);
    let below_bridge = CandidateBridge::build(&below, &cards).unwrap();
    assert!(!has_intrinsic_mana_candidate(&below_bridge, mox));

    let live = state_with(vec![
        permanent(&cards, 1, "Mox Opal"),
        permanent(&cards, 2, "Sol Ring"),
        permanent(&cards, 3, "Seat of the Synod"),
    ]);
    let live_bridge = CandidateBridge::build(&live, &cards).unwrap();
    assert!(has_intrinsic_mana_candidate(&live_bridge, mox));
}
