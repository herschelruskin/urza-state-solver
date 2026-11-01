#!/usr/bin/env python3
"""Pure Python first-two-seven physical Q2 calibration: no gameplay at inference.

Trained offline on random physical seven-card hands only. Feature manifest
contains capability counts and card-pair interactions but excludes every
literal hand: or seven: one-hot and every bottom feature (no bottom exists).
It predicts a clipped/shrunk correction to FROZEN v43 predicted Q2.
"""
from __future__ import annotations
import json,hashlib,math
from collections import Counter
import dack_mulligan_teacher_features_v13_20261031 as f
from dack_simulator.validation.collect_teacher_london_v13 import finalists

SCHEMA="dack_v46_early_seven_real_physical_residual_ridge_v1"
ALPHA=32.0
SHRINK=0.55
CLIP=0.20
FEATURE_INDICES=tuple(i for i,n in enumerate(f.FEATURES)
    if n in f.base.FEATURES[:24]
    or n in ("london_stage","seven_lands","seven_white_sources",
             "seven_tutor_count","hand_key_cards","seven_key_cards",
             "enlightened_white_t1","gardens_led_t1","fast_generic_t1",
             "mana_vault_tomb","mana_vault_city","sol_tomb","sol_city",
             "can_produce_white_and_two_generic")
    or n.startswith("pair:") or n.startswith("group:"))
NAMES=tuple(f.FEATURES[i] for i in FEATURE_INDICES)+(
    "v43_Q2","v43_Q2_minus_original_DP")

def features(seven,unknown,seat,stage,q,old_C):
    assert stage in (0,1)
    assert len(seven)==7 and len(unknown)==92
    cand=finalists(seven,7,unknown)
    assert len(cand)==1 and tuple(cand[0]["hand"])==tuple(seven)
    assert len(cand[0]["bottom"])==0
    x=f.extract(seven,seven,(),Counter(unknown),seat,7,stage,
                cand[0]["struct_rank"],0)
    return [float(x[i]) for i in FEATURE_INDICES]+[float(q),float(q)-float(old_C)]

def corrected(model,x,q):
    assert model["schema"]==SCHEMA and model["policy_approved"] is False
    assert model["feature_hash"]==f.feature_hash()
    assert model["feature_names"]==list(NAMES)
    assert len(x)==len(NAMES)
    residual=float(model["intercept"])
    for c,v,mu,s in zip(model["coefficients"],x,model["mean"],model["scale"]):
        residual+=float(c)*(float(v)-float(mu))/float(s)
    residual=max(-CLIP,min(CLIP,residual))
    return max(0.,min(1.,float(q)+SHRINK*residual))

def hash_file(path):
    from pathlib import Path
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

if __name__=="__main__":
    print(json.dumps({"feature_count":len(NAMES),"feature_hash":f.feature_hash(),
       "schema":SCHEMA,"alpha":ALPHA,"shrink":SHRINK,"clip":CLIP},sort_keys=True))
