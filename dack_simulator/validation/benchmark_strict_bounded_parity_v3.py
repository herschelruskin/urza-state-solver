#!/usr/bin/env python3
"""Proof test for production candidate: strict-key + bounded mulligan v3."""
from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))

import dack_paired_counterfactual_v3_bounded_20261031 as opt

ref=opt.reference
bound=opt.bounded

def audit_pair(game_id,variant):
    opt.audit()
    bound.uninstall()
    tick=time.perf_counter()
    baseline=ref.game(variant,game_id)
    base_sec=time.perf_counter()-tick
    bound.install()
    bound.reset_statistics()
    tick=time.perf_counter()
    optimized=ref.game(variant,game_id)
    opt_sec=time.perf_counter()-tick
    same=baseline==optimized
    report={
        "game_id":game_id,"variant":variant,
        "status":"PASS" if same else "FAIL",
        "strict_reference_seconds":round(base_sec,3),
        "strict_bounded_seconds":round(opt_sec,3),
        "speedup":round(base_sec/opt_sec,4) if opt_sec else None,
        "same_complete_game_result":same,
        "keep_n":baseline["keep_n"],"win_turn":baseline["win_turn"],
        "bounding_counts":bound.get_statistics()
    }
    print("STRICT_BOUND_POLICY_PARITY",json.dumps(report,sort_keys=True),flush=True)
    if not same:
        for key in baseline:
            if baseline[key]!=optimized[key]:
                print("DIFFERING_FIELD",key,baseline[key],optimized[key])
        raise AssertionError("strict bounded runner differs from strict reference")
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--game-id",type=int,default=0)
    p.add_argument("--variant",choices=list(ref.VARIANTS),default="one_key_34")
    a=p.parse_args()
    audit_pair(a.game_id,a.variant)
