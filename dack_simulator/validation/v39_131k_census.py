#!/usr/bin/env python3
"""v39 before-outcomes full 131k 1024-group physical London action census.

Whole 131000..132023 random IDs × early stages0/1/2, no game beam.
Save each changed action, final-deck divergence, and original
unconditional denominator. Selection is based entirely on observed
opening sevens and frozen model estimates and is independent of
realized physical outcomes. Never use 127k descriptive outcomes to
tune or label this 131k validation.
"""
from __future__ import annotations
from collections import Counter
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from dack_simulator.validation import v34_frozen_v33b_continuation as kernel
import dack_paired_counterfactual_v39_t2_risk_regret_20261101 as policy
import dack_mulligan_v37_features as feats
import dack_mulligan_v39_t2_risk_regret as opt

LO=131000
HI=132023
SCHEMA="dack_v39_131k_new_random_1024_outcome_blind_census_v1"

def run():
    policy.audit()
    ref=kernel.ref;deck=ref.SLOT_VARIANTS[kernel.DECK_KEY]
    entries=[];differ=[];live=[]
    for gid in range(LO,HI+1):
        seat,orders=ref.stage_slots(int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE)
        for stage in (0,1,2):
            seen=tuple(deck[x] for x in orders[stage][:7])
            unseen=tuple(deck[x] for x in orders[stage][7:])
            orig=kernel.current(seen,unseen,seat,stage)
            xx=feats.extract(seen,unseen,seat,stage,orig)
            new,diag=opt.choose(policy.MODEL,xx,stage,orig["old_v27_keep"])
            changed=new!=orig["old_v27_keep"]
            row={
              "game_id":gid,"seat":seat,"stage":stage,
              "old_keep":bool(orig["old_v27_keep"]),"new_keep":bool(new),
              "changed":bool(changed),
              "reason":diag["reason"],
              "pred_A2_med":diag["T2_median"],
              "pred_A2_lower":diag["T2_lower_quartile"],
              "pred_A2_upper":diag["T2_upper_quartile"],
              "pred_A3_med":diag["T3_median"],
              "old_v27_margin":orig["old_v27_Qkeep"]-orig["old_v27_DP"]
            }
            entries.append(row)
            if changed:
                row.update({
                  "visible_seven":list(seen),
                  "v33b_kept_hand":list(orig["hand"]),
                  "v33b_bottom":list(orig["bottom"]),
                })
                differ.append(row)
        state0,hist0=kernel.v33b.choose_keep(deck,seat,orders)
        state1,hist1=policy.choose_keep(deck,seat,orders)
        altered=state0.hand!=state1.hand or state0.library!=state1.library or len(hist0)!=len(hist1)
        if altered:
            live.append({
              "game_id":gid,"seat":seat,
              "old_actual_final_stage":hist0[-1]["stage"],
              "new_actual_final_stage":hist1[-1]["stage"],
              "old_keep_n":hist0[-1]["keep_n"],
              "new_keep_n":hist1[-1]["keep_n"],
            })
            assert any(row["changed"] for row in entries[-3:])
        else:
            assert state0.hand==state1.hand and state0.library==state1.library
        if (gid-LO+1)%256==0:
            print("DACK_V39_NO_OUTCOMES_RANDOM_GROUP_CENSUS",gid-LO+1,flush=True)
    assert len(entries)==(HI-LO+1)*3==3072
    assert len(set((r["game_id"],r["stage"]) for r in entries))==3072
    counts=Counter(r["reason"] for r in entries)
    bystage={str(s):dict(Counter(r["reason"] for r in entries if r["stage"]==s)) for s in (0,1,2)}
    out={
      "schema":SCHEMA,"status":"PASS","policy_approved":False,
      "physical_game_ids":[LO,HI],"physical_random_outer_groups":1024,
      "random_stage_state_denominator":3072,
      "all_three_London_stages_observed_in_each_group":True,
      "frozen_v37_direct_regret_model_sha256":policy.MODEL_SHA,
      "frozen_v33b_bottom_sha256":kernel.v33b.MODEL_SHA,
      "unchanged_actual_seeded_full_hand_library_implies_identical_gameplay":True,
      "no_full_game_or_counterfactual_rollouts_at_selection":True,
      "previous_127k_selected_physical_results_not_used":True,
      "real_99_slot_deck":kernel.DECK_KEY,
      "objective":"T2 first with 25pp predicted per-action T3 decline cap",
      "actual_action_changes":len(differ),
      "changed_actual_London_path_games":len(live),
      "maximum_possible_full_game_cohort_delta_pp":100*len(live)/1024,
      "maximum_possible_early_stage_uniform_delta_pp":100*len(differ)/3072,
      "action_reason_counts":dict(counts),
      "reason_counts_by_stage":bystage,
      "real_actual_London_path_divergences":live,
      "all_early_stage_decisions":entries
    }
    dest=ROOT/"datasets/v39_131k_frozen_outcome_blind_census.json"
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(out,sort_keys=True,indent=2)+"\n")
    print("DACK_V39_UNSEEN_N1024_ACTION_CENSUS_PASS",json.dumps({
      "states":3072,"changed_actions":len(differ),
      "actual_path_changed_games":len(live),
      "reasons":dict(counts),"by_stage":bystage
    },sort_keys=True),flush=True)

if __name__=="__main__":run()
