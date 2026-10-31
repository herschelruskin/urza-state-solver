#!/usr/bin/env python3
"""Corrective independent beam labels from hands chosen by learned v8 policy.

This is NOT deploying the unapproved model into normal games. It uses its
frozen decisions as an offline *data-collection behavior policy*, then runs
actual beam-160 gameplay with independently sampled hidden futures.

All game IDs are fresh (22k training, 32k calibration). Previously heldout
33k predictive and 41k paired-game IDs are NEVER reused for training.
Policy drift and learned action exploitation are sampled directly.

The exact source model + all 9 per-variant DP tables must exist and match
their hashes. The live learned runner remains unapproved for promotion.
"""
from __future__ import annotations
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import random
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))

from dack_simulator.validation import generate_offline_london_labels_v8 as common
import dack_paired_counterfactual_v8_learned_london_20261031 as learned

ref=learned.ref
d=ref.d
PROTOCOL="DACK-CORRECTIVE-LEARNED-SELECTED-V11"
MODEL="models/dack_v10_selected_calibration_EXPERIMENTAL.json"
DP_DIR="models"
SPLIT={
    "train":(22000,22999),
    "calibration":(32000,32999),
}
MODEL_HASH=None

def install_source_policy():
    global MODEL_HASH
    result=learned.audit(MODEL,DP_DIR,allow_diagnostic=True)
    assert learned.MODEL["deployed_policy_approved"] is False
    MODEL_HASH=result["policy_hash"]
    return MODEL_HASH

def sample_selected(gid,variant):
    if variant not in ref.VARIANTS:raise KeyError(variant)
    seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
    seat,stages=ref.stage_slots(seed)
    deck=ref.SLOT_VARIANTS[variant]
    state,history=learned.choose_keep(deck,seat,stages)
    final=history[-1]
    stage=int(final["stage"])
    order=stages[stage]
    seven=tuple(deck[s] for s in order[:7])
    unknown=tuple(deck[s] for s in order[7:])
    hand=tuple(state.hand)
    bottom=tuple(final["bottom"])
    assert len(hand)==int(final["keep_n"]) and len(hand)+len(bottom)==7
    assert len(unknown)==92 and tuple(state.library)==unknown+bottom
    assert Counter(seven)+Counter(unknown)==Counter(ref.VARIANTS[variant])
    assert Counter(hand)+Counter(bottom)==Counter(seven)
    return {
        "game_id":gid,"variant":variant,"stage":stage,"seat":seat,
        "seven":seven,"unknown":unknown,"hand":hand,"bottom":bottom,
        "keep_n":int(final["keep_n"]),
        "predicted_raw":float(final["raw"]),
        "predicted_t1":float(final["predicted_T1"]),
        "predicted_t2":float(final["predicted_T2_exact"]),
        "predicted_t3":float(final["predicted_T3_exact"]),
        "threshold":float(final["threshold"]),
        "model_policy_hash":final["policy_sha256"],
    }

def generate(start,games,out,split="train",variant="one_key_34",draws=4):
    if split not in SPLIT:raise ValueError("split not supported")
    lo,hi=SPLIT[split]
    if games<1 or draws<1 or not lo<=start<=start+games-1<=hi:
        raise ValueError("game IDs must stay within one independent split")
    version=install_source_policy()
    target=Path(out);target.parent.mkdir(parents=True,exist_ok=True)
    counts=Counter();begin=time.monotonic()
    header={
        "type":"metadata","schema":common.SCHEMA,"split":split,
        "start":start,"games":games,"variant":variant,
        "rules":common.LABEL_RULES,"beam":160,"max_turn":3,
        "draws_per_choice":draws,"choice_count_max":1,
        "source_physical_sha256":ref.source_sha(ref.MANIFEST_PATH),
        "source_spec_sha256":ref.source_sha(ref.SPEC_PATH),
        "sampling_protocol":PROTOCOL,
        "sampling_distribution":"natural_physical_7_conditioned_on_unapproved_learned_v8_kept_hand",
        "source_learned_policy_hash":version,
        "raw_sample_probabilities_biased":False,
        "policy_kept_not_natural_unselected":True,
        "learned_selection_without_hidden_library_peeking":True,
        "independent_hidden_future_draws":True,
        "warning":"Only representative for the FROZEN experimental source learned policy, not v5 nor an updated retrained policy"
    }
    with gzip.open(target,"wt",encoding="utf8") as fp:
        fp.write(json.dumps(header,separators=(",",":"))+"\n")
        for gid in range(start,start+games):
            case=sample_selected(gid,variant)
            assert case["model_policy_hash"]==version
            counts["scenarios"]+=1;counts["kept_"+str(case["keep_n"])]+=1
            for j in range(draws):
                lib=list(case["unknown"])
                randkey=(PROTOCOL,gid,variant,j)
                random.Random(common.seeded(*randkey,"hidden")).shuffle(lib)
                ref.sim.reset_caches()
                ref.sim.root.install(variant)
                ref.sim.m.set_trial_seed(common.seeded(*randkey,"dice"))
                turn=int(d._win_turn_from_unknown_order(
                    case["hand"],tuple(lib)+case["bottom"],
                    case["seat"],beam=160,max_turn=3) or 0)
                assert turn in (0,1,2,3)
                row={
                    "type":"label","game_id":gid,
                    "group_id":f"{variant}:{gid}",
                    "variant":variant,"scenario_stage":case["stage"],
                    "keep_n":case["keep_n"],"seat":case["seat"],
                    "seven":list(case["seven"]),"hand":list(case["hand"]),
                    "bottom":list(case["bottom"]),
                    "unknown_counts":dict(sorted(Counter(case["unknown"]).items())),
                    "candidate_index":0,"future_index":j,"label_turn":turn,
                    "selection_stratum":"learned_v8_policy_selected_natural",
                    "selection_protocol":PROTOCOL,
                    "selection_model_policy_hash":version,
                    "source_predicted_T1":case["predicted_t1"],
                    "source_predicted_T2_exact":case["predicted_t2"],
                    "source_predicted_T3_exact":case["predicted_t3"],
                    "source_predicted_utility":case["predicted_raw"],
                    "source_continuation_threshold":case["threshold"]
                }
                fp.write(json.dumps(row,separators=(",",":"))+"\n")
                counts["labels"]+=1;counts["T"+str(turn)]+=1
            print("CORRECTIVE_REAL_SCENARIO",gid,case["keep_n"],
                  case["predicted_raw"],dict(counts),flush=True)
    print("CORRECTIVE_LEARNED_REAL_LABEL_PASS",json.dumps({
        "source_model_policy_hash":version,
        "split":split,"start":start,"games":games,
        "counts":dict(counts),"seconds":round(time.monotonic()-begin,3)
    },sort_keys=True),flush=True)
    return dict(counts)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--split",choices=tuple(SPLIT),default="train")
    p.add_argument("--start",type=int,default=22000)
    p.add_argument("--games",type=int,default=4)
    p.add_argument("--variant",default="one_key_34",choices=list(ref.VARIANTS))
    p.add_argument("--draws",type=int,default=4)
    p.add_argument("--out",default="datasets/corrective_learned_22000.jsonl.gz")
    a=p.parse_args()
    generate(a.start,a.games,a.out,a.split,a.variant,a.draws)
