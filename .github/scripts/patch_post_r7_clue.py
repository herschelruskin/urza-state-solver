#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RULES = ROOT / "rust/crates/urza-rules/src/lib.rs"
BRIDGE = ROOT / "rust/crates/urza-policy-bridge/src/lib.rs"
DIAGNOSTIC = ROOT / "rust/crates/urza-mulligan/src/bin/post-r7-engine-tutor-diagnostic.rs"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def patch_rules() -> None:
    text = RULES.read_text()
    text = replace_once(
        text,
        'pub const POST_R7_RULES_VERSION: &str = "post_r7_card_advantage_v2_uthros";',
        'pub const POST_R7_RULES_VERSION: &str = "post_r7_card_advantage_v3_clue";',
        "rules version",
    )
    text = replace_once(
        text,
        'pub const ABILITY_UTHROS_ARTIFACT_DRAW: AbilityId = AbilityId(0x0411);',
        'pub const ABILITY_UTHROS_ARTIFACT_DRAW: AbilityId = AbilityId(0x0411);\n'
        'pub const ABILITY_CLUE_DRAW: AbilityId = AbilityId(0x0412);',
        "Clue ability id",
    )
    text = replace_once(
        text,
        '''    ActivateUthrosStation {
        source: ObjectId,
        creature: CanonicalObjectId,
    },
    ActivateUrzaSpin {
''',
        '''    ActivateUthrosStation {
        source: ObjectId,
        creature: CanonicalObjectId,
    },
    ActivateClueDraw {
        source: ObjectId,
        payment: ManaPayment,
    },
    ActivateUrzaSpin {
''',
        "Clue action enum",
    )
    text = replace_once(
        text,
        '''        Action::ActivateUthrosStation { source, creature } => {
            activate_uthros_station(state, cards, source, creature)?;
            Transition::default()
        }
        Action::ActivateUrzaSpin { source, payment } => {
''',
        '''        Action::ActivateUthrosStation { source, creature } => {
            activate_uthros_station(state, cards, source, creature)?;
            Transition::default()
        }
        Action::ActivateClueDraw { source, payment } => {
            activate_clue_draw(state, cards, source, payment)?;
            Transition::default()
        }
        Action::ActivateUrzaSpin { source, payment } => {
''',
        "Clue apply action",
    )

    marker = '''fn activate_urza_spin<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    source: ObjectId,
    payment: ManaPayment,
) -> Result<(), RuleError> {
'''
    clue_activate = '''fn activate_clue_draw<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    source: ObjectId,
    payment: ManaPayment,
) -> Result<(), RuleError> {
    ensure_priority(state)?;
    ensure_no_pending_decision(state)?;
    let permanent = battlefield_permanent(state, source)?.clone();
    if cards.clue_token_card() != Some(permanent.card) {
        return Err(RuleError::UnsupportedCardMechanic(permanent.card));
    }
    if state
        .battlefield
        .permanents()
        .iter()
        .any(|candidate| candidate.attached_to == Some(source))
    {
        return Err(RuleError::AttachedSacrificeDeferred(source));
    }
    let cost = ManaCost {
        generic: 2,
        ..ManaCost::default()
    };
    validate_payment(state.mana, payment, cost)?;

    // Mana payment and sacrifice are activation costs. Validate every deferred
    // boundary first, then commit both costs before putting the draw ability on
    // the stack. The common sacrifice path owns token/attachment lifecycle.
    spend_payment(&mut state.mana, payment);
    sacrifice_artifact(state, source)?;
    state.stack.push(StackObject::ActivatedAbility {
        source: SourceRef {
            object_id: Some(source),
            card: permanent.card,
        },
        ability: ABILITY_CLUE_DRAW,
        parameter: None,
    });
    state.window = Window::Priority;
    Ok(())
}

'''
    text = replace_once(text, marker, clue_activate + marker, "Clue activation function")

    old_dispatch = '''        StackObject::ControlledTrigger {
            source,
            ability: ABILITY_UTHROS_ARTIFACT_DRAW,
        } => {
            state.stack.pop();
            resolve_uthros_artifact_draw(state, cards, source)
        }
        StackObject::ActivatedAbility {
            source,
            ability: ABILITY_URZA_SPIN,
'''
    new_dispatch = '''        StackObject::ControlledTrigger {
            source,
            ability: ABILITY_UTHROS_ARTIFACT_DRAW,
        } => {
            state.stack.pop();
            resolve_uthros_artifact_draw(state, cards, source)
        }
        StackObject::ActivatedAbility {
            ability: ABILITY_CLUE_DRAW,
            ..
        } => {
            state.stack.pop();
            resolve_clue_draw(state)
        }
        StackObject::ActivatedAbility {
            source,
            ability: ABILITY_URZA_SPIN,
'''
    text = replace_once(text, old_dispatch, new_dispatch, "Clue resolver dispatch")

    resolve_marker = '''fn resolve_urza_spin(
    state: &mut TrueState,
    source: SourceRef,
    rng: GameRngContext,
) -> Result<Transition, RuleError> {
'''
    clue_resolve = '''fn resolve_clue_draw(state: &mut TrueState) -> Result<Transition, RuleError> {
    let drawn = draw_cards(state, 1)?;
    state.window = Window::Priority;
    Ok(Transition {
        observations: if drawn.is_empty() {
            Vec::new()
        } else {
            vec![RulesObservation::CardsDrawn(drawn)]
        },
    })
}

'''
    text = replace_once(text, resolve_marker, clue_resolve + resolve_marker, "Clue resolve function")

    if "mod post_r7_clue_tests" in text:
        raise SystemExit("Clue rules tests already present")
    text += r'''

#[cfg(test)]
mod post_r7_clue_tests {
    use std::collections::BTreeMap;

    use super::*;
    use urza_core::CardZone;

    const CLUE: CardDefId = CardDefId(600);
    const DRAW: CardDefId = CardDefId(601);
    const AURA: CardDefId = CardDefId(602);
    const URZA_DUMMY: CardDefId = CardDefId(603);
    const CONSTRUCT_DUMMY: CardDefId = CardDefId(604);

    #[derive(Default)]
    struct ClueCards {
        profiles: BTreeMap<CardDefId, CardProfile>,
    }

    impl ClueCards {
        fn new() -> Self {
            let mut profiles = BTreeMap::new();
            profiles.insert(
                CLUE,
                CardProfile {
                    card: CLUE,
                    role: R2CardRole::ArtifactPermanent,
                    battlefield_face: CardFace::Front,
                    is_artifact: true,
                    ..CardProfile::default()
                },
            );
            Self { profiles }
        }
    }

    impl CardDatabase for ClueCards {
        fn profile(&self, card: CardDefId) -> Option<CardProfile> {
            self.profiles.get(&card).copied()
        }

        fn commander_card(&self) -> CardDefId {
            URZA_DUMMY
        }

        fn urza_construct_token_card(&self) -> CardDefId {
            CONSTRUCT_DUMMY
        }

        fn clue_token_card(&self) -> Option<CardDefId> {
            Some(CLUE)
        }
    }

    fn permanent(object: u32, card: CardDefId, token: bool) -> PermanentState {
        PermanentState {
            object_id: ObjectId(object),
            card,
            face: CardFace::Front,
            tapped: false,
            summoning_sick: false,
            token,
            counters: CounterState::default(),
            mode: PermanentMode::Normal,
            attached_to: None,
            granted_ability: None,
        }
    }

    #[test]
    fn clue_activation_commits_two_mana_and_sacrifice_before_drawing_on_resolution() {
        let cards = ClueCards::new();
        let mut state = TrueState {
            turn: 3,
            phase: Phase::PrecombatMain,
            window: Window::Priority,
            library: TrueLibrary::unknown(vec![DRAW]),
            battlefield: BattlefieldZone::new(vec![permanent(1, CLUE, true)]),
            mana: ManaPool {
                colorless: 2,
                ..ManaPool::default()
            },
            ..TrueState::default()
        };

        apply_action(
            &mut state,
            &cards,
            Action::ActivateClueDraw {
                source: ObjectId(1),
                payment: ManaPayment {
                    colorless: 2,
                    ..ManaPayment::default()
                },
            },
        )
        .unwrap();

        assert_eq!(state.mana, ManaPool::default());
        assert!(state.battlefield.get(ObjectId(1)).is_none());
        assert!(state.graveyard.cards().is_empty(), "sacrificed Clue token must cease to exist");
        assert!(state.hand.is_empty());
        assert!(matches!(
            state.stack.last(),
            Some(StackObject::ActivatedAbility {
                ability: ABILITY_CLUE_DRAW,
                ..
            })
        ));

        let resolved = apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        assert_eq!(state.hand, CardZone::new(vec![DRAW]));
        assert_eq!(
            resolved.observations,
            vec![RulesObservation::CardsDrawn(vec![DRAW])]
        );
        state.validate().unwrap();
    }

    #[test]
    fn attached_clue_preserves_existing_player_chosen_sacrifice_deferral() {
        let cards = ClueCards::new();
        let clue = permanent(1, CLUE, true);
        let mut aura = permanent(2, AURA, false);
        aura.attached_to = Some(ObjectId(1));
        let mut state = TrueState {
            turn: 3,
            phase: Phase::PrecombatMain,
            window: Window::Priority,
            battlefield: BattlefieldZone::new(vec![clue, aura]),
            mana: ManaPool {
                colorless: 2,
                ..ManaPool::default()
            },
            ..TrueState::default()
        };
        state.validate().unwrap();

        let before = state.clone();
        let error = apply_action(
            &mut state,
            &cards,
            Action::ActivateClueDraw {
                source: ObjectId(1),
                payment: ManaPayment {
                    colorless: 2,
                    ..ManaPayment::default()
                },
            },
        )
        .unwrap_err();
        assert_eq!(error, RuleError::AttachedSacrificeDeferred(ObjectId(1)));
        assert_eq!(state, before, "deferred activation must not partially pay costs");
    }
}
'''
    RULES.write_text(text)


