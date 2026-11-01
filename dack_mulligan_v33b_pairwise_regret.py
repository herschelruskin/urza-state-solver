#!/usr/bin/env python3
"""Pure-Python bounded linear pairwise-regret bottom model for v33b.

Model predictions estimate action *differences*, never absolute Qkeep.
Training is only on the 112k independent physical game groups. Eight
shared physical futures per candidate generate noisy T2/T3 differences.
The 16 group-bootstrap ridge fits are a conservative stability gate,
not calibrated confidence intervals. No new random forest or beam calls.
"""
from __future__ import annotations
from collections import Counter
import hashlib
import json
import math
import random
from pathlib import Path
import dack_mulligan_v33b_capability_regret_features as feats

SCHEMA="dack_v33b_pairwise_capability_ridge_research_only"
LAMBDA=12.0
BOOTS=16
T2_MIN_LOWER=0.01
T3_MIN_MEDIAN=-0.025

def solve_ridge(rows,scales,l2=LAMBDA):
    p=len(feats.NAMES)
    cov=[[0.]*p for _ in range(p)]
    bt2=[0.]*p;bt3=[0.]*p
    for z,y2,y3,weight in rows:
        x=[float(v)/scales[i] for i,v in enumerate(z)]
        for i in range(p):
            bt2[i]+=weight*x[i]*y2
            bt3[i]+=weight*x[i]*y3
            for j in range(i,p):
                cov[i][j]+=weight*x[i]*x[j]
    for i in range(p):
        for j in range(i):
            cov[i][j]=cov[j][i]
        cov[i][i]+=l2
    aug=[cov[i][:]+[bt2[i],bt3[i]] for i in range(p)]
    # Fixed-size SPD ridge system; partial pivoting for reproducibility.
    for k in range(p):
        pivot=max(range(k,p),key=lambda i:abs(aug[i][k]))
        aug[k],aug[pivot]=aug[pivot],aug[k]
        assert abs(aug[k][k])>1e-12
        z=aug[k][k]
        for j in range(k,p+2):aug[k][j]/=z
        for i in range(p):
            if i==k:continue
            a=aug[i][k]
            if a:
                for j in range(k,p+2):aug[i][j]-=a*aug[k][j]
    b2=[aug[i][p] for i in range(p)]
    b3=[aug[i][p+1] for i in range(p)]
    assert all(math.isfinite(v) for v in b2+b3)
    return b2,b3

def quantiles(values):
    a=sorted(values);n=len(a)
    assert n==BOOTS
    return {"lower_quartile":a[(n-1)//4],
            "median":(a[n//2-1]+a[n//2])/2,
            "upper_quartile":a[(3*(n-1))//4]}

def predictions(model,delta):
    if model.get("schema")!=SCHEMA or model.get("feature_sha256")!=feats.feature_hash():
        raise ValueError("pairwise feature signature mismatch")
    if model.get("policy_approved") is not False:
        raise ValueError("unapproved policy expected")
    scales=model["feature_scales"]
    assert len(delta)==len(scales)==len(feats.NAMES)
    x=[v/s for v,s in zip(delta,scales)]
    q2=[sum(w*v for w,v in zip(e["T2"],x)) for e in model["ensemble"]]
    q3=[sum(w*v for w,v in zip(e["T3"],x)) for e in model["ensemble"]]
    assert len(q2)==len(q3)==BOOTS
    return quantiles(q2),quantiles(q3)

def choose(model,seven,unknown,seat,choices,options):
    """Only choose among the four training-supported proposal methods.

    The v14 baseline is a safe fallback on uncertain or neutral action
    differences. This never uses a realized hidden draw or game rollout.
    """
    assert len(seven)==7 and len(unknown)==92
    baseline=int(choices["v14_frozen"])
    bhand=tuple(options[baseline]["hand"])
    assert Counter(bhand)+Counter(options[baseline]["bottom"])==Counter(seven)
    best=None
    diagnostics=[]
    for idx in sorted(set(choices.values())):
        if idx==baseline:continue
        alt=options[idx]
        assert Counter(alt["hand"])+Counter(alt["bottom"])==Counter(seven)
        delta=feats.difference(bhand,alt["hand"],unknown,seat)
        q2,q3=predictions(model,delta)
        qualifies=(q2["lower_quartile"]>T2_MIN_LOWER and
                   q3["median"]>=T3_MIN_MEDIAN)
        diagnostics.append({"index":idx,"T2_lower":q2["lower_quartile"],
            "T2_median":q2["median"],"T3_median":q3["median"],
            "qualifies":qualifies})
        if qualifies:
            score=(q2["lower_quartile"],q2["median"],-idx)
            if best is None or score>best[0]:
                best=(score,idx)
    return (best[1] if best else baseline),diagnostics

def check():
    a=solve_ridge([((0.,)*len(feats.NAMES),0.,0.,1.)],
                  [1.]*len(feats.NAMES))
    assert len(a)==2 and all(all(v==0 for v in z) for z in a)
    print("DACK_V33B_RIDGE_ALGEBRA_SELFTEST_PASS",flush=True)

if __name__=="__main__":
    check()
