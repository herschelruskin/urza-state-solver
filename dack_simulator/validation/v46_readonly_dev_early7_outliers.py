#!/usr/bin/env python3
"""Read-only forensic on already-consumed v46 early-seven development states.

Highlight physically observed K16 vs shared C128 large disagreements.
This is POST-HOC EXPLORATION, not a new acceptance set or proof of optimal
KEEP/MULL for a particular hand. No refit, threshold changes or new physics.
"""
import gzip,glob,json
from pathlib import Path
R=Path(__file__).resolve().parents[2]
def run():
    rpt=json.loads((R/"benchmark_results/v46_156k_two_sevens_physical_train_dev.json").read_text())
    assert rpt["dev"]["dev_pass_full_game_gate"] is False
    dev={(z["gid"],z["stage"]):z for z in rpt["dev"]["per_state_research_diagnostics"]}
    assert len(dev)==128
    source={}
    for p in sorted(glob.glob(str(R/"benchmark_results/v46_new_156k_KC_physical_shards/v46_K_*.json.gz"))):
        with gzip.open(p,"rt") as f:d=json.load(f)
        if d["split"]!="dev":continue
        for r in d["rows"]:
            key=(r["gid"],r["stage"])
            assert key in dev and key not in source
            source[key]=r
    assert len(source)==128
    cases=[];all_approx=[]
    for key,z in sorted(dev.items()):
        src=source[key]
        K2=sum(0<t<=2 for t in src["turns"])/16
        K3=sum(0<t<=3 for t in src["turns"])/16
        C2=z["C2"];C3=z["C3"]
        assert abs(K2-sum(0<t<=2 for t in z["physical_K_turns"])/16)<1e-12
        assert abs(src["v43_pred_Q2"]-z["v43_Q2"])<1e-10
        sign=1 if z["old_v43_keep"] else -1
        v43_mis=sig=-sign*(K2-C2)
        if sig>0:all_approx.append((z["stage"],sign))
        if sig>0.10:
            cases.append({
              "gid":key[0],"stage":key[1],"seat":src["seat"],
              "seven":src["seven"],"v43_KEEP":z["old_v43_keep"],
              "v46_KEEP":z["v46_keep"],
              "K2_sampled_fraction":K2,"K3_sampled_fraction":K3,
              "C2_shared_fraction":C2,"C3_shared_fraction":C3,
              "v43_predicted_Q2":z["v43_Q2"],"v46_predicted_Q2":z["v46_K2"],
              "v43_original_DP":z["v43_DP"],
              "approx_abs_physical_Q2_action_regret":sig,
              "number_independent_K_futures":16,
              "physical_K_turns":src["turns"],
            })
    cases.sort(key=lambda x:x["approx_abs_physical_Q2_action_regret"],reverse=True)
    report={
       "schema":"dack_v46_exploratory_156k_dev_seven_card_outlier_hand_audit",
       "status":"PASS","dev_K_source_unique_outer_groups":64,
       "first_two_seven_stage_states":128,
       "already_seen_dev_forbidden_as_future_independent_holdout":True,
       "no_model_retraining_or_parameter_tuning":True,
       "conditional_sign_error_is_noisy_16_future_estimate":True,
       "stage0_approx_misvalued":sum(s==0 for s,_ in all_approx),
       "stage1_approx_misvalued":sum(s==1 for s,_ in all_approx),
       "large_absQ2_regret_examples":cases
    }
    p=R/"benchmark_results/v46_exploratory_dev_early_seven_hand_failures.json"
    p.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print("DACK_V46_DEV_EXPLORE_SEVEN_CARD_FAILURE_HANDS_PASS",
          json.dumps({k:v for k,v in report.items() if k!="large_absQ2_regret_examples"}),flush=True)
    for c in cases:
        print("DACK_V46_DEV_HAND",c["gid"],"stage",c["stage"],
              "seven",c["seven"],"observedK2",c["K2_sampled_fraction"],
              "C2",c["C2_shared_fraction"],"pred_v43",c["v43_predicted_Q2"],flush=True)
if __name__=="__main__":run()
