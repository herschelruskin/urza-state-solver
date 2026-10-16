#!/usr/bin/env python3
"""Integrity-checked pooled exact Boonweaver T1-T3 rates and matched deltas."""
import argparse
import glob
import gzip
import json
from collections import Counter
from math import sqrt
from pathlib import Path

VARIANTS=("current","oct10")

def wilson(k,n):
    if n==0:return (0.0,1.0)
    z=1.9599639845
    ph=k/n
    den=1+z*z/n
    center=(ph+z*z/(2*n))/den
    half=z*sqrt(ph*(1-ph)/n+z*z/(4*n*n))/den
    return [round(center-half,6),round(center+half,6)]

def pool(paths,expected,beam):
    rows={x:[] for x in VARIANTS}
    hashes={}
    for path in sorted(paths):
        with gzip.open(path,"rt",encoding="utf8") as f:payload=json.load(f)
        assert payload["schema"]=="boonweaver_exact99_t1t3_oct16",(path,payload.get("schema"))
        variant=payload["variant"]
        assert variant in VARIANTS,(path,variant)
        assert payload["games"]==len(payload["rows"])
        assert payload["beam"]==beam,(path,payload["beam"])
        assert payload["policy"]=="free_multiplayer_London_v077_lambda_0.5_continuation_provisional"
        old=hashes.setdefault(variant,payload["deck_sha256"])
        assert old==payload["deck_sha256"],(variant,old,payload["deck_sha256"])
        counted=Counter(int(x["win_turn"]) for x in payload["rows"])
        assert counted==Counter({int(k):int(v) for k,v in payload["counts"].items()})
        for row in payload["rows"]:
            gid=int(row["game_id"])
            assert row["seed"]==payload["seed_base"]+gid*1000003
            assert int(row["win_turn"]) in (0,1,2,3)
            assert 1<=int(row["keep_n"])<=7
        rows[variant].extend(payload["rows"])
    assert len(hashes)==2,("missing variants",hashes)
    for variant,rr in rows.items():
        ids=[int(x["game_id"]) for x in rr]
        assert len(rr)==expected,(variant,len(rr),expected)
        assert len(set(ids))==expected,(variant,"duplicate IDs")
        assert sorted(ids)==list(range(expected)),(variant,"missing IDs")
    def summary(rr):
        c=Counter(x["win_turn"] for x in rr)
        n=len(rr)
        exact={f"T{k}":c[k]/n for k in (1,2,3)}
        cumul={}
        ci={}
        for t in (1,2,3):
            count=sum(c[k] for k in range(1,t+1))
            cumul[f"by_T{t}"]=round(100*count/n,4)
            ci[f"by_T{t}_Wilson95pct"]=[round(100*v,3) for v in wilson(count,n)]
        return {"n":n,"counts":{str(k):c[k] for k in range(4)},
                "exact_pct":{k:round(100*v,4) for k,v in exact.items()},
                "cumulative_pct":cumul,"ci_pct":ci,
                "mean_keep":round(sum(x["keep_n"] for x in rr)/n,4),
                "free_mull_fraction":round(sum(x["free_mull_used"] for x in rr)/n,5)}
    report={v:summary(rows[v]) for v in VARIANTS}
    cur={int(r["game_id"]):r for r in rows["current"]}
    old={int(r["game_id"]):r for r in rows["oct10"]}
    delta={}
    for t in (1,2,3):
        indicators=[(int(cur[i]["win_turn"] in range(1,t+1))
                     -int(old[i]["win_turn"] in range(1,t+1)))
                    for i in range(expected)]
        mean=sum(indicators)/expected
        variance=(sum((z-mean)**2 for z in indicators)/(expected-1)
                  if expected>1 else 0.0)
        se=sqrt(variance/expected)
        delta[f"by_T{t}_pctpoints"]={
            "delta":round(100*mean,4),
            "paired_normal_95pct":[round(100*(mean-1.96*se),3),
                                   round(100*(mean+1.96*se),3)]}
    return {"status":"PASS","n_per_variant":expected,"beam":beam,
            "decks_sha256":hashes,"variants":report,
            "paired_current_minus_oct10":delta,
            "caveats":["Goldfish Dack deployment only; no opponent interaction",
                       "Three creature combo pieces mandatory in library",
                       "4-player free mulligan, but continuation values from older non-free benchmark",
                       "Smothering Tithe modeled as 3 treasures per opponent cycle",
                       "No exact post-Dack Boonweaver aura/trigger combo proof",
                       "Approximate paired normal intervals ignore solver/model misspecification"]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--glob",default="shards/*.json.gz")
    p.add_argument("--expected",type=int,default=1024)
    p.add_argument("--beam",type=int,default=240)
    p.add_argument("--out",default="boonweaver_exact99_pooled_20261016.json")
    p.add_argument("--selftest",action="store_true")
    args=p.parse_args()
    if args.selftest:
        assert wilson(0,10)[0]>=0 and wilson(10,10)[1]<=1.000001
        print("BOONWEAVER_POOL_SELFTEST_PASS",flush=True)
        return
    paths=glob.glob(args.glob,recursive=True)
    assert paths,("No shard data",args.glob)
    report=pool(paths,args.expected,args.beam)
    Path(args.out).write_text(json.dumps(report,indent=2),encoding="utf8")
    print("BOONWEAVER_POOLED_PASS "+json.dumps(report),flush=True)

if __name__=="__main__":main()
