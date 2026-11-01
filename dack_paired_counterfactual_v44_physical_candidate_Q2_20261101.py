#!/usr/bin/env python3
"""v44 candidate-level real-physical learned residual; experimental policy.

Physical candidate scorer is trained on complete legal bottom alternatives in
154000..154191 and independently diagnosed on 154192..154255.

At stages 2-5, combine frozen v27 Q2 and fixed shrinkage residual estimate,
choose highest new Q2 across original legal top12, and compare exactly that
selected candidate with the FROZEN v27 stage/seat continuation threshold.
For stages 0,1,6,7, use v43 original Q2-max policy unchanged. Thus v44
never extrapolates its supervised correction to untrained London stages.

NO hidden realized library order, NO original v5 expensive lookahead, no
after-the-fact acceptance/continuation tuning, no policy approval.
"""
from __future__ import annotations
import json,hashlib
from collections import Counter
from pathlib import Path
import dack_paired_counterfactual_v27_T2_only_DP_20261101 as v27
import dack_mulligan_teacher_features_v13_20261031 as f
import dack_mulligan_v44_candidate_residual_20261101 as phys
from dack_simulator.validation.collect_teacher_london_v13 import finalists
ROOT=Path(__file__).resolve().parent
MODEL_PATH=ROOT/"models/v44_all_candidate_Q2_residual_RESEARCH.json"
POLICY="dack_v44_physical_candidate_residual_max_Q2"
ref=v27.ref
MODEL=None;MODEL_SHA=None
def audit():
    global MODEL,MODEL_SHA
    result=v27.audit()
    assert result["status"]=="PASS" and ref.SPEC["beam"]==160
    MODEL=phys.audit(MODEL_PATH)
    MODEL_SHA=phys.sha(MODEL_PATH)
    assert MODEL["source_sha256_by_shard"]
    assert MODEL["true_physical_beam160_T2_residual_not_teacher_labels"]
    assert MODEL["model_trained_on_all_legal_bottom_alternatives_not_only_v14"]
    assert MODEL["dev_game_ids_excluded_from_fit"]==[154192,154255]
    ref.choose_keep=choose_keep
    ref.MULLIGAN_POLICY_NAME=POLICY
    ref.MULLIGAN_SAMPLER_NAME="zero_beam__physical_counterfactual_candidate_residual"
    return {"status":"PASS","model_sha256":MODEL_SHA,"policy":POLICY,
            "model_approved":False,"no_runtime_v5_beam":True,
            "strict_physical_gameplay_beam":160}
def choose_keep(deck_slots,seat,orders):
    if MODEL is None:raise RuntimeError("install v44 model before choosing mulligans")
    assert deck_slots==ref.SLOT_VARIANTS["one_key_34"]
    thresholds=v27.original.DP["seat_continuations"][str(seat)]["thresholds_by_london_stage"]
    hist=[]
    for stage,(kn,order) in enumerate(zip(ref.sim.STAGES,orders)):
        seven=tuple(deck_slots[s] for s in order[:7])
        unknown=tuple(deck_slots[s] for s in order[7:])
        assert len(seven)==7 and len(unknown)==92
        pool=Counter(unknown)
        candidates=finalists(seven,kn,unknown)
        predicted=[]
        for i,c in enumerate(candidates):
            x=f.extract(seven,c["hand"],c["bottom"],
                pool,seat,kn,stage,c["struct_rank"],i)
            raw=float(v27.original.estimator.predict(v27.original.MODEL,x))
            corrected=(phys.adjusted(MODEL,x,raw)
                      if stage in (2,3,4,5) else raw)
            predicted.append((corrected,-i,raw,c))
        value,neg_index,raw,selected=max(predicted,key=lambda x:(x[0],x[1]))
        threshold=float(thresholds[stage])
        kept=(kn==1 or value>=threshold)
        hand=tuple(selected["hand"]);bottom=tuple(selected["bottom"])
        assert Counter(hand)+Counter(bottom)==Counter(seven)
        hist.append({
          "stage":stage,"keep_n":kn,"kept":kept,
          "raw":round(value,7),"baseline_raw_Q2":round(raw,7),
          "threshold":round(threshold,7),"refined":False,"sampled_t1":None,
          "candidate_index":-neg_index,"candidate_count":len(candidates),
          "seven_slots":list(order[:7]),"seven":list(seven),
          "hand":list(hand),"bottom":list(bottom),
          "hand_slots":ref.selected_slots(order[:7],seven,hand),
          "bottom_slots":ref.selected_slots(order[:7],seven,bottom),
          "policy":POLICY,"model_sha256":MODEL_SHA,
        })
        if kept:return ref.d.State(1,hand,unknown+bottom),hist
    raise AssertionError("final London stage must keep")
if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser();p.add_argument("--audit",action="store_true");p.add_argument("--game",type=int)
    a=p.parse_args();r=audit()
    if a.audit:print("DACK_V44_PHYSICAL_RESIDUAL_ZERO_BEAM_POLICY_AUDIT_PASS",json.dumps(r),flush=True)
    if a.game is not None:
        g=ref.game("one_key_34",a.game)
        print("DACK_V44_PHYSICAL_RESIDUAL_GAME",json.dumps({
             "gid":a.game,"turn":g["win_turn"],"history":g["history"]}),flush=True)
