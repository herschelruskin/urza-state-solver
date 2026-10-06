#!/usr/bin/env python3
"""Pool compact core3 weak-slot N512 promotion artifacts."""
import argparse,csv,glob,gzip,json,math
from collections import defaultdict,Counter
Z=1.959963984540054
BASE="ablate__Final4_revert_Voltaic_to_Candelabra"
VARS=(
    "package__Core3_plus_Incubator_over_Prismatic",
    "package__Core3_plus_Lantern_over_Everflowing",
    "package__Core3_plus_Sonic_over_Everflowing",
)

def ep(w,k):
    w=int(w)
    if k=="T1": return int(w==1)
    if k=="le_T2": return int(w in (1,2))
    if k=="le_T3": return int(w in (1,2,3))
    raise ValueError(k)
def util(w):
    w=int(w); return 1.0 if w in (1,2) else .5 if w==3 else 0.0
def summ(rows):
    n=len(rows); c=Counter(int(r[4]) for r in rows)
    return {"n":n,"T1":c[1]/n,"le_T2":(c[1]+c[2])/n,
            "le_T3":(c[1]+c[2]+c[3])/n,
            "utility":sum(util(r[4]) for r in rows)/n,
            "mean_keep":sum(int(r[3]) for r in rows)/n}
def paired(a,b,fn):
    ds=[fn(x)-fn(y) for x,y in zip(a,b)]; n=len(ds); mu=sum(ds)/n
    var=sum((d-mu)**2 for d in ds)/(n-1) if n>1 else 0.0
    se=math.sqrt(var/n)
    return mu,(mu-Z*se,mu+Z*se)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--glob",required=True)
    ap.add_argument("--expected-games",type=int,default=512)
    ap.add_argument("--json-out",required=True)
    ap.add_argument("--csv-out",required=True)
    a=ap.parse_args()
    groups=defaultdict(list); meta={}
    files=glob.glob(a.glob)
    if not files: raise SystemExit("no compact artifacts")
    for fp in files:
        with gzip.open(fp,"rb") as f:p=json.loads(f.read())
        if p.get("schema")!="dack_compact_v1": raise SystemExit("schema mismatch "+fp)
        for v,z in p["variants"].items():
            groups[v].extend(z["rows"]); meta[v]={"replace":z["replace"],"deck_sha256":z["deck_sha256"]}
    for v in (BASE,)+VARS:
        groups[v].sort(key=lambda r:int(r[0]))
        if len(groups[v])!=a.expected_games: raise SystemExit(f"{v}: {len(groups[v])}")
        if len({int(r[0]) for r in groups[v]})!=a.expected_games: raise SystemExit("duplicate "+v)

    base=groups[BASE]; out=[]
    for v in VARS:
        rows=groups[v]
        for x,y in zip(rows,base):
            if tuple(map(int,x[:3]))!=tuple(map(int,y[:3])): raise SystemExit("pair mismatch "+v)
        rec={"variant":v,**summ(rows)}
        for k in ("T1","le_T2","le_T3"):
            mu,ci=paired(rows,base,lambda r,kk=k:ep(r[4],kk))
            vo=bo=0
            for x,y in zip(rows,base):
                xx=ep(x[4],k); yy=ep(y[4],k)
                vo+=int(xx and not yy); bo+=int(yy and not xx)
            rec[f"delta_{k}_pp"]=100*mu
            rec[f"ci95_{k}_lo_pp"]=100*ci[0]; rec[f"ci95_{k}_hi_pp"]=100*ci[1]
            rec[f"{k}_variant_only"]=vo; rec[f"{k}_core3_only"]=bo
        du,uci=paired(rows,base,lambda r:util(r[4]))
        dk,kci=paired(rows,base,lambda r:int(r[3]))
        rec["delta_utility"]=du; rec["ci95_utility_lo"]=uci[0]; rec["ci95_utility_hi"]=uci[1]
        rec["delta_mean_keep"]=dk
        rec["faster"]=sum((int(x[4]) or 4)<(int(y[4]) or 4) for x,y in zip(rows,base))
        rec["slower"]=sum((int(x[4]) or 4)>(int(y[4]) or 4) for x,y in zip(rows,base))
        rec["same"]=a.expected_games-rec["faster"]-rec["slower"]
        out.append(rec)
    out.sort(key=lambda r:(r["delta_utility"],r["delta_le_T2_pp"],r["delta_le_T3_pp"]),reverse=True)
    payload={"design":{"paired":True,"n_pairs":a.expected_games,"storage_schema":"dack_compact_v1",
        "baseline":"Core3: Bucknard over Liquimetal + KCI over Pearl + Manifold over Boulder; Candelabra retained"},
        "baseline_summary":summ(base),"results":out}
    with open(a.json_out,"w",encoding="utf-8") as f:json.dump(payload,f,indent=2)
    with open(a.csv_out,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(out[0].keys()));w.writeheader();w.writerows(out)

if __name__=="__main__":
    main()
