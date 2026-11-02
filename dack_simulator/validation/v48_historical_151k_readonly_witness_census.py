#!/usr/bin/env python3
"""Retrospective descriptive read-only v5/v43 early decision disagreement
coverage, using a PREVIOUSLY OPENED 151k file. NEVER validation/training.
Does not rerun v5, v43 physics or reinterpret a counterfactual other hand
as a proven benefit. Only documents which visible sevens have legal witnesses.
"""
from __future__ import annotations
from collections import Counter
import json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import dack_paired_counterfactual_v43_v27_max_Q2_20261101 as v43
import dack_turn_aware_legal_mana_features_v48_20261101 as mana
import dack_turn_aware_mana_tutor_guaranteed_v48b_20261101 as tutor
ref=v43.ref
DATA=ROOT/"benchmark_results/v45_v5_v43_matched_151k_N128_first_conflict.json"
def main():
    v43.audit()
    inp=json.loads(DATA.read_text())
    selected=[case for case in inp["cases"]
              if case["first_disagreement_stage"] in (0,1)]
    rows=[];t0=time.perf_counter()
    for case in selected:
        gid=case["gid"];stage=case["first_disagreement_stage"]
        seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
        seat,orders=ref.stage_slots(seed)
        assert seat==case["seat"]
        deck=ref.SLOT_VARIANTS["one_key_34"]
        seven=tuple(deck[k] for k in orders[stage][:7])
        unknown=tuple(deck[k] for k in orders[stage][7:])
        assert Counter(seven)==Counter(case["v43_selected_hand_at_comparison"])
        x=mana.analyze(seven,unknown,seat,keep_n=7,stage=stage,beam=32,depth=9)
        y=tutor.analyze(seven,unknown,seat,keep_n=7,stage=stage,beam=32,depth=9)
        rows.append({"gid":gid,"stage":stage,"seat":seat,
            "v5_T2":0<case["v5_turn"]<=2,
            "v43_T2":0<case["v43_turn"]<=2,
            "v5_kept_comparison_stage":case["v5_final_keep_stage"]==stage,
            "v43_kept_comparison_stage":case["v43_final_keep_stage"]==stage,
            "v43_Q2":case["v43_predicted_T2"],
            "v43_archived_DP":case["v43_DP_continuation"],
            "T1_no_draw_mana":x["mana_witness_T1_no_draw"],
            "T2_no_draw_mana":x["mana_witness_T2_no_draw"],
            "T2_source_tutor_mana":y["T2_tutor_legal_no_draw_witness"],
            "source_tutor_added":y["T2_tutor_legal_no_draw_witness"] and not x["mana_witness_T2_no_draw"],
            "seven":list(seven)})
    old_v5_only=[r for r in rows if r["v5_T2"] and not r["v43_T2"]]
    v5_kept_old_v43_mulled=[r for r in old_v5_only
            if r["v5_kept_comparison_stage"] and not r["v43_kept_comparison_stage"]]
    result={"schema":"dack_v48_readonly_previously_opened_151k_early_conflict_witness_coverage_v1",
      "status":"PASS","not_prospective_not_training_not_validation":True,
      "n_early_conflicts":len(rows),
      "v5_only_T2_early_conflicts":len(old_v5_only),
      "v5_only_T2_early_with_source_tutor_witness":
          sum(r["T2_source_tutor_mana"] for r in old_v5_only),
      "v5_kept_v43_mulled_and_only_v5_T2":len(v5_kept_old_v43_mulled),
      "that_subset_with_tutor_witness":sum(r["T2_source_tutor_mana"] for r in v5_kept_old_v43_mulled),
      "all_early_with_no_draw_T2_witness":sum(r["T2_no_draw_mana"] for r in rows),
      "all_early_with_guaranteed_tutor_T2_witness":sum(r["T2_source_tutor_mana"] for r in rows),
      "elapsed_seconds":time.perf_counter()-t0,
      "rows":rows}
    path=ROOT/"benchmark_results/v48_readonly_151k_early_v5_v43_witness_coverage.json"
    path.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print("DACK_V48_RETROSPECTIVE_V5_CONFLICT_WITNESS_COVERAGE_PASS",json.dumps({
      k:result[k] for k in ("n_early_conflicts","v5_only_T2_early_conflicts",
        "v5_only_T2_early_with_source_tutor_witness",
        "v5_kept_v43_mulled_and_only_v5_T2","that_subset_with_tutor_witness",
        "all_early_with_no_draw_T2_witness",
        "all_early_with_guaranteed_tutor_T2_witness")},sort_keys=True),flush=True)
if __name__=="__main__":main()
