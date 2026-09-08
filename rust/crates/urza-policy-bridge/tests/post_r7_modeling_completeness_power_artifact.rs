use urza_cards::CurrentCardDatabase;
use urza_core::{
    BattlefieldZone, CardZone, CounterState, ManaPool, ObjectId, PermanentMode, PermanentState,
    Phase, TrueLibrary, TrueState, Window,
};
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

#[test]
fn power_artifact_cast_candidate_targets_artifacts_but_not_creatures() {
    let cards = CurrentCardDatabase::load().unwrap();
    let power = card(&cards, "Power Artifact");
    let basalt = card(&cards, "Basalt Monolith");
    let spellseeker = card(&cards, "Spellseeker");
    let state = state_with(
        &cards,
        vec![
            permanent(&cards, 1, "Basalt Monolith", true),
            permanent(&cards, 2, "Spellseeker", false),
        ],
        &["Power Artifact"],
        ManaPool {
            blue: 2,
            ..ManaPool::default()
        },
    );
    let bridge = CandidateBridge::build(&state, &cards).unwrap();
    let basalt_target = bridge
        .information()
        .battlefield
        .iter()
        .find(|permanent| permanent.card == basalt)
        .unwrap()
        .canonical_id;
    let spellseeker_target = bridge
        .information()
        .battlefield
        .iter()
        .find(|permanent| permanent.card == spellseeker)
        .unwrap()
        .canonical_id;

    assert!(bridge.candidates().iter().any(|candidate| {
        matches!(
            bridge.resolve(candidate.token),
            Some(Action::CastAuraFromHand {
                card,
                target,
                payment,
            }) if *card == power && *target == basalt_target && payment.blue == 2
        )
    }));
    assert!(!bridge.candidates().iter().any(|candidate| {
        matches!(
            bridge.resolve(candidate.token),
            Some(Action::CastAuraFromHand { card, target, .. })
                if *card == power && *target == spellseeker_target
        )
    }));
}

#[test]
fn power_artifact_reduced_untap_cost_is_solver_visible_with_the_one_mana_floor() {
    let cards = CurrentCardDatabase::load().unwrap();
    let basalt = card(&cards, "Basalt Monolith");
    let mut power = permanent(&cards, 3, "Power Artifact", false);
    power.attached_to = Some(ObjectId(1));
    let state = state_with(
        &cards,
        vec![
            permanent(&cards, 1, "Basalt Monolith", true),
            permanent(&cards, 2, "Forensic Gadgeteer", false),
            power,
        ],
        &[],
        ManaPool {
            colorless: 1,
            ..ManaPool::default()
        },
    );
    let bridge = CandidateBridge::build(&state, &cards).unwrap();

    assert!(bridge.candidates().iter().any(|candidate| {
        candidate.key.card == Some(basalt)
            && matches!(
                bridge.resolve(candidate.token),
                Some(Action::ActivateNativeArtifactUntap { payment, .. })
                    if *payment == ManaPayment {
                        colorless: 1,
                        ..ManaPayment::default()
                    }
            )
    }));
    assert!(!bridge.candidates().iter().any(|candidate| {
        candidate.key.card == Some(basalt)
            && matches!(
                bridge.resolve(candidate.token),
                Some(Action::ActivateNativeArtifactUntap { payment, .. })
                    if *payment == ManaPayment::default()
            )
    }));
}

#[test]
fn power_artifact_bridge_candidate_executes_through_the_public_target() {
    let cards = CurrentCardDatabase::load().unwrap();
    let power = card(&cards, "Power Artifact");
    let basalt = card(&cards, "Basalt Monolith");
    let mut state = state_with(
        &cards,
        vec![permanent(&cards, 1, "Basalt Monolith", true)],
        &["Power Artifact"],
        ManaPool {
            blue: 2,
            ..ManaPool::default()
        },
    );
    let bridge = CandidateBridge::build(&state, &cards).unwrap();
    let target = bridge
        .information()
        .battlefield
        .iter()
        .find(|permanent| permanent.card == basalt)
        .unwrap()
        .canonical_id;
    let action = bridge
        .candidates()
        .iter()
        .find_map(|candidate| match bridge.resolve(candidate.token) {
            Some(Action::CastAuraFromHand {
                card,
                target: candidate_target,
                payment,
            }) if *card == power && *candidate_target == target && payment.blue == 2 => {
                bridge.resolved_action(candidate.token)
            }
            _ => None,
        })
        .unwrap();

    apply_action(&mut state, &cards, action).unwrap();
    apply_action(&mut state, &cards, Action::PassPriority).unwrap();
    let aura = state
        .battlefield
        .permanents()
        .iter()
        .find(|permanent| permanent.card == power)
        .unwrap();
    assert_eq!(aura.attached_to, Some(ObjectId(1)));
}
