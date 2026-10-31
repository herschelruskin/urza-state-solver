#!/usr/bin/env python3
"""Real beam labels on naturally drawn, policy-SELECTED London hands (v10).

Sampling is not conditioned on future outcomes. For each physical game-id:
  1. draw every London stage by the same public seed as the outer simulator;
  2. let the frozen cheap v7 London policy choose keep_n and bottom;
  3. sample independent, previously unseen complete orders of the 92-card
     unknown library for the chosen kept hand;
  4. run actual beam-160 Dack deployment for outcome labels.

This naturally reflects the v7 *selection distribution*, unlike the
fast-core-enriched v9 data. It is NOT a representative distribution for
the expensive v5 policy or a learned policy (which may select differently).

Never train and calibrate on the same group/game-id. The unseen future draw
order is never serialized; only its physical card multiset is included.
"""
from __future__ import annotations
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import random
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))

import dack_paired_counterfactual_v7_calibrated_nobeam_20261031 as v7
from dack_simulator.validation import generate_offline_london_labels_v8 as common

ref=v7.ref
d=ref.d
PROTOCOL="DACK-SELECTED-LONDON-V10"
LABEL_SCHEMA=common.SCHEMA
TRAIN_START=21000
CAL_START=31000
TRAIN_LIMIT=21999
CAL_LIMIT=31999

def sample_selected(gid,variant):
    if variant not in ref.VARIANTS:raise KeyError(variant)
    seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
    seat,stages=ref.stage_slots(seed)
    deck=ref.SLOT_VARIANTS[variant]
    state,history=v7.analytic.choose_keep(deck,seat,stages)
    chosen=history[-1]
    stage=int(chosen["stage"])
    order=stages[stage]
    seven=tuple(deck[s] for s in order[:7])
    unknown=tuple(deck[s] for s in order[7:])
    hand=tuple(state.hand)
    bottom=tuple(chosen["bottom"])
    assert len(hand)==chosen["keep_n"]
    assert len(bottom)+len(hand)==7
    assert len(unknown)==92
    assert tuple(state.library)==tuple(unknown)+bottom
    assert Counter(seven)+Counter(unknown)==Counter(ref.VARIANTS[variant])
    assert Counter(hand)+Counter(bottom)==Counter(seven)
    return {
        "game_id":gid,"variant":variant,"seat":seat,"stage":stage,
        "keep_n":int(chosen["keep_n"]),"seven":seven,"unknown":unknown,
        "hand":hand,"bottom":bottom,
        "mulligan_history":history,
        "selected_score":float(chosen["raw"]),
        "selected_threshold":float(chosen["threshold"]),
        "policy":v7.POLICY,
    }

def generate(start,games,out,split="train",variant="one_key_34",draws=4):
    lo,hi=(TRAIN_START,TRAIN_LIMIT) if split=="train" else (CAL_START,CAL_LIMIT)
    if split not in ("train","calibration"):raise ValueError("invalid split")
    if games<1 or draws<1 or not lo<=start<=start+games-1<=hi:
        raise ValueError("invalid split, IDs or rollout count")
    v7.audit()
    target=Path(out)
    target.parent.mkdir(parents=True,exist_ok=True)
    seen=Counter();started=time.monotonic()
    meta={
        "type":"metadata","schema":LABEL_SCHEMA,"split":split,
        "start":start,"games":games,"variant":variant,
        "rules":common.LABEL_RULES,"beam":160,"max_turn":3,
        "draws_per_choice":draws,"choice_count_max":1,
        "source_physical_sha256":ref.source_sha(ref.MANIFEST_PATH),
        "source_spec_sha256":ref.source_sha(ref.SPEC_PATH),
        "sampling_protocol":PROTOCOL,
        "sampling_distribution":"natural_physical_7_conditioned_on_v7_kept_hand",
        "recorded_policy":v7.POLICY,
        "selection_is_label_independent":True,
        "raw_sample_probabilities_biased":False,
        "policy_kept_not_natural_unselected":True,
        "independent_hidden_future_draws":True,
        "no_unseen_future_order_in_features":True,
        "limitation":"calibration representative for v7-selected hands, not v5 or learned policy"}
    with gzip.open(target,"wt",encoding="utf8") as fp:
        fp.write(json.dumps(meta,separators=(",",":"))+"\n")
        for gid in range(start,start+games):
            case=sample_selected(gid,variant)
            seen["scenarios"]+=1
            seen["kept_"+str(case["keep_n"])]+=1
            seen["selected_stage_"+str(case["stage"])]+=1
            for j in range(draws):
                lib=list(case["unknown"])
                rng_seed=common.seeded(PROTOCOL,variant,gid,j,"future")
                random.Random(rng_seed).shuffle(lib)
                ref.sim.reset_caches()
                ref.sim.root.install(variant)
                ref.sim.m.set_trial_seed(common.seeded(PROTOCOL,variant,gid,j,"dice"))
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
                    "selection_stratum":"v7_policy_kept_natural",
                    "selection_protocol":PROTOCOL,
                    "selection_policy":case["policy"],
                    "selected_proxy_score":case["selected_score"],
                    "selected_keep_threshold":case["selected_threshold"],
                }
                fp.write(json.dumps(row,separators=(",",":"))+"\n")
                seen["labels"]+=1
                seen["T"+str(turn)]+=1
            print("SELECTED_REAL_GAME",gid,case["keep_n"],
                  dict((f"T{k}",seen[f"T{k}"]) for k in range(4)),
                  round(time.monotonic()-started,3),flush=True)
    print("SELECTED_REAL_LABELS_PASS",json.dumps({
        "schema":LABEL_SCHEMA,"sampling_protocol":PROTOCOL,
        "split":split,"start":start,"games":games,"draws":draws,
        "counts":dict(seen),"seconds":round(time.monotonic()-started,3),
        "warning":"Representative for frozen v7-selected hands only"
    },sort_keys=True),flush=True)
    return dict(seen)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--split",choices=("train","calibration"),default="train")
    p.add_argument("--start",type=int,default=TRAIN_START)
    p.add_argument("--games",type=int,default=4)
    p.add_argument("--draws",type=int,default=4)
    p.add_argument("--variant",choices=list(ref.VARIANTS),default="one_key_34")
    p.add_argument("--out",default="datasets/selected_london_v10_train_21000.jsonl.gz")
    a=p.parse_args()
    generate(a.start,a.games,a.out,a.split,a.variant,a.draws)
