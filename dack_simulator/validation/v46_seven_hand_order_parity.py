#!/usr/bin/env python3
"""Goldfish replay parity: physical dealt seven versus v43 canonical hand order.

The seven-card hand has no bottom at London stages 0 and 1. Engine outcome
must not depend on whether cards are given in deal order or the v43 finalist's
canonical sorted order. Fail before fitting any model if not true.
"""
import random
from collections import Counter
from dack_simulator.validation import v45_frozen_v43_continuation as k
def run():
    k.initialize()
    ref=k.ref;deck=ref.SLOT_VARIANTS[k.DECK_KEY]
    checks=0
    for gid in range(163000,163008):
        seat,orders=ref.stage_slots(int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE)
        for stage in (0,1):
            order=orders[stage]
            seven=tuple(deck[i] for i in order[:7])
            unseen=tuple(deck[i] for i in order[7:])
            chosen=k.choose_at(stage,seat,order,deck)
            hand=tuple(chosen["hand"])
            assert chosen["bottom"]==[] and Counter(hand)==Counter(seven)
            for f in range(3):
                hidden=list(unseen)
                random.Random(k.stable_seed("v46_blind_unseen92_keep",gid,stage,f)).shuffle(hidden)
                results=[]
                for selected in (seven,hand):
                    ref.sim.reset_caches();ref.sim.root.install(k.DECK_KEY)
                    ref.sim.m.set_trial_seed(k.stable_seed("v46_keep_stateless_chance",gid,stage,f))
                    if hasattr(ref.d,"_WIN_CACHE"):ref.d._WIN_CACHE.clear()
                    t=ref.d._win_turn_from_unknown_order(selected,tuple(hidden),seat,beam=160,max_turn=3)
                    results.append(int(t or 0))
                assert results[0]==results[1],("hand ordering changes physical outcome",gid,stage,f,results)
                checks+=1
    assert checks==48
    print("DACK_V46_48_STRICT_BEAM160_STAGE01_HAND_ORDER_GOLDFISH_PARITY_PASS",flush=True)
if __name__=="__main__":run()
