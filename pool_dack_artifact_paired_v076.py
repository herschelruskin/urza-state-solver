#!/usr/bin/env python3
import argparse, glob, json, math, os
from collections import Counter

def ci_mean(v,z=1.959963984540054):
    n=len(v)
    if n<2:return [0,0]
    m=sum(v)/n
    s=math.sqrt(sum((x-m)**2 for x in v)/(n-1))
    h=z*s/math.sqrt(n)
    return [m-h,m+h]

ap=argparse.ArgumentParser()
ap.add_argument("--glob",required=True); ap.add_argument("--out",required=True)
a=ap.parse_args()
ps=[json.load(open(f)) for f in sorted(glob.glob(a.glob))]
assert ps
sig={(p["group"],p["base_deck_sha256"],json.dumps(p["policy_signature"],sort_keys=True)) for p in ps}
assert len(sig)==1,"incompatible shards"
rows=[r for p in ps for r in p["rows"]]
ids=[r["game_id"] for r in rows]; assert len(ids)==len(set(ids))
rows.sort(key=lambda r:r["game_id"])
names=list(rows[0]["variants"])
summary={}
for name in names:
    turns=[r["variants"][name]["win_turn"] for r in rows]
    c=Counter(turns); n=len(rows)
    summary[name]={"n":n,"counts":{str(k):int(v) for k,v in sorted(c.items())},
      "T1":c.get(1,0)/n,"le_T2":sum(t in (1,2) for t in turns)/n,
      "T3_exact":c.get(3,0)/n,"le_T3":sum(t in (1,2,3) for t in turns)/n,
      "utility":sum(1 if t in (1,2) else .5 if t==3 else 0 for t in turns)/n,
      "mean_keep":sum(r["variants"][name]["keep_n"] for r in rows)/n}
paired={}
for name in names[1:]:
    du=[]; better=worse=same=0; le2u=le2d=le3u=le3d=0
    for r in rows:
        bt=r["variants"]["baseline"]["win_turn"]; vt=r["variants"][name]["win_turn"]
        bu=1 if bt in (1,2) else .5 if bt==3 else 0
        vu=1 if vt in (1,2) else .5 if vt==3 else 0
        du.append(vu-bu)
        rank=lambda t:4 if t==0 else t
        if rank(vt)<rank(bt):better+=1
        elif rank(vt)>rank(bt):worse+=1
        else:same+=1
        b2=bt in (1,2);v2=vt in (1,2);b3=bt in (1,2,3);v3=vt in (1,2,3)
        if v2 and not b2:le2u+=1
        if b2 and not v2:le2d+=1
        if v3 and not b3:le3u+=1
        if b3 and not v3:le3d+=1
    paired[name]={"delta_utility":sum(du)/len(du),"delta_utility_ci95_normal":ci_mean(du),
      "delta_le_T2":summary[name]["le_T2"]-summary["baseline"]["le_T2"],
      "delta_le_T3":summary[name]["le_T3"]-summary["baseline"]["le_T3"],
      "turn_outcome":{"better":better,"worse":worse,"same":same},
      "le_T2_flips":{"improved":le2u,"worsened":le2d},
      "le_T3_flips":{"improved":le3u,"worsened":le3d}}
out={"test":"artifact_benchmark_paired_v076","group":ps[0]["group"],"n":len(rows),
     "base_deck_sha256":ps[0]["base_deck_sha256"],"policy_signature":ps[0]["policy_signature"],
     "generic_benchmark":ps[0]["generic_benchmark"],"summary":summary,"paired":paired}
os.makedirs(os.path.dirname(a.out) or ".",exist_ok=True)
json.dump(out,open(a.out,"w"),indent=2)
print(json.dumps(out,indent=2))
