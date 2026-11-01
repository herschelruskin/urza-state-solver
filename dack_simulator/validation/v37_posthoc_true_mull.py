#!/usr/bin/env python3
"""v37 posthoc exploratory shared Q(MULL) for T3-blocked states.

All rejected 7 returned to full99, future actual London stages
shuffled independently. Exact frozen v27 future keep and frozen
v33b bottom. 128 independently seeded physical futures per
relevant seat-stage cell, with nine unique required cells.
NOT independent policy validation after 127k census inspection.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,random,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from dack_simulator.validation import v34_frozen_v33b_continuation as kernel

MAN=ROOT/"datasets/v37_POSTHOC_T3_blocked_physical_diagnostic_manifest.json"
PROTO="DACK_V37_POSTHOC_127K_T3BLOCK_SHARED_FULL99_QMULL"
SCHEMA="dack_v37_posthoc_T3blocked_127k_TRUE_QMULL_1"
N=128
def seed(*args):
    return int.from_bytes(hashlib.sha256(json.dumps(
         (PROTO,*args),separators=(",",":")).encode()).digest()[:8],"big")
def run(seat,stage,out):
    assert seat in range(4) and stage in (0,1,2)
    kernel.initialize()
    m=json.loads(MAN.read_text())
    assert m["schema"]=="dack_v37_posthoc_127k_T3_only_blocked_action_census_exploratory"
    assert m["status"]=="PASS" and m["number_T2_gate_passed_T3_only_blocked"]==24
    assert m["no_physical_gameplay_outcomes_generated"]
    chosen=f"{seat}:{stage}" in m["required_C_cells_for_blocked_actions"]
    turns=[]
    if chosen:
        ref=kernel.ref;assert len(ref.SLOTS)==99 and ref.SPEC["beam"]==160
        for j in range(N):
            orders=[]
            for s in range(stage+1,8):
                slots=list(ref.SLOTS)
                random.Random(seed("future_99",seat,stage,j,s)).shuffle(slots)
                orders.append(tuple(slots))
            state,hist=kernel.continue_from(stage+1,seat,orders)
            assert hist and hist[0]["stage"]==stage+1 and hist[-1]["kept"]
            ref.sim.reset_caches();ref.sim.root.install(kernel.DECK_KEY)
            ref.sim.m.set_trial_seed(seed("stable_effects",seat,stage,j))
            t=int(ref.d._win_turn_from_unknown_order(
                 state.hand,state.library,seat,beam=160,max_turn=3) or 0)
            assert t in (0,1,2,3);turns.append(t)
        print("DACK_V37_POSTHOC_FULL99_MULL_C",seat,stage,N,flush=True)
    assert len(turns)==(N if chosen else 0)
    doc={
        "schema":SCHEMA,"status":"PASS","policy_approved":False,
        "posthoc_T3_blocked_selection_NOT_unseen_validation":True,
        "seat":seat,"stage":stage,"required_for_blocked_actions":chosen,
        "strict_beam160":True,
        "future_full99_reshuffles_return_rejected_seven":True,
        "frozen_v27_future_KEEP_v33b_bottom":True,
        "source_manifest_sha256":hashlib.sha256(MAN.read_bytes()).hexdigest(),
        "source_v33b_sha256":kernel.v33b.MODEL_SHA,
        "turns":turns}
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,"wt") as f:json.dump(doc,f,sort_keys=True)
    print("DACK_V37_POSTHOC_SHARED_MULL_CELL_PASS",seat,stage,len(turns),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--seat",type=int,required=True)
    p.add_argument("--stage",type=int,required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args();run(a.seat,a.stage,a.out)
