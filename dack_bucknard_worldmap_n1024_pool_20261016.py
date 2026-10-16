#!/usr/bin/env python3
"""Confirm the exact Oct 16 World Map -> Bucknard swap using 1,024 paired games.

Replicates only the second 512 games (IDs 512..1023) and reuses the independently
audited first 512 from run 38931616641. Reuse the 1,024 baseline from
run 38912678782. All shards are SHA/seed/card/range checked.

The counterfactual is a single-card swap, not an absolute T2 win-rate promise.
"""
from __future__ import annotations
import argparse, glob, gzip, json, math
from collections import Counter
from pathlib import Path

BASE_SHA="3a10a02e1aae070645129fa85ed94240f1ae9d5447e3711f7621f92064d9f129"
BUCK_SHA="f130ff4c9c0fbc888525070877fe820caba03e836e0be66ec60ea3410e950068"
SEED_BASE=7604096001
N=1024
EXPECTED_BEAM=240

def collect(glob_pattern,variant,expected_sha,ids):
    paths=sorted(glob.glob(glob_pattern,recursive=True))
    assert paths,(glob_pattern,"no artifact files")
    records={}
    hashes=set()
    for path in paths:
        with gzip.open(path,"rt",encoding="utf8") as f:
            payload=json.load(f)
        assert payload["variant"]==variant,(path,payload["variant"],variant)
        assert payload["beam"]==EXPECTED_BEAM,(path,payload["beam"])
        assert payload["seed_base"]==SEED_BASE,(path,payload["seed_base"])
        assert payload["games"]==len(payload["rows"]),(path,"incomplete")
        counts=Counter(int(r["win_turn"]) for r in payload["rows"])
        assert counts==Counter({int(k):v for k,v in payload["counts"].items()}),(path,"counts")
        hashes.add(payload["deck_sha256"])
        for r in payload["rows"]:
            gid=int(r["game_id"])
            assert gid==payload["shard"]*payload["games"]+list_position(r,payload["rows"]), (path,gid,"shard mapping")
            assert r["seed"]==SEED_BASE+gid*1000003,(path,gid,"seed")
            assert 0<=r["win_turn"]<=3,(path,gid,"turn")
            assert 1<=r["keep_n"]<=7,(path,gid,"mulligan")
            if gid in ids:
                assert gid not in records,(path,gid,"duplicate")
                records[gid]=r
    assert hashes=={expected_sha},(variant,hashes,expected_sha)
    assert set(records)==set(ids),(variant,"missing",sorted(set(ids)-set(records))[:5])
    return records, len(paths)

def list_position(row,rows):
    # Identity is unique in each shard; only used during integrity checks.
    return next(i for i,r in enumerate(rows) if r is row)

def wilson(k,n):
    z=1.9599639845
    p=k/n
    center=(p+z*z/(2*n))/(1+z*z/n)
    hw=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
    return [round((center-hw)*100,3),round((center+hw)*100,3)]

def describe(records):
    n=len(records);c=Counter(int(q["win_turn"]) for q in records.values())
    by={f"by_T{t}":sum(c[i] for i in range(1,t+1)) for t in (1,2,3)}
    return {"n":n,"counts":{str(i):c[i] for i in range(4)},
            "cumulative_pct":{k:round(100*v/n,4) for k,v in by.items()},
            "wilson95_pct":{k:wilson(v,n) for k,v in by.items()},
            "mean_keep":round(sum(q["keep_n"] for q in records.values())/n,4)}

def exact_binom_two_sided(better,worse):
    # Exact McNemar/binomial discordant-pair two-sided p, not normal approx.
    n=better+worse
    if n==0:return 1.0
    tail=sum(math.comb(n,i) for i in range(min(better,worse)+1))
    return min(1.,2*tail/(2**n))

def paired(buck,base):
    assert set(buck)==set(base)
    n=len(buck)
    rows={}
    for t in (1,2,3):
        dif=[int(0<buck[i]["win_turn"]<=t)-int(0<base[i]["win_turn"]<=t)
             for i in sorted(base)]
        gain=sum(d==1 for d in dif);loss=sum(d==-1 for d in dif)
        mean=sum(dif)/n
        var=sum((d-mean)**2 for d in dif)/(n-1)
        se=math.sqrt(var/n)
        rows[f"by_T{t}"]={
            "change_pp":round(100*mean,4),
            "paired_normal_95pct_pp":[round(100*(mean-1.96*se),3),
                                       round(100*(mean+1.96*se),3)],
            "buck_only":gain,
            "baseline_only":loss,
            "both_or_neither":n-gain-loss,
            "mcnemar_exact_two_sided_p":round(exact_binom_two_sided(gain,loss),6)
        }
    transition={}
    for i in sorted(base):
        key=f'{base[i]["win_turn"]}->{buck[i]["win_turn"]}'
        transition[key]=transition.get(key,0)+1
    return {"at_or_before_turn":rows,
            "individual_turn_transitions":dict(sorted(transition.items()))}

