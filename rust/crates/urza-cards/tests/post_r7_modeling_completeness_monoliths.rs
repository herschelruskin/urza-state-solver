use urza_cards::CurrentCardDatabase;
use urza_core::{CardZone, ManaPool, Phase, TrueLibrary, TrueState, Window};
use urza_rules::{
    Action, ManaAbility, ManaCost, ManaPayment, R2CardRole, advance_phase, apply_action,
};

fn card(cards: &CurrentCardDatabase, name: &str) -> urza_core::CardDefId {
    cards.card_id_by_name(name).unwrap()
}

fn priority_state(hand: Vec<urza_core::CardDefId>, mana: ManaPool) -> TrueState {
    let state = TrueState {
        turn: 1,
        phase: Phase::PrecombatMain,
        window: Window::Priority,
        hand: CardZone::new(hand),
        library: TrueLibrary::unknown(Vec::new()),
        mana,
        life: 40,
        ..TrueState::default()
    };
    state.validate().unwrap();
    state
}

fn audit_monolith(name: &str, cast_generic: u16, untap_generic: u16) {
    let cards = CurrentCardDatabase::load().unwrap();
    let monolith = card(&cards, name);
    let profile = cards.profile(monolith).unwrap();

    assert_eq!(profile.role, R2CardRole::ArtifactPermanent);
    assert!(profile.is_artifact);
    assert_eq!(
        profile.mana_cost,
        Some(ManaCost {
            generic: cast_generic,
            ..ManaCost::default()
        })
    );
    assert_eq!(profile.mana_ability, ManaAbility::TapForColorless(3));
    assert_eq!(profile.native_untap_generic, Some(untap_generic));
    assert!(profile.skip_normal_untap);

    let mut state = priority_state(
        vec![monolith],
        ManaPool {
            colorless: cast_generic,
            ..ManaPool::default()
        },
    );
    apply_action(
        &mut state,
        &cards,
        Action::CastFromHand {
            card: monolith,
            payment: ManaPayment {
                colorless: cast_generic,
                ..ManaPayment::default()
            },
        },
    )
    .unwrap();
    assert_eq!(state.mana, ManaPool::default());
    apply_action(&mut state, &cards, Action::PassPriority).unwrap();

    let source = state
        .battlefield
        .permanents()
        .iter()
        .find(|permanent| permanent.card == monolith)
        .unwrap()
        .object_id;
    assert!(!state.battlefield.get(source).unwrap().tapped);

    apply_action(&mut state, &cards, Action::ActivateManaAbility { source }).unwrap();
    assert_eq!(state.mana.colorless, 3);
    assert!(state.battlefield.get(source).unwrap().tapped);

    state.turn = 2;
    state.phase = Phase::Untap;
    state.window = Window::None;
    state.mana = ManaPool::default();
    state.validate().unwrap();
    advance_phase(&mut state, &cards).unwrap();
    assert_eq!(state.phase, Phase::Upkeep);
    assert!(state.battlefield.get(source).unwrap().tapped);

    state.mana = ManaPool {
        colorless: untap_generic,
        ..ManaPool::default()
    };
    apply_action(
        &mut state,
        &cards,
        Action::ActivateNativeArtifactUntap {
            source,
            payment: ManaPayment {
                colorless: untap_generic,
                ..ManaPayment::default()
            },
        },
    )
    .unwrap();
    assert_eq!(state.mana, ManaPool::default());
    assert!(state.battlefield.get(source).unwrap().tapped);
    apply_action(&mut state, &cards, Action::PassPriority).unwrap();
    assert!(!state.battlefield.get(source).unwrap().tapped);

    state.mana = ManaPool {
        colorless: untap_generic,
        ..ManaPool::default()
    };
    apply_action(
        &mut state,
        &cards,
        Action::ActivateNativeArtifactUntap {
            source,
            payment: ManaPayment {
                colorless: untap_generic,
                ..ManaPayment::default()
            },
        },
    )
    .unwrap();
    apply_action(&mut state, &cards, Action::PassPriority).unwrap();
    assert!(!state.battlefield.get(source).unwrap().tapped);
}

#[test]
fn basalt_monolith_matches_every_goldfish_relevant_oracle_clause() {
    audit_monolith("Basalt Monolith", 3, 3);
}

#[test]
fn grim_monolith_matches_every_goldfish_relevant_oracle_clause() {
    audit_monolith("Grim Monolith", 2, 4);
}
