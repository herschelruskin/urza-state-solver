#!/usr/bin/env python3
import argparse, glob, json, math, os
from collections import Counter

def ci_mean(vals,z=1.959963984540054):
    n=len(vals)
    if n < 2: return [0.0,0.0]
    m=sum(vals)/n
    s=math.sqrt(sum((x-m)**2 for x in vals)/(n-1))
    h=z*s/math.sqrt(n)
    return [m-h,m+h]

def rate(rows,name,pred):
    return sum(1 for r in rows if pred(r["variants"][name]["win_turn"])) / len(rows)

ap=argparse.ArgumentParser()
ap.add_argument("--glob",required=True)
ap.add_argument("--out",required=True)
a=ap.parse_args()
files=sorted(glob.glob(a.glob))
assert files, "no inputs"
payloads=[json.load(open(f)) for f in files]
sig={(p["base_deck_sha256"],json.dumps(p["policy_signature"],sort_keys=True),tuple(p["lands"])) for p in payloads}
assert len(sig)==1, "incompatible paired shards"
rows=[r for p in payloads for r in p["rows"]]
ids=[r["game_id"] for r in rows]
assert len(ids)==len(set(ids)), "duplicate game ids"
rows.sort(key=lambda r:r["game_id"])
lands=payloads[0]["lands"]
names=["baseline"]+lands
summary={}
for name in names:
    turns=[r["variants"][name]["win_turn"] for r in rows]
    c=Counter(turns)
    summary[name]={
      "n":len(rows),
      "counts":{str(k):int(v) for k,v in sorted(c.items())},
      "T1":c.get(1,0)/len(rows),
      "le_T2":sum(1 for t in turns if t in (1,2))/len(rows),
      "T3_exact":c.get(3,0)/len(rows),
      "le_T3":sum(1 for t in turns if t in (1,2,3))/len(rows),
      "utility":sum(1.0 if t in (1,2) else 0.5 if t==3 else 0.0 for t in turns)/len(rows),
      "mean_keep":sum(r["variants"][name]["keep_n"] for r in rows)/len(rows),
    }
base="baseline"
paired={}
for name in lands:
    du=[]; le2_up=le2_down=le3_up=le3_down=0
    turn_better=turn_worse=turn_same=0
    for r in rows:
        bt=r["variants"][base]["win_turn"]; vt=r["variants"][name]["win_turn"]
        bu=1.0 if bt in (1,2) else 0.5 if bt==3 else 0.0
        vu=1.0 if vt in (1,2) else 0.5 if vt==3 else 0.0
        du.append(vu-bu)
        b2=bt in (1,2); v2=vt in (1,2)
        b3=bt in (1,2,3); v3=vt in (1,2,3)
        if v2 and not b2: le2_up+=1
        if b2 and not v2: le2_down+=1
        if v3 and not b3: le3_up+=1
        if b3 and not v3: le3_down+=1
        rank=lambda t: 4 if t==0 else t
        if rank(vt)<rank(bt): turn_better+=1
        elif rank(vt)>rank(bt): turn_worse+=1
        else: turn_same+=1
    paired[name]={
      "delta_utility":sum(du)/len(du),
      "delta_utility_ci95_normal":ci_mean(du),
      "delta_le_T2":summary[name]["le_T2"]-summary[base]["le_T2"],
      "delta_le_T3":summary[name]["le_T3"]-summary[base]["le_T3"],
      "le_T2_flips":{"improved":le2_up,"worsened":le2_down},
      "le_T3_flips":{"improved":le3_up,"worsened":le3_down},
      "turn_outcome":{"better":turn_better,"worse":turn_worse,"same":turn_same},
    }
out={
 "test":"land_to_thought_vessel_paired",
 "n":len(rows),
 "base_deck_sha256":payloads[0]["base_deck_sha256"],
 "policy_signature":payloads[0]["policy_signature"],
 "summary":summary,
 "paired":paired,
}
os.makedirs(os.path.dirname(a.out) or ".",exist_ok=True)
json.dump(out,open(a.out,"w"),indent=2)
print(json.dumps(out,indent=2))
