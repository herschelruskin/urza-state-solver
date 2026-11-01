#!/usr/bin/env python3
"""Read-only v34 diagnostic of v27 Qkeep discrimination and shared C calibration.

No training, no deployed policy update, and NO new games. Original 117k
labels are CONSUMED validation for v34, so all post-hoc experiments are
descriptive and must be independently validated on NEW physical cohorts.
"""
from __future__ import annotations
from collections import Counter,defaultdict
import gzip,glob,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def read():
    files=sorted(glob.glob(str(ROOT/"benchmark_results/v34_consistent_regret_shards/v34_K_*.json.gz")))
    assert len(files)==24
    rows={"train":[],"untouched_validation":[]}
    for f in files:
        with gzip.open(f,"rt") as h:d=json.load(h)
        assert d["schema"]=="dack_v34_true_Qkeep_frozen_v33b_all_stages"
        assert d["status"]=="PASS" and d["actual_beam160"]
        rows[d["split"]]+=d["rows"]
    assert len(rows["train"])==448 and len(rows["untouched_validation"])==224
    pooled=json.loads((ROOT/"benchmark_results/v34_consistent_keep_mull_117k_screen.json").read_text())
    assert pooled["schema"]=="dack_v34_shared_consistent_keep_mull_conditional_117k_validation"
    assert pooled["status"]=="PASS"
    return rows,pooled

def mean(items):
    return sum(items)/len(items) if items else None

def bin_report(rr,cval):
    bins=defaultdict(list)
    for r in rr:
        margin=float(r["v27_pred_Qkeep_T2"])-float(r["v27_DP_threshold"])
        k=float(r["empirical_Qkeep_T2"])
        cv=float(cval[f'{r["seat"]}:{r["stage"]}'])
        key=("keep" if r["v27_would_keep"] else "mull",
             "far" if abs(margin)>.20 else
             "medium" if abs(margin)>.05 else "near")
        bins[key].append({
          "pred":r["v27_pred_Qkeep_T2"],"K":k,"C":cv,
          "advantage":k-cv,"margin":margin,"gid":r["game_id"]
        })
    report={}
    for key,values in sorted(bins.items()):
        report[key[0]+":"+key[1]]={
            "N":len(values),
            "mean_pred_Qkeep":mean([v["pred"] for v in values]),
            "mean_real_Qkeep":mean([v["K"] for v in values]),
            "mean_true_Qmull":mean([v["C"] for v in values]),
            "mean_real_advantage_keep_minus_mull":mean([v["advantage"] for v in values]),
            "mean_predicted_margin":mean([v["margin"] for v in values])}
    return report

