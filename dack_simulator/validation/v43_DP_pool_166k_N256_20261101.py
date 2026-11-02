#!/usr/bin/env python3
"""Pool exactly 8 N32 independent 166k physical shards; paired outer-deal CI.

FROZEN before 166k outcome access. Research candidate promotion gate is:
byT2 two-sided 95% paired bootstrap lower >0; no T1 decline worse than
2 percentage points; no T3 decline worse than 3 percentage points;
runtime <= 1.25x. Passing is not automatic promotion.
"""
from __future__ import annotations
import argparse,gzip,json,random,statistics
from pathlib import Path
START=166000;N=256
def metric(rows,stage):
    delta=[int(0<r["dp"]["turn"]<=stage)-int(0<r["v43"]["turn"]<=stage) for r in rows]
    rng=random.Random(166043+stage)
    boot=[]
    for _ in range(8000):
        boot.append(100*sum(delta[rng.randrange(N)] for __ in range(N))/N)
    boot.sort()
    return {"v43":sum(0<r["v43"]["turn"]<=stage for r in rows),
         "dp":sum(0<r["dp"]["turn"]<=stage for r in rows),
         "dp_only":delta.count(1),"v43_only":delta.count(-1),
         "delta_pp":round(100*sum(delta)/N,5),
         "paired_95_bootstrap_pp":[boot[199],boot[7799]]}
def pool(folder,out):
    shards=sorted(Path(folder).glob("v43dp_166*.json.gz"))
    assert len(shards)==8,("need exact 8",len(shards),list(map(str,shards)))
    rows=[];shas=set()
    for p in shards:
        with gzip.open(p,"rt") as f:r=json.load(f)
        assert r["status"]=="PASS" and r["N_independent_outer_deals"]==32
        assert r["schema"]=="dack_v43_policy_consistent_DP_vs_frozen_v43_matched_goldfish_166k_n32_v1"
        rows+=r["rows"];shas.add(r["dp_research_json_sha256"])
    assert len(shas)==1
    assert [x["gid"] for x in sorted(rows,key=lambda a:a["gid"])]==list(range(START,START+N))
    rows.sort(key=lambda x:x["gid"])
    assert all(x["dp"]["history"][0]["seven"]==x["v43"]["history"][0]["seven"] for x in rows)
    score={str(k):metric(rows,k) for k in (1,2,3)}
    same=sum((r["dp"]["hand"],r["dp"]["keep_n"],r["dp"]["bottom"])==
             (r["v43"]["hand"],r["v43"]["keep_n"],r["v43"]["bottom"]) for r in rows)
    for x in rows:
        if (x["dp"]["hand"],x["dp"]["keep_n"],x["dp"]["bottom"]) == (x["v43"]["hand"],x["v43"]["keep_n"],x["v43"]["bottom"]):
            assert x["dp"]["turn"]==x["v43"]["turn"]
    t0=sum(r["v43"]["elapsed"] for r in rows);t1=sum(r["dp"]["elapsed"] for r in rows)
    # No application-level speedup claim if per-child Python import dominates.
    ratio=t1/t0
    gate={"predeclared_byT2_bootstrap_lower_positive":score["2"]["paired_95_bootstrap_pp"][0]>0,
       "T1_decline_not_more_than_2pp":score["1"]["delta_pp"]>=-2,
       "T3_decline_not_more_than_3pp":score["3"]["delta_pp"]>=-3,
       "runtime_ratio_le_1point25":ratio<=1.25}
    result={"schema":"dack_v43_model_only_dp_fresh_166k_N256_paired_v1",
      "status":"PASS","N_independent_physical_games":N,"gid_range":[START,START+N-1],
      "tested_candidate":"frozen_v43_Q2_and_bottoms_with_policy_consistent_MODEL_ONLY_DP",
      "full_game_strict_goldfish_beam160":True,
      "no_155k_access":True,"no_165k_access":True,"no_new_model_training":True,
      "confidence_unit":"outer full99 physical source deal, not sampled futures",
      "frozen_baseline":"v43","dp_source_1024":[163700,164723],
      "source_model_sha256":next(iter(shas)),
      "by_turn":score,
      "same_final_hand_and_bottom_exact_terminal_parity":same,
      "changed_final_hand_or_bottom":N-same,
      "mean_keep_v43":statistics.mean(r["v43"]["keep_n"] for r in rows),
      "mean_keep_dp":statistics.mean(r["dp"]["keep_n"] for r in rows),
      "elapsed_seconds_sum_v43_child":t0,"elapsed_seconds_sum_dp_child":t1,
      "runtime_ratio_dp_div_v43":ratio,
      "gate":gate,"all_predeclared_gates_met":all(gate.values()),
      "promotion_requires_independent_review":True,
      "rows":rows}
    dest=Path(out);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print("DACK_V43_DP_FRESH_166K_N256_PASS",json.dumps({k:result[k] for k in (
       "N_independent_physical_games","by_turn","same_final_hand_and_bottom_exact_terminal_parity",
       "mean_keep_v43","mean_keep_dp","runtime_ratio_dp_div_v43","gate",
       "all_predeclared_gates_met")},sort_keys=True),flush=True)
    return result
if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument("--folder",required=True);a.add_argument("--out",required=True)
    z=a.parse_args();pool(z.folder,z.out)
