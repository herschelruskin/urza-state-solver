#!/usr/bin/env python3
"""Close the remaining Boonweaver goldfish false-win path: Aura exile.

Boonweaver Giant searches Auras from hand/graveyard/library, so merely
drawing or discarding Auras is NOT a combo failure; Gemstone Caverns
exiling a required Aura IS. Chrome Mox's code already protects Auras.
The prior _pregame_states() enumerated ANY noncreature Gemstone exile,
including required Auras. This layer removes those choices at the
source, AND rejects any Dack-cast endpoint with an exiled Aura as a
safety backstop. It leaves all other choices and game rules unchanged.

This module intentionally does not assume all non-Aura enchantments
are mandatory. It protects the entire recognized Aura class per the
user's stated policy; non-Aura combo cards require separate audit.
"""
from __future__ import annotations
from collections import Counter
import dack_bucknard_voltaic_stack_20261029 as priority

d=priority.d
sim=priority.sim
CORE_CREATURES=frozenset(("Boonweaver Giant","Preston, the Vanisher","Roaming Throne"))
PROTECTED_AURAS=frozenset(d.AURAS)
_PREV_PREGAME=d._pregame_states
_PREV_WIN=d.can_cast_dack
FIX_VERSION="boonweaver_all_aura_caverns_chrome_exile_guard_v1"

def _new_exile(before,after):
    return Counter(after.exile)-Counter(before.exile)

def safe_pregame_states(s,seat):
    original=_PREV_PREGAME(s,seat)
    allowed=[q for q in original
             if not any(card in PROTECTED_AURAS or card in CORE_CREATURES
                        for card in _new_exile(s,q))]
    assert allowed,"Original no-Gemstone-activation branch must survive"
    return allowed

def safe_dack_cast(s):
    # Validate combo support across zones without demanding an Aura
    # be in the library. Graveyard and hand are legal and do not fail.
    if any(card in PROTECTED_AURAS for card in s.exile):
        return False
    return _PREV_WIN(s)

d._pregame_states=safe_pregame_states
d.can_cast_dack=safe_dack_cast

def audit():
    import dack_actual_current_boulder_20261028 as live
    live.audit()
    assert CORE_CREATURES==live.COMBO_CREATURES
    assert "Hardlight Containment" in PROTECTED_AURAS
    assert "Lunarch Mantle" in PROTECTED_AURAS
    assert "Gift of Immortality" in PROTECTED_AURAS
    assert "Bound by Moonsilver" in PROTECTED_AURAS
    assert "Gemstone Caverns" in live.ACTUAL_CURRENT_99
    assert "World Map" not in live.ACTUAL_CURRENT_99
    assert not any(d.chrome_mox_allowed(a) for a in PROTECTED_AURAS)
    assert not any(d.chrome_mox_allowed(c) for c in CORE_CREATURES)
    lib=tuple(sorted(CORE_CREATURES))
    s=d.State(1,("Gemstone Caverns","Hardlight Containment","Plains","Silence"),lib)
    old=_PREV_PREGAME(s,seat=1)
    assert any("Hardlight Containment" in q.exile for q in old),(
        "The historical issue must be reproduced rather than assumed")
    new=d._pregame_states(s,seat=1)
    assert new and len(new)<len(old)
    assert not any("Hardlight Containment" in q.exile for q in new)
    assert any("Plains" in q.exile for q in new)
    assert any("Silence" in q.exile for q in new)
    assert d._pregame_states(s,seat=0)==_PREV_PREGAME(s,seat=0)
    s_only=d.State(1,("Gemstone Caverns","Lunarch Mantle"),lib)
    actual=d._pregame_states(s_only,seat=2)
    assert len(actual)==1 and actual[0]==s_only
    # Dack's cast-condition is NEVER invalidated by an Aura simply
    # being in hand or graveyard; it IS invalidated if exiled.
    base=d.State(1,("Gift of Immortality",),lib,w=2,c=4)
    assert d.can_cast_dack(base)
    grave=d.State(1,(),lib,w=2,c=4,grave=("Gift of Immortality",))
    assert d.can_cast_dack(grave)
    exiled=d.State(1,(),lib,w=2,c=4,exile=("Gift of Immortality",))
    assert not d.can_cast_dack(exiled)
    assert not d.can_cast_dack(d.State(
        1,(),lib[1:],w=2,c=4))
    return {"status":"PASS","fix":FIX_VERSION,
            "prior_gemstone_exiles_required_aura":True,
            "gemstone_aura_exile_after_fix":False,
            "chrome_mox_aura_imprint_allowed":False,
            "hand_or_graveyard_aura_valid_for_dack":True,
            "exiled_aura_invalid_for_dack":True,
            "recognized_aura_count":len(PROTECTED_AURAS),
            "preserves_actual_boulder_deck":True}

if __name__=="__main__":
    import json
    print("BOONWEAVER_AURA_EXILE_GUARD_AUDIT_PASS",json.dumps(audit()),flush=True)
