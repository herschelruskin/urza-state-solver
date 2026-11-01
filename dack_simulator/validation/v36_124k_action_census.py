#!/usr/bin/env python3
"""v36 124k random OUTCOME-BLIND exhaustive action census.

Census all 256 independent untouched game IDs × actual stages0,1,2
BEFORE generating one gameplay outcome. A one-step policy-value
comparison has EXACT contribution zero wherever old_action==new_action.
Preserve all 768 original decision states and 256 outer games in the
denominator, but only sample physically expensive KEEP outcomes at
disagreements. This is mathematically exact zero-regret pruning, not
a proxy for unknown outcome or a model change.
"""
from __future__ import annotations
from collections import Counter
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from dack_simulator.validation import v34_frozen_v33b_continuation as kernel
import dack_mulligan_v36_features as feat
import dack_mulligan_v36_keep_value as modelrun

LO=124000;HI=124255
SCHEMA="dack_v36_124k_frozen_actions_outcome_blind_census_v1"
def run():
    kernel.initialize()
    p=ROOT/"models/dack_v36_targeted_real_keep_EXPERIMENTAL.json"
    raw=p.read_bytes();model=modelrun.read_model(json.loads(raw))
    assert model["source_frozen_v33b_sha256"]==kernel.v33b.MODEL_SHA
    assert model["all_124k_holdout_unseen"]
    ref=kernel.ref;deck=ref.SLOT_VARIANTS[kernel.DECK_KEY]
    entries=[];different=[]
    for gid in range(LO,HI+1):
        seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
        seat,orders=ref.stage_slots(seed)
        for stage in (0,1,2):
            order=orders[stage]
            seven=tuple(deck[q] for q in order[:7])
            unknown=tuple(deck[q] for q in order[7:])
            assert len(unknown)==92
            assert Counter(seven)+Counter(unknown)==Counter(deck.values())
            original=kernel.current(seven,unknown,seat,stage)
            features=feat.extract(seven,original["hand"],original["bottom"],
                                  tuple(sorted(unknown)),seat,stage,
                                  original["old_v27_Qkeep"],original["old_v27_DP"])
            new,diag=modelrun.choose(model,features,seat,stage,
                  original["old_v27_keep"],original["old_v27_Qkeep"])
            row={"game_id":gid,"seat":seat,"stage":stage,
                 "keep_n":original["keep_n"],
                 "old_keep":bool(original["old_v27_keep"]),
                 "new_keep":bool(new),
                 "reason":diag["reason"],
                 "old_Qkeep":original["old_v27_Qkeep"],
                 "old_C":original["old_v27_DP"],
                 "keep_changed":bool(new)!=bool(original["old_v27_keep"])}
            if row["keep_changed"]:
                # Exact physical observed seven/hand/bottom needed for
                # the subsequent blind 92-future KEEP outcome collector.
                row.update({
                   "visible_seven":list(seven),
                   "chosen_v33b_hand":list(original["hand"]),
                   "chosen_v33b_bottom":list(original["bottom"]),
                   "predicted_delta_T2":diag["predicted_Qkeep_T2_median"]-
                                        diag["train_shared_C_T2"],
                })
                different.append(row)
            entries.append(row)
        if (gid-LO+1)%64==0:
            print("DACK_V36_124K_OUTCOME_BLIND_CENSUS_GROUPS",gid-LO+1,flush=True)
    assert len(entries)==256*3
    assert len(set((r["game_id"],r["stage"]) for r in entries))==len(entries)
    counts=Counter((r["stage"],r["reason"]) for r in different)
    out={
       "schema":SCHEMA,"status":"PASS",
       "all_game_ids":[LO,HI],"complete_independent_random_outer_groups":256,
       "all_stages_each_group":[0,1,2],"stage_states":768,
       "source_candidate_model_sha256":hashlib.sha256(raw).hexdigest(),
       "source_frozen_v33b_model_sha256":kernel.v33b.MODEL_SHA,
       "computed_before_any_124k_gameplay_outcomes":True,
       "original_124k_actual_sevens_unchanged":True,
       "do_not_discard_unchanged_actions_from_denominator":True,
       "unchanged_one_step_action_regret_is_EXACT_ZERO":True,
       "changed_actions":len(different),
       "changed_by_stage_reason":{f"{s}:{reason}":v for (s,reason),v in sorted(counts.items())},
       "all_decisions":entries,
       "policy_approved":False}
    dest=ROOT/"datasets/v36_124k_outcome_blind_action_census.json"
    dest.write_text(json.dumps(out,sort_keys=True,indent=2)+"\n")
    print("DACK_V36_124K_OUTCOME_BLIND_ZERO_REGRET_CENSUS_PASS",json.dumps({
      "changed_actions":len(different),"counts":out["changed_by_stage_reason"],
      "uncensored_population":768},sort_keys=True),flush=True)

if __name__=="__main__":run()
