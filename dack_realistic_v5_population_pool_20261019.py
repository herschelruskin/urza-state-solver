#!/usr/bin/env python3
"""Paired Dack v5 n32 reward estimate evaluation vs known-top v4."""
import argparse,glob,gzip,json,math
from collections import Counter
from pathlib import Path
SHA={"current":"3a10a02e1aae070645129fa85ed94240f1ae9d5447e3711f7621f92064d9f129",
"buck_worldmap":"f130ff4c9c0fbc888525070877fe820caba03e836e0be66ec60ea3410e950068"}

def load(path,variant,n,schema):
    rows={};files=sorted(glob.glob(path,recursive=True))
    assert files
    for f in files:
        with gzip.open(f,"rt") as fp:q=json.load(fp)
        assert q["schema"]==schema and q["variant"]==variant
        assert q["deck_sha256"]==SHA[variant]
        assert len(q["rows"])==q["games"]
        for i,r in enumerate(q["rows"]):
            gid=r["game_id"]
            assert gid==q["shard"]*q["games"]+i
            if gid<n:
                assert gid not in rows
                rows[gid]=r
    assert set(rows)==set(range(n)),(schema,variant,len(rows),n)
    return rows,len(files)

def summary(rows):
    n=len(rows);ct=Counter(x["win_turn"] for x in rows.values())
    return {"games":n,"T1":round(100*ct[1]/n,4),
            "T2":round(100*(ct[1]+ct[2])/n,4),
            "T3":round(100*(ct[1]+ct[2]+ct[3])/n,4),
            "mean_keep":round(sum(x["keep_n"] for x in rows.values())/n,3),
            "mean_rollout_calls":round(sum(x["rollout_calls"] for x in rows.values())/n,2)}

def paired(a,b):
    n=len(a);res={}
    for t in (1,2,3):
        ds=[int(0<a[i]["win_turn"]<=t)-int(0<b[i]["win_turn"]<=t)
            for i in range(n)]
        m=sum(ds)/n
        sd=math.sqrt(sum((d-m)**2 for d in ds)/((n-1)*n))
        res[f"T{t}"]={"delta_pp":round(100*m,4),
           "paired_95pct_pp":[round(100*(m-1.96*sd),3),round(100*(m+1.96*sd),3)],
           "v5_only":[i for i,d in enumerate(ds) if d>0],
           "v4_only":[i for i,d in enumerate(ds) if d<0]}
    return res

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--n",type=int,default=32)
    p.add_argument("--v4",default="v4")
    p.add_argument("--v5",default="v5")
    p.add_argument("--out",required=True)
    a=p.parse_args()
    data={"status":"PASS","n_per_deck":a.n,
          "design":"Matched-seed v5 twelve-draw Monte Carlo reward vs v4 three-draw Monte Carlo, same chance-aware beam and known-top information",
          "arms":{},"effects":{}}
    for variant in ("current","buck_worldmap"):
        v4,n4=load(f"{a.v4}/**/*{variant}*.json.gz",variant,a.n,
                   "dack_known_top_population_v4")
        v5,n5=load(f"{a.v5}/**/*{variant}*.json.gz",variant,a.n,
                   "dack_realistic_population_v5")
        data["arms"][variant]={"v4":summary(v4),"v5":summary(v5),
                              "v5_minus_v4":paired(v5,v4),
                              "artifact_shards":[n4,n5]}
        data.setdefault("_rows",{})[variant]={"v4":v4,"v5":v5}
    data["effects"]["buck_minus_worldmap_v5"]=paired(data["_rows"]["buck_worldmap"]["v5"],
                                             data["_rows"]["current"]["v5"])
    data["effects"]["buck_minus_worldmap_v4"]=paired(data["_rows"]["buck_worldmap"]["v4"],
                                             data["_rows"]["current"]["v4"])
    del data["_rows"]
    data["limitations"]=[
      "N32 is too small to settle 1-3pp differences",
      "V5 includes more future-draw samples and may still be systematically biased by finite beam",
      "Known-top tracking still partial",
      "In-turn hidden draw lookahead remains in legacy action generators",
      "No full combat interaction or post-Dack combo proof"]
    Path(a.out).write_text(json.dumps(data,indent=2)+"\n")
    print("DACK_V5_N32_REWARD_POPULATION_REPORT_PASS",json.dumps({
      "arms":{k:{"v4":v["v4"],"v5":v["v5"],"delta":v["v5_minus_v4"]}
              for k,v in data["arms"].items()}}),flush=True)
if __name__=="__main__":main()
