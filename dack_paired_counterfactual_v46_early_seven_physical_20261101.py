#!/usr/bin/env python3
"""Experimental v46 stage0/1 physical early-seven KEEP correction.

Exactly the original v43 candidate and hand selection is preserved at all
London stages. Only the KEEP/MULL decision at the first two 7-card stages
may differ based on a frozen physically supervised model. Stage1 remains
conditionally visited only after stage0 MULL. No runtime beam or v5 teacher.
"""
from __future__ import annotations
import hashlib,json
from pathlib import Path
from collections import Counter
import dack_mulligan_v46_seven_physical_calibration as values
from dack_simulator.validation import v45_frozen_v43_continuation as k
ref=k.ref
ROOT=Path(__file__).resolve().parent
PATH=ROOT/"models/v46_real_first_two_sevens_RESEARCH.json"
POLICY="dack_v46_frozen_true_physical_first_two_seven_value_gated"
MODEL=None
MODEL_SHA=None

def install():
    global MODEL,MODEL_SHA
    k.selftest()
    m=values.load(PATH)
    assert m["source_v27_model_sha256"]==values.sha(
         ROOT/"models/dack_v27_expanded_T2_only_value_EXPERIMENTAL.json")
    assert not m["policy_approved"] and m["train_independent_groups"]==128
    MODEL=m;MODEL_SHA=values.sha(PATH)
    ref.choose_keep=choose_keep
    ref.MULLIGAN_POLICY_NAME=POLICY
    ref.MULLIGAN_SAMPLER_NAME="none_physically_supervised_early7_no_lookahead"
    return {"status":"PASS","model_sha256":MODEL_SHA,
       "policy_approved":False,"first_two_stages_only":True,
       "strict_beam160":True}

def choose_keep(deck_slots,seat,orders):
    assert MODEL is not None
    assert deck_slots==ref.SLOT_VARIANTS[k.DECK_KEY]
    history=[]
    for stage,order in enumerate(orders):
        sel=k.choose_at(stage,seat,order,deck_slots)
        old=bool(sel["kept"])
        if stage in (0,1):
            seven=tuple(sel["seven"])
            assert sel["keep_n"]==7 and sel["bottom"]==[]
            from collections import Counter
            remaining=Counter(deck_slots.values())-Counter(seven)
            assert sum(remaining.values())==92
            x=values.features(seven,remaining,seat,stage,sel["raw"],sel["threshold"])
            keep,p2,p3=values.decide(MODEL,x,seat,stage,old)
            raw=round(p2,7)
            threshold=round(MODEL["shared_C"][str(seat)][str(stage)]["T2"],7)
        else:
            keep=old;raw=sel["raw"];threshold=sel["threshold"];p2=None;p3=None
        hist={
           "stage":stage,"keep_n":sel["keep_n"],"kept":bool(keep),
           "raw":raw,"threshold":threshold,"refined":False,
           "sampled_t1":None,"candidate_index":sel["candidate_index"],
           "candidate_count":1 if stage in (0,1) else None,
           "seven":sel["seven"],"seven_slots":sel["seven_slots"],
           "hand":sel["hand"],"bottom":sel["bottom"],
           "hand_slots":ref.selected_slots(order[:7],sel["seven"],sel["hand"]),
           "bottom_slots":ref.selected_slots(order[:7],sel["seven"],sel["bottom"]),
           "policy":POLICY,
           "frozen_v43_KEEP":old,
           "physical_T2_pred":round(p2,7) if p2 is not None else None,
           "physical_T3_pred":round(p3,7) if p3 is not None else None,
        }
        history.append(hist)
        if keep:return sel["state"],history
    raise AssertionError("one-card London stage must always keep")

def audit():
    a=install()
    assert ref.MULLIGAN_POLICY_NAME==POLICY
    deck=ref.SLOT_VARIANTS[k.DECK_KEY]
    for gid in (157900,157901,157902,157903):
        sd=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
        seat,orders=ref.stage_slots(sd)
        state,h=choose_keep(deck,seat,orders)
        assert h and h[-1]["kept"]
        for row in h:
            if row["stage"]>=2:
                assert row["kept"]==row["frozen_v43_KEEP"]
            if row["stage"]<=1:
                assert row["bottom"]==[] and row["keep_n"]==7
    return a

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser();p.add_argument("--audit",action="store_true")
    p.add_argument("--game",type=int)
    args=p.parse_args()
    a=audit()
    if args.audit:print("DACK_V46_FROZEN_EARLY_SEVEN_RUNTIME_AUDIT_PASS",json.dumps(a),flush=True)
    if args.game is not None:
        g=ref.game(k.DECK_KEY,args.game)
        print("DACK_V46_PHYSICAL_GOLDFISH",json.dumps({
           "gid":args.game,"turn":g["win_turn"],"history":g["history"]}),flush=True)
