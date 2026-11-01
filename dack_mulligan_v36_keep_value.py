#!/usr/bin/env python3
"""v36 frozen observable KEEP probability ensemble and two-sided action gate.

New QKEEP(T2,T3) comes from physical-outcome-trained forests on actual
frozen v33b bottom hands. 35% old v27 Qkeep and 65% new forest forms
T2 prediction; shared C is only from new 123k full99 futures.
No sampled unseen library order or rollout enters inference.
"""
from __future__ import annotations
import json,math,struct
import dack_mulligan_v36_features as feat

SCHEMA="dack_v36_123k_stratified_forest_physical_keep_value_1"
ENSEMBLE=8
ALPHA_OLD=.35
T2_DEADBAND=.02
T3_MAX_LOSS=.04
C_STDERR_MULT=.5

def tree_value(tree,x):
    i=0;depth=0
    while tree["left"][i]>=0:
        feature=int(tree["feature"][i])
        if not 0<=feature<len(x):raise ValueError("bad v36 forest split feature")
        x32=struct.unpack("<f",struct.pack("<f",float(x[feature])))[0]
        i=tree["left"][i] if x32<=tree["threshold"][i] else tree["right"][i]
        depth+=1
        if depth>12:raise ValueError("v36 tree exceeds depth12")
    return float(tree["value"][i])

def forest_value(trees,x):
    return max(0.,min(1.,sum(tree_value(t,x) for t in trees)/len(trees)))

def read_model(model):
    assert model["schema"]==SCHEMA
    assert model["feature_hash"]==feat.feature_hash()
    assert model["feature_names"]==list(feat.NAMES)
    assert model["policy_approved"] is False
    assert model["stages_eligible"]==[0,1,2]
    assert len(model["ensemble"])==ENSEMBLE
    assert len(model["C_by_seat_stage"])==12
    assert model["real_shared_C_futures_per_cell"]==128
    assert model["old_Qkeep_blend_weight"]==ALPHA_OLD
    assert model["T2_deadband"]==T2_DEADBAND
    assert model["T3_safeguard_max_loss"]==T3_MAX_LOSS
    assert model["C_std_error_multiplier"]==C_STDERR_MULT
    return model

def predictions(model,features,oldq):
    read_model(model)
    assert len(features)==len(feat.NAMES) and 0<=oldq<=1
    q2=[];q3=[]
    for ens in model["ensemble"]:
        new2=forest_value(ens["trees_T2"],features)
        new3=forest_value(ens["trees_T3"],features)
        b2=ALPHA_OLD*oldq+(1-ALPHA_OLD)*new2
        b3=max(b2,new3) # enforce P(T<=3)>=P(T<=2)
        assert 0<=b2<=b3<=1
        q2.append(b2);q3.append(b3)
    return sorted(q2),sorted(q3)

def choose(model,features,seat,stage,old_keep,old_q):
    assert seat in range(4) and stage in range(7)
    assert len(features)==len(feat.NAMES)
    if stage not in (0,1,2):
        return bool(old_keep),{"reason":"unchanged_later_stage",
                               "old_keep":bool(old_keep),"new_keep":bool(old_keep)}
    q2,q3=predictions(model,features,old_q)
    C=model["C_by_seat_stage"][f"{seat}:{stage}"]
    c2,c3=float(C["T2"]),float(C["T3"])
    assert 0<=c2<=c3<=1
    se2=(c2*(1-c2)/128.)**.5
    ans=bool(old_keep)
    reason="frozen_v27_fallback"
    if not old_keep and q2[ENSEMBLE//4]-c2-C_STDERR_MULT*se2>T2_DEADBAND and        q3[ENSEMBLE//4]-c3>=-T3_MAX_LOSS:
        ans=True;reason="v36_real_action_keep"
    elif old_keep and q2[3*ENSEMBLE//4]-c2+C_STDERR_MULT*se2<-T2_DEADBAND and          q3[3*ENSEMBLE//4]-c3<=T3_MAX_LOSS:
        ans=False;reason="v36_real_action_mull"
    return ans,{
       "old_keep":bool(old_keep),"new_keep":ans,"reason":reason,
       "predicted_Qkeep_T2_lower":q2[ENSEMBLE//4],
       "predicted_Qkeep_T2_median":q2[ENSEMBLE//2],
       "predicted_Qkeep_T2_upper":q2[3*ENSEMBLE//4],
       "predicted_Qkeep_T3_lower":q3[ENSEMBLE//4],
       "predicted_Qkeep_T3_median":q3[ENSEMBLE//2],
       "predicted_Qkeep_T3_upper":q3[3*ENSEMBLE//4],
       "train_shared_C_T2":c2,"train_shared_C_T3":c3,
       "C_binomial_std_error":se2
    }

def selftest():
    assert tree_value({"left":[-1],"right":[-1],"value":[.25],"feature":[-2],"threshold":[-2]},[0.])==.25
    assert ENSEMBLE==8 and feat.feature_hash()
    print("DACK_V36_INFERENCE_FOREST_INVARIANTS_PASS",flush=True)

if __name__=="__main__":selftest()
