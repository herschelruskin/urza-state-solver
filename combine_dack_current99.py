#!/usr/bin/env python3
import argparse, json, math, os
from collections import Counter

def wilson(k,n,z=1.959963984540054):
    if n==0:return [0.0,0.0]
    p=k/n; den=1+z*z/n
    ctr=(p+z*z/(2*n))/den
    half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [max(0,ctr-half),min(1,ctr+half)]

ap=argparse.ArgumentParser()
ap.add_argument("--base",required=True)
ap.add_argument("--extension",required=True)
ap.add_argument("--out",required=True)
a=ap.parse_args()

base=json.load(open(a.base))
ext=json.load(open(a.extension))
assert base["compatibility_signature"]==ext["compatibility_signature"], "baseline/extension config mismatch"

def count(obj,key): return int(obj["summary"][key]["count"])
keys=["T1","T2_exact","le_T2","T3_exact","le_T3","fail_T3"]
n=int(base["n"])+int(ext["n"])
summary={}
for k in keys:
    c=count(base,k)+count(ext,k)
    summary[k]={"count":c,"rate":c/n,"ci95":wilson(c,n)}

keep=Counter({int(k):int(v) for k,v in base.get("keep_counts",{}).items()})
keep.update({int(k):int(v) for k,v in ext.get("keep_counts",{}).items()})
seat=Counter({int(k):int(v) for k,v in base.get("seat_counts",{}).items()})
seat.update({int(k):int(v) for k,v in ext.get("seat_counts",{}).items()})
mean_keep=sum(k*v for k,v in keep.items())/n

out={
  "compatibility_signature":base["compatibility_signature"],
  "n":n,
  "base_n":int(base["n"]),
  "extension_n":int(ext["n"]),
  "utility_lambda_0_5":summary["le_T2"]["rate"]+0.5*summary["T3_exact"]["rate"],
  "summary":summary,
  "mean_keep":mean_keep,
  "keep_counts":dict(sorted(keep.items(),reverse=True)),
  "seat_counts":dict(sorted(seat.items())),
  "base_source":a.base,
  "extension_source":a.extension,
}
os.makedirs(os.path.dirname(a.out),exist_ok=True)
json.dump(out,open(a.out,"w"),indent=2)
print(json.dumps(out,indent=2))
