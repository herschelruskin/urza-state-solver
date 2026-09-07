from pathlib import Path

path = Path("rust/crates/urza-rules/src/lib.rs")
text = path.read_text()

old = '''    let permanent = permanents.remove(index);\n    state.battlefield = BattlefieldZone::new(permanents);\n    if permanent.token {\n        return Ok(());\n    }\n'''
first_repair = '''    let permanent = permanents.remove(index);\n    state.battlefield = BattlefieldZone::new(permanents);\n    state.delayed_events.retain(|event| {\n        !matches!(\n            event,\n            DelayedEvent::ChromeCopySacrifice {\n                object: delayed,\n                ..\n            } if *delayed == object_id\n        )\n    });\n    if permanent.token {\n        return Ok(());\n    }\n'''
attachment_repair = '''    let permanent = permanents.remove(index);\n    let mut attached_non_token_cards = Vec::new();\n    permanents.retain(|candidate| {\n        if candidate.attached_to == Some(object_id) {\n            if !candidate.token {\n                attached_non_token_cards.push(candidate.card);\n            }\n            false\n        } else {\n            true\n        }\n    });\n    state.battlefield = BattlefieldZone::new(permanents);\n    for card in attached_non_token_cards {\n        state.graveyard.insert(card);\n    }\n    state.delayed_events.retain(|event| {\n        !matches!(\n            event,\n            DelayedEvent::ChromeCopySacrifice {\n                object: delayed,\n                ..\n            } if *delayed == object_id\n        )\n    });\n    if permanent.token {\n        return Ok(());\n    }\n'''

if attachment_repair not in text:
    if first_repair in text:
        text = text.replace(first_repair, attachment_repair, 1)
    elif old in text:
        text = text.replace(old, attachment_repair, 1)
    else:
        raise SystemExit("expected Top-return lifecycle block was not found")

marker = '''    #[test]\n    fn generic_scry_observes_before_top_bottom_choice() {\n'''
chrome_test = '''    #[test]\n    fn chrome_copy_top_draw_clears_delayed_sacrifice_when_token_leaves() {\n        let cards = TestCards::r4();\n        let mut copied_top = artifact_permanent(7, TOP);\n        copied_top.token = true;\n        let mut state = TrueState {\n            turn: 5,\n            phase: Phase::Upkeep,\n            window: Window::Priority,\n            library: TrueLibrary::unknown(vec![TARGET_A, TARGET_B]),\n            battlefield: BattlefieldZone::new(vec![copied_top]),\n            delayed_events: vec![DelayedEvent::ChromeCopySacrifice {\n                object: ObjectId(7),\n                card: TOP,\n                due_turn: 5,\n            }],\n            ..TrueState::default()\n        };\n        state.validate().unwrap();\n\n        apply_action(\n            &mut state,\n            &cards,\n            Action::ActivateTopDraw {\n                source: ObjectId(7),\n            },\n        )\n        .unwrap();\n        let transition = apply_action(&mut state, &cards, Action::PassPriority).unwrap();\n\n        assert_eq!(\n            transition.observations,\n            vec![RulesObservation::CardsDrawn(vec![TARGET_A])]\n        );\n        assert_eq!(state.hand.cards(), &[TARGET_A]);\n        assert_eq!(state.library.cards(), &[TARGET_B]);\n        assert!(state.battlefield.get(ObjectId(7)).is_none());\n        assert!(state.delayed_events.is_empty());\n        assert!(state.stack.is_empty());\n        assert_eq!(state.window, Window::Priority);\n        state.validate().unwrap();\n    }\n\n'''
aura_test = '''    #[test]\n    fn top_draw_moves_attached_aura_to_graveyard_when_top_leaves() {\n        let cards = TestCards::r4();\n        let top = artifact_permanent(1, TOP);\n        let mut aura = artifact_permanent(2, POWER_ARTIFACT);\n        aura.attached_to = Some(ObjectId(1));\n        let mut state = TrueState {\n            turn: 6,\n            phase: Phase::PrecombatMain,\n            window: Window::Priority,\n            library: TrueLibrary::unknown(vec![TARGET_A, TARGET_B]),\n            battlefield: BattlefieldZone::new(vec![top, aura]),\n            ..TrueState::default()\n        };\n        state.validate().unwrap();\n\n        apply_action(\n            &mut state,\n            &cards,\n            Action::ActivateTopDraw {\n                source: ObjectId(1),\n            },\n        )\n        .unwrap();\n        let transition = apply_action(&mut state, &cards, Action::PassPriority).unwrap();\n\n        assert_eq!(\n            transition.observations,\n            vec![RulesObservation::CardsDrawn(vec![TARGET_A])]\n        );\n        assert_eq!(state.library.cards(), &[TOP, TARGET_B]);\n        assert_eq!(state.library.known_top(), &[TOP]);\n        assert_eq!(state.graveyard.cards(), &[POWER_ARTIFACT]);\n        assert!(state.battlefield.get(ObjectId(1)).is_none());\n        assert!(state.battlefield.get(ObjectId(2)).is_none());\n        assert!(state.stack.is_empty());\n        state.validate().unwrap();\n    }\n\n'''

if "fn chrome_copy_top_draw_clears_delayed_sacrifice_when_token_leaves()" not in text:
    if text.count(marker) != 1:
        raise SystemExit(f"expected one test insertion marker, found {text.count(marker)}")
    text = text.replace(marker, chrome_test + marker, 1)

if "fn top_draw_moves_attached_aura_to_graveyard_when_top_leaves()" not in text:
    if text.count(marker) != 1:
        raise SystemExit(f"expected one test insertion marker, found {text.count(marker)}")
    text = text.replace(marker, aura_test + marker, 1)

path.write_text(text)
