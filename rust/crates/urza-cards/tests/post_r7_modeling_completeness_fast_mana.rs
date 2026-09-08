use urza_cards::{
    CurrentCardDatabase, POST_R7_ACCEPTED_ACTIVE_IDENTITY_COUNT, load_r1_catalog,
    validate_post_r7_database,
};
use urza_core::{
    BattlefieldZone, CardZone, CounterState, ManaPool, ObjectId, PermanentMode, PermanentState,
    Phase, TrueLibrary, TrueState, Window,
};
use urza_rules::{Action, ManaAbility, ManaPayment, R2CardRole, RuleError, apply_action};

fn card(cards: &CurrentCardDatabase, name: &str) -> urza_core::CardDefId {
    cards.card_id_by_name(name).unwrap()
}

fn priority_state() -> TrueState {
    let state = TrueState {
        turn: 1,
        phase: Phase::PrecombatMain,
        window: Window::Priority,
        library: TrueLibrary::unknown(Vec::new()),
        life: 40,
        ..TrueState::default()
    };
    state.validate().unwrap();
    state
}

fn permanent(cards: &CurrentCardDatabase, object: u32, name: &str) -> PermanentState {
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

fn cost_contains_nonblue_colored_symbol(cost: &str) -> bool {
    cost.split('{')
        .skip(1)
        .filter_map(|part| part.split('}').next())
        .any(|symbol| {
            symbol
                .split('/')
                .any(|component| matches!(component, "W" | "B" | "R" | "G"))
        })
}

#[test]
fn pinned_deck_any_color_mana_projects_losslessly_to_blue() {
    let catalog = load_r1_catalog().unwrap();
    assert_eq!(catalog.cards.len(), 95);

    for metadata in &catalog.cards {
        assert!(
            !cost_contains_nonblue_colored_symbol(&metadata.mana_cost),
            "{} has non-blue colored mana in {:?}; any-color mana can no longer project to blue",
            metadata.deck_name,
            metadata.mana_cost
        );
        for face in &metadata.faces {
            assert!(
                !cost_contains_nonblue_colored_symbol(&face.mana_cost),
                "{} / {} has non-blue colored mana in {:?}; any-color mana can no longer project to blue",
                metadata.deck_name,
                face.name,
                face.mana_cost
            );
        }
    }
}

#[test]
fn lotus_petal_casts_for_zero_then_tap_sacrifices_for_blue() {
    let cards = CurrentCardDatabase::load().unwrap();
    let lotus = card(&cards, "Lotus Petal");
    let profile = cards.profile(lotus).unwrap();
    assert_eq!(profile.role, R2CardRole::ArtifactPermanent);
    assert_eq!(profile.mana_ability, ManaAbility::TapSacrificeForBlue);
    assert!(profile.is_artifact);

    let mut state = priority_state();
    state.hand = CardZone::new(vec![lotus]);
    apply_action(
        &mut state,
        &cards,
        Action::CastFromHand {
            card: lotus,
            payment: ManaPayment::default(),
        },
    )
    .unwrap();
    apply_action(&mut state, &cards, Action::PassPriority).unwrap();

    let source = state
        .battlefield
        .permanents()
        .iter()
        .find(|permanent| permanent.card == lotus)
        .unwrap()
        .object_id;
    apply_action(&mut state, &cards, Action::ActivateManaAbility { source }).unwrap();

    assert_eq!(state.mana.blue, 1);
    assert!(
        state
            .battlefield
            .permanents()
            .iter()
            .all(|permanent| permanent.card != lotus)
    );
    assert!(state.graveyard.cards().contains(&lotus));
}

#[test]
fn mox_opal_requires_three_artifacts_and_then_taps_for_blue() {
    let cards = CurrentCardDatabase::load().unwrap();
    let mox = card(&cards, "Mox Opal");
    let profile = cards.profile(mox).unwrap();
    assert_eq!(profile.role, R2CardRole::ArtifactPermanent);
    assert_eq!(profile.mana_ability, ManaAbility::MetalcraftTapForBlue);
    assert!(profile.is_artifact);

    let mut below_metalcraft = priority_state();
    below_metalcraft.battlefield = BattlefieldZone::new(vec![
        permanent(&cards, 1, "Mox Opal"),
        permanent(&cards, 2, "Sol Ring"),
    ]);
    below_metalcraft.validate().unwrap();
    assert!(matches!(
        apply_action(
            &mut below_metalcraft,
            &cards,
            Action::ActivateManaAbility {
                source: ObjectId(1)
            }
        ),
        Err(RuleError::NotManaSource(ObjectId(1)))
    ));
    assert_eq!(below_metalcraft.mana, ManaPool::default());
    assert!(
        !below_metalcraft
            .battlefield
            .get(ObjectId(1))
            .unwrap()
            .tapped
    );

    let mut metalcraft = priority_state();
    metalcraft.battlefield = BattlefieldZone::new(vec![
        permanent(&cards, 1, "Mox Opal"),
        permanent(&cards, 2, "Sol Ring"),
        permanent(&cards, 3, "Seat of the Synod"),
    ]);
    metalcraft.validate().unwrap();
    apply_action(
        &mut metalcraft,
        &cards,
        Action::ActivateManaAbility {
            source: ObjectId(1),
        },
    )
    .unwrap();
    assert_eq!(metalcraft.mana.blue, 1);
    assert!(metalcraft.battlefield.get(ObjectId(1)).unwrap().tapped);
}

#[test]
fn current_database_accepts_the_two_fast_mana_identities_without_mutating_r4() {
    validate_post_r7_database().unwrap();
    let cards = CurrentCardDatabase::load().unwrap();
    assert_eq!(POST_R7_ACCEPTED_ACTIVE_IDENTITY_COUNT, 52);
    assert_eq!(cards.supported_active_cards().len(), 52);
}
