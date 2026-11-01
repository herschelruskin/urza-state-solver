#!/usr/bin/env python3
"""Experimental v31 direct action-regret corrected London policy.

Deploys ONLY trained pure-Python residual Qkeep-Qmull correction on frozen
v27 value-DP; retains unchanged v14 bottom choice, strict stable dice, and
beam-160 game play. Never reads sampled outcomes, v5 teacher bottoms or
hidden topdeck order at inference. Do not promote without prospective test.
"""
from __future__ import annotations
from collections import Counter
from pathlib import Path
import hashlib,json
import dack_paired_counterfactual_v27_T2_only_DP_20261101 as frozen
import dack_paired_counterfactual_v22_all_stage_real_keep_DP_20261101 as controller
from dack_simulator.validation.collect_teacher_london_v13 import finalists
from dack_simulator.validation.v31_fit_action_regret import (
    MODEL_SCHEMA,SHRINK,predict_residual
)
import dack_mulligan_teacher_features_v13_20261031 as f
import dack_mulligan_keep_value_v22_20261101 as estimator

ref=controller.ref
POLICY="dack_v31_T2_Qregret_residual_london_UNAPPROVED"
MODEL_PATH="models/dack_v31_Q_advantage_residual_EXPERIMENTAL.json"
MODEL=None
SHA=None

def install():
    global MODEL,SHA
    orig=frozen.audit()
    assert orig["status"]=="PASS"
    p=Path(MODEL_PATH)
    m=json.loads(p.read_text())
    if m["schema"]!=MODEL_SCHEMA or m["candidate_policy_approved"] is not False:
        raise ValueError("wrong/unapproved Q model")
    if m["input_visible_feature_hash"]!=f.feature_hash():
        raise ValueError("feature incompatibility")
    for name,path in [
        ("source_v27_value_sha256",frozen.MODEL),
        ("source_v27_continuation_sha256",frozen.DP),
    ]:
        if m[name]!=hashlib.sha256(Path(path).read_bytes()).hexdigest():
            raise ValueError("frozen v27 dependency mismatch: "+name)
    if m["trained_on_103k_train_only"] is not True or m["shrinkage_correction"]!=SHRINK:
        raise ValueError("training or shrinkage mismatch")
    MODEL=m
    SHA=hashlib.sha256(p.read_bytes()).hexdigest()
    ref.choose_keep=choose_keep
    ref.MULLIGAN_POLICY_NAME=POLICY
    ref.MULLIGAN_SAMPLER_NAME="v31_real_Qaction_regret_no_london_beam"
    ref.RULES_VERSION=POLICY+"_"+SHA[:16]
    return SHA

def choose_keep(deck_slots,seat,orders):
    assert MODEL is not None
    assert deck_slots==ref.SLOT_VARIANTS["one_key_34"]
    thresholds=controller.DP["seat_continuations"][str(seat)]["thresholds_by_london_stage"]
    history=[]
    for stage,(kn,order) in enumerate(zip(ref.sim.STAGES,orders)):
        seven=tuple(deck_slots[k] for k in order[:7])
        unknown=tuple(deck_slots[k] for k in order[7:])
        pool=Counter(unknown)
        scored=[]
        for idx,c in enumerate(finalists(seven,kn,unknown)):
            x=f.extract(seven,c["hand"],c["bottom"],pool,seat,kn,stage,c["struct_rank"],idx)
            score=f.score_head(controller.old.MODEL,"choice_trees",x)
            scored.append((score,-idx,c,x))
        teacher_vote,negative_idx,c,x=max(scored,key=lambda z:(z[0],z[1]))
        value=estimator.predict(controller.MODEL,x)
        continuation=float(thresholds[stage])
        base_gap=value-continuation
        qinput=[float(v) for v in x]+[base_gap,value,continuation]
        residual=predict_residual(MODEL,qinput)
        corrected_gap=base_gap+SHRINK*residual
        keep=(kn==1 or corrected_gap>=0.)
        hand=tuple(c["hand"]);bottom=tuple(c["bottom"])
        assert len(hand)==kn and len(unknown)==92
        assert Counter(hand)+Counter(bottom)==Counter(seven)
        history.append({
            "stage":stage,"keep_n":kn,"kept":bool(keep),
            "raw":round(value,7),"threshold":round(continuation,7),
            "v27_baseline_action_keep":bool(kn==1 or base_gap>=0.),
            "predicted_Qadvantage_residual":round(residual,7),
            "corrected_keep_minus_mull_gap":round(corrected_gap,7),
            "policy":POLICY,"value_model_sha256":controller.MODEL_SHA,
            "continuation_dp_sha256":controller.DP_SHA,
            "Q_regret_model_sha256":SHA,
            "sampled_t1":None,"refined":False,
            "candidate_index":-negative_idx,
            "candidate_count":len(scored),
            "seven_slots":list(order[:7]),"seven":list(seven),
            "hand":list(hand),"bottom":list(bottom),
            "hand_slots":ref.selected_slots(order[:7],seven,hand),
            "bottom_slots":ref.selected_slots(order[:7],seven,bottom)
        })
        if keep:
            return ref.d.State(1,hand,unknown+bottom),history
    raise AssertionError("unreachable: forced final one card keep")

def audit():
    install()
    status=ref.audit()
    assert status["status"]=="PASS" and status["mulligan_policy"]==POLICY
    assert controller.MODEL["T3_reward_is_exactly_zero"]
    assert MODEL["candidate_policy_approved"] is False
    return dict(status,regret_model_sha256=SHA,
                value_model_sha256=controller.MODEL_SHA,
                DP_sha256=controller.DP_SHA,
                freeze_bottom_selection="v14_128",
                runtime_mulligan_beams=0,
                actual_gameplay_beam=160,
                model_approved=False)

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--audit",action="store_true")
    p.add_argument("--game",type=int,default=104000)
    a=p.parse_args()
    status=audit()
    if a.audit:print("DACK_V31_GAME_POLICY_AUDIT_PASS",json.dumps(status),flush=True)
    else:
        if not 104000<=a.game<104256:
            raise ValueError("104k independent prospective cohort only")
        x=ref.game("one_key_34",a.game)
        print("DACK_V31_PROSPECTIVE_GAME",json.dumps(x),flush=True)
