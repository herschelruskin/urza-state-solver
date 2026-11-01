#!/usr/bin/env python3
"""v36 outcome-blind true KEEP labels for archived training manifest or 124k holdout.

Before each sampled future, evaluate EXACT frozen v27 current QKEEP
and immutable v33b legal bottom on the observed 7; 16 (train) or
12 (independent validation) shuffled unknown92 hidden physical orders
plus stable seeded chance. Never use actual hidden next cards as features.
The stage0 and stage1 sevens remain separate.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,random,sys,time
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from dack_simulator.validation import v34_frozen_v33b_continuation as kernel
import dack_mulligan_v36_features as feats

SCHEMA="dack_v36_real_keep_value_labels_1"
FUTURES={"train":16,"holdout":12}
PROTO="DACK_V36_TRUE_KEEP_123K_TRAIN_124K_UNSEEN_V1"
MANIFEST=ROOT/"datasets/v36_preoutcome_123k_manifest.json"

def stable_seed(*args):
    return int.from_bytes(hashlib.sha256(json.dumps(
        (PROTO,*args),separators=(",",":")).encode()).digest()[:8],"big")

def expected(split,index):
    if split=="train":
        data=json.loads(MANIFEST.read_text())
        assert data["schema"]=="dack_v36_preoutcome_stratified_123k_physical_training_manifest_1"
        assert data["status"]=="PASS" and data["selection_by_predecision_features_only"]
        assert data["labels_available_only_after_manifest_frozen"]
        assert data["frozen_v33b_bottom_sha256"]==kernel.v33b.MODEL_SHA
        assert len(data["groups"])==256
        assert sorted(x["game_id"] for x in data["groups"])==sorted(set(x["game_id"] for x in data["groups"]))
        assert sum(x["sample"]=="random" for x in data["groups"])==128
        assert sum(x["sample"]=="boundary_enriched" for x in data["groups"])==128
        return data["groups"][index:index+4],hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    if split=="holdout":
        if index%4 or not 0<=index<128:raise ValueError("holdout index must be physical 4-group")
        return [{"game_id":124000+i,"sample":"unconditional_holdout",
                 "selection":None} for i in range(index,index+4)],"fresh_random_124k_unselected"
    raise ValueError("unrecognized split")

def run(split,index,out):
    kernel.initialize();feats.selftest()
    if index<0 or index%4 or index>= (256 if split=="train" else 128):
        raise ValueError("index four-group shard range")
    groups,manifest_sha=expected(split,index)
    assert len(groups)==4
    ref=kernel.ref;deck=ref.SLOT_VARIANTS[kernel.DECK_KEY]
    assert len(ref.SLOTS)==99 and ref.SPEC["beam"]==160
    started=time.monotonic();rows=[]
    for grp in groups:
        gid=int(grp["game_id"])
        seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
        seat,orders=ref.stage_slots(seed)
        for stage in (0,1,2):
            order=orders[stage]
            seven=tuple(deck[t] for t in order[:7])
            unknown=tuple(deck[t] for t in order[7:])
            assert len(seven)==7 and len(unknown)==92
            assert Counter(seven)+Counter(unknown)==Counter(deck.values())
            sel=kernel.current(seven,unknown,seat,stage)
            assert sel["keep_n"]==int(ref.sim.STAGES[stage])
            features=feats.extract(seven,sel["hand"],sel["bottom"],
                                   tuple(sorted(unknown)),seat,stage,
                                   sel["old_v27_Qkeep"],sel["old_v27_DP"])
            counts=[]
            for j in range(FUTURES[split]):
                hidden=list(unknown)
                random.Random(stable_seed("actual_unseen92",split,gid,stage,j)).shuffle(hidden)
                state=kernel.state_from(seven,tuple(hidden),sel)
                ref.sim.reset_caches();ref.sim.root.install(kernel.DECK_KEY)
                ref.sim.m.set_trial_seed(stable_seed("chance",split,gid,stage,j))
                turn=int(ref.d._win_turn_from_unknown_order(
                    state.hand,state.library,seat,beam=160,max_turn=3) or 0)
                assert turn in (0,1,2,3)
                counts.append(turn)
            rows.append({
              "game_id":gid,"source_stratum":grp["sample"],
              "selection_metadata":grp["selection"],
              "seat":seat,"stage":stage,"keep_n":sel["keep_n"],
              "seven":list(seven),"hand":list(sel["hand"]),"bottom":list(sel["bottom"]),
              "frozen_v27_old_keep":sel["old_v27_keep"],
              "old_v27_Qkeep":sel["old_v27_Qkeep"],
              "old_v27_C":sel["old_v27_DP"],
              "v33b_bottom_override":sel["v33b_overrode_bottom"],
              "features":list(features),"true_turns":counts,
              "cumulative_T2":sum(0<t<=2 for t in counts)/len(counts),
              "cumulative_T3":sum(0<t<=3 for t in counts)/len(counts)
            })
        print("DACK_V36_OUTCOME_BLIND_PHYSICAL_GROUP_PASS",split,gid,
              "elapsed",round(time.monotonic()-started,2),flush=True)
    assert len(rows)==12
    doc={
      "schema":SCHEMA,"status":"PASS","split":split,
      "manifest_sha256":manifest_sha,"index":index,
      "physical_groups":4,"game_ids":[g["game_id"] for g in groups],
      "stages":[0,1,2],"futures_per_state":FUTURES[split],
      "strict_actual_gameplay_beam160":True,
      "v33b_bottom_sha256":kernel.v33b.MODEL_SHA,
      "v36_feature_schema_sha256":feats.feature_hash(),
      "no_known_hidden_library_order_in_prediction":True,
      "training_selection_before_outcomes":True,
      "no_full_game_or_v5_policy_label":True,
      "rows":rows}
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,"wt") as f:json.dump(doc,f,sort_keys=True)
    print("DACK_V36_QKEEP_PHYSICAL_SHARD_PASS",split,index,flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--split",choices=tuple(FUTURES),required=True)
    p.add_argument("--index",type=int,required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args();run(a.split,a.index,a.out)
