#!/usr/bin/env python3
"""v46 new shared physical Qmull for seats x London stage0/1.

All 99 cards restored (including former seven) before each of 7/6 future
London stage deals. Draw stage orders independently; apply EXACT frozen v43
max-Q2 candidate+KEEP downstream and strict beam160 gameplay.
This distribution depends on seat and first rejected stage, not its cards.
Each seat-stage C128 lottery is ONE shared random object in inference.
"""
import argparse,gzip,json,random,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from dack_simulator.validation import v45_frozen_v43_continuation as k
from dack_simulator.validation.v46_collect_stage01_K16 import SCHEMA as KSCHEMA

SCHEMA="dack_v46_new_frozen_v43_full99_shared_C128_stage01_v1"
FUTURES=128
def run(seat,stage,out):
    assert seat in range(4) and stage in (0,1)
    k.initialize()
    ref=k.ref
    turns=[]
    for trial in range(FUTURES):
        future=[]
        for nextstage in range(stage+1,8):
            slots=list(ref.SLOTS)
            random.Random(k.stable_seed("v46_NEW_full99_separate_London",
                seat,stage,trial,nextstage)).shuffle(slots)
            assert len(slots)==99 and len(set(slots))==99
            future.append(tuple(slots))
        state,hist=k.continue_from(stage+1,seat,future)
        assert hist and hist[0]["stage"]==stage+1 and hist[-1]["kept"]
        ref.sim.reset_caches();ref.sim.root.install(k.DECK_KEY)
        ref.sim.m.set_trial_seed(k.stable_seed("v46_NEW_C_stateless_chance",
            seat,stage,trial))
        if hasattr(ref.d,"_WIN_CACHE"):ref.d._WIN_CACHE.clear()
        turn=ref.d._win_turn_from_unknown_order(
            state.hand,state.library,seat,beam=160,max_turn=3)
        assert turn is None or turn in (0,1,2,3)
        turns.append(int(turn or 0))
        if (trial+1)%32==0:
            print("DACK_V46_FULL99_C_PROGRESS",seat,stage,trial+1,flush=True)
    report={"schema":SCHEMA,"status":"PASS",
       "seat":seat,"stage":stage,"C_independent_full99_futures":FUTURES,
       "future_orders_new_tag_not_prior_v45_C":True,
       "all_99_cards_restored_before_each_London_draw":True,
       "full_99_deck_including_original_rejected_seven":True,
       "frozen_v43_policy_full_exact_continuation":True,
       "strict_beam160_and_stateless_dice":True,
       "shared_across_unrelated_K_seven_groups_same_seat_stage":True,
       "no_current_seven_or_hidden_current_order_in_C":True,
       "research_only":True,"turns":turns}
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,"wt") as f:json.dump(report,f,sort_keys=True)
    print("DACK_V46_FULL99_SHARED_C128_CELL_PASS",seat,stage,flush=True)
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--seat",type=int,required=True)
    p.add_argument("--stage",type=int,required=True);p.add_argument("--out",required=True)
    z=p.parse_args();run(z.seat,z.stage,z.out)
