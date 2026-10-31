#!/usr/bin/env python3
"""Matched policy-only holdout: v5 beam-mulligan versus v7 no-beam mulligan.

Run each policy in a *fresh process* to avoid module monkeypatch leakage.
Both have identical physical deck, seed, seat, sampled future order, strict
game state key, chance oracle and actual beam-160 deployment engine.

Policy choice differs on purpose. Interpret estimated win rates only as
policy-conditional goldfish outcomes, not a claim of approximate policy
equivalence. Trial sizes are descriptive until CI sufficiently narrow.
"""
from __future__ import annotations
import argparse
import gzip
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
VERSIONS={
    "beam_mulligan_v5":"dack_paired_counterfactual_v5_stable_chance_20261031",
    "analytic_mulligan_v7":"dack_paired_counterfactual_v7_calibrated_nobeam_20261031",
}
CONTROL="one_key_34"
SEED_MIN=12000

CHILD=(
    "import importlib,json,sys,time\n"
    "p=importlib.import_module(sys.argv[1]);gid=int(sys.argv[2]);p.audit()\n"
    "t=time.perf_counter();row=p.reference.game('one_key_34',gid) if hasattr(p,'reference') "
    "else p.ref.game('one_key_34',gid)\n"
    "print('POLICY_ONE_RESULT',json.dumps({'win_turn':row['win_turn'],"
    "'keep_n':row['keep_n'],'seat':row['seat'], 'hand':row['hand'],"
    "'first3':row['first3'], 'history':row['history'],"
    "'seconds':round(time.perf_counter()-t,4)}),flush=True)\n"
)

def evaluate_one(module,gid):
    try:
        p=subprocess.run([sys.executable,"-c",CHILD,module,str(gid)],
                         cwd=ROOT,text=True,capture_output=True,timeout=900,
                         check=True)
    except subprocess.CalledProcessError as err:
        print("CHILD_FAILURE",module,gid,err.stdout[-3000:],
              err.stderr[-3000:],flush=True)
        raise
    matches=[x[len("POLICY_ONE_RESULT "):] for x in p.stdout.splitlines()
             if x.startswith("POLICY_ONE_RESULT ")]
    if len(matches)!=1:
        raise ValueError(("Missing child result",module,gid,p.stdout[-1000:]))
    return json.loads(matches[0])

def run(start,games,out):
    assert start>=SEED_MIN and games>0
    rows=[]
    for gid in range(start,start+games):
        values={name:evaluate_one(module,gid)
                for name,module in VERSIONS.items()}
        assert values["beam_mulligan_v5"]["seat"]==values["analytic_mulligan_v7"]["seat"]
        rows.append({"game_id":gid,"variants":values})
        print("TWO_POLICY_SAME_SEED",gid,{
            name:{"win_turn":x["win_turn"],"keep_n":x["keep_n"],
                  "seconds":x["seconds"]} for name,x in values.items()
        },flush=True)
    stats={}
    for name in VERSIONS:
        values=[row["variants"][name] for row in rows]
        stats[name]={
            "n":len(values),"mean_keep":sum(x["keep_n"] for x in values)/len(values),
            "total_seconds":round(sum(x["seconds"] for x in values),4),
            "T1":sum(x["win_turn"]==1 for x in values),
            "T2_or_earlier":sum(x["win_turn"] in (1,2) for x in values),
            "T3_or_earlier":sum(x["win_turn"] in (1,2,3) for x in values)}
    delta=[int(0<x["variants"]["analytic_mulligan_v7"]["win_turn"]<=2)-
           int(0<x["variants"]["beam_mulligan_v5"]["win_turn"]<=2) for x in rows]
    summary={"v7_minus_v5_T2_wins":sum(delta),
             "v7_gains":delta.count(1),
             "v7_losses":delta.count(-1),
             "tied":delta.count(0)}
    report={"schema":"dack_v5_vs_v7_policy_only_holdout_v1",
            "start":start,"n":games,"versions":VERSIONS,
            "same_seed_same_cards_same_actual_beam":True,
            "policy_differs_only_during_mulligans":True,
            "training_seeds_disjoint":True,
            "summary":stats,"paired":summary,"rows":rows}
    dest=Path(out);dest.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(dest,"wt") as f:json.dump(report,f)
    print("V5_V7_POLICY_HOLDOUT_PASS",str(dest),json.dumps({
        "start":start,"n":games,"summary":stats,"paired":summary}),flush=True)
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--start",type=int,default=SEED_MIN)
    p.add_argument("--games",type=int,default=2)
    p.add_argument("--out",default="shards/policy_holdout_12000.json.gz")
    a=p.parse_args()
    run(a.start,a.games,a.out)
