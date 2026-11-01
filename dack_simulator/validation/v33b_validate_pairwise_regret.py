#!/usr/bin/env python3
"""v33b fresh 114k test of strictly training-only pairwise bottom regret.

Freeze all v27 London keep depth and v14 baseline choices. After a KEEP,
regret learner can choose only from baseline and the three existing
training-supported candidate generators. All labels use new 114k physical
unseen shuffles and strictly unchanged beam160 gameplay.
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
import dack_paired_counterfactual_v22_all_stage_real_keep_DP_20261101 as ctl
import dack_mulligan_v33b_pairwise_regret as reg
from dack_simulator.validation.v33b_bottom_ranker import rank

PROTO="DACK_V33B_PAIRWISE_HELDOUT_114K_PHYSICAL_20261101"
LO=114000; HI=114063; SHARD=4; FUTURES=8
MODEL_PATH=ROOT/"models/dack_v33b_ridge_regret_EXPERIMENTAL.json"

def seed(*args):
    return int.from_bytes(hashlib.sha256(
        json.dumps((PROTO,*args),separators=(",",":")).encode()).digest()[:8],"big")

def run(start,out):
    if start<LO or start+SHARD-1>HI or (start-LO)%SHARD:
        raise ValueError("114k fresh heldout four-game shards only")
    assert frozen.audit()["status"]=="PASS"
    model=json.loads(MODEL_PATH.read_text())
    assert model["schema"]==reg.SCHEMA
    assert model["training_source_ids"]==[112000,112127]
    assert model["heldout_113k_not_used"] and model["heldout_114k_reserved_for_validation"]
    assert model["policy_approved"] is False
    assert model["training_futures_per_candidate"]==8
    ref=ctl.ref
    assert ref.SPEC["beam"]==160 and len(ref.SLOTS)==99
    deck=ref.SLOT_VARIANTS["one_key_34"]
    results=[]
    started=time.perf_counter()
    for gid in range(start,start+SHARD):
        origin=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
        seat,orders=ref.stage_slots(origin)
        _,hist=ref.choose_keep(deck,seat,orders)
        last=hist[-1];assert last["kept"]
        stage=int(last["stage"]);kn=int(last["keep_n"])
        seven=tuple(deck[s] for s in orders[stage][:7])
        unknown=tuple(sorted(deck[s] for s in orders[stage][7:]))
        assert len(unknown)==92 and Counter(seven)+Counter(unknown)==Counter(ref.VARIANTS["one_key_34"])
        options,_,methods=rank(seven,kn,unknown,seat,stage,ctl.old.MODEL,ctl.MODEL)
        base=methods["v14_frozen"]
        assert Counter(options[base]["hand"])==Counter(last["hand"])
        assert Counter(options[base]["bottom"])==Counter(last["bottom"])
        choose,diagnostics=reg.choose(model,seven,unknown,seat,methods,options)
        outputs={}
        if kn<7:
            for ix in set((base,choose)):
                hand=tuple(options[ix]["hand"]);bottom=tuple(options[ix]["bottom"])
                turns=[]
                for j in range(FUTURES):
                    phys=list(unknown)
                    random.Random(seed("unseen92",gid,j)).shuffle(phys)
                    ref.sim.reset_caches()
                    ref.sim.root.install("one_key_34")
                    ref.sim.m.set_trial_seed(seed("dice",gid,j))
                    turn=int(ref.d._win_turn_from_unknown_order(
                        hand,tuple(phys)+bottom,seat,beam=160,max_turn=3) or 0)
                    assert turn in (0,1,2,3)
                    turns.append(turn)
                outputs[str(ix)]=turns
        results.append({
            "game_id":gid,"seat":seat,"stage":stage,"keep_n":kn,
            "no_bottom":kn==7,"baseline_index":base,"regret_index":choose,
            "baseline_bottom":options[base]["bottom"],
            "regret_bottom":options[choose]["bottom"],
            "selected_method_indices":methods,
            "predictor_signals":diagnostics,
            "outcomes_by_candidate":outputs
        })
        print("DACK_V33B_REGRET_HOLDOUT_GAME",gid,
              "stage",stage,"override",base!=choose,
              "elapsed",round(time.perf_counter()-started,2),flush=True)
    doc={
        "schema":"dack_v33b_pairwise_regret_114k_independent_validation",
        "status":"PASS","game_ids":[start,start+SHARD-1],
        "physical_groups":SHARD,"model_sha256":hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest(),
        "futures_per_selected_arm":FUTURES,"strict_beam":160,
        "v27_keep_depth_frozen":True,
        "v14_default_fallback":True,"new_hidden_futures_only":True,
        "no_training_or_tuning_on_114k":True,
        "outcome_not_feature":True,
        "only_training_supported_candidate_generators":True,
        "goldfish_not_interactive_winrate":True,
        "policy_approved":False,"rows":results}
    dst=Path(out);dst.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(dst,"wt") as f:json.dump(doc,f,sort_keys=True)
    print("DACK_V33B_REGRET_HELDOUT_SHARD_PASS",start,SHARD,
          round(time.perf_counter()-started,2),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--start",type=int,required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args();run(a.start,a.out)
