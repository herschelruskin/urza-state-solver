#!/usr/bin/env python3
"""v36 pre-outcome stratified physical training selection, no game rollouts.

Include 128 unconditional independent 123k physical groups and
128 near-boundary physical groups from a distinct 512-game candidate pool.
The pool is selected using ONLY visible-sevens / frozen-v27 estimates,
never realized outcomes, never a v5 policy decision or later deal outcome.
3 independent actual London sevens per group, stage0 and stage1 distinct.

Balance the selected stage/old-action categories so the training
covers both original keep and original mull actions at stages0..2.
Targeted groups improve coverage; ONLY the unbiased random stratum
or fresh independent 124k holdout measures population performance.
"""
from __future__ import annotations
import hashlib,json,sys
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from dack_simulator.validation import v34_frozen_v33b_continuation as kernel

LO_RANDOM=123000
HI_RANDOM=123127
LO_POOL=123128
HI_POOL=123639
QUOTAS={0:24,1:20,2:20}
SCHEMA="dack_v36_preoutcome_stratified_123k_physical_training_manifest_1"

def main():
    kernel.initialize()
    ref=kernel.ref
    deck=ref.SLOT_VARIANTS[kernel.DECK_KEY]
    scored=[]
    for gid in range(LO_POOL,HI_POOL+1):
        game_seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
        seat,orders=ref.stage_slots(game_seed)
        candidates=[]
        for stage in (0,1,2):
            seven=tuple(deck[slot] for slot in orders[stage][:7])
            unknown=tuple(deck[slot] for slot in orders[stage][7:])
            sel=kernel.current(seven,unknown,seat,stage)
            candidates.append({
                "stage":stage,"seat":seat,
                "base_keep":sel["old_v27_keep"],
                "base_margin":sel["old_v27_Qkeep"]-sel["old_v27_DP"],
            })
        scored.append({"gid":gid,"seat":seat,"stages":candidates})
        if (gid-LO_POOL+1)%128==0:
            print("DACK_V36_VISIBLE_ONLY_SELECTION_POOL_AUDITED",gid,flush=True)
    chosen={}
    # Predeclared balance quotas, each group selected at most once.
    for stage in (0,1,2):
        for keep in (True,False):
            candidates=sorted(
                (r for r in scored if r["gid"] not in chosen
                     and r["stages"][stage]["base_keep"]==keep),
                key=lambda r:(abs(r["stages"][stage]["base_margin"]),r["gid"]))
            quota=QUOTAS[stage]
            assert len(candidates)>=quota,("insufficient precommitted stratum",stage,keep,len(candidates))
            for r in candidates[:quota]:
                chosen[r["gid"]]={
                  "selection_stage":stage,"original_v27_keep":keep,
                  "absolute_margin":abs(r["stages"][stage]["base_margin"]),
                }
    assert len(chosen)==128
    assert len(set(chosen).intersection(range(LO_RANDOM,HI_RANDOM+1)))==0
    groups=[{"game_id":gid,"sample":"random","selection":None}
            for gid in range(LO_RANDOM,HI_RANDOM+1)]
    groups.extend({"game_id":gid,"sample":"boundary_enriched",
                   "selection":chosen[gid]} for gid in sorted(chosen))
    assert len(groups)==256
    label_counts=Counter((x["selection"]["selection_stage"],
                          x["selection"]["original_v27_keep"])
               for x in groups if x["selection"] is not None)
    assert all(label_counts[(s,k)]==n for s,n in QUOTAS.items() for k in (True,False))
    out={
      "schema":SCHEMA,"status":"PASS",
      "source_99_deck":"one_key_34",
      "frozen_v33b_bottom_sha256":kernel.v33b.MODEL_SHA,
      "random_unconditional_physical_ids":[LO_RANDOM,HI_RANDOM],
      "candidate_pool_ids":[LO_POOL,HI_POOL],
      "selected_near_boundary_count":128,
      "random_unconditional_count":128,
      "selection_by_predecision_features_only":True,
      "no_gameplay_rollouts_at_selection":True,
      "outcome_blind_balanced_seat_stage_action_strata":True,
      "selection_quotas_per_action_per_stage":{str(k):v for k,v in QUOTAS.items()},
      "labels_available_only_after_manifest_frozen":True,
      "stage0_stage1_separate":True,
      "per_action_selection_counts":{f"{s}:{int(k)}":v for (s,k),v in sorted(label_counts.items())},
      "groups":groups}
    p=ROOT/"datasets/v36_preoutcome_123k_manifest.json"
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(out,sort_keys=True,indent=2)+"\n")
    print("DACK_V36_PREOUTCOME_MANIFEST_PASS",json.dumps({
      "total_groups":len(groups),"selected":len(chosen),
      "strata":out["per_action_selection_counts"]},sort_keys=True),flush=True)

if __name__=="__main__":main()
