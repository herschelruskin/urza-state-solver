#!/usr/bin/env python3
"""v35 121k new shared Qmull true physical outcomes, frozen v33b future.

Each of 4 seats × stage0..6 receives 64 new full-99 London future
reshuffles. Neither the current seven nor new v35 decisions affect
Qmull; this exactly measures the FROZEN v33b continuation reference
used when training v35. NO new-policy Bellman self-consistency claim.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,random,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from dack_simulator.validation import v34_frozen_v33b_continuation as kernel
FUTURES=64
PROTO="DACK_V35_NEW121K_QMULL_FIXED_V33B_FUTURE_1"

def seed(*parts):
    return int.from_bytes(hashlib.sha256(json.dumps((PROTO,*parts),separators=(",",":")).encode()).digest()[:8],"big")

def one(seat,stage,out):
    if seat not in range(4) or stage not in range(7):raise ValueError("seat/stage invalid")
    kernel.initialize()
    ref=kernel.ref
    deck=ref.SLOT_VARIANTS[kernel.DECK_KEY]
    assert len(deck)==99 and len(ref.SLOTS)==99 and ref.SPEC["beam"]==160
    start=time.perf_counter();turns=[]
    for j in range(FUTURES):
        orders=[]
        for s in range(stage+1,8):
            slots=list(ref.SLOTS)
            random.Random(seed("full99_london",seat,stage,j,s)).shuffle(slots)
            orders.append(tuple(slots))
        state,hist=kernel.continue_from(stage+1,seat,orders)
        assert hist and hist[-1]["kept"] and hist[0]["stage"]==stage+1
        assert len(state.hand)==hist[-1]["keep_n"]
        ref.sim.reset_caches();ref.sim.root.install(kernel.DECK_KEY)
        ref.sim.m.set_trial_seed(seed("stable_chance",seat,stage,j))
        turn=int(ref.d._win_turn_from_unknown_order(
          state.hand,state.library,seat,beam=160,max_turn=3) or 0)
        assert turn in (0,1,2,3)
        turns.append(turn)
    output={
      "schema":"dack_v35_fresh121k_shared_Qmull",
      "status":"PASS","seat":seat,"stage":stage,
      "futures_per_cell":FUTURES,
      "outcome_turns":turns,
      "frozen_downstream_v27_keep_v33b_bottom":True,
      "complete_99_cards_reshuffled_each_future_stage":True,
      "current_seven_not_used":True,
      "strict_gameplay_beam":160,"policy_approved":False,
      "model_v33b_sha256":kernel.v33b.MODEL_SHA,
      "randomness_split":"new121k_C_independent"
    }
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,"wt") as f:json.dump(output,f,sort_keys=True)
    print("DACK_V35_121K_QMULL_CELL_PASS",seat,stage,FUTURES,
          round(time.perf_counter()-start,2),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--seat",type=int,required=True)
    p.add_argument("--stage",type=int,required=True)
    p.add_argument("--out",required=True)
    x=p.parse_args();one(x.seat,x.stage,x.out)
