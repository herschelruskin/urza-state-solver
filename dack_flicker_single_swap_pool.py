#!/usr/bin/env python3
"""Strict N512 matched-seed baseline vs five individual ramp restorations."""
from __future__ import annotations
import argparse, glob, json, math
from pathlib import Path
from dack_flicker_pool_1024 import pool, read_shard

VARIANTS=("baseline","single_ramp_0","single_ramp_1","single_ramp_2","single_ramp_3","single_ramp_4")
SWAPS=(
    ("The One Ring","Coalition Relic"),
    ("Throne of Eldraine","Implements of Sacrifice"),
    ("Staff of Compleation","Tooth of Ramos"),
    ("Mirage Mirror","Everflowing Chalice"),
    ("Rings of Brighthearth","Bucknard's Everfull Purse"),
)
def game_map(path,n,variant):
    fs=sorted(glob.glob(str(Path(path)/variant/"*.json.gz")))
    report=pool(fs,n,variant)
    rows={}
    for f in fs:
        dat=read_shard(f)
        for row in dat["rows"]:
            gid=int(row["game_id"])
            if gid in rows:raise ValueError("duplicate game_id")
            rows[gid]=row
    if set(rows)!=set(range(n)):raise ValueError("IDs missing")
    return report,rows

def paired(a,b,n,k):
    a_count=b_count=better=worse=0
    for i in range(n):
        aa=bool(a[i]["win_turn"] and int(a[i]["win_turn"])<=k)
        bb=bool(b[i]["win_turn"] and int(b[i]["win_turn"])<=k)
        a_count+=aa;b_count+=bb
        if bb and not aa:better+=1
        if aa and not bb:worse+=1
    d=(better-worse)/n
    se=math.sqrt(max(0,((better+worse)/n-d*d)/n))
    return dict(baseline_count=a_count,restored_count=b_count,
                baseline_pct=100*a_count/n,restored_pct=100*b_count/n,
                delta_pp=100*d,ci95_pp=[100*(d-1.95996398454*se),100*(d+1.95996398454*se)],
                better=better,worse=worse,discordant=better+worse)

def evaluate(path,n):
    reports={};games={}
    for v in VARIANTS:
        reports[v],games[v]=game_map(path,n,v)
    base=reports["baseline"]
    for v in VARIANTS[1:]:
        rep=reports[v]
        for k in ("objective","n","beam","seed_base","seed_scheme","mulligan_policy"):
            if base[k]!=rep[k]:raise ValueError(f"Incomparable metadata {v} {k}")
        if base["deck_sha256"]==rep["deck_sha256"]:raise ValueError(f"Identical decks: {v}")
        for i in range(n):
            if games["baseline"][i]["seed"]!=games[v][i]["seed"] or games["baseline"][i]["seat"]!=games[v][i]["seat"]:
                raise ValueError(f"Paired seed/seat mismatch: {v}/{i}")
    comparison={}
    for i,(old,new) in enumerate(SWAPS):
        v="single_ramp_"+str(i)
        comparison[v]={"removed":old,"added":new,
                       "T1":paired(games["baseline"],games[v],n,1),
                       "T2_cumulative":paired(games["baseline"],games[v],n,2),
                       "T3_cumulative":paired(games["baseline"],games[v],n,3)}
    rank=sorted(VARIANTS[1:],key=lambda v:comparison[v]["T2_cumulative"]["delta_pp"],reverse=True)
    return {"status":"complete","n_per_arm":n,"gameplay_beam":base["beam"],
            "same_seed_scheme":base["seed_scheme"],"baseline_outcomes":base["outcomes"],
            "single_swap_results":comparison,"T2_ranking_best_first":rank,
            "limitations":["Single-slot effects may be nonadditive; a five-card package was separately measured at N1024.",
                           "95% paired Wald intervals are exploratory, not multiplicity adjusted.",
                           "Dack cast is assumed to win unless Abdel+Solar are both in hand.",
                           "No opponent responses, removal, or interaction."],
            "deck_hashes":{v:reports[v]["deck_sha256"] for v in VARIANTS}}
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--root",default="shards")
    parser.add_argument("--n",type=int,default=512)
    parser.add_argument("--out",default="dack_flicker_single_swap_n512.json")
    args=parser.parse_args()
    o=evaluate(args.root,args.n)
    Path(args.out).write_text(json.dumps(o,indent=2)+"\n")
    print(json.dumps({"status":o["status"],"n":o["n_per_arm"],
                      "ranking":[{"name":v,**o["single_swap_results"][v]["T2_cumulative"]}
                          for v in o["T2_ranking_best_first"]]}),flush=True)
if __name__=="__main__":
    main()