def selftest():
    assert exact_binom_two_sided(4,0)==0.125
    assert exact_binom_two_sided(0,0)==1.0
    assert exact_binom_two_sided(5,5)==1.0
    assert wilson(0,10)[0]==0.
    b={i:{"win_turn":1 if i<2 else 0,"keep_n":7} for i in range(4)}
    a={i:{"win_turn":1 if i<3 else 0,"keep_n":7} for i in range(4)}
    assert paired(a,b)["at_or_before_turn"]["by_T1"]["buck_only"]==1
    print("BUCKNARD_N1024_POOLER_SELFTEST_PASS",flush=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--selftest",action="store_true")
    ap.add_argument("--baseline",default="baseline/**/*.json.gz")
    ap.add_argument("--first-half",default="old_buck/**/*.json.gz")
    ap.add_argument("--second-half",default="new_buck/**/*.json.gz")
    ap.add_argument("--out",default="bucknard_worldmap_n1024_confirmed.json")
    args=ap.parse_args()
    if args.selftest:
        selftest();return
    first_ids=set(range(512))
    second_ids=set(range(512,1024))
    baseline,base_n=collect(args.baseline,"current",BASE_SHA,first_ids|second_ids)
    first,first_n=collect(args.first_half,"buck_worldmap",BUCK_SHA,first_ids)
    second,second_n=collect(args.second_half,"buck_worldmap",BUCK_SHA,second_ids)
    combined={**first,**second}
    assert len(combined)==N and set(combined)==set(range(N))
    # Compare to a previously independently published baseline summary.
    assert Counter(q["win_turn"] for q in baseline.values())==Counter({0:157,1:50,2:405,3:412}),"baseline drift"
    out={
        "status":"PASS",
        "design":"Exact one-card swap World Map -> Bucknard's Everfull Purse",
        "n_paired_games":N,"beam":EXPECTED_BEAM,
        "deck_hashes":{"baseline":BASE_SHA,"bucknard":BUCK_SHA},
        "sources":{"baseline_run":38912678782,
                   "bucknard_first512_run":38931616641,
                   "bucknard_second512_run":"this workflow"},
        "shards_audited":{"baseline":base_n,"first_512":first_n,"second_512":second_n},
        "full":{
            "baseline":describe(baseline),
            "bucknard":describe(combined),
            "paired_bucknard_minus_baseline":paired(combined,baseline)},
        "first_512":{
            "baseline":describe({i:baseline[i] for i in first_ids}),
            "bucknard":describe(first),
            "paired_bucknard_minus_baseline":paired(first,{i:baseline[i] for i in first_ids})},
        "second_512":{
            "baseline":describe({i:baseline[i] for i in second_ids}),
            "bucknard":describe(second),
            "paired_bucknard_minus_baseline":paired(second,{i:baseline[i] for i in second_ids})},
        "caveats":[
            "Goldfish Dack deployment with 3 combo creatures remaining in library, not live-game win rate",
            "Search beam width 240 and provisional older mulligan continuation thresholds",
            "Bucknard modeled as {1}, tap, roll d4, make resulting Treasures and transfer control",
            "KCI may sacrifice Bucknard while the activated ability is on stack",
            "Random roll is deterministic by game/solver state; matches prior validated runner",
            "MTG combat/interaction and post-Dack Boonweaver combo not simulated",
            "No independent engine replication; paired CI conditional on solver accuracy"
        ]}
    Path(args.out).write_text(json.dumps(out,indent=2)+"\n",encoding="utf8")
    print("BUCKNARD_N1024_CONFIRMED_POOL_PASS",flush=True)
    for name,z in (("FULL",out["full"]),("FIRST512",out["first_512"]),("SECOND512",out["second_512"])):
        print(name,json.dumps({"baseline":z["baseline"]["cumulative_pct"],
                "bucknard":z["bucknard"]["cumulative_pct"],
                "delta":z["paired_bucknard_minus_baseline"]["at_or_before_turn"]}),flush=True)

if __name__=="__main__":
    main()
