#!/usr/bin/env python3
"""v39 untouched 131k selected by frozen observable-action disagreement ONLY.

A policy-action difference at the same early stage is D=(new-old)
×(Qkeep-C). If new==old it is algebraically EXACT zero for EVERY
physical unknown future, hence no need to simulate that stage.
Preserve ALL 3072 original physical states in pooled denominator.
Physical KEEP uses the EXACT previously frozen v33b bottom;
32 fresh independent unknown92 shuffles and actual beam160.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,random,sys,time
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from dack_simulator.validation import v34_frozen_v33b_continuation as kernel
import dack_paired_counterfactual_v39_t2_risk_regret_20261101 as policy
import dack_mulligan_v37_features as feat
import dack_mulligan_v39_t2_risk_regret as util

CENSUS=ROOT/"datasets/v39_131k_frozen_outcome_blind_census.json"
SCHEMA="dack_v39_131k_changed_only_true_physical_KEEP_v1"
PROTO="DACK_V39_NEW129K_UNSEEN32_KEEP_PHYSICAL"
N_SHARDS=16;FUTURES=32

def seed(*p):
    return int.from_bytes(hashlib.sha256(json.dumps(
       (PROTO,*p),separators=(",",":")).encode()).digest()[:8],"big")

def run(shard,out):
    if shard not in range(N_SHARDS):raise ValueError("16 shards")
    policy.audit()
    raw=CENSUS.read_bytes();d=json.loads(raw)
    assert d["schema"]=="dack_v39_131k_new_random_1024_outcome_blind_census_v1"
    assert d["status"]=="PASS" and d["random_stage_state_denominator"]==3072
    assert d["no_full_game_or_counterfactual_rollouts_at_selection"]
    assert d["frozen_v37_direct_regret_model_sha256"]==policy.MODEL_SHA
    assert d["frozen_v33b_bottom_sha256"]==kernel.v33b.MODEL_SHA
    assert d["actual_action_changes"]>=24 and d["changed_actual_London_path_games"]>=12
    selected=[x for x in d["all_early_stage_decisions"]
              if x["changed"] and (x["game_id"]-131000)%N_SHARDS==shard]
    ref=kernel.ref;deck=ref.SLOT_VARIANTS[kernel.DECK_KEY]
    result=[];start=time.monotonic()
    for x in selected:
        gid=x["game_id"];stage=x["stage"];seat=x["seat"]
        ss,orders=ref.stage_slots(int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE)
        assert ss==seat
        order=orders[stage]
        seven=tuple(deck[z] for z in order[:7])
        unseen=tuple(deck[z] for z in order[7:])
        assert Counter(seven)+Counter(unseen)==Counter(deck.values())
        sel=kernel.current(seven,unseen,seat,stage)
        assert seven==tuple(x["visible_seven"])
        assert Counter(sel["hand"])==Counter(x["v33b_kept_hand"])
        assert Counter(sel["bottom"])==Counter(x["v33b_bottom"])
        xx=feat.extract(seven,unseen,seat,stage,sel)
        new,diag=util.choose(policy.MODEL,xx,stage,sel["old_v27_keep"])
        assert new==x["new_keep"] and new!=sel["old_v27_keep"]
        outcomes=[]
        for j in range(FUTURES):
            cards=list(unseen)
            random.Random(seed("physical_hidden92",gid,stage,j)).shuffle(cards)
            state=kernel.state_from(seven,tuple(cards),sel)
            ref.sim.reset_caches();ref.sim.root.install(kernel.DECK_KEY)
            ref.sim.m.set_trial_seed(seed("stable_effects",gid,stage,j))
            t=int(ref.d._win_turn_from_unknown_order(
                state.hand,state.library,seat,beam=160,max_turn=3) or 0)
            assert t in (0,1,2,3)
            outcomes.append(t)
        result.append({
           "game_id":gid,"seat":seat,"stage":stage,
           "old_keep":x["old_keep"],"new_keep":x["new_keep"],
           "true_KEEP_win_turns":outcomes,
           "T1":sum(t==1 for t in outcomes)/FUTURES,
           "T2":sum(0<t<=2 for t in outcomes)/FUTURES,
           "T3":sum(0<t<=3 for t in outcomes)/FUTURES
        })
        assert result[-1]["T1"]<=result[-1]["T2"]<=result[-1]["T3"]
        print("DACK_V39_NEW129K_CHANGED_K_PHYSICAL",gid,stage,
              "elapsed",round(time.monotonic()-start,2),flush=True)
    outdoc={
      "schema":SCHEMA,"status":"PASS","policy_approved":False,
      "shard":shard,"n_futures_per_changed_state":FUTURES,
      "original_early_stage_denominator":3072,
      "source_census_sha256":hashlib.sha256(raw).hexdigest(),
      "model_sha256":policy.MODEL_SHA,
      "source_v33b_bottom_sha256":kernel.v33b.MODEL_SHA,
      "gameplay_beam":160,"exact_same_action_regret_zero_pruned":True,
      "physical_result_rows":result}
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,"wt") as f:json.dump(outdoc,f,sort_keys=True)
    print("DACK_V39_NEW129K_CHANGED_KEEP_SHARD_PASS",shard,len(result),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--shard",type=int,required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args();run(a.shard,a.out)