def patch_bridge() -> None:
    text = BRIDGE.read_text()
    text = replace_once(
        text,
        '    LandEntryChoice, ManaPayment, R2CardRole, SpecialSearchKind, SpellEffectKind, UtilityKind,\n',
        '    LandEntryChoice, ManaCost, ManaPayment, R2CardRole, SpecialSearchKind, SpellEffectKind, UtilityKind,\n',
        "bridge ManaCost import",
    )
    text = replace_once(
        text,
        'pub const CANDIDATE_BRIDGE_VERSION: &str = "post_r7_public_candidate_bridge_v2_uthros";\n'
        'pub const ORDINARY_ACTION_FAMILY_COUNT: usize = 28;',
        'pub const CANDIDATE_BRIDGE_VERSION: &str = "post_r7_public_candidate_bridge_v3_clue";\n'
        'pub const ORDINARY_ACTION_FAMILY_COUNT: usize = 29;',
        "bridge version/count",
    )
    text = replace_once(
        text,
        'const KIND_UTHROS_STATION: u16 = 36;',
        'const KIND_UTHROS_STATION: u16 = 36;\nconst KIND_CLUE_DRAW: u16 = 37;',
        "Clue bridge kind",
    )

    generation_anchor = '''        if profile.is_artifact {
            actions.push(Action::ActivateUrzaArtifactMana {
                artifact: representative,
            });
        }

        if profile.engine == EngineKind::GrindingStation {
'''
    generation_new = '''        if profile.is_artifact {
            actions.push(Action::ActivateUrzaArtifactMana {
                artifact: representative,
            });
        }
        if cards.clue_token_card() == Some(class.card) {
            for payment in enumerate_payments(
                information.mana,
                ManaCost {
                    generic: 2,
                    ..ManaCost::default()
                },
            ) {
                actions.push(Action::ActivateClueDraw {
                    source: representative,
                    payment,
                });
            }
        }

        if profile.engine == EngineKind::GrindingStation {
'''
    text = replace_once(text, generation_anchor, generation_new, "Clue candidate generation")

    classify_anchor = '''        | Action::ActivateFortuneTellersTalentLevel { .. }
        | Action::ActivateOneRingDraw { .. }
        | Action::ActivateUthrosStation { .. } => PolicyActionClass::ActivateAbility,
'''
    classify_new = '''        | Action::ActivateFortuneTellersTalentLevel { .. }
        | Action::ActivateOneRingDraw { .. }
        | Action::ActivateUthrosStation { .. }
        | Action::ActivateClueDraw { .. } => PolicyActionClass::ActivateAbility,
'''
    text = replace_once(text, classify_anchor, classify_new, "Clue action class")

    key_anchor = '''        Action::ActivateUthrosStation { source, creature } => {
            let mut out = source_key(
                KIND_UTHROS_STATION,
                *source,
                state,
                object_classes,
                Vec::new(),
            )?;
            out.target = Some(*creature);
            out
        }
        Action::ActivateUrzaSpin { source, payment } => source_key(
'''
    key_new = '''        Action::ActivateUthrosStation { source, creature } => {
            let mut out = source_key(
                KIND_UTHROS_STATION,
                *source,
                state,
                object_classes,
                Vec::new(),
            )?;
            out.target = Some(*creature);
            out
        }
        Action::ActivateClueDraw { source, payment } => source_key(
            KIND_CLUE_DRAW,
            *source,
            state,
            object_classes,
            payment_detail(*payment),
        )?,
        Action::ActivateUrzaSpin { source, payment } => source_key(
'''
    text = replace_once(text, key_anchor, key_new, "Clue public key")

    text = replace_once(
        text,
        '        assert_eq!(ORDINARY_ACTION_FAMILY_COUNT, 28);',
        '        assert_eq!(ORDINARY_ACTION_FAMILY_COUNT, 29);',
        "bridge family regression",
    )

    if "mod post_r7_clue_bridge_tests" in text:
        raise SystemExit("Clue bridge tests already present")
    text += r'''

#[cfg(test)]
mod post_r7_clue_bridge_tests {
    use super::*;
    use urza_cards::{CLUE_TOKEN_CARD_ID, PostR7CardDatabase};
    use urza_core::{
        BattlefieldZone, CardFace, CounterState, PermanentMode, PermanentState, Phase, TrueState,
        Window,
    };

    fn permanent(object: u32, card: CardDefId, token: bool) -> PermanentState {
        PermanentState {
            object_id: ObjectId(object),
            card,
            face: CardFace::Front,
            tapped: false,
            summoning_sick: false,
            token,
            counters: CounterState::default(),
            mode: PermanentMode::Normal,
            attached_to: None,
            granted_ability: None,
        }
    }

    fn clue_state(mana: u16) -> TrueState {
        TrueState {
            turn: 3,
            phase: Phase::PrecombatMain,
            window: Window::Priority,
            battlefield: BattlefieldZone::new(vec![permanent(1, CLUE_TOKEN_CARD_ID, true)]),
            mana: ManaPool {
                colorless: mana,
                ..ManaPool::default()
            },
            ..TrueState::default()
        }
    }

    #[test]
    fn post_r7_bridge_exposes_clue_cash_in_only_with_two_mana() {
        let cards = PostR7CardDatabase::load().unwrap();
        let state = clue_state(2);
        let bridge = CandidateBridge::build(&state, &cards).unwrap();
        let clue = bridge
            .candidates()
            .iter()
            .filter(|candidate| candidate.key.kind == KIND_CLUE_DRAW)
            .collect::<Vec<_>>();
        assert_eq!(clue.len(), 1);
        assert_eq!(clue[0].class, PolicyActionClass::ActivateAbility);
        assert!(matches!(
            bridge.resolve(clue[0].token),
            Some(Action::ActivateClueDraw { .. })
        ));

        let short = clue_state(1);
        let bridge = CandidateBridge::build(&short, &cards).unwrap();
        assert!(
            bridge
                .candidates()
                .iter()
                .all(|candidate| candidate.key.kind != KIND_CLUE_DRAW)
        );
    }

    #[test]
    fn attached_clue_is_filtered_from_public_candidate_surface() {
        let cards = PostR7CardDatabase::load().unwrap();
        let mut state = clue_state(2);
        let mut aura = permanent(2, cards.card_id_by_name("Power Artifact").unwrap(), false);
        aura.attached_to = Some(ObjectId(1));
        let mut permanents = state.battlefield.permanents().to_vec();
        permanents.push(aura);
        state.battlefield = BattlefieldZone::new(permanents);
        state.validate().unwrap();

        let bridge = CandidateBridge::build(&state, &cards).unwrap();
        assert!(
            bridge
                .candidates()
                .iter()
                .all(|candidate| candidate.key.kind != KIND_CLUE_DRAW)
        );
    }
}
'''
    BRIDGE.write_text(text)


