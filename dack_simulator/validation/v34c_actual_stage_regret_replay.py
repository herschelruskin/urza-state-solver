#!/usr/bin/env python3
"""v34c 115k actual v5-v27 earliest KEEP/MULL disagreement: forced KEEP labels.

Selection criterion = DIFFERENT ACTUAL FINAL LONDON STAGE ONLY, NEVER
the original 115k win turn. Current stage seven/seat matched physically.
KEEP uses immutable v33b bottom, 16 calibration + 16 replication fresh
unseen-92 shuffled futures. MULL values are already physically sampled
from all 99, independently, in v34 exact downstream Qmull archive.
This file performs ZERO mull or v5 beam calls and NO model fitting.
"""
from __future__ import annotations
import argparse
from collections import Counter
import gzip,glob,hashlib,json,random,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from dack_simulator.validation import v34_frozen_v33b_continuation as kernel

PROTO="DACK_V34C_ACTUAL_KEEP_DISAGREEMENT_FRESH_FUTURES_1"
SPLITS=("calibration","replication")
SAMPLES=16;SHARDS=8

def candidates():
    paths=sorted(glob.glob(str(ROOT/"benchmark_results/v33b_prospective_115k_shards/v33b_115k_*.json.gz")))
    assert len(paths)==64,("require all archived original 115k physical shards",len(paths))
    rows=[]
    for p in paths:
        with gzip.open(p,"rt") as f:d=json.load(f)
        assert d["schema"]=="dack_v33b_prospective_115k_three_policy_strict"
        assert d["status"]=="PASS" and d["strict_gameplay_beam"]==160
        assert d["v27_v33b_identical_london_stages_and_keep_actions"]
        rows+=d["rows"]
    rows.sort(key=lambda r:r["game_id"])
    assert [r["game_id"] for r in rows]==list(range(115000,115256))
    selected=[]
    for row in rows:
        v5=row["v5"]["history"]
        v27=row["v27_frozen"]["history"]
        assert v5[-1]["kept"] and v27[-1]["kept"]
        s5=int(v5[-1]["stage"]);s27=int(v27[-1]["stage"])
        if s5==s27:continue
        s=min(s5,s27)
        assert s<7
        a=v5[s];b=v27[s]
        assert int(a["stage"])==int(b["stage"])==s
        assert tuple(a["seven_slots"])==tuple(b["seven_slots"])
        assert tuple(a["seven"])==tuple(b["seven"])
        assert bool(a["kept"])!=bool(b["kept"])
        assert bool(a["kept"])==(s5<s27)
        assert bool(b["kept"])==(s27<s5)
        selected.append({"game_id":row["game_id"],"seat":row["v5"]["seat"],
           "stage":s,"v5_kept_stage":s5,"v27_kept_stage":s27,
           "v5_first_keeps":s5<s27})
    assert len(selected)==100,("v34b 115k original different-stage census changed",len(selected))
    return selected

def one(row):
    ref=kernel.ref;deck=ref.SLOT_VARIANTS[kernel.DECK_KEY]
    gid=row["game_id"];s=row["stage"];seat=row["seat"]
    phys_seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
    other_seat,orders=ref.stage_slots(phys_seed)
    assert other_seat==seat
    seven=tuple(deck[x] for x in orders[s][:7])
    unknown=tuple(deck[x] for x in orders[s][7:])
    assert Counter(seven)+Counter(unknown)==Counter(deck.values())
    sel=kernel.current(seven,unknown,seat,s)
    assert sel["old_v27_keep"]==(not row["v5_first_keeps"])
    hand=tuple(sel["hand"]);bottom=tuple(sel["bottom"])
    assert Counter(hand)+Counter(bottom)==Counter(seven)
    splits={}
    for split in SPLITS:
        turns=[]
        for future in range(SAMPLES):
            shuffled=list(unknown)
            random.Random(kernel.stable_seed("v34c_new_keep_unseen92",
                 split,gid,s,future)).shuffle(shuffled)
            state=kernel.state_from(seven,tuple(shuffled),sel)
            ref.sim.reset_caches();ref.sim.root.install(kernel.DECK_KEY)
            ref.sim.m.set_trial_seed(kernel.stable_seed(
                "v34c_gameplay_chance",split,gid,s,future))
            t=int(ref.d._win_turn_from_unknown_order(
                state.hand,state.library,seat,beam=160,max_turn=3) or 0)
            assert t in (0,1,2,3)
            turns.append(t)
        splits[split]=turns
    return {**row,
      "seven":list(seven),"v33b_hand":list(hand),"v33b_bottom":list(bottom),
      "v33b_overrode_v14_bottom":sel["v33b_overrode_bottom"],
      "v27_absolute_Qkeep_prediction":sel["old_v27_Qkeep"],
      "v27_original_DP_threshold":sel["old_v27_DP"],
      "original_115k_result_not_used_in_selection_or_label":True,
      "actual_strict_beam160":True,
      "fresh_keep_futures_by_split":splits}

def run(shard,out):
    if not 0<=shard<SHARDS:raise ValueError("8 shards 0..7")
    kernel.initialize()
    allrows=candidates()
    chosen=[r for i,r in enumerate(allrows) if i%SHARDS==shard]
    assert chosen
    t0=time.monotonic()
    rows=[]
    for r in chosen:
        rows.append(one(r))
        print("DACK_V34C_ACTUAL_DISAGREEMENT",r["game_id"],r["stage"],
          "v5_keeps_first",r["v5_first_keeps"],
          "seconds",round(time.monotonic()-t0,2),flush=True)
    report={
       "schema":"dack_v34c_115k_earliest_actual_stage_disagreement_forced_keep",
       "status":"PASS","shard":shard,"total_eligible_groups":len(allrows),
       "source_115k_game_ids":[115000,115255],
       "selected_only_on_actual_policy_stage_disagreement":True,
       "original_115k_win_turn_never_read_for_selection":True,
       "actual_beam160":True,"future_splits":SPLITS,
       "futures_per_split":SAMPLES,
       "Qmull_reused_exact_v34_independent_full99_archive":True,
       "Qmull_rollouts_here":0,
       "no_frozen_policy_engine_or_model_changes":True,
       "frozen_v33b_model_sha256":kernel.v33b.MODEL_SHA,
       "policy_approved":False,"rows":rows}
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,"wt") as f:json.dump(report,f,sort_keys=True)
    print("DACK_V34C_FORCED_KEEP_SHARD_PASS",shard,len(rows),
          round(time.monotonic()-t0,2),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--shard",type=int,required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args();run(a.shard,a.out)
