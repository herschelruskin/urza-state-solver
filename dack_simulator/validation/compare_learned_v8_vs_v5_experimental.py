#!/usr/bin/env python3
"""STRICTLY RESEARCH-ONLY paired v5 vs unapproved learned v8 policy.

Model remains deployed_policy_approved=false. This script permits evaluating
its behavior only in independent, frozen game-ID bands and does not promote it.
Each policy's single-game goldfish simulation is spawned in a fresh Python
process to avoid patch/state leakage. Actual gameplay beam remains 160.

This is a first *behavioral screening* not evidence of noninferiority.
"""
from __future__ import annotations
import argparse
import gzip
import json
from pathlib import Path
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))

from dack_paired_counterfactual_v1_20261030 import SEED_STRIDE,SPEC

MODEL="models/dack_v10_selected_calibration_EXPERIMENTAL.json"
DP_DIR="models"
ROOT=Path(__file__).resolve().parents[2]

CHILD=(
    "import json,sys,time\n"
    "variant=sys.argv[1];gid=int(sys.argv[2]);pol=sys.argv[3]\n"
    "if pol=='v5':\n"
    " import dack_paired_counterfactual_v5_stable_chance_20261031 as p\n"
    " p.audit();sim=p.reference\n"
    "elif pol=='learned_experimental':\n"
    " import dack_paired_counterfactual_v8_learned_london_20261031 as p\n"
    " p.audit('models/dack_v10_selected_calibration_EXPERIMENTAL.json',"
    "'models',allow_diagnostic=True);sim=p.ref\n"
    " assert p.MODEL['deployed_policy_approved'] is False\n"
    "else:raise ValueError('bad policy')\n"
    "t=time.perf_counter();r=sim.game(variant,gid)\n"
    "print('POLICY_RESULT',json.dumps({'win_turn':r['win_turn'],"
    "'keep_n':r['keep_n'],'seat':r['seat'],'hand':r['hand'],"
    "'first3':r['first3'],'history':r['history'],"
    "'seconds':round(time.perf_counter()-t,4)}),flush=True)\n"
)

def evaluate(policy,gid,variant):
    result=subprocess.run([sys.executable,"-c",CHILD,variant,str(gid),policy],
                          cwd=ROOT,text=True,capture_output=True,timeout=1200)
    if result.returncode:
        print("EXPERIMENTAL_CHILD_ERROR",policy,gid,result.stdout[-2000:],
              result.stderr[-2000:],flush=True)
        raise RuntimeError("child sim failed")
    matches=[x[len("POLICY_RESULT "):] for x in result.stdout.splitlines()
             if x.startswith("POLICY_RESULT ")]
    if len(matches)!=1:
        raise AssertionError(("expected one child record",policy,gid))
    return json.loads(matches[0])

def main(start,games,output,variant="one_key_34"):
    if start<41000 or start+games>42000 or games<1:
        raise ValueError("policy test must use reserved independent 41k game IDs")
    rows=[]
    for gid in range(start,start+games):
        ref=evaluate("v5",gid,variant)
        candidate=evaluate("learned_experimental",gid,variant)
        assert ref["seat"]==candidate["seat"]
        # Same physical game ID yields the same seat and per-stage permutations.
        # Different keep stages can legitimately draw different first3.
        rows.append({"game_id":gid,"v5":ref,"learned":candidate})
        print("LEARNED_EXPERIMENTAL_PAIR",gid,
              {"v5":(ref["keep_n"],ref["win_turn"],ref["seconds"]),
               "learned":(candidate["keep_n"],candidate["win_turn"],candidate["seconds"])},
              flush=True)
    def measures(name):
        r=[x[name] for x in rows]
        return {"n":len(r),
                "T1":sum(x["win_turn"]==1 for x in r),
                "T2":sum(0<x["win_turn"]<=2 for x in r),
                "T3":sum(0<x["win_turn"]<=3 for x in r),
                "mean_keep":sum(x["keep_n"] for x in r)/len(r),
                "total_seconds":sum(x["seconds"] for x in r)}
    discord=[int(0<x["learned"]["win_turn"]<=2)-
             int(0<x["v5"]["win_turn"]<=2) for x in rows]
    report={
        "schema":"dack_experimental_learned_london_v8_vs_v5_paired_v1",
        "status":"PASS","game_range":[start,start+games-1],
        "variant":variant,"policy_model_still_unapproved":True,
        "no_mulligan_beam_in_learned_policy":True,
        "actual_gameplay_beam":160,
        "physical_shuffle_seed_and_per_stage_slot_order_paired":True,
        "realized_draws_can_differ_if_mulligan_stage_differs":True,
        "metrics":{"v5":measures("v5"),"learned":measures("learned")},
        "learned_T2_gains":discord.count(1),
        "learned_T2_losses":discord.count(-1),
        "learned_T2_ties":discord.count(0),
        "warning":"Tiny research diagnostic. Cannot infer noninferiority; model calibrated for v7-selected hands, not learned-selected hands.",
        "rows":rows}
    target=Path(output);target.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(target,"wt") as out:json.dump(report,out)
    print("LEARNED_EXPERIMENTAL_PAIRED_PASS",json.dumps({
        k:v for k,v in report.items() if k!="rows"},sort_keys=True),flush=True)
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--start",type=int,default=41000)
    p.add_argument("--games",type=int,default=2)
    p.add_argument("--variant",default="one_key_34")
    p.add_argument("--out",default="shards/learned_exp_41000.json.gz")
    a=p.parse_args()
    main(a.start,a.games,a.out,a.variant)
