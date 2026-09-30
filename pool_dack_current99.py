#!/usr/bin/env python3
import argparse, json, glob, math, csv, os
from collections import Counter

def wilson(k,n,z=1.959963984540054):
    if n==0:return [0.0,0.0]
    p=k/n; den=1+z*z/n
    ctr=(p+z*z/(2*n))/den
    half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [max(0,ctr-half),min(1,ctr+half)]

ap=argparse.ArgumentParser()
ap.add_argument("--glob",dest="pat",default="shards/**/*.json")
ap.add_argument("--json-out",default="results/dack_v075_current99_n128.json")
ap.add_argument("--csv-out",default="results/dack_v075_current99_n128_games.csv")
a=ap.parse_args()

paths=sorted(glob.glob(a.pat,recursive=True))
if not paths: raise SystemExit("no shard JSON files")
payloads=[json.load(open(p)) for p in paths]
sig=payloads[0]["compatibility_signature"]
for p in payloads[1:]:
    assert p["compatibility_signature"]==sig, "incompatible shard signature"
rows=[]
for p in payloads: rows.extend(p["rows"])
ids=[r["game_id"] for r in rows]
assert len(ids)==len(set(ids)), "duplicate game ids"
rows.sort(key=lambda r:r["game_id"])
n=len(rows); c=Counter(r["win_turn"] for r in rows)
metrics={
    "T1":c[1],
    "T2_exact":c[2],
    "le_T2":c[1]+c[2],
    "T3_exact":c[3],
    "le_T3":c[1]+c[2]+c[3],
    "fail_T3":c[0],
}
summary={}
for name,k in metrics.items():
    summary[name]={"count":k,"rate":k/n,"ci95":wilson(k,n)}
keep=Counter(r["keep_n"] for r in rows)
seat=Counter(r["seat"] for r in rows)
out={
    "compatibility_signature":sig,
    "n":n,
    "shards":len(payloads),
    "summary":summary,
    "mean_keep":sum(r["keep_n"] for r in rows)/n,
    "keep_counts":dict(sorted(keep.items(),reverse=True)),
    "seat_counts":dict(sorted(seat.items())),
    "source_shards":[{"shard":p["shard"],"games":p["games"],
                      "elapsed_seconds":p["elapsed_seconds"]} for p in payloads],
}
os.makedirs(os.path.dirname(a.json_out),exist_ok=True)
json.dump(out,open(a.json_out,"w"),indent=2)
with open(a.csv_out,"w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=["game_id","seed","seat","keep_n","keep_utility","win_turn"])
    w.writeheader()
    for r in rows:w.writerow({k:r[k] for k in w.fieldnames})
print(json.dumps(out,indent=2))
