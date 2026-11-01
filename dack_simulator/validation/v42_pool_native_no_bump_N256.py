#!/usr/bin/env python3
"""Pool full N256 original-v5 no-assertive-bump physical replay.

Shards must each prove original-v5 historical outcome PARITY before any
no-bump comparisons are considered. Same original v5 bottom evaluator,
same physical hands / hidden draws / gameplay, only the KEEP threshold changes.
Paired N256 is a *reused* historical evaluation cohort, not prospective
model acceptance.
"""
from __future__ import annotations
import argparse,glob,gzip,json,random
from pathlib import Path
from collections import Counter
SCHEMA="dack_v42_native_without_assertive_bump_real_physical_counterfactual_1"
POLICIES=("original_v5_turn_replayed","native_no_bump_real_turn",
          "v27_frozen_original_turn","v33b_frozen_original_turn")
N=256

def by(turn,h):return int(0<int(turn)<=h)

def stats(rows,key):
    turns=[int(r[key]) for r in rows]
    return {f"by_T{h}":sum(by(t,h) for t in turns) for h in (1,2,3)}

def paired(rows,new,old,h):
    diffs=[by(r[new],h)-by(r[old],h) for r in rows]
    rng=random.Random(420000+sum(map(ord,new+old))+h)
    boots=sorted(100*sum(diffs[rng.randrange(N)] for _ in range(N))/N
                 for _ in range(8000))
    return {
      "delta_pp":100*sum(diffs)/N,
      "gains":sum(x>0 for x in diffs),
      "losses":sum(x<0 for x in diffs),
      "two_source_original_shuffles_shared":True,
      "paired_group_bootstrap_95ci_pp":[boots[199],boots[7799]],
    }

def run(glob_pattern,out):
    paths=sorted(glob.glob(glob_pattern))
    assert len(paths)==8,("Expected 8 contiguous 32-game shards",len(paths))
    rows=[]
    for p in paths:
        with gzip.open(p,"rt") as f:z=json.load(f)
        assert z["schema"]==SCHEMA and z["status"]=="PASS"
        assert z["all_original_v5_physical_game_win_turns_replayed_exactly"]
        assert z["strict_beam160_original_v5_rules_and_stateless_chance"]
        assert z["original_v5_lookahead_calls"]==0
        assert z["native_no_bump_uses_only_prior_visited_v5_stage_scores"]
        assert z["native_no_bump_uses_unchanged_v5_candidate_bottom"]
        assert z["not_new_independent_model_validation"]
        assert len(z["rows"])==32 and z["physical_game_ids"][1]-z["physical_game_ids"][0]==31
        rows.extend(z["rows"])
    rows.sort(key=lambda r:r["game_id"])
    assert [r["game_id"] for r in rows]==list(range(115000,115256))
    for r in rows:
        assert r["original_v5_turn_replayed"]==r["original_v5_turn_archived"]
        assert r["native_no_bump_keep_stage"]<=r["original_v5_assertive_keep_stage"]
        assert r["early_stop_due_to_bump_removal"]==(
            r["native_no_bump_keep_stage"]<r["original_v5_assertive_keep_stage"])
        assert all(r[p] in (0,1,2,3) for p in POLICIES)
    changed=[r for r in rows if r["early_stop_due_to_bump_removal"]]
    outdata={
      "schema":"dack_v42_v5_assertive_bumps_only_physical_N256_reused_115k",
      "status":"PASS","N":N,"source_groups":[115000,115255],
      "strict_99_real_physical_slots_and_beam160":True,
      "same_original_v5_candidates_scores_and_retained_bottoms":True,
      "native_no_bump_policy_has_no_v5_beam_calls_in_replay":True,
      "all_archived_original_v5_win_turns_verified_exactly":True,
      "historic_115k_previously_inspected_NOT_PROSPECTIVE":True,
      "N_groups_with_native_kept_earlier":len(changed),
      "N_groups_with_no_difference":N-len(changed),
      "mean_actual_keep_stage_delta_native_minus_assertive":
        sum(r["native_no_bump_keep_stage"]-r["original_v5_assertive_keep_stage"]
            for r in rows)/N,
      "per_policy_counts":{p:stats(rows,p) for p in POLICIES},
      "paired":{f"native_minus_v5_T{h}":
         paired(rows,"native_no_bump_real_turn","original_v5_turn_replayed",h)
         for h in (1,2,3)},
      "changed_only":{
        "N":len(changed),
        "native_better_T2":sum(by(r["native_no_bump_real_turn"],2)>
                             by(r["original_v5_turn_replayed"],2) for r in changed),
        "v5_better_T2":sum(by(r["native_no_bump_real_turn"],2)<
                             by(r["original_v5_turn_replayed"],2) for r in changed),
        "native_better_T3":sum(by(r["native_no_bump_real_turn"],3)>
                             by(r["original_v5_turn_replayed"],3) for r in changed),
        "v5_better_T3":sum(by(r["native_no_bump_real_turn"],3)<
                             by(r["original_v5_turn_replayed"],3) for r in changed),
        "earlier_native_kept_stage_counts":dict(Counter(str(r["native_no_bump_keep_stage"]) for r in changed)),
      },
      "limitations":[
        "This is a same-physical-game counterfactual with archived original v5 candidate scores and bottoms; it isolates threshold penalty, not v5 versus later-score differences.",
        "Historical 115k already observed for earlier models and cannot be used as a new acceptance set.",
        "Native KEEP at a previously rejected stage is evaluated only from original-v5 history; no hindsight about future stage cards in policy decision.",
        "Outcome is goldfish Dack deployment, not multiplayer cEDH victory.",
        "No claim that original v5 is globally optimal or that these score thresholds transfer to another deck.",
      ],
    }
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(outdata,indent=2,sort_keys=True)+"\n")
    print("DACK_V42_NATIVE_NO_BUMP_N256_PHYSICAL_POOL_PASS",json.dumps({
       "n":N,"counts":outdata["per_policy_counts"],
       "earlier_keeps":len(changed),
       "paired":outdata["paired"],"changed":outdata["changed_only"]
    },sort_keys=True),flush=True)

if __name__=="__main__":
    a=argparse.ArgumentParser()
    a.add_argument("--source",required=True)
    a.add_argument("--out",default="benchmark_results/v42_native_no_bump_v5_physical_N256.json")
    z=a.parse_args();run(z.source,z.out)
