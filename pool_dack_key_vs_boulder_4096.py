#!/usr/bin/env python3
"""Pool the exact paired N=4096 Manifold Key vs Giant's Boulder comparison."""
import argparse, csv, glob, json, math
from collections import Counter

Z=1.959963984540054

def wilson(k,n,z=Z):
    if not n: return [0.0,0.0]
    p=k/n
    den=1+z*z/n
    ctr=(p+z*z/(2*n))/den
    half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [ctr-half,ctr+half]

def rate_block(k,n):
    return {
        "count":int(k),"n":int(n),
        "rate":k/n if n else None,
        "pct":100*k/n if n else None,
        "ci95":wilson(k,n) if n else None,
    }

def arm_summary(rows):
    n=len(rows)
    c=Counter(int(r["win_turn"]) for r in rows)
    t1,t2,t3,fail=c[1],c[2],c[3],c[0]
    le2=t1+t2; le3=le2+t3
    keeps=[int(r["keep_n"]) for r in rows]
    return {
        "n":n,
        "T1":rate_block(t1,n),
        "T2_exact":rate_block(t2,n),
        "le_T2":rate_block(le2,n),
        "T3_exact":rate_block(t3,n),
        "le_T3":rate_block(le3,n),
        "fail_T3":rate_block(fail,n),
        "utility_lambda_0_5":(le2+0.5*t3)/n,
        "mean_keep":sum(keeps)/n,
        "keep_counts":{str(k):sum(x==k for x in keeps) for k in range(7,0,-1)},
    }

def endpoint(win,which):
    w=int(win)
    if which=="T1": return int(w==1)
    if which=="le_T2": return int(w in (1,2))
    if which=="le_T3": return int(w in (1,2,3))
    raise ValueError(which)

def paired_binary(key_rows,base_rows,which):
    diffs=[]
    key_only=base_only=both=neither=0
    for kr,br in zip(key_rows,base_rows):
        k=endpoint(kr["win_turn"],which)
        b=endpoint(br["win_turn"],which)
        diffs.append(k-b)
        if k and b: both+=1
        elif k: key_only+=1
        elif b: base_only+=1
        else: neither+=1
    n=len(diffs)
    delta=sum(diffs)/n
    if n>1:
        var=sum((x-delta)**2 for x in diffs)/(n-1)
        se=math.sqrt(var/n)
    else:
        se=0.0
    return {
        "endpoint":which,
        "key_minus_boulder_rate":delta,
        "key_minus_boulder_pp":100*delta,
        "paired_se":se,
        "paired_ci95_rate":[delta-Z*se,delta+Z*se],
        "paired_ci95_pp":[100*(delta-Z*se),100*(delta+Z*se)],
        "key_only_success":key_only,
        "boulder_only_success":base_only,
        "both_success":both,
        "neither_success":neither,
        "discordant_pairs":key_only+base_only,
        "agreement_rate":(both+neither)/n,
    }

