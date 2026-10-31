#!/usr/bin/env python3
"""Derive London continuation thresholds by backward induction, OFFLINE.

For learned conditional utility U(hand,bottom,seat,known deck multiset),
let M_k be the maximum predicted utility over all legal k-card keeps for
one sampled seven. Let C_1 = E[M_1]. For k=2..7:
    C_k = E[max(M_k,C_(k-1))].
At a London stage with k cards to keep, mulligan if M_k < C_(k-1).
The first free seven mulligans into another seven; use C_7, while the
second seven uses C_6. This exact stage distinction matters.

The expectation is approximated over independent outer seven-card draws,
but each M_k evaluates ALL physical bottom subsets and never plays a beam.
This is model-based dynamic programming, not an exact estimate of true
gameplay value. Recompute separately per deck and seat and record seed/proto.
"""
from __future__ import annotations
import argparse
from collections import Counter
from itertools import combinations
import json
import random
from pathlib import Path

import dack_mulligan_learned_features_v8_20261031 as features
import dack_paired_counterfactual_v1_20261030 as ref

SCHEMA="dack_learned_london_dp_continuation_v8"
DP_SEED_START=50000

def bottom_options(seven,keep_n):
    for indexes in combinations(range(7),7-keep_n):
        used=set(indexes)
        hand=tuple(sorted(seven[i] for i in range(7) if i not in used))
        bottom=tuple(seven[i] for i in indexes)
        yield hand,bottom

def best_candidate(seven,unknown,seat,keep_n,model):
    counts=Counter(unknown)
    choice=None
    for hand,bottom in bottom_options(seven,keep_n):
        x=features.extract(hand,bottom,counts,seat,keep_n)
        distribution=features.probability_from_export(model,x)
        score=features.expected_utility(distribution)
        structure=sum(ref.d.bottom_priority(c,seven) for c in bottom)
        rank=(score,structure)
        if choice is None or rank>choice[0]:
            choice=(rank,hand,bottom,distribution)
    return choice

def draw_seven_for_dp(variant,seed):
    slots=list(ref.SLOTS)
    random.Random(int(seed)).shuffle(slots)
    names=ref.SLOT_VARIANTS[variant]
    return tuple(names[x] for x in slots[:7]),tuple(names[x] for x in slots[7:])

def calibrate(model,variant="one_key_34",samples=256,start=DP_SEED_START):
    if samples<2:raise ValueError("need at least 2 independent seven-card draws")
    if variant not in ref.VARIANTS:raise KeyError(variant)
    seat_tables={}
    for seat in range(4):
        continuation={0:0.}
        for keep_n in range(1,8):
            values=[]
            for i in range(samples):
                # Every (seat,keep-size,sample,variant) receives an independent
                # uniform physical slot permutation. No action outcome labels.
                seed=(start*10**8 + seat*10**6 + keep_n*10**4+i +
                      list(ref.VARIANTS).index(variant)*17)
                seven,unknown=draw_seven_for_dp(variant,seed)
                best=best_candidate(seven,unknown,seat,keep_n,model)
                value=best[0][0]
                values.append(max(value,continuation[keep_n-1]))
            continuation[keep_n]=sum(values)/len(values)
            print("LONDON_DP_STAGE",variant,seat,keep_n,
                  round(continuation[keep_n],6),flush=True)
        # Two seven stages: first 7 -> fresh 7; second 7 -> 6.
        thresholds=[continuation[7],continuation[6]]
        thresholds.extend(continuation[k-1] for k in ref.sim.STAGES[2:])
        assert len(thresholds)==len(ref.sim.STAGES)
        assert all(0.<=x<=1. for x in thresholds)
        seat_tables[str(seat)]={
            "continuations_by_keep_n":{str(k):v for k,v in continuation.items()},
            "thresholds_by_london_stage":thresholds,
        }
    return {
        "schema":SCHEMA,"variant":variant,"samples_per_seat_per_keep_n":samples,
        "independent_seed_protocol_start":start,
        "stage_keep_counts":list(ref.sim.STAGES),
        "seats":seat_tables,"feature_sha256":features.feature_hash(),
        "model_train_game_ids_must_not_overlap_dp":True,
        "actual_deployment_labels_used_for_dp":False,
        "warning":"Model-based continuation values require independent policy-level holdout"}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--model",required=True)
    p.add_argument("--variant",default="one_key_34",choices=list(ref.VARIANTS))
    p.add_argument("--samples",type=int,default=256)
    p.add_argument("--start",type=int,default=DP_SEED_START)
    p.add_argument("--out",default="models/dack_london_v8_dp_onekey.json")
    a=p.parse_args()
    model=json.loads(Path(a.model).read_text())
    result=calibrate(model,a.variant,a.samples,a.start)
    dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("LEARNED_LONDON_DP_PASS",str(dest),flush=True)
