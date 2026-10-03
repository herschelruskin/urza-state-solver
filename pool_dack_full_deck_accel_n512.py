#!/usr/bin/env python3
"""Pool paired N=512 full-deck acceleration revalidation shards."""
import argparse,csv,glob,json,math,os
from collections import Counter,defaultdict

Z=1.959963984540054

def endpoint(w,name):
    w=int(w)
    if name=="T1": return int(w==1)
    if name=="le_T2": return int(w in (1,2))
    if name=="le_T3": return int(w in (1,2,3))
    raise ValueError(name)

def utility(w):
    w=int(w)
    return 1.0 if w in (1,2) else (0.5 if w==3 else 0.0)

def arm(rows):
    n=len(rows); c=Counter(int(r["win_turn"]) for r in rows)
    le2=c[1]+c[2]; le3=le2+c[3]
    return {
        "n":n,
        "T1":c[1]/n,"T2_exact":c[2]/n,"le_T2":le2/n,
        "T3_exact":c[3]/n,"le_T3":le3/n,"fail_T3":c[0]/n,
        "utility_lambda_0_5":(le2+0.5*c[3])/n,
        "mean_keep":sum(int(r["keep_n"]) for r in rows)/n,
    }

def paired_stats(a,b,fn=lambda r:r):
    # a-b
    vals=[float(fn(x))-float(fn(y)) for x,y in zip(a,b)]
    n=len(vals); mu=sum(vals)/n
    var=sum((x-mu)**2 for x in vals)/(n-1) if n>1 else 0.0
    se=math.sqrt(var/n) if n else 0.0
    return {"delta":mu,"se":se,"ci95":[mu-Z*se,mu+Z*se]}

