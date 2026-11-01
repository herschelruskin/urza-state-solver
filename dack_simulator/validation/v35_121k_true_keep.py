#!/usr/bin/env python3
"""v35 121k entirely fresh conditional QKEEP+predicted action audit.

All stage0..6 sevens sampled irrespective of actual baseline London
path. For each retained v33b hand, 8 independent unknown-92 physical
future permutations; prediction frozen BEFORE sampling any future.
All game physics exact stable-dice beam160; no v5 or teacher execution.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,random,sys,time
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from dack_simulator.validation import v34_frozen_v33b_continuation as kernel
import dack_mulligan_v35_action_regret as regret
import dack_mulligan_v35_action_features as features

LO=121000;HI=121127;SHARD=4;FUTURES=8
PATH=ROOT/"models/dack_v35_early_action_regret_EXPERIMENTAL.json"
PROTO="DACK_V35_FRESH121K_QKEEP_20261101"

def seed(*parts):
    return int.from_bytes(hashlib.sha256(json.dumps((PROTO,*parts),separators=(",",":")).encode()).digest()[:8],"big")

def run(start,out):
    if not LO<=start<=HI or (start-LO)%SHARD or start+SHARD-1>HI:
        raise ValueError("reserved 121k holdout four-game shard only")
    kernel.initialize()
    raw=PATH.read_bytes();model=json.loads(raw)
    assert model["schema"]==regret.SCHEMA
    assert model["feature_hash"]==features.hash_names()
    assert model["source_v33b_bottom_sha256"]==kernel.v33b.MODEL_SHA
    assert model["heldout_121k_never_seen"] and not model["policy_approved"]
    ref=kernel.ref;deck=ref.SLOT_VARIANTS[kernel.DECK_KEY]
    assert len(ref.SLOTS)==99 and ref.SPEC["beam"]==160
    starttime=time.perf_counter()
    rows=[]
    for gid in range(start,start+SHARD):
        original=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
        seat,orders=ref.stage_slots(original)
        for stage in range(7):
            kn=int(ref.sim.STAGES[stage]);order=orders[stage]
            seven=tuple(deck[t] for t in order[:7])
            unseen=tuple(deck[t] for t in order[7:])
            assert len(unseen)==92 and Counter(seven)+Counter(unseen)==Counter(deck.values())
            sel=kernel.current(seven,unseen,seat,stage)
            assert sel["keep_n"]==kn
            feat=features.extract(stage,seat,seven,sel["hand"],tuple(sorted(unseen)),
                     sel["old_v27_Qkeep"],sel["old_v27_DP"])
            new_keep,diagnostic=regret.decision(model,feat,stage,sel["old_v27_keep"])
            trials=[]
            for j in range(FUTURES):
                phys=list(unseen)
                random.Random(seed("fresh_unknown92",gid,stage,j)).shuffle(phys)
                state=kernel.state_from(seven,tuple(phys),sel)
                ref.sim.reset_caches();ref.sim.root.install(kernel.DECK_KEY)
                ref.sim.m.set_trial_seed(seed("stable_effects",gid,stage,j))
                turn=int(ref.d._win_turn_from_unknown_order(
                    state.hand,state.library,seat,beam=160,max_turn=3) or 0)
                assert turn in (0,1,2,3)
                trials.append(turn)
            rows.append({
              "game_id":gid,"seat":seat,"stage":stage,"keep_n":kn,
              "raw_seven":list(seven),
              "kept_hand":list(sel["hand"]),
              "legal_bottom":list(sel["bottom"]),
              "original_v27_keep":bool(sel["old_v27_keep"]),
              "new_v35_keep":bool(new_keep),
              "old_Qkeep":sel["old_v27_Qkeep"],
              "old_C":sel["old_v27_DP"],
              "model_prediction":diagnostic,
              "futures":[int(t) for t in trials],
              "physically_unseen_shuffle_not_model_input":True
            })
        print("DACK_V35_121K_PHYSICAL_GAME_PASS",gid,
           "7_stages","elapsed",round(time.perf_counter()-starttime,2),flush=True)
    assert len(rows)==SHARD*7
    doc={
      "schema":"dack_v35_121k_fresh_stages_Qkeep",
      "status":"PASS","game_ids":[start,start+SHARD-1],
      "physical_groups":SHARD,"all_actual_stages":list(range(7)),
      "futures_per_stage":FUTURES,"actual_gameplay_beam":160,
      "model_sha256":hashlib.sha256(raw).hexdigest(),
      "fixed_v33b_sha256":kernel.v33b.MODEL_SHA,
      "no_future_peeking":True,"no_refitting":True,
      "not_full_policy_evaluation":True,"policy_approved":False,
      "rows":rows}
    path=Path(out);path.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(path,"wt") as f:json.dump(doc,f,sort_keys=True)
    print("DACK_V35_121K_QKEEP_SHARD_PASS",start,flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--start",type=int,required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args();run(a.start,a.out)
