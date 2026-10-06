#!/usr/bin/env python3
"""Pool compact paired N512 weak-slot promotion shards."""
import argparse,csv,glob,json,math
from collections import defaultdict,Counter
Z=1.959963984540054
BASE="ablate__Final4_revert_Voltaic_to_Candelabra"
VARS=[
"package__Core3_plus_Incubator_over_Prismatic",
"package__Core3_plus_Lantern_over_Everflowing",
"package__Core3_plus_Sonic_over_Everflowing",
]

def ep(w,name):
    w=int(w)
    if name=="T1": return int(w==1)
    if name=="le_T2": return int(w in (1,2))
    if name=="le_T3": return int(w in (1,2,3))
    raise ValueError(name)
def util(w):
    w=int(w)
    return 1.0 if w in (1,2) else .5 if w==3 else 0.0
def summary(rows):
    n=len(rows); c=Counter(int(r[3]) for r in rows)
    return {"n":n,"T1":c[1]/n,"le_T2":(c[1]+c[2])/n,
            "le_T3":(c[1]+c[2]+c[3])/n,
            "utility":sum(util(r[3]) for r in rows)/n,
            "mean_keep":sum(int(r[2]) for r in rows)/n}
def paired(a,b,fn):
    ds=[fn(x)-fn(y) for x,y in zip(a,b)]
    n=len(ds); mu=sum(ds)/n
    var=sum((x-mu)**2 for x in ds)/(n-1) if n>1 else 0.0
    se=math.sqrt(var/n)
    return mu,(mu-Z*se,mu+Z*se)
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--glob",required=True)
    ap.add_argument("--expected-games",type=int,default=512)
    ap.add_argument("--json-out",required=True)
    ap.add_argument("--csv-out",required=True)
    a=ap.parse_args()
    groups=defaultdict(list); repl={}
    for fp in glob.glob(a.glob):
        with open(fp,encoding="utf-8") as f:p=json.load(f)
        if p.get("schema")!="dack_compact_rows_v1": raise SystemExit("bad schema "+fp)
        groups[p["variant"]].extend(p["rows"]); repl[p["variant"]]=p["replace"]
    for v in [BASE]+VARS:
        groups[v].sort(key=lambda r:int(r[0]))
        if len(groups[v])!=a.expected_games: raise SystemExit(f"{v}: {len(groups[v])}")
        if len({int(r[0]) for r in groups[v]})!=a.expected_games: raise SystemExit("duplicate "+v)
    base=groups[BASE]; out=[]
    for v in VARS:
        rows=groups[v]
        for x,y in zip(rows,base):
            if (int(x[0]),int(x[1]))!=(int(y[0]),int(y[1])): raise SystemExit("pair mismatch "+v)
        s=summary(rows)
        row={"variant":v,"replace":json.dumps(repl[v],separators=(",",":")),**s}
        for name in ("T1","le_T2","le_T3"):
            mu,ci=paired(rows,base,lambda r,n=name:ep(r[3],n))
            vo=bo=0
            for x,y in zip(rows,base):
                xx=ep(x[3],name); yy=ep(y[3],name)
                vo+=int(xx and not yy); bo+=int(yy and not xx)
            row[f"delta_{name}_pp"]=100*mu
            row[f"ci95_{name}_lo_pp"]=100*ci[0]
            row[f"ci95_{name}_hi_pp"]=100*ci[1]
            row[f"{name}_variant_only"]=vo; row[f"{name}_core3_only"]=bo
        du,uci=paired(rows,base,lambda r:util(r[3]))
        dk,kci=paired(rows,base,lambda r:int(r[2]))
        row["delta_utility"]=du; row["ci95_utility_lo"]=uci[0]; row["ci95_utility_hi"]=uci[1]
        row["delta_mean_keep"]=dk; row["ci95_mean_keep_lo"]=kci[0]; row["ci95_mean_keep_hi"]=kci[1]
        faster=slower=same=0
        for x,y in zip(rows,base):
            tx=int(x[3]) or 4; ty=int(y[3]) or 4
            if tx<ty:faster+=1
            elif ty<tx:slower+=1
            else:same+=1
        row["faster"]=faster; row["slower"]=slower; row["same"]=same
        out.append(row)
    out.sort(key=lambda r:(r["delta_utility"],r["delta_le_T2_pp"],r["delta_le_T3_pp"]),reverse=True)
    payload={"schema":"dack_paired_summary_v1",
             "design":{"paired":True,"n_pairs":a.expected_games,
                       "baseline":"Core3: Bucknard over Liquimetal + KCI over Pearl + Manifold over Boulder; Candelabra retained",
                       "production_rows":"compact [game_id,seat,keep_n,win_turn]"},
             "baseline_summary":summary(base),"results":out}
    with open(a.json_out,"w",encoding="utf-8") as f:json.dump(payload,f,indent=2)
    with open(a.csv_out,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(out[0].keys()));w.writeheader();w.writerows(out)

if __name__=="__main__":
    main()
