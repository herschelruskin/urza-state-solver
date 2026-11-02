#!/usr/bin/env python3
"""Adversarial engine/RNG regression for v43 selective visible-seven fallback.
No acceptance results are accessed. Tests exact hidden-order invariance, same
hypothetical futures, restoration of original game chance seed, and legality.
"""
from __future__ import annotations
from collections import Counter
import json,time,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import dack_paired_counterfactual_v43_selective_line_20261101 as h
def main():
    t0=time.perf_counter()
    h.install(enabled=True)
    seven=("Gemstone Caverns","Mox Diamond","Mana Vault",
           "Lion's Eye Diamond","The Mycosynth Gardens","Plains","Lunarch Mantle")
    allcards=Counter(h.ref.VARIANTS["one_key_34"])
    for card in seven:allcards[card]-=1
    assert all(x>=0 for x in allcards.values())
    unknown=[x for x,n in allcards.items() for _ in range(n)]
    assert len(unknown)==92
    assert h.risk_patterns(seven)
    outer_seed=173375699;h.OUTER_SEED=outer_seed
    original=h.ref.sim.m.set_trial_seed
    allseeds=[]
    def wrapped(seed):
        allseeds.append(seed)
        return original(seed)
    h.ref.sim.m.set_trial_seed=wrapped
    try:
        q1,t1=h.independent_physical_keep(seven,tuple(unknown),seat=2,stage=0,q=.36)
        assert allseeds[-1]==outer_seed
        q2,t2=h.independent_physical_keep(seven,tuple(reversed(unknown)),seat=2,stage=0,q=.36)
        assert allseeds[-1]==outer_seed
    finally:
        h.ref.sim.m.set_trial_seed=original
    assert t1==t2 and q1==q2,(t1,t2,q1,q2)
    assert len(t1)==h.FUTURES==6 and all(x in (0,1,2) for x in t1)
    assert len(allseeds)==(h.FUTURES+1)*2
    result={"status":"PASS","test":"visible_seven_resampling_order_invariance_and_outer_chance_restoration",
       "inner_hidden92_reverse_order_same_result":True,"same_physical_six_turns":t1,
       "independent_resampling_does_not_look_at_actual_hidden_order":True,
       "outer_seed_restored_twice":True,
       "trial_seed_calls":len(allseeds),"elapsed_seconds":time.perf_counter()-t0}
    print("DACK_V43_HYBRID_FALLBACK_INVARIANCE_PASS",json.dumps(result,sort_keys=True),flush=True)
if __name__=="__main__":main()
