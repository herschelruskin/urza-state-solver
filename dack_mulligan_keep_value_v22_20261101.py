"""Pure-Python conditional keep utility for EVERY London stage (v22).

U = P(T1 exact)+P(T2 exact)+.5*P(T3 exact), estimated from real
beam160 physical unknown-library futures for student-proposed candidate.
Unlike the prior v16 model, training intentionally includes hands rejected
by its frozen source student and states not actually reached in games.

This model alone is not an approved keep decision. Compare to a separately
derived continuation expectation C_k under London mulligan rules.
"""
from __future__ import annotations
import hashlib,json,struct
import dack_mulligan_teacher_features_v13_20261031 as feats

SCHEMA="dack_v22_counterfactual_keep_value_forest"

def predict(model,x):
    if model.get("schema")!=SCHEMA or model.get("feature_hash")!=feats.feature_hash():
        raise ValueError("keep-utility model mismatch")
    if model.get("deployed_policy_approved") is not False:
        raise ValueError("research-only keep model expected")
    if len(x)!=model.get("feature_count"):raise ValueError("keep feature mismatch")
    forest=model.get("trees")
    if not forest:raise ValueError("no keep regression trees")
    accum=0.
    for tree in forest:
        i=0;depth=0
        while tree["left"][i]>=0:
            j=int(tree["feature"][i])
            # scikit-learn tree/forest predict casts the incoming feature
            # matrix to float32 before taking threshold branches. Match that
            # numeric contract without requiring NumPy at inference time.
            x32=struct.unpack("<f",struct.pack("<f",float(x[j])))[0]
            i=tree["left"][i] if x32<=tree["threshold"][i] else tree["right"][i]
            depth+=1
            if depth>30:raise ValueError("invalid keep regression tree")
        accum+=float(tree["value"][i])
    return max(0.,min(1.,accum/len(forest)))

def model_hash(model):
    return hashlib.sha256(json.dumps(
        model,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def selftest():
    m={"schema":SCHEMA,"feature_hash":feats.feature_hash(),
       "feature_count":len(feats.FEATURES),"deployed_policy_approved":False,
       "trees":[{"left":[-1],"right":[-1],"feature":[-2],
                 "threshold":[-2.],"value":[.375]}]}
    assert predict(m,[0.]*len(feats.FEATURES))==.375
    assert len(model_hash(m))==64
    return {"status":"PASS","pure_python_no_beam_inference":True,
            "features":len(feats.FEATURES),"model_unapproved":True}

if __name__=="__main__":
    print(json.dumps(selftest(),indent=2))
