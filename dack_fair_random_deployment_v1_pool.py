#!/usr/bin/env python3
"""Paired T1/T2/T3 rates and roll audits, no-oracle Dack Boonweaver v1."""
from __future__ import annotations
from collections import Counter
import argparse, glob, gzip, hashlib, json, math
from pathlib import Path

SEED_BASE=7604096001
BASE_SHA="3a10a02e1aae070645129fa85ed94240f1ae9d5447e3711f7621f92064d9f129"
BUCK_SHA="f130ff4c9c0fbc888525070877fe820caba03e836e0be66ec60ea3410e950068"

def fetch(path,variant,n,beam,cap):
    files=sorted(glob.glob(path,recursive=True))
    assert files,(path,"empty")
    rows={}
    for file in files:
        with gzip.open(file,"rt") as f:d=json.load(f)
        assert d["schema"]=="dack_fair_random_deployment_v1"
        assert d["variant"]==variant and d["beam"]==beam and d["candidate_cap"]==cap
        assert d["seed_base"]==SEED_BASE
        assert d["deck_sha256"]==(BASE_SHA if variant=="current" else BUCK_SHA)
        assert len(d["rows"])==d["games"]
        assert Counter(str(q["win_turn"]) for q in d["rows"])==Counter(d["counts"])
        for j,q in enumerate(d["rows"]):
            gid=int(q["game_id"])
            assert gid==d["shard"]*d["games"]+j,(file,gid)
            assert q["seed"]==SEED_BASE+gid*1000003
            assert gid not in rows
            assert q["win_turn"] in (0,1,2,3)
            assert 1<=q["keep_n"]<=7
            assert len(q["rolls"])<=3
            assert all(1<=r<=4 for r in q["rolls"])
            if variant=="current": assert q["rolls"]==[],(gid,"baseline rolled Bucknard")
            rows[gid]=q
    assert set(rows)==set(range(n)),(variant,"missing",set(range(n))-set(rows))
    return rows,len(files)

def summary(rows):
    n=len(rows);ct=Counter(q["win_turn"] for q in rows.values())
    return {"n":n,"counts":{str(t):ct[t] for t in range(4)},
            "by_turn_pct":{f"T{t}":round(100*sum(ct[i] for i in range(1,t+1))/n,4) for t in (1,2,3)},
            "mean_keep":round(sum(q["keep_n"] for q in rows.values())/n,4)}

def paired(buck,base):
    n=len(base)
    out={}
    for t in (1,2,3):
        ds=[int(0<buck[i]["win_turn"]<=t)-int(0<base[i]["win_turn"]<=t) for i in range(n)]
        m=sum(ds)/n
        se=math.sqrt(sum((x-m)**2 for x in ds)/(n-1)/n)
        out[f"T{t}"]={"delta_pp":round(100*m,4),
                     "paired_normal95_pp":[round(100*(m-1.96*se),3),round(100*(m+1.96*se),3)],
                     "buck_only":sum(x>0 for x in ds),
                     "baseline_only":sum(x<0 for x in ds)}
    return out

def oracle(expr,variant,n):
    out={}
    for fn in glob.glob(expr,recursive=True):
        with gzip.open(fn,"rt") as f:d=json.load(f)
        if d["variant"]!=variant:continue
        for row in d["rows"]:
            if row["game_id"]<n:
                assert row["game_id"] not in out
                out[row["game_id"]]=row
    assert set(out)==set(range(n))
    return out

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--baseline",default="shards/current/*.json.gz")
    p.add_argument("--buck",default="shards/buck_worldmap/*.json.gz")
    p.add_argument("--oracle-base",default="oracle_base/**/*.json.gz")
    p.add_argument("--oracle-buck",default="oracle_buck/**/*.json.gz")
    p.add_argument("--n",type=int,default=256)
    p.add_argument("--beam",type=int,default=160)
    p.add_argument("--candidate-cap",type=int,default=8)
    p.add_argument("--out",default="dack_fair_random_deployment_v1_report.json")
    a=p.parse_args()
    baseline,nb=fetch(a.baseline,"current",a.n,a.beam,a.candidate_cap)
    buck,nk=fetch(a.buck,"buck_worldmap",a.n,a.beam,a.candidate_cap)
    o_base=oracle(a.oracle_base,"current",a.n)
    o_buck=oracle(a.oracle_buck,"buck_worldmap",a.n)
    rolls=Counter(r for q in buck.values() for r in q["rolls"])
    cnt=Counter(len(q["rolls"]) for q in buck.values())
    out={
      "status":"PASS","n_per_arm":a.n,
      "mode":"fair-realization: 1 committed state per turn, exogenous d4 after payment/KCI commitment",
      "beam":a.beam,"candidate_cap":a.candidate_cap,
      "current":summary(baseline),"buck_worldmap":summary(buck),
      "paired":paired(buck,baseline),
      "same_game_ids_original_hindsight":{"current":summary(o_base),
          "buck_worldmap":summary(o_buck),"paired":paired(o_buck,o_base)},
      "roll_audit":{"faces":{str(i):rolls[i] for i in (1,2,3,4)},
                    "games_by_number_of_rolls":dict(cnt),
                    "total_rolls":sum(rolls.values())},
      "shards":{"current":nb,"buck_worldmap":nk},
      "warnings":[
        "CANNOT claim calibrated real-life win rate: one-state end-turn beam heuristic is approximate and may be conservative",
        "Generic within-turn lookahead into unknown mid-turn tutor shuffle/draw sequences remains a risk",
        "Scry is legitimately allowed to inspect revealed top cards, but post-scry future draws may leak through beam selection",
        "Gemstone pregame selected by a hand/board heuristic before draw",
        "Mulligan eval uses deterministic conditional sample model neutral roll 2, not identical to actual chance-aware mulligan optimality",
        "Only a single Bucknard activation is allowed per turn by this experimental policy",
        "Opponent interaction, artifacts handed to opponents, post-Dack combo line not simulated"
      ]
    }
    Path(a.out).write_text(json.dumps(out,indent=2)+"\n")
    print("FAIR_RANDOM_PAIRED_REPORT_PASS",json.dumps(out),flush=True)

if __name__=="__main__":main()
