#!/usr/bin/env python3
"""v47 research hybrid: ORIGINAL v5 sampled beam60 evaluator at the first two
seven-card London stages ONLY; all later stages original frozen v43.

These stages each have only one legal candidate kept seven; no bottom
choices to beam-search. v5 exact original utility T1+T2+0.5*T3, original
provisional frozen 7-card continuation and +.20 assertive penalty, original
sampled-T1 waiver. Uses expensive physical lookahead on two early sevens
only; is NOT a no-beam student, and v5's provisional C may be inconsistent
with future v43 continuation. Measure real goldfish and runtime honestly.
"""
from __future__ import annotations
import json,hashlib,time
from collections import Counter
import dack_paired_counterfactual_v5_stable_chance_20261031 as v5
from dack_simulator.validation import v45_frozen_v43_continuation as k

ref=k.ref
POLICY="dack_v47_true_v5_stage0_1_only_then_frozen_v43_from_stage2_RESEARCH"
INSTALLED=False

def install():
    global INSTALLED
    k.initialize()
    # Ensure actual original v5 stateless dice, bounded candidate scorer and
    # terminal witness are installed after v43's own original audit.
    v5.install()
    assert ref.SPEC["beam"]==160 and len(ref.SLOTS)==99
    assert tuple(ref.sim.STAGES)==(7,7,6,5,4,3,2,1)
    assert ref.sim.ACTIVE_POLICY=="assertive"
    assert abs(float(ref.batch.CONFIG["lambda"])-.5)<1e-12
    assert abs(float(ref.batch.FROZEN_CONTINUATION[6])-.55603)<1e-7
    assert abs(float(ref.sim.ASSERTIVE_BUMPS[7])-.20)<1e-9
    ref.choose_keep=choose_keep
    ref.MULLIGAN_POLICY_NAME=POLICY
    ref.MULLIGAN_SAMPLER_NAME="true_original_v5_eight_or_sixteen_gameplay_futures_ONLY_first_two_sevens"
    INSTALLED=True
    return {"status":"PASS","policy":POLICY,
      "first_two_stages_original_true_v5_beam60":True,
      "stage2plus_original_frozen_v43":True,
      "not_no_beam":True,"policy_approved":False,
      "original_v5_assertive_cutoff_provisional_under_v43_future":True}

def choose_keep(deck_slots,seat,orders):
    assert INSTALLED and deck_slots==ref.SLOT_VARIANTS["one_key_34"]
    history=[]
    for stage,order in enumerate(orders):
        if stage in (0,1):
            seven=[deck_slots[s] for s in order[:7]]
            rest=[deck_slots[s] for s in order[7:]]
            assert len(seven)==7 and len(rest)==92
            raw,ev,struct,hand,bottom,unknown,ignored,refined=ref.batch.evaluate_keep(
                seven,7,rest,seat)
            assert Counter(hand)==Counter(seven) and len(bottom)==0
            assert Counter(unknown)==Counter(rest)
            standard=float(ref.batch.FROZEN_CONTINUATION[6])
            native=(float(raw)>=standard)
            t1=float(ev["t1"])
            cutoff=standard+(0. if native and t1>0 else
                                float(ref.sim.ASSERTIVE_BUMPS[7]))
            keep=bool(float(raw)>=cutoff)
            state=ref.d.State(1,tuple(hand),tuple(unknown))
            candidate_idx=0
            historical_provenance="original_v5_true_gameplay_value"
        else:
            c=k.choose_at(stage,seat,order,deck_slots)
            hand=tuple(c["hand"]);bottom=tuple(c["bottom"])
            raw=float(c["raw"]);cutoff=float(c["threshold"])
            t1=None;refined=False
            keep=bool(c["kept"]);state=c["state"]
            candidate_idx=int(c["candidate_index"])
            seven=list(c["seven"])
            historical_provenance="frozen_v43_max_Q2_candidate"
        history.append({
          "stage":stage,"keep_n":ref.sim.STAGES[stage],
          "kept":keep,"raw":round(float(raw),7),
          "threshold":round(float(cutoff),7),
          "refined":bool(refined),"sampled_t1":None if t1 is None else round(float(t1),7),
          "seven":list(seven),"seven_slots":list(order[:7]),
          "hand":list(hand),"bottom":list(bottom),
          "candidate_index":candidate_idx,
          "hand_slots":ref.selected_slots(order[:7],seven,hand),
          "bottom_slots":ref.selected_slots(order[:7],seven,bottom),
          "policy_provenance":historical_provenance,
        })
        if keep:return state,history
    raise AssertionError("terminal London must KEEP")
def audit():
    return install()

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--audit",action="store_true")
    p.add_argument("--game",type=int)
    a=p.parse_args();q=audit()
    print("DACK_V47_ORIGINAL_V5_EARLY_ONLY_HYBRID_AUDIT_PASS",json.dumps(q),flush=True)
    if a.game is not None:
        z=ref.game("one_key_34",a.game)
        print("DACK_V47_EARLY_TRUE_V5_ONE_GAME",json.dumps({
           "gid":a.game,"win_turn":z["win_turn"],"history":z["history"]}),flush=True)
