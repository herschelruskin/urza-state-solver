use urza_info::{
    AbilityId, CanonicalObjectId, CardCount, CardDefId, CardFace, CounterState, InformationState,
    LibraryBelief, ObservedPendingDecision, ObservedPermanent, ObservedSourceRef,
    ObservedStackKind, ObservedStackObject, PermanentMode, Phase,
};
use urza_policy::{
    ActionToken, PolicyActionClass, PolicyCandidate, PolicyPublicKey, StrategicPolicy,
    StrategicPolicyConfig, TerminalRecipe,
};

const ASSISTANT: AbilityId = AbilityId(0x0413);
const UTHROS_DRAW: AbilityId = AbilityId(0x0411);

fn source(card: u16) -> ObservedSourceRef {
    ObservedSourceRef {
        canonical_object: None,
        card: CardDefId(card),
    }
}

fn candidate(
    token: u16,
    class: PolicyActionClass,
    kind: u16,
    card: Option<u16>,
) -> PolicyCandidate {
    PolicyCandidate::new(
        ActionToken(token),
        class,
        PolicyPublicKey {
            kind,
            card: card.map(CardDefId),
            ..PolicyPublicKey::default()
        },
    )
}

fn contingent(token: u16, detail: Vec<u16>, card: Option<u16>) -> PolicyCandidate {
    PolicyCandidate::new(
        ActionToken(token),
        PolicyActionClass::ContingentDecision,
        PolicyPublicKey {
            kind: 99,
            card: card.map(CardDefId),
            detail,
            ..PolicyPublicKey::default()
        },
    )
}

fn trigger(ability: AbilityId) -> ObservedStackObject {
    ObservedStackObject {
        kind: ObservedStackKind::ControlledTrigger,
        card: None,
        source: Some(source(7)),
        target: None,
        ability: Some(ability),
        parameter: None,
    }
}

fn permanent(card: u16, id: u16) -> ObservedPermanent {
    ObservedPermanent {
        canonical_id: CanonicalObjectId(id),
        card: CardDefId(card),
        face: CardFace::Front,
        tapped: false,
        summoning_sick: false,
        token: false,
        counters: CounterState::default(),
        mode: PermanentMode::Normal,
        attached_to: None,
        granted_ability: None,
    }
}

fn configured() -> StrategicPolicy {
    let mut config = StrategicPolicyConfig::default();
    config.card_values.insert(CardDefId(10), 120);
    config.card_values.insert(CardDefId(20), 110);
    config.card_values.insert(CardDefId(30), 0);
    config.assistant_scry_ability = Some(ASSISTANT);
    config.uthros_draw_ability = Some(UTHROS_DRAW);
    StrategicPolicy::new(config)
}

#[test]
fn tutor_chooses_terminal_completion_over_static_target_order() {
    let mut config = StrategicPolicyConfig::default();
    config.card_values.insert(CardDefId(10), 200);
    config.card_values.insert(CardDefId(20), 100);
    config
        .terminal_recipes
        .push(TerminalRecipe::new(vec![CardDefId(5), CardDefId(20)]));
    let policy = StrategicPolicy::new(config);
    let information = InformationState {
        hand: vec![CardDefId(5)],
        pending: ObservedPendingDecision::TutorTarget { source: source(80) },
        ..InformationState::default()
    };
    let flashy = contingent(1, Vec::new(), Some(10));
    let completion = contingent(9, Vec::new(), Some(20));
    let fail = contingent(0, Vec::new(), None);

    assert_eq!(
        policy
            .choose(&information, &[flashy, fail, completion])
            .unwrap(),
        Some(ActionToken(9))
    );
}

#[test]
fn scry_keeps_public_high_value_and_bottoms_public_low_value() {
    let policy = configured();
    let high_information = InformationState {
        pending: ObservedPendingDecision::ScryChoice {
            source: source(1),
            looked_at: vec![CardDefId(10)],
        },
        ..InformationState::default()
    };
    let keep_high = contingent(1, vec![1, 10, 0], None);
    let bottom_high = contingent(2, vec![0, 1, 10], None);
    assert_eq!(
        policy
            .choose(&high_information, &[bottom_high, keep_high])
            .unwrap(),
        Some(ActionToken(1))
    );

    let low_information = InformationState {
        pending: ObservedPendingDecision::ScryChoice {
            source: source(1),
            looked_at: vec![CardDefId(30)],
        },
        ..InformationState::default()
    };
    let keep_low = contingent(3, vec![1, 30, 0], None);
    let bottom_low = contingent(4, vec![0, 1, 30], None);
    assert_eq!(
        policy
            .choose(&low_information, &[keep_low, bottom_low])
            .unwrap(),
        Some(ActionToken(4))
    );
}

#[test]
fn top_reorder_places_best_observed_card_first() {
    let policy = configured();
    let information = InformationState {
        pending: ObservedPendingDecision::TopReorder {
            source: source(1),
            cards: vec![CardDefId(30), CardDefId(10), CardDefId(20)],
        },
        ..InformationState::default()
    };
    let bad_first = contingent(1, vec![30, 20, 10], None);
    let best_first = contingent(2, vec![10, 20, 30], None);
    assert_eq!(
        policy
            .choose(&information, &[bad_first, best_first])
            .unwrap(),
        Some(ActionToken(2))
    );
}

