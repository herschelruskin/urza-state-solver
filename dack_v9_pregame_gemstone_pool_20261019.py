#!/usr/bin/env python3
"""Compare v9 pregame expected-value commitments vs frozen Realistic v7, n32."""
from __future__ import annotations
import argparse,glob,gzip,json,math
from collections import Counter
from pathlib import Path
SHA={"current":"3a10a02e1aae070645129fa85ed94240f1ae9d5447e3711f7621f92064d9f129",
"buck_worldmap":"f130ff4c9c0fbc888525070877fe820caba03e836e0be66ec60ea3410e950068"}
def read(path,variant,schema,n):
    files=glob.glob(path,recursive=True);assert files,path
    rows={}
    for f in files:
        with gzip.open(f,"rt") as handle:q=json.load(handle)
        assert q["schema"]==schema and q["variant"]==variant
        assert q["deck_sha256"]==SHA[variant]
        for i,row in enumerate(q["rows"]):
            gid=row["game_id"]
            assert gid==q["shard"]*q["games"]+i and gid not in rows
            rows[gid]=row
    assert set(rows)==set(range(n)),(variant,schema,len(rows))
    return rows,len(files)
def metrics(rows):
    n=len(rows)
    return {f"T{t}":round(100*sum(0<q["win_turn"]<=t for q in rows.values())/n,4) for t in (1,2,3)}
def paired(a,b):
    n=len(a);out={}
    for t in (1,2,3):
        diff=[int(0<a[i]["win_turn"]<=t)-int(0<b[i]["win_turn"]<=t) for i in range(n)]
        mu=sum(diff)/n
        se=math.sqrt(sum((d-mu)**2 for d in diff)/(n*(n-1)))
        out[f"T{t}"]={"delta_pp":round(100*mu,4),
          "normal_95pct_pp":[round(100*(mu-1.96*se),3),round(100*(mu+1.96*se),3)],
          "v9_only":[i for i,x in enumerate(diff) if x==1],
          "v7_only":[i for i,x in enumerate(diff) if x==-1]}
    return out
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--v7",default="v7")
    p.add_argument("--v9",default="v9")
    p.add_argument("--n",type=int,default=32)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    result={"status":"PASS","n_per_deck":a.n,
       "method":"Expected T1-T3 deployment chance over twelve pregame unseen draw strata; same legal original pregame options and frozen v7 in-turn beam.",
       "arms":{},"deck_swap":{}}
    by={}
    for variant in SHA:
        old,no=read(f"{a.v7}/**/{variant}_shard_*.json.gz",variant,
                    "dack_realistic_forecast_fidelity_v7",a.n)
        new,nn=read(f"{a.v9}/**/{variant}_shard_*.json.gz",variant,
                    "dack_v9_pregame_ev",a.n)
        assert all(old[i]["keep_n"]==new[i]["keep_n"] for i in range(a.n))
        changed=[i for i in range(a.n) if new[i]["pregame_audit"]["pregame_changed_decisions"]]
        choices=[i for i in range(a.n) if new[i]["pregame_audit"]["pregame_alternative_games"]]
        by[variant]={"v7":old,"v9":new}
        result["arms"][variant]={"v7":metrics(old),"v9":metrics(new),
           "v9_minus_v7":paired(new,old),
           "pregame_alternative_game_ids":choices,"pregame_changed_game_ids":changed,
           "pregame_logs":{str(i):new[i]["pregame_audit"]["decision_logs"] for i in choices},
           "shard_count":[no,nn]}
    result["deck_swap"]["v9"]=paired(by["buck_worldmap"]["v9"],by["current"]["v9"])
    result["deck_swap"]["v7"]=paired(by["buck_worldmap"]["v7"],by["current"]["v7"])
    result["limitations"]=[
      "N32 preliminary; Gemstone appears infrequently",
      "Known-top handling partial, original legal exile options inherited unchanged",
      "Within-turn unknown future cards may still influence original action engine",
      "Finite forecast beams and no opponent interaction",
      "Goldfish Dack deployment is a proxy, not full match win probability"]
    Path(a.out).write_text(json.dumps(result,indent=2)+"\n")
    print("DACK_V9_GEMSTONE_PREGAME_PAIRED_REPORT_PASS",json.dumps({
      k:{"v9_minus_v7":v["v9_minus_v7"],"options":v["pregame_alternative_game_ids"],
         "changed":v["pregame_changed_game_ids"]} for k,v in result["arms"].items()}),flush=True)
if __name__=="__main__":main()
