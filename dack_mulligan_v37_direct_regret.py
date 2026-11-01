#!/usr/bin/env python3
"""v37 frozen direct QKEEP-minus-QMULL policy model.

Two physical-outcome-trained DIRECT signed action advantage regressors
for cumulative T2 and T3. NO independent keep-score-vs-old-value
blending. Ensemble bootstraps outer physical groups AND 12 shared C
seat-stage lotteries independently in each fitted member.
The same C bootstrap per seat/stage applies across ALL hands in member.
"""
from __future__ import annotations
import struct,math
import dack_mulligan_v37_features as feat

SCHEMA="dack_v37_direct_regret_group_and_C_bootstrap_forest_v1"
N=12;T2_DEADBAND=.020;T3_ALLOWED_LOSS=.040

def tree_value(t,x):
    i=0;steps=0
    while t["left"][i]>=0:
        f=t["feature"][i]
        assert 0<=f<len(x)
        v=struct.unpack("<f",struct.pack("<f",float(x[f])))[0]
        i=t["left"][i] if v<=t["threshold"][i] else t["right"][i]
        steps+=1
        if steps>10:raise ValueError("tree depth invalid")
    return float(t["value"][i])

def forest_value(trees,x):
    assert len(trees)==32
    value=sum(tree_value(t,x) for t in trees)/len(trees)
    return max(-1.,min(1.,value))

def validate(model):
    if model.get("schema")!=SCHEMA or model.get("feature_hash")!=feat.feature_hash():
        raise ValueError("wrong v37 action regret feature/model schema")
    if model.get("policy_approved") is not False or model.get("stages_eligible")!=[0,1,2]:
        raise ValueError("unapproved frozen v37 stage contract mismatch")
    if len(model.get("ensemble",[]))!=N:raise ValueError("12 models expected")
    if model.get("T2_deadband")!=T2_DEADBAND or model.get("T3_max_loss")!=T3_ALLOWED_LOSS:
        raise ValueError("changed model thresholds")
    return model

def predict(model,x):
    assert len(x)==len(feat.NAMES)
    assert model["feature_hash"]==feat.feature_hash()
    a2=[];a3=[]
    for ens in model["ensemble"]:
        a2.append(forest_value(ens["T2"],x))
        a3.append(forest_value(ens["T3"],x))
    return sorted(a2),sorted(a3)

def decide(model,x,stage,old_keep):
    assert 0<=stage<8
    if stage>=3:
        return bool(old_keep),{"old_keep":bool(old_keep),"new_keep":bool(old_keep),
                               "reason":"unchanged_later_stage"}
    p2,p3=predict(model,x)
    mid2=p2[N//2];mid3=p3[N//2]
    keep=bool(old_keep);reason="frozen_v27_fallback"
    if not old_keep and p2[N//4]>T2_DEADBAND and mid3>=-T3_ALLOWED_LOSS:
        keep=True;reason="v37_true_regret_keep"
    elif old_keep and p2[3*N//4]<-T2_DEADBAND and mid3<=T3_ALLOWED_LOSS:
        keep=False;reason="v37_true_regret_mull"
    return keep,{
      "old_keep":bool(old_keep),"new_keep":keep,"reason":reason,
      "pred_adv_T2_lower":p2[N//4],"pred_adv_T2_med":mid2,
      "pred_adv_T2_upper":p2[3*N//4],
      "pred_adv_T3_lower":p3[N//4],"pred_adv_T3_med":mid3,
      "pred_adv_T3_upper":p3[3*N//4],
    }

def selftest():
    assert len(feat.NAMES)==75 and N==12
    leaf={"left":[-1],"feature":[-2],"value":[-.25],"threshold":[-2]}
    assert forest_value([leaf]*32,[1.])==-.25
    assert T2_DEADBAND==.02
    print("DACK_V37_DIRECT_REGRET_NO_V27_BLEND_SELFTEST_PASS",flush=True)

if __name__=="__main__":selftest()
