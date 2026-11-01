#!/usr/bin/env python3
"""v43 genuine bottom-only v5-stage hybrid on 256 archived original physical deals.

A: Original v5 assertive keep stage + ORIGINAL v5 bottom.
B: Exactly same original v5 keep stage + frozen v14/v27 bottom chooser.
No one uses original v5 lookahead to choose B's bottom. Zero new v5 beams,
strict 99 cards, original actual shuffled unseen92 order, same seat, original
stable dice, beam160. Exact original v5 terminal parity on EVERY game.
Historical already-used 115k is research, not fresh model acceptance.
"""
from __future__ import annotations
import argparse,gzip,glob,json,hashlib,sys,time
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import dack_paired_counterfactual_v5_stable_chance_20261031 as teacher
import dack_paired_counterfactual_v27_T2_only_DP_20261101 as v27
import dack_mulligan_teacher_features_v13_20261031 as features
from dack_simulator.validation.collect_teacher_london_v13 import finalists
ref=teacher.reference
SCHEMA="dack_v43_fixed_original_v5_stage_v14_bottom_physical_hybrid_1"

def load():
    paths=sorted(glob.glob(str(ROOT/"benchmark_results/v33b_prospective_115k_shards/v33b_115k_*.json.gz")))
    assert len(paths)==64
    a={}
    for p in paths:
        with gzip.open(p,"rt") as f:d=json.load(f)
        assert d["status"]=="PASS" and d["schema"]=="dack_v33b_prospective_115k_three_policy_strict"
        for x in d["rows"]:
            gid=x["game_id"];assert gid not in a;a[gid]=x
    assert set(a)==set(range(115000,115256))
    return a

def replay(hand,bottom,unknown,seven,seat,seed):
    assert Counter(hand)+Counter(bottom)==Counter(seven)
    assert len(unknown)==92 and len(unknown)+len(hand)+len(bottom)==99
    ref.sim.reset_caches();ref.sim.root.install("one_key_34")
    ref.sim.m.set_trial_seed(seed)
    ref.d._WIN_CACHE.clear()
    t=ref.d._win_turn_from_unknown_order(
        tuple(hand),tuple(unknown)+tuple(bottom),seat,beam=160,max_turn=3)
    assert t is None or t in (0,1,2,3)
    return int(t or 0)

def run(start,out):
    if start not in range(115000,115256,32):raise ValueError("8 fixed 32-game shards only")
    rows=load()
    teacher.audit()
    assert ref.SPEC["beam"]==160
    # v27.install loads only the v14/128 candidate-choice classifier and
    # frozen T2 value/DP model. It never changes which stage we keep here.
    v27.audit()
    assert v27.original.old.MODEL["schema"]==features.EXPORT_SCHEMA
    result=[];t0=time.perf_counter()
    for gid in range(start,start+32):
        r=rows[gid];old=r["v5"]["history"][-1]
        stage=int(old["stage"]);kn=int(old["keep_n"])
        seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
        seat,orders=ref.stage_slots(seed)
        assert seat==r["v5"]["seat"]
        seven=tuple(ref.SLOT_VARIANTS["one_key_34"][s] for s in orders[stage][:7])
        unknown=tuple(ref.SLOT_VARIANTS["one_key_34"][s] for s in orders[stage][7:])
        assert seven==tuple(old["seven"])
        assert Counter(ref.SLOT_VARIANTS["one_key_34"].values())==Counter(seven)+Counter(unknown)
        # Check original v5 exact physical result even when v27 loaded.
        before=replay(old["hand"],old["bottom"],unknown,seven,seat,seed)
        assert before==r["v5"]["turn"],("original exact playback failed",gid,before,r["v5"]["turn"])
        candidates=finalists(seven,kn,unknown)
        scored=[]
        for i,c in enumerate(candidates):
            x=features.extract(seven,c["hand"],c["bottom"],Counter(unknown),
                                seat,kn,stage,c["struct_rank"],i)
            vote=features.score_head(v27.original.old.MODEL,"choice_trees",x)
            scored.append((vote,-i,c))
        vote,minus_i,selected=max(scored,key=lambda x:(x[0],x[1]))
        hybrid=replay(selected["hand"],selected["bottom"],unknown,seven,seat,seed)
        changed=(Counter(selected["hand"])!=Counter(old["hand"]) or
                 tuple(selected["bottom"])!=tuple(old["bottom"]))
        if not changed:assert hybrid==before
        result.append({
          "game_id":gid,"seat":seat,"original_v5_keep_stage":stage,
          "v27_original_keep_stage":int(r["v27_frozen"]["history"][-1]["stage"]),
          "bottom_changed_only":changed,"v14_candidate_index":-minus_i,
          "original_v5_bottom":list(old["bottom"]),
          "frozen_v14_bottom":list(selected["bottom"]),
          "original_v5_kept_hand":list(old["hand"]),
          "frozen_v14_kept_hand":list(selected["hand"]),
          "original_v5_win_turn_replayed":before,
          "v5_stage_plus_v14_bottom_win_turn":hybrid,
          "original_v27_final_turn":int(r["v27_frozen"]["turn"]),
          "original_v33b_final_turn":int(r["v33b_regret_bottom"]["turn"]),
        })
        if (gid-start+1)%8==0:
            print("DACK_V43_FIXED_STAGE_BOTTOM_HYBRID_PROGRESS",gid,
                  "changes",sum(x["bottom_changed_only"] for x in result),
                  "elapsed_seconds",round(time.perf_counter()-t0,2),flush=True)
    assert len(result)==32
    o={
      "schema":SCHEMA,"status":"PASS","physical_ids":[start,start+31],
      "original_v5_candidate_scores_not_rerun":True,
      "exact_original_v5_terminal_win_parity_per_game":True,
      "physical_99_original_seat_and_hidden_order":True,
      "unchanged_original_v5_keep_stage":True,
      "frozen_v14_bottom_choice_at_original_v5_keep_stage":True,
      "uses_only_legal_visible_cards_for_bottom_decision":True,
      "strict_actual_gameplay_beam160":True,
      "historical_sample_NOT_unseen":True,
      "results":result}
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,"wt") as f:json.dump(o,f,sort_keys=True)
    print("DACK_V43_FIXED_V5_STAGE_V14_BOTTOM_SHARD_PASS",start,flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--start",type=int,required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args();run(a.start,a.out)
