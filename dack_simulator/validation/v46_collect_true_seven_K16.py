#!/usr/bin/env python3
"""v46 physically sample both seven-card London stages on new random deals.

Each outer game produces two distinct *potential* stages; the first is
always visited, the second is reached only if stage0 is MULL under a given
policy. Each retained hand is exactly the seven, bottom=[]; K futures use
16 independent unseen92 permutations and independent stable chance.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,random,sys,time
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from dack_simulator.validation import v45_frozen_v43_continuation as k
SCHEMA="dack_v46_first_two_sevens_new_physical_K16_v1"
START=156000
END_TRAIN=156127
END_DEV=156191
FUTURES=16
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def game(state,seat,seed):
    ref=k.ref
    ref.sim.reset_caches();ref.sim.root.install(k.DECK_KEY)
    ref.sim.m.set_trial_seed(seed)
    if hasattr(ref.d,"_WIN_CACHE"):ref.d._WIN_CACHE.clear()
    turn=ref.d._win_turn_from_unknown_order(state.hand,state.library,
                 seat,beam=160,max_turn=3)
    assert turn is None or turn in (0,1,2,3)
    return int(turn or 0)

def one(gid):
    ref=k.ref
    deck=ref.SLOT_VARIANTS[k.DECK_KEY]
    physical_seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
    seat,orders=ref.stage_slots(physical_seed)
    rows=[]
    for stage in (0,1):
        order=orders[stage]
        seven=tuple(deck[z] for z in order[:7])
        unknown=tuple(deck[z] for z in order[7:])
        assert Counter(seven)+Counter(unknown)==Counter(deck.values())
        sel=k.choose_at(stage,seat,order,deck)
        assert sel["keep_n"]==7 and sel["hand"]==list(seven) and sel["bottom"]==[]
        assert sel["candidate_index"]==0
        turns=[]
        for j in range(FUTURES):
            sh=list(unknown)
            random.Random(k.stable_seed("v46_new_K_unseen92",gid,stage,j)).shuffle(sh)
            state=ref.d.State(1,seven,tuple(sh))
            turns.append(game(state,seat,k.stable_seed("v46_new_K_chance",gid,stage,j)))
        rows.append({
           "gid":gid,"seat":seat,"stage":stage,"seven":list(seven),
           "v43_pred_Q2":float(sel["raw"]),"v43_DP":float(sel["threshold"]),
           "v43_early_KEEP":bool(sel["kept"]),
           "v43_single_candidate_index":0,
           "no_bottom_cards":True,
           "hidden_92_never_used_in_decision":True,
           "turns":turns,
        })
    assert len(rows)==2
    return rows

def run(split,start,out):
    assert split in ("train","dev")
    lo,hi=(START,END_TRAIN) if split=="train" else (END_TRAIN+1,END_DEV)
    assert lo<=start<=hi and (start-lo)%16==0 and start+15<=hi
    assert k.selftest()
    t=time.perf_counter();outrows=[]
    for gid in range(start,start+16):
        outrows+=one(gid)
        print("DACK_V46_NEW_TWO_SEVEN_PHYSICAL",split,gid,"T2",
             [sum(0<v<=2 for v in q["turns"]) for q in outrows[-2:]],
             "elapsed_seconds",round(time.perf_counter()-t,2),flush=True)
    m=ROOT/"models/dack_v27_expanded_T2_only_value_EXPERIMENTAL.json"
    d={
       "schema":SCHEMA,"status":"PASS","split":split,
       "range":[start,start+15],"independent_outer_physical_deals":16,
       "two_stages_per_deal":[0,1],"K_futures_per_state":FUTURES,
       "strict_99_real_cards_actual_beam160":True,
       "frozen_v43_24_deal_continuation_parity_passed":True,
       "no_bottoms_for_either_seven_card_stage":True,
       "stage1_is_hypothetical_if_stage0_kept":True,
       "no_v5_beam_or_teacher_labels":True,
       "physical_shuffles_and_chance_independent_of_model_scores":True,
       "source_v27_model_sha256":sha(m),
       "training_or_dev_source_not_full_game_result":True,
       "rows":outrows,
    }
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,"wt") as f:json.dump(d,f,sort_keys=True)
    print("DACK_V46_REAL_TWO_SEVEN_PHYSICAL_SHARD_PASS",split,start,flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--split",required=True,choices=("train","dev"))
    p.add_argument("--start",type=int,required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args();run(a.split,a.start,a.out)
