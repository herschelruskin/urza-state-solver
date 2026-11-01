#!/usr/bin/env python3
"""v38 single predeclared T2-weighted action-regret policy, no new fitting.

Frozen v37 regression predicts the *paired* physical action difference:
A2 = P(T<=2|KEEP)-P(T<=2|MULL)
A3 = P(T<=3|KEEP)-P(T<=3|MULL)
U = A2+0.5*A3, which is P(by T2)+0.5*P(by T3).

Do NOT confuse with P(by T2)+0.5*P(EXACT T3) = .5*(A2+A3).
The ensemble is paired by tree seed: compute U from each SAME-member
T2/T3 regressor before taking quartiles. Aggregating independently
sorted T2 and T3 quantiles breaks their correlation.
No independent v27 utility score blending. No v5 teacher action label.
"""
from __future__ import annotations
import math
import dack_mulligan_v37_direct_regret as v37
import dack_mulligan_v37_features as feat

SCHEMA="dack_v38_predeclared_T2_plus_half_cumulative_T3_advantage"
T3_CUMULATIVE_WEIGHT=.5
UTILITY_DEADBAND=.02
BOOT_MODELS=12
STAGES=(0,1,2)

def model_check(model):
    v37.validate(model)
    assert v37.N==BOOT_MODELS and v37.N==len(model["ensemble"])
    assert model["source_v33b_sha256"]
    assert model["127k_validation_unseen"] is True # archived source training contract
    assert model["policy_approved"] is False
    return model

def member_values(model,x):
    model_check(model)
    if len(x)!=len(feat.NAMES):raise ValueError("feature schema mismatch")
    a=[]
    for e in model["ensemble"]:
        q2=v37.forest_value(e["T2"],x)
        q3=v37.forest_value(e["T3"],x)
        u=q2+T3_CUMULATIVE_WEIGHT*q3
        assert math.isfinite(u) and -1.5<=u<=1.5
        a.append((q2,q3,u))
    assert len(a)==BOOT_MODELS
    return a

def choose(model,x,stage,old_keep):
    assert 0<=stage<8
    if stage not in STAGES:
        return bool(old_keep),{
            "old_keep":bool(old_keep),"new_keep":bool(old_keep),
            "reason":"frozen_v27_later_stage"}
    values=member_values(model,x)
    u=sorted(z[2] for z in values)
    a2=sorted(z[0] for z in values)
    a3=sorted(z[1] for z in values)
    old=bool(old_keep);new=old
    reason="frozen_v27_fallback"
    if not old and u[BOOT_MODELS//4]>UTILITY_DEADBAND:
        new=True;reason="v38_weighted_regret_KEEP"
    elif old and u[3*BOOT_MODELS//4]<-UTILITY_DEADBAND:
        new=False;reason="v38_weighted_regret_MULL"
    return new,{
      "old_keep":old,"new_keep":new,"reason":reason,
      "utility_definition":"PbyT2_plus_half_PbyT3_cumulative",
      "utility_weight_T3_cumulative":T3_CUMULATIVE_WEIGHT,
      "U_lower_quartile":u[BOOT_MODELS//4],
      "U_median":u[BOOT_MODELS//2],
      "U_upper_quartile":u[3*BOOT_MODELS//4],
      "T2_median":a2[BOOT_MODELS//2],
      "T3_median":a3[BOOT_MODELS//2],
      "ensemble_quartile_stability_not_formal_CI":True
    }

def selftest():
    assert len(feat.NAMES)==75
    assert STAGES==(0,1,2)
    assert T3_CUMULATIVE_WEIGHT==.5 and UTILITY_DEADBAND==.02
    # Crucial algebra identity for all possible success indicators:
    for t in (0,1,2,3):
        p2=int(t in (1,2));p3=int(t in (1,2,3));exact3=int(t==3)
        assert abs((p2+.5*p3)-(1.5*p2+.5*exact3))<1e-12
        assert abs((p2+.5*exact3)-.5*(p2+p3))<1e-12
    print("DACK_V38_PAIRED_ENSEMBLE_CUMULATIVE_UTILITY_SELFTEST_PASS",flush=True)

if __name__=="__main__":selftest()
