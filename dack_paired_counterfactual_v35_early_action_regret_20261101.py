#!/usr/bin/env python3
"""v35 UNAPPROVED early-action correction over immutable v33b bottom policy.

At each London stage first reproduce the original frozen v27
Qkeep and C for the v14 baseline; bottom after a KEEP remains
the exact frozen v33b pairwise regret selected legal subset.
Only London actual stages 0,1,2 are eligible for a new
KEEP/MULL action, and only if the precommitted ridge stability
gate and T3 safeguard are satisfied.

This is a one-step improved policy against a frozen v33b future.
Full policy Bellman self-consistency after overrides is NOT assumed;
requires fresh prospective end-to-end measurement before promotion.
"""
from __future__ import annotations
from collections import Counter
import hashlib,json
from pathlib import Path
from dack_simulator.validation import v34_frozen_v33b_continuation as kernel
import dack_mulligan_v35_action_regret as regret
import dack_mulligan_v35_action_features as features

ref=kernel.ref
POLICY="dack_v35_early_action_regret_research_UNAPPROVED"
MODEL_PATH=Path("models/dack_v35_early_action_regret_EXPERIMENTAL.json")
MODEL=None;MODEL_SHA=None

def install():
    global MODEL,MODEL_SHA
    kernel.initialize()
    raw=MODEL_PATH.read_bytes();model=json.loads(raw)
    if model.get("schema")!=regret.SCHEMA or model.get("feature_hash")!=features.hash_names():
        raise ValueError("invalid frozen v35 keep regret feature/model schema")
    assert model["source_v33b_bottom_sha256"]==kernel.v33b.MODEL_SHA
    assert model["heldout_121k_never_seen"] and model["policy_approved"] is False
    assert model["override_stages"]==[0,1,2]
    assert len(model["ensemble"])==regret.BOOTS
    assert model["source_v27_keep_model_sha256"]==hashlib.sha256(
       Path(kernel.v33b.frozen.MODEL).read_bytes()).hexdigest()
    assert model["source_v27_dp_sha256"]==hashlib.sha256(
       Path(kernel.v33b.frozen.DP).read_bytes()).hexdigest()
    MODEL=model;MODEL_SHA=hashlib.sha256(raw).hexdigest()
    ref.choose_keep=choose_keep
    ref.RULES_VERSION=POLICY+"_"+MODEL_SHA[:16]
    ref.MULLIGAN_POLICY_NAME=POLICY
    ref.MULLIGAN_SAMPLER_NAME="v35_no_beam_direct_action_regret"
    return MODEL_SHA

def choose_keep(deck_slots,seat,orders):
    if MODEL is None:raise RuntimeError("v35 must install first")
    assert deck_slots==ref.SLOT_VARIANTS[kernel.DECK_KEY]
    history=[]
    for stage,(kn,order) in enumerate(zip(ref.sim.STAGES,orders)):
        seven=tuple(deck_slots[t] for t in order[:7])
        unknown=tuple(deck_slots[t] for t in order[7:])
        assert Counter(seven)+Counter(unknown)==Counter(ref.VARIANTS[kernel.DECK_KEY])
        current=kernel.current(seven,unknown,seat,stage)
        hand,bottom=tuple(current["hand"]),tuple(current["bottom"])
        assert len(hand)==kn and len(bottom)==7-kn
        if kn==1:
            keep=True
            d={"old_keep":True,"new_keep":True,"reason":"forced_terminal_stage7"}
        else:
            x=features.extract(stage,seat,seven,hand,tuple(sorted(unknown)),
                      current["old_v27_Qkeep"],current["old_v27_DP"])
            keep,d=regret.decision(MODEL,x,stage,current["old_v27_keep"])
        history.append({
           "stage":stage,"keep_n":kn,"kept":bool(keep),
           "raw":round(current["old_v27_Qkeep"],7),
           "threshold":round(current["old_v27_DP"],7),
           "refined":False,"sampled_t1":None,
           "seven_slots":list(order[:7]),"seven":list(seven),
           "hand":list(hand),"bottom":list(bottom),
           "hand_slots":ref.selected_slots(order[:7],seven,hand),
           "bottom_slots":ref.selected_slots(order[:7],seven,bottom),
           "v35_original_v27_keep":current["old_v27_keep"],
           "v35_decision":d,
           "v35_model_sha256":MODEL_SHA,
           "v35_v33b_bottom_unchanged":True,
           "policy":POLICY
        })
        if keep:
            return ref.d.State(1,hand,unknown+bottom),history
    raise AssertionError("London stage7 terminal one-card KEEP not reached")

def audit():
    sha=install()
    a=ref.audit()
    assert a["status"]=="PASS" and a["mulligan_policy"]==POLICY
    assert tuple(ref.sim.STAGES)==(7,7,6,5,4,3,2,1)
    assert len(ref.SLOTS)==99 and ref.SPEC["beam"]==160
    assert regret.T2_MIN_ACTION_MARGIN==.06 and regret.T3_MAX_ALLOWED_LOSS==-.04
    assert regret.MAX_RESIDUAL_CORRECTION==.35
    return dict(a,model_sha256=sha,policy_approved=False,
       physical_99_and_actual_gameplay_beam160=True,
       mulligan_beams=0,stages_eligible_for_change=[0,1,2],
       unchanged_frozen_v33b_bottom=True,
       new_policy_Bellman_consistent=False)

def smoke():
    audit()
    for gid in range(122000,122008):
        seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
        seat,orders=ref.stage_slots(seed)
        state,history=choose_keep(ref.SLOT_VARIANTS[kernel.DECK_KEY],seat,orders)
        assert history[-1]["kept"]
        assert state.hand==tuple(history[-1]["hand"])
        assert len(state.library)==92+len(history[-1]["bottom"])
        assert all(h["kept"]==h["v35_original_v27_keep"] for h in history
                   if h["stage"]>=3)
        for h in history:
            assert Counter(h["seven"])==Counter(h["hand"])+Counter(h["bottom"])
        # Metamorphic: when every model override is suppressed, the
        # complete v27 KEEP decisions and v33b bottom must replay.
        no_change=True
        for h in history:
            if h["kept"]!=h["v35_original_v27_keep"]:
                no_change=False
        if no_change:
            saved=ref.choose_keep
            ref.choose_keep=kernel.v33b.choose_keep
            try:
                older,hist=ref.choose_keep(ref.SLOT_VARIANTS[kernel.DECK_KEY],seat,orders)
                assert len(hist)==len(history)
                assert older.hand==state.hand and older.library==state.library
            finally:
                ref.choose_keep=saved
    print("DACK_V35_FROZEN_BOTTOM_AND_NO_BEAM_SMOKE_PASS",flush=True)

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--audit",action="store_true")
    p.add_argument("--game",type=int,default=122000)
    a=p.parse_args()
    smoke()
    if not a.audit:
        assert 122000<=a.game<122256
        print("DACK_V35_PROSPECTIVE_SMOKE_GAME",json.dumps(ref.game(
                  kernel.DECK_KEY,a.game)),flush=True)
