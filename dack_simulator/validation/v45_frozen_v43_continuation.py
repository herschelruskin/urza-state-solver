#!/usr/bin/env python3
"""v45 exact original-v43 downstream KEEP/MULL physical continuation kernel.

Previously v34/c tested v27+v33b downstream, which is NOT correct for v43.
Here, EVERY forced-mull has its own shuffled, fully restored 99-slot deck
at each subsequent London stage; its downstream KEEP and bottom are exactly
the installed v43 max-v27-Q2 candidate decision, NOT original v5 or v27.

Original v5 is only read from saved first-conflict histories by the
physical sampler. No v5 simulator or lookahead is required.
"""
from __future__ import annotations
import hashlib,json,random
from collections import Counter
import dack_paired_counterfactual_v43_v27_max_Q2_20261101 as v43
import dack_mulligan_teacher_features_v13_20261031 as f
from dack_simulator.validation.collect_teacher_london_v13 import finalists

ref=v43.ref
DECK_KEY="one_key_34"
PROTO="DACK_V45_PHYSICAL_SHARED_V43_TRUE_CONTINUATION_V1"

def stable_seed(*args):
    return int.from_bytes(hashlib.sha256(json.dumps((PROTO,*args),
        separators=(",",":"),sort_keys=False).encode()).digest()[:8],"big")

def initialize():
    a=v43.audit()
    assert a["status"]=="PASS" and len(ref.SLOTS)==99
    assert ref.SPEC["beam"]==160 and tuple(ref.sim.STAGES)==(7,7,6,5,4,3,2,1)
    assert ref.SLOT_VARIANTS[DECK_KEY]==ref.SLOT_VARIANTS["one_key_34"]
    return a

def choose_at(stage,seat,order,deck):
    kn=int(ref.sim.STAGES[stage])
    seven=tuple(deck[s] for s in order[:7])
    unknown=tuple(deck[s] for s in order[7:])
    assert len(seven)==7 and len(unknown)==92
    assert Counter(seven)+Counter(unknown)==Counter(deck.values())
    thresholds=v43.v27.original.DP["seat_continuations"][str(seat)]["thresholds_by_london_stage"]
    candidates=finalists(seven,kn,unknown)
    pool=Counter(unknown)
    ranked=[]
    for i,c in enumerate(candidates):
        x=f.extract(seven,c["hand"],c["bottom"],pool,
            seat,kn,stage,c["struct_rank"],i)
        value=float(v43.v27.original.estimator.predict(v43.v27.original.MODEL,x))
        ranked.append((value,-i,c))
    value,neg,c=max(ranked,key=lambda z:(z[0],z[1]))
    cutoff=float(thresholds[stage])
    keep=(kn==1 or value>=cutoff)
    hand=tuple(c["hand"]);bottom=tuple(c["bottom"])
    assert Counter(hand)+Counter(bottom)==Counter(seven)
    return {
      "stage":stage,"keep_n":kn,"kept":bool(keep),
      "seven":list(seven),"seven_slots":list(order[:7]),
      "hand":list(hand),"bottom":list(bottom),
      "raw":round(value,7),"threshold":round(cutoff,7),
      "candidate_index":-neg,
      "state":ref.d.State(1,hand,unknown+bottom),
    }

def continue_from(start,seat,orders):
    assert 0<=start<=7
    assert len(orders)==8-start
    deck=ref.SLOT_VARIANTS[DECK_KEY]
    hist=[]
    for stage,order in zip(range(start,8),orders):
        r=choose_at(stage,seat,order,deck)
        hist.append(r)
        if r["kept"]:return r["state"],hist
    raise AssertionError("London one-card stage must keep")

def future_orders(seat,first_disagreement_stage,future):
    assert first_disagreement_stage in range(7)
    result=[]
    for stage in range(first_disagreement_stage+1,8):
        slots=list(ref.SLOTS)
        random.Random(stable_seed("v45_independent_mull_full99",
            seat,first_disagreement_stage,future,stage)).shuffle(slots)
        assert len(slots)==99 and len(set(slots))==99
        result.append(tuple(slots))
    return result

def selftest():
    initialize()
    deck=ref.SLOT_VARIANTS[DECK_KEY]
    for gid in range(168000,168024):
        seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
        seat,orders=ref.stage_slots(seed)
        original,hist=ref.choose_keep(deck,seat,orders)
        state,copy=continue_from(0,seat,orders)
        assert original.hand==state.hand and original.library==state.library
        assert len(hist)==len(copy)
        for a,b in zip(hist,copy):
            for key in ("stage","keep_n","kept","seven","bottom","hand","candidate_index"):
                assert a[key]==b[key],("v43 continuation mismatch",gid,key,a[key],b[key])
            assert abs(float(a["raw"])-b["raw"])<=1e-7
            assert abs(float(a["threshold"])-b["threshold"])<=1e-7
    for stage in range(7):
        x=future_orders(2,stage,4)
        assert len(x)==7-stage
        assert all(len(z)==99 for z in x)
    print("DACK_V45_FROZEN_V43_DOWNSTREAM_STAGE0_REPLAY_PARITY_PASS",24,flush=True)
    return True

if __name__=="__main__":selftest()
