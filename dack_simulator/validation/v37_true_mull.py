#!/usr/bin/env python3
"""v37 training 12 independent Qmull C cells, 256 true full-99 futures each.

Forced MULL returns rejected seven to complete 99; independent later
London sevens, EXACT frozen-v27-future-KEEP/v33b-bottom. No reject-hand
identity or actual unknown order affects C. Stable chance strict beam160.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,random,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from dack_simulator.validation import v34_frozen_v33b_continuation as kernel
SCHEMA="dack_v37_real_physical_shared_frozen_v33b_Qmull_1"
PROTO="DACK_V37_TRAIN_FULL99_QMULL_126K_V1"
N=256

def seed(*parts):
    return int.from_bytes(hashlib.sha256(json.dumps(
      (PROTO,*parts),separators=(",",":")).encode()).digest()[:8],"big")

def run(seat,stage,out):
    if seat not in range(4) or stage not in (0,1,2):raise ValueError
    kernel.initialize()
    ref=kernel.ref;assert ref.SPEC["beam"]==160 and len(ref.SLOTS)==99
    started=time.monotonic();turns=[]
    for j in range(N):
        orders=[]
        for later in range(stage+1,8):
            slots=list(ref.SLOTS)
            random.Random(seed("reshuffle99",seat,stage,j,later)).shuffle(slots)
            orders.append(tuple(slots))
        state,hist=kernel.continue_from(stage+1,seat,orders)
        assert hist[0]["stage"]==stage+1 and hist[-1]["kept"]
        ref.sim.reset_caches();ref.sim.root.install(kernel.DECK_KEY)
        ref.sim.m.set_trial_seed(seed("effects",seat,stage,j))
        t=int(ref.d._win_turn_from_unknown_order(
            state.hand,state.library,seat,beam=160,max_turn=3) or 0)
        assert t in (0,1,2,3)
        turns.append(t)
        if (j+1)%64==0:
            print("DACK_V37_QMULL_TRAIN_PROGRESS",seat,stage,j+1,
                  round(time.monotonic()-started,2),flush=True)
    doc={
      "schema":SCHEMA,"status":"PASS","seat":seat,"stage":stage,
      "physical_full99_futures":N,
      "downstream_exact_frozen_v27_KEEP_v33b_bottom":True,
      "reject_seven_restored_and_all_99_reshuffled":True,
      "strict_actual_beam160":True,
      "source_v33b_sha256":kernel.v33b.MODEL_SHA,
      "true_turns":turns,
      "real_C_T2":sum(0<t<=2 for t in turns)/N,
      "real_C_T3":sum(0<t<=3 for t in turns)/N,
      "policy_approved":False
    }
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,"wt") as f:json.dump(doc,f,sort_keys=True)
    print("DACK_V37_QMULL_256_TRUE_GAME_CELL_PASS",seat,stage,flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--seat",type=int,required=True)
    p.add_argument("--stage",type=int,required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args();run(a.seat,a.stage,a.out)
