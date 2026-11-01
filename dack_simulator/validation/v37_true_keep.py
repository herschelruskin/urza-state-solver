#!/usr/bin/env python3
"""v37 true beam160 KEEP physical labels, blind to future hidden92 order.

Random: 256 independent groups, all actual stages0,1,2 ×8 futures.
Enriched: 128 other physical groups, ONE preselected v13-v27
action-disagreement stage/group ×48 futures. Selection manifest sealed
before any 126k gameplay outcome. Every label a real strict beam160
goldfish deployment under original v33b bottom.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,random,sys,time
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from dack_simulator.validation import v34_frozen_v33b_continuation as kernel
import dack_mulligan_v37_features as feats

MANIFEST=ROOT/"datasets/v37_preoutcome_training_manifest.json"
SCHEMA="dack_v37_real_physical_126k_direct_regret_KEEP_source_v1"
FUTURES={"random":8,"enriched":48}
PROTO="DACK_V37_KEEP_126K_OUTCOME_BLIND_REAL_BEAM160"

def seed(*parts):
    return int.from_bytes(hashlib.sha256(json.dumps(
      (PROTO,*parts),separators=(",",":")).encode()).digest()[:8],"big")

def run(part,index,out):
    assert part in FUTURES and index>=0 and index%4==0
    n=256 if part=="random" else 128
    assert index+4<=n
    kernel.initialize();feats.smoke()
    m=json.loads(MANIFEST.read_text())
    assert m["schema"]=="dack_v37_outcome_blind_three_strata_manifest_v1"
    assert m["status"]=="PASS" and m["selection_outcome_blind"]
    assert m["v33b_frozen_sha256"]==kernel.v33b.MODEL_SHA
    groups=(m["random_groups"] if part=="random" else m["enriched_groups"])[index:index+4]
    assert len(groups)==4
    ref=kernel.ref;deck=ref.SLOT_VARIANTS[kernel.DECK_KEY]
    t0=time.monotonic();rows=[]
    for group in groups:
        gid=group["game_id"]
        seat,orders=ref.stage_slots(int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE)
        if part=="enriched":assert group["seat"]==seat
        stages=(0,1,2) if part=="random" else (group["stage"],)
        for stage in stages:
            seven=tuple(deck[t] for t in orders[stage][:7])
            unknown=tuple(deck[t] for t in orders[stage][7:])
            assert len(unknown)==92 and Counter(seven)+Counter(unknown)==Counter(deck.values())
            sel=kernel.current(seven,unknown,seat,stage)
            if part=="enriched":
                assert sel["old_v27_keep"]==group["v27_keep"]
                assert abs(sel["old_v27_Qkeep"]-sel["old_v27_DP"]-group["v27_margin"])<1e-12
            features=feats.extract(seven,unknown,seat,stage,sel)
            trials=[]
            for j in range(FUTURES[part]):
                hidden=list(unknown)
                random.Random(seed(part,gid,stage,j,"unknown92")).shuffle(hidden)
                state=kernel.state_from(seven,tuple(hidden),sel)
                ref.sim.reset_caches();ref.sim.root.install(kernel.DECK_KEY)
                ref.sim.m.set_trial_seed(seed(part,gid,stage,j,"physicalchance"))
                w=int(ref.d._win_turn_from_unknown_order(
                    state.hand,state.library,seat,beam=160,max_turn=3) or 0)
                assert w in (0,1,2,3)
                trials.append(w)
            rows.append({
              "game_id":gid,"seat":seat,"stage":stage,
              "group_source":group["sample"],
              "physical_source_partition":part,
              "seven":list(seven),"hand":list(sel["hand"]),
              "bottom":list(sel["bottom"]),
              "old_keep":sel["old_v27_keep"],
              "features":list(features),
              "old_v27_Qkeep":sel["old_v27_Qkeep"],
              "old_v27_C":sel["old_v27_DP"],
              "true_turns":trials,
              "true_K_T2":sum(0<t<=2 for t in trials)/len(trials),
              "true_K_T3":sum(0<t<=3 for t in trials)/len(trials),
            })
        print("DACK_V37_126K_TRUE_KEEP_GROUP",part,gid,
              "elapsed",round(time.monotonic()-t0,2),flush=True)
    assert len(rows)==(12 if part=="random" else 4)
    doc={
      "schema":SCHEMA,"status":"PASS","part":part,"index":index,
      "physical_groups":4,"game_ids":[g["game_id"] for g in groups],
      "selection_manifest_sha256":hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
      "source_v33b_sha256":kernel.v33b.MODEL_SHA,
      "feature_sha256":feats.feature_hash(),
      "futures_per_stage":FUTURES[part],
      "stage_count_per_game":3 if part=="random" else 1,
      "strict_gameplay_beam160":True,
      "no_v5_action_as_training_label":True,
      "all_99_physical_deck_and_actual_first_two_sevens":True,
      "blind_hidden92_shuffle_from_multiset":True,
      "policy_approved":False,"rows":rows
    }
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,"wt") as f:json.dump(doc,f,sort_keys=True)
    print("DACK_V37_KEEP_PHYSICAL_SHARD_PASS",part,index,flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--part",choices=list(FUTURES),required=True)
    p.add_argument("--index",type=int,required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args();run(a.part,a.index,a.out)
