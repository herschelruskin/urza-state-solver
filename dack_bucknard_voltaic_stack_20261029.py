#!/usr/bin/env python3
"""Correct Voltaic Key / Bucknard's Everfull Purse priority interaction.

In Magic: activate Bucknard {1},{T}, hold priority, pay {1},{T} with
Voltaic Key to UNTAP Bucknard, activate Bucknard {1},{T} again while
the original ability is on the stack. Both abilities resolve and make
separately rolled d4 Treasure quantities; only then is Bucknard handed
to the player on the right. You MUST fund all {3} generic before seeing
any Treasure; no treasure from first ability can fund the response.

This solver has no actual priority stack. Implement a narrowly scoped
atomic compound action so Key's value is not understated. No “free
untap after first resolution”; do not let transferred Purse be used.

The solver's deterministic die outcomes use different salts for the
two independent d4 rolls. These remain an optimistic goldfish; no
multiplayer opponent response or perfect blind-roll decision policy.
"""
from __future__ import annotations
from dataclasses import replace
import dack_prism_color_sources_20261028 as fix
import dack_v077_full_deck_accel as buck
sim=fix.sim
d=sim.d
P="Bucknard's Everfull Purse"
K="Voltaic Key"
_BASE_UTILITY=d.utility_actions
ENABLED=True
FIX_VERSION="bucknard_key_pre_resolution_double_activation_20261029_v1"

def double_bucknard_key_actions(s):
    """Return ONLY compound stack-based outputs, never ordinary source uses."""
    if not ENABLED:return []
    pidx=next((i for i,p in enumerate(s.battlefield)
               if d.effective_name(p)==P and not p.tapped),None)
    kidx=next((i for i,k in enumerate(s.battlefield)
               if d.effective_name(k)==K and not k.tapped),None)
    if pidx is None or kidx is None or pidx==kidx:
        return []
    outputs=[]
    for paid in d.pay_options(s,3):
        if len(paid.battlefield)!=len(s.battlefield):continue
        bp=paid.battlefield[pidx]; bk=paid.battlefield[kidx]
        if d.effective_name(bp)!=P or bp.tapped:continue
        if d.effective_name(bk)!=K or bk.tapped:continue
        # Both activations are announced before either die result is known.
        # The original engine salts a single Bucknard activation by turn.
        roll1=buck._roll(s,P,4,paid.turn)
        roll2=buck._roll(s,P,4,10001+paid.turn)
        bf=list(paid.battlefield)
        purse=bf.pop(pidx)
        key_index=kidx-(1 if pidx<kidx else 0)
        bf[key_index]=replace(bf[key_index],tapped=True)
        outputs.append(replace(paid,battlefield=tuple(bf),
                               treasures=paid.treasures+roll1+roll2))
        # If KCI is controlled, respond again and sacrifice Bucknard:
        # both abilities remain stacked and still generate both rolls.
        if any(d.effective_name(q)=="Krark-Clan Ironworks"
               for q in bf):
            outputs.append(replace(paid,battlefield=tuple(bf),
                                   treasures=paid.treasures+roll1+roll2,
                                   c=paid.c+2,grave=paid.grave+(purse.name,)))
    return outputs

def corrected_utility(s):
    old=_BASE_UTILITY(s)
    extra=double_bucknard_key_actions(s)
    if not extra:return old
    seen=set()
    out=[]
    for q in list(old)+extra:
        k=d.key(q)
        if k not in seen:
            seen.add(k);out.append(q)
    return out

d.utility_actions=corrected_utility

def witness():
    # A direct 2-activation line has 1 Purse + 1 Key + THREE floating
    # generic mana. After the line: Key tapped, Purse GONE, two rolls.
    buck.set_trial_seed(101)
    s=d.State(1,(),(),(d.Perm(P),d.Perm(K)),c=3)
    choices=double_bucknard_key_actions(s)
    assert choices
    assert all(q.c==0 and len(q.battlefield)==1 and
               d.effective_name(q.battlefield[0])==K and
               q.battlefield[0].tapped and 2<=q.treasures<=8
               for q in choices),choices
    assert len(choices)==1,"KCI-free action must have exactly one compound branch"
    assert d.is_artifact_perm(P), "Purse must be a Key-legal artifact"
    # Transferring Bucknard away means no reactivation or untapping it
    # after abilities finish.
    q=choices[0]
    assert not any(d.effective_name(p)==P for p in q.battlefield)
    assert not double_bucknard_key_actions(q)
    # Strict costs and control of Key/untapped source.
    for c in (0,1,2):
        short=d.State(1,(),(),(d.Perm(P),d.Perm(K)),c=c)
        assert not double_bucknard_key_actions(short),("mana leakage",c)
    assert not double_bucknard_key_actions(
        d.State(1,(),(),(d.Perm(P,True),d.Perm(K)),c=3))
    assert not double_bucknard_key_actions(
        d.State(1,(),(),(d.Perm(P),d.Perm(K,True)),c=3))
    assert not double_bucknard_key_actions(
        d.State(1,(),(),(d.Perm(P),),c=3))
    # Contrast: legacy resolves the first Bucknard activation immediately,
    # so it cannot reach the compound two-roll 3-mana output.
    previous=ENABLED
    try:
        globals()["ENABLED"]=False
        assert not double_bucknard_key_actions(s)
        legacy=_BASE_UTILITY(s)
        assert any(q.treasures>=1 and len(q.battlefield)==1 and
                   d.effective_name(q.battlefield[0])==K
                   for q in legacy)
        globals()["ENABLED"]=True
        assert any(q.treasures==choices[0].treasures and
                   len(q.battlefield)==1 and
                   q.battlefield[0].tapped for q in d.utility_actions(s))
    finally:
        globals()["ENABLED"]=previous
    return {"fix":FIX_VERSION,"status":"PASS","roll1":buck._roll(s,P,4,s.turn),
            "roll2":buck._roll(s,P,4,10001+s.turn),
            "cost_generic":3,"transferred_after_resolution":True,
            "no_treasure_finances_stack_actions":True,
            "simulated_stack_priority":"atomic two-activation macro",
            "legacy_status":"misses double-roll line"}

if __name__=="__main__":
    import json
    print("BUCKNARD_VOLTAIC_PRIORITY_AUDIT_PASS",json.dumps(witness()),flush=True)
