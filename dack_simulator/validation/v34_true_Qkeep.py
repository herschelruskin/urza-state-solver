#!/usr/bin/env python3
"""v34 evaluate Q(KEEP) with actual selected v33b bottom and true futures.

Sample ALL seven decision-capable London stages (0..6), including
hypothetically unvisited stages. For each stage choose the EXACT
current v14-based v27 Qkeep and fixed v33b bottom, without seeing
the order of the next 92 physical cards. Sample eight independent
unseen-92 futures and stable dice, unchanged strict game beam160.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,random,sys,time
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from dack_simulator.validation import v34_frozen_v33b_continuation as kernel

PROTO="DACK_V34_QKEEP_UNBIASED_PHYSICAL_STAGE_SAMPLE_V1"
SPLITS={"train":(116000,116063),
        "untouched_validation":(117000,117031)}
FUTURES=8;SHARD=4

def one(gid,split):
    ref=kernel.ref; deck=ref.SLOT_VARIANTS[kernel.DECK_KEY]
    seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
    seat,orders=ref.stage_slots(seed)
    rows=[]
    for stage in range(7):
        kn=int(ref.sim.STAGES[stage])
        order=orders[stage]
        seven=tuple(deck[x] for x in order[:7])
        unseen=tuple(deck[x] for x in order[7:])
        assert len(seven)==7 and len(unseen)==92
        assert Counter(seven)+Counter(unseen)==Counter(deck)
        sel=kernel.current(seven,unseen,seat,stage)
        # No path's realized cards can leak to the policy: unknown is
        # available as counts only to current().
        trials=[]
        for future in range(FUTURES):
            sh=list(unseen)
            random.Random(kernel.stable_seed(
                "q_keep_new_unseen92",split,gid,stage,future)).shuffle(sh)
            state=kernel.state_from(seven,tuple(sh),sel)
            ref.sim.reset_caches();ref.sim.root.install(kernel.DECK_KEY)
            ref.sim.m.set_trial_seed(kernel.stable_seed(
                "q_keep_blind_effects",split,gid,stage,future))
            turn=int(ref.d._win_turn_from_unknown_order(
                state.hand,state.library,seat,beam=160,max_turn=3) or 0)
            assert turn in (0,1,2,3)
            trials.append(turn)
        rows.append({
           "game_id":gid,"seat":seat,"stage":stage,"keep_n":kn,
           "seven":list(seven),
           "selected_v33b_hand":list(sel["hand"]),
           "selected_v33b_bottom":list(sel["bottom"]),
           "selected_v14_hand":list(sel["v14_hand"]),
           "selected_v14_bottom":list(sel["v14_bottom"]),
           "v33b_overrode_bottom":sel["v33b_overrode_bottom"],
           "v27_pred_Qkeep_T2":sel["old_v27_Qkeep"],
           "v27_DP_threshold":sel["old_v27_DP"],
           "v27_would_keep":sel["old_v27_keep"],
           "outcomes":trials,
           "empirical_Qkeep_T1":sum(x==1 for x in trials)/FUTURES,
           "empirical_Qkeep_T2":sum(0<x<=2 for x in trials)/FUTURES,
           "empirical_Qkeep_T3":sum(0<x<=3 for x in trials)/FUTURES
        })
    return rows

def run(split,start,out):
    if split not in SPLITS:raise ValueError("split unknown")
    lo,hi=SPLITS[split]
    if not lo<=start<=hi or start+SHARD-1>hi or (start-lo)%SHARD:
        raise ValueError("four-game reserved complete-shard restriction")
    kernel.initialize()
    assert len(kernel.ref.SLOTS)==99 and kernel.ref.SPEC["beam"]==160
    t0=time.monotonic()
    rows=[]
    for gid in range(start,start+SHARD):
        rows.extend(one(gid,split))
        print("DACK_V34_QKEEP_PHYSICAL_GAME",split,gid,
              "all_stages",7,"elapsed",round(time.monotonic()-t0,2),flush=True)
    assert len(rows)==SHARD*7
    result={
       "schema":"dack_v34_true_Qkeep_frozen_v33b_all_stages",
       "status":"PASS","split":split,
       "game_ids":[start,start+SHARD-1],
       "physical_groups":SHARD,"stages":list(range(7)),
       "futures_per_stage":FUTURES,"actual_beam160":True,
       "all_stages_sampled_independent_of_actual_keeping":True,
       "current_hand_selection_uses_only_seven_and_unseen_multiset":True,
       "known_92_multiset_physically_shuffled_for_outcome":True,
       "frozen_v27_Qkeep_and_bottom_v33b":True,
       "separate_future_draws_per_stage":True,
       "v33b_model_sha256":kernel.v33b.MODEL_SHA,
       "v27_model_sha256":hashlib.sha256((ROOT/kernel.v33b.frozen.MODEL).read_bytes()).hexdigest(),
       "not_full_game_policy_evaluation":True,
       "no_policy_training_or_adaptation_in_rollout":True,
       "policy_approved":False,"rows":rows}
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,"wt") as f:json.dump(result,f,sort_keys=True)
    print("DACK_V34_QKEEP_SHARD_PASS",split,start,flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--split",choices=list(SPLITS),required=True)
    p.add_argument("--start",type=int,required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args();run(a.split,a.start,a.out)
