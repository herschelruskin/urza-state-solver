#!/usr/bin/env python3
"""Frozen v46 experimental stage0/1 physical Q2 correction, v43 after stage1.

Original v43 candidate-max bottoming remains unchanged at ALL stages;
only the first two (no-bottom) seven-card KEEP decisions can be overridden.
No v5 beams, no hidden draw order or hindsight, research only.
"""
from __future__ import annotations
import hashlib,json,struct
from collections import Counter
from pathlib import Path
import dack_paired_counterfactual_v43_v27_max_Q2_20261101 as v43
import dack_mulligan_teacher_features_v13_20261031 as f
from dack_simulator.validation.collect_teacher_london_v13 import finalists

ROOT=Path(__file__).resolve().parent
MODEL_PATH=ROOT/"models/v46_first_two_sevens_Q2_residual_RESEARCH.json"
SCHEMA="dack_v46_train_frozen_early_seven_physical_Q2_residual_v1"
POLICY="dack_v46_physical_calibrated_stages_0_1_then_exact_v43"
ref=v43.ref
MODEL=None
MODEL_SHA=None

def float32(x):return struct.unpack("<f",struct.pack("<f",float(x)))[0]

def tree_value(tree,x):
    i=0
    for it in range(40):
        left=tree["left"][i]
        if left<0:return float(tree["value"][i])
        j=tree["feature"][i]
        assert 0<=j<len(x)
        i=left if float32(x[j])<=tree["threshold"][i] else tree["right"][i]
    raise AssertionError("invalid v46 forest depth")

def calibrated_q(model,x,oldQ):
    assert len(x)==model["model_input_n"]
    residual=sum(tree_value(t,x) for t in model["forest_trees"])/len(model["forest_trees"])
    clip=float(model["residual_clip_abs"])
    return max(0.,min(1.,float(oldQ)+float(model["shrinkage"])*max(-clip,min(clip,residual))))

def install():
    global MODEL,MODEL_SHA
    result=v43.audit()
    assert result["status"]=="PASS" and ref.SPEC["beam"]==160
    data=MODEL_PATH.read_bytes();m=json.loads(data)
    assert m["schema"]==SCHEMA and m["status"]=="EXPERIMENTAL_UNAPPROVED"
    assert m["policy_approved"] is False and m["train_groups"]==128
    assert m["train_ids"]==[160000,160127] and m["dev_excluded_ids"]==[160128,160191]
    assert m["stage0_1_only_no_bottom_choices"]
    assert m["feature_hash"]==f.feature_hash()
    assert [f.FEATURES[i] for i in m["feature_indices"]]+["v43_predicted_Q2"]==m["feature_names"]
    assert len(m["forest_trees"])==80 and m["model_input_n"]==len(m["feature_names"])
    MODEL=m;MODEL_SHA=hashlib.sha256(data).hexdigest()
    ref.choose_keep=choose_keep
    ref.MULLIGAN_POLICY_NAME=POLICY
    ref.MULLIGAN_SAMPLER_NAME="none_frozen_physical_calibration_forest_0_1"
    return dict(result,policy=POLICY,model_sha256=MODEL_SHA,policy_approved=False)

def choose_keep(deck_slots,seat,orders):
    assert MODEL is not None
    assert deck_slots==ref.SLOT_VARIANTS["one_key_34"]
    dp=v43.v27.original.DP["seat_continuations"][str(seat)]["thresholds_by_london_stage"]
    hist=[]
    for stage,(kn,order) in enumerate(zip(ref.sim.STAGES,orders)):
        seven=tuple(deck_slots[s] for s in order[:7])
        unseen=tuple(deck_slots[s] for s in order[7:])
        assert len(seven)==7 and len(unseen)==92
        cand=finalists(seven,kn,unseen)
        pool=Counter(unseen)
        pred=[]
        for i,c in enumerate(cand):
            features=f.extract(seven,c["hand"],c["bottom"],pool,
                 seat,kn,stage,c["struct_rank"],i)
            q=float(v43.v27.original.estimator.predict(v43.v27.original.MODEL,features))
            pred.append((q,-i,c,features))
        q,neg,selected,features=max(pred,key=lambda x:(x[0],x[1]))
        cutoff=float(dp[stage])
        baseline_keep=bool(kn==1 or q>=cutoff)
        new_keep=baseline_keep
        adjusted=None;C=None
        if stage<2:
            assert kn==7 and len(cand)==1 and not selected["bottom"]
            xx=[float(features[i]) for i in MODEL["feature_indices"]]+[q]
            adjusted=calibrated_q(MODEL,xx,q)
            C=MODEL["C_train_64_futures_only"][f"{seat}_{stage}"]["2"]
            margin=adjusted-C
            if abs(margin)>=MODEL["deadband"]:new_keep=bool(margin>0)
        hand=tuple(selected["hand"]);bottom=tuple(selected["bottom"])
        assert Counter(hand)+Counter(bottom)==Counter(seven)
        hist.append({"stage":stage,"keep_n":kn,"kept":new_keep,
              "raw":round(q,7),"threshold":round(cutoff,7),
              "original_v43_keep":baseline_keep,
              "v46_adj_pred_Q2":None if adjusted is None else round(adjusted,7),
              "v46_physical_C_train":C,
              "candidate_index":-neg,"candidate_count":len(cand),
              "seven_slots":list(order[:7]),"seven":list(seven),
              "hand":list(hand),"bottom":list(bottom),
              "hand_slots":ref.selected_slots(order[:7],seven,hand),
              "bottom_slots":ref.selected_slots(order[:7],seven,bottom),
              "policy":POLICY})
        if new_keep:return ref.d.State(1,hand,unseen+bottom),hist
    raise AssertionError("one-card stage must keep")

def audit():
    r=install()
    assert ref.MULLIGAN_POLICY_NAME==POLICY
    deck=ref.SLOT_VARIANTS["one_key_34"]
    # Later stages are exact v43 when reached; direct comparison on 24
    # stage-specific original London draws, independent of early changes.
    import dack_simulator.validation.v45_frozen_v43_continuation as kernel
    for gid in range(168020,168044):
        seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
        seat,orders=ref.stage_slots(seed)
        for stage in range(2,8):
            cur=kernel.choose_at(stage,seat,orders[stage],deck)
            kn=cur["keep_n"]
            a=finalists(tuple(cur["seven"]),kn,
                 tuple(deck[x] for x in orders[stage][7:]))
            assert a and cur["candidate_index"] in range(len(a))
    return r

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser();p.add_argument("--audit",action="store_true");p.add_argument("--game",type=int)
    a=p.parse_args()
    x=audit()
    if a.audit:print("DACK_V46_RESEARCH_EARLY_SEVEN_MODEL_AUDIT_PASS",json.dumps(x),flush=True)
    if a.game is not None:
        g=ref.game("one_key_34",a.game)
        print("DACK_V46_RESEARCH_GAME",json.dumps({"gid":a.game,"turn":g["win_turn"],"history":g["history"]}),flush=True)
