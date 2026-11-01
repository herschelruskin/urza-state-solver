#!/usr/bin/env python3
"""v32 policy: unchanged all-stage v27 Q(KEEP), empirically shared Q(MULL).

Only change from frozen v27 = threshold for keeping. For each seat and
London stage, Q(MULL) was precomputed by 96 actual independent beam160
deployments after restoring all 99 cards and following frozen v27 future
London policy. 32 more fresh observations check predictive calibration.
The measured Q(MULL) is shrunk 75% real +25% frozen v27 DP prior, fixed
in advance. At inference no future game/order is sampled or inspected.
All bottoming remains frozen v14 128 and uses all eight London stages.

The continuation is specifically a *one-step policy-improvement estimate*
under future frozen v27, not a self-consistent DP after replacing decisions.
It needs separate prospective paired end-to-end game evaluation.
"""
from __future__ import annotations
from collections import Counter
from pathlib import Path
import hashlib,json
import dack_paired_counterfactual_v27_T2_only_DP_20261101 as frozen
import dack_paired_counterfactual_v22_all_stage_real_keep_DP_20261101 as controller
from dack_simulator.validation.collect_teacher_london_v13 import finalists
import dack_mulligan_teacher_features_v13_20261031 as f
import dack_mulligan_keep_value_v22_20261101 as estimator

ref=controller.ref
POLICY="dack_v32_shared_real_Qmull_v27_keep_value_UNAPPROVED"
CONTINUATION_PATH="models/dack_v32_shared_Qmull_continuation_EXPERIMENTAL.json"
SHARED=None
SHARED_SHA=None

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def install():
    global SHARED,SHARED_SHA
    r=frozen.audit()
    assert r["status"]=="PASS"
    path=Path(CONTINUATION_PATH)
    data=json.loads(path.read_text())
    assert data["schema"]=="dack_v32_physical_Qmull_shared_continuation_UNAPPROVED"
    assert data["model_approved"] is False
    assert data["frozen_v27_downstream_policy"] is True
    assert data["keep_estimator_unchanged_v27_93k_all_eight_stages"] is True
    assert data["fixed_predeclared_real_weight"]==.75
    for key,source in (
        ("source_v27_model_file_sha256",frozen.MODEL),
        ("source_v27_dp_file_sha256",frozen.DP),
        ("source_v14_bottom_file_sha256",controller.KEEP_BASELINE)):
        if data[key]!=sha(source):
            raise ValueError("dependency mismatched: "+key)
    assert len(data["seat_continuations"])==4
    for seat in range(4):
        arr=data["seat_continuations"][str(seat)]["thresholds_by_london_stage"]
        assert len(arr)==8 and all(0<=v<=1 for v in arr[:7]) and arr[7]==-1.
    SHARED=data;SHARED_SHA=sha(path)
    ref.choose_keep=choose_keep
    ref.MULLIGAN_POLICY_NAME=POLICY
    ref.MULLIGAN_SAMPLER_NAME="v32_precomputed_shared_physical_Qmull_zero_beam"
    ref.RULES_VERSION=POLICY+"_"+SHARED_SHA[:16]
    return SHARED_SHA

def choose_keep(deck_slots,seat,orders):
    assert SHARED is not None
    assert deck_slots==ref.SLOT_VARIANTS["one_key_34"]
    thresholds=SHARED["seat_continuations"][str(seat)]["thresholds_by_london_stage"]
    hist=[]
    for stage,(kn,order) in enumerate(zip(ref.sim.STAGES,orders)):
        seven=tuple(deck_slots[i] for i in order[:7])
        unknown=tuple(deck_slots[i] for i in order[7:])
        pool=Counter(unknown)
        scored=[]
        for idx,c in enumerate(finalists(seven,kn,unknown)):
            x=f.extract(seven,c["hand"],c["bottom"],pool,seat,kn,stage,c["struct_rank"],idx)
            vote=f.score_head(controller.old.MODEL,"choice_trees",x)
            scored.append((vote,-idx,c,x))
        _,neg_idx,c,x=max(scored,key=lambda z:(z[0],z[1]))
        keep_value=estimator.predict(controller.MODEL,x)
        continuation=float(thresholds[stage])
        baseline=float(controller.DP["seat_continuations"][str(seat)]["thresholds_by_london_stage"][stage])
        keep=kn==1 or keep_value>=continuation
        hand=tuple(c["hand"]);bottom=tuple(c["bottom"])
        assert len(hand)==kn and len(unknown)==92
        assert Counter(hand)+Counter(bottom)==Counter(seven)
        hist.append({
           "stage":stage,"keep_n":kn,"kept":keep,
           "raw":round(keep_value,7),"threshold":round(continuation,7),
           "frozen_v27_threshold":round(baseline,7),
           "frozen_v27_keep":bool(kn==1 or keep_value>=baseline),
           "candidate_index":-neg_idx,"candidate_count":len(scored),
           "seven_slots":list(order[:7]),"seven":list(seven),
           "hand":list(hand),"bottom":list(bottom),
           "hand_slots":ref.selected_slots(order[:7],seven,hand),
           "bottom_slots":ref.selected_slots(order[:7],seven,bottom),
           "sampled_t1":None,"refined":False,"policy":POLICY,
           "continuation_sha256":SHARED_SHA,
           "frozen_keep_value_model_sha256":controller.MODEL_SHA,
        })
        if keep:return ref.d.State(1,hand,unknown+bottom),hist
    raise AssertionError("terminal London one-card keep required")

def audit():
    install()
    r=ref.audit()
    assert r["status"]=="PASS" and r["mulligan_policy"]==POLICY
    assert controller.MODEL["T3_reward_is_exactly_zero"]
    return dict(r,model_approved=False,policy_approved=False,
                shared_Qmull_sha256=SHARED_SHA,
                keep_estimator="frozen_v27_all_eight_stages",
                bottom_estimator="frozen_v14_128",
                london_beam_calls=0,actual_gameplay_beam=160,
                no_student_Qgap_regression=True)

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--audit",action="store_true")
    p.add_argument("--game",type=int,default=110000)
    a=p.parse_args()
    report=audit()
    print("DACK_V32_REAL_SHARED_CONTINUATION_AUDIT_PASS",json.dumps(report),flush=True)
    if not a.audit:
        if not 110000<=a.game<110256:
            raise ValueError("only 110k fresh prospective IDs allowed")
        print("DACK_V32_GAME",json.dumps(ref.game("one_key_34",a.game)),flush=True)
