#!/usr/bin/env python3
import argparse,csv,glob,json,math
from collections import defaultdict,Counter
Z=1.959963984540054
BASE="ablate__Final4_revert_Voltaic_to_Candelabra"
VARS=[
"package__Core3_plus_Voltaic_over_Basalt",
"package__Core3_plus_CloudKey_over_TheMindStone",
"package__Core3_plus_Extraplanar_over_TheMindStone",
"package__Core3_plus_Helm_over_Coalition",
]
def ep(w,n):
    w=int(w)
    return int(w==1) if n=="T1" else int(w in (1,2)) if n=="le_T2" else int(w in (1,2,3))
def util(w):
    w=int(w); return 1.0 if w in (1,2) else .5 if w==3 else 0.0
def summ(rows):
    n=len(rows); c=Counter(int(r["win_turn"]) for r in rows)
    return {"n":n,"T1":c[1]/n,"le_T2":(c[1]+c[2])/n,"le_T3":(c[1]+c[2]+c[3])/n,
            "utility":sum(util(r["win_turn"]) for r in rows)/n,
            "mean_keep":sum(int(r["keep_n"]) for r in rows)/n}
def paired(a,b,fn):
    ds=[fn(x)-fn(y) for x,y in zip(a,b)]; n=len(ds); mu=sum(ds)/n
    var=sum((d-mu)**2 for d in ds)/(n-1) if n>1 else 0; se=math.sqrt(var/n)
    return mu,(mu-Z*se,mu+Z*se)
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--glob",required=True); ap.add_argument("--expected-games",type=int,default=512)
    ap.add_argument("--json-out",required=True); ap.add_argument("--csv-out",required=True)
    a=ap.parse_args()
    g=defaultdict(list)
    for fp in glob.glob(a.glob):
        with open(fp,encoding="utf-8") as f:p=json.load(f)
        if p["variant"] in [BASE]+VARS:g[p["variant"]].extend(p["rows"])
    for k in [BASE]+VARS:
        g[k].sort(key=lambda r:int(r["game_id"]))
        if len(g[k])!=a.expected_games: raise SystemExit(f"{k}: {len(g[k])}")
    base=g[BASE]; out=[]
    for v in VARS:
        rows=g[v]
        for x,y in zip(rows,base):
            if (int(x["game_id"]),int(x["seed"]),int(x["seat"]))!=(int(y["game_id"]),int(y["seed"]),int(y["seat"])):
                raise SystemExit("pair mismatch "+v)
        row={"variant":v,**summ(rows)}
        for endpoint in ("T1","le_T2","le_T3"):
            mu,ci=paired(rows,base,lambda r,e=endpoint:ep(r["win_turn"],e))
            ao=bo=0
            for x,y in zip(rows,base):
                xx=ep(x["win_turn"],endpoint); yy=ep(y["win_turn"],endpoint)
                ao+=int(xx and not yy); bo+=int(yy and not xx)
            row[f"delta_{endpoint}_pp"]=100*mu
            row[f"ci95_{endpoint}_lo_pp"]=100*ci[0]; row[f"ci95_{endpoint}_hi_pp"]=100*ci[1]
            row[f"{endpoint}_variant_only"]=ao; row[f"{endpoint}_core3_only"]=bo
        du,uci=paired(rows,base,lambda r:util(r["win_turn"]))
        dk,kci=paired(rows,base,lambda r:int(r["keep_n"]))
        row["delta_utility"]=du; row["ci95_utility_lo"]=uci[0]; row["ci95_utility_hi"]=uci[1]
        row["delta_mean_keep"]=dk
        out.append(row)
    out.sort(key=lambda r:(r["delta_utility"],r["delta_le_T2_pp"],r["delta_le_T3_pp"]),reverse=True)
    payload={"design":{"paired":True,"n_pairs":a.expected_games,"baseline":"Core3: Bucknard over Liquimetal + KCI over Pearl + Manifold over Boulder; Candelabra retained"},
             "baseline_summary":summ(base),"results":out}
    with open(a.json_out,"w",encoding="utf-8") as f:json.dump(payload,f,indent=2)
    with open(a.csv_out,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(out[0].keys()));w.writeheader();w.writerows(out)
if __name__=="__main__":main()
