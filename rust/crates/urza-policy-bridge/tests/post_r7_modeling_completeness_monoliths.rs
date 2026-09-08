use urza_cards::CurrentCardDatabase;
use urza_core::{
    BattlefieldZone, CounterState, ManaPool, ObjectId, PermanentMode, PermanentState, Phase,
    TrueState, Window,
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

fn state_with(permanent: PermanentState, colorless: u16) -> TrueState {
    let state = TrueState {
        turn: 1,
        phase: Phase::PrecombatMain,
        window: Window::Priority,
        battlefield: BattlefieldZone::new(vec![permanent]),
        mana: ManaPool {
            colorless,
            ..ManaPool::default()
        },
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

fn has_native_untap_candidate(
    bridge: &CandidateBridge,
    source_card: urza_core::CardDefId,
    expected_payment: u16,
) -> bool {
    bridge.candidates().iter().any(|candidate| {
        candidate.class == PolicyActionClass::ManaSetup
            && candidate.key.card == Some(source_card)
            && matches!(
                bridge.resolve(candidate.token),
                Some(Action::ActivateNativeArtifactUntap { payment, .. })
                    if payment.colorless == expected_payment
            )
    })
}

fn audit_bridge(name: &str, untap_generic: u16) {
    let cards = CurrentCardDatabase::load().unwrap();
    let monolith = card(&cards, name);

    let ready = state_with(permanent(&cards, 1, name, false), untap_generic);
    let ready_bridge = CandidateBridge::build(&ready, &cards).unwrap();
    assert!(has_intrinsic_mana_candidate(&ready_bridge, monolith));
    assert!(has_native_untap_candidate(
        &ready_bridge,
        monolith,
        untap_generic
    ));

    let tapped = state_with(permanent(&cards, 1, name, true), untap_generic);
    let tapped_bridge = CandidateBridge::build(&tapped, &cards).unwrap();
    assert!(!has_intrinsic_mana_candidate(&tapped_bridge, monolith));
    assert!(has_native_untap_candidate(
        &tapped_bridge,
        monolith,
        untap_generic
    ));

    let short = state_with(
        permanent(&cards, 1, name, true),
        untap_generic.saturating_sub(1),
    );
    let short_bridge = CandidateBridge::build(&short, &cards).unwrap();
    assert!(!has_native_untap_candidate(
        &short_bridge,
        monolith,
        untap_generic
    ));
}

#[test]
fn basalt_monolith_mana_and_native_untap_are_solver_visible() {
    audit_bridge("Basalt Monolith", 3);
}

#[test]
fn grim_monolith_mana_and_native_untap_are_solver_visible() {
    audit_bridge("Grim Monolith", 4);
}
