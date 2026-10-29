#!/usr/bin/env python3
"""Protect essential Boonweaver cards against exile and false combo wins.

Boonweaver Giant can source Auras from hand/graveyard/library. Protect the
full recognized Aura class from Chrome Mox and Gemstone Caverns exile.
Gleaming Splendor is NOT an Aura, but is explicitly user-confirmed as
required combo support: protect it too, without misclassifying its card type.

Protection must cover both normal Chrome Mox casts AND United Battlefront's
alternative Chrome Mox hit, which checks newer.WHITE_IMPRINTS directly.
Reject Dack-cast terminal states where a protected Aura or Gleaming
Splendor is exiled. Preserve the three combo creatures' library gate.
"""
from __future__ import annotations
from collections import Counter
import dack_bucknard_voltaic_stack_20261029 as priority

d=priority.d
sim=priority.sim
CORE_CREATURES=frozenset(("Boonweaver Giant","Preston, the Vanisher","Roaming Throne"))
PROTECTED_AURAS=frozenset(d.AURAS)
PROTECTED_NON_AURA=frozenset(("Gleaming Splendor",))
PROTECTED_EXILE=PROTECTED_AURAS|PROTECTED_NON_AURA
_PREV_PREGAME=d._pregame_states
_PREV_WIN=d.can_cast_dack
_PREV_CHROME=d.chrome_mox_allowed
# The Battlefront Chrome Mox code uses newer.WHITE_IMPRINTS directly
# rather than calling d.chrome_mox_allowed.
newer=sim.root.newer
_PREV_WHITE_IMPRINTS=frozenset(newer.WHITE_IMPRINTS)
# Snapshot before changing module-level WHITE_IMPRINTS; historical Chrome
# policy is a lambda that looks up that module global dynamically.
_WAS_CHROME_IMPRINTABLE=_PREV_CHROME("Gleaming Splendor")
_WAS_BATTLEFRONT_IMPRINTABLE="Gleaming Splendor" in _PREV_WHITE_IMPRINTS
FIX_VERSION="boonweaver_auras_plus_gleaming_splendor_exile_guard_v2"

def safe_chrome_mox_imprint(card):
    return card not in PROTECTED_EXILE and _PREV_CHROME(card)

d.chrome_mox_allowed=safe_chrome_mox_imprint
newer.WHITE_IMPRINTS=frozenset(
    card for card in _PREV_WHITE_IMPRINTS if card not in PROTECTED_EXILE)
# Keep the visible Boonweaver policy whitelist coherent for all future users.
sim.root.WHITE_IMPRINTS=newer.WHITE_IMPRINTS

def _new_exile(before,after):
    return Counter(after.exile)-Counter(before.exile)

def safe_pregame_states(s,seat):
    original=_PREV_PREGAME(s,seat)
    allowed=[q for q in original
             if not any(card in PROTECTED_EXILE or card in CORE_CREATURES
                        for card in _new_exile(s,q))]
    assert allowed,"Original no-Gemstone-activation branch must survive"
    return allowed

def safe_dack_cast(s):
    # Auras may be in hand/graveyard/library. Splendor is a separate
    # non-Aura requirement; prohibit exiling it without asserting it is
    # fetchable from every non-exile zone.
    if any(card in PROTECTED_EXILE for card in s.exile):
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
    assert "Gleaming Splendor" not in PROTECTED_AURAS, "Do not recategorize non-Aura"
    assert PROTECTED_NON_AURA==frozenset(("Gleaming Splendor",))
    assert "Gleaming Splendor" in live.ACTUAL_CURRENT_99
    assert "Gemstone Caverns" in live.ACTUAL_CURRENT_99
    assert "World Map" not in live.ACTUAL_CURRENT_99
    assert not any(d.chrome_mox_allowed(a) for a in PROTECTED_AURAS)
    assert not any(d.chrome_mox_allowed(c) for c in CORE_CREATURES)
    assert _WAS_CHROME_IMPRINTABLE, "Verify originally unsafe Chrome imprint"
    assert _WAS_BATTLEFRONT_IMPRINTABLE, "Verify unsafe Battlefront path"
    assert not d.chrome_mox_allowed("Gleaming Splendor")
    assert "Gleaming Splendor" not in newer.WHITE_IMPRINTS
    assert d.chrome_mox_allowed("Silence"), "Keep safe Chrome Mox imprints usable"
    assert "Silence" in newer.WHITE_IMPRINTS
    lib=tuple(sorted(CORE_CREATURES))
    # Chrome Mox can enter via United Battlefront, which consults a
    # different whitelist from ordinary Chrome Mox.
    assert not newer._front_hit(d.State(
        1,("Gleaming Splendor",),lib),"Chrome Mox")
    safe_front=newer._front_hit(d.State(1,("Silence",),lib),"Chrome Mox")
    assert any("Silence" in q.exile for q in safe_front)
    # Normal direct Chrome actions must likewise reject Splendor.
    assert not any("Gleaming Splendor" in q.exile for q in
                   d.special_actions(d.State(
                       1,("Chrome Mox","Gleaming Splendor"),lib)))

    s=d.State(1,("Gemstone Caverns","Hardlight Containment","Plains","Silence"),lib)
    old=_PREV_PREGAME(s,seat=1)
    assert any("Hardlight Containment" in q.exile for q in old),(
        "The historical issue must be reproduced rather than assumed")
    new=d._pregame_states(s,seat=1)
    assert new and len(new)<len(old)
    assert not any("Hardlight Containment" in q.exile for q in new)
    assert any("Plains" in q.exile for q in new)
    assert any("Silence" in q.exile for q in new)
    splendor_hand=d.State(
        1,("Gemstone Caverns","Gleaming Splendor","Plains","Silence"),lib)
    previously_unsafe=_PREV_PREGAME(splendor_hand,seat=1)
    assert any("Gleaming Splendor" in q.exile for q in previously_unsafe)
    corrected=d._pregame_states(splendor_hand,seat=1)
    assert corrected and len(corrected)<len(previously_unsafe)
    assert not any("Gleaming Splendor" in q.exile for q in corrected)
    assert any("Plains" in q.exile for q in corrected)
    assert any("Silence" in q.exile for q in corrected)
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
    splendor_hand_ok=d.State(1,("Gleaming Splendor",),lib,w=2,c=4)
    assert d.can_cast_dack(splendor_hand_ok), "No false exile failure when in hand"
    splendor_exiled=d.State(1,(),lib,w=2,c=4,exile=("Gleaming Splendor",))
    assert not d.can_cast_dack(splendor_exiled), "Exiled Splendor cannot be a combo win"
    assert not d.can_cast_dack(d.State(
        1,(),lib[1:],w=2,c=4))
    return {"status":"PASS","fix":FIX_VERSION,
            "prior_gemstone_exiles_required_aura":True,
            "gemstone_aura_exile_after_fix":False,
            "chrome_mox_aura_imprint_allowed":False,
            "hand_or_graveyard_aura_valid_for_dack":True,
            "exiled_aura_invalid_for_dack":True,
            "recognized_aura_count":len(PROTECTED_AURAS),
            "gleaming_splendor_is_non_aura":True,
            "gleaming_splendor_chrome_imprint_allowed":False,
            "gleaming_splendor_battlefront_imprint_allowed":False,
            "gleaming_splendor_gemstone_exile_allowed":False,
            "exiled_splendor_invalid_for_dack":True,
            "preserves_actual_boulder_deck":True}

if __name__=="__main__":
    import json
    print("BOONWEAVER_AURA_EXILE_GUARD_AUDIT_PASS",json.dumps(audit()),flush=True)
