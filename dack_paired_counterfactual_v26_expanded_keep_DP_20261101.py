#!/usr/bin/env python3
"""Experimental v26 enlarged real-value forest with the frozen v14 bottom selector.

No model promotion, no 96k evaluation fitting, no speculative mulligan beam.
"""
import hashlib
import json
from pathlib import Path
import dack_paired_counterfactual_v22_all_stage_real_keep_DP_20261101 as original

ref=original.ref
MODEL_PATH="models/dack_v26_expanded_real_keep_value_EXPERIMENTAL.json"
DP_PATH="models/dack_v26_expanded_all_stage_continuations_EXPERIMENTAL.json"
POLICY="dack_v26_expanded_real_keep_value_DP_UNAPPROVED"

def audit():
    original.estimator.selftest()
    original.install(modelpath=MODEL_PATH,dppath=DP_PATH)
    ref.MULLIGAN_POLICY_NAME=POLICY
    ref.MULLIGAN_SAMPLER_NAME="v26_real_utility_London_DP_no_lookahead_beam"
    ref.RULES_VERSION=POLICY+"_"+original.MODEL_SHA[:12]+"_"+original.DP_SHA[:12]
    status=ref.audit()
    assert status["status"]=="PASS"
    assert status["mulligan_policy"]==POLICY
    assert original.MODEL["training_games"]==256
    assert original.MODEL["validation_games"]==64
    assert original.MODEL["deployed_policy_approved"] is False
    assert original.DP["model_approved"] is False
    assert original.DP["model_sha256"]==original.estimator.model_hash(original.MODEL)
    return dict(status,mulligan_beam=0,actual_gameplay_beam=160,
                model_approved=False,model_sha256=original.MODEL_SHA,
                continuation_sha256=original.DP_SHA,
                first_free_seven_supported=True,
                bottom_selector="unchanged_frozen_v14_128")

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--audit",action="store_true")
    p.add_argument("--game",type=int,default=97000)
    args=p.parse_args()
    print("V26_EXPANDED_VALUE_AUDIT_PASS",json.dumps(audit()),flush=True)
    if not args.audit:
        if not 97000<=args.game<98000:
            raise ValueError("v26 requires fresh never-examined 97k physical IDs")
        print("V26_EXPANDED_REAL_GAME",json.dumps(ref.game("one_key_34",args.game)),flush=True)