def paired_binary(a,b,name):
    ao=bo=both=neither=0
    diffs=[]
    for x,y in zip(a,b):
        aa=endpoint(x["win_turn"],name); bb=endpoint(y["win_turn"],name)
        diffs.append(aa-bb)
        if aa and bb: both+=1
        elif aa: ao+=1
        elif bb: bo+=1
        else: neither+=1
    n=len(diffs); mu=sum(diffs)/n
    var=sum((x-mu)**2 for x in diffs)/(n-1) if n>1 else 0.0
    se=math.sqrt(var/n) if n else 0.0
    return {
        "delta":mu,"delta_pp":100*mu,"se":se,
        "ci95":[mu-Z*se,mu+Z*se],
        "ci95_pp":[100*(mu-Z*se),100*(mu+Z*se)],
        "a_only":ao,"b_only":bo,"both":both,"neither":neither,
        "discordant":ao+bo,
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--glob",required=True)
    ap.add_argument("--baseline-games",required=True)
    ap.add_argument("--expected-games",type=int,default=512)
    ap.add_argument("--variants",required=True,help="semicolon-separated expected variant names")
    ap.add_argument("--json-out",required=True)
    ap.add_argument("--csv-out",required=True)
    a=ap.parse_args()
    expected=[x for x in a.variants.split(";") if x]

    base=[]
    with open(a.baseline_games,newline="",encoding="utf-8") as f:
        for r in csv.DictReader(f):
            gid=int(r["game_id"])
            if gid>=a.expected_games: continue
            base.append({
                "game_id":gid,"seed":int(r["seed"]),"seat":int(r["seat"]),
                "keep_n":int(r["keep_n"]),"win_turn":int(r["win_turn"]),
                "keep_utility":float(r["keep_utility"]),
            })
    base.sort(key=lambda r:r["game_id"])
    if len(base)!=a.expected_games: raise SystemExit(f"baseline rows {len(base)}")

    groups=defaultdict(list); sigs={}; shard_times=defaultdict(float)
    for fp in glob.glob(a.glob):
        with open(fp,encoding="utf-8") as f:p=json.load(f)
        v=p["variant"]
        groups[v].extend(p["rows"])
        shard_times[v]+=float(p.get("elapsed_seconds",0.0))
        sig=p["compatibility_signature"]
        if v in sigs:
            # compare invariant fields exactly
            if sigs[v]!=sig: raise SystemExit(f"incompatible shards for {v}")
        else:sigs[v]=sig

    missing=[v for v in expected if v not in groups]
    unexpected=[v for v in groups if v not in expected]
    if missing or unexpected: raise SystemExit(f"missing={missing} unexpected={unexpected}")

    results={}; rows_out=[]
    for v in expected:
        vr=groups[v]; vr.sort(key=lambda r:int(r["game_id"]))
        if len(vr)!=a.expected_games: raise SystemExit(f"{v}: expected {a.expected_games}, got {len(vr)}")
        seen=set()
        for x,y in zip(vr,base):
            gid=int(x["game_id"])
            if gid in seen: raise SystemExit(f"{v}: duplicate {gid}")
            seen.add(gid)
            if gid!=y["game_id"] or int(x["seed"])!=y["seed"] or int(x["seat"])!=y["seat"]:
                raise SystemExit(f"{v}: pairing mismatch game {gid}")

        kind=sigs[v]["kind"]
        var_arm=arm(vr); base_arm=arm(base)

        # raw = simulated variant minus exact current baseline
        raw={name:paired_binary(vr,base,name) for name in ("T1","le_T2","le_T3")}
        raw_util=paired_stats(vr,base,lambda r:utility(r["win_turn"]))
        raw_keep=paired_stats(vr,base,lambda r:int(r["keep_n"]))

        # Reported orientation is always "named card/package value":
        # current_vs_generic => current baseline - generic replacement arm
        # prospects/packages => prospect/package arm - current baseline
        sign=-1.0 if kind=="current_vs_generic" else 1.0
        oriented={}
        for name,p in raw.items():
            oriented[name]={
                "delta_pp":sign*p["delta_pp"],
                "ci95_pp":sorted([sign*p["ci95_pp"][0],sign*p["ci95_pp"][1]]),
                "favored_only":p["b_only"] if sign<0 else p["a_only"],
                "reference_only":p["a_only"] if sign<0 else p["b_only"],
                "discordant":p["discordant"],
            }
        oriented_util={
            "delta":sign*raw_util["delta"],
            "ci95":sorted([sign*raw_util["ci95"][0],sign*raw_util["ci95"][1]])
        }
        oriented_keep={
            "delta_cards":sign*raw_keep["delta"],
            "ci95":sorted([sign*raw_keep["ci95"][0],sign*raw_keep["ci95"][1]])
        }

        faster_named=faster_ref=same=0
        for x,y in zip(vr,base):
            vx=int(x["win_turn"]) or 4; by=int(y["win_turn"]) or 4
            # prospect/package named arm = variant; current-card named arm = baseline
            nx,rx=(vx,by) if sign>0 else (by,vx)
            if nx<rx:faster_named+=1
            elif rx<nx:faster_ref+=1
            else:same+=1

        results[v]={
            "kind":kind,"replace":sigs[v]["replace"],
            "simulated_variant_arm":var_arm,"current_baseline_arm":base_arm,
            "reported_orientation":"current-minus-generic" if sign<0 else "variant-minus-current",
            "reported_delta":oriented,
            "reported_utility_delta":oriented_util,
            "reported_mean_keep_delta":oriented_keep,
            "timing":{"named_option_faster":faster_named,"reference_faster":faster_ref,"same":same},
            "sum_variant_shard_seconds":shard_times[v],
            "deck_sha256":sigs[v]["deck_sha256"],
        }
        label=" + ".join(new for old,new in sigs[v]["replace"]) if sign>0 else " + ".join(old for old,new in sigs[v]["replace"])
        reference="current baseline" if sign>0 else "generic replacement"
        rows_out.append({
            "variant":v,"label":label,"kind":kind,"reference":reference,
            "delta_T1_pp":oriented["T1"]["delta_pp"],
            "ci95_T1_lo_pp":oriented["T1"]["ci95_pp"][0],"ci95_T1_hi_pp":oriented["T1"]["ci95_pp"][1],
            "delta_leT2_pp":oriented["le_T2"]["delta_pp"],
            "ci95_leT2_lo_pp":oriented["le_T2"]["ci95_pp"][0],"ci95_leT2_hi_pp":oriented["le_T2"]["ci95_pp"][1],
            "delta_leT3_pp":oriented["le_T3"]["delta_pp"],
            "ci95_leT3_lo_pp":oriented["le_T3"]["ci95_pp"][0],"ci95_leT3_hi_pp":oriented["le_T3"]["ci95_pp"][1],
            "delta_utility":oriented_util["delta"],
            "delta_mean_keep":oriented_keep["delta_cards"],
            "named_option_faster":faster_named,"reference_faster":faster_ref,"same_timing":same,
        })

    payload={
        "design":{
            "paired":True,"n_pairs_per_variant":a.expected_games,
            "baseline":"frozen v0.76 exact current-99 N4096 games restricted to game_id 0..511",
            "same_seed_seat_policy":True,
            "purpose":"natural full-deck revalidation of historical forced-opening acceleration screens",
        },
        "baseline_summary":arm(base),
        "variants":results,
    }
    with open(a.json_out,"w",encoding="utf-8") as f:json.dump(payload,f,indent=2)
    fields=list(rows_out[0].keys())
    with open(a.csv_out,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows_out)
    print(json.dumps({"status":"complete","variants":len(expected),"n_each":a.expected_games,
                      "json_out":a.json_out,"csv_out":a.csv_out},indent=2))

if __name__=="__main__":main()
