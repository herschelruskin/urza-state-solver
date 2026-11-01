#!/usr/bin/env python3
"""v37 posthoc exploratory T2-vs-T3 blocked-state and actual path census.

127k HOLDOUT ALREADY INSPECTED: this is NOT independent policy validation.
Freeze identity of all 24 states where T2 predicted action would flip,
but T3 safeguard alone blocked. No physical outcome simulation.
Also replay deterministic hypothetical T2-only action policy on every
actual full London sequence; compare final hand+library to frozen v33b.
Any later physical labels are EXPLORATORY ONLY and cannot tune v37 on 127k.
"""
from __future__ import annotations
import hashlib,json,sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from dack_simulator.validation import v34_frozen_v33b_continuation as kernel
import dack_mulligan_v37_features as feats
import dack_mulligan_v37_direct_regret as modelrun
import dack_paired_counterfactual_v37_direct_regret_20261101 as v37

SCHEMA="dack_v37_posthoc_127k_T3_only_blocked_action_census_exploratory"
def decide_T2_only(seven,unknown,seat,stage,sel):
    if stage>=3:return bool(sel["old_v27_keep"])
    x=feats.extract(seven,unknown,seat,stage,sel)
    a2,a3=modelrun.predict(v37.MODEL,x)
    old=bool(sel["old_v27_keep"])
    if not old and a2[modelrun.N//4]>modelrun.T2_DEADBAND:return True
    if old and a2[3*modelrun.N//4]<-modelrun.T2_DEADBAND:return False
    return old

def run():
    v37.audit();ref=kernel.ref;deck=ref.SLOT_VARIANTS[kernel.DECK_KEY]
    original=json.loads((ROOT/"datasets/v37_127k_outcome_blind_census.json").read_text())
    assert original["status"]=="PASS" and original["changed_stage_decisions"]==0
    blocked=[];otherT2=[];altchanged=[]
    for gid in range(127200,127456):
        seat,orders=ref.stage_slots(int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE)
        for stage in (0,1,2):
            seven=tuple(deck[q] for q in orders[stage][:7])
            unknown=tuple(deck[q] for q in orders[stage][7:])
            sel=kernel.current(seven,unknown,seat,stage)
            x=feats.extract(seven,unknown,seat,stage,sel)
            q2,q3=modelrun.predict(v37.MODEL,x)
            old=bool(sel["old_v27_keep"])
            t2flipped=decide_T2_only(seven,unknown,seat,stage,sel)!=old
            full,details=modelrun.decide(v37.MODEL,x,stage,old)
            assert full==old
            if t2flipped:
                assert (old and q3[modelrun.N//2]>modelrun.T3_ALLOWED_LOSS) or (
                        not old and q3[modelrun.N//2]<-modelrun.T3_ALLOWED_LOSS)
                blocked.append({
                   "game_id":gid,"seat":seat,"stage":stage,
                   "old_v27_KEEP":old,
                   "new_T2_only_KEEP":not old,
                   "visible_seven":list(seven),
                   "v33b_kept_hand":list(sel["hand"]),
                   "v33b_bottom":list(sel["bottom"]),
                   "v37_pred_T2_lower":q2[modelrun.N//4],
                   "v37_pred_T2_median":q2[modelrun.N//2],
                   "v37_pred_T2_upper":q2[3*modelrun.N//4],
                   "v37_pred_T3_median":q3[modelrun.N//2],
                })
        # Actual complete London path under counterfactual T2-only override.
        base,history=kernel.v33b.choose_keep(deck,seat,orders)
        path=[]
        for s,(kn,order) in enumerate(zip(ref.sim.STAGES,orders)):
            seven=tuple(deck[q] for q in order[:7])
            unknown=tuple(deck[q] for q in order[7:])
            sel=kernel.current(seven,unknown,seat,s)
            keep=decide_T2_only(seven,unknown,seat,s,sel)
            path.append({"stage":s,"old_keep":sel["old_v27_keep"],"new_keep":keep})
            if keep:
                newstate=kernel.state_from(seven,unknown,sel)
                break
        assert path[-1]["new_keep"]
        if base.hand!=newstate.hand or base.library!=newstate.library:
            assert any(x["old_keep"]!=x["new_keep"] for x in path)
            altchanged.append({"game_id":gid,"seat":seat,
                "old_final_stage":history[-1]["stage"],
                "T2_only_final_stage":path[-1]["stage"],
                "altered_reached_stages":[z["stage"] for z in path
                         if z["old_keep"]!=z["new_keep"]]})
    assert len(blocked)==24,(len(blocked),"audited count of T3-only blocked actions changed")
    assert len(set((x["game_id"],x["stage"]) for x in blocked))==24
    assert all(x["stage"] in (0,1,2) for x in blocked)
    source=ROOT/"models/dack_v37_direct_regret_EXPERIMENTAL.json"
    report={
       "schema":SCHEMA,"status":"PASS","policy_approved":False,
       "posthoc_127k_diagnostic_not_independent_validation":True,
       "no_physical_gameplay_outcomes_generated":True,
       "number_T2_gate_passed_T3_only_blocked":len(blocked),
       "actual_256_game_complete_London_final_state_changed_by_T2_only_override":len(altchanged),
       "actual_full_London_difference_games":altchanged,
       "required_C_cells_for_blocked_actions":sorted(
          {f"{x['seat']}:{x['stage']}" for x in blocked}),
       "blocked_visible_actions":blocked,
       "source_model_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
       "original_127k_census_sha256":hashlib.sha256(
           (ROOT/"datasets/v37_127k_outcome_blind_census.json").read_bytes()).hexdigest(),
       "T3_only_posthoc_relaxation_NOT_validated_for_deployment":True
    }
    p=ROOT/"datasets/v37_POSTHOC_T3_blocked_physical_diagnostic_manifest.json"
    p.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print("DACK_V37_POSTHOC_T3_BLOCKER_REACHABILITY_PASS",
          json.dumps({"blocked":len(blocked),"actual_London_paths_changed":len(altchanged),
          "cells":report["required_C_cells_for_blocked_actions"]},sort_keys=True),flush=True)
if __name__=="__main__":run()
