#!/usr/bin/env python3
"""Complete Bucknard pre-resolution stack lines for VOLTAIC + MANIFOLD Keys.

The existing Oct29 patch adds a Voltaic Key 2x Bucknard activation for
{3} generic paid BEFORE any die rolls/Treasure production.

This extends it to Manifold Key alone (same exact {3} line) and to
BOTH keys together ({5} generic for THREE Bucknard d4 activations).
It never uses the first roll's Treasures to pay later activations;
Bucknard leaves our battlefield after the stack finishes resolving.

Voltaic and Manifold both cost {1},{T}: untap target artifact.
Regular untapping of Mana Vault, Grim/Basalt, Bucknard etc. is already
implemented by the inherited solver. No new ramp source is invented.
"""
from __future__ import annotations
from dataclasses import replace
import dack_boonweaver_aura_exile_guard_20261029 as guard
import dack_bucknard_voltaic_stack_20261029 as old

d=guard.d
sim=guard.sim
buck=old.buck
P=old.P
VOLTAIC="Voltaic Key"
MANIFOLD="Manifold Key"
FIX_VERSION="bucknard_pre_resolution_manifold_and_double_key_three_dice_v1"
_PREVIOUS_UTILITY=d.utility_actions

def _compound(s,needed):
    """needed: tuple of distinct key names, one per pre-resolution untap."""
    pidx=next((i for i,p in enumerate(s.battlefield)
               if d.effective_name(p)==P and not p.tapped),None)
    if pidx is None:return []
    source_keys={}
    for key in needed:
        pos=next((i for i,q in enumerate(s.battlefield)
                  if d.effective_name(q)==key and not q.tapped),None)
        if pos is None:return []
        source_keys[key]=pos
    cost=2*len(needed)+1  # {1} Bucknard x(1+key count) + {1} each key
    outs=[]
    for paid in d.pay_options(s,cost):
        if len(paid.battlefield)!=len(s.battlefield):continue
        if paid.battlefield[pidx].tapped or any(
             paid.battlefield[j].tapped for j in source_keys.values()):
            continue
        # Roll one die per Bucknard activation. All choices committed
        # and mana paid before any die produces Treasures.
        rolls=[buck._roll(s,P,4,paid.turn)]+[
            buck._roll(s,P,4,10001*k+paid.turn)
            for k in range(1,len(needed)+1)]
        bf=list(paid.battlefield)
        removed=bf.pop(pidx)
        for key,index in source_keys.items():
            shifted=index-(1 if pidx<index else 0)
            assert d.effective_name(bf[shifted])==key
            bf[shifted]=replace(bf[shifted],tapped=True)
        treasures=sum(rolls)
        outs.append(replace(paid,battlefield=tuple(bf),
                            treasures=paid.treasures+treasures))
        if any(d.effective_name(q)=="Krark-Clan Ironworks" for q in bf):
            outs.append(replace(paid,battlefield=tuple(bf),
                                treasures=paid.treasures+treasures,
                                c=paid.c+2,grave=paid.grave+(removed.name,)))
    return outs

def extended_utility(s):
    out=list(_PREVIOUS_UTILITY(s))
    extra=_compound(s,(MANIFOLD,)) + _compound(s,(VOLTAIC,MANIFOLD))
    if not extra:return out
    seen=set();merged=[]
    for q in out+extra:
        k=d.key(q)
        if k not in seen:
            seen.add(k);merged.append(q)
    return merged

d.utility_actions=extended_utility

def witness():
    assert guard.audit()["status"]=="PASS"
    assert old.witness()["status"]=="PASS"
    assert d.is_artifact_perm(MANIFOLD) and d.is_artifact_perm(VOLTAIC)
    assert d.COSTS[MANIFOLD]==(1,0,0)
    assert d.COSTS[VOLTAIC]==(1,0,0)
    buck.set_trial_seed(556677)
    m=d.State(1,(),(),(d.Perm(P),d.Perm(MANIFOLD)),c=3)
    two=_compound(m,(MANIFOLD,))
    assert len(two)==1 and two[0].c==0
    assert 2<=two[0].treasures<=8
    assert len(two[0].battlefield)==1 and two[0].battlefield[0].tapped
    assert d.effective_name(two[0].battlefield[0])==MANIFOLD
    assert not any(d.effective_name(p)==P for p in two[0].battlefield)
    for cost in (0,1,2):
        assert not _compound(d.State(
            1,(),(),(d.Perm(P),d.Perm(MANIFOLD)),c=cost),(MANIFOLD,))
    both=d.State(1,(),(),(d.Perm(P),d.Perm(VOLTAIC),d.Perm(MANIFOLD)),c=5)
    three=_compound(both,(VOLTAIC,MANIFOLD))
    assert len(three)==1 and three[0].c==0
    assert 3<=three[0].treasures<=12
    assert len(three[0].battlefield)==2 and all(p.tapped for p in three[0].battlefield)
    assert {d.effective_name(p) for p in three[0].battlefield}=={VOLTAIC,MANIFOLD}
    assert not _compound(three[0],(VOLTAIC,MANIFOLD))
    for cost in (0,1,2,3,4):
        assert not _compound(d.State(
            1,(),(),(d.Perm(P),d.Perm(VOLTAIC),d.Perm(MANIFOLD)),c=cost),
            (VOLTAIC,MANIFOLD)),("financed by pre-resolution treasure",cost)
    assert not _compound(d.State(
        1,(),(),(d.Perm(P,True),d.Perm(VOLTAIC),d.Perm(MANIFOLD)),c=5),
        (VOLTAIC,MANIFOLD))
    for tapped in (VOLTAIC,MANIFOLD):
        s=d.State(1,(),(),(d.Perm(P),
                           d.Perm(VOLTAIC,tapped==VOLTAIC),
                           d.Perm(MANIFOLD,tapped==MANIFOLD)),c=5)
        assert not _compound(s,(VOLTAIC,MANIFOLD))
    assert any(q.treasures==three[0].treasures and
               {d.effective_name(p) for p in q.battlefield}=={VOLTAIC,MANIFOLD}
               and all(p.tapped for p in q.battlefield)
               for q in d.utility_actions(both))
    kci=d.State(1,(),(),(d.Perm(P),d.Perm(VOLTAIC),d.Perm(MANIFOLD),
                        d.Perm("Krark-Clan Ironworks")),c=5)
    z=_compound(kci,(VOLTAIC,MANIFOLD))
    assert len(z)==2 and any(q.c==2 and P in q.grave for q in z)
    return {"status":"PASS","fix":FIX_VERSION,
            "manifold_bucknard_2_activations_mana":3,
            "two_keys_bucknard_3_activations_mana":5,
            "treasure_before_payment_allowed":False,
            "source_transferred_only_after_stack":True,
            "all_required_auras_and_splendor_protected":True,
            "preserves_previous_voltaic_macro":True,
            "main_artifact_untap_still_inherited":True}

if __name__=="__main__":
    import json
    print("SECOND_KEY_MANIFOLD_BUCKNARD_STACK_AUDIT_PASS",json.dumps(witness()),flush=True)