def diagnostic(rr,cval):
    groups=defaultdict(list)
    for r in rr:
        groups[r["stage"]].append(r)
    report={"N_stage_states":len(rr),"N_physical_groups":len(set(r["game_id"] for r in rr))}
    report["by_stage"]={}
    for stage,rows in sorted(groups.items()):
        mse=mean([(float(r["v27_pred_Qkeep_T2"])-float(r["empirical_Qkeep_T2"]))**2
                  for r in rows])
        bias=mean([float(r["empirical_Qkeep_T2"])-float(r["v27_pred_Qkeep_T2"])
                  for r in rows])
        true_adv=[float(r["empirical_Qkeep_T2"])-float(cval[f'{r["seat"]}:{r["stage"]}'])
                  for r in rows]
        old_margin=[float(r["v27_pred_Qkeep_T2"])-float(r["v27_DP_threshold"])
                    for r in rows]
        n=len(rows)
        k=[i for i,r in enumerate(rows) if r["v27_would_keep"]]
        m=[i for i,r in enumerate(rows) if not r["v27_would_keep"]]
        # 'Noisy oracle' upper bound is biased upward because only 8
        # futures per KEEP. Do NOT infer achievable performance from it.
        optimistic_regret=mean([max(0.,v) if not rows[i]["v27_would_keep"] else max(0.,-v)
                                for i,v in enumerate(true_adv)])
        old_decisions=[bool(r["v27_would_keep"]) for r in rows]
        # Replacing original threshold with VALIDATION true C is a
        # retrospective oracle sensitivity, NOT a deployable policy.
        direct_c_decisions=[
            float(r["v27_pred_Qkeep_T2"])>=float(cval[f'{r["seat"]}:{r["stage"]}'])
            for r in rows]
        direct_delta=mean([(int(a)-int(b))*v
                    for a,b,v in zip(direct_c_decisions,old_decisions,true_adv)])
        report["by_stage"][str(stage)]={
            "N":n,"old_keeps":len(k),"old_mulls":len(m),
            "mean_v27_prediction":mean([r["v27_pred_Qkeep_T2"] for r in rows]),
            "mean_true_keep_by_T2":mean([r["empirical_Qkeep_T2"] for r in rows]),
            "mean_v27_prediction_bias_true_minus_prediction":bias,
            "raw_Qkeep_MSE_to_eight_future_empirical_fraction":mse,
            "mean_true_advantage_keep_minus_mull_among_old_keeps":mean([true_adv[i] for i in k]),
            "mean_true_advantage_keep_minus_mull_among_old_mulls":mean([true_adv[i] for i in m]),
            "mean_original_Qkeep_minus_old_C":mean(old_margin),
            "old_versus_TRUE_C_changed_decisions_diagnostic":sum(a!=b for a,b in zip(direct_c_decisions,old_decisions)),
            "old_versus_TRUE_C_posthoc_one_step_T2_gain_pp_NOT_VALIDATION":100*direct_delta,
            "optimistic_noisy_oracle_T2_regret_pp_NOT_ACTIONABLE":100*optimistic_regret}
    report["margin_bins"]=bin_report(rr,cval)
    return report

def main():
    rows,source=read()
    old=source["old_seat_stage_C_T2"]
    trainC=source["train_seat_stage_C_T2"]
    valC=source["heldout_seat_stage_C_T2"]
    bycell=[]
    for s in range(7):
        for seat in range(4):
            key=f"{seat}:{s}"
            bycell.append({
                "seat":seat,"stage":s,"old_C":old[key],
                "independent_training_true_C":trainC[key],
                "independent_validation_true_C":valC[key],
                "train_minus_old":trainC[key]-old[key],
                "validation_minus_old":valC[key]-old[key]})
    report={
       "schema":"dack_v34_readonly_keep_score_rank_and_continuation_audit",
       "status":"PASS","physical_beam_evaluations_new":0,
       "validation_117k_is_already_consumed_no_candidate_tuning":True,
       "not_new_policy":True,
       "source_rollouts":source["physical_rollouts_keep"]+source["physical_rollouts_mull"],
       "continuation_by_seat_stage":bycell,
       "training_Qkeep_diagnostic":diagnostic(rows["train"],trainC),
       "untouched_v34_117k_Qkeep_diagnostic_consumed":diagnostic(rows["untouched_validation"],valC),
       "technical_warnings":[
          "Only 8 futures per keep Q and 32 per heldout C cell",
          "Unvisited-stage labels have different distribution from played path",
          "Noisy per-hand empirical maximum introduces optimistic selection bias",
          "Posthoc true C threshold contrast is not a deployable validation result",
          "Big seat-stage C differences can reflect estimation uncertainty and distribution shifts",
          "Do not treat average calibration as identical to individual hand discrimination",
          "No rules or physical game engine changed"]
    }
    p=ROOT/"benchmark_results/v34_readonly_keep_rank_and_continuation_audit.json"
    p.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print("DACK_V34_READONLY_KEEP_RANK_AUDIT_PASS",json.dumps({
       "train_stage":report["training_Qkeep_diagnostic"]["by_stage"],
       "heldout_stage":report["untouched_v34_117k_Qkeep_diagnostic_consumed"]["by_stage"]
       },sort_keys=True),flush=True)

if __name__=="__main__":main()
