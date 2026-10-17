#!/usr/bin/env python3
"""Compare paired realistic-beam v2 (T2+T3 policy) vs v1 (next-draw policy)."""
from __future__ import annotations
import argparse,glob,gzip,json,math
from collections import Counter
from pathlib import Path
DECK={"current":"3a10a02e1aae070645129fa85ed94240f1ae9d5447e3711f7621f92064d9f129",
      "buck_worldmap":"f130ff4c9c0fbc888525070877fe820caba03e836e0be66ec60ea3410e950068"}
def read(expr,variant,schema,n):
    files=sorted(glob.glob(expr,recursive=True));assert files,(expr,"no files")
    rows={}
    for f in files:
        with gzip.open(f,"rt") as fh:d=json.load(fh)
        assert d["schema"]==schema
        assert d["variant"]==variant and d["deck_sha256"]==DECK[variant]
        for j,r in enumerate(d["rows"]):
            assert r["game_id"]==d["shard"]*d["games"]+j
            gid=r["game_id"]
            if gid<n:
                assert gid not in rows
                rows[gid]=r
    assert set(rows)==set(range(n)),(variant,schema,"incomplete",len(rows))
    return rows,len(files)
def stat(rows):
    n=len(rows);c=Counter(x["win_turn"] for x in rows.values())
    return {"n":n,"counts":dict(c),"by_turn_pct":{
       f"T{t}":round(100*sum(c[j] for j in range(1,t+1))/n,4)
       for t in (1,2,3)},
       "mean_rollout_calls":round(sum(r.get("planning_counts",{}).get("rollout_calls",0)
                                    for r in rows.values())/n,2)}
def paired(left,right):
    n=len(left);assert n==len(right) and set(left)==set(right)
    dct={}
    for t in (1,2,3):
        vals=[int(0<left[j]["win_turn"]<=t)-int(0<right[j]["win_turn"]<=t)
              for j in range(n)]
        mn=sum(vals)/n
        se=math.sqrt(sum((v-mn)**2 for v in vals)/((n-1)*n))
        dct[f"T{t}"]={"delta_pp":round(100*mn,4),
            "paired_95pct_pp":[round(100*(mn-1.96*se),3),round(100*(mn+1.96*se),3)],
            "new_only":sum(v==1 for v in vals),"old_only":sum(v==-1 for v in vals)}
    return dct
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--n",type=int,default=32)
    p.add_argument("--v2",default="v2shards")
    p.add_argument("--v1",default="v1shards")
    p.add_argument("--out",default="realistic_info_beam_v2_n32.json")
    a=p.parse_args()
    result={"status":"PASS","n_per_deck":a.n,
       "method":"Realistic v2 is a two-step chance-aware horizon (T2 + T3, T2 weight 1, T3 0.5); v1 is one-step and heuristic fallback.",
       "settings_v2":{"beam":120,"pass_cap":9,"buck_cap":3,
            "draw_samples":3,"rollout_beam":42,"rollout_depth":18,
            "t3_samples":2,"t2_continuations":2},
       "settings_v1":{"beam":120,"pass_cap":7,"buck_cap":3,
            "draw_samples":3,"rollout_beam":42,"rollout_depth":14},
       "arms":{},"effects":{}}
    for variant in ("current","buck_worldmap"):
        new,ns=read(f"{a.v2}/**/{variant}_shard_*.json.gz",variant,
                    "realistic_info_beam_v2",a.n)
        old,os=read(f"{a.v1}/**/{variant}_shard_*.json.gz",variant,
                    "realistic_info_beam_v1",a.n)
        result["arms"][variant]={"v2":stat(new),"v1":stat(old),
            "v2_minus_v1":paired(new,old),"new_shards":ns,"old_shards":os}
        result.setdefault("_data",{})[variant]={"v1":old,"v2":new}
    result["effects"]["buck_minus_worldmap_v2"]=paired(
        result["_data"]["buck_worldmap"]["v2"],result["_data"]["current"]["v2"])
    result["effects"]["buck_minus_worldmap_v1"]=paired(
        result["_data"]["buck_worldmap"]["v1"],result["_data"]["current"]["v1"])
    del result["_data"]
    result["limitations"]=[
        "N32 exploratory pilot; uncertainty of small effects remains high",
        "V2 changes planning horizon and rollout depth/pass-cap, not a pure horizon ablation",
        "Within-turn future-card peek after tutor/draw still possible",
        "Known-top-card information not explicitly tracked",
        "Mulligan continuation policy remains inherited",
        "Future Bucknard activations in hypothetical rollouts are disabled",
        "Goldfish Dack deployment proxy and no opponent action simulation"]
    Path(a.out).write_text(json.dumps(result,indent=2)+"\n")
    print("REALISTIC_BEAM_V2_COMPARE_PASS",json.dumps(result),flush=True)
if __name__=="__main__":main()
