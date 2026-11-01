#!/usr/bin/env python3
"""v46 research-only one-stage-at-a-time first/second seven KEEP correction.

Stage0 variant ALWAYS retains frozen v43 stage1+ continuation.
Stage1 variant ALWAYS retains frozen v43 stage0 and stages2+.
Therefore the 128-sample physical Qmull thresholds are policy-consistent
for the edited stage. Never merge both edits without redoing stage0 Qmull.
"""
from __future__ import annotations
import json,hashlib
from pathlib import Path
from collections import Counter
import dack_paired_counterfactual_v43_v27_max_Q2_20261101 as original
import dack_mulligan_v46_first_two_sevens_physical as f
from dack_simulator.validation import v45_frozen_v43_continuation as kernel

ROOT=Path(__file__).resolve().parent
MODEL_PATH=ROOT/"models/v46_early_Q2_residual_RESEARCH.json"
DEV_PATH=ROOT/"benchmark_results/v46_first_two_sevens_random_dev_N64.json"
ref=kernel.ref
POLICY="dack_v46_one_stage_early_real_Q2_calibration_UNAPPROVED"
STAGE=None;MODE=None;MODEL=None

def install(stage,mode,require_dev=True):
    global STAGE,MODE,MODEL
    assert stage in (0,1) and mode in ("C_only","ridge_C")
    info=kernel.initialize()
    assert info["status"]=="PASS"
    doc=json.loads(MODEL_PATH.read_text())
    assert doc["schema"]==f.SCHEMA and doc["policy_approved"] is False
    assert doc["original_99_card_deck"]=="one_key_34"
    assert doc["feature_hash"]==f.f.feature_hash()
    assert doc["stage0_and_stage1_must_not_be_simultaneously_edited_under_old_stage0_C"]
    if require_dev:
        dev=json.loads(DEV_PATH.read_text())
        assert dev["status"]=="PASS" and dev["no_model_or_policy_approved"]
        assert dev["source_model_sha256"]==f.hash_file(MODEL_PATH)
        assert dev["dev_results"][str(stage)][mode]["development_gate_pass"],(
          "Model has no predeclared dev clearance for real full-game test",stage,mode)
    STAGE=stage;MODE=mode;MODEL=doc
    ref.choose_keep=choose_keep
    ref.MULLIGAN_POLICY_NAME=f"{POLICY}_stage{stage}_{mode}"
    ref.MULLIGAN_SAMPLER_NAME="no_teacher_rollouts_exact_v43_downstream"
    return {"status":"PASS","stage":stage,"mode":mode,
       "model_sha256":f.hash_file(MODEL_PATH),
       "no_v5_lookahead":True,"policy_approved":False,
       "all_other_london_stages_original_v43":True,
       "physical_C128_applies_to_unmodified_future_policy":True}

def choose_keep(deck_slots,seat,orders):
    assert STAGE in (0,1) and MODE in ("C_only","ridge_C") and MODEL is not None
    assert deck_slots==ref.SLOT_VARIANTS["one_key_34"]
    history=[]
    for stage,order in enumerate(orders):
        a=kernel.choose_at(stage,seat,order,deck_slots)
        q=float(a["raw"]);threshold=float(a["threshold"])
        original_keep=bool(a["kept"])
        if stage==STAGE:
            seven=tuple(a["seven"])
            unseen=tuple(deck_slots[s] for s in order[7:])
            assert len(a["bottom"])==0 and Counter(a["hand"])==Counter(seven)
            assert len(unseen)==92
            cell=MODEL["frozen_v43_true_full99_C128_physical"][f"{seat}:{stage}"]
            threshold=float(cell["T2"])
            if MODE=="ridge_C":
                xx=f.features(seven,unseen,seat,stage,q,float(a["threshold"]))
                q=f.corrected(MODEL,xx,q)
            kept=bool(q>=threshold)
        else:
            kept=original_keep
        hand=tuple(a["hand"]);bottom=tuple(a["bottom"])
        h={
            "stage":stage,"keep_n":a["keep_n"],"kept":kept,
            "raw":round(q,7),"threshold":round(threshold,7),
            "refined":False,"sampled_t1":None,
            "candidate_index":a["candidate_index"],
            "seven_slots":list(order[:7]),"seven":a["seven"],
            "hand":list(hand),"bottom":list(bottom),
            "hand_slots":ref.selected_slots(order[:7],a["seven"],hand),
            "bottom_slots":ref.selected_slots(order[:7],a["seven"],bottom),
            "policy":ref.MULLIGAN_POLICY_NAME,
        }
        history.append(h)
        if kept:return a["state"],history
    raise AssertionError("one-card terminal London must keep")

def audit(stage=0,mode="C_only"):
    return install(stage,mode)

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--stage",type=int,choices=(0,1),required=True)
    p.add_argument("--mode",choices=("C_only","ridge_C"),required=True)
    p.add_argument("--game",type=int)
    a=p.parse_args()
    info=audit(a.stage,a.mode)
    print("DACK_V46_EARLY_ONE_STAGE_ONLY_POLICY_AUDIT_PASS",json.dumps(info),flush=True)
    if a.game is not None:
        q=ref.game("one_key_34",a.game)
        print("DACK_V46_EXPERIMENTAL_GAME",json.dumps({
          "gid":a.game,"win_turn":q["win_turn"],"keep_n":q["keep_n"],
          "history":q["history"]}),flush=True)
