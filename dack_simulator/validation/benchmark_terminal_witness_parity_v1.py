#!/usr/bin/env python3
"""Original strict-v3 versus witness-accelerated strict-v4 parity benchmark."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))

import dack_paired_counterfactual_v4_witness_20261031 as opt

def compare(game_id,variant):
    ref=opt.reference
    opt.audit()
    opt.witness.uninstall()
    opt.bounded.install()
    start=time.perf_counter()
    baseline=ref.game(variant,game_id)
    ref_seconds=time.perf_counter()-start

    opt.install()
    opt.witness.counters.clear()
    start=time.perf_counter()
    accelerated=ref.game(variant,game_id)
    accelerated_seconds=time.perf_counter()-start
    fields=("game_id","seat","variant","keep_n","hand","first3",
            "history","frontier_events","win_turn")
    discrepancies=[key for key in fields if baseline[key]!=accelerated[key]]
    out={
        "schema":"exact_london_witness_parity_v1",
        "game_id":game_id,"variant":variant,
        "status":"PASS" if not discrepancies else "FAIL",
        "mismatched_fields":discrepancies,
        "strict_reference_seconds":round(ref_seconds,4),
        "witness_seconds":round(accelerated_seconds,4),
        "speedup":round(ref_seconds/accelerated_seconds,4),
        "witness_counts":dict(opt.witness.counters),
        "keep_n":baseline["keep_n"],"win_turn":baseline["win_turn"],
    }
    print("WITNESS_EXACT_PARITY",json.dumps(out,sort_keys=True),flush=True)
    if discrepancies:
        for key in discrepancies:
            print("MISMATCH",key,json.dumps({"before":baseline[key],
                  "after":accelerated[key]}),flush=True)
        raise AssertionError("Witness acceleration changed recorded policy or win turn")
    return out

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--game-id",type=int,default=0)
    p.add_argument("--variant",choices=list(opt.reference.VARIANTS),default="one_key_34")
    a=p.parse_args()
    compare(a.game_id,a.variant)
