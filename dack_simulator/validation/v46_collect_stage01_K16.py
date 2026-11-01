#!/usr/bin/env python3
"""v46 unconditional random seven at London 0 and 1: real physical QKEEP.

Sample distinct game IDs. Both stage-0 and stage-1 seven are scored even
when v43 would have kept stage-0; stage-1 is a legitimate independently
reshuffled counterfactual seven, not an actual reached stage. Count independent
outer game IDs, NOT 2*16 rollouts as independent hands.

For each seven: 16 new independent hidden92 futures, original deck/cards,
same physical hand because no bottoms at these two stages; strict beam160,
original stable-dice. Preserve frozen v43 original Q2 score and threshold.
"""
import argparse,gzip,json,random,hashlib,sys
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from dack_simulator.validation import v45_frozen_v43_continuation as k

SCHEMA="dack_v46_random_seven_real_beam160_stage0_stage1_K16_v1"
FIRST=163000;N=256;SHARD=16;FUTURES=16
def run(start,out):
    assert start in range(FIRST,FIRST+N,SHARD)
    k.initialize()
    ref=k.ref;deck=ref.SLOT_VARIANTS[k.DECK_KEY]
    assert len(deck)==99 and tuple(ref.sim.STAGES[:2])==(7,7)
    rows=[]
    for gid in range(start,start+SHARD):
        canonical=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
        seat,orders=ref.stage_slots(canonical)
        for stage in (0,1):
            order=orders[stage]
            seven=tuple(deck[t] for t in order[:7])
            unseen=tuple(deck[t] for t in order[7:])
            assert len(unseen)==92 and Counter(seven)+Counter(unseen)==Counter(deck.values())
            assert len(seven)==7
            chosen=k.choose_at(stage,seat,order,deck)
            assert Counter(chosen["hand"])==Counter(seven) and chosen["bottom"]==[]
            assert chosen["seven"]==list(seven)
            turns=[]
            for future in range(FUTURES):
                hidden=list(unseen)
                random.Random(k.stable_seed("v46_blind_unseen92_keep",
                    gid,stage,future)).shuffle(hidden)
                state=ref.d.State(1,seven,tuple(hidden))
                ref.sim.reset_caches();ref.sim.root.install(k.DECK_KEY)
                ref.sim.m.set_trial_seed(k.stable_seed(
                    "v46_keep_stateless_chance",gid,stage,future))
                if hasattr(ref.d,"_WIN_CACHE"):ref.d._WIN_CACHE.clear()
                turn=ref.d._win_turn_from_unknown_order(
                    state.hand,state.library,seat,beam=160,max_turn=3)
                assert turn is None or turn in (0,1,2,3)
                turns.append(int(turn or 0))
            rows.append({"gid":gid,"stage":stage,"seat":seat,
                 "seven":list(seven),
                 "source_v43_pred_Q2":float(chosen["raw"]),
                 "source_v43_DP":float(chosen["threshold"]),
                 "source_v43_keep":bool(chosen["kept"]),
                 "physical_keep_turns":turns})
        print("DACK_V46_RANDOM_SEVEN_K_DONE",gid,
              "stage0",sum(0<t<=2 for t in rows[-2]["physical_keep_turns"]),
              "stage1",sum(0<t<=2 for t in rows[-1]["physical_keep_turns"]),flush=True)
    assert len(rows)==32
    doc={"schema":SCHEMA,"status":"PASS","range":[start,start+15],
       "N_independent_physical_groups":16,"stage_states_per_group":2,
       "K_independent_blind_futures_per_stage":FUTURES,
       "strict_99_card_beam160_original_dice":True,
       "stage0_and_stage1_have_no_bottom_choices":True,
       "stage1_sampled_even_if_stage0_would_keep":True,
       "unseen_realized_future_never_input_to_v43_score":True,
       "source_data_is_new_random_physical_not_teacher_selected":True,
       "no_model_trained_on_any_game_from_163k_at_collection":True,
       "research_only":True,"rows":rows}
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,"wt") as f:json.dump(doc,f,sort_keys=True)
    print("DACK_V46_RANDOM_16_GROUP_K_SHARD_PASS",start,flush=True)
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--start",type=int,required=True)
    p.add_argument("--out",required=True);args=p.parse_args();run(args.start,args.out)
