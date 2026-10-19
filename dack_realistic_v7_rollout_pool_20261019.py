#!/usr/bin/env python3
"""Pool paired v7 fidelity vs v6 on exactly 32 matching game IDs per deck."""
import argparse,glob,gzip,json,math
from collections import Counter
from pathlib import Path
SHA={"current":"3a10a02e1aae070645129fa85ed94240f1ae9d5447e3711f7621f92064d9f129",
"buck_worldmap":"f130ff4c9c0fbc888525070877fe820caba03e836e0be66ec60ea3410e950068"}
def load(pattern,variant,expected,schema):
    fns=glob.glob(pattern,recursive=True);assert fns,(pattern,"missing files")
    rows={}
    for fn in fns:
        with gzip.open(fn,"rt") as f:q=json.load(f)
        assert q["schema"]==schema and q["variant"]==variant
        assert q["deck_sha256"]==SHA[variant] and len(q["rows"])==q["games"]
        for n,row in enumerate(q["rows"]):
            gid=row["game_id"]
            assert gid==q["shard"]*q["games"]+n and gid not in rows
            rows[gid]=row
    assert set(rows)==set(range(expected)),(variant,schema,len(rows))
    return rows,len(fns)
def summarize(z):
    n=len(z);c=Counter(v["win_turn"] for v in z.values())
    return {"n":n,"by_turn_pct":{f"T{k}":round(100*sum(c[j] for j in range(1,k+1))/n,4) for k in (1,2,3)},
            "mean_keep":round(sum(v["keep_n"] for v in z.values())/n,3),
            "mean_forecast_rollouts":round(sum(v.get("forecast_rollout_calls",v.get("rollout_calls",0)) for v in z.values())/n,2)}
def contrast(a,b):
    n=len(a)
    d={}
    for turn in (1,2,3):
        vals=[int(0<a[i]["win_turn"]<=turn)-int(0<b[i]["win_turn"]<=turn) for i in range(n)]
        avg=sum(vals)/n
        se=math.sqrt(sum((x-avg)**2 for x in vals)/(n*(n-1)))
        d[f"T{turn}"]={"delta_pp":round(100*avg,4),
                      "paired_normal_95pct_pp":[round(100*(avg-1.96*se),3),round(100*(avg+1.96*se),3)],
                      "v7_only":[i for i,x in enumerate(vals) if x>0],
                      "v6_only":[i for i,x in enumerate(vals) if x<0]}
    return d
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--v6",default="v6")
    p.add_argument("--v7",default="v7")
    p.add_argument("--n",type=int,default=32)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    out={"status":"PASS","n_per_deck":a.n,
         "design":"Forecast-only beam 42/depth18 (v6) versus beam96/depth24 (v7), identical actual beam120/stratified next-card distribution/knowledge flags",
         "arms":{},"deck_swap":{}}
    data={}
    for variant in SHA:
        old,no=load(f"{a.v6}/**/{variant}_shard_*.json.gz",variant,a.n,
                    "dack_realistic_stratified_reward_v6")
        new,nn=load(f"{a.v7}/**/{variant}_shard_*.json.gz",variant,a.n,
                    "dack_realistic_forecast_fidelity_v7")
        assert all(new[i]["keep_n"]==old[i]["keep_n"] for i in range(a.n))
        data[variant]={"old":old,"new":new}
        out["arms"][variant]={"v6":summarize(old),"v7":summarize(new),
                              "v7_minus_v6":contrast(new,old),"shard_counts":[no,nn]}
    out["deck_swap"]["v7_buck_minus_current"]=contrast(data["buck_worldmap"]["new"],data["current"]["new"])
    out["deck_swap"]["v6_buck_minus_current"]=contrast(data["buck_worldmap"]["old"],data["current"]["old"])
    out["limitations"]=[
      "N32 preliminary, uncertainty for small differences remains high",
      "Forecast widths/depth changed together, not a pure single-variable effect",
      "Within-turn action generation can still inspect unknown subsequent cards",
      "Known-top detection still only covers selected tutors",
      "Goldfish Dack deployment, not interactive 4-player win rate"
    ]
    Path(a.out).write_text(json.dumps(out,indent=2)+"\n")
    print("DACK_V7_FORECAST_FIDELITY_POOLED_PASS",json.dumps(out),flush=True)
if __name__=="__main__":main()
