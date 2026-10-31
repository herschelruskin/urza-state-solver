#!/usr/bin/env python3
"""E2E audit: all London decisions exactly match reference when bounding enabled.

Run in one Python interpreter with complete cache reset between modes.
Do not claim faster until the exact decision-parity assertions pass.
"""
from __future__ import annotations
import argparse
import json
import time
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import dack_paired_counterfactual_v1_20261030 as reference
import dack_mulligan_branchbound_v1_20261031 as bounded

def one(variant,game_id):
    if reference.d.dack_bottom_weighted_ev_seat is not bounded._ORIGINAL:
        bounded.uninstall()
    reference.audit()
    start=time.perf_counter()
    baseline=reference.game(variant,game_id)
    elapsed_ref=time.perf_counter()-start

    bounded.reset_statistics()
    bounded.install()
    try:
        start=time.perf_counter()
        candidate=reference.game(variant,game_id)
        elapsed_bounded=time.perf_counter()-start
    finally:
        bounded.uninstall()
    comparable=("game_id","seat","variant","keep_n","hand",
                "first3","win_turn","history","frontier_events")
    differences=[k for k in comparable if baseline[k]!=candidate[k]]
    report={
        "schema":"dack_bounded_exact_parity_v1",
        "variant":variant,"game_id":game_id,
        "status":"PASS" if not differences else "FAIL",
        "different_fields":differences,
        "reference_seconds":round(elapsed_ref,4),
        "bounded_seconds":round(elapsed_bounded,4),
        "speedup":round(elapsed_ref/elapsed_bounded,4) if elapsed_bounded else None,
        "reference_win_turn":baseline["win_turn"],
        "bounded_win_turn":candidate["win_turn"],
        "keep_n":baseline["keep_n"],
        "bounded_statistics":bounded.get_statistics(),
    }
    print("BOUNDED_EXACT_POLICY_PARITY",json.dumps(report,sort_keys=True),flush=True)
    if differences:
        for key in differences:
            print("PARITY_MISMATCH",key,json.dumps({
                "reference":baseline[key],"bounded":candidate[key]},default=str),
                flush=True)
        raise AssertionError("bounded evaluator changed goldfish outcome or London policy")
    return report

if __name__=="__main__":
    a=argparse.ArgumentParser()
    a.add_argument("--variant",default="one_key_34",choices=list(reference.VARIANTS))
    a.add_argument("--game-id",type=int,default=0)
    x=a.parse_args()
    one(x.variant,x.game_id)
