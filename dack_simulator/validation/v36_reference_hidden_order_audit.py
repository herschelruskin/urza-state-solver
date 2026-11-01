#!/usr/bin/env python3
"""v36 method audit: v5 London policy invariance to secret 92 order.

The physical seven and seat are fixed. Replace the 92 unseen physical
slots at EVERY London stage with a different permutation. This must
NOT alter a legitimate mulligan policy's KEEP decisions, legal bottoms,
or numerical estimated keep utilities. Only later real gameplay may
legitimately depend on the hidden physical library order.

v5 uses hypothetical beam rollouts and deterministic seeded draws;
this test specifically checks for direct actual-future-order leakage.
Passing cannot prove absence of all modeling bias.
"""
from __future__ import annotations
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import dack_paired_counterfactual_v5_stable_chance_20261031 as v5
from collections import Counter

def run():
    assert v5.audit()["status"]=="PASS"
    ref=v5.reference;deck=ref.SLOT_VARIANTS["one_key_34"]
    n=0
    for gid in (115003,115043,115171):
        seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
        seat,orders=ref.stage_slots(seed)
        permuted=tuple(tuple(list(order[:7])+list(reversed(order[7:])))
                       for order in orders)
        assert len(permuted)==8
        for o,p in zip(orders,permuted):
            assert o[:7]==p[:7] and sorted(o[7:])==sorted(p[7:])
            assert o[7:]!=p[7:]
        def eval(orders):
            ref.sim.reset_caches();ref.sim.root.install("one_key_34")
            ref.sim.m.set_trial_seed(seed)
            return ref.choose_keep(deck,seat,orders)
        a,history=eval(orders)
        b,history2=eval(permuted)
        assert len(history)==len(history2)
        assert a.hand==b.hand
        for j,(x,y) in enumerate(zip(history,history2)):
            for key in ("stage","keep_n","kept","raw","sampled_t1",
                        "threshold","refined","seven","hand","bottom","seven_slots"):
                assert x[key]==y[key],("actual hidden 92 order affected v5 decision",gid,j,key,x[key],y[key])
            n+=1
        print("DACK_V36_REFERENCE_V5_HIDDEN92_PERMUTATION_INVARIANCE_PASS",
              gid,len(history),flush=True)
    assert n>=3
    print("DACK_V36_REFERENCE_V5_ACTUAL_FUTURE_ORDER_LEAKAGE_AUDIT_PASS",
          n,"decision_stages",flush=True)

if __name__=="__main__":run()
