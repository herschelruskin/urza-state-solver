#!/usr/bin/env python3
"""v33b unapproved no-beam London bottom-only pairwise regret deployment.

First execute the complete FROZEN v27 keep/mull policy with its original
v14 bottom selector and original v27 Qkeep/continuation table.
ONLY AFTER it has elected KEEP, permit a candidate bottom override by
the independently trained 112k pairwise-regret model. Thus kept London
stage and decision depth are 100% unchanged from v27; any deployment
change is caused solely by legal bottom selection. Recalibrating Qkeep
for this selector is a separate later study, not silently claimed.
"""
from __future__ import annotations
from collections import Counter
import hashlib
import json
from pathlib import Path
import dack_paired_counterfactual_v27_T2_only_DP_20261101 as frozen
import dack_paired_counterfactual_v22_all_stage_real_keep_DP_20261101 as ctl
import dack_mulligan_v33b_pairwise_regret as reg
from dack_simulator.validation.v33b_bottom_ranker import rank

ref=ctl.ref
POLICY="dack_v33b_bottom_only_train112_regret_UNAPPROVED"
MODEL_PATH=Path("models/dack_v33b_ridge_regret_EXPERIMENTAL.json")
MODEL=None
MODEL_SHA=None

def install():
    global MODEL,MODEL_SHA
    assert frozen.audit()["status"]=="PASS"
    raw=MODEL_PATH.read_bytes()
    model=json.loads(raw)
    if model["schema"]!=reg.SCHEMA or model["feature_sha256"]!=reg.feats.feature_hash():
        raise ValueError("incompatible action-regret capability features")
    if model["training_source_ids"]!=[112000,112127] or not model["heldout_113k_not_used"]:
        raise ValueError("model trained on different physical cohort")
    if model["policy_approved"] is not False or len(model["ensemble"])!=reg.BOOTS:
        raise ValueError("unapproved ridge ensemble required")
    assert model["training_source_model_shas"]["models/dack_v27_expanded_T2_only_value_EXPERIMENTAL.json"]==hashlib.sha256(Path(frozen.MODEL).read_bytes()).hexdigest()
    assert model["training_source_model_shas"]["models/dack_v27_T2_only_continuations_EXPERIMENTAL.json"]==hashlib.sha256(Path(frozen.DP).read_bytes()).hexdigest()
    MODEL=model
    MODEL_SHA=hashlib.sha256(raw).hexdigest()
    ref.choose_keep=choose_keep
    ref.RULES_VERSION=POLICY+"_"+MODEL_SHA[:16]
    ref.MULLIGAN_POLICY_NAME=POLICY
    ref.MULLIGAN_SAMPLER_NAME="v33b_pairwise_bottom_no_mulligan_beam"
    return MODEL_SHA

def choose_keep(deck_slots,seat,orders):
    assert MODEL is not None
    assert deck_slots==ref.SLOT_VARIANTS["one_key_34"]
    # This call always uses the frozen v27 policies, never ref.choose_keep;
    # the current ref.choose_keep is this v33b wrapper.
    base_state,history=ctl.choose_keep(deck_slots,seat,orders)
    assert history and history[-1]["kept"]
    last=history[-1]
    stage=int(last["stage"]);kn=int(last["keep_n"])
    order=orders[stage]
    seven=tuple(deck_slots[s] for s in order[:7])
    unknown=tuple(deck_slots[s] for s in order[7:])
    assert len(unknown)==92 and Counter(seven)+Counter(unknown)==Counter(ref.VARIANTS["one_key_34"])
    options,_,methods=rank(seven,kn,tuple(sorted(unknown)),seat,stage,
                           ctl.old.MODEL,ctl.MODEL)
    baseline=methods["v14_frozen"]
    assert Counter(options[baseline]["hand"])==Counter(last["hand"])
    assert Counter(options[baseline]["bottom"])==Counter(last["bottom"])
    winner,details=reg.choose(MODEL,seven,tuple(sorted(unknown)),seat,methods,options)
    newhand=tuple(options[winner]["hand"])
    bottom=tuple(options[winner]["bottom"])
    assert Counter(newhand)+Counter(bottom)==Counter(seven)
    assert len(newhand)==kn and len(bottom)==7-kn
    last.update({
        "v33b_bottom_only_override":winner!=baseline,
        "v33b_frozen_v27_baseline_hand":list(last["hand"]),
        "v33b_frozen_v27_baseline_bottom":list(last["bottom"]),
        "v33b_frozen_v27_keep_depth_unchanged":True,
        "v33b_model_sha256":MODEL_SHA,
        "v33b_candidate_methods":methods,
        "v33b_regret_summaries":details,
        "candidate_index":winner,"candidate_count":len(options),
        "hand":list(newhand),"bottom":list(bottom),
        "hand_slots":ref.selected_slots(order[:7],seven,newhand),
        "bottom_slots":ref.selected_slots(order[:7],seven,bottom),
        "policy":POLICY,
    })
    # The exact unknown 92 physical card slots retain their actual
    # shuffled order; bottoms are appended as in original engine.
    return ref.d.State(1,newhand,unknown+bottom),history

def audit():
    sha=install()
    original=ref.audit()
    assert original["status"]=="PASS" and original["mulligan_policy"]==POLICY
    assert ctl.MODEL["T3_reward_is_exactly_zero"] is True
    assert reg.T2_MIN_LOWER==.01 and reg.T3_MIN_MEDIAN==-.025
    return dict(original,
        strict_physical_99=True,
        actual_gameplay_beam=160,
        mulligan_lookahead_beams=0,
        frozen_v27_keep_depth=True,
        altered_bottom_only_if_frozen_v27_keeps=True,
        model_sha256=sha,
        model_approved=False,policy_approved=False)

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--audit",action="store_true")
    p.add_argument("--game",type=int,default=115000)
    a=p.parse_args()
    print("DACK_V33B_BOTTOM_ONLY_AUDIT_PASS",json.dumps(audit()),flush=True)
    if not a.audit:
        if not 115000<=a.game<115256:
            raise ValueError("115k strictly prospective games only")
        print("DACK_V33B_BOTTOM_ONLY_GAME",
              json.dumps(ref.game("one_key_34",a.game)),flush=True)
