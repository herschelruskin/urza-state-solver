#!/usr/bin/env python3
"""Matched game-level failure inventory: Full Beam vs Realistic Beam v1/v2.

Reads COMPLETED artifacts without rerunning expensive gameplay. Describes,
but does not presume to prove causes of, deployment differences.
"""
from __future__ import annotations
import argparse,glob,gzip,json,math
from collections import Counter
from pathlib import Path
BASE="3a10a02e1aae070645129fa85ed94240f1ae9d5447e3711f7621f92064d9f129"
BUCK="f130ff4c9c0fbc888525070877fe820caba03e836e0be66ec60ea3410e950068"
SHA={"current":BASE,"buck_worldmap":BUCK}
def read(pattern,variant,n,schema=None):
    files=sorted(glob.glob(pattern,recursive=True));assert files,(pattern,"no files")
    rows={}
    for path in files:
        with gzip.open(path,"rt") as f:x=json.load(f)
        if x["variant"]!=variant:continue
        assert x["deck_sha256"]==SHA[variant],(path,"deck hash")
        if schema:assert x["schema"]==schema,(path,x.get("schema"))
        assert len(x["rows"])==x["games"]
        for j,r in enumerate(x["rows"]):
            gid=int(r["game_id"])
            assert gid==int(x["shard"])*int(x["games"])+j
            if gid>=n:continue
            assert gid not in rows,(variant,pattern,gid,"dup")
            assert 0<=r["win_turn"]<=3
            rows[gid]=r
    assert set(rows)==set(range(n)),(pattern,len(rows),n)
    return rows,files
def by_turn(rows,t):
    return sum(0<r["win_turn"]<=t for r in rows.values())
def classify(full,real,t):
    result={"both_success":[],"full_only":[],"realistic_only":[],"both_miss":[]}
    for i in range(len(real)):
        a=0<full[i]["win_turn"]<=t
        b=0<real[i]["win_turn"]<=t
        result["both_success" if a and b else
               "full_only" if a else "realistic_only" if b else "both_miss"].append(i)
    return result
def audit_arms(full,v1,v2,t,cap=32):
    cl=classify(full,v2,t)
    cases=[]
    for gid in cl["full_only"]+cl["realistic_only"]:
        x=full[gid];y=v2[gid];z=v1[gid]
        turns=y["turn_audit"]
        cases.append({
          "game_id":gid,"kind":"full_only" if gid in cl["full_only"] else "realistic_only",
          "full_turn":x["win_turn"],"v1_turn":z["win_turn"],"v2_turn":y["win_turn"],
          "full_keep":x["keep_n"],"v2_keep":y["keep_n"],
          "mulligan_same_keep":x["keep_n"]==y["keep_n"],
          "v2_rolls":y.get("rolls",[]),
          "v2_rollout_calls":y["planning_counts"]["rollout_calls"],
          "v2_turn_choices":[{
            "turn":s["turn"],"phase":s["phase"],
            "pass_candidates":s.get("pass_candidates"),
            "buck_plans":s.get("buck_plans"),
            "die":s.get("die")} for s in turns],
        })
    return {"turn":t,"full_pct":round(100*by_turn(full,t)/len(full),3),
            "v1_pct":round(100*by_turn(v1,t)/len(v1),3),
            "v2_pct":round(100*by_turn(v2,t)/len(v2),3),
            "counts":{k:len(v) for k,v in cl.items()},
            "ids":cl,
            "fail_or_recovered_cases":cases[:cap]}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--n",type=int,default=32)
    p.add_argument("--old-base",default="old_base/**/*.json.gz")
    p.add_argument("--old-buck",default="old_buck/**/*.json.gz")
    p.add_argument("--v1",default="v1/**/*.json.gz")
    p.add_argument("--v2",default="v2/**/*.json.gz")
    p.add_argument("--out",default="dack_realistic_beam_game_failure_audit_n32.json")
    a=p.parse_args()
    result={"status":"PASS","n_per_deck":a.n,
      "method":"Paired complete game outcomes, same IDs and deck hashes, archived Full Beam vs Realistic Beam v1 and v2. No actual gameplay replays.",
      "arms":{}}
    for variant in ("current","buck_worldmap"):
        full,ff=read(a.old_base if variant=="current" else a.old_buck,variant,a.n)
        v1,f1=read(a.v1,variant,a.n,"realistic_info_beam_v1")
        v2,f2=read(a.v2,variant,a.n,"realistic_info_beam_v2")
        by={}
        for t in (2,3):
            by[f"T{t}"]=audit_arms(full,v1,v2,t)
        result["arms"][variant]={"matched_games":a.n,"files":{
             "full":len(ff),"v1":len(f1),"v2":len(f2)},
             "same_keep_count_full_v2":sum(full[i]["keep_n"]==v2[i]["keep_n"] for i in range(a.n)),
             "turn_comparison":by}
    result["limitations"]=[
       "An outcome difference alone does not prove its cause is turn-boundary clairvoyance",
       "This report does not replay per-game action histories, so cannot attribute individual losses to tutor/shuffle/selection",
       "V2 rollouts have a shorter beam and deeper but still limited planning horizon compared with Full Beam",
       "Some v2 mulligan choices can differ because deck includes Bucknard, causing confounding",
       "Small N32 sample; avoid treating percentage-point differences as calibrated win rates",
    ]
    Path(a.out).write_text(json.dumps(result,indent=2)+"\n")
    print("DACK_REALISTIC_FAILURE_GAME_INVENTORY_PASS",json.dumps({
        "summary":{name:{t:r["counts"] for t,r in q["turn_comparison"].items()}
                   for name,q in result["arms"].items()}
    }),flush=True)
if __name__=="__main__":main()
