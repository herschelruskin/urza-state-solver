#!/usr/bin/env python3
"""v46 shared C128: independent full99 MULL futures, exact frozen v43.

There are eight seat-stage cells: seat0..3 x London stages 0,1. All
deals at the same stage and seat share a finite sample of continuation
values, which must be resampled ONCE per cell in any uncertainty analysis.
"""
import argparse,gzip,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from dack_simulator.validation import v45_frozen_v43_continuation as k
from dack_simulator.validation.v46_collect_true_seven_K16 import game
SCHEMA="dack_v46_first_two_sevens_shared_full99_C128_v1"
N=128
def orders(seat,stage,j):
    import random
    result=[]
    ref=k.ref
    for next_stage in range(stage+1,8):
        slots=list(ref.SLOTS)
        random.Random(k.stable_seed("v46_new_full99_C_london",
            seat,stage,j,next_stage)).shuffle(slots)
        assert len(slots)==99 and len(set(slots))==99
        result.append(tuple(slots))
    return result

def run(seat,stage,out):
    assert seat in range(4) and stage in (0,1)
    k.selftest()
    turns=[]
    for j in range(N):
        next_orders=orders(seat,stage,j)
        state,hist=k.continue_from(stage+1,seat,next_orders)
        assert hist[0]["stage"]==stage+1 and hist[-1]["kept"]
        assert all(h["keep_n"]==k.ref.sim.STAGES[h["stage"]] for h in hist)
        turns.append(game(state,seat,k.stable_seed("v46_new_full99_C_chance",seat,stage,j)))
        if (j+1)%32==0:print("DACK_V46_FULL99_MULL_PROGRESS",seat,stage,j+1,flush=True)
    assert len(turns)==N
    d={"schema":SCHEMA,"status":"PASS","seat":seat,"stage":stage,
       "source_outer_deal_independent":True,
       "full99_returned_at_every_later_stage":True,
       "not_already_conditioned_on_original_seven":True,
       "exact_frozen_v43_downstream_replay_parity":True,
       "strict_gameplay_beam160":True,
       "C_independent_full99_futures":N,"turns":turns,
       "shared_C_across_train_and_dev_uncertainty_not_independent":True,
    }
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,"wt") as f:json.dump(d,f,sort_keys=True)
    print("DACK_V46_SHARED_FULL99_C128_PASS",seat,stage,flush=True)
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--seat",type=int,required=True)
    p.add_argument("--stage",type=int,required=True)
    p.add_argument("--out",required=True)
    x=p.parse_args();run(x.seat,x.stage,x.out)