def patch_diagnostic() -> None:
    text = DIAGNOSTIC.read_text()
    text = replace_once(
        text,
        'use urza_cards::CurrentCardDatabase;',
        'use urza_cards::{CLUE_TOKEN_CARD_ID, CurrentCardDatabase};',
        "diagnostic clue token import",
    )
    text = replace_once(
        text,
        'const DIAGNOSTIC_VERSION: &str = "post_r7_engine_tutor_diagnostic_v1";\n'
        'const KIND_CHOOSE_SEARCH_TARGET: u16 = 28;',
        'const DIAGNOSTIC_VERSION: &str = "post_r7_engine_tutor_diagnostic_v2_clue";\n'
        'const KIND_CHOOSE_SEARCH_TARGET: u16 = 28;\n'
        'const KIND_CLUE_DRAW: u16 = 37;',
        "diagnostic version/kind",
    )
    text = replace_once(
        text,
        '''#[derive(Debug, Default, Clone)]
struct TutorStats {
''',
        '''#[derive(Debug, Default, Clone)]
struct ClueStats {
    visible_decisions: u64,
    candidate_decisions: u64,
    selected_decisions: u64,
}

#[derive(Debug, Default, Clone)]
struct TutorStats {
''',
        "Clue diagnostic stats",
    )
    text = replace_once(
        text,
        '    let mut tutor_stats = BTreeMap::<String, TutorStats>::new();',
        '    let mut tutor_stats = BTreeMap::<String, TutorStats>::new();\n'
        '    let mut clue_stats = ClueStats::default();',
        "Clue stats init",
    )

    tutor_anchor = '''            let tutor_candidates = bridge
                .candidates()
                .iter()
                .filter(|candidate| candidate.key.kind == KIND_CHOOSE_SEARCH_TARGET)
                .collect::<Vec<_>>();
'''
    clue_scan = '''            let clue_visible = information
                .battlefield
                .iter()
                .any(|permanent| permanent.card == CLUE_TOKEN_CARD_ID);
            if clue_visible {
                clue_stats.visible_decisions += 1;
            }
            let clue_candidates = bridge
                .candidates()
                .iter()
                .filter(|candidate| candidate.key.kind == KIND_CLUE_DRAW)
                .count();
            if clue_candidates != 0 {
                clue_stats.candidate_decisions += 1;
                if step.key.kind == KIND_CLUE_DRAW {
                    clue_stats.selected_decisions += 1;
                }
            }

'''
    text = replace_once(text, tutor_anchor, clue_scan + tutor_anchor, "Clue diagnostic scan")

    output_anchor = '''    for (source, stats) in tutor_stats {
'''
    clue_output = '''    println!(
        "CLUE_SUMMARY\\tvisible_decisions={}\\tcandidate_decisions={}\\tselected_decisions={}",
        clue_stats.visible_decisions,
        clue_stats.candidate_decisions,
        clue_stats.selected_decisions,
    );
    for (source, stats) in tutor_stats {
'''
    text = replace_once(text, output_anchor, clue_output, "Clue diagnostic output")
    DIAGNOSTIC.write_text(text)


patch_rules()
patch_bridge()
patch_diagnostic()
print("post-R7 Gadgeteer/Clue cash-in slice patched")
