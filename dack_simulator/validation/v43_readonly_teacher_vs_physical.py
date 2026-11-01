#!/usr/bin/env python3
"""v43 read-only physically realized KEEP value vs incompatible v5/v27 scores.

Only compare like-with-like hands: original v5 selected hand/bottom, original
v27 hand/bottom and frozen v33b forced physical KEEP hand/bottom must all
match. On stage0 and stage1 they necessarily match. On other London stages
exclude candidate mismatches; never attribute a mismatched Q to v5's hand.
Use 32 independent physical K outcomes from previously consumed v34c as
diagnostics; original v5 objective U=PbyT2+.5 PexactT3 (not PbyT2).
"""
from __future__ import annotations
import json, math,sys
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from dack_simulator.validation import v34c_pool_actual_disagreement as v34
S="dack_v43_archived_original_v5_and_v27_physically_matched_keep_diagnostics_1"

def by(t,h):return int(0<int(t)<=h)
def run(out):
    cases=json.loads((ROOT/"benchmark_results/v42_original_v5_vs_v27_threshold_mechanism_115k.json").read_text())["cases"]
    groups,cs,sha=v34.load(
      str(ROOT/"benchmark_results/v34c_forced_keep_shards/v34c_keep_*.json.gz"),
      str(ROOT/"benchmark_results/v34_consistent_regret_shards/v34_C_*.json.gz"))
    measured={r["game_id"]:r for r in groups}
    assert len(measured)==len(cases)==100
    records=[];dropped=Counter()
    for q in cases:
        r=measured[q["game_id"]]
        assert r["stage"]==q["stage"] and r["seat"]==q["seat"]
        handmatch=(Counter(q["v5_hand"])==Counter(q["v27_hand"])==
                   Counter(r["v33b_hand"]))
        bottommatch=(Counter(q["v5_bottom"])==Counter(q["v27_bottom"])==
                     Counter(r["v33b_bottom"]))
        if not handmatch or not bottommatch:
            dropped["different_retained_hand"]+=1
            dropped["early_different_retained_hand"]+=int(q["stage"]<=1)
            continue
        trials=r["fresh_keep_futures_by_split"]["calibration"]+r["fresh_keep_futures_by_split"]["replication"]
        assert len(trials)==32
        k={h:sum(by(t,h) for t in trials)/32 for h in (1,2,3)}
        true_u=.5*(k[2]+k[3])
        teacher=float(q["v5_raw"])
        student=float(q["v27_pred_Qkeep"])
        records.append({
         "gid":q["game_id"],"stage":q["stage"],"mechanism":q["mechanism"],
         "teacher_v5_U":teacher,"student_v27_pred_T2":student,
         "physical_true_KbyT2_32":k[2],
         "physical_true_KbyT3_32":k[3],
         "physical_true_KU_T2_plus_half_exactT3_32":true_u,
         "physical_K_T2_minus_v27_prediction":k[2]-student,
         "physical_K_U_minus_v5_teacher_prediction":true_u-teacher,
         "first_7_or_second_7":q["stage"]<=1,
         "identical_hand_and_bottom_both_models_and_forced_physics":True,
         "v5_lookahead_beam":60,
         "strict_physical_K_beam":160,
        })
    def stat(rr):
        if not rr:return {"N":0}
        n=len(rr)
        return {
         "N":n,
         "teacher_v5_U_mean":sum(z["teacher_v5_U"] for z in rr)/n,
         "student_v27_T2_mean":sum(z["student_v27_pred_T2"] for z in rr)/n,
         "actual_physical_K_U_mean":sum(z["physical_true_KU_T2_plus_half_exactT3_32"] for z in rr)/n,
         "actual_physical_K_T2_mean":sum(z["physical_true_KbyT2_32"] for z in rr)/n,
         "v5_teacher_U_mean_minus_physical_U":sum(z["teacher_v5_U"]-
           z["physical_true_KU_T2_plus_half_exactT3_32"] for z in rr)/n,
         "v27_pred_T2_mean_minus_physical_T2":sum(z["student_v27_pred_T2"]-
           z["physical_true_KbyT2_32"] for z in rr)/n,
         "v5_U_rmse_vs_32_trial_physical":math.sqrt(sum((
           z["teacher_v5_U"]-z["physical_true_KU_T2_plus_half_exactT3_32"])**2
              for z in rr)/n),
         "v27_T2_rmse_vs_32_trial_physical":math.sqrt(sum((
           z["student_v27_pred_T2"]-z["physical_true_KbyT2_32"])**2
              for z in rr)/n),
        }
    result={
      "schema":S,"status":"PASS",
      "source":"v42 archived first v5-v27 conflicts plus v34c 32 independent strict-beam160 forced KEEP physical trials",
      "all_physical_and_teacher_archives_already_consumed":True,
      "actual_K_ground_truth_is_32_noisy_trials_not_exact_probability":True,
      "only_identical_candidate_retained_hand_and_bottom_compared":True,
      "teacher_original_utility_and_student_PbyT2_not_same_target":True,
      "v5_teacher_uses_beam60_vs_true_physical_beam160":True,
      "not_predictive_holdout_or_model_promotion":True,
      "N_archived_conflict_groups":100,
      "N_identical_hand_matches":len(records),
      "dropped_mismatches":dict(dropped),
      "all_matched":stat(records),
      "early_0_1":stat([r for r in records if r["stage"]<=1]),
      "v5_keeps_but_v27_mulls":stat([r for r in records if r["mechanism"]=="v5_keep_v27_mull__not_an_assertive_veto"]),
      "v5_mulls_but_v27_keeps":stat([r for r in records if r["mechanism"]!="v5_keep_v27_mull__not_an_assertive_veto"]),
      "specific_115025":next(r for r in records if r["gid"]==115025),
      "individual_groups":records,
    }
    assert len(records)>=41
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print("DACK_V43_ARCHIVED_SAME_HAND_V5_V27_PHYSICAL_DIAGNOSTIC_PASS",
       json.dumps({k:result[k] for k in ("N_identical_hand_matches",
          "early_0_1","v5_keeps_but_v27_mulls","v5_mulls_but_v27_keeps",
          "specific_115025")},sort_keys=True),flush=True)

if __name__=="__main__":
    run(ROOT/"benchmark_results/v43_v5_v27_same_hand_physical_K_calibration.json")
