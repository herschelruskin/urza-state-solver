#!/usr/bin/env python3
"""Strictly pool and compare paired-seed flicker baseline vs restored-ramp 5x5."""
from __future__ import annotations
import argparse
from collections import Counter
import glob, json, math
from pathlib import Path
from dack_flicker_pool_1024 import pool, read_shard

VARIANTS=("baseline","ramp_restore5")
METRICS=(("T1",1),("cumulative_T2",2),("cumulative_T3",3))

def all_rows(files,n):
    rows={}
    for file in files:
        data=read_shard(file)
        for r in data["rows"]:
            gid=int(r["game_id"])
            if gid in rows: raise ValueError("Duplicate game ID "+str(gid))
            rows[gid]=r
    if set(rows)!=set(range(n)):raise ValueError("Missing or excess game IDs")
    return rows

def evaluate(root,n,seed_scheme="seed_base + game_id * 1000003"):
    out={}
    game_data={}
    for variant in VARIANTS:
        files=sorted(glob.glob(str(Path(root)/variant/"*.json.gz")))
        out[variant]=pool(files,n,variant)
        game_data[variant]=all_rows(files,n)
        if out[variant]["seed_scheme"]!=seed_scheme:
            raise ValueError("Unexpected seed scheme")
    for k in ("seed_base","beam","mulligan_policy","seed_scheme","objective"):
        if out[VARIANTS[0]][k]!=out[VARIANTS[1]][k]:
            raise ValueError("Mixed batch metadata for "+k)
    if out[VARIANTS[0]]["deck_sha256"]==out[VARIANTS[1]]["deck_sha256"]:
        raise ValueError("Ablation and baseline deck hashes identical")
    A=game_data["baseline"];B=game_data["ramp_restore5"]
    if any(A[i]["seed"]!=B[i]["seed"] or A[i]["seat"]!=B[i]["seat"] for i in range(n)):
        raise ValueError("Paired games have different seeds or seat allocation")
    diffs={}
    for metric,turn in METRICS:
        b_good=0; a_good=0; better=worse=same_positive=same_negative=0
        for i in range(n):
            aa=bool(A[i]["win_turn"] and int(A[i]["win_turn"])<=turn)
            bb=bool(B[i]["win_turn"] and int(B[i]["win_turn"])<=turn)
            a_good+=aa;b_good+=bb
            if bb and not aa:better+=1
            elif aa and not bb:worse+=1
            elif aa: same_positive+=1
            else:same_negative+=1
        d=(better-worse)/n
        discordant=(better+worse)/n
        se=math.sqrt(max(0,(discordant-d*d)/n))
        diffs[metric]={
            "baseline_count":a_good,"ramp_restore5_count":b_good,
            "baseline_pct":100*a_good/n,"ramp_restore5_pct":100*b_good/n,
            "delta_pp":100*d,"paired_ci95_pp":[100*(d-1.95996398454*se),
                                             100*(d+1.95996398454*se)],
            "ramp5_only_wins":better,"baseline_only_wins":worse,
            "both_win":same_positive,"neither_win":same_negative,
        }
    keep={}
    for v in VARIANTS:
        rows=game_data[v]
        keep[v]={
            "mean_keep_n":sum(int(r["keep_n"]) for r in rows.values())/n,
            "keep_n_counts":dict(sorted(Counter(str(r["keep_n"]) for r in rows.values()).items()))
        }
    return {
        "schema":"dack_flicker_ramp5_paired_n1024_v1",
        "n_paired_games":n,
        "variants":{v:{"deck_sha256":out[v]["deck_sha256"],
            "outcomes":out[v]["outcomes"],"mulligans":keep[v]} for v in VARIANTS},
        "same_seed_base":out["baseline"]["seed_base"],
        "gameplay_beam":out["baseline"]["beam"],
        "mulligan_policy":out["baseline"]["mulligan_policy"],
        "paired_comparison":diffs,
        "notes":[
            "Legal 99-card flicker deck is the constant backbone; exactly five artifacts exchanged.",
            "Flicker combo is assumed to succeed after eligible Dack cast; Abdel+Solar pair in hand is a provisional loss.",
            "Opponents do not interact; Smothering Tithe produces 3 Treasures per completed opponent cycle.",
            "Mana Vault/Monolith/Mirage Mirror and all five restored ramp artifacts receive the latest shared engine fixes.",
            "Matched seeds and seats; deck substitutions can change shuffle-visible cards, decisions and mulligans.",
            "Wald approximate paired-difference CIs describe sampling variability, not mechanical correctness.",
        ],
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",default="shards")
    ap.add_argument("--n",type=int,default=1024)
    ap.add_argument("--out",default="dack_flicker_ramp5_paired_n1024.json")
    a=ap.parse_args()
    result=evaluate(a.root,a.n)
    Path(a.out).write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"pass","n":a.n,"beam":result["gameplay_beam"],
                      "paired":result["paired_comparison"]}),flush=True)

if __name__=="__main__":
    main()
