#!/usr/bin/env python3
"""Evaluate frozen learned T1/T2/T3 predictions on NEVER-TRAINED v7-kept hands.

Only descriptive predictive evaluation. It does NOT measure performance of a
new learned mulligan policy; that requires independent paired full games.

Each 7-card scenario contributes multiple correlated real beam rollouts.
Confidence intervals resample independent outer game IDs, not individual
rollout rows. The model is never refit or recalibrated on this test set.
"""
from __future__ import annotations
from collections import Counter,defaultdict
import argparse
import gzip
import json
import math
from pathlib import Path
import random
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))

import dack_mulligan_learned_features_v8_20261031 as model_util

def read(paths):
    rows=[];ids=set()
    for path in paths:
        with gzip.open(path,"rt",encoding="utf8") as f:
            meta=json.loads(next(f))
            if meta["split"]!="evaluation":
                raise ValueError("refusing non-holdout records")
            if meta["sampling_protocol"]!="DACK-SELECTED-LONDON-V10":
                raise ValueError("unexpected holdout selection mechanism")
            for line in f:
                r=json.loads(line)
                if r["type"]!="label" or not 33000<=r["game_id"]<=33999:
                    raise ValueError("invalid evaluation group")
                if r["selection_stratum"]!="v7_policy_kept_natural":
                    raise ValueError("invalid natural selected-hand stratum")
                rows.append(r);ids.add(r["game_id"])
    if len(ids)<16:raise ValueError("at least 16 independent groups needed")
    return rows

def report(model,rows,bootstraps=200):
    if model.get("schema")!="dack_london_multiclass_softmax_v8":
        raise ValueError("invalid model")
    if model.get("feature_sha256")!=model_util.feature_hash():
        raise ValueError("feature mismatch")
    probs=[]
    truth=[]
    groups=[]
    for row in rows:
        x=model_util.extract(row["hand"],row["bottom"],
                             row["unknown_counts"],row["seat"],row["keep_n"])
        p=model_util.probability_from_export(model,x)
        probs.append(p);truth.append(int(row["label_turn"]))
        groups.append(int(row["game_id"]))
    n=len(rows)
    def stat(indices):
        sample=[truth[i] for i in indices]
        pp=[probs[i] for i in indices]
        brier=sum(sum((p[k]-float(t==k))**2 for k in range(4))
                  for p,t in zip(pp,sample))/len(indices)
        logloss=sum(-math.log(max(1e-12,p[t]))
                    for p,t in zip(pp,sample))/len(indices)
        def event(expected,observed):
            return {
                "expected":sum(expected)/len(indices),
                "observed":sum(observed)/len(indices),
                "mean_absolute_prediction_error":abs(
                    sum(expected)-sum(observed))/len(indices)
            }
        return {
            "multiclass_brier":brier,
            "multiclass_log_loss":logloss,
            "T1":event([p[1] for p in pp],[int(t==1) for t in sample]),
            "T2_cumulative":event([p[1]+p[2] for p in pp],
                                  [int(t in (1,2)) for t in sample]),
            "T3_cumulative":event([1.-p[0] for p in pp],
                                  [int(t!=0) for t in sample])
        }
    result=stat(list(range(n)))
    boundaries=(0.0,.05,.1,.2,.35,.5,.7,1.0)
    reliability={}
    for name,pi,actual in [
        ("T1",lambda p:p[1],lambda t:t==1),
        ("T2_cumulative",lambda p:p[1]+p[2],lambda t:t in (1,2)),
        ("T3_cumulative",lambda p:1.-p[0],lambda t:t!=0),
    ]:
        bins=[]
        for lo,hi in zip(boundaries[:-1],boundaries[1:]):
            indexes=[i for i,p in enumerate(probs)
                     if lo<=pi(p)<hi or (hi==1. and pi(p)==1.)]
            if not indexes:continue
            bins.append({
                "range":[lo,hi],"n":len(indexes),
                "predicted":sum(pi(probs[i]) for i in indexes)/len(indexes),
                "observed":sum(int(actual(truth[i])) for i in indexes)/len(indexes)
            })
        reliability[name]=bins
    by_group=defaultdict(list)
    for i,gid in enumerate(groups):by_group[gid].append(i)
    gids=sorted(by_group)
    rng=random.Random(0xDACC)
    replicates=[]
    for _ in range(bootstraps):
        chosen=[gids[rng.randrange(len(gids))] for _ in gids]
        indexes=[idx for gid in chosen for idx in by_group[gid]]
        replicates.append(stat(indexes))
    ci={}
    for metric in ("multiclass_brier","multiclass_log_loss"):
        vals=sorted(x[metric] for x in replicates)
        ci[metric]=[vals[int(.025*len(vals))],
                    vals[min(len(vals)-1,int(.975*len(vals)))]]
    return {
        "schema":"dack_selected_model_independent_predictive_holdout_v1",
        "status":"PASS","model_was_frozen_prior_to_holdout":True,
        "model_approved_for_policy_deployment":False,
        "n_group_scenarios":len(gids),"n_real_rollouts":n,
        "observed_class_counts":dict(sorted(Counter(truth).items())),
        "metrics":result,"independent_group_bootstrap_95_ci":ci,
        "reliability_bins":reliability,
        "warning":"This is ONLY predictive holdout for v7-selected kept hands. It is not an unbiased four-player win rate or independent learned-policy gameplay test."
    }

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--model",required=True)
    p.add_argument("--evaluation",nargs="+",required=True)
    p.add_argument("--out",default="benchmark_results/v10_independent_model_holdout.json")
    a=p.parse_args()
    model=json.loads(Path(a.model).read_text())
    rows=read(a.evaluation)
    result=report(model,rows)
    target=Path(a.out);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2)+"\n")
    print("INDEPENDENT_SELECTED_PREDICTIVE_HOLDOUT",json.dumps(result),flush=True)
