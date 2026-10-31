#!/usr/bin/env python3
"""Demonstrate the legacy beam-key collision before enabling strict keying.

The inherited key omits grave/exile; this is a diagnostic that should
produce concrete witnesses rather than quietly assuming the key is exact.
"""
from __future__ import annotations
from dataclasses import replace
from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import dack_counterfactual_rules_v1_20261030 as patched

d=patched.d
combo=tuple(sorted(patched.sim.root.COMBO))

def audit():
    good=d.State(1, (), combo, w=2, c=4)
    exiled=replace(good, exile=("Gleaming Splendor",))
    same_key=(d.key(good)==d.key(exiled))
    allowed_good=bool(d.can_cast_dack(good))
    allowed_exiled=bool(d.can_cast_dack(exiled))
    assert same_key, "baseline key changed; revisit strict-key migration"
    assert allowed_good and not allowed_exiled, "exile witness no longer discriminates"

    # Graveyard matters to the visible-state tutor policy even before Dack
    # is cast (Campfire recovery of a required creature).
    empty=d.State(1, (), ("Campfire",))
    contaminated=replace(empty, grave=("Boonweaver Giant",))
    grave_collision=(d.key(empty)==d.key(contaminated))
    normal_target=d.artifact_tutor_choice(empty)
    recovery_target=d.artifact_tutor_choice(contaminated)
    assert grave_collision
    assert normal_target is None and recovery_target=="Campfire"
    return {
        "status":"EXPECTED_KEY_COLLISIONS_CONFIRMED",
        "exile_equal_key":same_key,
        "exile_changes_deployment_eligibility":True,
        "grave_equal_key":grave_collision,
        "grave_changes_tutor_target":True,
        "safe_to_reuse_legacy_key_for_cross_variant_cache":False,
    }

if __name__=="__main__":
    print(json.dumps(audit(), indent=2))
