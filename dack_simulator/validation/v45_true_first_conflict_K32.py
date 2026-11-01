#!/usr/bin/env python3
"""v45: independent physical KEEP samples at real v5/v43 first disagreements.
Original 151k outer groups are already inspected; no population claims.
"""
import argparse,hashlib,json,gzip,random,sys
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from dack_simulator.validation import v45_frozen_v43_continuation as k
SOURCE=ROOT/"benchmark_results/v45_v5_v43_matched_151k_N128_first_conflict.json"
SCHEMA="dack_v45_physical_first_conflict_K32_C64_v43_downstream_1"
def cases():
    d=json.loads(SOURCE.read_text())
    assert d["status"]=="PASS" and d["counts"]=={"N":128,"v5_byT2":73,"v43_byT2":65}
    a=sorted([r for r in d["cases"] if r["first_disagreement_stage"] is not None],key=lambda x:x["gid"])
    assert len(a)==44
    return a,hashlib.sha256(SOURCE.read_bytes()).hexdigest()
def game(state,seat,seed):
    ref=k.ref
    ref.sim.reset_caches();ref.sim.root.install(k.DECK_KEY)
    ref.sim.m.set_trial_seed(seed)
    if hasattr(ref.d,"_WIN_CACHE"):ref.d._WIN_CACHE.clear()
    t=ref.d._win_turn_from_unknown_order(state.hand,state.library,seat,beam=160,max_turn=3)
    assert t is None or t in (0,1,2,3)
    return int(t or 0)
def run(shard,out):
    assert shard in range(8)
    k.selftest()
    allrows,sha=cases()
    rows=[]
    for ix,r in enumerate(allrows):
        if ix%8!=shard:continue
        gid=int(r["gid"]);stage=int(r["first_disagreement_stage"]);seat=int(r["seat"])
        ref=k.ref;deck=ref.SLOT_VARIANTS[k.DECK_KEY]
        s=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
        actual_seat,orders=ref.stage_slots(s);assert seat==actual_seat
        order=orders[stage];seven=tuple(deck[x] for x in order[:7])
        unseen=tuple(deck[x] for x in order[7:])
        assert len(unseen)==92 and Counter(seven)+Counter(unseen)==Counter(deck.values())
        v5first=bool(r["v5_keeps_first"])
        pre="v5" if v5first else "v43"
        hand=tuple(r[pre+"_selected_hand_at_comparison"])
        bottom=tuple(r[pre+"_selected_bottom_at_comparison"])
        assert Counter(hand)+Counter(bottom)==Counter(seven)
        outcomes=[]
        for trial in range(32):
            shuffled=list(unseen)
            random.Random(k.stable_seed("v45_K_unseen92",gid,stage,trial)).shuffle(shuffled)
            state=ref.d.State(1,hand,tuple(shuffled)+bottom)
            outcomes.append(game(state,seat,k.stable_seed("v45_K_chance",gid,stage,trial)))
        rows.append({"gid":gid,"seat":seat,"stage":stage,"v5_first_keeps":v5first,
            "hand_selected_by":pre,"hand":list(hand),"bottom":list(bottom),
            "turns":outcomes})
        print("DACK_V45_NEW_KEEP_PHYSICAL",gid,stage,v5first,sum(0<t<=2 for t in outcomes),flush=True)
    assert 5<=len(rows)<=6
    d={"schema":SCHEMA,"status":"PASS","kind":"K","shard":shard,
       "source_sha256":sha,"K_futures":32,
       "source_historical_N44_not_fresh_population":True,
       "true_v43_downstream_selftest":True,
       "blind_unknown92_and_real_beam160":True,
       "no_original_v5_evaluator_used":True,"rows":rows}
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,"wt") as f:json.dump(d,f,sort_keys=True)
    print("DACK_V45_K_SHARD_PASS",shard,len(rows),flush=True)
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--shard",type=int,required=True);p.add_argument("--out",required=True)
    q=p.parse_args();run(q.shard,q.out)
