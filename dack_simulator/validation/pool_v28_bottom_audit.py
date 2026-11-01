#!/usr/bin/env python3
"""Pool N64 v28 bottom-selection audit. 99k games are never used for fitting."""
import collections,glob,gzip,json,random,statistics
from pathlib import Path

def grouped_difference(rows,a,b,key):
    diffs=[]
    for r in rows:
        c={z["candidate_index"]:z for z in r["candidate_results"]}
        ai=r[a];bi=r[b]
        assert ai in c and bi in c
        diffs.append(c[ai][key]-c[bi][key])
    rng=random.Random(281128)
    boot=sorted(sum(diffs[rng.randrange(len(diffs))] for _ in diffs)/len(diffs)
                for _ in range(10000))
    return {
       "n_independent_decision_groups":len(diffs),
       "mean_paired_difference":statistics.mean(diffs),
       "paired_bootstrap_95ci":[boot[249],boot[9749]],
       "strict_positive_groups":sum(x>0 for x in diffs),
       "strict_negative_groups":sum(x<0 for x in diffs),
       "tied_groups":sum(x==0 for x in diffs),
    }

def main():
    files=sorted(glob.glob("collected/v28_99k_*.json.gz"))
    assert len(files)==16,len(files)
    rows=[]
    for f in files:
        with gzip.open(f,"rt") as stream:
            doc=json.load(stream)
        assert doc["schema"]=="dack_v28_v5_bottom_order_independence_and_unseen_value"
        assert doc["status"]=="PASS" and doc["n_games"]==4
        assert doc["teacher_actual_hidden_order_invariance"] is True
        assert doc["teacher_and_labels_disjoint_rollout_seeds"] is True
        rows+=doc["rows"]
    rows.sort(key=lambda z:z["game_id"])
    assert [z["game_id"] for z in rows]==list(range(99000,99064))
    eligible=[z for z in rows if z["status"]=="audited"]
    for z in eligible:z["first_index"]=0
    assert eligible and all(z["actual_unknown_order_permutation_invariance_verified"] for z in eligible)
    assert all(z["sampled_independent_futures_per_candidate"]==16 for z in eligible)
    assert all(z["independent_same_future_for_all_candidates"] for z in eligible)
    report={
       "schema":"dack_v28_frozen_v5_bottom_hidden_order_and_unseen_utility_N64",
       "status":"PASS",
       "game_ids":[99000,99063],
       "sampled_independent_game_groups":64,
       "bottom_eligible_game_groups":len(eligible),
       "kept7_no_bottom":64-len(eligible),
       "total_evaluated_candidate_futures":sum(16*len(z["candidate_results"]) for z in eligible),
       "v5_actual_hidden_order_invariant_all_groups":True,
       "observed_teacher_choice_outside_structural_top3":sum(z["selected_v5_outside_structural_top3"] for z in eligible),
       "observed_teacher_choice_differs_v14":sum(z["v5_changes_bottom_vs_v14"] for z in eligible),
       "v5_struct_first_agreement":sum(z["v5_candidate_index"]==0 for z in eligible),
       "v5_v14_agreement":sum(z["v5_candidate_index"]==z["v14_candidate_index"] for z in eligible),
       "keep_n_distribution":dict(sorted(collections.Counter(str(z["keep_n"]) for z in eligible).items())),
       "seat_distribution":dict(sorted(collections.Counter(str(z["seat"]) for z in eligible).items())),
       "paired_independent_16_future_comparisons":{
         a+"_vs_"+b:{
            metric:grouped_difference(eligible,a,b,metric)
            for metric in ("heldout_blended_utility","heldout_by_T2","heldout_by_T3")
         } for a,b in [
            ("v5_candidate_index","v14_candidate_index"),
            ("v5_candidate_index","first_index"),
         ]
       },
       "individual_research_groups":eligible,
       "no_model_training_or_99k_tuning":True,
       "teacher_future_samples_are_NOT_actual_realized_topdeck":True,
       "limitation":"v5 is a sampled-lookahead policy over hypothetical futures; heldout futures test generalization, not exact EV. Potential full-library visibility inside goldfish gameplay is a separate engine-design question.",
    }
    out=Path("benchmark_results/v28_bottom_hidden_order_and_unseen_value_N64.json")
    out.parent.mkdir(exist_ok=True,parents=True)
    out.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print("DACK_V28_HIDDEN_ORDER_AND_UNSEEN_UTILITY_N64_PASS",json.dumps({
      k:v for k,v in report.items() if k!="individual_research_groups"
    },sort_keys=True),flush=True)

if __name__=="__main__":
    main()
