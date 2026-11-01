#!/usr/bin/env python3
"""v37 127k complete outcome-blind direct action-regret census and London paths.

All 256 NEW physical game IDs × actual London stages0,1,2,
including hypothetically unvisited states; original v27 decisions
versus FROZEN v37 signed physical KEEP-minus-MULL learner.
Before any 127k outcome, record EXACT action differences and
whether the actual final kept hand+physical library differs from
v33b. Identical final physical states have identical outcome under
same beam160/stable chance seed; no gameplay needed for those cases.
"""
from __future__ import annotations
import hashlib,json,sys
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from dack_simulator.validation import v34_frozen_v33b_continuation as kernel
import dack_mulligan_v37_direct_regret as modelrun
import dack_mulligan_v37_features as feat
import dack_paired_counterfactual_v37_direct_regret_20261101 as p37

LO=127200;HI=127455
SCHEMA="dack_v37_127k_unseen_complete_outcome_blind_action_census_v1"

def run():
    p37.audit()
    m=p37.MODEL;ref=kernel.ref;deck=ref.SLOT_VARIANTS[kernel.DECK_KEY]
    rows=[];changed=[];real_changes=[]
    reasons=Counter();by_stage=defaultdict(Counter)
    for gid in range(LO,HI+1):
        seat,orders=ref.stage_slots(int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE)
        for stage in (0,1,2):
            seven=tuple(deck[s] for s in orders[stage][:7])
            unknown=tuple(deck[s] for s in orders[stage][7:])
            assert len(unknown)==92
            sel=kernel.current(seven,unknown,seat,stage)
            x=feat.extract(seven,unknown,seat,stage,sel)
            new,d=modelrun.decide(m,x,stage,sel["old_v27_keep"])
            rec={
              "game_id":gid,"seat":seat,"stage":stage,
              "old_keep":bool(sel["old_v27_keep"]),
              "new_keep":bool(new),"changed":bool(new)!=bool(sel["old_v27_keep"]),
              "reason":d["reason"],
              "v27_margin":sel["old_v27_Qkeep"]-sel["old_v27_DP"],
              "pred_adv_T2":d["pred_adv_T2_med"],
              "pred_adv_T3":d["pred_adv_T3_med"],
            }
            if rec["changed"]:
                rec.update({
                  "visible_seven":list(seven),
                  "v33b_hand":list(sel["hand"]),
                  "v33b_bottom":list(sel["bottom"]),
                })
                changed.append(rec)
            rows.append(rec)
            reasons[d["reason"]]+=1;by_stage[stage][d["reason"]]+=1
        # Actual runtime London path, no beam160 deployment here.
        state0,h0=kernel.v33b.choose_keep(deck,seat,orders)
        state1,h1=p37.choose_keep(deck,seat,orders)
        if state0.hand!=state1.hand or state0.library!=state1.library:
            real_changes.append({
               "game_id":gid,"seat":seat,
               "v33b_kept_actual_stage":h0[-1]["stage"],
               "v37_kept_actual_stage":h1[-1]["stage"],
               "old_final_hand":list(state0.hand),
               "new_final_hand":list(state1.hand),
            })
            assert any(r["changed"] for r in rows[-3:])
        else:
            assert state0.hand==state1.hand and state0.library==state1.library
        if (gid-LO+1)%64==0:
            print("DACK_V37_127K_PREOUTCOME_CENSUS_RANDOM_GROUPS",gid-LO+1,flush=True)
    assert len(rows)==256*3
    assert len({(r["game_id"],r["stage"]) for r in rows})==768
    assert sum(reasons.values())==768
    data={
      "schema":SCHEMA,"status":"PASS","policy_approved":False,
      "game_ids":[LO,HI],"random_physical_outer_groups":256,
      "random_stage_states":768,"all_early_actual_stage_indices":[0,1,2],
      "model_sha256":p37.MODEL_SHA,
      "source_v33b_sha256":kernel.v33b.MODEL_SHA,
      "no_127k_actual_game_outcomes_sampled":True,
      "no_holdout_model_tuning":True,
      "all_observed_actions_and_stages_preserved":True,
      "unchanged_action_exact_zero_regret":True,
      "changed_stage_decisions":len(changed),
      "changed_reached_final_physical_games":len(real_changes),
      "reason_counts":dict(reasons),
      "by_stage":{str(stage):dict(v) for stage,v in by_stage.items()},
      "changed_real_London_game_details":real_changes,
      "complete_stage_rows":rows,
      "gate_required_min_changed_stage_states":12,
      "gate_required_min_changed_actual_London_games":5,
      "coverage_prerequisite_satisfied":len(changed)>=12 and len(real_changes)>=5,
    }
    dest=ROOT/"datasets/v37_127k_outcome_blind_census.json"
    dest.write_text(json.dumps(data,sort_keys=True,indent=2)+"\n")
    print("DACK_V37_127K_PREOUTCOME_CENSUS_PASS",json.dumps({
       "changed_stages":len(changed),"changed_reached_actual_games":len(real_changes),
       "coverage_prerequisite_satisfied":data["coverage_prerequisite_satisfied"],
       "reason_counts":dict(reasons)},sort_keys=True),flush=True)

if __name__=="__main__":run()
