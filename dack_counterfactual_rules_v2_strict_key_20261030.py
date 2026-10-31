#!/usr/bin/env python3
"""Conservative state-equivalence hardening, separate from historical solver.

The inherited beam key ignores grave/exile, Saga history and success/repair
fields even though these can change legal future choices. This strict key
extends (never weakens) the inherited identity. Runtime cost must be measured
against the original before a large statistical screen.
"""
from __future__ import annotations
from dataclasses import replace
import json

import dack_counterfactual_rules_v1_20261030 as base

d, sim, newer = base.d, base.sim, base.newer
RULES_VERSION = "dack_physical_treasure_staff_strict_key_v2"
PREVIOUS_RULES_VERSION = base.RULES_VERSION
_legacy_key = d.key

def strict_key(s):
    return (
        _legacy_key(s),
        tuple(sorted(s.grave)),
        tuple(sorted(s.exile)),
        tuple(s.saga_age),
        bool(s.success),
        int(s.repaired),
    )

d.key = strict_key

def rule_smoke():
    v1 = base.rule_smoke()
    assert v1["status"] == "PASS"
    combo = tuple(sorted(sim.root.COMBO))
    a = d.State(1, (), combo, w=2, c=4)
    b = replace(a, exile=("Gleaming Splendor",))
    assert _legacy_key(a) == _legacy_key(b)
    assert strict_key(a) != strict_key(b)
    assert d.can_cast_dack(a) and not d.can_cast_dack(b)

    a = d.State(1, (), ("Campfire",))
    b = replace(a, grave=("Boonweaver Giant",))
    assert _legacy_key(a) == _legacy_key(b)
    assert strict_key(a) != strict_key(b)
    assert d.artifact_tutor_choice(a) is None
    assert d.artifact_tutor_choice(b) == "Campfire"

    a = d.State(1, (), combo)
    for changes in (
        {"saga_age":(("Urza's Saga", 1),)},
        {"success":True}, {"repaired":1},
    ):
        b = replace(a, **changes)
        assert _legacy_key(a) == _legacy_key(b)
        assert strict_key(a) != strict_key(b)
    return {
        "status":"PASS",
        "rules_version":RULES_VERSION,
        "inherited_collision_witnesses":5,
        "legacy_rules_version":PREVIOUS_RULES_VERSION,
        "strict_grave_exile_saga_repair":True,
        "runtime_fidelity_confirmed":False,
    }

if __name__=="__main__":
    print(json.dumps(rule_smoke(), indent=2))
