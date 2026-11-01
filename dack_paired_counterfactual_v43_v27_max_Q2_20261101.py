#!/usr/bin/env python3
"""v43 NEW experimental v27 MAX-Q2 candidate/KEEP coupled policy.

Keep original v27 T2-only scorer and continuation DP exactly frozen. The
SOLE change: choose from original structural top12 London candidate bottoms
by maximum frozen v27 Q2 estimate, then score KEEP using that SAME selected
candidate, rather than selecting bottom from a separate v14 classification
head. This is OOD candidate maximization and is NOT policy approved.
"""
from __future__ import annotations
import hashlib,json
from collections import Counter
from pathlib import Path
import dack_paired_counterfactual_v27_T2_only_DP_20261101 as v27
import dack_mulligan_teacher_features_v13_20261031 as features
from dack_simulator.validation.collect_teacher_london_v13 import finalists
ref=v27.ref
POLICY="dack_v43_maximize_frozen_v27_Qkeep_across_legal_bottoms"
STATS=Counter()
def install():
    a=v27.audit()
    assert a["status"]=="PASS" and ref.SPEC["beam"]==160
    assert v27.original.MODEL["T3_reward_is_exactly_zero"]
    assert len(ref.SLOTS)==99
    assert v27.original.DP["model_approved"] is False
    ref.choose_keep=choose_keep
    ref.MULLIGAN_POLICY_NAME=POLICY
    ref.MULLIGAN_SAMPLER_NAME="none__v27_Q2_predicted_over_up_to12_candidate_bottoms"
    return dict(a,new_policy=POLICY,policy_approved=False)
def choose_keep(deck_slots,seat,orders):
    assert deck_slots==ref.SLOT_VARIANTS["one_key_34"]
    thresholds=v27.original.DP["seat_continuations"][str(seat)]["thresholds_by_london_stage"]
    hist=[]
    for stage,(kn,order) in enumerate(zip(ref.sim.STAGES,orders)):
        seven=tuple(deck_slots[s] for s in order[:7])
        unknown=tuple(deck_slots[s] for s in order[7:])
        assert len(seven)==7 and len(unknown)==92
        pool=Counter(unknown)
        candidates=finalists(seven,kn,unknown)
        predictions=[]
        for i,c in enumerate(candidates):
            x=features.extract(seven,c["hand"],c["bottom"],pool,
                 seat,kn,stage,c["struct_rank"],i)
            q=v27.original.estimator.predict(v27.original.MODEL,x)
            predictions.append((float(q),-i,c))
        q,neg_index,selected=max(predictions,key=lambda x:(x[0],x[1]))
        threshold=float(thresholds[stage])
        kept=bool(kn==1 or q>=threshold)
        hand=tuple(selected["hand"]);bottom=tuple(selected["bottom"])
        assert Counter(hand)+Counter(bottom)==Counter(seven)
        STATS["visited_stage"]+=1
        STATS["kept" if kept else "mulled"]+=1
        hist.append({
          "stage":stage,"keep_n":kn,"kept":kept,"raw":round(q,7),
          "threshold":round(threshold,7),"refined":False,"sampled_t1":None,
          "candidate_index":-neg_index,"candidate_count":len(candidates),
          "seven_slots":list(order[:7]),"seven":list(seven),
          "hand":list(hand),"bottom":list(bottom),
          "hand_slots":ref.selected_slots(order[:7],seven,hand),
          "bottom_slots":ref.selected_slots(order[:7],seven,bottom),
          "policy":POLICY,
        })
        if kept:
            return ref.d.State(1,hand,unknown+bottom),hist
    raise AssertionError("London terminal must keep")
def audit():
    info=install()
    assert ref.MULLIGAN_POLICY_NAME==POLICY
    assert v27.original.MODEL["training_states"]==2048
    return info
if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser();p.add_argument("--audit",action="store_true");p.add_argument("--game",type=int)
    a=p.parse_args();info=audit()
    if a.audit:print("DACK_V43_MAXQ2_RESEARCH_POLICY_AUDIT_PASS",json.dumps(info),flush=True)
    if a.game is not None:
        g=ref.game("one_key_34",a.game)
        print("DACK_V43_MAXQ2_ONE",json.dumps({"gid":a.game,"turn":g["win_turn"],"history":g["history"]}),flush=True)
