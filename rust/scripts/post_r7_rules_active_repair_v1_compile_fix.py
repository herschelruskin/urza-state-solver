from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_once(path: str, old: str, new: str) -> None:
    file = ROOT / path
    text = file.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one match in {path}, got {count}: {old[:120]!r}")
    file.write_text(text.replace(old, new, 1))


replace_once(
    "rust/crates/urza-policy-bridge/src/lib.rs",
    "    LandEntryChoice, ManaCost, ManaPayment, R2CardRole, SpecialSearchKind, SpellEffectKind,\n",
    "    LandEntryChoice, ManaPayment, R2CardRole, SpecialSearchKind, SpellEffectKind,\n",
)

replace_once(
    "rust/crates/urza-cards/tests/post_r7_modeling_completeness_rules_active_repair_v1.rs",
    "    ABILITY_ARTIFICERS_ASSISTANT_SCRY, ABILITY_FLOODCALLER_UNTAP, Action, CardDatabase,\n    EngineKind,",
    "    ABILITY_ARTIFICERS_ASSISTANT_SCRY, ABILITY_FLOODCALLER_UNTAP, Action, EngineKind,",
)

replace_once(
    "rust/crates/urza-cards/tests/post_r7_modeling_completeness_rules_active_repair_v1.rs",
    "    apply_action(\n        &mut power_state,\n        &cards,\n        Action::ActivateUthrosStation {\n            source: ObjectId(3),\n            creature: canonical_for(&power_state, ObjectId(2)),\n        },\n    )",
    "    let battered_target = canonical_for(&power_state, ObjectId(2));\n    apply_action(\n        &mut power_state,\n        &cards,\n        Action::ActivateUthrosStation {\n            source: ObjectId(3),\n            creature: battered_target,\n        },\n    )",
)

replace_once(
    "rust/crates/urza-cards/tests/post_r7_modeling_completeness_rules_active_repair_v1.rs",
    "    apply_action(\n        &mut copy_state,\n        &cards,\n        Action::ActivateChromeDome {\n            source: ObjectId(10),\n            target: canonical_for(&copy_state, ObjectId(11)),\n            payment: ManaPayment {",
    "    let copy_target = canonical_for(&copy_state, ObjectId(11));\n    apply_action(\n        &mut copy_state,\n        &cards,\n        Action::ActivateChromeDome {\n            source: ObjectId(10),\n            target: copy_target,\n            payment: ManaPayment {",
)

replace_once(
    "rust/crates/urza-cards/tests/post_r7_modeling_completeness_rules_active_repair_v1.rs",
    "    apply_action(\n        &mut sacrifice_state,\n        &cards,\n        Action::ActivateGrindingStation {\n            source: ObjectId(1),\n            sacrifice: canonical_for(&sacrifice_state, ObjectId(2)),\n        },\n    )",
    "    let sacrifice_target = canonical_for(&sacrifice_state, ObjectId(2));\n    apply_action(\n        &mut sacrifice_state,\n        &cards,\n        Action::ActivateGrindingStation {\n            source: ObjectId(1),\n            sacrifice: sacrifice_target,\n        },\n    )",
)

replace_once(
    "rust/crates/urza-cards/tests/post_r7_modeling_completeness_rules_active_repair_v1.rs",
    "        apply_action(\n            &mut state,\n            &cards,\n            Action::CastTargetedFromHand {\n                card: card(&cards, spell),\n                target: canonical_for(&state, ObjectId(11)),\n                payment,\n            },\n        )",
    "        let grant_target = canonical_for(&state, ObjectId(11));\n        apply_action(\n            &mut state,\n            &cards,\n            Action::CastTargetedFromHand {\n                card: card(&cards, spell),\n                target: grant_target,\n                payment,\n            },\n        )",
)

replace_once(
    "rust/crates/urza-cards/tests/post_r7_modeling_completeness_rules_active_repair_v1.rs",
    "        apply_action(\n            &mut state,\n            &cards,\n            Action::ActivateGrantedKnackBounce {\n                source: ObjectId(11),\n                target: canonical_for(&state, ObjectId(12)),\n            },\n        )",
    "        let bounce_target = canonical_for(&state, ObjectId(12));\n        apply_action(\n            &mut state,\n            &cards,\n            Action::ActivateGrantedKnackBounce {\n                source: ObjectId(11),\n                target: bounce_target,\n            },\n        )",
)
