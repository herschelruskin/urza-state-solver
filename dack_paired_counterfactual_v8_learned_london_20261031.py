#!/usr/bin/env python3
"""Deploy a TRAINED, HELD-OUT-calibrated no-beam London value model.

Requires:
  - independently trained four-class JSON probability model;
  - seat- and variant-specific backward-induction continuation tables
    computed WITHOUT gameplay outcomes on a separate seed band.

The model, threshold files and their hashes are immutable per experiment.
No fallback to heuristic v7 is allowed when a model is absent.
This module is an opt-in runner, not activated by imports.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import dack_paired_counterfactual_v1_20261030 as ref
import dack_counterfactual_rules_v2_strict_key_20261030 as strict
import dack_mulligan_stateless_roll_v1_20261031 as dice
import dack_mulligan_learned_features_v8_20261031 as features
from dack_simulator.validation import derive_learned_london_dp_v8 as dp

RULES_VERSION_PREFIX="dack_strict_stable_dice_learned_london_v8"
MODEL=None
CONTINUATIONS={}
POLICY_HASH=None

def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def load(model_path,dp_directory):
    global MODEL,CONTINUATIONS,POLICY_HASH
    model=json.loads(Path(model_path).read_text())
    if model["schema"]!="dack_london_multiclass_softmax_v8":
        raise ValueError("unsupported model")
    if model["feature_sha256"]!=features.feature_hash():
        raise ValueError("model feature signature mismatch")
    # Every arm has its own physical deck and a distinct DP continuation
    # calculation. No arm may reuse another arm's thresholds.
    records={}
    hashes=[_sha(model_path)]
    folder=Path(dp_directory)
    for variant in ref.VARIANTS:
        path=folder / ("dack_london_v8_dp_"+variant+".json")
        if not path.is_file():
            raise FileNotFoundError(("missing deck-specific DP table",str(path)))
        obj=json.loads(path.read_text())
        if obj["schema"]!=dp.SCHEMA or obj["variant"]!=variant:
            raise ValueError("DP variant/protocol mismatch")
        if obj["feature_sha256"]!=features.feature_hash():
            raise ValueError("DP feature signature mismatch")
        if obj["stage_keep_counts"]!=list(ref.sim.STAGES):
            raise ValueError("London stage sequence changed")
        if sorted(obj["seats"])!=["0","1","2","3"]:
            raise ValueError("must have seat-specific thresholds")
        records[variant]=obj
        hashes.append(_sha(path))
    digest=hashlib.sha256(":".join(hashes).encode()).hexdigest()
    MODEL=model
    CONTINUATIONS=records
    POLICY_HASH=digest
    return digest

def choose_keep(deck_slots,seat,order_by_stage):
    if MODEL is None or not CONTINUATIONS or POLICY_HASH is None:
        raise RuntimeError("trained model and all per-variant DP tables are required")
    # The exact variant is keyed by the game's *physical slot mapping*.
    name=next((k for k,v in ref.SLOT_VARIANTS.items() if v==deck_slots),None)
    if name is None:raise ValueError("unregistered physical deck")
    thresholds=CONTINUATIONS[name]["seats"][str(seat)]["thresholds_by_london_stage"]
    history=[]
    for stage,(keep_n,order) in enumerate(zip(ref.sim.STAGES,order_by_stage)):
        seven=tuple(deck_slots[slot] for slot in order[:7])
        unknown=tuple(deck_slots[slot] for slot in order[7:])
        (utility,structure),hand,bottom,distribution=dp.best_candidate(
            seven,unknown,seat,keep_n,MODEL)
        cutoff=float(thresholds[stage])
        keep=(int(keep_n)==1 or utility>=cutoff)
        history.append({
            "stage":stage,"keep_n":int(keep_n),"kept":bool(keep),
            "raw":round(utility,7),"sampled_t1":round(distribution[1],7),
            "threshold":round(cutoff,7),"refined":False,
            "policy":"learned_model_v8","policy_sha256":POLICY_HASH,
            "predicted_T1":distribution[1],
            "predicted_T2_exact":distribution[2],
            "predicted_T3_exact":distribution[3],
            "predicted_fail_by_T3":distribution[0],
            "seven_slots":list(order[:7]),"seven":list(seven),
            "hand":list(hand),"bottom":list(bottom),
            "hand_slots":ref.selected_slots(order[:7],seven,hand),
            "bottom_slots":ref.selected_slots(order[:7],seven,bottom)})
        if keep:
            return ref.d.State(1,tuple(hand),tuple(unknown)+tuple(bottom)),history
    raise AssertionError("no terminal one-card London keep")

def install(model_path,dp_directory):
    dice.install()
    digest=load(model_path,dp_directory)
    ref.rules=strict
    ref.RULES_VERSION=RULES_VERSION_PREFIX+"_"+digest[:16]
    ref.MULLIGAN_POLICY_NAME="learned_london_v8:"+digest
    ref.MULLIGAN_SAMPLER_NAME="offline_supervised_fourclass_no_beam"
    ref.choose_keep=choose_keep
    return digest

def audit(model_path,dp_directory):
    assert strict.rule_smoke()["status"]=="PASS"
    digest=install(model_path,dp_directory)
    check=ref.audit()
    assert check["rules_version"]==RULES_VERSION_PREFIX+"_"+digest[:16]
    return dict(check,policy_hash=digest,gameplay_beam=160,
                mulligan_beam=0,model_calibrated_offline=True,
                independent_policy_level_holdout_still_required=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--model",required=True)
    p.add_argument("--continuations-dir",required=True)
    p.add_argument("--audit",action="store_true")
    p.add_argument("--single-variant",choices=list(ref.VARIANTS))
    p.add_argument("--start",type=int,default=40000)
    p.add_argument("--games",type=int,default=1)
    p.add_argument("--out",default="shards/learned_london_v8_40000.json.gz")
    p.add_argument("--store",default=None)
    a=p.parse_args()
    report=audit(a.model,a.continuations_dir)
    if a.audit:
        print(json.dumps(report,indent=2))
    elif a.single_variant:
        print("LEARNED_POLICY_GAME",json.dumps(ref.game(a.single_variant,a.start)),flush=True)
    else:
        ref.run(a.start,a.games,a.out,a.store)
