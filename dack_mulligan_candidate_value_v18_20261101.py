"""Pure-Python frozen v18 candidate-utility forest.

The value approximates expected U = P(T1) + P(T2 exact) + .5*P(T3 exact).
It is NOT a globally calibrated probability estimator. Validated only on
the physical v5-visited, keep_n 3..6 London distribution.

This module does not access the simulation, oracle or future library order.
"""
from __future__ import annotations
import hashlib,json,math
import dack_mulligan_teacher_features_v13_20261031 as feats

SCHEMA="dack_v18_paired_candidate_utility_forest"

def feature_hash():return feats.feature_hash()

def predict(model,x):
    if model.get("schema")!=SCHEMA:
        raise ValueError("invalid candidate utility model")
    if model.get("feature_hash")!=feature_hash():
        raise ValueError("candidate feature signature mismatch")
    if model.get("deployed_policy_approved") is not False:
        raise ValueError("experimental scoring only")
    if len(x)!=model.get("feature_count"):
        raise ValueError("incompatible feature count")
    trees=model["trees"]
    if not trees:raise ValueError("empty value forest")
    score=0.
    for tree in trees:
        i=0;steps=0
        while tree["left"][i]>=0:
            j=int(tree["feature"][i])
            i=int(tree["left"][i]) if x[j]<=tree["threshold"][i] else int(tree["right"][i])
            steps+=1
            if steps>30:raise ValueError("corrupt value tree")
        score+=float(tree["value"][i])
    return max(0.,min(1.,score/len(trees)))

def best_structural_top(model,features_by_candidate):
    """Only the naturally enumerated first 3, never the teacher-only 4th."""
    if not features_by_candidate:raise ValueError("no candidate features")
    return max(range(min(3,len(features_by_candidate))),
               key=lambda i:(predict(model,features_by_candidate[i]),-i))

def selftest():
    m={"schema":SCHEMA,"feature_hash":feature_hash(),
       "deployed_policy_approved":False,"feature_count":len(feats.FEATURES),
       "trees":[{"left":[-1],"right":[-1],"feature":[-2],
                 "threshold":[-2.],"value":[.625]}]}
    assert predict(m,[0.]*len(feats.FEATURES))==.625
    assert best_structural_top(m,[[0.]*len(feats.FEATURES)]*3)==0
    return {"status":"PASS","feature_count":len(feats.FEATURES),
            "no_beam_inference":True,"model_still_unapproved":True}

if __name__=="__main__":
    print(json.dumps(selftest(),indent=2))
