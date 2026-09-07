from pathlib import Path

path = Path("rust/crates/urza-rules/src/lib.rs")
text = path.read_text()

old = '''    let permanent = permanents.remove(index);\n    state.battlefield = BattlefieldZone::new(permanents);\n    if permanent.token {\n        return Ok(());\n    }\n'''
new = '''    let permanent = permanents.remove(index);\n    state.battlefield = BattlefieldZone::new(permanents);\n    state.delayed_events.retain(|event| {\n        !matches!(\n            event,\n            DelayedEvent::ChromeCopySacrifice {\n                object: delayed,\n                ..\n            } if *delayed == object_id\n        )\n    });\n    if permanent.token {\n        return Ok(());\n    }\n'''

if new not in text:
    if text.count(old) != 1:
        raise SystemExit(f"expected one Top-return lifecycle match, found {text.count(old)}")
    text = text.replace(old, new, 1)

marker = '''    #[test]\n    fn generic_scry_observes_before_top_bottom_choice() {\n'''
test = '''    #[test]\n    fn chrome_copy_top_draw_clears_delayed_sacrifice_when_token_leaves() {\n        let cards = TestCards::r4();\n        let mut copied_top = artifact_permanent(7, TOP);\n        copied_top.token = true;\n        let mut state = TrueState {\n            turn: 5,\n            phase: Phase::Upkeep,\n            window: Window::Priority,\n            library: TrueLibrary::unknown(vec![TARGET_A, TARGET_B]),\n            battlefield: BattlefieldZone::new(vec![copied_top]),\n            delayed_events: vec![DelayedEvent::ChromeCopySacrifice {\n                object: ObjectId(7),\n                card: TOP,\n                due_turn: 5,\n            }],\n            ..TrueState::default()\n        };\n        state.validate().unwrap();\n\n        apply_action(\n            &mut state,\n            &cards,\n            Action::ActivateTopDraw {\n                source: ObjectId(7),\n            },\n        )\n        .unwrap();\n        let transition = apply_action(&mut state, &cards, Action::PassPriority).unwrap();\n\n        assert_eq!(\n            transition.observations,\n            vec![RulesObservation::CardsDrawn(vec![TARGET_A])]\n        );\n        assert_eq!(state.hand.cards(), &[TARGET_A]);\n        assert_eq!(state.library.cards(), &[TARGET_B]);\n        assert!(state.battlefield.get(ObjectId(7)).is_none());\n        assert!(state.delayed_events.is_empty());\n        assert!(state.stack.is_empty());\n        assert_eq!(state.window, Window::Priority);\n        state.validate().unwrap();\n    }\n\n'''

if "fn chrome_copy_top_draw_clears_delayed_sacrifice_when_token_leaves()" not in text:
    if text.count(marker) != 1:
        raise SystemExit(f"expected one test insertion marker, found {text.count(marker)}")
    text = text.replace(marker, test + marker, 1)

path.write_text(text)
