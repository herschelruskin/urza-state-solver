#!/usr/bin/env python3
"""v39 single direct T2-action regret with bounded predicted T3 loss.

Retains frozen v37 K−C physical outcome regressors. Policy is:
1) Predict SAME 12 ensemble member signed T2/T3 advantages.
2) Require T2 advantage to cross ±.02 at quartile, not just mean.
3) Require conservative predicted T3 decline <=0.25 for changing.
No independent keep-score model or old Qkeep blending, no new training,
no changes to physical 99-card engine or frozen v33b legal bottom.
Experimental tolerance is 25 percentage points *per changed hand*;
does NOT claim this is acceptable as a cEDH player choice.
"""
from __future__ import annotations
import math
import dack_mulligan_v37_direct_regret as v37
import dack_mulligan_v37_features as feat

SCHEMA="dack_v39_T2_priority_with_per_action_T3_risk_budget_1"
N=12
T2_SIGN_MARGIN=.02
T3_MAX_PREDICTED_CUMULATIVE_LOSS=.25
STAGES=(0,1,2)

def model_check(model):\n    v37.validate(model)\n    assert model["policy_approved"] is False\n    assert model["training_group_n"]==384\n    return model\n\ndef ensemble(model,x):
    v37.validate(model)
    assert len(x)==len(feat.NAMES)
    a2=[];a3=[]
    for e in model["ensemble"]:
        a2.append(v37.forest_value(e["T2"],x))
        a3.append(v37.forest_value(e["T3"],x))
    assert len(a2)==len(a3)==N
    return sorted(a2),sorted(a3)

def choose(model,x,stage,old_keep):
    assert 0<=stage<8
    if stage not in STAGES:
        return bool(old_keep),{
          "old_keep":bool(old_keep),"new_keep":bool(old_keep),
          "reason":"frozen_v27_later_stage"}
    q2,q3=ensemble(model,x)
    old=bool(old_keep);decision=old
    reason="frozen_v27_fallback"
    if not old:
        t2_adv=q2[N//4]
        t3_worst_loss=q3[N//4]
        if t2_adv>T2_SIGN_MARGIN and t3_worst_loss>=-T3_MAX_PREDICTED_CUMULATIVE_LOSS:
            decision=True;reason="v39_T2_regret_KEEP"
    else:
        t2_adv=q2[3*N//4]
        t3_worst_loss=q3[3*N//4]
        if t2_adv<-T2_SIGN_MARGIN and t3_worst_loss<=T3_MAX_PREDICTED_CUMULATIVE_LOSS:
            decision=False;reason="v39_T2_regret_MULL"
    assert decision==old or stage<3
    return decision,{
      "old_keep":old,"new_keep":decision,"reason":reason,
      "T2_lower_quartile":q2[N//4],"T2_median":q2[N//2],
      "T2_upper_quartile":q2[3*N//4],
      "T3_lower_quartile":q3[N//4],"T3_median":q3[N//2],
      "T3_upper_quartile":q3[3*N//4],
      "T2_sign_margin":T2_SIGN_MARGIN,
      "max_predicted_T3_loss_per_changed_hand":T3_MAX_PREDICTED_CUMULATIVE_LOSS,
      "not_calibrated_ensemble_confidence_intervals":True
    }

def selftest():
    assert len(feat.NAMES)==75
    assert N==v37.N==12
    assert 0<T2_SIGN_MARGIN<.1
    assert 0<T3_MAX_PREDICTED_CUMULATIVE_LOSS<.5
    print("DACK_V39_DIRECT_T2_REGRET_AND_T3_RISK_BUDGET_SELFTEST_PASS",flush=True)

if __name__=="__main__":selftest()
