#!/usr/bin/env python3
"""v34 true shared Q(MULL) under the EXACT unchanged v33b downstream policy.

The rejected seven is fully returned to the real 99. Future sevens
freshly reshuffle all 99, so Q(MULL) is a (seat,stage) constant under
the fixed downstream policy, independent of rejected hand identity.
No v5 rollout, no decision-boundary training, no policy updates.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,time,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from dack_simulator.validation import v34_frozen_v33b_continuation as kernel

PROTO="DACK_V34_SHARED_QMULL_FIXED_V33B_POLICY_1"
N_TRAIN=64;N_VALID=32
def one(seat,stage,out):
    assert 0<=seat<4 and 0<=stage<7
    kernel.initialize()
    ref=kernel.ref
    assert len(ref.SLOTS)==99 and ref.SPEC["beam"]==160
    rows=[];t0=time.monotonic()
    for split,n in (("train",N_TRAIN),("untouched_validation",N_VALID)):
        for j in range(n):
            orders=kernel.later_orders(seat,stage,j,split)
            state,history=kernel.continue_from(stage+1,seat,orders)
            assert history and history[0]["stage"]==stage+1
            assert history[-1]["kept"]
            ref.sim.reset_caches();ref.sim.root.install(kernel.DECK_KEY)
            ref.sim.m.set_trial_seed(kernel.stable_seed(
                "q_mull_gameplay_effects",seat,stage,j,split))
            turn=int(ref.d._win_turn_from_unknown_order(
                state.hand,state.library,seat,beam=160,max_turn=3) or 0)
            assert turn in (0,1,2,3)
            rows.append({"split":split,"trial":j,"turn":turn,
                "kept_at_actual_london_stage":history[-1]["stage"]})
        print("DACK_V34_QMULL_SEAT_STAGE_SPLIT_PASS",seat,stage,split,n,
              round(time.monotonic()-t0,2),flush=True)
    assert len(rows)==N_TRAIN+N_VALID
    saved={
       "schema":"dack_v34_shared_Qmull_exact_frozen_v33b_downstream",
       "status":"PASS","seat":seat,"stage":stage,
       "training_futures":N_TRAIN,"validation_futures":N_VALID,
       "strict_beam160":True,"all_99_returned_each_future_stage":True,
       "actual_seat_and_london_stage_used":True,
       "rejected_visible_hand_not_used_in_future_shuffles":True,
       "downstream_policy":"frozen_v27_all_stage_KEEP_plus_frozen_v33b_bottom",
       "downstream_policy_matched_for_training_validation":True,
       "T2_primary_T3_safeguard":True,
       "no_engine_changes":True,"policy_approved":False,
       "v33b_model_sha256":kernel.v33b.MODEL_SHA,
       "source_sha256":{
         "v27_value":hashlib.sha256((ROOT/kernel.v33b.frozen.MODEL).read_bytes()).hexdigest(),
         "v27_continuation":hashlib.sha256((ROOT/kernel.v33b.frozen.DP).read_bytes()).hexdigest()},
       "results":rows}
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,"wt") as f:json.dump(saved,f,sort_keys=True)
    print("DACK_V34_QMULL_SHARD_PASS",seat,stage,flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--seat",type=int,required=True)
    p.add_argument("--stage",type=int,required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args();one(a.seat,a.stage,a.out)
