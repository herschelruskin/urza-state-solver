#!/usr/bin/env python3
"""v46 seven-card T2/T3 physical calibration: dependency-free inference.

Only original visible 7, unknown 92 multiset, seat, London stage and frozen
v43 own Q2/DP may enter the input. Exact card identities are summarized by
stable feature names. No original v5 beam search, future card order, physical
draw rollouts or sklearn at inference time.
"""
from __future__ import annotations
import json,hashlib,struct
from collections import Counter
from pathlib import Path
import dack_mulligan_teacher_features_v13_20261031 as f
from dack_simulator.validation.collect_teacher_london_v13 import finalists

SCHEMA="dack_v46_two_sevens_physical_forest_v1"
BASE=tuple(i for i,n in enumerate(f.FEATURES)
    if (i<24 or n in (
        "seven_lands","seven_white_sources","seven_tutor_count",
        "hand_key_cards","seven_key_cards",
        "enlightened_white_t1","gardens_led_t1","fast_generic_t1",
        "mana_vault_tomb","mana_vault_city","sol_tomb","sol_city",
        "can_produce_white_and_two_generic")
        or n.startswith("pair:") or n.startswith("group:")))
NAMES=("frozen_v43_Q2","frozen_v43_DP")+tuple(f.FEATURES[i] for i in BASE)
BLEND=0.50
DEADBAND=0.05
T3_LOSS_CAP=0.10

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def fp32(x):
    return struct.unpack("<f",struct.pack("<f",float(x)))[0]

def features(seven,unknown_counts,seat,stage,v43_q,v43_c):
    if stage not in (0,1):raise ValueError("calibration applies only to original seven")
    seven=tuple(seven)
    opts=finalists(seven,7,tuple(k for k,v in unknown_counts.items() for _ in range(v)))
    assert len(opts)==1 and opts[0]["bottom"]==[] and opts[0]["hand"]==list(seven)
    x=f.extract(seven,seven,(),Counter(unknown_counts),seat,7,stage,
                opts[0]["struct_rank"],0)
    return [float(v43_q),float(v43_c)]+[float(x[i]) for i in BASE]

def head(model,name,xx):
    trees=model["heads"][name]
    assert len(xx)==len(model["feature_names"])==len(NAMES)
    assert len(trees)==80
    vals=[fp32(z) for z in xx]
    score=0.0
    for t in trees:
        i=0
        while t["left"][i]>=0:
            fi=t["feature"][i]
            i=t["left"][i] if vals[fi]<=t["threshold"][i] else t["right"][i]
        score+=t["value"][i]
    return max(0.,min(1.,score/len(trees)))

def physical_predictions(model,x):
    raw2=head(model,"T2",x)
    raw3=head(model,"T3",x)
    q43=x[0]
    pred2=max(0.,min(1.,(1-BLEND)*q43+BLEND*raw2))
    # T3 cannot be blended with baseline T2 since the target differs.
    pred3=raw3
    return pred2,pred3

def decide(model,x,seat,stage,old_keep):
    p2,p3=physical_predictions(model,x)
    c=model["shared_C"][str(seat)][str(stage)]
    diff=p2-c["T2"]
    proposal=(True if diff>DEADBAND else
             False if diff< -DEADBAND else bool(old_keep))
    # Don't switch if trained predicted T3 outcome sacrifices > 10pp.
    if (int(proposal)-int(old_keep))*(p3-c["T3"]) < -T3_LOSS_CAP:
        proposal=bool(old_keep)
    return bool(proposal),p2,p3

def load(path):
    m=json.loads(Path(path).read_text())
    assert m["schema"]==SCHEMA and m["policy_approved"] is False
    assert m["source_feature_sha256"]==f.feature_hash()
    assert tuple(m["feature_names"])==NAMES
    assert m["blend"]==BLEND and m["deadband"]==DEADBAND
    assert m["t3_harm_cap"]==T3_LOSS_CAP
    assert m["train_independent_groups"]==128
    assert set(m["heads"])=={"T2","T3"}
    assert set(m["shared_C"])=={str(s) for s in range(4)}
    assert all(set(v)=={"0","1"} for v in m["shared_C"].values())
    return m
