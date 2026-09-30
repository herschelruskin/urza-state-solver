#!/usr/bin/env python3
import argparse,glob,json,math,os
ap=argparse.ArgumentParser();ap.add_argument("--glob",required=True);ap.add_argument("--out",required=True);a=ap.parse_args()
rows=[]
for f in glob.glob(a.glob): rows+=json.load(open(f))["rows"]
ids=[r["game_id"] for r in rows]; assert len(ids)==len(set(ids))
rows.sort(key=lambda r:r["game_id"])
def summ(which):
    ts=[r[which]["win_turn"] for r in rows]; n=len(ts)
    return {"n":n,"T1":sum(t==1 for t in ts)/n,"le_T2":sum(t in (1,2) for t in ts)/n,
            "T3_exact":sum(t==3 for t in ts)/n,"le_T3":sum(t in (1,2,3) for t in ts)/n,
            "utility":sum(r[which]["utility"] for r in rows)/n,
            "mean_keep":sum(r[which]["keep_n"] for r in rows)/n}
o=summ("old");f=summ("fixed")
du=[r["fixed"]["utility"]-r["old"]["utility"] for r in rows]
better=worse=same=0
rank=lambda t:4 if t==0 else t
for r in rows:
    x=rank(r["old"]["win_turn"]);y=rank(r["fixed"]["win_turn"])
    if y<x: better+=1
    elif y>x:worse+=1
    else:same+=1
out={"test":"pearl_artifact_identity_paired","n":len(rows),"old":o,"fixed":f,
     "delta":{"le_T2":f["le_T2"]-o["le_T2"],"le_T3":f["le_T3"]-o["le_T3"],
              "utility":f["utility"]-o["utility"],"better":better,"worse":worse,"same":same}}
os.makedirs(os.path.dirname(a.out) or ".",exist_ok=True);json.dump(out,open(a.out,"w"),indent=2);print(json.dumps(out,indent=2))
