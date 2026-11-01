#!/usr/bin/env python3
"""v37 PRE-OUTCOME selection of physical early KEEP/MULL training hands.

No gameplay rolls, real outcome labels, or 115k/117k/121k/124k.
256 independent random 126k physical groups × all stages 0,1,2.
Another 768 unique physical IDs are scanned for mismatch between
the FROZEN zero-beam v13 *proxy* of v5 and v27, then 128 physical
IDs are chosen (64 near-boundary discordant; 64 confident discordant).
The v13 proxy is NOT original actual v5, and is NOT a ground-truth
policy label. It serves ONLY as outcome-blind active-sampling heuristic.
Full 99-slot game IDs and actual London stages remain distinct.
"""
from __future__ import annotations
from collections import Counter
import json,hashlib,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from dack_simulator.validation import v34_frozen_v33b_continuation as kernel
from dack_simulator.validation.collect_teacher_london_v13 import finalists

RANDOM_IDS=(126000,126255)
POOL_IDS=(126256,127023)
SCHEMA="dack_v37_outcome_blind_three_strata_manifest_v1"

def teacher_vote(seven,unseen,seat,stage,sel):
    kn=int(kernel.ref.sim.STAGES[stage])
    opts=finalists(seven,kn,unseen)
    i=sel["v14_baseline_candidate_index"]
    assert i in range(len(opts))
    z=opts[i]
    xx=kernel.f.extract(seven,z["hand"],z["bottom"],Counter(unseen),
                seat,kn,stage,z["struct_rank"],i)
    vote=kernel.f.score_head(kernel.ctl.old.MODEL,"keep_trees",xx)
    cutoff=float(kernel.ctl.old.MODEL["keep_cutoff"])
    return vote,cutoff

def run():
    kernel.initialize()
    ref=kernel.ref;deck=ref.SLOT_VARIANTS[kernel.DECK_KEY]
    all_candidates=[]
    for gid in range(POOL_IDS[0],POOL_IDS[1]+1):
        seat,orders=ref.stage_slots(int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE)
        for stage in (0,1,2):
            seven=tuple(deck[s] for s in orders[stage][:7])
            unknown=tuple(deck[s] for s in orders[stage][7:])
            sel=kernel.current(seven,unknown,seat,stage)
            v,cut=teacher_vote(seven,unknown,seat,stage,sel)
            teacher=v>=cut
            old=bool(sel["old_v27_keep"])
            margin=float(sel["old_v27_Qkeep"]-sel["old_v27_DP"])
            if teacher==old:continue
            all_candidates.append({
                "game_id":gid,"seat":seat,"stage":stage,
                "v27_keep":old,"teacher_proxy_keep":teacher,
                "v27_margin":margin,"abs_margin":abs(margin),
                "proxy_teacher_score":v,"teacher_cutoff":cut,
            })
        if (gid-POOL_IDS[0]+1)%128==0:
            print("DACK_V37_OUTCOME_BLIND_TEACHER_PROXY_CANDIDATE_SCAN",
                  gid-POOL_IDS[0]+1,flush=True)
    used=set()
    selected=[]
    # Predeclared: choose 64 smallest original v27 decision margins
    # then 64 largest, among *different physical IDs* with opposite
    # actions from v13 proxy. Never select by physical win outcomes.
    for name,reverse in (("discordant_boundary",False),("discordant_confident",True)):
        eligible=sorted(all_candidates,key=lambda a:(
            -a["abs_margin"] if reverse else a["abs_margin"],
            a["game_id"],a["stage"]))
        n=0
        for r in eligible:
            if r["game_id"] in used:continue
            used.add(r["game_id"]);selected.append({"sample":name,**r})
            n+=1
            if n==64:break
        assert n==64,("not enough predecision v13-v27 policy disagreements",name,
                      len(all_candidates),n)
    assert len(used)==len(selected)==128
    random_entries=[{"game_id":gid,"sample":"unconditional_random",
            "stage":None} for gid in range(*[RANDOM_IDS[0],RANDOM_IDS[1]+1])]
    assert not set(x["game_id"] for x in random_entries)&used
    result={
      "schema":SCHEMA,"status":"PASS","policy_approved":False,
      "source_99_variant":kernel.DECK_KEY,
      "random_game_ids":list(RANDOM_IDS),
      "candidate_pool_game_ids":list(POOL_IDS),
      "n_random_groups":256,"n_discordant_enriched_groups":128,
      "n_candidate_disagreement_stage_states":len(all_candidates),
      "sample_64_near_and_64_far_margins":True,
      "selection_outcome_blind":True,
      "v13_is_proxy_NOT_original_v5":True,
      "no_teacher_action_used_as_training_label":True,
      "v33b_frozen_sha256":kernel.v33b.MODEL_SHA,
      "known_london_stages":[7,7,6,5,4,3,2,1],
      "random_groups":random_entries,"enriched_groups":selected,
      "stratum_action_stage_counts":{
       k:dict(Counter(str((r["stage"],int(r["v27_keep"]))) for r in selected if r["sample"]==k))
       for k in ("discordant_boundary","discordant_confident")
      }
    }
    p=ROOT/"datasets/v37_preoutcome_training_manifest.json"
    p.parent.mkdir(exist_ok=True,parents=True)
    p.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("DACK_V37_OUTCOME_BLIND_MANIFEST_PASS",
          json.dumps({"candidates":len(all_candidates),
          "groups":len(random_entries)+len(selected),
          "strata":result["stratum_action_stage_counts"]},sort_keys=True),flush=True)

if __name__=="__main__":run()
