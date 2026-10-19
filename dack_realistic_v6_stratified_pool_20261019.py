#!/usr/bin/env python3
"""Validate & compare independent matched Dack v4, corrected v5 and v6."""
from __future__ import annotations
import argparse,glob,gzip,json,math
from collections import Counter
from pathlib import Path
SHA={"current":"3a10a02e1aae070645129fa85ed94240f1ae9d5447e3711f7621f92064d9f129",
"buck_worldmap":"f130ff4c9c0fbc888525070877fe820caba03e836e0be66ec60ea3410e950068"}
SCHEMA={"v4":"dack_known_top_population_v4",
        "v5":"dack_realistic_population_v5",
        "v6":"dack_realistic_stratified_reward_v6"}
def fetch(pattern,version,deck,n=32):
    files=sorted(glob.glob(pattern,recursive=True))
    assert files,(version,deck,pattern)
    rows={}
    for path in files:
        with gzip.open(path,"rt") as f:q=json.load(f)
        if q["variant"]!=deck:continue
        assert q["schema"]==SCHEMA[version] and q["deck_sha256"]==SHA[deck]
        assert q["seed_base"]==7604096001
        if version=="v6":
            assert q["draws"]==12 and q["next_draws"]==6
        for i,r in enumerate(q["rows"]):
            gid=r["game_id"]
            assert gid==q["shard"]*q["games"]+i
            assert gid not in rows
            rows[gid]=r
    assert set(rows)==set(range(n)),(version,deck,len(rows))
    return rows
def stats(rows):
    ct=Counter(z["win_turn"] for z in rows.values());n=len(rows)
    return {"T1":round(100*ct[1]/n,3),"T2":round(100*(ct[1]+ct[2])/n,3),
       "T3":round(100*(ct[1]+ct[2]+ct[3])/n,3),
       "mean_keep":round(sum(x["keep_n"] for x in rows.values())/n,3),
       "rollout_calls_mean":round(sum(x["rollout_calls"] for x in rows.values())/n,2)}
def pairs(a,b):
    n=len(a);x={}
    for t in (1,2,3):
        deltas=[int(0<a[k]["win_turn"]<=t)-int(0<b[k]["win_turn"]<=t)
                for k in range(n)]
        avg=sum(deltas)/n
        se=math.sqrt(sum((d-avg)**2 for d in deltas)/(n*(n-1)))
        x[f"T{t}"]={"delta_pp":round(100*avg,4),
                    "normal_paired_95pct_pp":[round(100*(avg-1.96*se),3),
                                              round(100*(avg+1.96*se),3)],
                    "only_first":[k for k,v in enumerate(deltas) if v>0],
                    "only_second":[k for k,v in enumerate(deltas) if v<0]}
    return x
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--v4",default="v4")
    p.add_argument("--v5",default="v5")
    p.add_argument("--v6",default="v6")
    p.add_argument("--out",default="dack_v6_stratified_reward_n32.json")
    a=p.parse_args()
    allrows={}
    report={"status":"PASS","n_per_arm":32,
      "design":"Independent matched-game comparison. v6 replaces IID draw samples with frequency-weighted stratified unseen draws; v4 known-top 3-sample and v5 known-top corrected 12-sample preserved.",
      "arms":{}}
    for deck in SHA:
        arm={}
        for v in SCHEMA:
            data=fetch(f"{getattr(a,v)}/**/{deck}_shard_*.json.gz",v,deck)
            arm[v]=data
        assert all(arm["v4"][i]["keep_n"]==arm["v6"][i]["keep_n"]
                   for i in range(32)),("mulligan mismatch",deck)
        report["arms"][deck]={
          "v4":stats(arm["v4"]),"v5":stats(arm["v5"]),"v6":stats(arm["v6"]),
          "v6_minus_v4":pairs(arm["v6"],arm["v4"]),
          "v6_minus_v5":pairs(arm["v6"],arm["v5"])}
        allrows[deck]=arm
    report["deck_swap_effects"]={v:pairs(allrows["buck_worldmap"][v],
                                           allrows["current"][v])
                                 for v in SCHEMA}
    report["limitations"]=[
      "Small N32, differences may be noise",
      "Within-turn inherited oracle still can access unknown future draws",
      "Known-top v4 tracking only Enlightened / Loyal Tutor and may miss other info",
      "Finite beam 120 for gameplay and 42 for counterfactual future rollout",
      "Stratified weights are ex ante correct, policy value still approximate",
      "Goldfish deployment proxy, not full interactive cEDH game outcome"]
    Path(a.out).write_text(json.dumps(report,indent=2)+"\n")
    print("DACK_V6_STRATIFIED_N32_REPORT_PASS",json.dumps({
      k:{v:r[v] for v in ("v4","v5","v6")} for k,r in report["arms"].items()
    }),flush=True)
if __name__=="__main__":main()
