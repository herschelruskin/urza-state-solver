#!/usr/bin/env python3
"""v45 physical continuation C2/C3 under FROZEN full v43 MAX-Q2 London policy.

For each seat and CURRENT rejected stage (0..4), return all 99 physical cards,
reshuffle a NEW independent stage-specific deck for later London stages,
follow the *unchanged* v43 coupled candidate/KEEP logic from stage+1, and
execute strict actual beam160 goldfish gameplay on the retained hand.

NO original v5, NO trial-specific hidden futures in KEEP features, NO v45
model training. This calibrates the old-v27 learned DP CONTINUATION against
physical values under the *new v43 policy*; all values are conditional on
seat and stage, NOT on a particular rejected visible seven.

First prove the reimplementation matches complete v43.choose_keep from
stage0 on physical matched 99-slot sources, including exact ordered bottoms.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,random,sys,time
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import dack_paired_counterfactual_v43_v27_max_Q2_20261101 as v43
import dack_paired_counterfactual_v27_T2_only_DP_20261101 as v27
import dack_mulligan_teacher_features_v13_20261031 as feat
from dack_simulator.validation.collect_teacher_london_v13 import finalists
ref=v43.ref
PROTO="DACK_V45_V43_STRICT_FULL99_PHYSICAL_CONTINUATION_20261101"
SCHEMA="dack_v45_157k_real_v43_conditional_next_london_continuation_v1"
TRIALS=96
EARLY_STAGES=(0,1,2,3,4)
def seed(*args):
    return int.from_bytes(hashlib.sha256(json.dumps((PROTO,*args),
        separators=(",",":")).encode()).digest()[:8],"big")
def stage_order(seat,source_stage,trial,real_stage):
    assert source_stage<real_stage<8
    slots=list(ref.SLOTS)
    random.Random(seed("full99_resuffle",seat,source_stage,trial,real_stage)).shuffle(slots)
    assert len(slots)==99 and set(slots)==set(ref.SLOTS)
    return tuple(slots)
def later_policy(start_stage,seat,orders):
    assert 0<=start_stage<=7
    assert len(orders)==8-start_stage
    deck=ref.SLOT_VARIANTS["one_key_34"]
    threshold=v27.original.DP["seat_continuations"][str(seat)]["thresholds_by_london_stage"]
    history=[]
    for stage,order in zip(range(start_stage,8),orders):
        kn=int(ref.sim.STAGES[stage])
        seven=tuple(deck[s] for s in order[:7])
        unknown=tuple(deck[s] for s in order[7:])
        assert len(seven)==7 and len(unknown)==92
        assert Counter(seven)+Counter(unknown)==Counter(deck.values())
        options=finalists(seven,kn,unknown)
        scored=[]
        for i,c in enumerate(options):
            x=feat.extract(seven,c["hand"],c["bottom"],Counter(unknown),
                seat,kn,stage,c["struct_rank"],i)
            q=float(v27.original.estimator.predict(v27.original.MODEL,x))
            scored.append((q,-i,c))
        q,negative,selected=max(scored,key=lambda x:(x[0],x[1]))
        cutoff=float(threshold[stage])
        keep=bool(kn==1 or q>=cutoff)
        hand=tuple(selected["hand"]);bottom=tuple(selected["bottom"])
        assert Counter(hand)+Counter(bottom)==Counter(seven)
        history.append({"stage":stage,"keep_n":kn,"kept":keep,
                        "hand":list(hand),"bottom":list(bottom),
                        "seven":list(seven),
                        "Q2":q,"continuation":cutoff,
                        "selected_candidate_index":-negative})
        if keep:
            return ref.d.State(1,hand,unknown+bottom),history
    raise AssertionError("last London stage must KEEP")
def selftest():
    info=v43.audit()
    assert info["status"]=="PASS"
    assert ref.SPEC["beam"]==160 and len(ref.SLOTS)==99
    for gid in range(157900,157912):
        sd=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
        seat,orders=ref.stage_slots(sd)
        original,old=ref.choose_keep(ref.SLOT_VARIANTS["one_key_34"],seat,orders)
        reconstructed,hist=later_policy(0,seat,orders)
        assert original.hand==reconstructed.hand
        assert original.library==reconstructed.library
        assert len(old)==len(hist)
        for a,b in zip(old,hist):
            assert a["stage"]==b["stage"] and a["kept"]==b["kept"]
            assert a["hand"]==b["hand"] and a["bottom"]==b["bottom"]
    print("DACK_V45_V43_LONDON_FROZEN_MANUAL_CONTINUATION_PARITY_PASS",flush=True)
def run(seat,source_stage,out):
    if seat not in range(4) or source_stage not in EARLY_STAGES:
        raise ValueError("seat must be 0-3 and source stage must be 0-4")
    selftest()
    old_threshold=v27.original.DP["seat_continuations"][str(seat)]["thresholds_by_london_stage"][source_stage]
    results=[];t0=time.perf_counter()
    for trial in range(TRIALS):
        orders=[stage_order(seat,source_stage,trial,s)
                for s in range(source_stage+1,8)]
        ref.sim.reset_caches();ref.sim.root.install("one_key_34")
        state,hist=later_policy(source_stage+1,seat,orders)
        assert hist[0]["stage"]==source_stage+1 and hist[-1]["kept"]
        ref.sim.reset_caches();ref.sim.root.install("one_key_34")
        ref.sim.m.set_trial_seed(seed("strict_real_play_chance",seat,source_stage,trial))
        ref.d._WIN_CACHE.clear()
        win=ref.d._win_turn_from_unknown_order(
            state.hand,state.library,seat,beam=160,max_turn=3)
        assert win is None or win in (0,1,2,3)
        results.append({"trial":trial,"win_turn":int(win or 0),
             "future_keep_stage":hist[-1]["stage"],
             "future_kept_bottom":hist[-1]["bottom"]})
        if (trial+1)%24==0:
            print("DACK_V45_TRUE_V43_C_PROGRESS",seat,source_stage,trial+1,
                "T2",sum(0<x["win_turn"]<=2 for x in results),
                "seconds",round(time.perf_counter()-t0,1),flush=True)
    turns=[x["win_turn"] for x in results]
    data={
        "schema":SCHEMA,"status":"PASS","seat":seat,
        "rejected_stage":source_stage,"next_stage":source_stage+1,
        "physical_C_futures":TRIALS,"future_full_99_card_decks_restored":True,
        "new_independent_full99_shuffle_per_future_London_stage":True,
        "original_v43_candidate_choice_and_KEEP_reproduced_exactly":True,
        "unchanged_future_policy":"v43 MAX frozen v27 Q2 across legal tops",
        "strict_physical_beam160":True,
        "original_v5_runtime_beams":0,
        "no_current_seven_in_future_C_lottery":True,
        "all_Boonweaver_deck_cards_present_in_full99":True,
        "original_v27_learned_DP_threshold":float(old_threshold),
        "physical_future_PbyT1":sum(t==1 for t in turns)/TRIALS,
        "physical_future_PbyT2":sum(0<t<=2 for t in turns)/TRIALS,
        "physical_future_PbyT3":sum(0<t<=3 for t in turns)/TRIALS,
        "mean_later_final_stage":sum(x["future_keep_stage"] for x in results)/TRIALS,
        "no_fitted_calibration_or_policy_replacement":True,
        "not_full_game_winrate_and_not_pristine_acceptance":True,
        "results":results,
    }
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,"wt") as gz:json.dump(data,gz,sort_keys=True)
    print("DACK_V45_V43_REAL_PHYSICAL_CONTINUATION_C_PASS",
          seat,source_stage,data["physical_future_PbyT2"],
          data["original_v27_learned_DP_threshold"],flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--seat",type=int,required=True)
    p.add_argument("--stage",type=int,required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args();run(a.seat,a.stage,a.out)