def paired_mean_delta(key_vals,base_vals):
    diffs=[float(k)-float(b) for k,b in zip(key_vals,base_vals)]
    n=len(diffs); delta=sum(diffs)/n
    var=sum((x-delta)**2 for x in diffs)/(n-1) if n>1 else 0.0
    se=math.sqrt(var/n) if n else 0.0
    return {
        "mean_delta":delta,
        "se":se,
        "ci95":[delta-Z*se,delta+Z*se],
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--glob",required=True)
    ap.add_argument("--expected-games",type=int,default=4096)
    ap.add_argument("--baseline-games",required=True)
    ap.add_argument("--baseline-summary",required=True)
    ap.add_argument("--json-out",required=True)
    ap.add_argument("--pairs-csv",required=True)
    a=ap.parse_args()

    files=sorted(glob.glob(a.glob))
    if not files:
        raise SystemExit("no Key shards found")

    key_rows=[]; sig=None; seen=set(); shard_times=[]
    for fp in files:
        with open(fp,encoding="utf-8") as f:
            p=json.load(f)
        if sig is None: sig=p["compatibility_signature"]
        if p["compatibility_signature"]!=sig:
            raise SystemExit(f"incompatible Key shard: {fp}")
        shard_times.append(float(p.get("elapsed_seconds",0.0)))
        for r in p["rows"]:
            gid=int(r["game_id"])
            if gid in seen: raise SystemExit(f"duplicate Key game_id {gid}")
            seen.add(gid); key_rows.append(r)
    key_rows.sort(key=lambda r:int(r["game_id"]))

    base_rows=[]
    with open(a.baseline_games,newline="",encoding="utf-8") as f:
        for r in csv.DictReader(f):
            base_rows.append({
                "game_id":int(r["game_id"]),
                "seed":int(r["seed"]),
                "seat":int(r["seat"]),
                "keep_n":int(r["keep_n"]),
                "mulligans":int(r["mulligans"]),
                "keep_utility":float(r["keep_utility"]),
                "win_turn":int(r["win_turn"]),
                "kept_hand":r["kept_hand"],
                "bottomed_cards":r["bottomed_cards"],
            })
    base_rows.sort(key=lambda r:r["game_id"])

    n=len(key_rows)
    if n!=a.expected_games or len(base_rows)!=a.expected_games:
        raise SystemExit(f"expected {a.expected_games} paired games, got Key={n}, Boulder={len(base_rows)}")

    with open(a.baseline_summary,encoding="utf-8") as f:
        base_summary_json=json.load(f)
    if sig["boulder_deck_sha256"]!=base_summary_json["compatibility_signature"]["deck_sha256"]:
        raise SystemExit("Boulder deck hash does not match frozen baseline")
    if int(sig["seed_base"])!=int(base_summary_json["compatibility_signature"]["seed_base"]):
        raise SystemExit("seed base mismatch")

    for kr,br in zip(key_rows,base_rows):
        gid=int(kr["game_id"])
        if gid!=int(br["game_id"]): raise SystemExit(f"game_id mismatch at {gid}")
        if int(kr["seed"])!=int(br["seed"]): raise SystemExit(f"seed mismatch at {gid}")
        if int(kr["seat"])!=int(br["seat"]): raise SystemExit(f"seat mismatch at {gid}")

    key_sum=arm_summary(key_rows)
    base_sum=arm_summary(base_rows)

    paired={
        x:paired_binary(key_rows,base_rows,x)
        for x in ("T1","le_T2","le_T3")
    }

    # Earlier win is better; encode T1=1,T2=2,T3=3,fail=4.
    key_faster=base_faster=same=0
    for kr,br in zip(key_rows,base_rows):
        kw=int(kr["win_turn"]) or 4
        bw=int(br["win_turn"]) or 4
        if kw<bw:key_faster+=1
        elif bw<kw:base_faster+=1
        else:same+=1

    utility_key=[endpoint(r["win_turn"],"le_T2")+0.5*int(int(r["win_turn"])==3) for r in key_rows]
    utility_base=[endpoint(r["win_turn"],"le_T2")+0.5*int(int(r["win_turn"])==3) for r in base_rows]

    out={
        "comparison":"Manifold Key vs Giant's Boulder",
        "design":{
            "paired":True,
            "n_pairs":n,
            "one_card_change":"Giant's Boulder -> Manifold Key",
            "same_game_ids":True,
            "same_seeds":True,
            "same_seats":True,
            "same_mulligan_policy":True,
            "same_gameplay_beam":True,
            "same_max_turn":True,
            "boulder_baseline_reused":True,
            "compatibility_signature_key":sig,
        },
        "arms":{
            "Manifold Key":key_sum,
            "Giant's Boulder":base_sum,
        },
        "paired_deltas_key_minus_boulder":paired,
        "utility_lambda_0_5_delta":paired_mean_delta(utility_key,utility_base),
        "mean_keep_delta":paired_mean_delta(
            [r["keep_n"] for r in key_rows],[r["keep_n"] for r in base_rows]),
        "win_timing_pairs":{
            "key_faster":key_faster,
            "boulder_faster":base_faster,
            "same_timing":same,
            "key_faster_pct":100*key_faster/n,
            "boulder_faster_pct":100*base_faster/n,
            "same_timing_pct":100*same/n,
        },
        "runtime":{
            "key_shards":len(files),
            "sum_key_shard_seconds":sum(shard_times),
            "mean_key_shard_seconds":sum(shard_times)/len(shard_times),
            "max_key_shard_seconds":max(shard_times),
        },
    }

    with open(a.json_out,"w",encoding="utf-8") as f:
        json.dump(out,f,indent=2)

    fields=[
        "game_id","seed","seat",
        "boulder_win_turn","key_win_turn",
        "boulder_keep_n","key_keep_n",
        "boulder_keep_utility","key_keep_utility",
        "T1_delta_key_minus_boulder",
        "le_T2_delta_key_minus_boulder",
        "le_T3_delta_key_minus_boulder",
    ]
    with open(a.pairs_csv,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
        for kr,br in zip(key_rows,base_rows):
            w.writerow({
                "game_id":kr["game_id"],"seed":kr["seed"],"seat":kr["seat"],
                "boulder_win_turn":br["win_turn"],"key_win_turn":kr["win_turn"],
                "boulder_keep_n":br["keep_n"],"key_keep_n":kr["keep_n"],
                "boulder_keep_utility":br["keep_utility"],"key_keep_utility":kr["keep_utility"],
                "T1_delta_key_minus_boulder":endpoint(kr["win_turn"],"T1")-endpoint(br["win_turn"],"T1"),
                "le_T2_delta_key_minus_boulder":endpoint(kr["win_turn"],"le_T2")-endpoint(br["win_turn"],"le_T2"),
                "le_T3_delta_key_minus_boulder":endpoint(kr["win_turn"],"le_T3")-endpoint(br["win_turn"],"le_T3"),
            })

    print(json.dumps({
        "status":"complete",
        "n_pairs":n,
        "key_T1":key_sum["T1"]["rate"],
        "boulder_T1":base_sum["T1"]["rate"],
        "key_le_T2":key_sum["le_T2"]["rate"],
        "boulder_le_T2":base_sum["le_T2"]["rate"],
        "key_le_T3":key_sum["le_T3"]["rate"],
        "boulder_le_T3":base_sum["le_T3"]["rate"],
        "delta_pp":{k:v["key_minus_boulder_pp"] for k,v in paired.items()},
    },indent=2))

if __name__=="__main__":
    main()
