#!/usr/bin/env python3
"""v46 independent physical values for first and second London sevens.

All physically independent deal IDs: train 160000..160127, dev
160128..160191. Each group yields BOTH hypothetical seven-card stages
(the second is physically reached only when first stage mulliganed).
Every sampled KKEEP keeps the entire seven with zero bottoming, and all
unknown92 futures are independently reshuffled. No source-v5 action labels.
C sampling uses independent full99 v43 future London continuation.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,random,sys,time
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from dack_simulator.validation import v45_frozen_v43_continuation as k

SCHEMA="dack_v46_independent_first_two_sevens_K24_C128_physical_source_v1"
GROUPS_PER_SHARD=8
K_FUTURES=24
C_FUTURES=128
TRAIN=(160000,160127)
DEV=(160128,160191)

def win(state,seat,seed):
    ref=k.ref
    ref.sim.reset_caches();ref.sim.root.install(k.DECK_KEY)
    ref.sim.m.set_trial_seed(seed)
    if hasattr(ref.d,"_WIN_CACHE"):ref.d._WIN_CACHE.clear()
    t=ref.d._win_turn_from_unknown_order(state.hand,state.library,seat,beam=160,max_turn=3)
    assert t is None or t in (0,1,2,3)
    return int(t or 0)

def sample_group(gid,split):
    ref=k.ref;deck=ref.SLOT_VARIANTS[k.DECK_KEY]
    seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
    seat,orders=ref.stage_slots(seed)
    rows=[]
    for stage in (0,1):
        order=orders[stage]
        seven=tuple(deck[s] for s in order[:7])
        unseen=tuple(deck[s] for s in order[7:])
        assert Counter(seven)+Counter(unseen)==Counter(deck.values())
        assert len(seven)==7 and len(unseen)==92
        v43=k.choose_at(stage,seat,order,deck)
        assert v43["keep_n"]==7 and v43["candidate_index"]==0
        assert Counter(v43["hand"])==Counter(seven) and not v43["bottom"]
        assert v43["state"].hand==tuple(v43["hand"]) and v43["state"].library==unseen
        turns=[]
        for f in range(K_FUTURES):
            shuffled=list(unseen)
            random.Random(k.stable_seed("v46_K_unknown92",split,gid,stage,f)).shuffle(shuffled)
            state=ref.d.State(1,tuple(v43["hand"]),tuple(shuffled))
            turns.append(win(state,seat,k.stable_seed("v46_K_chance",split,gid,stage,f)))
        rows.append({
            "gid":gid,"stage":stage,"seat":seat,
            "seven":list(seven),"unknown_counts":dict(sorted(Counter(unseen).items())),
            "v43_raw_Q2":v43["raw"],"v43_DP_threshold":v43["threshold"],
            "v43_keep":v43["kept"],"keep_turns":turns,
            "zero_bottoms_and_no_seven_hand_choice":True,
            "not_guaranteed_second_stage_is_reached":stage==1,
        })
    return rows

def K(shard,out):
    assert shard in range(24)
    split="train" if shard<16 else "dev"
    start=160000+shard*GROUPS_PER_SHARD
    a,b=TRAIN if split=="train" else DEV
    assert a<=start and start+7<=b
    k.initialize()
    results=[];starttime=time.perf_counter()
    for gid in range(start,start+GROUPS_PER_SHARD):
        results+=sample_group(gid,split)
        print("DACK_V46_PHYSICAL_EARLY_SEVEN",split,gid,
             "T2",sum(0<t<=2 for t in results[-2]["keep_turns"]),
             sum(0<t<=2 for t in results[-1]["keep_turns"]),
             "seconds",round(time.perf_counter()-starttime,1),flush=True)
    assert len(results)==16
    doc={"schema":SCHEMA,"status":"PASS","kind":"K","split":split,
       "groups":8,"physical_state_rows":16,"K_futures_each":K_FUTURES,
       "real_99_cards_and_physical_beam160":True,
       "full_seven_kept_no_bottom_choice":True,
       "candidate_value_used_same_visible_seven":True,
       "K_hidden_order_blind_to_decisions":True,
       "stage1_is_hypothetical_not_always_reached":True,
       "train_dev_disjoint_source_groups":True,
       "v5_teacher_not_used":True,"no_model_fitted_or_promoted":True,
       "rows":results}
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,"wt") as f:json.dump(doc,f,sort_keys=True)
    print("DACK_V46_EARLY_SEVEN_K_SHARD_PASS",split,shard,flush=True)

def C(seat,stage,out):
    assert seat in range(4) and stage in (0,1)
    k.initialize()
    t0=time.perf_counter()
    turns=[]
    for future in range(C_FUTURES):
        # Fresh entire 99 slot redraw; separate stage subkeys; frozen v43
        # downstream for all future stages, NOT trained v46 or original-v5.
        orders=k.future_orders(seat,stage,20000+future)
        state,hist=k.continue_from(stage+1,seat,orders)
        assert hist[0]["stage"]==stage+1 and hist[-1]["kept"]
        turns.append(win(state,seat,k.stable_seed("v46_C_chance",seat,stage,future)))
        if (future+1)%32==0:print("DACK_V46_C_FULL99_PHYSICAL",seat,stage,future+1,"seconds",round(time.perf_counter()-t0,1),flush=True)
    doc={"schema":SCHEMA,"status":"PASS","kind":"C",
       "seat":seat,"stage":stage,"C_futures":C_FUTURES,
       "true_v43_frozen_full99_continuation":True,
       "restores_all_99_cards_and_new_london_shuffles":True,
       "seat_stage_C_shared_not_independent_per_hand":True,
       "v5_teacher_not_used":True,"no_model_fitted_or_promoted":True,
       "turns":turns}
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,"wt") as f:json.dump(doc,f,sort_keys=True)
    print("DACK_V46_C_CELL_PASS",seat,stage,flush=True)

if __name__=="__main__":
    a=argparse.ArgumentParser()
    a.add_argument("--kind",choices=["K","C"],required=True)
    a.add_argument("--shard",type=int)
    a.add_argument("--seat",type=int);a.add_argument("--stage",type=int)
    a.add_argument("--out",required=True)
    q=a.parse_args()
    if q.kind=="K":K(q.shard,q.out)
    else:C(q.seat,q.stage,q.out)