#[test]
fn trigger_order_draws_good_known_top_first_and_scries_bad_known_top_first() {
    let policy = configured();
    let base_stack = vec![trigger(ASSISTANT), trigger(UTHROS_DRAW)];
    let assistant_first = contingent(1, vec![0, 1], None);
    let uthros_first = contingent(2, vec![1, 0], None);

    let good = InformationState {
        library: LibraryBelief {
            known_top: vec![CardDefId(10)],
            ..LibraryBelief::default()
        },
        stack: base_stack.clone(),
        pending: ObservedPendingDecision::TriggerOrder {
            source: source(40),
            trigger_count: 2,
        },
        ..InformationState::default()
    };
    assert_eq!(
        policy
            .choose(&good, &[assistant_first.clone(), uthros_first.clone()])
            .unwrap(),
        Some(ActionToken(2))
    );

    let bad = InformationState {
        library: LibraryBelief {
            known_top: vec![CardDefId(30)],
            ..LibraryBelief::default()
        },
        stack: base_stack,
        pending: ObservedPendingDecision::TriggerOrder {
            source: source(40),
            trigger_count: 2,
        },
        ..InformationState::default()
    };
    assert_eq!(
        policy
            .choose(&bad, &[uthros_first, assistant_first])
            .unwrap(),
        Some(ActionToken(1))
    );
}

#[test]
fn unknown_library_multiset_cannot_change_trigger_order() {
    let policy = configured();
    let candidates = [
        contingent(1, vec![0, 1], None),
        contingent(2, vec![1, 0], None),
    ];
    let make = |remaining_counts| InformationState {
        library: LibraryBelief {
            remaining_counts,
            known_top: Vec::new(),
            known_bottom: Vec::new(),
        },
        stack: vec![trigger(ASSISTANT), trigger(UTHROS_DRAW)],
        pending: ObservedPendingDecision::TriggerOrder {
            source: source(40),
            trigger_count: 2,
        },
        ..InformationState::default()
    };
    let a = make(vec![CardCount {
        card: CardDefId(10),
        count: 1,
    }]);
    let b = make(vec![CardCount {
        card: CardDefId(30),
        count: 1,
    }]);
    assert_eq!(
        policy.choose(&a, &candidates).unwrap(),
        policy.choose(&b, &candidates).unwrap()
    );
}

#[test]
fn top_can_intervene_above_relevant_triggers_once_then_stack_drains() {
    let mut config = StrategicPolicyConfig::default();
    config.stack_intervention_kind_values.insert(15, 200);
    config
        .stack_intervention_trigger_abilities
        .insert(ASSISTANT);
    config
        .stack_intervention_trigger_abilities
        .insert(UTHROS_DRAW);
    let policy = StrategicPolicy::new(config);
    let pass = candidate(1, PolicyActionClass::PassPriority, 1, None);
    let top_look = candidate(2, PolicyActionClass::ActivateAbility, 15, Some(77));
    let information = InformationState {
        stack: vec![trigger(ASSISTANT), trigger(UTHROS_DRAW)],
        ..InformationState::default()
    };
    assert_eq!(
        policy
            .choose(&information, &[pass.clone(), top_look.clone()])
            .unwrap(),
        Some(ActionToken(2))
    );

    let already_known = InformationState {
        library: LibraryBelief {
            known_top: vec![CardDefId(10), CardDefId(20), CardDefId(30)],
            ..LibraryBelief::default()
        },
        stack: vec![trigger(ASSISTANT), trigger(UTHROS_DRAW)],
        ..InformationState::default()
    };
    assert_eq!(
        policy.choose(&already_known, &[top_look, pass]).unwrap(),
        Some(ActionToken(1))
    );
}

#[test]
fn engine_activation_value_competes_with_casts_inside_spend_bucket() {
    let mut config = StrategicPolicyConfig::default();
    config.card_values.insert(CardDefId(70), 100);
    config.action_kind_values.insert(35, 300);
    let policy = StrategicPolicy::new(config);
    let information = InformationState {
        phase: Phase::PrecombatMain,
        ..InformationState::default()
    };
    let cast = candidate(1, PolicyActionClass::CastSpell, 9, Some(60));
    let ring_draw = candidate(2, PolicyActionClass::ActivateAbility, 35, Some(70));
    assert_eq!(
        policy.choose(&information, &[cast, ring_draw]).unwrap(),
        Some(ActionToken(2))
    );
}

#[test]
fn cast_that_completes_public_terminal_recipe_beats_higher_base_card() {
    let mut config = StrategicPolicyConfig::default();
    config.card_values.insert(CardDefId(10), 100);
    config.card_values.insert(CardDefId(20), 220);
    config.card_values.insert(CardDefId(40), 90);
    config
        .terminal_recipes
        .push(TerminalRecipe::new(vec![CardDefId(10), CardDefId(40)]));
    let policy = StrategicPolicy::new(config);
    let information = InformationState {
        phase: Phase::PrecombatMain,
        battlefield: vec![permanent(10, 1)],
        ..InformationState::default()
    };
    let standalone = candidate(1, PolicyActionClass::CastSpell, 9, Some(20));
    let completion = candidate(2, PolicyActionClass::CastSpell, 9, Some(40));
    assert_eq!(
        policy
            .choose(&information, &[standalone, completion])
            .unwrap(),
        Some(ActionToken(2))
    );
}
