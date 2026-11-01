#!/usr/bin/env python3
"""Matched N128 original-v5 vs frozen v27 and coupled maxQ2.
Already-inspected 151k experimental cohort: NOT a new sealed holdout.
"""
import glob,gzip,json,random
from pathlib import Path
N=128
def by(t,h):return int(0<int(t)<=h)
def run():
    files=sorted(glob.glob("collected/v43_original_v5_151k_*.json.gz"))
    assert len(files)==8
    v5={}
    for file in files:
        with gzip.open(file,"rt") as f:q=json.load(f)
        assert q["schema"]=="dack_v43_same_151k_original_v5_reference_N128_shard"
        assert q["status"]=="PASS" and q["original_v5_with_no_modifications"]
        for r in q["rows"]:
            assert r["game_id"] not in v5
            v5[r["game_id"]]=r
    assert set(v5)==set(range(151000,151128))
    m={}
    paths=sorted(glob.glob("benchmark_results/v43_fresh_151k_maxQ2_shards/v43_151k_*.json.gz"))
    assert len(paths)==8
    for file in paths:
        with gzip.open(file,"rt") as f:q=json.load(f)
        assert q["status"]=="PASS" and q["schema"]=="dack_v43_fresh_151k_v27_vs_maxQ2_N256_paired_shard"
        for r in q["rows"]:
            if r["gid"] in v5:
                assert r["gid"] not in m
                m[r["gid"]]=r
    assert set(m)==set(v5)
    rows=[]
    for gid in sorted(v5):
        old=v5[gid];other=m[gid]
        assert old["seat"]==other["v27"]["seat"]==other["maxQ2"]["seat"]
        assert old["history"][0]["seven_slots"]==other["v27"]["history"][0]["seven_slots"]==other["maxQ2"]["history"][0]["seven_slots"]
        rows.append({
          "gid":gid,"v5":old["turn"],"v27":other["v27"]["turn"],"maxQ2":other["maxQ2"]["turn"],
          "v5_keep_n":old["keep_n"],"maxQ2_keep_n":other["maxQ2"]["keep_n"],
        })
    rates={p:{f"T{h}":sum(by(r[p],h) for r in rows) for h in (1,2,3)}
           for p in ("v5","v27","maxQ2")}
    pair={}
    for pol in ("v27","maxQ2"):
        for h in (1,2,3):
            ds=[by(r[pol],h)-by(r["v5"],h) for r in rows]
            rng=random.Random(151128+h+sum(map(ord,pol)))
            boot=sorted(100*sum(ds[rng.randrange(N)] for _ in range(N))/N for _ in range(9000))
            pair[f"{pol}_minus_v5_T{h}"]={
               "delta_pp":100*sum(ds)/N,
               "net_games":sum(ds),"gains":ds.count(1),"losses":ds.count(-1),
               "paired_95ci_pp":[boot[224],boot[8774]],
            }
    out={
     "schema":"dack_v43_original_v5_vs_v27_maxQ2_matched_151k_retro_N128",
     "status":"PASS","N":N,"same_physical_99_and_stable_dice":True,
     "already_inspected_151k_not_fresh_acceptance":True,
     "original_v5_engine_unmodified":True,
     "outcome_goldfish_dack_deployment_not_multiplayer_wr":True,
     "counts":rates,"paired":pair,
    }
    p=Path("benchmark_results/v43_v5_vs_maxQ2_on_151k_retro_N128.json")
    p.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print("DACK_V43_ORIGINAL_V5_MATCHED_N128_RETROSPECTIVE_PASS",json.dumps(out,sort_keys=True),flush=True)
if __name__=="__main__":run()
