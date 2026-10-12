#!/usr/bin/env python3
"""Pool strictly matched Dack flicker T1-T3 shards; reject mixed/incomplete data."""
from __future__ import annotations
import argparse
from collections import Counter
import glob, gzip, json, math, tempfile
from pathlib import Path

def wilson(k,n,z=1.959963984540054):
    if not n:return [0.0,1.0]
    p=k/n;zz=z*z
    center=(p+zz/(2*n))/(1+zz/n)
    half=z*math.sqrt(p*(1-p)/n+zz/(4*n*n))/(1+zz/n)
    return [max(0,center-half),min(1,center+half)]

def read_shard(path):
    with gzip.open(path,"rt",encoding="utf8") as f:
        return json.load(f)

def pool(files,expected_n,expected_variant=None):
    if not files:raise ValueError("No shard files")
    all_rows=[]; signatures=set(); shards={}; deck_shas=set()
    for path in sorted(files):
        dat=read_shard(path)
        if dat.get("schema")!="dack_flicker_t1t3_deployment_v078":
            raise ValueError(f"Wrong schema: {path}")
        variant=dat["variant"]
        if expected_variant is not None and variant!=expected_variant:
            raise ValueError(f"Mixed variant: {path}")
        signature=(variant,dat["deck_sha256"],dat["seed_base"],
                   dat["beam"],dat["mulligan_policy"],
                   dat.get("seed_scheme"),dat.get("objective"))
        signatures.add(signature)
        deck_shas.add(dat["deck_sha256"])
        rows=dat["rows"]
        if dat["games"]!=len(rows):
            raise ValueError(f"Wrong row count: {path}")
        shard=int(dat["shard"])
        if shard in shards:
            raise ValueError(f"Repeated shard id: {shard}")
        shards[shard]=path
        start=shard*dat["games"]
        if [z["game_id"] for z in rows]!=list(range(start,start+len(rows))):
            raise ValueError(f"Shard has missing/reordered IDs: {path}")
        counts=Counter(str(z["win_turn"]) for z in rows)
        if counts!=Counter(dat["counts"]):
            raise ValueError(f"Count mismatch: {path}")
        all_rows.extend(rows)
    if len(signatures)!=1 or len(deck_shas)!=1:
        raise ValueError("Mixed deck hash, beam, policy, seed or objective")
    if len(all_rows)!=expected_n:
        raise ValueError(f"Expected {expected_n}, found {len(all_rows)}")
    ids=[int(r["game_id"]) for r in all_rows]
    if len(set(ids))!=expected_n or sorted(ids)!=list(range(expected_n)):
        raise ValueError("Duplicate or missing game IDs")
    variant,deck_sha,seed_base,beam,policy,seed_scheme,objective=next(iter(signatures))
    for r in all_rows:
        if int(r["seed"])!=int(seed_base)+int(r["game_id"])*1000003:
            raise ValueError(f"Seed mismatch for game {r['game_id']}")
        if r["win_turn"] not in (0,1,2,3):
            raise ValueError(f"Invalid cast turn for game {r['game_id']}")
    counts=Counter(r["win_turn"] for r in all_rows)
    outcomes={}
    for name,k in [("T1_exact",counts[1]),
                   ("T2_exact",counts[2]),
                   ("T3_exact",counts[3]),
                   ("T2_cumulative",counts[1]+counts[2]),
                   ("T3_cumulative",counts[1]+counts[2]+counts[3]),
                   ("no_cast_T3",counts[0])]:
        outcomes[name]={"count":k,"rate":k/expected_n,
                        "wilson95":wilson(k,expected_n)}
    return {
        "schema":"dack_flicker_t1t3_pooled_v1",
        "objective":objective,
        "variant":variant,"n":expected_n,"n_shards":len(shards),
        "deck_sha256":deck_sha,"beam":beam,"seed_base":seed_base,
        "seed_scheme":seed_scheme,"mulligan_policy":policy,
        "outcomes":outcomes,
        "keep_hand_sizes":dict(sorted(Counter(r["keep_n"] for r in all_rows).items(),reverse=True)),
        "starting_seats":dict(sorted(Counter(r["seat"] for r in all_rows).items())),
        "notes":["Marginal estimates from 1024 four-player-seat-seeded goldfish games.",
                 "Dack cast counts as a goldfish win when the provisional combo-hand condition holds; not 4-player match wins.",
                 "Abdel + Radiant Solar simultaneously in hand blocks the provisional assumed-win Dack cast.",
                 "Opponent-facing interaction absent; Smothering Tithe assumes 3 treasures/cycle.",
                 "Old London continuation values are retained for paired comparisons."]
    }

def selftest():
    with tempfile.TemporaryDirectory() as td:
        paths=[]
        for shard in range(2):
            rows=[]
            for k in range(2):
                gid=shard*2+k
                rows.append(dict(game_id=gid,seed=123+gid*1000003,
                                 seat=gid%4,keep_n=7,win_turn=gid%4))
            payload={
                "schema":"dack_flicker_t1t3_deployment_v078",
                "objective":"Dack early cast test","variant":"baseline",
                "deck_sha256":"test123","seed_base":123,"beam":240,
                "mulligan_policy":"test_policy",
                "seed_scheme":"seed_base + game_id * 1000003",
                "shard":shard,"games":2,"counts":dict(Counter(str(x["win_turn"]) for x in rows)),
                "rows":rows
            }
            path=Path(td)/f"shard{shard}.json.gz"
            with gzip.open(path,"wt",encoding="utf8") as f:json.dump(payload,f)
            paths.append(str(path))
        res=pool(paths,4,"baseline")
        assert res["n"]==4 and res["outcomes"]["T3_cumulative"]["count"]==3
        for subset,n in [(paths[:1],4),(paths,8)]:
            try:pool(subset,n)
            except ValueError:pass
            else:raise AssertionError("Incomplete input accepted")
        try:pool(paths+[paths[0]],4)
        except ValueError:pass
        else:raise AssertionError("Duplicate shard accepted")
    print("DACK_FLICKER_POOL_SELFTEST_PASS",flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--selftest",action="store_true")
    p.add_argument("--glob",default="shards/**/*.json.gz")
    p.add_argument("--expected",type=int,default=1024)
    p.add_argument("--variant",default=None)
    p.add_argument("--out",default="dack_flicker_pooled_report.json")
    args=p.parse_args()
    if args.selftest:selftest();return
    result=pool(glob.glob(args.glob,recursive=True),args.expected,args.variant)
    Path(args.out).write_text(json.dumps(result,indent=2)+"\n",encoding="utf8")
    print(json.dumps({"status":"complete","variant":result["variant"],
                      "n":result["n"],"outcomes":result["outcomes"]}),flush=True)

if __name__=="__main__":
    main()
