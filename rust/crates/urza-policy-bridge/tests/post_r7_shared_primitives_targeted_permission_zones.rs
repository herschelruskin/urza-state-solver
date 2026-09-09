use urza_cards::CurrentCardDatabase;
use urza_core::{
    BattlefieldZone, CardZone, CounterState, LibraryKnowledge, ManaPool, ObjectId, PermanentMode,
    PermanentState, PermissionId, Phase, SourceRef, TrueLibrary, TrueState, UrzaPermission, Window,
};
use urza_policy_bridge::CandidateBridge;
use urza_rules::{Action, CardDatabase};

fn card(cards: &CurrentCardDatabase, name: &str) -> urza_core::CardDefId {
    cards.card_id_by_name(name).unwrap()
}

fn permanent(cards: &CurrentCardDatabase, object: u32, name: &str) -> PermanentState {
    let id = card(cards, name);
    let profile = cards.profile(id).unwrap();
    PermanentState {
        object_id: ObjectId(object),
        card: id,
        face: profile.battlefield_face,
        tapped: false,
        summoning_sick: false,
        token: false,
        counters: CounterState::default(),
        mode: PermanentMode::Normal,
        attached_to: None,
        granted_ability: None,
    }
}

fn build(state: TrueState, cards: &CurrentCardDatabase) -> CandidateBridge {
    state.validate().unwrap();
    CandidateBridge::build(&state, cards).unwrap()
}

#[test]
fn targeted_library_top_permission_is_visible_to_policy_bridge() {
    let cards = CurrentCardDatabase::load().unwrap();
    let knack = card(&cards, "Banishing Knack");
    let mut chip = permanent(&cards, 1, "The Reality Chip");
    chip.mode = PermanentMode::RealityChipAttached;
    chip.attached_to = Some(ObjectId(2));
    let state = TrueState {
        turn: 1,
        phase: Phase::EndStep,
        window: Window::Priority,
        library: TrueLibrary::new(
            vec![knack],
            LibraryKnowledge {
                known_top: 1,
                known_bottom: 0,
            },
        )
        .unwrap(),
        battlefield: BattlefieldZone::new(vec![chip, permanent(&cards, 2, "Battered Golem")]),
        mana: ManaPool {
            blue: 1,
            ..ManaPool::default()
        },
        ..TrueState::default()
    };

    let bridge = build(state, &cards);
    assert!(bridge.candidates().iter().any(|candidate| {
        matches!(
            bridge.resolve(candidate.token),
            Some(Action::CastTargetedLibraryTop { card, .. }) if *card == knack
        )
    }));
}

#[test]
fn targeted_urza_permission_is_visible_to_policy_bridge_without_mana() {
    let cards = CurrentCardDatabase::load().unwrap();
    let helix = card(&cards, "Retraction Helix");
    let state = TrueState {
        turn: 1,
        phase: Phase::EndStep,
        window: Window::Priority,
        exile: CardZone::new(vec![helix]),
        battlefield: BattlefieldZone::new(vec![permanent(&cards, 10, "Battered Golem")]),
        urza_permissions: vec![UrzaPermission {
            permission_id: PermissionId(1),
            card: helix,
            expires_turn: 1,
            free_cast: true,
            source: SourceRef {
                object_id: None,
                card: cards.commander_card(),
            },
        }],
        ..TrueState::default()
    };

    let bridge = build(state, &cards);
    assert!(bridge.candidates().iter().any(|candidate| {
        matches!(
            bridge.resolve(candidate.token),
            Some(Action::PlayUrzaPermissionTargeted {
                permission_slot: 0,
                ..
            })
        )
    }));
}
