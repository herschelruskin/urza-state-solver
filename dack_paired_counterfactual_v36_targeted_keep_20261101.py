#!/usr/bin/env python3
"""v36 UNAPPROVED 123k physical forest early London KEEP/MULL policy.

Only stages 0,1,2 may change decisions, with a conservative
T2-vs-shared-C and T3 safeguard. EXACT frozen v33b original
bottom-choice ranker on final KEEP, v27 frozen decisions all
later stages and terminal stage7. 99 real physical card slots.
Mulligan has no speculative beam; gameplay strict beam160.
"""
from __future__ import annotations
from collections import Counter
import hashlib,json
from pathlib import Path
from dack_simulator.validation import v34_frozen_v33b_continuation as kernel
import dack_mulligan_v36_keep_value as val
import dack_mulligan_v36_features as feat

ref=kernel.ref
MODEL_PATH=Path("models/dack_v36_targeted_real_keep_EXPERIMENTAL.json")
POLICY="dack_v36_targeted_real_value_early_keep_UNAPPROVED"
MODEL=None;MODEL_SHA=None

def install():
    global MODEL,MODEL_SHA
    kernel.initialize()
    raw=MODEL_PATH.read_bytes()
    model=val.read_model(json.loads(raw))
    assert model["source_frozen_v33b_sha256"]==kernel.v33b.MODEL_SHA
    assert model["source_v27_Q_model_sha256"]==hashlib.sha256(
       Path(kernel.v33b.frozen.MODEL).read_bytes()).hexdigest()
    assert model["source_v27_DP_sha256"]==hashlib.sha256(
       Path(kernel.v33b.frozen.DP).read_bytes()).hexdigest()
    assert model["all_124k_holdout_unseen"] and model["all_125k_prospective_unseen"]
    MODEL=model;MODEL_SHA=hashlib.sha256(raw).hexdigest()
    ref.choose_keep=choose_keep
    ref.RULES_VERSION=POLICY+"_"+MODEL_SHA[:16]
    ref.MULLIGAN_POLICY_NAME=POLICY
    ref.MULLIGAN_SAMPLER_NAME="v36_pure_python_early_keep_real_Q_forest_no_beam"
    return MODEL_SHA

def choose_keep(deck_slots,seat,orders):
    if MODEL is None:raise ValueError("v36 research model must install")
    assert deck_slots==ref.SLOT_VARIANTS[kernel.DECK_KEY]
    hist=[]
    for stage,(kn,order) in enumerate(zip(ref.sim.STAGES,orders)):
        seven=tuple(deck_slots[s] for s in order[:7])
        unknown=tuple(deck_slots[s] for s in order[7:])
        assert Counter(seven)+Counter(unknown)==Counter(ref.VARIANTS[kernel.DECK_KEY])
        s=kernel.current(seven,unknown,seat,stage)
        hand=tuple(s["hand"]);bottom=tuple(s["bottom"])
        assert len(hand)==kn and len(bottom)==7-kn
        if kn==1:
            keep=True;diagnostic={"reason":"terminal_stage7_must_keep",
                "old_keep":True,"new_keep":True}
        elif stage<3:
            x=feat.extract(seven,hand,bottom,tuple(sorted(unknown)),seat,stage,
                           s["old_v27_Qkeep"],s["old_v27_DP"])
            keep,diagnostic=val.choose(MODEL,x,seat,stage,
                                      s["old_v27_keep"],s["old_v27_Qkeep"])
        else:
            keep=bool(s["old_v27_keep"])
            diagnostic={"reason":"unchanged_later_stage",
                        "old_keep":keep,"new_keep":keep}
        hist.append({
          "stage":stage,"keep_n":kn,"kept":bool(keep),
          "seven_slots":list(order[:7]),"seven":list(seven),
          "raw":round(s["old_v27_Qkeep"],7),
          "threshold":round(s["old_v27_DP"],7),
          "hand":list(hand),"bottom":list(bottom),
          "hand_slots":ref.selected_slots(order[:7],seven,hand),
          "bottom_slots":ref.selected_slots(order[:7],seven,bottom),
          "v36_frozen_v27_original_keep":bool(s["old_v27_keep"]),
          "v36_frozen_v33b_bottom":True,
          "v36_action_diagnostic":diagnostic,
          "policy":POLICY,
        })
        if keep:
            return ref.d.State(1,hand,unknown+bottom),hist
    raise AssertionError("stage7 always KEEP")

def audit():
    sha=install();a=ref.audit()
    assert a["status"]=="PASS" and a["mulligan_policy"]==POLICY
    assert tuple(ref.sim.STAGES)==(7,7,6,5,4,3,2,1)
    assert ref.SPEC["beam"]==160 and len(ref.SLOTS)==99
    return dict(a,model_sha256=sha,policy_approved=False,
       no_mulligan_beams=True,strict_actual_beam160=True,
       frozen_v33b_bottom=True,only_actual_stages_0_1_2_change=True,
       new_downstream_policy_Bellman_self_consistency_NOT_established=True)

def smoke():
    audit()
    for gid in range(125900,125910):
        seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
        seat,orders=ref.stage_slots(seed)
        state,hist=choose_keep(ref.SLOT_VARIANTS[kernel.DECK_KEY],seat,orders)
        assert hist[-1]["kept"] and state.hand==tuple(hist[-1]["hand"])
        assert len(state.library)==92+len(hist[-1]["bottom"])
        for h in hist:
            assert Counter(h["seven"])==Counter(h["hand"])+Counter(h["bottom"])
            assert h["stage"]<3 or h["kept"]==h["v36_frozen_v27_original_keep"]
        if all(h["kept"]==h["v36_frozen_v27_original_keep"] for h in hist):
            saved=ref.choose_keep
            ref.choose_keep=kernel.v33b.choose_keep
            try:
                earlier,oldhist=ref.choose_keep(ref.SLOT_VARIANTS[kernel.DECK_KEY],seat,orders)
                assert state.hand==earlier.hand and state.library==earlier.library
                assert len(hist)==len(oldhist)
            finally:ref.choose_keep=saved
    print("DACK_V36_STRICT_FROZEN_BOTTOM_EARLY_KEEP_SMOKE_PASS",flush=True)

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--audit",action="store_true")
    p.add_argument("--game",type=int,default=125000)
    a=p.parse_args();smoke()
    if not a.audit:
        assert 125000<=a.game<125256
        print("DACK_V36_RESEARCH_ONE_GAME",json.dumps(ref.game(
                    kernel.DECK_KEY,a.game)),flush=True)
