use urza_cards::CurrentCardDatabase;
use urza_core::{
    BattlefieldZone, CardZone, CounterState, ManaPool, ObjectId, PermanentMode, PermanentState,
    Phase, StackObject, TrueLibrary, TrueState, Window,
};
use urza_info::observe;
use urza_rules::{
    ABILITY_CAM_DRAW_TWO, ABILITY_CAM_TAP_UNTAP, ABILITY_KEY_UNTAP, Action, CamEffectChoice,
    CardDatabase, ManaPayment, UtilityKind, apply_action,
};

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
        mode: match profile.utility {
            UtilityKind::UthrosResearchCraft => PermanentMode::UthrosStation,
            _ => PermanentMode::Normal,
        },
        attached_to: None,
        granted_ability: None,
    }
}

fn canonical_for(state: &TrueState, wanted: ObjectId) -> urza_info::CanonicalObjectId {
    observe(state)
        .unwrap()
        .battlefield
        .into_iter()
        .find(|permanent| {
            urza_info::resolve_canonical_object(state, permanent.canonical_id).unwrap()
                == Some(wanted)
        })
        .unwrap()
        .canonical_id
}

#[test]
fn sewer_veillance_cam_sacrifice_draw_two_stages_ltb_above_the_activation() {
    let cards = CurrentCardDatabase::load().unwrap();
    let island = card(&cards, "Island");
    let sol_ring = card(&cards, "Sol Ring");
    let mut state = TrueState {
        turn: 1,
        phase: Phase::PrecombatMain,
        window: Window::Priority,
        library: TrueLibrary::unknown(vec![island, sol_ring]),
        battlefield: BattlefieldZone::new(vec![
            permanent(&cards, 1, "Sewer-veillance Cam", false),
            permanent(&cards, 2, "Battered Golem", false),
        ]),
        mana: ManaPool {
            blue: 1,
            colorless: 3,
            ..ManaPool::default()
        },
        ..TrueState::default()
    };

    apply_action(
        &mut state,
        &cards,
        Action::ActivateCamDrawTwo {
            source: ObjectId(1),
            payment: ManaPayment {
                blue: 1,
                colorless: 3,
                ..ManaPayment::default()
            },
        },
    )
    .unwrap();

    assert!(state.battlefield.get(ObjectId(1)).is_none());
    assert!(state.graveyard.cards().contains(&card(&cards, "Sewer-veillance Cam")));
    assert!(matches!(
        state.stack.first(),
        Some(StackObject::ActivatedAbility {
            ability: ABILITY_CAM_DRAW_TWO,
            ..
        })
    ));
    assert!(matches!(
        state.stack.last(),
        Some(StackObject::ControlledTrigger {
            ability: ABILITY_CAM_TAP_UNTAP,
            ..
        })
    ));
    assert!(state.hand.is_empty());

    apply_action(&mut state, &cards, Action::PassPriority).unwrap();
    let target = canonical_for(&state, ObjectId(2));
    apply_action(&mut state, &cards, Action::ChooseCamTarget { target }).unwrap();
    apply_action(&mut state, &cards, Action::PassPriority).unwrap();
    apply_action(
        &mut state,
        &cards,
        Action::ChooseCamEffect {
            choice: CamEffectChoice::Decline,
        },
    )
    .unwrap();
    assert!(matches!(
        state.stack.last(),
        Some(StackObject::ActivatedAbility {
            ability: ABILITY_CAM_DRAW_TWO,
            ..
        })
    ));
    apply_action(&mut state, &cards, Action::PassPriority).unwrap();
    assert_eq!(state.hand.len(), 2);
    assert!(state.library.cards().is_empty());
}

#[test]
fn cam_draw_two_uses_artifact_activation_reducers_with_the_one_mana_floor() {
    let cards = CurrentCardDatabase::load().unwrap();
    let mut state = TrueState {
        turn: 1,
        phase: Phase::PrecombatMain,
        window: Window::Priority,
        library: TrueLibrary::unknown(vec![card(&cards, "Island"), card(&cards, "Sol Ring")]),
        battlefield: BattlefieldZone::new(vec![
            permanent(&cards, 10, "Sewer-veillance Cam", false),
            permanent(&cards, 11, "Forensic Gadgeteer", false),
        ]),
        mana: ManaPool {
            blue: 1,
            colorless: 2,
            ..ManaPool::default()
        },
        ..TrueState::default()
    };
    apply_action(
        &mut state,
        &cards,
        Action::ActivateCamDrawTwo {
            source: ObjectId(10),
            payment: ManaPayment {
                blue: 1,
                colorless: 2,
                ..ManaPayment::default()
            },
        },
    )
    .unwrap();
}

#[test]
fn voltaic_and_manifold_key_share_targeted_artifact_untap_but_preserve_another() {
    let cards = CurrentCardDatabase::load().unwrap();

    let mut voltaic = TrueState {
        turn: 1,
        phase: Phase::PrecombatMain,
        window: Window::Priority,
        battlefield: BattlefieldZone::new(vec![permanent(&cards, 20, "Voltaic Key", false)]),
        mana: ManaPool {
            colorless: 1,
            ..ManaPool::default()
        },
        ..TrueState::default()
    };
    let voltaic_self = canonical_for(&voltaic, ObjectId(20));
    apply_action(
        &mut voltaic,
        &cards,
        Action::ActivateKeyUntap {
            source: ObjectId(20),
            target: voltaic_self,
            payment: ManaPayment {
                colorless: 1,
                ..ManaPayment::default()
            },
        },
    )
    .unwrap();
    assert!(voltaic.battlefield.get(ObjectId(20)).unwrap().tapped);
    assert!(matches!(
        voltaic.stack.last(),
        Some(StackObject::TargetedActivatedAbility {
            ability: ABILITY_KEY_UNTAP,
            ..
        })
    ));
    apply_action(&mut voltaic, &cards, Action::PassPriority).unwrap();
    assert!(!voltaic.battlefield.get(ObjectId(20)).unwrap().tapped);

    let mut manifold = TrueState {
        turn: 1,
        phase: Phase::PrecombatMain,
        window: Window::Priority,
        battlefield: BattlefieldZone::new(vec![
            permanent(&cards, 30, "Manifold Key", false),
            permanent(&cards, 31, "Mana Vault", true),
            permanent(&cards, 32, "Forensic Gadgeteer", false),
        ]),
        mana: ManaPool {
            colorless: 1,
            ..ManaPool::default()
        },
        ..TrueState::default()
    };
    let manifold_self = canonical_for(&manifold, ObjectId(30));
    assert!(
        apply_action(
            &mut manifold,
            &cards,
            Action::ActivateKeyUntap {
                source: ObjectId(30),
                target: manifold_self,
                payment: ManaPayment {
                    colorless: 1,
                    ..ManaPayment::default()
                },
            },
        )
        .is_err(),
        "Manifold Key requires another target artifact"
    );
    let vault = canonical_for(&manifold, ObjectId(31));
    apply_action(
        &mut manifold,
        &cards,
        Action::ActivateKeyUntap {
            source: ObjectId(30),
            target: vault,
            payment: ManaPayment {
                colorless: 1,
                ..ManaPayment::default()
            },
        },
    )
    .unwrap();
    apply_action(&mut manifold, &cards, Action::PassPriority).unwrap();
    assert!(!manifold.battlefield.get(ObjectId(31)).unwrap().tapped);
}
