#!/usr/bin/env python3
"""v36 124k ONLY changed-action true KEEP physical labels.

Read permanently frozen exhaustive 768-stage outcome-blind 124k
action census. For each changed decision in this shard, replay 32
independent shuffled unknown92 libraries with the EXACT v33b bottom
and strict beam160 stable seeded chance. Unchanged actions have
one-step regret EXACTLY ZERO and are never simulated here.

Shard selection by original game-ID modulo 16 depends on NO outcome.
All 256 outer physical game IDs remain in final population denominator.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,random,sys,time
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from dack_simulator.validation import v34_frozen_v33b_continuation as kernel
import dack_mulligan_v36_features as features
import dack_mulligan_v36_keep_value as runtime

N_SHARDS=16
N_FUTURES=32
PROTO="DACK_V36_124K_CHANGED_ONLY_BLIND_KEEP_REPLAY_V1"
CENSUS=ROOT/"datasets/v36_124k_outcome_blind_action_census.json"
MODEL=ROOT/"models/dack_v36_targeted_real_keep_EXPERIMENTAL.json"

def seed(*xs):
    return int.from_bytes(hashlib.sha256(json.dumps(
      (PROTO,*xs),separators=(",",":")).encode()).digest()[:8],"big")

def run(shard,out):
    if shard not in range(N_SHARDS):raise ValueError("16 fixed complete shards")
    kernel.initialize()
    raw=MODEL.read_bytes();m=runtime.read_model(json.loads(raw))
    data=json.loads(CENSUS.read_text())
    assert data["schema"]=="dack_v36_124k_frozen_actions_outcome_blind_census_v1"
    assert data["status"]=="PASS" and data["stage_states"]==768
    assert data["computed_before_any_124k_gameplay_outcomes"]
    assert data["complete_independent_random_outer_groups"]==256
    assert data["source_candidate_model_sha256"]==hashlib.sha256(raw).hexdigest()
    assert data["source_frozen_v33b_model_sha256"]==kernel.v33b.MODEL_SHA
    ref=kernel.ref;deck=ref.SLOT_VARIANTS[kernel.DECK_KEY]
    rows=[];started=time.perf_counter()
    chosen=[x for x in data["all_decisions"]
             if x["keep_changed"] and (x["game_id"]-124000)%N_SHARDS==shard]
    for entry in chosen:
        gid=entry["game_id"];stage=entry["stage"];seat=entry["seat"]
        originalseed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
        seat2,orders=ref.stage_slots(originalseed)
        assert seat==seat2
        seven=tuple(deck[x] for x in orders[stage][:7])
        unknown=tuple(deck[x] for x in orders[stage][7:])
        assert Counter(seven)+Counter(unknown)==Counter(deck.values())
        current=kernel.current(seven,unknown,seat,stage)
        assert tuple(entry["visible_seven"])==seven
        assert Counter(entry["chosen_v33b_hand"])==Counter(current["hand"])
        assert Counter(entry["chosen_v33b_bottom"])==Counter(current["bottom"])
        feat=features.extract(seven,current["hand"],current["bottom"],
                               tuple(sorted(unknown)),seat,stage,
                               current["old_v27_Qkeep"],current["old_v27_DP"])
        a,d=runtime.choose(m,feat,seat,stage,
                            current["old_v27_keep"],current["old_v27_Qkeep"])
        assert a==entry["new_keep"] and current["old_v27_keep"]==entry["old_keep"]
        assert a!=current["old_v27_keep"]
        labels=[]
        for j in range(N_FUTURES):
            hidden=list(unknown)
            random.Random(seed("new_unseen92",gid,stage,j)).shuffle(hidden)
            state=kernel.state_from(seven,tuple(hidden),current)
            ref.sim.reset_caches();ref.sim.root.install(kernel.DECK_KEY)
            ref.sim.m.set_trial_seed(seed("game_effects",gid,stage,j))
            t=int(ref.d._win_turn_from_unknown_order(
                  state.hand,state.library,seat,beam=160,max_turn=3) or 0)
            assert t in (0,1,2,3)
            labels.append(t)
        rows.append({
          "game_id":gid,"seat":seat,"stage":stage,
          "old_keep":entry["old_keep"],"new_keep":entry["new_keep"],
          "true_KEEP_turns":labels,
          "real_KEEP_by_T1":sum(t==1 for t in labels)/N_FUTURES,
          "real_KEEP_by_T2":sum(0<t<=2 for t in labels)/N_FUTURES,
          "real_KEEP_by_T3":sum(0<t<=3 for t in labels)/N_FUTURES,
          "physical_unseen_92_shuffled_blind":True,
        })
        assert rows[-1]["real_KEEP_by_T1"]<=rows[-1]["real_KEEP_by_T2"]<=rows[-1]["real_KEEP_by_T3"]
        print("DACK_V36_ONLY_REGRET_RELEVANT_KEEP_REPLAY",gid,stage,
           "elapsed",round(time.perf_counter()-started,2),flush=True)
    assert len(rows)==len(chosen)
    outdoc={
       "schema":"dack_v36_124k_changed_only_physical_keep_outcomes",
       "status":"PASS","shard":shard,
       "total_unconditional_action_stage_states":768,
       "changed_actions_in_this_shard":len(rows),
       "fresh_physical_futures_per_changed_state":N_FUTURES,
       "no_gameplay_for_exact_zero_action_regret":True,
       "frozen_action_census_sha256":hashlib.sha256(CENSUS.read_bytes()).hexdigest(),
       "model_sha256":hashlib.sha256(raw).hexdigest(),
       "v33b_bottom_sha256":kernel.v33b.MODEL_SHA,
       "actual_gameplay_beam160":True,
       "policy_approved":False,"rows":rows
    }
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,"wt") as f:json.dump(outdoc,f,sort_keys=True)
    print("DACK_V36_CHANGED_ONLY_STRICT_PHYSICAL_SHARD_PASS",shard,len(rows),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--shard",type=int,required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args();run(a.shard,a.out)
