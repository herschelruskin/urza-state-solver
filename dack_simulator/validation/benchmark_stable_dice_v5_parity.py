#!/usr/bin/env python3
"""Same-seed strict-bounded-v5 reference versus witnessed version."""
from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import dack_paired_counterfactual_v5_stable_chance_20261031 as v5

def one(game_id,variant):
    v5.audit()
    v5.without_witness()
    start=time.perf_counter()
    baseline=v5.reference.game(variant,game_id)
    ref_seconds=time.perf_counter()-start
    v5.install()
    v5.witness.counters.clear()
    start=time.perf_counter()
    accelerated=v5.reference.game(variant,game_id)
    fast_seconds=time.perf_counter()-start
    fields=("seat","keep_n","hand","first3","win_turn","history","frontier_events")
    mismatch=[field for field in fields if baseline[field]!=accelerated[field]]
    report={"schema":"dack_stable_dice_witness_parity_v1","status":"FAIL" if mismatch else "PASS",
            "variant":variant,"game_id":game_id,"mismatch":mismatch,
            "reference_seconds":round(ref_seconds,4),"accelerated_seconds":round(fast_seconds,4),
            "speedup":round(ref_seconds/fast_seconds,3),
            "win_turn":baseline["win_turn"],"keep_n":baseline["keep_n"],
            "terminal_witness_stats":dict(v5.witness.counters)}
    print("STABLE_DICE_WITNESS_PARITY",json.dumps(report,sort_keys=True),flush=True)
    if mismatch:
        for field in mismatch:
            print("WITNESS_FIELD_DIFFERENCE",field,json.dumps({
                "reference":baseline[field],"witness":accelerated[field]}),flush=True)
        raise AssertionError("Stable-dice win-only search still changes result")
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--game-id",type=int,default=0)
    p.add_argument("--variant",choices=list(v5.reference.VARIANTS),default="one_key_34")
    a=p.parse_args()
    one(a.game_id,a.variant)
