#!/usr/bin/env python3
"""v38 independent 129k forced-MULL value under frozen common continuation.

Only (seat,stage) cells attached to at least one policy-disagreement
need physical outcomes, because all others have exactly zero
action-value contrast. Reject current seven, restore ALL 99 physical
slots at each later London stage, follow the same frozen v27
keep+v33b bottom continuation used for K in training/validation.
128 independent physical full99 replay futures per required C cell.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,random,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from dack_simulator.validation import v34_frozen_v33b_continuation as kernel
import dack_paired_counterfactual_v38_weighted_regret_20261101 as policy

CENSUS=ROOT/"datasets/v38_129k_frozen_outcome_blind_census.json"
PROTO="DACK_V38_NEW129K_FULL99_FROZEN_FUTURE_C"
N=128
SCHEMA="dack_v38_129k_independent_shared_true_MULL_v1"

def seed(*p):
    return int.from_bytes(hashlib.sha256(json.dumps(
       (PROTO,*p),separators=(",",":")).encode()).digest()[:8],"big")

def run(seat,stage,out):
    if seat not in range(4) or stage not in (0,1,2):raise ValueError("cell invalid")
    policy.audit()
    raw=CENSUS.read_bytes();d=json.loads(raw)
    assert d["schema"]=="dack_v38_129k_new_random_512_outcome_blind_census_v1"
    assert d["status"]=="PASS" and d["random_stage_state_denominator"]==1536
    assert d["actual_action_changes"]>=12 and d["changed_actual_London_path_games"]>=8
    assert d["frozen_v37_direct_regret_model_sha256"]==policy.MODEL_SHA
    required=set((x["seat"],x["stage"]) for x in d["all_early_stage_decisions"] if x["changed"])
    key=(seat,stage)
    # Empty C cells are still archived to keep a fixed 12-job matrix,
    # but need no physical simulated futures.
    futures=N if key in required else 0
    ref=kernel.ref;outcomes=[];start=time.monotonic()
    for j in range(futures):
        orders=[]
        for later in range(stage+1,8):
            slots=list(ref.SLOTS)
            random.Random(seed("restore_full99",seat,stage,j,later)).shuffle(slots)
            orders.append(tuple(slots))
        state,hist=kernel.continue_from(stage+1,seat,orders)
        assert hist[0]["stage"]==stage+1 and hist[-1]["kept"]
        ref.sim.reset_caches();ref.sim.root.install(kernel.DECK_KEY)
        ref.sim.m.set_trial_seed(seed("stable_effects",seat,stage,j))
        t=int(ref.d._win_turn_from_unknown_order(
           state.hand,state.library,seat,beam=160,max_turn=3) or 0)
        assert t in (0,1,2,3)
        outcomes.append(t)
    assert len(outcomes)==futures
    doc={
      "schema":SCHEMA,"status":"PASS","policy_approved":False,
      "seat":seat,"stage":stage,"required_for_changed_actions":key in required,
      "physical_full99_futures":futures,"physical_win_turns":outcomes,
      "source_census_sha256":hashlib.sha256(raw).hexdigest(),
      "frozen_bottom_sha256":kernel.v33b.MODEL_SHA,
      "frozen_common_downstream_original_v27_keep_v33b_bottom":True,
      "reject_seven_restored_complete99_each_future":True,
      "gameplay_beam":160,
    }
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,"wt") as f:json.dump(doc,f,sort_keys=True)
    print("DACK_V38_NEW129K_TRUE_MULL_CELL_PASS",seat,stage,futures,
          round(time.monotonic()-start,2),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--seat",type=int,required=True)
    p.add_argument("--stage",type=int,required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args();run(a.seat,a.stage,a.out)
