#!/usr/bin/env python3
"""v39 untouched 133k prospective true physical full-game matched N1024.

Only launch if independent 131k conditional physical T2 gain passed
ALL frozen gates. For each 133k physical game original 99-slot
London eight-seven orders and seat matched, legal v33b bottom.
If final hand AND exact ordered library match, actual seeded
stable-beam160 gameplay result is mathematically identical and
simulated once only (exact-path collapse; no probability proxy).
If paths differ, run two independent exact physical beam160 games
under the SAME initial seat and stable seed. Track speed and
T1/T2/T3 actual full-policy outcomes.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,sys,time
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from dack_simulator.validation import v34_frozen_v33b_continuation as kernel
import dack_paired_counterfactual_v39_t2_risk_regret_20261101 as policy

LO=133000;HI=134023;SHARD=16
PROTO="DACK_V39_NEW133K_FULL_PHYSICAL_PROSPECTIVE_TWO_POLICIES_V1"
RESULT=ROOT/"benchmark_results/v39_131k_independent_action_regret.json"

def simulate(ref,seat,seed,state):
    ref.sim.reset_caches();ref.sim.root.install(kernel.DECK_KEY)
    ref.sim.m.set_trial_seed(seed)
    ref.d._WIN_CACHE.clear()
    t=time.perf_counter()
    turn=int(ref.d._win_turn_from_unknown_order(
             state.hand,state.library,seat,beam=160,max_turn=3) or 0)
    elapsed=time.perf_counter()-t
    assert turn in (0,1,2,3)
    return turn,elapsed

def run(start,out):
    if not LO<=start<=HI or (start-LO)%SHARD or start+SHARD-1>HI:
        raise ValueError("reserved 133k N1024 16-group prospective shard")
    policy.audit()
    gate=json.loads(RESULT.read_text())
    assert gate["schema"]=="dack_v39_131k_N1024_real_action_regret_two_source_v1"
    assert gate["status"]=="PASS" and gate["predeclared_gate_passed"]
    assert gate["prospective_133k"]=="ALLOWED"
    assert gate["model_sha256"]==policy.MODEL_SHA
    ref=kernel.ref;deck=ref.SLOT_VARIANTS[kernel.DECK_KEY]
    rows=[];starttime=time.monotonic()
    for gid in range(start,start+SHARD):
        seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
        seat,orders=ref.stage_slots(seed)
        begin=time.perf_counter()
        state0,h0=kernel.v33b.choose_keep(deck,seat,orders)
        dt0=time.perf_counter()-begin
        begin=time.perf_counter()
        state1,h1=policy.choose_keep(deck,seat,orders)
        dt1=time.perf_counter()-begin
        assert h0[-1]["kept"] and h1[-1]["kept"]
        assert all(Counter(z["seven"])==Counter(z["hand"])+Counter(z["bottom"]) for z in h1)
        assert all(z["kept"]==z["v39_original_v27_keep"] for z in h1 if z["stage"]>=3)
        assert len(state0.library)==92+(7-h0[-1]["keep_n"])
        assert len(state1.library)==92+(7-h1[-1]["keep_n"])
        equal=state0.hand==state1.hand and state0.library==state1.library
        if equal:
            assert len(h0)==len(h1)
            assert all(z["kept"]==z["v39_original_v27_keep"] for z in h1)
        t0,g0=simulate(ref,seat,seed,state0)
        if equal:
            t1=t0;g1=g0
        else:
            t1,g1=simulate(ref,seat,seed,state1)
        row={
           "game_id":gid,"seat":seat,
           "baseline_v33b":{"win_turn":t0,"keep_n":h0[-1]["keep_n"],
                           "actual_final_stage":h0[-1]["stage"],
                           "chooser_seconds":dt0,"gameplay_seconds":g0},
           "new_v39":{"win_turn":t1,"keep_n":h1[-1]["keep_n"],
                       "actual_final_stage":h1[-1]["stage"],
                       "chooser_seconds":dt1,"gameplay_seconds":g1},
           "same_physical_final_hand_and_ordered_library":equal,
           "strict_stable_physical_seed":seed,
           "new_policy_changed_actual_reached_stage":not equal,
        }
        rows.append(row)
        print("DACK_V39_NEW133K_PAIRED_PHYSICAL_GAME",gid,t0,t1,
              "changed_final_state",not equal,
              "elapsed",round(time.monotonic()-starttime,2),flush=True)
    assert len(rows)==SHARD
    doc={
       "schema":"dack_v39_133k_N1024_matched_v33b_v39_real_full_game_v1",
       "status":"PASS","policy_approved":False,
       "physical_group_ids":[start,start+SHARD-1],
       "n_outer_independent_groups":SHARD,
       "same_original_99_card_deal_and_seat":True,
       "same_state_same_seed_one_exact_gameplay_replay_allowed":True,
       "actual_rules_stable_dice_gameplay_beam160":True,
       "no_new_training_from_131k_or_133k":True,
       "validated_131k_gate_file_sha256":hashlib.sha256(RESULT.read_bytes()).hexdigest(),
       "source_frozen_direct_regret_model_sha256":policy.MODEL_SHA,
       "original_v33b_bottom_unchanged":True,
       "rows":rows}
    path=Path(out);path.parent.mkdir(exist_ok=True,parents=True)
    with gzip.open(path,"wt") as f:json.dump(doc,f,sort_keys=True)
    print("DACK_V39_133K_PROSPECTIVE_SHARD_PASS",start,SHARD,flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--start",type=int,required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args();run(a.start,a.out)
