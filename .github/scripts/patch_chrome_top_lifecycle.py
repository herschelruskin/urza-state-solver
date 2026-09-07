from pathlib import Path

path = Path("rust/crates/urza-rules/src/lib.rs")
text = path.read_text()

# Keep only the two concrete Top lifecycle repairs. Knack with an incoming
# attachment remains intentionally deferred by activate_granted_knack_bounce.
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
knack_corrected = '''    let removed = permanents.remove(index);\n    for candidate in &mut permanents {\n        if candidate.attached_to == Some(object_id)\n            && cards\n                .profile(candidate.card)\n                .is_some_and(|profile| profile.utility == UtilityKind::RealityChip)\n        {\n            candidate.mode = PermanentMode::RealityChipCreature;\n            candidate.attached_to = None;\n        }\n    }\n    let mut attached_non_token_cards = Vec::new();\n    permanents.retain(|candidate| {\n        if candidate.attached_to == Some(object_id) {\n            if !candidate.token {\n                attached_non_token_cards.push(candidate.card);\n            }\n            false\n        } else {\n            true\n        }\n    });\n    state.battlefield = BattlefieldZone::new(permanents);\n    for card in attached_non_token_cards {\n        state.graveyard.insert(card);\n    }\n    state.delayed_events.retain(|event| {\n        !matches!(event, DelayedEvent::ChromeCopySacrifice { object, .. } if *object == object_id)\n    });\n    if !removed.token {\n        state.hand.insert(removed.card);\n    }\n'''
if knack_corrected in text:
    text = text.replace(knack_corrected, knack_original, 1)
elif knack_broad in text:
    text = text.replace(knack_broad, knack_original, 1)
elif knack_original not in text:
    raise SystemExit("expected Knack deferred-boundary resolver block was not found")

# Remove either provisional Knack regression; that path is deliberately not a
# public legal action while AttachedBounceDeferred is part of the frozen rules.
start = text.find('    #[test]\n    fn knack_bounce_moves_attached_aura_to_graveyard_when_target_leaves() {')
if start != -1:
    next_test = text.find('    #[test]\n', start + 12)
    if next_test == -1:
        raise SystemExit("could not find test following provisional Knack regression")
    text = text[:start] + text[next_test:]

path.write_text(text)
