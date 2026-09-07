from pathlib import Path

path = Path("rust/crates/urza-rules/src/lib.rs")
text = path.read_text()

# Keep only concrete lifecycle repairs. Knack with an incoming attachment
# remains intentionally deferred by activate_granted_knack_bounce.
top_old = '''    let permanent = permanents.remove(index);\n    state.battlefield = BattlefieldZone::new(permanents);\n    if permanent.token {\n        return Ok(());\n    }\n'''
top_delay_repair = '''    let permanent = permanents.remove(index);\n    state.battlefield = BattlefieldZone::new(permanents);\n    state.delayed_events.retain(|event| {\n        !matches!(\n            event,\n            DelayedEvent::ChromeCopySacrifice {\n                object: delayed,\n                ..\n            } if *delayed == object_id\n        )\n    });\n    if permanent.token {\n        return Ok(());\n    }\n'''
top_attachment_repair = '''    let permanent = permanents.remove(index);\n    let mut attached_non_token_cards = Vec::new();\n    permanents.retain(|candidate| {\n        if candidate.attached_to == Some(object_id) {\n            if !candidate.token {\n                attached_non_token_cards.push(candidate.card);\n            }\n            false\n        } else {\n            true\n        }\n    });\n    state.battlefield = BattlefieldZone::new(permanents);\n    for card in attached_non_token_cards {\n        state.graveyard.insert(card);\n    }\n    state.delayed_events.retain(|event| {\n        !matches!(\n            event,\n            DelayedEvent::ChromeCopySacrifice {\n                object: delayed,\n                ..\n            } if *delayed == object_id\n        )\n    });\n    if permanent.token {\n        return Ok(());\n    }\n'''
if top_attachment_repair not in text:
    if top_delay_repair in text:
        text = text.replace(top_delay_repair, top_attachment_repair, 1)
    elif top_old in text:
        text = text.replace(top_old, top_attachment_repair, 1)
    else:
        raise SystemExit("expected Top-return lifecycle block was not found")

knack_original = '''    let removed = permanents.remove(index);\n    state.battlefield = BattlefieldZone::new(permanents);\n    state.delayed_events.retain(|event| {\n        !matches!(event, DelayedEvent::ChromeCopySacrifice { object, .. } if *object == object_id)\n    });\n    if !removed.token {\n        state.hand.insert(removed.card);\n    }\n'''
knack_broad = '''    let removed = permanents.remove(index);\n    let mut attached_non_token_cards = Vec::new();\n    permanents.retain(|candidate| {\n        if candidate.attached_to == Some(object_id) {\n            if !candidate.token {\n                attached_non_token_cards.push(candidate.card);\n            }\n            false\n        } else {\n            true\n        }\n    });\n    state.battlefield = BattlefieldZone::new(permanents);\n    for card in attached_non_token_cards {\n        state.graveyard.insert(card);\n    }\n    state.delayed_events.retain(|event| {\n        !matches!(event, DelayedEvent::ChromeCopySacrifice { object, .. } if *object == object_id)\n    });\n    if !removed.token {\n        state.hand.insert(removed.card);\n    }\n'''
if knack_broad in text:
    text = text.replace(knack_broad, knack_original, 1)
elif knack_original not in text:
    raise SystemExit("expected Knack deferred-boundary resolver block was not found")

# Remove the provisional Knack regression if an earlier helper ever inserted it.
start = text.find('    #[test]\n    fn knack_bounce_moves_attached_aura_to_graveyard_when_target_leaves() {')
if start != -1:
    next_test = text.find('    #[test]\n', start + 12)
    if next_test == -1:
        raise SystemExit("could not find test following provisional Knack regression")
    text = text[:start] + text[next_test:]

sacrifice_old = '''    let permanent = permanents.remove(index);\n    state.battlefield = BattlefieldZone::new(permanents);\n    if !permanent.token {\n        state.graveyard.insert(permanent.card);\n    }\n    state.delayed_events.retain(|event| {\n'''
sacrifice_repair = '''    let permanent = permanents.remove(index);\n    for candidate in &mut permanents {\n        if candidate.attached_to == Some(object)\n            && candidate.mode == PermanentMode::RealityChipAttached\n        {\n            candidate.mode = PermanentMode::RealityChipCreature;\n            candidate.attached_to = None;\n        }\n    }\n    let mut attached_non_token_cards = Vec::new();\n    permanents.retain(|candidate| {\n        if candidate.attached_to == Some(object) {\n            if !candidate.token {\n                attached_non_token_cards.push(candidate.card);\n            }\n            false\n        } else {\n            true\n        }\n    });\n    state.battlefield = BattlefieldZone::new(permanents);\n    for card in attached_non_token_cards {\n        state.graveyard.insert(card);\n    }\n    if !permanent.token {\n        state.graveyard.insert(permanent.card);\n    }\n    state.delayed_events.retain(|event| {\n'''
if sacrifice_repair not in text:
    if text.count(sacrifice_old) != 1:
        raise SystemExit(f"expected one sacrifice lifecycle block, found {text.count(sacrifice_old)}")
    text = text.replace(sacrifice_old, sacrifice_repair, 1)

marker = '''    #[test]\n    fn generic_scry_observes_before_top_bottom_choice() {\n'''
chrome_sacrifice_test = '''    #[test]\n    fn chrome_copy_mandatory_sacrifice_resolves_attachments() {\n        let cards = TestCards::r4();\n        let mut copied_golem = artifact_permanent(1, GOLEM);\n        copied_golem.token = true;\n        let mut aura = artifact_permanent(2, POWER_ARTIFACT);\n        aura.attached_to = Some(ObjectId(1));\n        let mut chip = artifact_permanent(3, REALITY_CHIP);\n        chip.mode = PermanentMode::RealityChipAttached;\n        chip.attached_to = Some(ObjectId(1));\n        let mut state = TrueState {\n            turn: 6,\n            phase: Phase::EndStep,\n            window: Window::Resolving,\n            battlefield: BattlefieldZone::new(vec![copied_golem, aura, chip]),\n            delayed_events: vec![DelayedEvent::ChromeCopySacrifice {\n                object: ObjectId(1),\n                card: GOLEM,\n                due_turn: 6,\n            }],\n            ..TrueState::default()\n        };\n        state.validate().unwrap();\n\n        resolve_chrome_dome_sacrifice(\n            &mut state,\n            &cards,\n            SourceRef {\n                object_id: Some(ObjectId(1)),\n                card: GOLEM,\n            },\n        )\n        .unwrap();\n\n        assert!(state.battlefield.get(ObjectId(1)).is_none());\n        assert!(state.battlefield.get(ObjectId(2)).is_none());\n        assert!(state.graveyard.cards().contains(&POWER_ARTIFACT));\n        let chip = state.battlefield.get(ObjectId(3)).unwrap();\n        assert_eq!(chip.card, REALITY_CHIP);\n        assert_eq!(chip.mode, PermanentMode::RealityChipCreature);\n        assert_eq!(chip.attached_to, None);\n        assert!(state.delayed_events.is_empty());\n        assert_eq!(state.window, Window::Priority);\n        state.validate().unwrap();\n    }\n\n'''
if "fn chrome_copy_mandatory_sacrifice_resolves_attachments()" not in text:
    if text.count(marker) != 1:
        raise SystemExit(f"expected one test insertion marker, found {text.count(marker)}")
    text = text.replace(marker, chrome_sacrifice_test + marker, 1)

path.write_text(text)
