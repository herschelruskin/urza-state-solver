#!/usr/bin/env python3
"""v44 runtime-only research residual adjustment to frozen v27 candidate Q2.

A real-physical 154k candidate-level forest is fitted on the TARGET
  observed_P(by T2 | selected exact retained hand) - frozen_v27_Q2
among all original legal structural top12 candidates (not only v14 winner).
The prior v27 Q2 is a useful regularizing prior, not an oracle.

v44 candidate score = clip[0,1](v27_Q2 + 0.50*clip(forest_residual,-.20,.20)).
Use this SAME candidate score for candidate choice and KEEP-vs-DP,
preserving the v43 coupling architecture. No v5 lookahead.

The 0.50 shrinkage and .20 bounded correction are predeclared in code
BEFORE dev physical samples. The model remains unapproved.
"""
from __future__ import annotations
import hashlib,json,struct
from pathlib import Path
import dack_mulligan_teacher_features_v13_20261031 as f
SCHEMA="dack_v44_physically_supervised_candidate_residual_154k"
SHRINKAGE=.50
CLIP_ABS=.20
ESTIMATORS=96
MAX_DEPTH=8
MIN_LEAF=12
EXCLUDED_PREFIXES=("seven:","bottom:")
FEATURE_INDICES=tuple(i for i,name in enumerate(f.FEATURES)
                      if not name.startswith(EXCLUDED_PREFIXES))
def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def tree_predict(trees,values):
    z=0.
    for t in trees:
        node=0
        while t["left"][node]>=0:
            k=int(t["feature"][node])
            raw=float(values[k])
            x32=struct.unpack("<f",struct.pack("<f",raw))[0]
            node=t["left"][node] if x32<=float(t["threshold"][node]) else t["right"][node]
        z+=float(t["value"][node])
    return z/len(trees)
def adjusted(model,features,base_q):
    assert model["schema"]==SCHEMA and model["policy_approved"] is False
    assert model["feature_hash"]==f.feature_hash()
    assert model["shrinkage"]==SHRINKAGE and model["residual_clip_abs"]==CLIP_ABS
    assert tuple(model["feature_indices"])==FEATURE_INDICES
    assert len(features)==len(f.FEATURES)
    raw=tree_predict(model["trees"],[features[j] for j in FEATURE_INDICES])
    residual=min(CLIP_ABS,max(-CLIP_ABS,raw))
    q=max(0.,min(1.,float(base_q)+SHRINKAGE*residual))
    return q
def audit(path):
    m=json.loads(Path(path).read_text())
    assert m["schema"]==SCHEMA and m["policy_approved"] is False
    assert m["feature_hash"]==f.feature_hash()
    assert m["shrinkage"]==SHRINKAGE and m["residual_clip_abs"]==CLIP_ABS
    assert m["training_physical_game_groups"]==192
    assert m["excluded_literal_onehot_cards"]
    assert tuple(m["feature_indices"])==FEATURE_INDICES
    assert len(m["trees"])==ESTIMATORS
    assert m["original_deck"]=="one_key_34"
    return m
