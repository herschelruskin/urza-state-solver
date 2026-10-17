#!/usr/bin/env python3
"""Pool matched Realistic Beam N64 pilot and compare with frozen Full Beam."""
from __future__ import annotations
import argparse,glob,gzip,json,math
from collections import Counter
from pathlib import Path

NAMES=("current","buck_worldmap")
SHA={"current":"3a10a02e1aae070645129fa85ed94240f1ae9d5447e3711f7621f92064d9f129",
     "buck_worldmap":"f130ff4c9c0fbc888525070877fe820caba03e836e0be66ec60ea3410e950068"}
SEED_BASE=7604096001

def load(pattern,name,n,beam,cap,draws,rbeam,rdepth):
    files=sorted(glob.glob(pattern,recursive=True));assert files,(name,pattern)
    rows={}
    for file in files:
        with gzip.open(file,"rt") as f:q=json.load(f)
        assert q["schema"]=="realistic_info_beam_v1"
        assert q["variant"]==name and q["deck_sha256"]==SHA[name]
        assert q["beam"]==beam and q["pass_cap"]==cap
        assert q["draw_samples"]==draws
        assert q["rollout_beam"]==rbeam and q["rollout_depth"]==rdepth
        assert q["seed_base"]==SEED_BASE and len(q["rows"])==q["games"]
        assert Counter(str(r["win_turn"]) for r in q["rows"])==Counter(q["counts"])
        for j,r in enumerate(q["rows"]):
            gid=int(r["game_id"])
            assert gid==q["shard"]*q["games"]+j
            assert r["seed"]==SEED_BASE+gid*1000003
            assert gid not in rows and 0<=r["win_turn"]<=3
            assert 1<=r["keep_n"]<=7
            assert all(1<=die<=4 for die in r["rolls"])
            if name=="current":assert not r["rolls"]
            rows[gid]=r
    assert set(rows)==set(range(n)),(name,"missing",sorted(set(range(n))-set(rows))[:10])
    return rows,len(files)

def stats(rows):
    n=len(rows);ct=Counter(q["win_turn"] for q in rows.values())
    return {"n":n,"counts":{str(k):ct[k] for k in range(4)},
            "cumulative_pct":{f"by_T{t}":round(100*sum(ct[k] for k in range(1,t+1))/n,4)
                              for t in (1,2,3)},
            "mean_keep":round(sum(q["keep_n"] for q in rows.values())/n,4),
            "mean_rollout_calls":round(sum(q["planning_counts"]["rollout_calls"] for q in rows.values())/n,2) if all("planning_counts" in q for q in rows.values()) else None}

def paired(buck,base):
    n=len(base);out={}
    for t in (1,2,3):
        ds=[int(0<buck[i]["win_turn"]<=t)-int(0<base[i]["win_turn"]<=t) for i in range(n)]
        mean=sum(ds)/n;se=math.sqrt(sum((x-mean)**2 for x in ds)/((n-1)*n))
        gain=sum(x==1 for x in ds);loss=sum(x==-1 for x in ds)
        discordant=gain+loss
        exact=(min(1.,2*sum(math.comb(discordant,j)
            for j in range(min(gain,loss)+1))/(2**discordant)) if discordant else 1.)
        out[f"by_T{t}"]={"delta_pp":round(mean*100,4),
            "paired_normal_95pct_pp":[round(100*(mean-1.96*se),3),
                                       round(100*(mean+1.96*se),3)],
            "buck_only":gain,"baseline_only":loss,
            "mcnemar_exact_p":round(exact,6)}
    return out

def old(expr,variant,n):
    paths=glob.glob(expr,recursive=True);assert paths
    results={}
    for path in paths:
        with gzip.open(path,"rt") as f:q=json.load(f)
        if q["variant"]!=variant:continue
        for r in q["rows"]:
            gid=int(r["game_id"])
            if gid<n:
                assert gid not in results
                results[gid]=r
    assert set(results)==set(range(n)),(variant,n,len(results))
    return results

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--shards",default="shards")
    p.add_argument("--oracle-base",default="old_current/**/*.json.gz")
    p.add_argument("--oracle-buck",default="old_buck/**/*.json.gz")
    p.add_argument("--n",type=int,default=64)
    p.add_argument("--beam",type=int,default=120)
    p.add_argument("--pass-cap",type=int,default=7)
    p.add_argument("--draw-samples",type=int,default=3)
    p.add_argument("--rollout-beam",type=int,default=42)
    p.add_argument("--rollout-depth",type=int,default=14)
    p.add_argument("--out",default="dack_realistic_beam_n64_pilot.json")
    a=p.parse_args()
    curves={}
    for name in NAMES:
        data,files=load(f"{a.shards}/**/{name}_*.json.gz",
             name,a.n,a.beam,a.pass_cap,a.draw_samples,a.rollout_beam,a.rollout_depth)
        curves[name]={"rows":data,"files":files,"summary":stats(data)}
    prior_current=old(a.oracle_base,"current",a.n)
    prior_buck=old(a.oracle_buck,"buck_worldmap",a.n)
    rolls=Counter(r for q in curves["buck_worldmap"]["rows"].values()
                  for r in q["rolls"])
    out={
        "status":"PASS","policy":"realistic_info_beam_v1",
        "description":"Bounded future-draw Monte Carlo rollouts choose among intra-turn beam pass states without revealed next draw; precommitted Bucknard fair d4",
        "n_per_arm":a.n,"beam":a.beam,"pass_cap":a.pass_cap,
        "draw_samples":a.draw_samples,"rollout_beam":a.rollout_beam,
        "rollout_depth":a.rollout_depth,
        "current":curves["current"]["summary"],
        "buck_worldmap":curves["buck_worldmap"]["summary"],
        "paired":paired(curves["buck_worldmap"]["rows"],curves["current"]["rows"]),
        "old_full_beam_same_ids":{
           "current":stats(prior_current),"buck_worldmap":stats(prior_buck),
           "paired":paired(prior_buck,prior_current)},
        "exogenous_bucknard_d4_histogram":{str(k):rolls[k] for k in (1,2,3,4)},
        "shards":{name:curves[name]["files"] for name in NAMES},
        "limitations":[
          "Full Beam reference is an optimistic upper-bound proxy, not real-game rate",
          "Realistic Beam uses small Monte Carlo samples and small rollout width/depth",
          "Only one turn-ending state is ultimately committed before future card draw",
          "Mulligans remain inherited neutral-roll sampled continuation heuristic",
          "Within-turn draw/search/shuffle actions can still look ahead in the inherited action generators",
          "Forecast rollouts suppress future Bucknard randomness and may undervalue it",
          "Counterfactual next-draw sampling treats library as wholly unknown, including previously tutored known-top cards",
          "Search and random-event handling not yet fully information-set correct",
          "No live opponent interaction; no post-Dack combo validation"
        ]}
    Path(a.out).write_text(json.dumps(out,indent=2)+"\n")
    print("DACK_REALISTIC_BEAM_POOL_PASS",json.dumps(out),flush=True)

if __name__=="__main__":
    main()
