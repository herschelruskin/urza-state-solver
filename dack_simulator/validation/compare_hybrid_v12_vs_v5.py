#!/usr/bin/env python3
"""Research-only paired v5 vs margin-gated hybrid v12 on untouched outer game IDs.

Fixed ambiguity margin 0.075 was chosen after inspecting 42k developmental
failures. This research must use UNSEEN 43k seeds. Both candidate and baseline
use the same physical stage shuffles, stable dice and beam-160 actual gameplay.
"""
from __future__ import annotations
import argparse
import gzip
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
CHILD=(
    "import json,sys,time\n"
    "variant=sys.argv[1];gid=int(sys.argv[2]);pol=sys.argv[3]\n"
    "if pol=='v5':\n"
    " import dack_paired_counterfactual_v5_stable_chance_20261031 as p\n"
    " p.audit();sim=p.reference\n"
    "elif pol=='hybrid_m075':\n"
    " import dack_paired_counterfactual_v12_hybrid_m075_20261031 as p\n"
    " p.audit();sim=p.ref\n"
    " assert p.learned.MODEL['deployed_policy_approved'] is False\n"
    "else:raise ValueError('unrecognized research policy')\n"
    "start=time.perf_counter();r=sim.game(variant,gid)\n"
    "print('RESEARCH_GAME',json.dumps({'seat':r['seat'],"
    "'win_turn':r['win_turn'],'keep_n':r['keep_n'],"
    "'hand':r['hand'],'history':r['history'],"
    "'first3':r['first3'],'seconds':round(time.perf_counter()-start,4),"
    "'fallback_stages':int(getattr(p,'STATS',{}).get('beam_fallback_stages',0)),"
    "'total_london_stages':int(getattr(p,'STATS',{}).get('london_stages',0))}),flush=True)\n"
)

def one(policy,game_id,variant):
    r=subprocess.run([sys.executable,"-c",CHILD,variant,str(game_id),policy],
                     cwd=ROOT,text=True,capture_output=True,timeout=1200)
    if r.returncode!=0:
        print("RESEARCH_GAME_ERROR",policy,game_id,r.stdout[-2500:],r.stderr[-2500:],flush=True)
        raise RuntimeError("Research child gameplay failure")
    matches=[line[len("RESEARCH_GAME "):] for line in r.stdout.splitlines()
             if line.startswith("RESEARCH_GAME ")]
    if len(matches)!=1:raise RuntimeError("Missing child record")
    return json.loads(matches[0])

def main(start,games,out,variant="one_key_34"):
    if games<1 or start<43000 or start+games-1>=44000:
        raise ValueError("Hybrid experimental policy evaluation reserved 43000-43999 only")
    rows=[]
    for game_id in range(start,start+games):
        baseline=one("v5",game_id,variant)
        candidate=one("hybrid_m075",game_id,variant)
        if baseline["seat"]!=candidate["seat"]:
            raise AssertionError("Paired game seat changed")
        rows.append({"game_id":game_id,"v5":baseline,"hybrid_m075":candidate})
        print("V12_HYBRID_PAIRED_GAME",game_id,{
            "v5":(baseline["win_turn"],baseline["keep_n"],baseline["seconds"]),
            "hybrid_m075":(candidate["win_turn"],candidate["keep_n"],candidate["seconds"])
        },flush=True)
    stats={}
    for name in ("v5","hybrid_m075"):
        r=[row[name] for row in rows]
        stats[name]={
            "n":len(r),"T1":sum(x["win_turn"]==1 for x in r),
            "T2":sum(0<x["win_turn"]<=2 for x in r),
            "T3":sum(0<x["win_turn"]<=3 for x in r),
            "mean_keep":sum(x["keep_n"] for x in r)/len(r),
            "total_seconds":round(sum(x["seconds"] for x in r),4),
            "total_fallback_stages":sum(x.get("fallback_stages",0) for x in r),
            "total_london_stages":sum(x.get("total_london_stages",0) for x in r)
        }
    diffs=[int(0<x["hybrid_m075"]["win_turn"]<=2)-int(0<x["v5"]["win_turn"]<=2) for x in rows]
    result={
        "status":"PASS","schema":"dack_hybrid_m075_research_paired_v1",
        "game_range":[start,start+games-1],"variant":variant,
        "same_physical_stage_shuffle_and_seat":True,
        "can_have_different_actual_draws_due_to_different_keep_stage":True,
        "experimental_model_approved":False,
        "actual_gameplay_beam":160,
        "metrics":stats,
        "paired_T2_gains":diffs.count(1),
        "paired_T2_losses":diffs.count(-1),
        "paired_T2_ties":diffs.count(0),
        "warning":"Low-N paired research screen only; cannot claim noninferiority.",
        "rows":rows
    }
    target=Path(out);target.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(target,"wt") as f:json.dump(result,f)
    print("V12_HYBRID_RESEARCH_PAIR_PASS",json.dumps({
        k:v for k,v in result.items() if k!="rows"},sort_keys=True),flush=True)
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--start",type=int,default=43000)
    p.add_argument("--games",type=int,default=2)
    p.add_argument("--variant",default="one_key_34")
    p.add_argument("--out",default="shards/v12_research_43000.json.gz")
    a=p.parse_args()
    main(a.start,a.games,a.out,a.variant)
