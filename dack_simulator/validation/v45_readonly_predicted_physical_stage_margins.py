#!/usr/bin/env python3
"""Read-only old v43 predicted margin vs NEW physically measured K/C margin.

On 44 previously inspected actual v5-v43 first-conflict hands, use v43's
original predicted Q2 and original frozen v27 DP from the historical
natural-stage trace (no model calls), then compare with independently drawn
32 K KEEP and shared 96 C MULL physical future estimates.

Predicted Q2 is supervised by selected v14 physical policies, whereas C
is learned v27-DP; physical K/C are sampled real beam160 probabilities.
No model fitted; this diagnostic must not become a tuning target on 151k.
"""
from __future__ import annotations
import gzip,json,math
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def old_v43(gid):
    start=151000+((gid-151000)//32)*32
    p=ROOT/f"benchmark_results/v43_fresh_151k_maxQ2_shards/v43_151k_{start}.json.gz"
    with gzip.open(p,"rt") as f:doc=json.load(f)
    matches=[x for x in doc["rows"] if x["gid"]==gid]
    assert len(matches)==1
    return matches[0]["maxQ2"]
def correlation(a,b):
    assert len(a)==len(b) and len(a)>1
    ma=sum(a)/len(a);mb=sum(b)/len(b)
    numerator=sum((x-ma)*(y-mb) for x,y in zip(a,b))
    da=sum((x-ma)**2 for x in a);db=sum((y-mb)**2 for y in b)
    return numerator/math.sqrt(da*db) if da>0 and db>0 else None
def main():
    doc=json.loads((ROOT/"benchmark_results/v45_first_v5_v43_conflict_physical_K_vs_C_N44.json").read_text())
    assert doc["status"]=="PASS" and doc["outer_selected_game_groups"]==44
    allrows=[]
    for r in doc["per_selected_hand"]:
        gid=int(r["gid"]);stage=int(r["stage"])
        state=old_v43(gid)["history"][stage]
        assert state["stage"]==stage
        assert bool(state["kept"])==bool(r["v43_FIRST_action_keep"])
        pred=float(state["raw"])
        olddp=float(state["threshold"])
        K=float(r["QKEEP_byT2"]);C=float(r["QMULL_frozen_v43_byT2"])
        predicted_margin=pred-olddp
        true_margin=K-C
        if stage==7:raise AssertionError("no stage7 actual disagreement")
        # Original v43 actual action is determined by frozen old predicted Q2
        assert (predicted_margin>=-1e-6)==bool(state["kept"]),(
           "archived predictor-parity failure",gid,predicted_margin,state["kept"])
        a={
          "gid":gid,"seat":r["seat"],"stage":stage,
          "v43_earlier":r["v43_earlier"],"v5_earlier":r["v5_earlier"],
          "v43_predicted_Q2_exact_selected_hand":pred,
          "v43_inherited_DP_score":olddp,
          "v43_predicted_Qminus_DP_margin":predicted_margin,
          "independent_physical_QKEEP_T2_32":K,
          "independent_shared_future_QMULL_T2_96":C,
          "actual_QKEEPminus_QMULL_margin":true_margin,
          "predicted_Q2_minus_actual_QKEEP":pred-K,
          "physical_QMULL_minus_inherited_DP_score":C-olddp,
          "v43_KEEP_but_physical_margin_negative":bool(state["kept"] and true_margin<0),
          "v43_MULL_but_physical_margin_positive":bool(not state["kept"] and true_margin>0),
          "original_v5_action_matches_noisy_physical_margin":
             (r["v5_FIRST_action_keep"] and true_margin>0 or
              (not r["v5_FIRST_action_keep"] and true_margin<0)),
          "v43_action_matches_noisy_physical_margin":
             (state["kept"] and true_margin>0 or
              (not state["kept"] and true_margin<0)),
        }
        allrows.append(a)
    assert len(allrows)==44
    def metrics(rows):
        if not rows:return None
        n=len(rows)
        return {
          "N_selected_first_conflicts":n,
          "v43_earlier_cases":sum(r["v43_earlier"] for r in rows),
          "v5_earlier_cases":sum(r["v5_earlier"] for r in rows),
          "v43_predicted_keep_but_physically_mull_preferred":sum(r["v43_KEEP_but_physical_margin_negative"] for r in rows),
          "v43_predicted_mull_but_physically_keep_preferred":sum(r["v43_MULL_but_physical_margin_positive"] for r in rows),
          "v5_action_matches_noisy_physical_margin":sum(r["original_v5_action_matches_noisy_physical_margin"] for r in rows),
          "v43_action_matches_noisy_physical_margin":sum(r["v43_action_matches_noisy_physical_margin"] for r in rows),
          "mean_predicted_v43_Q2_minus_actual_QKEEP_pp":
             100*sum(r["predicted_Q2_minus_actual_QKEEP"] for r in rows)/n,
          "mean_physical_future_C_minus_inherited_oldDP_pp":
             100*sum(r["physical_QMULL_minus_inherited_DP_score"] for r in rows)/n,
          "mean_v43_predicted_keept_vs_oldDP_margin_pp":
             100*sum(r["v43_predicted_Qminus_DP_margin"] for r in rows)/n,
          "mean_physical_QKEEP_minus_future_QMULL_margin_pp":
             100*sum(r["actual_QKEEPminus_QMULL_margin"] for r in rows)/n,
          "pearson_Q2_prediction_vs_physical_QKEEP":
             correlation([r["v43_predicted_Q2_exact_selected_hand"] for r in rows],
                         [r["independent_physical_QKEEP_T2_32"] for r in rows]),
          "pearson_predicted_v43_QminusDP_vs_physical_KminusC":
             correlation([r["v43_predicted_Qminus_DP_margin"] for r in rows],
                         [r["actual_QKEEPminus_QMULL_margin"] for r in rows]),
        }
    result={
     "schema":"dack_v45_v43_predicted_vs_physical_keep_mull_first_conflict_margin_audit",
     "status":"PASS",
     "source_44_old_real_v5_v43_selected_first_disagreements":True,
     "new_independent_K32_shared_C96_per_cell":True,
     "no_new_physics_or_model_retraining_in_this_audit":True,
     "original_151k_retrospectively_selected_NOT_population_sample":True,
     "per_hand_physical_sign_uncertain_from_32_K_96_C_samples":True,
     "model_decision_prediction_not_same_as_statistical_truth":True,
     "metrics":{
         "all":metrics(allrows),
         "early_stage0_1":metrics([r for r in allrows if r["stage"] in (0,1)]),
         "v43_earlier":metrics([r for r in allrows if r["v43_earlier"]]),
         "v5_earlier":metrics([r for r in allrows if r["v5_earlier"]]),
         **{f"stage_{s}":metrics([r for r in allrows if r["stage"]==s]) for s in range(5)},
     },
     "all_selected_hands":allrows,
    }
    p=ROOT/"benchmark_results/v45_v43_Q2_DP_vs_true_physical_K_C_margin_audit.json"
    p.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print("DACK_V45_V43_MULL_DECISION_PREDICTION_VS_PHYSICAL_MARGIN_PASS",
          json.dumps(result["metrics"],sort_keys=True),flush=True)
if __name__=="__main__":main()
