#!/usr/bin/env python3
"""v36 read-only gate attribution and complete London path equivalence.

No new physical game outcomes, no feature or threshold tuning.
All 256 random 124k outer physical seeds, all stage0/1/2 seven
observations. Attribute why original v27 action was/wasn't changed:
 - model median T2 advantage favors original action,
 - opposite-sign but fails T2 lower/upper quartile+shared C buffer,
 - passes T2 but T3 safeguard blocks,
 - passes both and actually changes.
Then replay COMPLETE REAL London choices with frozen v33b and
v36 under EXACT same 99 physical deal stages, no game beam.
When both return identical physical final hand+library, actual
strict beam160 deterministic deployment MUST match, without
spending any simulation budget.
"""
from __future__ import annotations
from collections import Counter,defaultdict
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from dack_simulator.validation import v34_frozen_v33b_continuation as kernel
import dack_mulligan_v36_keep_value as runtime
import dack_mulligan_v36_features as feats
import dack_paired_counterfactual_v36_targeted_keep_20261101 as v36

CENSUS=ROOT/"datasets/v36_124k_outcome_blind_action_census.json"

def run():
    v36.audit()
    ref=kernel.ref
    raw=v36.MODEL_PATH.read_bytes();model=runtime.read_model(json.loads(raw))
    census=json.loads(CENSUS.read_text())
    assert census["schema"]=="dack_v36_124k_frozen_actions_outcome_blind_census_v1"
    assert census["status"]=="PASS" and census["stage_states"]==768
    assert census["source_candidate_model_sha256"]==hashlib.sha256(raw).hexdigest()
    cmap={(r["game_id"],r["stage"]):r for r in census["all_decisions"]}
    assert len(cmap)==768
    count=Counter();perstage=defaultdict(Counter)
    livechanged=[]
    physicallyidentical=0
    physicallydifferent=0
    for gid in range(124000,124256):
        seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
        seat,orders=ref.stage_slots(seed)
        deck=ref.SLOT_VARIANTS[kernel.DECK_KEY]
        for stage in (0,1,2):
            seven=tuple(deck[s] for s in orders[stage][:7])
            unknown=tuple(deck[s] for s in orders[stage][7:])
            sel=kernel.current(seven,unknown,seat,stage)
            xx=feats.extract(seven,sel["hand"],sel["bottom"],tuple(sorted(unknown)),
                     seat,stage,sel["old_v27_Qkeep"],sel["old_v27_DP"])
            old=bool(sel["old_v27_keep"])
            q2,q3=runtime.predictions(model,xx,sel["old_v27_Qkeep"])
            c=model["C_by_seat_stage"][f"{seat}:{stage}"]
            c2=float(c["T2"]);c3=float(c["T3"])
            se2=(c2*(1-c2)/128)**.5
            median2=q2[runtime.ENSEMBLE//2]-c2
            if old:
                favors_opposite=median2<0
                T2_pass=q2[3*runtime.ENSEMBLE//4]-c2+runtime.C_STDERR_MULT*se2<-runtime.T2_DEADBAND
                T3_pass=q3[3*runtime.ENSEMBLE//4]-c3<=runtime.T3_MAX_LOSS
            else:
                favors_opposite=median2>0
                T2_pass=q2[runtime.ENSEMBLE//4]-c2-runtime.C_STDERR_MULT*se2>runtime.T2_DEADBAND
                T3_pass=q3[runtime.ENSEMBLE//4]-c3>=-runtime.T3_MAX_LOSS
            new,diag=runtime.choose(model,xx,seat,stage,old,sel["old_v27_Qkeep"])
            assert new==cmap[(gid,stage)]["new_keep"]
            assert old==cmap[(gid,stage)]["old_keep"]
            assert new!=old if T2_pass and T3_pass else new==old
            if not favors_opposite:
                reason="T2_prediction_favors_original"
            elif not T2_pass:
                reason="opposite_T2_but_stability_or_C_margin_insufficient"
            elif not T3_pass:
                reason="T2_supports_override_but_T3_safeguard_blocks"
            else:
                reason="both_gates_pass_real_override"
            count[reason]+=1;perstage[stage][reason]+=1
        # Main physical mulligan path must remain EXACT if no
        # stage0..2 action was changed, even when unvisited
        # counterfactual future stage values differed.
        old_state,oldhist=kernel.v33b.choose_keep(deck,seat,orders)
        new_state,newhist=v36.choose_keep(deck,seat,orders)
        actual_different=(
            len(oldhist)!=len(newhist)
            or old_state.hand!=new_state.hand
            or old_state.library!=new_state.library
        )
        if actual_different:
            physicallydifferent+=1
            livechanged.append({
              "gid":gid,"old_kept_actual_stage":oldhist[-1]["stage"],
              "new_kept_actual_stage":newhist[-1]["stage"],
              "new_reasons":[r["v36_action_diagnostic"]["reason"] for r in newhist
                             if r["v36_action_diagnostic"]["reason"].startswith("v36_real_action")],
            })
            assert any(cmap[(gid,s)]["keep_changed"] for s in (0,1,2))
        else:
            physicallyidentical+=1
            assert old_state.hand==new_state.hand and old_state.library==new_state.library
    assert physicallyidentical+physicallydifferent==256
    assert sum(count.values())==768
    assert count["both_gates_pass_real_override"]==census["changed_actions"]==2
    report={
      "schema":"dack_v36_readonly_gate_and_actual_London_path_attribution_124k",
      "status":"PASS",
      "no_actual_gameplay_beam_calls":True,"no_model_refitting":True,
      "n_total_random_independent_outer_groups":256,
      "n_all_actual_early_stages":768,
      "action_reason_counts":dict(count),
      "reason_by_actual_london_stage":{str(s):dict(d) for s,d in sorted(perstage.items())},
      "actual_London_final_physical_hand_and_library_identical_games":physicallyidentical,
      "actual_London_final_physical_hand_or_library_DIFFERENT_games":physicallydifferent,
      "different_actual_path_detail":livechanged,
      "cohort_specific_max_full_game_T2_delta_pp":100*physicallydifferent/256,
      "cohort_specific_max_one_step_uniform_conditional_T2_delta_pp":100*2/768,
      "same_final_hand_and_library_guarantees_same_game_outcome_under_same_seed":True,
      "future_distribution_changed_policy_Bellman_not_evaluated":True,
      "model_sha256":hashlib.sha256(raw).hexdigest(),
      "unapproved_policy":True,
      "limitations":[
         "These are empirical cohort-specific action-coverage upper bounds, not population CI",
         "Census includes hypothetical stages that may not be visited by actual policies",
         "Strict causal difference of final physical state is deterministic only for fixed actual game seeds",
         "Gate decomposition is a posthoc read-only analysis, not a new trained candidate"]
    }
    p=ROOT/"benchmark_results/v36_124k_readonly_gates_and_actual_path.json"
    p.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print("DACK_V36_READONLY_LONDON_PATH_AND_ACTION_GATE_AUDIT_PASS",
          json.dumps(report,sort_keys=True),flush=True)

if __name__=="__main__":run()
