#!/usr/bin/env python3
"""v35 tiny group-bootstrap ridge estimator of real KEEP-minus-MULL regret.

Frozen original v27 margin is the default, regressed residual is a
bounded correction. Never imitate the v5 action label. Train only on:
116k physical ALL-stage KEEP outcomes (8 futures/state);
115k original actual-disagreement KEEP outcomes (CALIBRATION 16 futures
only), and v34 shared Qmull TRAIN split (64 futures/seat-stage).
117k v34 validation and v34c replication never used in training.
"""
from __future__ import annotations
import hashlib,json,math,random
import dack_mulligan_v35_action_features as feats

SCHEMA="dack_v35_frozen_v33b_action_regret_ridge_1"
BOOTS=24
LAMBDA=16.0
EARLY_WEIGHT=2.0
SELECTED_DISAGREEMENT_GROUP_WEIGHT=0.75
T2_MIN_ACTION_MARGIN=0.06
T3_MAX_ALLOWED_LOSS=-0.04
MAX_RESIDUAL_CORRECTION=0.35

def ridge(records,scales,l2=LAMBDA):
    n=feats.N
    cov=[[0.]*n for _ in range(n)]
    rhs=[[0.]*n for _ in range(2)]
    for x,y2,y3,w in records:
        z=[v/s for v,s in zip(x,scales)]
        for i in range(n):
            rhs[0][i]+=w*z[i]*y2
            rhs[1][i]+=w*z[i]*y3
            for j in range(i,n):
                cov[i][j]+=w*z[i]*z[j]
    for i in range(n):
        for j in range(i):cov[i][j]=cov[j][i]
        cov[i][i]+=l2
    aug=[cov[i][:]+[rhs[0][i],rhs[1][i]] for i in range(n)]
    for k in range(n):
        pivot=max(range(k,n),key=lambda i:abs(aug[i][k]))
        aug[k],aug[pivot]=aug[pivot],aug[k]
        assert abs(aug[k][k])>1e-12
        a=aug[k][k]
        for j in range(k,n+2):aug[k][j]/=a
        for i in range(n):
            if i==k:continue
            b=aug[i][k]
            if b:
                for j in range(k,n+2):aug[i][j]-=b*aug[k][j]
    out=[[aug[i][n+p] for i in range(n)] for p in range(2)]
    assert all(math.isfinite(z) for ws in out for z in ws)
    return out

def prediction(model,x):
    if model.get("schema")!=SCHEMA or model.get("feature_hash")!=feats.hash_names():
        raise ValueError("wrong v35 model or feature signature")
    if model.get("policy_approved") is not False:
        raise ValueError("unreviewed research candidate expected")
    if len(x)!=feats.N:raise ValueError("wrong feature count")
    scaled=[v/s for v,s in zip(x,model["scales"])]
    margin=x[1]
    t2=[];t3=[]
    for e in model["ensemble"]:
        residual=max(-MAX_RESIDUAL_CORRECTION,min(MAX_RESIDUAL_CORRECTION,
             sum(w*v for w,v in zip(e["residual_T2"],scaled))))
        t2.append(margin+residual)
        t3.append(sum(w*v for w,v in zip(e["direct_T3"],scaled)))
    assert len(t2)==len(t3)==BOOTS
    return sorted(t2),sorted(t3)

def decision(model,x,stage,old_keep):
    """Only actual London stages 0,1,2 eligible for override.

    This policy improvement is evaluated against FROZEN v33b Qmull,
    not falsely claimed Bellman-self-consistent after intervention.
    """
    assert stage in range(7)
    q2,q3=prediction(model,x)
    result=bool(old_keep)
    reason="frozen_v27_fallback"
    if stage in feats.EARLY:
        # Use two-sided bootstrap-quartile stability, not a formal CI.
        # This policy can flip only when a nontrivial advantage and T3
        # safeguard are simultaneously satisfied. Neither was tuned.
        if not old_keep and q2[BOOTS//4]>T2_MIN_ACTION_MARGIN and            q3[BOOTS//2]>=T3_MAX_ALLOWED_LOSS:
            result=True;reason="regret_select_keep"
        elif old_keep and q2[(3*BOOTS)//4]<-T2_MIN_ACTION_MARGIN and              q3[BOOTS//2]<=-T3_MAX_ALLOWED_LOSS:
            # We want T3 gain when switching to MULL, hence
            # KEEP-minus-MULL T3 advantage must be <= -0.04.
            result=False;reason="regret_select_mull"
    return result,{
      "old_keep":bool(old_keep),"new_keep":result,"reason":reason,
      "T2_lower_quartile":q2[BOOTS//4],
      "T2_median":q2[BOOTS//2],
      "T2_upper_quartile":q2[(3*BOOTS)//4],
      "T3_median":q3[BOOTS//2]}

def selftest():
    n=feats.N
    x=(0.,)*n
    aa=ridge([(x,0.,0.,1.)],[1.]*n)
    assert len(aa)==2 and all(all(v==0 for v in b) for b in aa)
    assert feats.N==19 and BOOTS==24
    assert T2_MIN_ACTION_MARGIN>0 and T3_MAX_ALLOWED_LOSS<0
    print("DACK_V35_ACTION_REGRET_RIDGE_SELFTEST_PASS",flush=True)

if __name__=="__main__":
    selftest()
