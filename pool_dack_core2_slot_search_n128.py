#!/usr/bin/env python3
"""Pool the broad paired N=128 core2 slot search."""
import argparse,csv,glob,json,math
from collections import defaultdict,Counter
Z=1.959963984540054

def ep(w,name):
    w=int(w)
    if name=="T1": return int(w==1)
    if name=="le_T2": return int(w in (1,2))
    if name=="le_T3": return int(w in (1,2,3))
    raise ValueError(name)
def util(w):
    w=int(w); return 1.0 if w in (1,2) else (0.5 if w==3 else 0.0)
def summary(rows):
    n=len(rows); c=Counter(int(r["win_turn"]) for r in rows)
    return {"n":n,"T1":c[1]/n,"le_T2":(c[1]+c[2])/n,
            "le_T3":(c[1]+c[2]+c[3])/n,
            "utility":sum(util(r["win_turn"]) for r in rows)/n,
            "mean_keep":sum(int(r["keep_n"]) for r in rows)/n}
def paired(a,b,fn):
    vals=[float(fn(x))-float(fn(y)) for x,y in zip(a,b)]
    n=len(vals); mu=sum(vals)/n
    var=sum((v-mu)**2 for v in vals)/(n-1) if n>1 else 0
    se=math.sqrt(var/n)
    return mu,[mu-Z*se,mu+Z*se]
def binary(a,b,name):
    mu,ci=paired(a,b,lambda r:ep(r["win_turn"],name))
    ao=bo=0
    for x,y in zip(a,b):
        xx=ep(x["win_turn"],name); yy=ep(y["win_turn"],name)
        if xx and not yy: ao+=1
        elif yy and not xx: bo+=1
    return 100*mu,[100*ci[0],100*ci[1]],ao,bo

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--glob",required=True)
    ap.add_argument("--expected-games",type=int,default=128)
    ap.add_argument("--json-out",required=True)
    ap.add_argument("--csv-out",required=True)
    a=ap.parse_args()
    groups=defaultdict(list); meta={}
    for fp in glob.glob(a.glob):
        with open(fp,encoding="utf-8") as f:p=json.load(f)
        groups[p["label"]].extend(p["rows"])
        meta[p["label"]]={"candidate":p["candidate"],"cut":p["cut"],
                          "deck_sha256":p["compatibility_signature"]["deck_sha256"]}
    for label,rows in groups.items():
        rows.sort(key=lambda r:int(r["game_id"]))
        if len(rows)!=a.expected_games: raise SystemExit(f"{label}: {len(rows)}")
        if len({int(r["game_id"]) for r in rows})!=a.expected_games: raise SystemExit(f"duplicate {label}")
    base=groups["CORE2_BASE"]
    out=[]
    for label,rows in groups.items():
        if label=="CORE2_BASE": continue
        for x,y in zip(rows,base):
            if (int(x["game_id"]),int(x["seed"]),int(x["seat"])) != (int(y["game_id"]),int(y["seed"]),int(y["seat"])):
                raise SystemExit("pair mismatch "+label)
        t1=binary(rows,base,"T1"); t2=binary(rows,base,"le_T2"); t3=binary(rows,base,"le_T3")
        du,uci=paired(rows,base,lambda r:util(r["win_turn"]))
        dk,kci=paired(rows,base,lambda r:int(r["keep_n"]))
        faster=slower=same=0
        for x,y in zip(rows,base):
            tx=int(x["win_turn"]) or 4; ty=int(y["win_turn"]) or 4
            if tx<ty:faster+=1
            elif ty<tx:slower+=1
            else:same+=1
        s=summary(rows)
        out.append({
            "label":label,"candidate":meta[label]["candidate"],"cut":meta[label]["cut"],
            "T1":s["T1"],"le_T2":s["le_T2"],"le_T3":s["le_T3"],"utility":s["utility"],
            "delta_T1_pp":t1[0],"ci_T1_lo_pp":t1[1][0],"ci_T1_hi_pp":t1[1][1],
            "delta_leT2_pp":t2[0],"ci_leT2_lo_pp":t2[1][0],"ci_leT2_hi_pp":t2[1][1],
            "delta_leT3_pp":t3[0],"ci_leT3_lo_pp":t3[1][0],"ci_leT3_hi_pp":t3[1][1],
            "delta_utility":du,"ci_utility_lo":uci[0],"ci_utility_hi":uci[1],
            "delta_mean_keep":dk,"faster":faster,"slower":slower,"same":same,
            "discordant_leT2":t2[2]+t2[3],"discordant_leT3":t3[2]+t3[3],
        })
    out.sort(key=lambda r:(r["delta_utility"],r["delta_leT2_pp"],r["delta_leT3_pp"]),reverse=True)
    payload={"design":{"paired":True,"n_pairs":a.expected_games,
             "baseline":"Bucknard over Liquimetal + KCI over Pearl; all other current cards retained",
             "purpose":"broad discovery for additional acceleration in other mana slots"},
             "baseline_summary":summary(base),"results":out}
    with open(a.json_out,"w",encoding="utf-8") as f:json.dump(payload,f,indent=2)
    fields=list(out[0].keys())
    with open(a.csv_out,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(out)
    print(json.dumps({"status":"complete","variants":len(out),"baseline":payload["baseline_summary"],
                      "top5":[(r["candidate"],r["cut"],r["delta_utility"]) for r in out[:5]]},indent=2))

if __name__=="__main__":main()
