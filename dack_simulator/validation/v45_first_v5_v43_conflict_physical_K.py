#!/usr/bin/env python3
"""v45 fresh physical Qkeep for first v5/v43 real London disagreements.

Select EXACTLY 44 original physically observed 151k N128 first-stage v5-v43
disagreements from the already-audited v45 read-only source. For EVERY one,
force KEEP of the ORIGINAL v43-selected legal retained hand/bottom at that
first disagreement stage and sample 32 new unseen92 + original stable chance
physical goldfish futures with strict beam160.

No original v5 lookahead in these forced keep evaluations; original teacher
action is a *historical reference label*, never used to choose K bottom.
No future card order leaked in KEEP score. These are selected disagreement
hands, not an unbiased sample of all physical opening sevens. Separate
future-MULL C seat/stage lotteries under unchanged v43 are collected by
v45_real_v43_continuation_C; any one-step causal interpretation requires
the SAME frozen bottom and later continuation on both arms.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,random,sys,time
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import dack_paired_counterfactual_v43_v27_max_Q2_20261101 as v43
from dack_simulator.validation.collect_teacher_london_v13 import finalists
ref=v43.ref
SCHEMA="dack_v45_original_v5_v43_151k_first_conflict_true_forced_Qkeep_N44"
PROTO="DACK_V45_V5_V43_FRESH_FIRST_CONFLICT_KEEP_20261101"
K_TRIALS=32
def seed(*args):
    return int.from_bytes(hashlib.sha256(json.dumps((PROTO,*args),
       separators=(",",":")).encode()).digest()[:8],"big")
def read_source():
    p=ROOT/"benchmark_results/v45_v5_v43_remaining_T2_gap_same151k_N128.json"
    r=json.loads(p.read_text())
    assert r["schema"]=="dack_v45_original_v5_vs_coupled_v43_matched_151k_N128_residual_audit"
    assert r["status"]=="PASS" and r["N_matched_games"]==128
    selected=sorted((z for z in r["all_records"] if z["comparison_stratum"]=="different_keep_stage"),
                     key=lambda z:z["gid"])
    assert len(selected)==44
    assert sum(z["stage_direction"]=="v43_earlier" for z in selected)==28
    assert sum(z["stage_direction"]=="v5_earlier" for z in selected)==16
    return selected
def load_v43_trace(gid):
    shard=(gid-151000)//32
    start=151000+shard*32
    path=ROOT/f"benchmark_results/v43_fresh_151k_maxQ2_shards/v43_151k_{start}.json.gz"
    with gzip.open(path,"rt") as gz:doc=json.load(gz)
    assert doc["status"]=="PASS" and doc["schema"]=="dack_v43_fresh_151k_v27_vs_maxQ2_N256_paired_shard"
    matching=[x for x in doc["rows"] if x["gid"]==gid]
    assert len(matching)==1
    return matching[0]["maxQ2"]
def one(r):
    gid=int(r["gid"]);stage=int(r["first_conflict_stage"])
    seat=int(r["seat"])
    old=load_v43_trace(gid)
    assert seat==old["seat"]
    assert stage<len(old["history"]) and stage in (0,1,2,3,4)
    item=old["history"][stage]
    kn=int(ref.sim.STAGES[stage])
    assert item["stage"]==stage and item["keep_n"]==kn
    assert bool(item["kept"])==bool(r["v43_keep_on_first_comparable_stage"])
    sd=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
    real_seat,orders=ref.stage_slots(sd)
    assert real_seat==seat
    deck=ref.SLOT_VARIANTS["one_key_34"]
    order=orders[stage]
    seven=tuple(deck[s] for s in order[:7])
    unknown=tuple(deck[s] for s in order[7:])
    hand=tuple(item["hand"]);bottom=tuple(item["bottom"])
    assert tuple(item["seven"])==seven
    assert Counter(seven)==Counter(hand)+Counter(bottom)
    assert len(unknown)==92 and Counter(deck.values())==Counter(seven)+Counter(unknown)
    # Validate exact v43 selected bottom belongs to original v5 legal top12
    # (same legal candidate family, even when original v5 MULLS this hand).
    options=finalists(seven,kn,unknown)
    assert any(c["hand"]==list(hand) and c["bottom"]==list(bottom) for c in options)
    trials=[]
    for j in range(K_TRIALS):
        sh=list(unknown)
        random.Random(seed("unseen92",gid,stage,j)).shuffle(sh)
        ref.sim.reset_caches();ref.sim.root.install("one_key_34")
        ref.sim.m.set_trial_seed(seed("gameplay_chance",gid,stage,j))
        ref.d._WIN_CACHE.clear()
        val=ref.d._win_turn_from_unknown_order(
            hand,tuple(sh)+bottom,seat,beam=160,max_turn=3)
        assert val is None or val in (0,1,2,3)
        trials.append(int(val or 0))
    return {
        "gid":gid,"stage":stage,"seat":seat,
        "v5_earlier":r["stage_direction"]=="v5_earlier",
        "v43_earlier":r["stage_direction"]=="v43_earlier",
        "original_v5_kept_this_stage":r["v5_keep_on_first_comparable_stage"],
        "original_v43_kept_this_stage":r["v43_keep_on_first_comparable_stage"],
        "visible_seven":list(seven),"exact_v43_hand":list(hand),
        "exact_v43_bottom":list(bottom),
        "true_physical_KEEP_turns":trials,
        "PbyT2_KEEP_estimate":sum(0<t<=2 for t in trials)/K_TRIALS,
        "PbyT3_KEEP_estimate":sum(0<t<=3 for t in trials)/K_TRIALS,
    }
def run(shard,out):
    if shard not in (0,1,2,3):raise ValueError("four fixed shards only")
    audit=v43.audit()
    assert audit["status"]=="PASS"
    assert ref.SPEC["beam"]==160 and len(ref.SLOTS)==99
    selected=read_source()[shard*11:(shard+1)*11]
    assert len(selected)==11
    rows=[];t0=time.perf_counter()
    for r in selected:
        rows.append(one(r))
        print("DACK_V45_FIRST_CONFLICT_TRUE_KEEP",r["gid"],"stage",r["first_conflict_stage"],
           "v5_earlier",r["stage_direction"]=="v5_earlier",
           "actual_K2",rows[-1]["PbyT2_KEEP_estimate"],
           "elapsed",round(time.perf_counter()-t0,2),flush=True)
    doc={
      "schema":SCHEMA,"status":"PASS","shard":shard,
      "N_real_original_151k_conflict_groups":len(rows),
      "K_real_unknown92_future_rollouts_per_group":K_TRIALS,
      "original_v43_candidate_hand_and_bottom_replayed_exactly":True,
      "strict_original_99_slot_beam160":True,
      "new_hidden92_resampled_without_policy_future_leak":True,
      "fixed_original_v5_v43_first_disagreement_selection_before_new_QKEEP":True,
      "old_151k_selection_is_retrospective_not_population_random":True,
      "physical_KEEP_alone_not_full_game_winrate":True,
      "no_original_v5_lookahead_and_no_new_model_fit":True,
      "rows":rows
    }
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,"wt") as gz:json.dump(doc,gz,sort_keys=True)
    print("DACK_V45_FIRST_CONFLICT_TRUE_KEEP_SHARD_PASS",shard,flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--shard",type=int,required=True);p.add_argument("--out",required=True)
    a=p.parse_args();run(a.shard,a.out)
