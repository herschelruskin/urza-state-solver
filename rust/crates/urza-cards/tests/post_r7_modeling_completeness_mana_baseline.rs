use urza_cards::CurrentCardDatabase;
use urza_core::{CardZone, ManaPool, Phase, TrueLibrary, TrueState, Window};
use urza_rules::{
    Action, LandEntryChoice, ManaAbility, ManaPayment, R2CardRole, apply_action,
};

fn card(cards: &CurrentCardDatabase, name: &str) -> urza_core::CardDefId {
    cards.card_id_by_name(name).unwrap()
}

fn hand_state(cards: &[urza_core::CardDefId]) -> TrueState {
    let state = TrueState {
        turn: 1,
        phase: Phase::PrecombatMain,
        window: Window::Priority,
        hand: CardZone::new(cards.to_vec()),
        library: TrueLibrary::unknown(Vec::new()),
        life: 40,
        ..TrueState::default()
    };
    state.validate().unwrap();
    state
}

fn only_permanent_id(state: &TrueState) -> urza_core::ObjectId {
    state.battlefield.permanents()[0].object_id
}

#[test]
fn island_is_a_complete_untapped_blue_land_for_goldfish() {
    let cards = CurrentCardDatabase::load().unwrap();
    let island = card(&cards, "Island");
    let profile = cards.profile(island).unwrap();
    assert_eq!(profile.role, R2CardRole::Land);
    assert_eq!(profile.mana_ability, ManaAbility::TapForBlue);
    assert!(!profile.is_artifact);

    let mut state = hand_state(&[island]);
    apply_action(
        &mut state,
        &cards,
        Action::PlayLand {
            card: island,
            entry: LandEntryChoice::Default,
        },
    )
    .unwrap();
    let source = only_permanent_id(&state);
    assert!(!state.battlefield.permanents()[0].tapped);

    apply_action(
        &mut state,
        &cards,
        Action::ActivateManaAbility { source },
    )
    .unwrap();
    assert_eq!(state.mana.blue, 1);
    assert!(state.battlefield.permanents()[0].tapped);
}

#[test]
fn ancient_tomb_produces_two_colorless_and_deals_two_damage() {
    let cards = CurrentCardDatabase::load().unwrap();
    let tomb = card(&cards, "Ancient Tomb");
    let profile = cards.profile(tomb).unwrap();
    assert_eq!(profile.role, R2CardRole::Land);
    assert_eq!(
        profile.mana_ability,
        ManaAbility::TapForColorlessAndDamage { mana: 2, damage: 2 }
    );

    let mut state = hand_state(&[tomb]);
    apply_action(
        &mut state,
        &cards,
        Action::PlayLand {
            card: tomb,
            entry: LandEntryChoice::Default,
        },
    )
    .unwrap();
    let source = only_permanent_id(&state);
    apply_action(
        &mut state,
        &cards,
        Action::ActivateManaAbility { source },
    )
    .unwrap();

    assert_eq!(state.mana.colorless, 2);
    assert_eq!(state.life, 38);
    assert!(state.battlefield.permanents()[0].tapped);
}

#[test]
fn sol_ring_casts_for_one_and_taps_for_two_colorless() {
    let cards = CurrentCardDatabase::load().unwrap();
    let ring = card(&cards, "Sol Ring");
    let profile = cards.profile(ring).unwrap();
    assert_eq!(profile.role, R2CardRole::ArtifactPermanent);
    assert_eq!(profile.mana_ability, ManaAbility::TapForColorless(2));
    assert!(profile.is_artifact);

    let mut state = hand_state(&[ring]);
    state.mana.colorless = 1;
    apply_action(
        &mut state,
        &cards,
        Action::CastFromHand {
            card: ring,
            payment: ManaPayment {
                colorless: 1,
                ..ManaPayment::default()
            },
        },
    )
    .unwrap();
    assert_eq!(state.mana, ManaPool::default());
    apply_action(&mut state, &cards, Action::PassPriority).unwrap();
    let source = only_permanent_id(&state);

    apply_action(
        &mut state,
        &cards,
        Action::ActivateManaAbility { source },
    )
    .unwrap();
    assert_eq!(state.mana.colorless, 2);
}

#[test]
fn seat_of_the_synod_is_both_blue_land_and_artifact() {
    let cards = CurrentCardDatabase::load().unwrap();
    let seat = card(&cards, "Seat of the Synod");
    let profile = cards.profile(seat).unwrap();
    assert_eq!(profile.role, R2CardRole::Land);
    assert_eq!(profile.mana_ability, ManaAbility::TapForBlue);
    assert!(profile.is_artifact);

    let mut state = hand_state(&[seat]);
    apply_action(
        &mut state,
        &cards,
        Action::PlayLand {
            card: seat,
            entry: LandEntryChoice::Default,
        },
    )
    .unwrap();
    let source = only_permanent_id(&state);
    apply_action(
        &mut state,
        &cards,
        Action::ActivateManaAbility { source },
    )
    .unwrap();

    assert_eq!(state.mana.blue, 1);
    assert!(state.battlefield.permanents()[0].tapped);
}
