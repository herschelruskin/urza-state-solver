#!/usr/bin/env python3
"""Generate honest, offline T1/T2/T3 labels for a learned London value model.

No gameplay beam runs DURING mulligan decisions. Beam=160 is used here only
as an offline source of realized labels. Each training label is generated
by executing a complete future from a *freshly sampled* hidden library.

All feature fields are available at mulligan time; actual library order is
never serialized. Each scenario is grouped by its outer game_id. Distinct
candidate bottoms and rollouts from a scenario MUST remain in one split.

Historical pilot and calibrated no-beam policy game IDs are excluded.
Use separate game-ID bands for training/calibration/heldout policy evaluation.
"""
from __future__ import annotations
import argparse
from collections import Counter
from itertools import combinations
import gzip
import hashlib
import json
from pathlib import Path
import random
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))

import dack_paired_counterfactual_v5_stable_chance_20261031 as teacher
import dack_mulligan_analytic_policy_v6_20261031 as proxy

ref=teacher.reference
d=ref.d
SCHEMA="dack_offline_london_outcomes_v1"
LABEL_RULES="strict_state_stable_dice_actual_beam160"
PROTOCOL_SALT="DACK-LONDON-OFFLINE-V1"
START_TRAIN=20000
START_CALIBRATION=30000
START_POLICY_EVAL=40000
ALLOWED_SPLITS={
    "train":(20000,29999),
    "calibration":(30000,39999),
    "policy_evaluation":(40000,49999)
}

def seeded(*values):
    msg=json.dumps([PROTOCOL_SALT,*values],separators=(",",":"),ensure_ascii=False)
    return int.from_bytes(hashlib.sha256(msg.encode("utf8")).digest()[:8],"big")

def candidates(seven,keep_n,unknown,seat,max_candidates=3):
    """Diverse, policy-independent options with explicit non-oracle selection."""
    n=7-int(keep_n)
    pool=[]
    for inds in combinations(range(7),n):
        taken=set(inds)
        bottom=tuple(seven[i] for i in inds)
        hand=d.sort_hand(seven[i] for i in range(7) if i not in taken)
        structural=sum(d.bottom_priority(seven[i],seven) for i in inds)
        analytic=proxy.proxy_features(hand,unknown,seat)["proxy_utility"]
        pool.append((structural,analytic,hand,bottom))
    by_struct=sorted(pool,key=lambda x:x[0],reverse=True)
    by_analytic=sorted(pool,key=lambda x:(x[1],x[0]),reverse=True)
    selection=[by_struct[0],by_analytic[0]]
    # Additional structured exploration, not outcome-adaptive selection.
    rng=random.Random(seeded(seven,keep_n,seat,"candidate"))
    if len(pool)>2:
        selection.append(pool[rng.randrange(len(pool))])
    selection.extend(by_struct[1:max_candidates+1])
    out=[];seen=set()
    for row in selection:
        # Preserve ordered bottom because the physical London library has
        # a bottom zone; different ordered bottoms need not be equivalent.
        key=(row[2],row[3])
        if key in seen:continue
        seen.add(key)
        out.append((row[2],row[3],row[0]))
        if len(out)>=max_candidates:break
    return out

def sample_scenario(gid,variant,stage=None,max_candidates=3,draws=4):
    if variant not in ref.VARIANTS:raise KeyError(variant)
    seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
    seat,orders=ref.stage_slots(seed)
    if stage is None:
        stage=gid%len(ref.sim.STAGES)
    stage=int(stage)
    keep_n=int(ref.sim.STAGES[stage])
    order=orders[stage]
    names=ref.SLOT_VARIANTS[variant]
    seven=tuple(names[slot] for slot in order[:7])
    unknown=tuple(names[slot] for slot in order[7:])
    assert len(unknown)==92
    return {
        "game_id":gid,"variant":variant,"stage":stage,
        "keep_n":keep_n,"seat":seat,"seven":seven,
        "unknown":unknown,
        "candidate_options":candidates(seven,keep_n,unknown,seat,max_candidates),
        "draws":int(draws)
    }

