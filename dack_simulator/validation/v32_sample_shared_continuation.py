#!/usr/bin/env python3
"""v32: estimate shared real Q(MULL) once for each (seat, London stage).

Conditional on taking a mulligan, every rejected seven returns to the
same physical 99-card deck. Subsequent London deals have the same
distribution regardless of rejected hand. Here C[seat][stage] is estimated
under the unchanged FROZEN v27 policy for later stages, with strict beam160
gameplay, independently of any current seven. Never provide realized
future card order to a policy. Stages 0..6 only (stage 7 forced keep).

Training estimator and separated calibration validation use distinct
hash-seeded fresh physical future orders, not 92k/93k/94k or 103k-104k.
Never change v5/v14/v27. Output is only a candidate continuation table.
"""
from __future__ import annotations
import argparse,hashlib,json,random,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from dack_simulator.validation.v31_collect_action_regret import (
    frozen,controller,choose_mull_continuation,BEAM
)

PROTO="DACK_V32_SHARED_MULL_CONTINUATION_V1"
N_TRAIN=96
N_VALID=32

def seed(*parts):
    x=json.dumps((PROTO,*parts),separators=(",",":")).encode()
    return int.from_bytes(hashlib.sha256(x).digest()[:8],"big")

def one(seat,stage):
    frozen.audit()
    assert tuple(controller.ref.sim.STAGES)==(7,7,6,5,4,3,2,1)
    assert len(controller.ref.SLOTS)==99
    assert controller.MODEL["T3_reward_is_exactly_zero"]
    deck=controller.ref.SLOT_VARIANTS["one_key_34"]
    out=[]
    started=time.perf_counter()
    for split,n in (("train",N_TRAIN),("validation",N_VALID)):
        for trial in range(n):
            orders=[]
            for later in range(stage+1,8):
                x=list(controller.ref.SLOTS)
                random.Random(seed("physical_london",split,seat,stage,trial,later)).shuffle(x)
                orders.append(tuple(x))
            q,hist=choose_mull_continuation(deck,seat,stage+1,orders)
            controller.ref.sim.reset_caches()
            controller.ref.sim.root.install("one_key_34")
            controller.ref.sim.m.set_trial_seed(
                seed("dice",split,seat,stage,trial))
            t=int(controller.ref.d._win_turn_from_unknown_order(
                q.hand,q.library,seat,beam=BEAM,max_turn=3) or 0)
            assert t in (0,1,2,3)
            assert len(hist)>=1 and hist[-1]["kept"]
            assert hist[0]["stage"]==stage+1
            out.append({
                "split":split,"trial":trial,"turn":t,
                "kept_at_london_stage":hist[-1]["stage"],
            })
        print("DACK_V32_SHARED_C_GROUP",seat,stage,split,n,
              round(time.perf_counter()-started,2),flush=True)
    assert len(out)==N_TRAIN+N_VALID
    raw={
      "schema":"dack_v32_shared_mull_continuation_frozen_v27",
      "status":"PASS","seat":seat,"stage":stage,
      "all_99_returned_on_mull":True,
      "policy_after_mull":"frozen_v27_all_eight_stages_v14_bottom",
      "initial_seven_independent":True,
      "train_count":N_TRAIN,"validation_count":N_VALID,
      "actual_beam":160,"only_physical_hidden_shuffle_labels":True,
      "model_approved":False,
      "results":out,
    }
    return raw

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--seat",type=int,required=True,choices=range(4))
    p.add_argument("--stage",type=int,required=True,choices=range(7))
    p.add_argument("--out",required=True)
    a=p.parse_args()
    out=one(a.seat,a.stage)
    dest=Path(a.out);dest.parent.mkdir(exist_ok=True,parents=True)
    dest.write_text(json.dumps(out,separators=(",",":"),sort_keys=True)+"\n")
    print("DACK_V32_C_SHARD_PASS",a.seat,a.stage,flush=True)
