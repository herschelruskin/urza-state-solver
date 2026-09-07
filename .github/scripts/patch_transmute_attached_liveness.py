from pathlib import Path

path = Path("rust/crates/urza-policy-bridge/src/lib.rs")
text = path.read_text()

anchor = '''    actions.retain(|action| {\n        let transmute_cast = match action {\n'''
replacement = '''    let has_supported_transmute_sacrifice = artifact_classes.iter().any(|class| {\n        let representative = class.objects[0];\n        !state\n            .battlefield\n            .permanents()\n            .iter()\n            .any(|permanent| permanent.attached_to == Some(representative))\n    });\n\n    actions.retain(|action| {\n        let transmute_cast = match action {\n'''
if "let has_supported_transmute_sacrifice =" not in text:
    if anchor not in text:
        raise SystemExit("transmute root-action filter anchor not found")
    text = text.replace(anchor, replacement, 1)

old_tail = '''        !transmute_cast || !artifact_classes.is_empty()\n'''
new_tail = '''        !transmute_cast || has_supported_transmute_sacrifice\n'''
if old_tail in text:
    text = text.replace(old_tail, new_tail, 1)
elif new_tail not in text:
    raise SystemExit("transmute root-action filter tail not found")

test_name = "transmute_with_only_attached_artifact_is_not_exposed_as_a_dead_end_root"
if test_name not in text:
    existing = '    #[test]\n    fn transmute_without_a_sacrifice_is_not_exposed_as_a_dead_end_root() {'
    start = text.find(existing)
    if start == -1:
        raise SystemExit("existing transmute dead-end regression not found")
    next_test = text.find('    #[test]\n', start + len(existing))
    if next_test == -1:
        raise SystemExit("test insertion point not found")
    regression = '''    #[test]\n    fn transmute_with_only_attached_artifact_is_not_exposed_as_a_dead_end_root() {\n        let cards = R4CardDatabase::load().unwrap();\n        let transmute = cards.card_id_by_name("Transmute Artifact").unwrap();\n        let sol_ring = cards.card_id_by_name("Sol Ring").unwrap();\n        let power_artifact = cards.card_id_by_name("Power Artifact").unwrap();\n        let mana_vault = cards.card_id_by_name("Mana Vault").unwrap();\n\n        let mut aura = permanent(9, power_artifact);\n        aura.attached_to = Some(ObjectId(8));\n        let mut state = priority_state();\n        state.hand = CardZone::new(vec![transmute]);\n        state.mana = ManaPool {\n            blue: 2,\n            ..ManaPool::default()\n        };\n        state.battlefield = BattlefieldZone::new(vec![permanent(8, sol_ring), aura]);\n        state.validate().unwrap();\n\n        let bridge = CandidateBridge::build(&state, &cards).unwrap();\n        assert!(!bridge.candidates().iter().any(|candidate| matches!(\n            bridge.resolve(candidate.token),\n            Some(Action::CastFromHand { card, .. }) if *card == transmute\n        )));\n\n        let mut permanents = state.battlefield.permanents().to_vec();\n        permanents.push(permanent(10, mana_vault));\n        state.battlefield = BattlefieldZone::new(permanents);\n        state.validate().unwrap();\n        let bridge = CandidateBridge::build(&state, &cards).unwrap();\n        assert!(bridge.candidates().iter().any(|candidate| matches!(\n            bridge.resolve(candidate.token),\n            Some(Action::CastFromHand { card, .. }) if *card == transmute\n        )));\n    }\n\n'''
    text = text[:next_test] + regression + text[next_test:]

path.write_text(text)
