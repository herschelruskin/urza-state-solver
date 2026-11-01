#!/usr/bin/env python3
"""v37 read-only post-failure why DIRECT advantage agrees with v27.

NO new outcome labels, no model refit. For full 256 new 127k
physical groups×3 London stages, compute predictions BEFORE outcomes,
and distinguish (a) median A2 agrees with old action, (b) opposite
median sign but conservative A2 quartile fails, (c) A2 passes but
T3 blocks, (d) passed all gates. Verify all final physical hands
and libraries match v33b. Report selection-stage direction imbalance
and exact conditional/full-game zero on THIS cohort only.
"""
from __future__ import annotations
import hashlib,json,sys
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from dack_simulator.validation import v34_frozen_v33b_continuation as kernel
import dack_mulligan_v37_features as feat
import dack_mulligan_v37_direct_regret as modelrun
import dack_paired_counterfactual_v37_direct_regret_20261101 as p37

def run():
    p37.audit()
    census=ROOT/"datasets/v37_127k_outcome_blind_census.json"
    d=json.loads(census.read_text())
    assert d["schema"]=="dack_v37_127k_unseen_complete_outcome_blind_action_census_v1"
    assert d["status"]=="PASS" and d["changed_stage_decisions"]==0
    assert d["changed_reached_final_physical_games"]==0
    assert d["model_sha256"]==p37.MODEL_SHA
    from dack_simulator.validation.v37_manifest import SCHEMA as MANIFEST_SCHEMA
    m=json.loads((ROOT/"datasets/v37_preoutcome_training_manifest.json").read_text())
    assert m["schema"]==MANIFEST_SCHEMA and m["status"]=="PASS"
    ref=kernel.ref;deck=ref.SLOT_VARIANTS[kernel.DECK_KEY]
    reasons=Counter();perstage=defaultdict(Counter)
    oldactions=Counter();media=[]
    for gid in range(127200,127456):
        seat,orders=ref.stage_slots(int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE)
        for stage in (0,1,2):
            seen=tuple(deck[x] for x in orders[stage][:7])
            hidden=tuple(deck[x] for x in orders[stage][7:])
            sel=kernel.current(seen,hidden,seat,stage)
            f=feat.extract(seen,hidden,seat,stage,sel)
            pred2,pred3=modelrun.predict(p37.MODEL,f)
            old=sel["old_v27_keep"]
            med2=pred2[modelrun.N//2]
            oldactions[(stage,int(old))]+=1
            if old:
                opposite=med2<0
                t2gate=pred2[3*modelrun.N//4]<-modelrun.T2_DEADBAND
                t3gate=pred3[modelrun.N//2]<=modelrun.T3_ALLOWED_LOSS
            else:
                opposite=med2>0
                t2gate=pred2[modelrun.N//4]>modelrun.T2_DEADBAND
                t3gate=pred3[modelrun.N//2]>=-modelrun.T3_ALLOWED_LOSS
            new,diagnostic=modelrun.decide(p37.MODEL,f,stage,old)
            assert new==old and diagnostic["reason"]=="frozen_v27_fallback"
            if not opposite:reason="median_direct_regret_sign_agrees_with_v27"
            elif not t2gate:reason="opposite_median_but_T2_ensemble_stability_or_margin_fails"
            elif not t3gate:reason="T2_supports_change_but_T3_safeguard_blocks"
            else:reason="both_pass_ACTION_CHANGED"
            reasons[reason]+=1;perstage[str(stage)][reason]+=1
            media.append((int(old),med2))
    assert len(media)==768 and sum(reasons.values())==768
    assert reasons["both_pass_ACTION_CHANGED"]==0
    bysource=defaultdict(list)
    for r in m["enriched_groups"]:bysource[r["sample"]].append(r)
    pool_stats={}
    for src,arr in bysource.items():
        pool_stats[src]={
          "n":len(arr),
          "v27_KEEP_count":sum(int(x["v27_keep"]) for x in arr),
          "v13_proxy_KEEP_count":sum(int(x["teacher_proxy_keep"]) for x in arr),
          "mean_abs_original_v27_margin":sum(x["abs_margin"] for x in arr)/len(arr),
          "mean_abs_v13_teacher_vote_distance_cutoff":
             sum(abs(x["proxy_teacher_score"]-x["teacher_cutoff"]) for x in arr)/len(arr)
        }
    p=ROOT/"benchmark_results/v37_readonly_action_sign_and_sampling_pitfalls.json"
    out={
      "schema":"dack_v37_127k_zero_beam_action_sign_and_sampling_audit_v1",
      "status":"PASS","policy_approved":False,
      "n_unselected_outer_games":256,
      "n_actual_early_stage_states":768,
      "no_new_beam160_games":True,
      "predicted_signed_T2_mean_by_original_action":{
        name:sum(x[1] for x in media if x[0]==act)/sum(x[0]==act for x in media)
        for name,act in (("old_MULL",0),("old_KEEP",1))
      },
      "original_action_counts_by_stage":{f"{s}:{k}":v for (s,k),v in sorted(oldactions.items())},
      "action_gate_reason_count":dict(reasons),
      "by_stage_gate_counts":dict(perstage),
      "training_proxy_discordant_stratum_diagnostics":pool_stats,
      "all_768_actions_identical":True,
      "all_256_final_physical_hand_and_library_identical":True,
      "conditional_population_value_difference_exactly_zero_on_this_cohort":True,
      "full_game_turn_DACK_deployment_difference_exactly_zero_on_this_cohort":True,
      "population_generalization_CANNOT_be_assumed_from_cohort_exact_equality":True,
      "source_model_sha256":p37.MODEL_SHA,
      "source_census_sha256":hashlib.sha256(census.read_bytes()).hexdigest(),
    }
    p.write_text(json.dumps(out,sort_keys=True,indent=2)+"\n")
    print("DACK_V37_READONLY_ACTION_SIGN_FAILURE_AUDIT_PASS",
         json.dumps(out,sort_keys=True),flush=True)

if __name__=="__main__":run()
