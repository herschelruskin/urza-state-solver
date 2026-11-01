#!/usr/bin/env python3
"""v36 physically sampled shared Q(MULL): frozen v27 future/v33b bottoms.

Seat-stage C independent of rejected opening seven because each rejected
seven returns to full 99, and all future London sevens are independently
shuffled from full 99. No current-hand or actual future game order peeking.
Train C has 128 futures/cell, disjoint 124k holdout C 64/cell.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,random,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from dack_simulator.validation import v34_frozen_v33b_continuation as kernel

SCHEMA="dack_v36_physical_shared_frozen_v33b_Qmull_1"
FUTURES={"train":128,"holdout":64}
PROTO="DACK_V36_123K_124K_DISJOINT_FULL99_QMULL_V1"

def seed(*args):
    return int.from_bytes(hashlib.sha256(json.dumps(
       (PROTO,*args),separators=(",",":")).encode()).digest()[:8],"big")

def run(split,seat,stage,out):
    if split not in FUTURES or seat not in range(4) or stage not in (0,1,2):
        raise ValueError("v36 C must have train/holdout seat0..3 stage0..2")
    kernel.initialize()
    ref=kernel.ref
    assert ref.SPEC["beam"]==160 and len(ref.SLOTS)==99
    started=time.monotonic();turns=[];later_stages=[]
    for j in range(FUTURES[split]):
        orders=[]
        for later in range(stage+1,8):
            slot=list(ref.SLOTS)
            random.Random(seed("future_full99",split,seat,stage,j,later)).shuffle(slot)
            orders.append(tuple(slot))
        state,history=kernel.continue_from(stage+1,seat,orders)
        assert history[0]["stage"]==stage+1 and history[-1]["kept"]
        ref.sim.reset_caches();ref.sim.root.install(kernel.DECK_KEY)
        ref.sim.m.set_trial_seed(seed("stable_effects",split,seat,stage,j))
        t=int(ref.d._win_turn_from_unknown_order(
          state.hand,state.library,seat,beam=160,max_turn=3) or 0)
        assert t in (0,1,2,3)
        turns.append(t);later_stages.append(history[-1]["stage"])
    assert len(turns)==FUTURES[split]
    doc={
       "schema":SCHEMA,"status":"PASS","split":split,
       "seat":seat,"stage":stage,
       "futures_per_cell":FUTURES[split],
       "source_frozen_v33b_sha256":kernel.v33b.MODEL_SHA,
       "downstream_keep_v27_bottom_v33b":True,
       "all_99_shuffled_at_each_later_stage":True,
       "rejected_seven_not_visible_in_shared_C":True,
       "strict_gameplay_beam160":True,
       "physical_turns":turns,
       "final_kept_london_stages":later_stages,
       "real_Qmull_T2":sum(0<t<=2 for t in turns)/len(turns),
       "real_Qmull_T3":sum(0<t<=3 for t in turns)/len(turns),
    }
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,"wt") as f:json.dump(doc,f,sort_keys=True)
    print("DACK_V36_TRUE_QMULL_CELL_PASS",split,seat,stage,
       round(time.monotonic()-started,2),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--split",choices=tuple(FUTURES),required=True)
    p.add_argument("--seat",type=int,required=True)
    p.add_argument("--stage",type=int,required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args();run(a.split,a.seat,a.stage,a.out)
