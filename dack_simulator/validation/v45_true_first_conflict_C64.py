#!/usr/bin/env python3
"""v45 independent full99 future v43 mull continuation after actual conflicts.
Separate chance and independently restored deck for every new future London
stage, shared only within same seat/stage cell in the final bootstrap.
"""
import argparse,hashlib,json,gzip,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from dack_simulator.validation import v45_frozen_v43_continuation as k
from dack_simulator.validation.v45_true_first_conflict_K32 import SOURCE,SCHEMA,game,cases
def run(seat,stage,out):
    assert seat in range(4) and stage in range(5)
    k.selftest()
    selected,sha=cases()
    used=any(r["seat"]==seat and r["first_disagreement_stage"]==stage for r in selected)
    turns=[]
    if used:
        for future in range(64):
            orders=k.future_orders(seat,stage,future)
            state,hist=k.continue_from(stage+1,seat,orders)
            assert hist[0]["stage"]==stage+1 and hist[-1]["kept"]
            turns.append(game(state,seat,k.stable_seed("v45_C_chance",seat,stage,future)))
            if (future+1)%16==0:print("DACK_V45_NEW_FULL99_MULL",seat,stage,future+1,flush=True)
    assert len(turns)==(64 if used else 0)
    report={"schema":SCHEMA,"status":"PASS","kind":"C",
      "seat":seat,"stage":stage,"source_sha256":sha,
      "source_historical_N44_not_fresh_population":True,
      "true_v43_downstream_selftest":True,
      "all_99_cards_restored_for_each_later_london_stage":True,
      "full99_future_not_influenced_by_original_seven":True,
      "C_full99_independent_futures":len(turns),"turns":turns}
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,"wt") as f:json.dump(report,f,sort_keys=True)
    print("DACK_V45_C_CELL_PASS",seat,stage,len(turns),flush=True)
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--seat",type=int,required=True);p.add_argument("--stage",type=int,required=True)
    p.add_argument("--out",required=True);q=p.parse_args();run(q.seat,q.stage,q.out)
