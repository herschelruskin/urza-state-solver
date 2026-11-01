#!/usr/bin/env python3
"""v38 goldfish research-only weighted direct-action-regret London policy.

Exactly reproduce frozen v27 current Qkeep and original v33b bottom
for each observed stage seven; v38 changes ONLY KEEP vs MULL at stages
0..2 via a paired-ensemble utility U=PbyT2+0.5*PbyT3, not exact3.
No mulligan beam searches. Retain same actual physical library after
KEEP; full 99 reshuffled at each new London seven stage. No peeking.
"""
from __future__ import annotations
from collections import Counter
import hashlib,json
from pathlib import Path
from dack_simulator.validation import v34_frozen_v33b_continuation as kernel
import dack_mulligan_v37_features as features
import dack_mulligan_v38_weighted_regret as opt

POLICY="dack_v38_predeclared_weighted_regret_experimental_UNAPPROVED"
MODEL_PATH=Path("models/dack_v37_direct_regret_EXPERIMENTAL.json")
ref=kernel.ref
MODEL=None
MODEL_SHA=None

def install():
    global MODEL,MODEL_SHA
    kernel.initialize()
    opt.selftest()
    raw=MODEL_PATH.read_bytes()
    mdl=opt.model_check(json.loads(raw))
    assert mdl["source_v33b_sha256"]==kernel.v33b.MODEL_SHA
    assert hashlib.sha256(Path(kernel.v33b.frozen.MODEL).read_bytes()).hexdigest()==mdl["source_v27_q_sha256"]
    assert hashlib.sha256(Path(kernel.v33b.frozen.DP).read_bytes()).hexdigest()==mdl["source_v27_C_sha256"]
    MODEL=mdl;MODEL_SHA=hashlib.sha256(raw).hexdigest()
    ref.choose_keep=choose_keep
    ref.RULES_VERSION=POLICY+"_"+MODEL_SHA[:16]
    ref.MULLIGAN_POLICY_NAME=POLICY
    ref.MULLIGAN_SAMPLER_NAME="v38_fast_weighted_action_regret_no_beam"
    return MODEL_SHA

def choose_keep(deck_slots,seat,orders):
    if MODEL is None:raise RuntimeError("v38 install first")
    assert deck_slots==ref.SLOT_VARIANTS[kernel.DECK_KEY]
    hist=[]
    for stage,(kn,order) in enumerate(zip(ref.sim.STAGES,orders)):
        seven=tuple(deck_slots[x] for x in order[:7])
        unseen=tuple(deck_slots[x] for x in order[7:])
        assert Counter(seven)+Counter(unseen)==Counter(ref.VARIANTS[kernel.DECK_KEY])
        sel=kernel.current(seven,unseen,seat,stage)
        hand,bottom=tuple(sel["hand"]),tuple(sel["bottom"])
        assert len(hand)==kn and len(bottom)==7-kn
        if stage<3:
            xx=features.extract(seven,unseen,seat,stage,sel)
            keep,diagnostic=opt.choose(MODEL,xx,stage,sel["old_v27_keep"])
        else:
            keep=bool(sel["old_v27_keep"])
            diagnostic={"old_keep":keep,"new_keep":keep,"reason":"frozen_v27_later_stage"}
        if kn==1:
            assert keep
        hist.append({
          "stage":stage,"keep_n":kn,"kept":bool(keep),
          "raw":round(sel["old_v27_Qkeep"],7),
          "threshold":round(sel["old_v27_DP"],7),
          "seven_slots":list(order[:7]),"seven":list(seven),
          "hand":list(hand),"bottom":list(bottom),
          "hand_slots":ref.selected_slots(order[:7],seven,hand),
          "bottom_slots":ref.selected_slots(order[:7],seven,bottom),
          "v38_original_v27_keep":bool(sel["old_v27_keep"]),
          "v38_unchanged_v33b_bottom":True,
          "v38_action_diagnostic":diagnostic,
          "policy":POLICY,
        })
        if keep:return ref.d.State(1,hand,unseen+bottom),hist
    raise AssertionError("stage7 one-card must keep")

def audit():
    sha=install()
    status=ref.audit()
    assert status["status"]=="PASS" and status["mulligan_policy"]==POLICY
    assert tuple(ref.sim.STAGES)==(7,7,6,5,4,3,2,1)
    assert ref.SPEC["beam"]==160 and len(ref.SLOTS)==99
    return dict(status,model_sha256=sha,policy_approved=False,
      only_first_three_actual_stage_actions_can_change=True,
      utility="P_by_T2 + 0.5*P_by_T3",
      complete_real_99_physical_slots=True,
      actual_gameplay_beam=160,mulligan_beam=0,
      no_changed_policy_Bellman_consistency_claim=True)

def smoke():
    audit()
    deck=ref.SLOT_VARIANTS[kernel.DECK_KEY]
    for gid in range(129990,130000):
        seat,orders=ref.stage_slots(int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE)
        state,hist=choose_keep(deck,seat,orders)
        assert hist[-1]["kept"] and state.hand==tuple(hist[-1]["hand"])
        assert len(state.library)==92+len(hist[-1]["bottom"])
        assert all(Counter(h["seven"])==Counter(h["hand"])+Counter(h["bottom"]) for h in hist)
        assert all(h["kept"]==h["v38_original_v27_keep"] for h in hist if h["stage"]>=3)
        if all(h["kept"]==h["v38_original_v27_keep"] for h in hist):
            prev,h2=kernel.v33b.choose_keep(deck,seat,orders)
            assert prev.hand==state.hand and prev.library==state.library
            assert len(hist)==len(h2)
    print("DACK_V38_LONDON_FROZEN_BOTTOM_PARITY_SMOKE_PASS",flush=True)

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--audit",action="store_true")
    p.add_argument("--game",type=int,default=130000)
    a=p.parse_args();smoke()
    if not a.audit:
        assert 130000<=a.game<130512
        print("DACK_V38_EXPERIMENTAL_GAME",json.dumps(ref.game(kernel.DECK_KEY,a.game)),flush=True)
