#!/usr/bin/env python3
"""EXPERIMENTAL confidence-gated London policy, learned v11 + exact v5 fallback.

Train/calibration IDs, v11 paired IDs 42k, and the three v11 missed-T2
diagnostic seeds are development data. The 0.075 fallback band is chosen
AFTER looking at those failures. Fresh 43k IDs are strictly required for
honest end-to-end assessment; do not infer performance from development.

For each stage:
 - model scores ALL legal London bottom choices; 
 - if abs(max learned utility - learned DP continuation threshold) > 0.075:
     use learned bottom and keep/mull directly, no beam;
 - otherwise call the ORIGINAL, exact-per-sample bounded 8/16-future
   mulligan evaluator and use its hand selection + assertive cutoff.
Actual gameplay remains the inherited beam-160 strict/stable-dice solver.
"""
from __future__ import annotations
from collections import Counter
import argparse
import hashlib
import json

import dack_paired_counterfactual_v8_learned_london_20261031 as learned
import dack_paired_counterfactual_v5_stable_chance_20261031 as oracle
from dack_simulator.validation.derive_learned_london_dp_v8 import best_candidate

ref=learned.ref
MODEL="models/dack_v11_corrective_EXPERIMENTAL.json"
DP_DIR="models/v11_dp"
MARGIN=0.075
VERSION_PREFIX="dack_development_only_learned_v11_hybrid_m075"
STATS=Counter()

def choose_keep(deck_slots,seat,order_by_stage):
    if learned.MODEL is None or not learned.CONTINUATIONS:
        raise RuntimeError("No loaded frozen learned model and DP tables")
    name=next((n for n,x in ref.SLOT_VARIANTS.items() if x==deck_slots),None)
    if name is None:raise ValueError("Unregistered physical-99 deck")
    cutoffs=learned.CONTINUATIONS[name]["seats"][str(seat)]["thresholds_by_london_stage"]
    history=[]
    for stage,(keep_n,order) in enumerate(zip(ref.sim.STAGES,order_by_stage)):
        seven=tuple(deck_slots[s] for s in order[:7])
        unknown=tuple(deck_slots[s] for s in order[7:])
        (predicted,structure),hand,bottom,probs=best_candidate(
            seven,unknown,seat,keep_n,learned.MODEL)
        predicted_cutoff=float(cutoffs[stage])
        margin=float(predicted)-predicted_cutoff
        should_fallback=(int(keep_n)>1 and abs(margin)<=MARGIN)
        if should_fallback:
            STATS["beam_fallback_stages"]+=1
            raw,ev,struct,hand,bottom,actual_unknown,ignored,refined=(
                ref.batch.evaluate_keep(seven,keep_n,unknown,seat))
            if tuple(actual_unknown)!=unknown:
                raise AssertionError("Fallback changed unknown physical deck")
            standard=0. if keep_n==1 else ref.batch.FROZEN_CONTINUATION[keep_n-1]
            native_keep=float(raw)>=standard
            t1=float(ev["t1"])
            bump=ref.sim.ASSERTIVE_BUMPS.get(keep_n,0.)
            threshold=standard+(0. if native_keep and t1>0 else bump)
            keep=(keep_n==1 or float(raw)>=threshold)
            score=float(raw)
            source="exact_bounded_v5_fallback"
        else:
            STATS["model_only_stages"]+=1
            refined=False
            score=float(predicted)
            threshold=predicted_cutoff
            t1=float(probs[1])
            keep=(keep_n==1 or score>=threshold)
            source="learned_v11_only"
        STATS["london_stages"]+=1
        STATS["keep" if keep else "mull"]+=1
        history.append({
            "stage":stage,"keep_n":int(keep_n),"kept":bool(keep),
            "raw":round(score,7),"threshold":round(threshold,7),
            "sampled_t1":round(t1,7),"refined":bool(refined),
            "decision_source":source,
            "model_score":round(float(predicted),7),
            "model_cutoff":round(predicted_cutoff,7),
            "model_margin":round(margin,7),
            "fallback":should_fallback,
            "model_predicted_probs":list(probs),
            "source_model_hash":learned.POLICY_HASH,
            "seven_slots":list(order[:7]),"seven":list(seven),
            "hand":list(hand),"bottom":list(bottom),
            "hand_slots":ref.selected_slots(order[:7],seven,hand),
            "bottom_slots":ref.selected_slots(order[:7],seven,bottom),
        })
        if keep:
            if len(hand)!=keep_n or len(unknown)!=92:
                raise AssertionError("London kept-hand invariant violated")
            return ref.d.State(1,tuple(hand),tuple(unknown)+tuple(bottom)),history
    raise AssertionError("Hybrid London did not keep terminal hand")

def audit():
    oracle.audit()
    learned.audit(MODEL,DP_DIR,allow_diagnostic=True)
    # Oracle's exact bounded/same-dice future evaluator remains installed.
    oracle.install()
    if learned.MODEL.get("deployed_policy_approved") is not False:
        raise AssertionError("Experiment requires unapproved model")
    ref.RULES_VERSION=VERSION_PREFIX+"_"+learned.POLICY_HASH[:16]
    ref.MULLIGAN_POLICY_NAME=VERSION_PREFIX
    ref.MULLIGAN_SAMPLER_NAME="learned_or_exact_beam_ambiguous_only"
    ref.choose_keep=choose_keep
    result=ref.audit()
    assert result["status"]=="PASS" and result["mulligan_policy"]==VERSION_PREFIX
    return dict(result,
        learned_model_approved_for_production=False,
        experimental_mulligan_ambiguity_band=MARGIN,
        ambiguity_band_selected_after_42k_development_trace=True,
        strict_holdout_seed_min=43000,
        full_gameplay_beam=160,
        fallback_uses_original_8_to_16_sample_policy=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--audit",action="store_true")
    p.add_argument("--single-variant",choices=list(ref.VARIANTS))
    p.add_argument("--start",type=int,default=43000)
    p.add_argument("--games",type=int,default=1)
    p.add_argument("--out",default="shards/hybrid_m075_43000.json.gz")
    p.add_argument("--store",default=None)
    a=p.parse_args()
    if not a.audit and not 43000<=a.start and a.start+a.games<=44000:
        raise ValueError("Hybrid experiments must run exclusively on fresh 43k seed band")
    result=audit()
    if a.audit:
        print(json.dumps(result,indent=2),flush=True)
    elif a.single_variant:
        print("HYBRID_EXPERIMENTAL_GAME",json.dumps(ref.game(a.single_variant,a.start)),flush=True)
        print("HYBRID_MULLIGAN_STATS",dict(STATS),flush=True)
    else:
        ref.run(a.start,a.games,a.out,a.store)
        print("HYBRID_MULLIGAN_STATS",dict(STATS),flush=True)
