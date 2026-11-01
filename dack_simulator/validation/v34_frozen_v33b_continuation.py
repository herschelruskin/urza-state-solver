#!/usr/bin/env python3
"""v34: exact frozen-v33b downstream continuation kernel; no rules changes.

At every stage, choose EXACT frozen v27 Qkeep/v14 baseline, compare against
frozen v27 DP, then use the already frozen v33b regret bottom IF keeping.
The current stage's forced KEEP uses v33b bottom. Forced MULL restores ALL
99 cards, samples fresh London stage orders, and follows this same policy
from stage+1. This removes the v32 continuation-policy mismatch.
"""
from __future__ import annotations
from collections import Counter
import hashlib,json,random
import dack_paired_counterfactual_v33b_regret_bottom_only_20261101 as v33b
import dack_paired_counterfactual_v22_all_stage_real_keep_DP_20261101 as ctl
import dack_mulligan_teacher_features_v13_20261031 as f
from dack_simulator.validation.collect_teacher_london_v13 import finalists
from dack_simulator.validation.v33b_bottom_ranker import rank
import dack_mulligan_v33b_pairwise_regret as reg

ref=ctl.ref
PROTO="DACK_V34_FROZEN_V33B_CONSISTENT_DOWNSTREAM_KERNEL_20261101"
DECK_KEY="one_key_34"

def stable_seed(*parts):
    return int.from_bytes(hashlib.sha256(json.dumps((PROTO,*parts),
        separators=(",",":")).encode()).digest()[:8],"big")

def initialize():
    assert v33b.audit()["status"]=="PASS"
    assert tuple(ref.sim.STAGES)==(7,7,6,5,4,3,2,1)
    assert ref.SPEC["beam"]==160 and len(ref.SLOTS)==99
    assert ctl.MODEL["T3_reward_is_exactly_zero"] is True
    assert ctl.old.MODEL["deployed_policy_approved"] is False
    assert v33b.MODEL["policy_approved"] is False

def current(seven,unknown,seat,stage):
    """Selection never sees the order of unknown 92 physical cards."""
    kn=int(ref.sim.STAGES[stage])
    assert len(seven)==7 and len(unknown)==92
    pool=Counter(unknown)
    choices=finalists(seven,kn,unknown)
    scored=[]
    for idx,choice in enumerate(choices):
        xx=f.extract(seven,choice["hand"],choice["bottom"],pool,
                     seat,kn,stage,choice["struct_rank"],idx)
        vote=f.score_head(ctl.old.MODEL,"choice_trees",xx)
        scored.append((vote,-idx,xx,choice))
    vote,negative,xx,base=max(scored,key=lambda q:(q[0],q[1]))
    old_q=ctl.estimator.predict(ctl.MODEL,xx)
    old_threshold=ctl.DP["seat_continuations"][str(seat)]["thresholds_by_london_stage"][stage]
    opts,scores,method_indices=rank(tuple(seven),kn,tuple(sorted(unknown)),
                                    seat,stage,ctl.old.MODEL,ctl.MODEL)
    assert Counter(opts[method_indices["v14_frozen"]]["hand"])==Counter(base["hand"])
    assert Counter(opts[method_indices["v14_frozen"]]["bottom"])==Counter(base["bottom"])
    new_idx,diagnostics=reg.choose(v33b.MODEL,tuple(seven),tuple(sorted(unknown)),
                                   seat,method_indices,opts)
    new=opts[new_idx]
    assert Counter(new["hand"])+Counter(new["bottom"])==Counter(seven)
    return {
        "stage":stage,"keep_n":kn,"seat":seat,
        "old_v27_Qkeep":float(old_q),
        "old_v27_DP":float(old_threshold),
        "old_v27_keep":bool(kn==1 or old_q>=old_threshold),
        "v14_baseline_candidate_index":-negative,
        "v33b_selected_candidate_index":new_idx,
        "v33b_overrode_bottom":new_idx!=method_indices["v14_frozen"],
        "hand":tuple(new["hand"]),"bottom":tuple(new["bottom"]),
        "v14_hand":tuple(base["hand"]),"v14_bottom":tuple(base["bottom"]),
        "candidate_methods":method_indices
    }

def state_from(seven,unknown,sel):
    assert Counter(seven)==Counter(sel["hand"])+Counter(sel["bottom"])
    # Physical future ordering stays unchanged; bottoms appended at rear.
    return ref.d.State(1,tuple(sel["hand"]),tuple(unknown)+tuple(sel["bottom"]))

def later_orders(seat,stage,trial,split):
    # No initial current seven is used to generate these full 99 shuffles.
    all_orders=[]
    for future_stage in range(stage+1,8):
        slots=list(ref.SLOTS)
        random.Random(stable_seed("future_99_full_deck",seat,stage,trial,split,
                                  future_stage)).shuffle(slots)
        all_orders.append(tuple(slots))
    return all_orders

def continue_from(stage,seat,later_orders):
    """Apply EXACT frozen v27 keep decisions, fixed v33b bottoms after keep."""
    assert len(later_orders)==8-stage
    deck=ref.SLOT_VARIANTS[DECK_KEY]
    history=[]
    for s,order in zip(range(stage,8),later_orders):
        seven=tuple(deck[t] for t in order[:7])
        unknown=tuple(deck[t] for t in order[7:])
        selection=current(seven,unknown,seat,s)
        keep=selection["old_v27_keep"]
        history.append({"stage":s,"keep_n":selection["keep_n"],
                        "kept":keep,
                        "Qkeep":selection["old_v27_Qkeep"],
                        "threshold":selection["old_v27_DP"],
                        "hand":list(selection["hand"]),
                        "bottom":list(selection["bottom"])})
        if keep:
            return state_from(seven,unknown,selection),history
    raise AssertionError("London stage seven must keep one card")

def selftest():
    initialize()
    deck=ref.SLOT_VARIANTS[DECK_KEY]
    for gid in range(116900,116908):
        seat,orders=ref.stage_slots(int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE)
        original,hist=ref.choose_keep(deck,seat,orders)
        reproduced,other=continue_from(0,seat,orders)
        assert len(hist)==len(other)
        for a,b in zip(hist,other):
            assert (a["stage"],a["keep_n"],a["kept"])==(
                    b["stage"],b["keep_n"],b["kept"])
            if a["kept"]:
                assert Counter(a["hand"])==Counter(b["hand"])
                assert Counter(a["bottom"])==Counter(b["bottom"])
        assert original.hand==reproduced.hand
        assert original.library==reproduced.library
    # Rejected London seven does not alter future deck composition.
    for s in range(7):
        assert len(later_orders(2,s,5,"test"))==7-s
        assert all(len(z)==99 and set(z)==set(ref.SLOTS) for z in
                   later_orders(2,s,5,"test"))
    print("DACK_V34_FROZEN_CONTINUATION_KERNEL_PARITY_PASS",flush=True)

if __name__=="__main__":
    selftest()
