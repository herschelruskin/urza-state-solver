#!/usr/bin/env python3
"""Prospective, unfitted feature-validity screen on independent first-seven
observable keeps, with actual strict beam160 forced-keep physical outcomes.
No policy changes, no model training, no saved acceptance cohort access.

168000..168255 never used in prior runs. A feature never sees future draw
order, whereas *after extraction*, conditional physics uses the actual
future 92 order. Do not treat 256 conditional outcomes as exact P(T2).
"""
from __future__ import annotations
import argparse,gzip,json,sys,time
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import dack_paired_counterfactual_v43_v27_max_Q2_20261101 as v43
import dack_turn_aware_legal_mana_features_v48_20261101 as feats
ref=v43.ref
SCHEMA="dack_v48_initial7_168k_physical_label_and_legal_mana_features_independent_v1"
def record(gid):
    deck=ref.SLOT_VARIANTS["one_key_34"]
    seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
    seat,orders=ref.stage_slots(seed)
    seven=tuple(deck[k] for k in orders[0][:7])
    unknown=tuple(deck[k] for k in orders[0][7:])
    assert len(seven)==7 and len(unknown)==92
    assert Counter(seven)+Counter(unknown)==Counter(deck.values())
    # Feature visibility boundary: the analyzer reconstructs a canonical
    # unseen deck, deliberately NOT the real first-draw/hidden order.
    t0=time.perf_counter()
    x=feats.analyze(seven,unknown,seat,7,stage=0,beam=32,depth=9)
    features_seconds=time.perf_counter()-t0
    assert x["hand"]==sorted(seven)
    # No speculative feature state is carried into the physical label.
    ref.sim.reset_caches()
    ref.sim.root.install("one_key_34")
    ref.sim.m.set_trial_seed(seed)
    ref.d._WIN_CACHE.clear()
    t1=time.perf_counter()
    physical=int(ref.d._win_turn_from_unknown_order(
         tuple(sorted(seven)),unknown,seat,beam=160,max_turn=3) or 0)
    physical_seconds=time.perf_counter()-t1
    assert physical in (0,1,2,3)
    # After the physical label, obtain v43's first-stage score for descriptive
    # posthoc calibration. This is a frozen-model prediction, NOT a proposed policy.
    ref.sim.reset_caches()
    ref.sim.root.install("one_key_34")
    _,hist=v43.choose_keep(deck,seat,orders)
    early=hist[0]
    assert early["seven"]==list(seven) and early["stage"]==0
    return {"gid":gid,"seat":seat,"seven":list(seven),"stage0_Q2":early["raw"],
       "stage0_threshold":early["threshold"],
       "stage0_frozen_v43_kept":early["kept"],
       "physical_forced_keep_turn":physical,
       "physical_forced_keep_byT1":int(physical==1),
       "physical_forced_keep_byT2":int(0<physical<=2),
       "physical_forced_keep_byT3":int(0<physical<=3),
       "feat":x,"feature_seconds":features_seconds,
       "physical_seconds":physical_seconds}
def main(start,out):
    assert start in range(168000,168256,32)
    v43.audit()
    rows=[]
    for gid in range(start,start+32):
        rows.append(record(gid))
        if len(rows)%8==0:
            print("DACK_V48_FIRST_SEVEN_PHYSICAL_PROGRESS",gid,
              "witness_T1",sum(r["feat"]["mana_witness_T1_no_draw"] for r in rows),
              "witness_T2",sum(r["feat"]["mana_witness_T2_no_draw"] for r in rows),
              "actual_T2",sum(r["physical_forced_keep_byT2"] for r in rows),
              flush=True)
    dest=Path(out);dest.parent.mkdir(exist_ok=True,parents=True)
    with gzip.open(dest,"wt") as f:json.dump({"status":"PASS","schema":SCHEMA,
      "start":start,"N_independent_deals":32,
      "feature_does_not_use_physical_hidden_order":True,
      "physical_labels_forced_first_seven_same_source_hand_and_real_draws":True,
      "model_frozen_and_no_training":True,
      "source_deal_first_seven_keep_is_counterfactual_if_v43_mulliganed":True,
      "beam160_goldfish_not_cEDH_multiplayer":True,
      "not_acceptance_and_155k_unopened":True,
      "rows":rows},f,sort_keys=True)
    print("DACK_V48_FIRST_SEVEN_PHYSICAL_SHARD_PASS",start,flush=True)
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--start",type=int,required=True);p.add_argument("--out",required=True)
    z=p.parse_args();main(z.start,z.out)
