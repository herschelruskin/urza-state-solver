#!/usr/bin/env python3
"""v27 strictly T2-targeted London DP; preserved frozen v14 bottom model."""
import json
import dack_paired_counterfactual_v22_all_stage_real_keep_DP_20261101 as original
ref=original.ref
MODEL="models/dack_v27_expanded_T2_only_value_EXPERIMENTAL.json"
DP="models/dack_v27_T2_only_continuations_EXPERIMENTAL.json"
POLICY="dack_v27_expanded_T2_only_DP_UNAPPROVED"

def audit():
    original.estimator.selftest()
    original.install(modelpath=MODEL,dppath=DP)
    ref.MULLIGAN_POLICY_NAME=POLICY
    ref.MULLIGAN_SAMPLER_NAME="v27_T2_only_real_value_no_mulligan_beam"
    ref.RULES_VERSION=POLICY+"_"+original.MODEL_SHA[:12]+"_"+original.DP_SHA[:12]
    r=ref.audit()
    assert r["status"]=="PASS" and r["mulligan_policy"]==POLICY
    assert original.MODEL["T3_reward_is_exactly_zero"] is True
    assert original.MODEL["training_games"]==256
    assert original.MODEL["validation_games"]==64
    assert original.MODEL["deployed_policy_approved"] is False
    assert original.DP["model_approved"] is False
    assert original.DP["model_sha256"]==original.estimator.model_hash(original.MODEL)
    return dict(r,model_hash=original.MODEL_SHA,continuation_hash=original.DP_SHA,
                t3_objective_reward=0,lookahead_mulligan_beam=0,actual_beam160=True,
                policy_approved=False,frozen_bottom="v14_128")

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--audit",action="store_true")
    p.add_argument("--game",type=int,default=98000)
    a=p.parse_args()
    print("V27_T2_ONLY_DP_AUDIT_PASS",json.dumps(audit()),flush=True)
    if not a.audit:
        if not 98000<=a.game<99000:raise ValueError("reserved prospective 98k only")
        print("V27_REAL_GAME",json.dumps(ref.game("one_key_34",a.game)),flush=True)
