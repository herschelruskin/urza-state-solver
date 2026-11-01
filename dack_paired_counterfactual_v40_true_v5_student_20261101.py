#!/usr/bin/env python3
"""Frozen v40 true-v5 behavior-clone London policy; research only.
Reuses the v13 tested pure-Python two-head inference and rules by mapping
v40 selected feature columns back onto the original 347-feature indices.
No v5 hypothetical search is performed when choosing mulligans.
"""
from __future__ import annotations
import json,hashlib,sys
from pathlib import Path
import dack_paired_counterfactual_v13_teacher_distill_20261031 as prior
import dack_mulligan_teacher_features_v13_20261031 as f
import dack_mulligan_stateless_roll_v1_20261031 as dice
import dack_counterfactual_rules_v2_strict_key_20261030 as strict

ROOT=Path(__file__).resolve().parent
POLICY="dack_v40_true_v5_clone_20261101"
MODELS={
 "full":"models/v40_true_v5_archived/v40_archived_actual_v5_full_1288_RESEARCH.json",
 "portable":"models/v40_true_v5_archived/v40_archived_actual_v5_portable_1288_RESEARCH.json",
}
MODE=None
MODEL_SHA=None
ref=prior.ref

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def install(mode="portable"):
    global MODE,MODEL_SHA
    if mode not in MODELS:raise ValueError("unknown mode")
    mpath=ROOT/MODELS[mode]
    original=json.loads(mpath.read_text())
    if original["policy_approved"] is not False or original["mode"]!=mode:
        raise ValueError("original v40 model must remain research-only")
    assert original["train_group_n"]==1288
    assert original["source_corpus_sha256"]==sha(ROOT/"datasets/v40_recovered_original_v5_history_1592.jsonl.gz")
    assert original["feature_schema_sha256"]==f.feature_hash()
    indices=original["feature_indices"]
    assert len(indices)==len(original["feature_names"])
    assert all(f.FEATURES[i]==n for i,n in zip(indices,original["feature_names"]))
    assert len(set(indices))==len(indices)
    def expanded(head):
        trees=[]
        for original_tree in original[head]:
            tree=dict(original_tree)
            tree["feature"]=[indices[v] if v>=0 else v
                             for v in original_tree["feature"]]
            trees.append(tree)
        assert len(trees)==48
        return trees
    trained={
        "schema":f.EXPORT_SCHEMA,"feature_hash":f.feature_hash(),
        "source_manifest_sha256":ref.source_sha(ref.MANIFEST_PATH),
        "deployed_policy_approved":False,
        "choice_trees":expanded("choice_trees"),
        "keep_trees":expanded("keep_trees"),
        "keep_cutoff":original["keep_threshold"],
    }
    MODE=mode
    MODEL_SHA=sha(mpath)
    prior.MODEL=trained
    prior.MODEL_SHA=MODEL_SHA
    prior.POLICY=POLICY+"_"+mode
    dice.install()
    prior.ref.rules=strict
    prior.ref.RULES_VERSION=prior.POLICY+"_"+MODEL_SHA[:12]
    prior.ref.MULLIGAN_POLICY_NAME=prior.POLICY
    prior.ref.MULLIGAN_SAMPLER_NAME="none_frozen_actual_v5_behavior_cloning"
    prior.ref.choose_keep=prior.choose_keep
    assert ref.SPEC["beam"]==160 and len(ref.SLOTS)==99
    return MODEL_SHA

def audit(mode="portable"):
    assert strict.rule_smoke()["status"]=="PASS"
    install(mode)
    doc=ref.audit()
    assert doc["mulligan_policy"]==prior.POLICY
    return {
       "status":"PASS","policy":prior.POLICY,"mode":mode,
       "source_sha256":MODEL_SHA,"strict_beam_goldfish":160,
       "v5_lookahead_in_mulligans":0,"policy_approved":False,
       "rules_audit":doc,
    }

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--mode",choices=tuple(MODELS),default="portable")
    p.add_argument("--audit",action="store_true")
    p.add_argument("--game",type=int)
    a=p.parse_args()
    res=audit(a.mode)
    if a.audit:print("DACK_V40_TRUE_STUDENT_AUDIT_PASS",json.dumps(res),flush=True)
    if a.game is not None:
        g=ref.game("one_key_34",a.game)
        print("DACK_V40_TRUE_STUDENT_GAME",json.dumps({
          "game_id":a.game,"turn":g["win_turn"],"seat":g["seat"],
          "keep_n":g["keep_n"],"history":g["history"]}),flush=True)
