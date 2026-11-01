#!/usr/bin/env python3
"""v37 unapproved DIRECT physical action-regret early London policy.

Frozen v27 Q/C + exact v33b legal bottom state. Only stage0/1/2
potential KEEP/MULL changes from v37 direct signed A2/A3 ensemble.
All later v27 decisions frozen. No mulligan beam, hidden order peeking,
or mutation of original physical gameplay rules.
"""
from __future__ import annotations
import hashlib,json
from collections import Counter
from pathlib import Path
from dack_simulator.validation import v34_frozen_v33b_continuation as kernel
import dack_mulligan_v37_direct_regret as modelrun
import dack_mulligan_v37_features as feat

ref=kernel.ref
POLICY="dack_v37_direct_action_regret_UNAPPROVED"
MODEL_PATH=Path("models/dack_v37_direct_regret_EXPERIMENTAL.json")
MODEL=None
MODEL_SHA=None

def install():
    global MODEL,MODEL_SHA
    kernel.initialize()
    raw=MODEL_PATH.read_bytes()
    m=modelrun.validate(json.loads(raw))
    assert m["source_v33b_sha256"]==kernel.v33b.MODEL_SHA
    assert m["source_v27_q_sha256"]==hashlib.sha256(
      Path(kernel.v33b.frozen.MODEL).read_bytes()).hexdigest()
    assert m["source_v27_C_sha256"]==hashlib.sha256(
      Path(kernel.v33b.frozen.DP).read_bytes()).hexdigest()
    assert m["127k_validation_unseen"] and m["128k_prospective_unseen"]
    assert m["under_frozen_future_v27_keep_v33b_bottom"]
    MODEL=m;MODEL_SHA=hashlib.sha256(raw).hexdigest()
    ref.choose_keep=choose_keep
    ref.RULES_VERSION=POLICY+"_"+MODEL_SHA[:16]
    ref.MULLIGAN_POLICY_NAME=POLICY
    ref.MULLIGAN_SAMPLER_NAME="v37_no_beam_direct_true_action_regret"
    return MODEL_SHA

def choose_keep(deck_slots,seat,orders):
    assert MODEL is not None
    assert deck_slots==ref.SLOT_VARIANTS[kernel.DECK_KEY]
    hist=[]
    for stage,(kn,order) in enumerate(zip(ref.sim.STAGES,orders)):
        seven=tuple(deck_slots[s] for s in order[:7])
        unknown=tuple(deck_slots[s] for s in order[7:])
        assert Counter(seven)+Counter(unknown)==Counter(ref.VARIANTS[kernel.DECK_KEY])
        sel=kernel.current(seven,unknown,seat,stage)
        hand=tuple(sel["hand"]);bottom=tuple(sel["bottom"])
        assert len(hand)==kn and len(bottom)==7-kn
        old=bool(sel["old_v27_keep"])
        if stage<3:
            x=feat.extract(seven,unknown,seat,stage,sel)
            keep,reason=modelrun.decide(MODEL,x,stage,old)
        else:
            keep=old
            reason={"old_keep":old,"new_keep":old,
                    "reason":("forced_terminal_stage7" if kn==1 else "unchanged_later_stage")}
        hist.append({
          "stage":stage,"keep_n":kn,"kept":bool(keep),
          "seven_slots":list(order[:7]),"seven":list(seven),
          "raw":round(sel["old_v27_Qkeep"],7),
          "threshold":round(sel["old_v27_DP"],7),
          "hand":list(hand),"bottom":list(bottom),
          "hand_slots":ref.selected_slots(order[:7],seven,hand),
          "bottom_slots":ref.selected_slots(order[:7],seven,bottom),
          "v37_frozen_v27_original_keep":old,
          "v37_frozen_v33b_bottom":True,
          "v37_action_diagnostic":reason,
          "policy":POLICY,
        })
        if keep:
            return ref.d.State(1,hand,unknown+bottom),hist
    raise AssertionError("terminal London must KEEP")

def audit():
    sha=install()
    d=ref.audit()
    assert d["status"]=="PASS" and d["mulligan_policy"]==POLICY
    assert tuple(ref.sim.STAGES)==(7,7,6,5,4,3,2,1)
    assert len(ref.SLOTS)==99 and ref.SPEC["beam"]==160
    return dict(d,model_sha256=sha,policy_approved=False,
        no_mulligan_beam=True,strict_physical_game_beam160=True,
        only_stages0_1_2_change=True,frozen_v33b_bottom=True,
        one_step_frozen_future_not_new_policy_bellman=True)

def smoke():
    audit();deck=ref.SLOT_VARIANTS[kernel.DECK_KEY]
    for gid in range(128900,128916):
        seat,orders=ref.stage_slots(int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE)
        a,h=choose_keep(deck,seat,orders)
        assert h[-1]["kept"] and tuple(h[-1]["hand"])==a.hand
        assert len(a.library)==92+len(h[-1]["bottom"])
        for r in h:
            assert Counter(r["seven"])==Counter(r["hand"])+Counter(r["bottom"])
            assert r["stage"]<3 or r["kept"]==r["v37_frozen_v27_original_keep"]
        if all(r["kept"]==r["v37_frozen_v27_original_keep"] for r in h):
            older,original=kernel.v33b.choose_keep(deck,seat,orders)
            assert len(original)==len(h)
            assert older.hand==a.hand and older.library==a.library
    print("DACK_V37_STRICT_PHYSICAL_FROZEN_BOTTOM_PARITY_PASS",flush=True)

if __name__=="__main__":
    smoke()
