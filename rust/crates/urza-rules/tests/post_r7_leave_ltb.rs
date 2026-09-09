use std::collections::BTreeMap;

use urza_core::{
    BattlefieldZone, CardDefId, CardFace, CardZone, CounterState, DelayedEvent, ManaPool, ObjectId,
    PendingDecision, PermanentMode, PermanentState, Phase, StackObject, TrueLibrary, TrueState,
    Window,
};
use urza_info::observe;
use urza_rng::{LogicalEventId, RootSeed, WorldId};
use urza_rules::{
    ABILITY_CAM_TAP_UNTAP, Action, CardDatabase, CardProfile, GameRngContext, ManaCost, ManaPayment,
    R2CardRole, SpecialSearchKind, UtilityKind, apply_action, apply_action_with_rng,
};

const TRANSMUTE: CardDefId = CardDefId(900);
const CAM: CardDefId = CardDefId(901);
const CREATURE: CardDefId = CardDefId(902);
const LIBRARY_CARD: CardDefId = CardDefId(903);
const COMMANDER: CardDefId = CardDefId(904);
const CONSTRUCT: CardDefId = CardDefId(905);

struct Cards {
    profiles: BTreeMap<CardDefId, CardProfile>,
}

impl Cards {
    fn new() -> Self {
        let mut profiles = BTreeMap::new();
        profiles.insert(
            TRANSMUTE,
            CardProfile {
                card: TRANSMUTE,
                mana_cost: Some(ManaCost {
                    blue: 2,
                    ..ManaCost::default()
                }),
                mana_value: 2,
                role: R2CardRole::SearchSpell,
                battlefield_face: CardFace::Front,
                special_search: SpecialSearchKind::TransmuteArtifact,
                ..CardProfile::default()
            },
        );
        profiles.insert(
            CAM,
            CardProfile {
                card: CAM,
                mana_value: 3,
                role: R2CardRole::ArtifactPermanent,
                battlefield_face: CardFace::Front,
                utility: UtilityKind::SewerVeillanceCam,
                is_artifact: true,
                ..CardProfile::default()
            },
        );
        profiles.insert(
            CREATURE,
            CardProfile {
                card: CREATURE,
                mana_value: 2,
                role: R2CardRole::CreaturePermanent,
                battlefield_face: CardFace::Front,
                is_creature: true,
                ..CardProfile::default()
            },
        );
        profiles.insert(
            LIBRARY_CARD,
            CardProfile {
                card: LIBRARY_CARD,
                mana_value: 0,
                role: R2CardRole::ArtifactPermanent,
                battlefield_face: CardFace::Front,
                is_artifact: true,
                ..CardProfile::default()
            },
        );
        Self { profiles }
    }
}

impl CardDatabase for Cards {
    fn profile(&self, card: CardDefId) -> Option<CardProfile> {
        self.profiles.get(&card).copied()
    }

    fn commander_card(&self) -> CardDefId {
        COMMANDER
    }

    fn urza_construct_token_card(&self) -> CardDefId {
        CONSTRUCT
    }
}

fn permanent(object: u32, card: CardDefId) -> PermanentState {
    PermanentState {
        object_id: ObjectId(object),
        card,
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
fn transmute_cam_trigger_flushes_only_after_staged_resolution_completes() {
    let cards = Cards::new();
    let mut state = TrueState {
        turn: 1,
        phase: Phase::PrecombatMain,
        window: Window::Priority,
        hand: CardZone::new(vec![TRANSMUTE]),
        library: TrueLibrary::unknown(vec![LIBRARY_CARD]),
        battlefield: BattlefieldZone::new(vec![permanent(1, CAM), permanent(2, CREATURE)]),
        mana: ManaPool {
            blue: 2,
            ..ManaPool::default()
        },
        ..TrueState::default()
    };

    apply_action(
        &mut state,
        &cards,
        Action::CastFromHand {
            card: TRANSMUTE,
            payment: ManaPayment {
                blue: 2,
                ..ManaPayment::default()
            },
        },
    )
    .unwrap();
    apply_action(&mut state, &cards, Action::PassPriority).unwrap();

    let cam = canonical_for(&state, ObjectId(1));
    apply_action(
        &mut state,
        &cards,
        Action::ChooseTransmuteSacrifice { artifact: cam },
    )
    .unwrap();

    assert!(matches!(state.pending, PendingDecision::TransmuteTarget { .. }));
    assert_eq!(state.window, Window::PostObservation);
    assert!(state.stack.is_empty());
    assert!(state.delayed_events.iter().any(|event| matches!(
        event,
        DelayedEvent::DeferredControlledTrigger {
            ability: ABILITY_CAM_TAP_UNTAP,
            ..
        }
    )));

    apply_action_with_rng(
        &mut state,
        &cards,
        Action::ChooseSearchTarget { target: None },
        GameRngContext {
            root: RootSeed::from_u64(55),
            world: WorldId(0),
            logical_event: LogicalEventId(17),
        },
    )
    .unwrap();

    assert!(matches!(state.pending, PendingDecision::None));
    assert_eq!(state.window, Window::Priority);
    assert!(state.delayed_events.is_empty());
    assert!(matches!(
        state.stack.last(),
        Some(StackObject::ControlledTrigger {
            ability: ABILITY_CAM_TAP_UNTAP,
            ..
        })
    ));

    apply_action(&mut state, &cards, Action::PassPriority).unwrap();
    assert!(matches!(state.pending, PendingDecision::CamTarget { .. }));
}