def generate(start,games,out,variant="one_key_34",max_candidates=3,draws=4,split="train"):
    lo,hi=ALLOWED_SPLITS[split]
    if games<1 or draws<1 or max_candidates<1:raise ValueError("positive sizes only")
    if start<lo or start+games-1>hi:raise ValueError("game IDs violate split boundary")
    teacher.audit()
    ref.sim.root.install(variant)
    target=Path(out);target.parent.mkdir(parents=True,exist_ok=True)
    stats=Counter()
    begin=time.monotonic()
    metadata={
        "schema":SCHEMA,"split":split,"start":start,"games":games,
        "variant":variant,"rules":LABEL_RULES,"beam":int(ref.SPEC["beam"]),
        "max_turn":3,"choice_count_max":max_candidates,"draws_per_choice":draws,
        "source_physical_sha256":ref.source_sha(ref.MANIFEST_PATH),
        "source_spec_sha256":ref.source_sha(ref.SPEC_PATH),
        "seed_protocol":PROTOCOL_SALT,
        "features_visible_at_mulligan_only":True,
        "labels_from_actual_beam_gameplay":True,
        "no_policy_leakage_across_group_splits":True,
        "warning":"Teacher-beam outcomes approximate optimized goldfish deployment, not real multiplayer win probability"
    }
    with gzip.open(target,"wt",encoding="utf8") as f:
        f.write(json.dumps({"type":"metadata",**metadata},separators=(",",":"))+"\n")
        for gid in range(start,start+games):
            case=sample_scenario(gid,variant,max_candidates=max_candidates,draws=draws)
            for ci,(hand,bottom,struct) in enumerate(case["candidate_options"]):
                for j in range(draws):
                    # Distinct random hidden futures conditional on observed
                    # seven and bottom choice. The true future is NOT used.
                    lib=list(case["unknown"])
                    random.Random(seeded(gid,variant,case["stage"],ci,j,"hidden")).shuffle(lib)
                    complete=tuple(lib)+tuple(bottom)
                    # Stable-dice oracle is reset to independent draw seed.
                    ref.sim.reset_caches()
                    ref.sim.root.install(variant)
                    ref.sim.m.set_trial_seed(seeded(gid,variant,case["stage"],ci,j,"dice"))
                    turn=d._win_turn_from_unknown_order(
                        hand,complete,case["seat"],beam=160,max_turn=3)
                    turn=int(turn or 0)
                    assert turn in (0,1,2,3)
                    # Persist known multiset, but NEVER secret sampled draw order.
                    rec={
                        "type":"label","game_id":gid,
                        "group_id":f"{variant}:{gid}",
                        "scenario_stage":case["stage"],"keep_n":case["keep_n"],
                        "variant":variant,"seat":case["seat"],
                        "seven":list(case["seven"]),
                        "hand":list(hand),"bottom":list(bottom),
                        "unknown_counts":dict(sorted(Counter(case["unknown"]).items())),
                        "candidate_index":ci,"future_index":j,
                        "structural_score":list(struct) if isinstance(struct,tuple) else struct,
                        "label_turn":turn}
                    f.write(json.dumps(rec,separators=(",",":"))+"\n")
                    stats["labels"]+=1
                    stats[f"label_{turn}"]+=1
                    if stats["labels"]%4==0:
                        print("OFFLINE_LABEL_PROGRESS",gid,stats["labels"],
                              round(time.monotonic()-begin,2),flush=True)
            stats["scenarios"]+=1
    metadata["observed_labels"]=dict(stats)
    metadata["elapsed_seconds"]=round(time.monotonic()-begin,3)
    print("OFFLINE_LABEL_DATASET_PASS",json.dumps(metadata,sort_keys=True),flush=True)
    return metadata

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--split",choices=tuple(ALLOWED_SPLITS),default="train")
    p.add_argument("--start",type=int,default=20000)
    p.add_argument("--games",type=int,default=1)
    p.add_argument("--variant",choices=list(ref.VARIANTS),default="one_key_34")
    p.add_argument("--candidates",type=int,default=3)
    p.add_argument("--draws",type=int,default=4)
    p.add_argument("--out",default="datasets/dack_offline_london_train_20000.jsonl.gz")
    a=p.parse_args()
    generate(a.start,a.games,a.out,a.variant,a.candidates,a.draws,a.split)
