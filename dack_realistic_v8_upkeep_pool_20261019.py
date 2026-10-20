#!/usr/bin/env python3
"""Matched 32-game v8 upkeep policy vs untouched Realistic v6."""
from __future__ import annotations
import argparse,glob,gzip,json,math
from collections import Counter
from pathlib import Path
SHA={"current":"3a10a02e1aae070645129fa85ed94240f1ae9d5447e3711f7621f92064d9f129",
"buck_worldmap":"f130ff4c9c0fbc888525070877fe820caba03e836e0be66ec60ea3410e950068"}
def load(pat,variant,schema,n):
    rows={};files=glob.glob(pat,recursive=True)
    assert files,(pat,"no shards")
    for fn in files:
        with gzip.open(fn,"rt") as f:q=json.load(f)
        assert q["schema"]==schema and q["variant"]==variant
        assert q["deck_sha256"]==SHA[variant]
        for i,r in enumerate(q["rows"]):
            assert r["game_id"]==q["shard"]*q["games"]+i
            gid=r["game_id"]
            assert gid not in rows
            rows[gid]=r
    assert set(rows)==set(range(n)),(pat,n,len(rows))
    return rows,len(files)
def summary(rows):
    n=len(rows);c=Counter(r["win_turn"] for r in rows.values())
    return {"n":n,"by_turn_pct":{f"T{t}":round(100*sum(c[i] for i in range(1,t+1))/n,4) for t in (1,2,3)},
            "mean_keep":round(sum(r["keep_n"] for r in rows.values())/n,3)}
def diff(a,b):
    n=len(a);assert set(a)==set(b)
    out={}
    for turn in (1,2,3):
        dd=[int(0<a[i]["win_turn"]<=turn)-int(0<b[i]["win_turn"]<=turn) for i in range(n)]
        mean=sum(dd)/n
        se=math.sqrt(sum((x-mean)**2 for x in dd)/(n*(n-1)))
        out[f"T{turn}"]={"delta_pp":round(100*mean,4),
          "paired_95pct_pp":[round(100*(mean-1.96*se),3),round(100*(mean+1.96*se),3)],
          "v8_only":[i for i,x in enumerate(dd) if x==1],
          "v6_only":[i for i,x in enumerate(dd) if x==-1]}
    return out
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--v6",default="v6")
    p.add_argument("--v8",default="v8")
    p.add_argument("--n",type=int,default=32)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    o={"status":"PASS","design":"Change only real-turn Mana Vault upkeep commitment from score-based to pre-draw stratified chance EV; all card rules, mulligans and turn-end reward remain v6",
       "n_per_arm":a.n,"decks":{},"deck_swap":{}}
    raw={}
    for v in SHA:
        before,n6=load(f"{a.v6}/**/{v}_shard_*.json.gz",v,"dack_realistic_stratified_reward_v6",a.n)
        after,n8=load(f"{a.v8}/**/{v}_shard_*.json.gz",v,"dack_upkeep_legal_ev_v8",a.n)
        assert all(before[i]["keep_n"]==after[i]["keep_n"] for i in range(a.n))
        raw[v]=(before,after)
        decisions=[(i,after[i]["upkeep_audit"]) for i in range(a.n)]
        o["decks"][v]={"v6":summary(before),"v8":summary(after),
            "v8_minus_v6":diff(after,before),
            "upkeep_options_multiple_total":sum(q["multiple_upkeep_options"] for i,q in decisions),
            "upkeep_decisions_changed_total":sum(q["different_upkeep_decision"] for i,q in decisions),
            "upkeep_decisions_changed_game_ids":[i for i,q in decisions if q["different_upkeep_decision"]],
            "upkeep_rollout_count_total":sum(q["upkeep_rollouts"] for i,q in decisions),
            "upkeep_detailed_logs":{str(i):q["upkeep_choice_log"] for i,q in decisions if q["upkeep_choice_log"]},
            "shards":[n6,n8]}
    o["deck_swap"]={"v8":diff(raw["buck_worldmap"][1],raw["current"][1]),
                    "v6":diff(raw["buck_worldmap"][0],raw["current"][0])}
    o["limitations"]=[
      "N32 exploratory; game differences are not statistically calibrated",
      "Upkeep comparison uses 6 stratified same-turn draw scenarios",
      "Within-turn hidden draw/action lookahead is inherited and still unresolved",
      "Known-top tutor metadata covers only selected tutors",
      "Goldfish Dack casting is not full interactive cEDH win rate"]
    Path(a.out).write_text(json.dumps(o,indent=2)+"\n")
    print("DACK_V8_UPKEEP_POLICY_POOLED_PASS",json.dumps(o),flush=True)
if __name__=="__main__":main()
