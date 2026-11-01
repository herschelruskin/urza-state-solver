#!/usr/bin/env python3
"""Pool physically sampled full99 v43 continuation lottery seat/stage cells.

True future PbyT2 is an actual physical conditional probability approximation
under the frozen v43 downstream policy, whereas frozen inherited v27-DP is
a predicted policy utility cutoff; differences expose mismatch but MUST NOT
be directly used as a replacement decision threshold without calibration
and prospective action-regret tests.
"""
from __future__ import annotations
import glob,gzip,json,math
from collections import defaultdict
from pathlib import Path
SCHEMA="dack_v45_157k_real_v43_conditional_next_london_continuation_v1"
TRIALS=96
def by(t,h):return int(0<t<=h)
def wilson(x,n):
    z=1.96;p=x/n;den=1+z*z/n
    mid=(p+z*z/(2*n))/den
    rad=z/den*math.sqrt(p*(1-p)/n+z*z/(4*n*n))
    return [mid-rad,mid+rad]
def main():
    paths=sorted(glob.glob("collected/v45_v43_C_*.json.gz"))
    assert len(paths)==20,("full 4 seats x 5 early stage cells required",len(paths))
    cells={};summ=defaultdict(list)
    for path in paths:
        with gzip.open(path,"rt") as f:d=json.load(f)
        assert d["schema"]==SCHEMA and d["status"]=="PASS"
        assert d["future_full_99_card_decks_restored"]
        assert d["new_independent_full99_shuffle_per_future_London_stage"]
        assert d["original_v43_candidate_choice_and_KEEP_reproduced_exactly"]
        assert d["strict_physical_beam160"] and d["original_v5_runtime_beams"]==0
        assert d["no_current_seven_in_future_C_lottery"]
        assert d["physical_C_futures"]==TRIALS and len(d["results"])==TRIALS
        seat=int(d["seat"]);stage=int(d["rejected_stage"])
        assert seat in (0,1,2,3) and stage in (0,1,2,3,4)
        key=f"seat{seat}_stage{stage}"
        assert key not in cells
        turns=[r["win_turn"] for r in d["results"]]
        counts={h:sum(by(t,h) for t in turns) for h in (1,2,3)}
        assert all(abs(counts[h]/TRIALS-d[f"physical_future_PbyT{h}"])<1e-12 for h in (1,2,3))
        cells[key]={
           "seat":seat,"rejected_stage":stage,"N_physical_full99_futures":TRIALS,
           "frozen_v27_DP_score_threshold":d["original_v27_learned_DP_threshold"],
           "true_frozen_v43_PbyT2_estimate":counts[2]/TRIALS,
           "difference_true_v43_C2_minus_frozen_v27_pred_DP":
                counts[2]/TRIALS-d["original_v27_learned_DP_threshold"],
           "physical_counts":{f"byT{h}":counts[h] for h in (1,2,3)},
           "Wilson_95ci_true_v43_PbyT2":wilson(counts[2],TRIALS),
           "mean_future_final_kept_stage":d["mean_later_final_stage"],
        }
        summ[stage].append(cells[key])
    assert len(cells)==20
    bystage={}
    for stage,records in sorted(summ.items()):
        assert len(records)==4
        n=TRIALS*4;k=sum(r["physical_counts"]["byT2"] for r in records)
        avgpred=sum(r["frozen_v27_DP_score_threshold"] for r in records)/4
        bystage[str(stage)]={
           "N_physical_future_groups":n,
           "actual_frozen_v43_future_PbyT2":k/n,
           "original_v27_learned_DP_avg_threshold":avgpred,
           "actual_minus_inherited_predicted_DP":k/n-avgpred,
           "Wilson95_actual_future_PbyT2_across_seats":wilson(k,n),
           "max_cell_absolute_estimate_minus_prior_score":
               max(abs(r["difference_true_v43_C2_minus_frozen_v27_pred_DP"]) for r in records),
        }
    doc={
       "schema":"dack_v45_v43_future_mulligan_physical_vs_old_v27_DP_20cell_audit",
       "status":"PASS",
       "source_physical_99slot_independent_C_futures":TRIALS*20,
       "source_20_seat_by_rejected_stage_lotteries":True,
       "stage0_and_stage1_separate_continuations":True,
       "physical_future_policy_is_frozen_coupled_v43":True,
       "old_DP_utility_and_physical_probability_NOT_guaranteed_same_scale":True,
       "no_prospective_policy_acceptance":True,
       "no_new_model_or_thresholds_fitted":True,
       "by_stage":bystage,"by_cell":cells,
    }
    p=Path("benchmark_results/v45_v43_physical_continuation_vs_v27_DP_20cells.json")
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print("DACK_V45_TRUE_V43_FUTURE_CONTINUATION_PHYSICAL_20CELL_PASS",
           json.dumps({"total":TRIALS*20,"stages":bystage},sort_keys=True),flush=True)
if __name__=="__main__":main()
