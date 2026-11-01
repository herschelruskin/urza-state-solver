#!/usr/bin/env python3
"""v33b frozen physical conditional evaluation of existing bottom strategies.

For every independent physical outer game, follow unchanged v27 London
policy to the last kept seven, then compare alternative LEGAL bottoms on
freshly shuffled same 92-card inventory. Stage and seat do not change.
A no-bottom seven is counted but costs no beam evaluations.
No learning, teacher lookahead, or outcome-dependent candidate choice.
"""
from __future__ import annotations
import argparse
from collections import Counter
import gzip
import hashlib
import json
import random
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import dack_paired_counterfactual_v27_T2_only_DP_20261101 as frozen
import dack_paired_counterfactual_v22_all_stage_real_keep_DP_20261101 as controller
from dack_simulator.validation.v33b_bottom_ranker import rank,METHODS
BEAM=160
FUTURES=8
PROTO="DACK_V33B_FROZEN_BOTTOM_SCREEN_WITH_INDEPENDENT_PHYSICAL_FUTURES_1"
SPLITS={"train":(112000,112127),"validation":(113000,113063)}
SHARD=4

def seed(*args):
    h=hashlib.sha256(json.dumps((PROTO,*args),separators=(",",":")).encode()).digest()
    return int.from_bytes(h[:8],"big")

def game(gid,split):
    ref=controller.ref
    deck=ref.SLOT_VARIANTS["one_key_34"]
    original_seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
    seat,orders=ref.stage_slots(original_seed)
    state,history=ref.choose_keep(deck,seat,orders)
    assert history[-1]["kept"]
    last=history[-1]
    stage=int(last["stage"]);kn=int(last["keep_n"])
    order=orders[stage]
    seven=tuple(deck[s] for s in order[:7])
    unknown=tuple(deck[s] for s in order[7:])
    assert len(unknown)==92
    assert Counter(seven)+Counter(unknown)==Counter(ref.VARIANTS["one_key_34"])
    assert Counter(last["hand"])+Counter(last["bottom"])==Counter(seven)
    options,scores,choices=rank(seven,kn,unknown,seat,stage,
                                controller.old.MODEL,controller.MODEL)
    base=options[choices["v14_frozen"]]
    assert Counter(base["hand"])==Counter(last["hand"])
    assert Counter(base["bottom"])==Counter(last["bottom"])
    outcomes={}
    if kn!=7:
        for idx in sorted(set(choices.values())):
            candidate=options[idx]
            hand=tuple(candidate["hand"]);bottom=tuple(candidate["bottom"])
            trials=[]
            for j in range(FUTURES):
                perm=list(unknown)
                random.Random(seed("fresh_unknown_92",split,gid,j)).shuffle(perm)
                ref.sim.reset_caches()
                ref.sim.root.install("one_key_34")
                ref.sim.m.set_trial_seed(seed("stable_effects",split,gid,j))
                t=int(ref.d._win_turn_from_unknown_order(
                    hand,tuple(perm)+bottom,seat,beam=BEAM,max_turn=3) or 0)
                assert t in (0,1,2,3)
                trials.append(t)
            outcomes[str(idx)]=trials
    return {"game_id":gid,"seat":seat,"stage":stage,"keep_n":kn,
            "no_bottom":kn==7,"seven":list(seven),
            "selected":choices,
            "selected_bottoms":{name:options[idx]["bottom"] for name,idx in choices.items()},
            "selected_scores":{name:scores[idx] for name,idx in choices.items()},
            "outcomes_by_candidate_index":outcomes,
            "observed_actual_110k_win_turn_used":False,
            "all_candidate_scorers_search_free":True,
            "unknown_order_was_not_available_to_selectors":True}

def run(split,start,shard,out):
    if split not in SPLITS or shard!=SHARD:
        raise ValueError("must use 4-group physical shards")
    lo,hi=SPLITS[split]
    if not lo<=start<=hi or start+SHARD-1>hi or (start-lo)%SHARD!=0:
        raise ValueError("reserved split IDs only")
    a=frozen.audit();assert a["status"]=="PASS"
    ref=controller.ref
    assert len(ref.SLOTS)==99 and ref.SPEC["beam"]==160
    assert tuple(ref.sim.STAGES)==(7,7,6,5,4,3,2,1)
    st=time.perf_counter()
    rows=[]
    for gid in range(start,start+shard):
        row=game(gid,split)
        rows.append(row)
        print("V33B_BOTTOM_SCREEN_GAME",gid,row["stage"],
              row["selected"],round(time.perf_counter()-st,2),flush=True)
    path=Path(out);path.parent.mkdir(exist_ok=True,parents=True)
    report={
        "schema":"dack_v33b_bottom_screen_fresh_physical_futures",
        "status":"PASS","split":split,"game_ids":[start,start+shard-1],
        "physical_groups":SHARD,"futures_per_arm":FUTURES,
        "actual_gameplay_beam":BEAM,"methods":METHODS,
        "no_training_on_archived_110k_diagnostics":True,
        "no_actual_future_order_visible_to_bottom_selector":True,
        "same_92_unknown_shuffle_and_chance_seed_between_candidates":True,
        "no_mulligan_or_gameplay_engine_changes":True,
        "model_approved":False,"policy_approved":False,
        "source_sha":{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
           for p in ("models/v14_curve/v14_teacher_groups_128.json",
              "models/dack_v27_expanded_T2_only_value_EXPERIMENTAL.json",
              "models/dack_v18_paired_candidate_utility_EXPERIMENTAL.json",
              "models/dack_v27_T2_only_continuations_EXPERIMENTAL.json")},
        "rows":rows}
    with gzip.open(path,"wt") as f:json.dump(report,f,sort_keys=True)
    print("DACK_V33B_BOTTOM_SCREEN_SHARD_PASS",split,start,shard,
          round(time.perf_counter()-st,2),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--split",choices=list(SPLITS),required=True)
    p.add_argument("--start",type=int,required=True)
    p.add_argument("--games",type=int,default=SHARD)
    p.add_argument("--out",required=True)
    x=p.parse_args();run(x.split,x.start,x.games,x.out)
