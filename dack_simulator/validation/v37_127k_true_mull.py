#!/usr/bin/env python3
"""v37 127k fresh full99 MULL Q for ONLY seat-stage with changed action.

Read sealed outcome-blind 768-state census. If no change at cell,
output empty, because the cell's value has an EXACT zero coefficient
in the policy one-step regret. Else sample 128 full99 independent
London future sequences, exact frozen v27 future KEEP+v33b bottom
and stable strict beam160 gameplay.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,random,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from dack_simulator.validation import v34_frozen_v33b_continuation as kernel

CENSUS=ROOT/"datasets/v37_127k_outcome_blind_census.json"
PROTO="DACK_V37_127K_HOLDOUT_NEW_FULL99_SHARED_MULL"
N=128
SCHEMA="dack_v37_127k_true_shared_frozen_QMULL_v1"
def seed(*parts):
    return int.from_bytes(hashlib.sha256(json.dumps(
        (PROTO,*parts),separators=(",",":")).encode()).digest()[:8],"big")

def run(seat,stage,out):
    assert seat in range(4) and stage in (0,1,2)
    kernel.initialize()
    c=json.loads(CENSUS.read_text())
    assert c["schema"]=="dack_v37_127k_unseen_complete_outcome_blind_action_census_v1"
    assert c["status"]=="PASS" and c["no_127k_actual_game_outcomes_sampled"]
    assert c["source_v33b_sha256"]==kernel.v33b.MODEL_SHA
    required={(r["seat"],r["stage"]) for r in c["complete_stage_rows"] if r["changed"]}
    chosen=(seat,stage) in required
    turns=[]
    if chosen:
        ref=kernel.ref
        for j in range(N):
            orders=[]
            for s in range(stage+1,8):
                slots=list(ref.SLOTS)
                random.Random(seed("new_full99",seat,stage,j,s)).shuffle(slots)
                orders.append(tuple(slots))
            state,hist=kernel.continue_from(stage+1,seat,orders)
            assert hist and hist[0]["stage"]==stage+1 and hist[-1]["kept"]
            ref.sim.reset_caches();ref.sim.root.install(kernel.DECK_KEY)
            ref.sim.m.set_trial_seed(seed("effects",seat,stage,j))
            t=int(ref.d._win_turn_from_unknown_order(
                state.hand,state.library,seat,beam=160,max_turn=3) or 0)
            assert t in (0,1,2,3);turns.append(t)
            if (j+1)%64==0:
                print("DACK_V37_127K_FULL99_SHARED_C",seat,stage,j+1,flush=True)
    assert len(turns)==(N if chosen else 0)
    doc={
      "schema":SCHEMA,"status":"PASS",
      "seat":seat,"stage":stage,"required_by_changed_action":chosen,
      "full99_futures":len(turns),
      "full99_restored_after_rejected_seven":True,
      "unchanged_action_C_exact_zero_pruning":True,
      "frozen_v27_future_KEEP_and_v33b_bottom":True,
      "source_v33b_sha256":kernel.v33b.MODEL_SHA,
      "census_sha256":hashlib.sha256(CENSUS.read_bytes()).hexdigest(),
      "strict_actual_beam160":True,"turns":turns}
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,"wt") as f:json.dump(doc,f,sort_keys=True)
    print("DACK_V37_127K_C_CELL_PASS",seat,stage,len(turns),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--seat",type=int,required=True)
    p.add_argument("--stage",type=int,required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args();run(a.seat,a.stage,a.out)
