#!/usr/bin/env python3
"""Pool direct paired N=1024 comparison of the 3-card and 4-card packages."""
import argparse,csv,glob,json,math
from collections import Counter,defaultdict

Z=1.959963984540054
THREE="ablate__Final4_revert_Voltaic_to_Candelabra"
FOUR="package__Final4_Buck_KCI_Manifold_Voltaic"

def ep(w,name):
    w=int(w)
    if name=="T1": return int(w==1)
    if name=="le_T2": return int(w in (1,2))
    if name=="le_T3": return int(w in (1,2,3))
    raise ValueError(name)

def util(w):
    w=int(w)
    return 1.0 if w in (1,2) else (0.5 if w==3 else 0.0)

def summary(rows):
    n=len(rows); c=Counter(int(r["win_turn"]) for r in rows)
    return {
        "n":n,
        "T1":c[1]/n,
        "T2_exact":c[2]/n,
        "le_T2":(c[1]+c[2])/n,
        "T3_exact":c[3]/n,
        "le_T3":(c[1]+c[2]+c[3])/n,
        "fail_T3":c[0]/n,
        "utility_lambda_0_5":sum(util(r["win_turn"]) for r in rows)/n,
        "mean_keep":sum(int(r["keep_n"]) for r in rows)/n,
    }

def paired_binary(a,b,name):
    vals=[]; aonly=bonly=both=neither=0
    for x,y in zip(a,b):
        aa=ep(x["win_turn"],name); bb=ep(y["win_turn"],name)
        vals.append(aa-bb)
        if aa and bb: both+=1
        elif aa: aonly+=1
        elif bb: bonly+=1
        else: neither+=1
    n=len(vals); mu=sum(vals)/n
    var=sum((v-mu)**2 for v in vals)/(n-1) if n>1 else 0.0
    se=math.sqrt(var/n)
    return {
        "three_minus_four_rate":mu,
        "three_minus_four_pp":100*mu,
        "paired_se":se,
        "paired_ci95_pp":[100*(mu-Z*se),100*(mu+Z*se)],
        "three_only_success":aonly,
        "four_only_success":bonly,
        "both_success":both,
        "neither_success":neither,
        "discordant_pairs":aonly+bonly,
    }

def paired_mean(a,b,fn):
    vals=[float(fn(x))-float(fn(y)) for x,y in zip(a,b)]
    n=len(vals); mu=sum(vals)/n
    var=sum((v-mu)**2 for v in vals)/(n-1) if n>1 else 0.0
    se=math.sqrt(var/n)
    return {"mean_delta":mu,"se":se,"ci95":[mu-Z*se,mu+Z*se]}

def load_baseline(path,n):
    out=[]
    with open(path,newline="",encoding="utf-8") as f:
        for r in csv.DictReader(f):
            gid=int(r["game_id"])
            if gid>=n: continue
            out.append({"game_id":gid,"seed":int(r["seed"]),"seat":int(r["seat"]),
                        "keep_n":int(r["keep_n"]),"win_turn":int(r["win_turn"])})
    out.sort(key=lambda r:r["game_id"])
    if len(out)!=n: raise SystemExit(f"baseline rows {len(out)} != {n}")
    return out

