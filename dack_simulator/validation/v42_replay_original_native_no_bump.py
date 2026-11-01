#!/usr/bin/env python3
"""Counterfactual physically replay original-v5 WITHOUT assertive +KEEP bumps.

Do NOT re-evaluate any mulligan hand, teacher rollouts, candidate bottom, or
later policy. The native (no extra bump) policy must stop no later than the
original assertive v5, so its exact hand and bottom are in the archived
115k original-v5 natural stage history. On each already observed stage,
use the original v5 native frozen cutoff, NOT v27 C or a learned value.

The physical win is replayed from the unexposed original stage's shuffled
unknown92 order + archived bottom, with exact same 99 slots, seat, stable
chance and beam160 gameplay. First replay original assertive v5 endgame
and require exact parity with the original archived actual win turn.
"""
from __future__ import annotations
import argparse,gzip,glob,hashlib,json,sys,time
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import dack_paired_counterfactual_v5_stable_chance_20261031 as teacher
ref=teacher.reference
SCHEMA="dack_v42_native_without_assertive_bump_real_physical_counterfactual_1"
PILOT_N=4
SHARD_N=32
def source():
    files=sorted(glob.glob(str(ROOT/"benchmark_results/v33b_prospective_115k_shards/v33b_115k_*.json.gz")))
    assert len(files)==64
    rr=[]
    for p in files:
        with gzip.open(p,"rt") as f:z=json.load(f)
        assert z["schema"]=="dack_v33b_prospective_115k_three_policy_strict" and z["status"]=="PASS"
        assert z["strict_gameplay_beam"]==160
        rr.extend(z["rows"])
    rr.sort(key=lambda x:x["game_id"])
    assert [r["game_id"] for r in rr]==list(range(115000,115256))
    return rr

def native_stage(history):
    for r in history:
        kn=int(r["keep_n"])
        C=0. if kn==1 else float(ref.batch.FROZEN_CONTINUATION[kn-1])
        if kn==1 or float(r["raw"])>=C:
            return int(r["stage"])
    raise AssertionError("native never found KEEP from original v5 history")

def gameplay(row,stage,seat,orders,seed,deck):
    rr=row["v5"]["history"]
    item=rr[stage]
    assert item["stage"]==stage and item["keep_n"]==ref.sim.STAGES[stage]
    order=orders[stage]
    seven=[deck[x] for x in order[:7]]
    assert item["seven_slots"]==list(order[:7]) and item["seven"]==seven
    unknown=tuple(deck[x] for x in order[7:])
    hand=tuple(item["hand"])
    bottom=tuple(item["bottom"])
    assert Counter(hand)+Counter(bottom)==Counter(seven)
    assert len(unknown)==92 and len(hand)==item["keep_n"]
    ref.sim.reset_caches()
    ref.sim.root.install("one_key_34")
    ref.sim.m.set_trial_seed(seed)
    ref.d._WIN_CACHE.clear()
    t=ref.d._win_turn_from_unknown_order(
        hand,unknown+bottom,seat,beam=160,max_turn=3)
    assert t is None or t in (1,2,3)
    return int(t or 0)

def run(start,out,games=4):
    if not (games==PILOT_N and start==115000 or
            games==SHARD_N and start in range(115000,115256,32)):
        raise ValueError("only pilot (115000,4) or eight aligned 32-game shards")
    # Install ONLY original rules and stable dice, not any successor model.
    teacher.install()
    assert tuple(ref.sim.STAGES)==(7,7,6,5,4,3,2,1)
    assert ref.batch.CONFIG["lambda"]==0.5
    assert ref.SPEC["beam"]==160
    src=source()
    deck=ref.SLOT_VARIANTS["one_key_34"]
    outrows=[];t0=time.monotonic()
    for r in src[start-115000:start-115000+games]:
        gid=int(r["game_id"])
        seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
        seat,orders=ref.stage_slots(seed)
        assert seat==r["v5"]["seat"]==r["v27_frozen"]["seat"]
        hist=r["v5"]["history"]
        s0=int(hist[-1]["stage"])
        sn=native_stage(hist)
        assert 0<=sn<=s0<=7
        original=gameplay(r,s0,seat,orders,seed,deck)
        expected=int(r["v5"]["turn"])
        if original!=expected:
            raise AssertionError((
               "ORIGINAL v5 PHY GAME REPLAY PARITY FAILED; NO VALID NATIVE CONTRAST",
               gid,original,expected,seat,s0))
        native=(original if sn==s0 else
                gameplay(r,sn,seat,orders,seed,deck))
        outrows.append({
          "game_id":gid,"seat":seat,
          "original_v5_assertive_keep_stage":s0,
          "native_no_bump_keep_stage":sn,
          "early_stop_due_to_bump_removal":sn<s0,
          "original_v5_turn_replayed":original,
          "original_v5_turn_archived":expected,
          "native_no_bump_real_turn":native,
          "v27_frozen_original_turn":int(r["v27_frozen"]["turn"]),
          "v33b_frozen_original_turn":int(r["v33b_regret_bottom"]["turn"]),
          "native_retained_hand":list(hist[sn]["hand"]),
          "native_bottom":list(hist[sn]["bottom"]),
          "assertive_retained_hand":list(hist[s0]["hand"]),
          "assertive_bottom":list(hist[s0]["bottom"]),
        })
        print("DACK_V42_TRUE_NATIVE_NO_BUMP_GAME",gid,
            "v5",original,"native",native,"v27",r["v27_frozen"]["turn"],
            "v5_native_different_stage",sn<s0,
            "seconds",round(time.monotonic()-t0,2),flush=True)
    assert len(outrows)==games
    result={
      "schema":SCHEMA,"status":"PASS",
      "physical_game_ids":[start,start+games-1],
      "source":"already fixed original v5 115k physical natural London trace",
      "strict_99_real_slots":True,
      "strict_beam160_original_v5_rules_and_stateless_chance":True,
      "all_original_v5_physical_game_win_turns_replayed_exactly":True,
      "original_v5_lookahead_calls":0,
      "native_no_bump_uses_only_prior_visited_v5_stage_scores":True,
      "native_no_bump_uses_unchanged_v5_candidate_bottom":True,
      "v5_alternative_rejected_hand_not_inferred_outside_trace":True,
      "not_new_independent_model_validation":True,
      "not_multiplayer_cedh_winrate":True,
      "rows":outrows
    }
    path=Path(out);path.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(path,"wt") as f:json.dump(result,f,sort_keys=True)
    print("DACK_V42_V5_NATIVE_NO_BUMP_PHYSICAL_PARITY_SHARD_PASS",start,flush=True)

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--start",type=int,required=True)
    parser.add_argument("--out",required=True)
    parser.add_argument("--games",type=int,default=4)
    args=parser.parse_args()
    run(args.start,args.out,args.games)
