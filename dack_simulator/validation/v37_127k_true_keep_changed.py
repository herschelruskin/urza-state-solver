#!/usr/bin/env python3
"""v37 independent 127k physical QKEEP only where v37 action != v27.

Outcome-blind 768-stage census is SEALED beforehand. For each changed
actual-stage hand, evaluate 32 new independent unknown92 permutations,
stable chance, exact frozen v33b bottom and strict beam160.
Unchanged actions contribute EXACT ZERO to one-step action regret.
Each of 64 four-outer-game shards still archives an empty record
if no candidate changes fall within its fixed physical ID range.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,random,sys,time
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from dack_simulator.validation import v34_frozen_v33b_continuation as kernel
import dack_mulligan_v37_features as feats
import dack_mulligan_v37_direct_regret as run
CENSUS=ROOT/"datasets/v37_127k_outcome_blind_census.json"
MODEL=ROOT/"models/dack_v37_direct_regret_EXPERIMENTAL.json"
N=32;SCHEMA="dack_v37_127k_true_changed_action_KEEP_only_v1"
PROTO="DACK_V37_127K_UNSEEN_CHANGED_KEEP_PHYSICAL_LABELS"
def seed(*items):
    return int.from_bytes(hashlib.sha256(json.dumps(
        (PROTO,*items),separators=(",",":")).encode()).digest()[:8],"big")

def one(index,out):
    assert index in range(64)
    kernel.initialize()
    census=json.loads(CENSUS.read_text())
    assert census["schema"]=="dack_v37_127k_unseen_complete_outcome_blind_action_census_v1"
    assert census["status"]=="PASS" and census["random_stage_states"]==768
    assert census["no_127k_actual_game_outcomes_sampled"]
    raw=MODEL.read_bytes();m=run.validate(json.loads(raw))
    assert hashlib.sha256(raw).hexdigest()==census["model_sha256"]
    assert kernel.v33b.MODEL_SHA==census["source_v33b_sha256"]
    base=127200+index*4
    changed=[r for r in census["complete_stage_rows"] if
             r["changed"] and base<=r["game_id"]<base+4]
    ref=kernel.ref;deck=ref.SLOT_VARIANTS[kernel.DECK_KEY]
    outrows=[];started=time.monotonic()
    for r in changed:
        gid=r["game_id"];stage=r["stage"];seat=r["seat"]
        originalseat,orders=ref.stage_slots(int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE)
        assert seat==originalseat
        seven=tuple(deck[s] for s in orders[stage][:7])
        unknown=tuple(deck[s] for s in orders[stage][7:])
        assert Counter(seven)+Counter(unknown)==Counter(deck.values())
        sel=kernel.current(seven,unknown,seat,stage)
        assert tuple(r["visible_seven"])==seven
        assert Counter(r["v33b_hand"])==Counter(sel["hand"])
        assert Counter(r["v33b_bottom"])==Counter(sel["bottom"])
        x=feats.extract(seven,unknown,seat,stage,sel)
        candidate,diag=run.decide(m,x,stage,sel["old_v27_keep"])
        assert candidate==r["new_keep"] and bool(sel["old_v27_keep"])==r["old_keep"]
        turns=[]
        for j in range(N):
            hidden=list(unknown)
            random.Random(seed("physical_hidden92",gid,stage,j)).shuffle(hidden)
            state=kernel.state_from(seven,tuple(hidden),sel)
            ref.sim.reset_caches();ref.sim.root.install(kernel.DECK_KEY)
            ref.sim.m.set_trial_seed(seed("stable_game_effects",gid,stage,j))
            t=int(ref.d._win_turn_from_unknown_order(
                state.hand,state.library,seat,beam=160,max_turn=3) or 0)
            assert t in (0,1,2,3);turns.append(t)
        outrows.append({"game_id":gid,"seat":seat,"stage":stage,
                        "old_keep":r["old_keep"],"new_keep":r["new_keep"],
                        "physical_KEEP_turns":turns})
        print("DACK_V37_127K_CHANGED_TRUE_KEEP",gid,stage,
              round(time.monotonic()-started,2),flush=True)
    assert len(outrows)==len(changed)
    doc={
      "schema":SCHEMA,"status":"PASS","shard":index,
      "game_ids":[base,base+3],
      "stage_population_denominator":768,
      "complete_outcome_blind_action_census_sha256":hashlib.sha256(CENSUS.read_bytes()).hexdigest(),
      "model_sha256":hashlib.sha256(raw).hexdigest(),
      "source_v33b_sha256":kernel.v33b.MODEL_SHA,
      "keep_futures_per_changed_state":N,
      "strict_actual_gameplay_beam160":True,
      "same_action_exact_zero_regret_pruned":True,
      "no_policy_approval":True,"rows":outrows}
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,"wt") as f:json.dump(doc,f,sort_keys=True)
    print("DACK_V37_127K_CHANGED_ONLY_KEEP_SHARD_PASS",index,len(outrows),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--index",type=int,required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args();one(a.index,a.out)
