#!/usr/bin/env python3
"""v37 posthoc exploratory physical KEEP outcomes for 24 T3-blocked actions.

Selected on frozen v37 *predictions*, after inspecting the 127k
action census. This is NOT independent population validation.
The 24 exact visible sevens/seat/stages were saved and sealed in
POSTHOC manifest before *these* physical outcome draws.
32 fresh independent unknown92 permutations/hand, strict beam160,
exact frozen v33b kept bottom, original stable seeded effects.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,random,sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from dack_simulator.validation import v34_frozen_v33b_continuation as kernel

MAN=ROOT/"datasets/v37_POSTHOC_T3_blocked_physical_diagnostic_manifest.json"
PROTO="DACK_V37_POSTHOC_127K_24_T3BLOCK_PHYSICAL_KEEP_FUTURES"
SCHEMA="dack_v37_posthoc_T3blocked_127k_TRUE_KEEP_1"
N=32;SHARDS=8
def seed(*args):
    return int.from_bytes(hashlib.sha256(json.dumps(
        (PROTO,*args),separators=(",",":")).encode()).digest()[:8],"big")

def run(index,out):
    if index not in range(SHARDS):raise ValueError
    kernel.initialize()
    m=json.loads(MAN.read_text())
    assert m["schema"]=="dack_v37_posthoc_127k_T3_only_blocked_action_census_exploratory"
    assert m["status"]=="PASS" and m["number_T2_gate_passed_T3_only_blocked"]==24
    assert m["no_physical_gameplay_outcomes_generated"]
    ref=kernel.ref;deck=ref.SLOT_VARIANTS[kernel.DECK_KEY]
    rows=[]
    for i,entry in enumerate(m["blocked_visible_actions"]):
        if i%SHARDS!=index:continue
        gid=entry["game_id"];stage=entry["stage"];seat=entry["seat"]
        originalseat,orders=ref.stage_slots(int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE)
        assert seat==originalseat and entry["old_v27_KEEP"]
        seen=tuple(deck[x] for x in orders[stage][:7])
        unknown=tuple(deck[x] for x in orders[stage][7:])
        assert Counter(seen)+Counter(unknown)==Counter(deck.values())
        sel=kernel.current(seen,unknown,seat,stage)
        assert list(seen)==entry["visible_seven"]
        assert Counter(sel["hand"])==Counter(entry["v33b_kept_hand"])
        assert Counter(sel["bottom"])==Counter(entry["v33b_bottom"])
        turns=[]
        for j in range(N):
            hidden=list(unknown)
            random.Random(seed("unknown92",gid,stage,j)).shuffle(hidden)
            state=kernel.state_from(seen,tuple(hidden),sel)
            ref.sim.reset_caches();ref.sim.root.install(kernel.DECK_KEY)
            ref.sim.m.set_trial_seed(seed("stable_effects",gid,stage,j))
            t=int(ref.d._win_turn_from_unknown_order(
                state.hand,state.library,seat,beam=160,max_turn=3) or 0)
            assert t in (0,1,2,3)
            turns.append(t)
        rows.append({
           "game_id":gid,"stage":stage,"seat":seat,
           "source_manifest_selected_index":i,
           "true_KEEP_turns":turns,
           "model_pred_KEEP_minus_MULL_T2":entry["v37_pred_T2_median"],
           "model_pred_KEEP_minus_MULL_T3":entry["v37_pred_T3_median"]})
        print("DACK_V37_POSTHOC_TRUE_KEEP",gid,stage,i,flush=True)
    assert len(rows)==3
    doc={
      "schema":SCHEMA,"status":"PASS","policy_approved":False,
      "clearly_posthoc_exploratory_not_independent_validation":True,
      "physical_beam160":True,
      "futures_per_selected_action":N,
      "source_manifest_sha256":hashlib.sha256(MAN.read_bytes()).hexdigest(),
      "source_frozen_v33b_sha256":kernel.v33b.MODEL_SHA,
      "shard":index,"rows":rows}
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,"wt") as f:json.dump(doc,f,sort_keys=True)
    print("DACK_V37_POSTHOC_T3_KEEP_SHARD_PASS",index,len(rows),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--index",type=int,required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args();run(a.index,a.out)
