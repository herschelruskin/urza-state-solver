use urza_cards::CurrentCardDatabase;
use urza_core::{
    BattlefieldZone, CardZone, CounterState, LibraryKnowledge, ManaPool, ObjectId, PermanentMode,
    PermanentState, PermissionId, Phase, SourceRef, StackObject, TrueLibrary, TrueState,
    UrzaPermission, Window,
};
use urza_info::observe;
use urza_rules::{Action, CardDatabase, ManaPayment, UtilityKind, apply_action};

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
        mode: match profile.utility {
            UtilityKind::RealityChip => PermanentMode::RealityChipCreature,
            UtilityKind::FortuneTellersTalent => PermanentMode::FortuneTellersTalentLevel1,
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

fn blue_one() -> ManaPayment {
    ManaPayment {
        blue: 1,
        ..ManaPayment::default()
    }
}

fn end_step_state(permanents: Vec<PermanentState>) -> TrueState {
    TrueState {
        turn: 1,
        phase: Phase::EndStep,
        window: Window::Priority,
        battlefield: BattlefieldZone::new(permanents),
        ..TrueState::default()
    }
}

#[test]
fn targeted_spell_uses_reality_chip_library_top_permission() {
    let cards = CurrentCardDatabase::load().unwrap();
    let knack = card(&cards, "Banishing Knack");
    let mut chip = permanent(&cards, 1, "The Reality Chip");
    chip.mode = PermanentMode::RealityChipAttached;
    chip.attached_to = Some(ObjectId(2));
    let mut state = end_step_state(vec![chip, permanent(&cards, 2, "Battered Golem")]);
    state.library = TrueLibrary::new(
        vec![knack],
        LibraryKnowledge {
            known_top: 1,
            known_bottom: 0,
        },
    )
    .unwrap();
    state.mana = ManaPool {
        blue: 1,
        ..ManaPool::default()
    };
    let target = canonical_for(&state, ObjectId(2));

    apply_action(
        &mut state,
        &cards,
        Action::CastTargetedLibraryTop {
            card: knack,
            target,
            payment: blue_one(),
        },
    )
    .unwrap();

    assert!(state.library.cards().is_empty());
    assert!(matches!(
        state.stack.last(),
        Some(StackObject::TargetedSpell { card, .. }) if *card == knack
    ));
    apply_action(&mut state, &cards, Action::PassPriority).unwrap();
    assert!(
        state
            .battlefield
            .get(ObjectId(2))
            .unwrap()
            .granted_ability
            .is_some()
    );
}

#[test]
fn targeted_spell_uses_fortune_tellers_talent_library_top_permission() {
    let cards = CurrentCardDatabase::load().unwrap();
    let helix = card(&cards, "Retraction Helix");
    let mut talent = permanent(&cards, 10, "Fortune Teller's Talent");
    talent.mode = PermanentMode::FortuneTellersTalentLevel2;
    let mut state = end_step_state(vec![talent, permanent(&cards, 11, "Battered Golem")]);
    state.library = TrueLibrary::new(
        vec![helix],
        LibraryKnowledge {
            known_top: 1,
            known_bottom: 0,
        },
    )
    .unwrap();
    state.mana = ManaPool {
        blue: 1,
        ..ManaPool::default()
    };
    state.spell_cast_this_turn = true;
    let target = canonical_for(&state, ObjectId(11));

    apply_action(
        &mut state,
        &cards,
        Action::CastTargetedLibraryTop {
            card: helix,
            target,
            payment: blue_one(),
        },
    )
    .unwrap();
    apply_action(&mut state, &cards, Action::PassPriority).unwrap();
    assert!(
        state
            .battlefield
            .get(ObjectId(11))
            .unwrap()
            .granted_ability
            .is_some()
    );
}

#[test]
fn targeted_spell_uses_urza_exile_permission_without_mana_payment() {
    let cards = CurrentCardDatabase::load().unwrap();
    let helix = card(&cards, "Retraction Helix");
    let mut state = end_step_state(vec![permanent(&cards, 20, "Battered Golem")]);
    state.exile = CardZone::new(vec![helix]);
    state.urza_permissions = vec![UrzaPermission {
        permission_id: PermissionId(7),
        card: helix,
        expires_turn: 1,
        free_cast: true,
        source: SourceRef {
            object_id: None,
            card: cards.commander_card(),
        },
    }];
    let target = canonical_for(&state, ObjectId(20));

    apply_action(
        &mut state,
        &cards,
        Action::PlayUrzaPermissionTargeted {
            permission_slot: 0,
            target,
        },
    )
    .unwrap();

    assert!(!state.exile.cards().contains(&helix));
    assert!(state.urza_permissions.is_empty());
    assert!(matches!(
        state.stack.last(),
        Some(StackObject::TargetedSpell { card, .. }) if *card == helix
    ));
    apply_action(&mut state, &cards, Action::PassPriority).unwrap();
    assert!(
        state
            .battlefield
            .get(ObjectId(20))
            .unwrap()
            .granted_ability
            .is_some()
    );
}
