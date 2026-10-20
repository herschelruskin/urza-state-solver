#!/usr/bin/env python3
"""Compare same-seed Realistic v10 blind London mulligans with v7 historical."""
import argparse,glob,gzip,json,math
from pathlib import Path
SHA={"current":"3a10a02e1aae070645129fa85ed94240f1ae9d5447e3711f7621f92064d9f129",
"buck_worldmap":"f130ff4c9c0fbc888525070877fe820caba03e836e0be66ec60ea3410e950068"}
def load(pattern,variant,schema,n):
    rows={};fns=glob.glob(pattern,recursive=True);assert fns
    for fn in fns:
        with gzip.open(fn,"rt") as f:q=json.load(f)
        assert q["schema"]==schema and q["variant"]==variant
        assert q["deck_sha256"]==SHA[variant]
        assert len(q["rows"])==q["games"]
        for j,x in enumerate(q["rows"]):
            gid=x["game_id"]
            assert gid==q["shard"]*q["games"]+j and gid not in rows
            rows[gid]=x
    assert set(rows)==set(range(n)),(variant,schema,n,len(rows))
    return rows
def rates(data):
    n=len(data)
    return {f"T{t}":round(100*sum(0<x["win_turn"]<=t for x in data.values())/n,4) for t in (1,2,3)}
def paired(a,b):
    n=len(a)
    out={}
    for t in (1,2,3):
        dif=[int(0<a[i]["win_turn"]<=t)-int(0<b[i]["win_turn"]<=t) for i in range(n)]
        avg=sum(dif)/n
        se=math.sqrt(sum((z-avg)**2 for z in dif)/(n*(n-1)))
        out[f"T{t}"]={"delta_pp":round(avg*100,4),
          "paired_normal_95pct_pp":[round((avg-1.96*se)*100,3),round((avg+1.96*se)*100,3)],
          "v10_only":[i for i,v in enumerate(dif) if v>0],
          "v7_only":[i for i,v in enumerate(dif) if v<0]}
    return out
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--v7",default="v7")
    p.add_argument("--v10",default="v10")
    p.add_argument("--n",type=int,default=32)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    out={"status":"PASS","n_per_deck":a.n,
         "design":"Same actual shuffle and v7 within-turn policy; v10 only canonicalizes the Monte Carlo unknown library multiset for London mulligan keep/bottom forecasts",
         "arms":{},"deck_swap":{}}
    data={}
    for variant in SHA:
        old=load(f"{a.v7}/**/{variant}_shard_*.json.gz",variant,
                 "dack_realistic_forecast_fidelity_v7",a.n)
        new=load(f"{a.v10}/**/{variant}_shard_*.json.gz",variant,
                 "dack_v10_blind_mulligans",a.n)
        data[variant]={"v7":old,"v10":new}
        changed_keep=[i for i in range(a.n) if old[i]["keep_n"]!=new[i]["keep_n"]]
        out["arms"][variant]={
          "v7":rates(old),"v10":rates(new),"v10_minus_v7":paired(new,old),
          "changed_keep_depth_games":changed_keep,
          "keep_depth_differences":[{"gid":i,"old_keep":old[i]["keep_n"],
                 "new_keep":new[i]["keep_n"]} for i in changed_keep],
          "identical_seat_count":sum(old[i]["seat"]==new[i]["seat"] for i in range(a.n))}
    out["deck_swap"]["v10"]=paired(data["buck_worldmap"]["v10"],data["current"]["v10"])
    out["deck_swap"]["v7"]=paired(data["buck_worldmap"]["v7"],data["current"]["v7"])
    out["limitations"]=[
       "Corrects one actual-order leak but mulligan evaluator still models continuation with optimistic original beam",
       "Frozen continuation thresholds are still calibrated under older sampling assumptions",
       "N32 exploratory, not precise enough to resolve small winrate deltas",
       "In-turn hidden draw foresight persists inside inherited action generation"]
    Path(a.out).write_text(json.dumps(out,indent=2)+"\n")
    print("DACK_V10_BLIND_MULLIGAN_N32_POOL_PASS",json.dumps({
      k:{"rates":v["v10"],"vs_v7":v["v10_minus_v7"],
         "changed_depths":v["changed_keep_depth_games"]} for k,v in out["arms"].items()}),flush=True)
if __name__=="__main__":main()