def paired_vs_base(rows,base,name):
    return paired_binary(rows,base,name)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--glob",required=True)
    ap.add_argument("--baseline-games",required=True)
    ap.add_argument("--expected-games",type=int,default=1024)
    ap.add_argument("--json-out",required=True)
    ap.add_argument("--csv-out",required=True)
    a=ap.parse_args()

    groups=defaultdict(list); sigs={}
    for fp in glob.glob(a.glob):
        with open(fp,encoding="utf-8") as f:p=json.load(f)
        v=p["variant"]
        if v not in (THREE,FOUR): continue
        groups[v].extend(p["rows"])
        sig=p["compatibility_signature"]
        if v in sigs and sigs[v]!=sig: raise SystemExit(f"incompatible shards {v}")
        sigs[v]=sig

    for v in (THREE,FOUR):
        groups[v].sort(key=lambda r:int(r["game_id"]))
        if len(groups[v])!=a.expected_games:
            raise SystemExit(f"{v}: {len(groups[v])} rows")
        seen=set()
        for r in groups[v]:
            gid=int(r["game_id"])
            if gid in seen: raise SystemExit(f"duplicate {v} {gid}")
            seen.add(gid)

    three=groups[THREE]; four=groups[FOUR]
    for x,y in zip(three,four):
        if int(x["game_id"])!=int(y["game_id"]) or int(x["seed"])!=int(y["seed"]) or int(x["seat"])!=int(y["seat"]):
            raise SystemExit("3-vs-4 pairing mismatch")

    base=load_baseline(a.baseline_games,a.expected_games)
    for rows,v in ((three,THREE),(four,FOUR)):
        for x,y in zip(rows,base):
            if int(x["game_id"])!=y["game_id"] or int(x["seed"])!=y["seed"] or int(x["seat"])!=y["seat"]:
                raise SystemExit(f"baseline pairing mismatch {v}")

    direct={name:paired_binary(three,four,name) for name in ("T1","le_T2","le_T3")}
    util_direct=paired_mean(three,four,lambda r:util(r["win_turn"]))
    keep_direct=paired_mean(three,four,lambda r:int(r["keep_n"]))

    three_faster=four_faster=same=0
    for x,y in zip(three,four):
        tx=int(x["win_turn"]) or 4; fy=int(y["win_turn"]) or 4
        if tx<fy: three_faster+=1
        elif fy<tx: four_faster+=1
        else:same+=1

    vs_current={}
    for label,rows in (("three_card",three),("four_card",four)):
        vs_current[label]={
            "summary":summary(rows),
            "delta_vs_current":{
                name:paired_vs_base(rows,base,name)
                for name in ("T1","le_T2","le_T3")
            },
            "utility_delta_vs_current":paired_mean(rows,base,lambda r:util(r["win_turn"])),
            "mean_keep_delta_vs_current":paired_mean(rows,base,lambda r:int(r["keep_n"])),
        }

    payload={
        "design":{
            "paired":True,
            "n_pairs":a.expected_games,
            "three_card_package":"Bucknard's Everfull Purse + Krark-Clan Ironworks + Manifold Key; keep Candelabra of Tawnos",
            "four_card_package":"Bucknard's Everfull Purse + Krark-Clan Ironworks + Manifold Key + Voltaic Key; cut Candelabra of Tawnos",
            "same_game_ids_seeds_seats":True,
            "baseline":"frozen v0.76 current-99 first 1024 games",
        },
        "three_card_summary":summary(three),
        "four_card_summary":summary(four),
        "direct_three_minus_four":direct,
        "utility_three_minus_four":util_direct,
        "mean_keep_three_minus_four":keep_direct,
        "win_timing":{"three_faster":three_faster,"four_faster":four_faster,"same":same},
        "vs_current":vs_current,
    }
    with open(a.json_out,"w",encoding="utf-8") as f:json.dump(payload,f,indent=2)

    rows=[]
    for name in ("T1","le_T2","le_T3"):
        p=direct[name]
        rows.append({
            "endpoint":name,
            "three_card_rate":summary(three)[name],
            "four_card_rate":summary(four)[name],
            "three_minus_four_pp":p["three_minus_four_pp"],
            "ci95_lo_pp":p["paired_ci95_pp"][0],
            "ci95_hi_pp":p["paired_ci95_pp"][1],
            "three_only_success":p["three_only_success"],
            "four_only_success":p["four_only_success"],
            "discordant_pairs":p["discordant_pairs"],
        })
    fields=list(rows[0].keys())
    with open(a.csv_out,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    print(json.dumps({"status":"complete","n":a.expected_games,"json_out":a.json_out,"csv_out":a.csv_out},indent=2))

if __name__=="__main__":main()
