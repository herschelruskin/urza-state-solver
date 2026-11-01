#!/usr/bin/env python3
"""v41 prospective *conditional* physical action-value source, 148k pilot.

Mode K: 64 entirely new independent physical groups x 3 early stages x 8
independently reshuffled hidden92 futures under exact v33b retained hand.
Mode C: 12 independent seat-stage cells x 64 fully restored 99-card future
London draws under the frozen v27/v33b continuation (NOT v41 future).
The v41 full-group model and decision rule are frozen BEFORE outcomes.
This is NOT a whole-game comparison nor a prospective v5 benchmark.
"""
from __future__ import annotations
import argparse,gzip,glob,hashlib,json,random,sys,time
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from dack_simulator.validation import v34_frozen_v33b_continuation as kernel
from dack_simulator.validation import v41_train_early_physical_regret as train

MODELPATH=ROOT/"models/v41_early_physical_regret/v41_capability_early_physical_regret_RESEARCH.json"
SCHEMA="dack_v41_148k_prospective_conditional_physical_K_C_1"
START,STOP=148000,148064
K_SHARD=8
K_TRIALS=8
C_TRIALS=64

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def model():
    m=json.loads(MODELPATH.read_text())
    assert m["schema"]==train.SCHEMA and m["mode"]=="capability"
    assert m["model_approved"] is False and m["no_v5_teacher_features_or_labels_in_fit"]
    assert m["stage_states"]==253 and m["source_physical_groups"]==125
    assert tuple(m["gamma_stage_deployment_only"])==(0,1,2)
    assert m["keep_threshold_deadband"]==.05 and m["max_predicted_T3_loss"]==.10
    return m

def frozen_C():
    paths=sorted(glob.glob(str(ROOT/"benchmark_results/v34_consistent_regret_shards/v34_C_*.json.gz")))
    assert len(paths)==28
    out={}
    for path in paths:
        with gzip.open(path,"rt") as src:d=json.load(src)
        assert d["schema"]=="dack_v34_shared_Qmull_exact_frozen_v33b_downstream"
        assert d["status"]=="PASS" and d["strict_beam160"]
        key=(int(d["seat"]),int(d["stage"]))
        trials=[int(t["turn"]) for t in d["results"]]
        assert len(trials)==96 and key not in out
        out[key]={h:sum(train.pass_by(t,h) for t in trials)/96 for h in (2,3)}
    return out

def fitted(m,h,x):
    a=m["models"][f"K{h}"]
    idx=a["feature_indices"]
    assert [train.ALL_NAMES[int(j)] for j in idx]==a["feature_names"]
    features=[x[int(j)] for j in idx]
    z=sum(float(b)*(float(v)-float(mean))/float(scale)
          for b,v,mean,scale in zip(a["coefficients"],features,a["scale_mean"],a["scale"]))
    return max(0.,min(1.,float(a["intercept"])+z))

def setup():
    kernel.initialize()
    assert kernel.DECK_KEY=="one_key_34"
    assert kernel.ref.SPEC["beam"]==160 and len(kernel.ref.SLOTS)==99
    m=model()
    assert kernel.v33b.MODEL_SHA==m["source_v33b_model_sha256"]
    return m,frozen_C()

def K_one(gid,m,old_C):
    ref=kernel.ref
    deck=ref.SLOT_VARIANTS[kernel.DECK_KEY]
    seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
    seat,orders=ref.stage_slots(seed)
    out=[]
    for stage in (0,1,2):
        order=orders[stage]
        seven=tuple(deck[t] for t in order[:7])
        unknown=tuple(deck[t] for t in order[7:])
        assert Counter(seven)+Counter(unknown)==Counter(deck.values())
        sel=kernel.current(seven,unknown,seat,stage)
        assert Counter(sel["hand"])+Counter(sel["bottom"])==Counter(seven)
        x=train.features(seven,sel["hand"],sel["bottom"],unknown,seat,
              stage,sel["old_v27_Qkeep"],sel["old_v27_DP"])
        p2=fitted(m,2,x);p3=fitted(m,3,x)
        cell=old_C[(seat,stage)]
        proposal=train.decide({
             "old_keep":sel["old_v27_keep"],"C2":cell[2],"C3":cell[3]
        },p2,p3)
        results=[]
        for future in range(K_TRIALS):
            sh=list(unknown)
            random.Random(kernel.stable_seed(
                  "v41_new_148k_blind_keep_unseen92",gid,stage,future)).shuffle(sh)
            state=kernel.state_from(seven,tuple(sh),sel)
            ref.sim.reset_caches();ref.sim.root.install(kernel.DECK_KEY)
            ref.sim.m.set_trial_seed(kernel.stable_seed(
                  "v41_new_148k_independent_gameplay_chance",gid,stage,future))
            turn=int(ref.d._win_turn_from_unknown_order(
                state.hand,state.library,seat,beam=160,max_turn=3) or 0)
            assert turn in (0,1,2,3)
            results.append(turn)
        out.append({
            "game_id":gid,"seat":seat,"stage":stage,"keep_n":sel["keep_n"],
            "seven":list(seven),
            "selected_v33b_hand":list(sel["hand"]),
            "selected_v33b_bottom":list(sel["bottom"]),
            "bottom_changed_from_v14":bool(sel["v33b_overrode_bottom"]),
            "v27_keep":bool(sel["old_v27_keep"]),
            "v41_keep":bool(proposal),
            "v41_pred_K2":p2,"v41_pred_K3":p3,
            "old_96_C2":cell[2],"old_96_C3":cell[3],
            "physical_K_turns":results,
        })
    return out

def run_K(start,out):
    if not (START<=start<STOP and start%K_SHARD==0 and start+K_SHARD<=STOP):
        raise ValueError("K exactly one of eight 148k N8 shards")
    m,c=setup()
    rows=[];t0=time.monotonic()
    for gid in range(start,start+K_SHARD):
        r=K_one(gid,m,c)
        assert len(r)==3
        rows+=r
        print("DACK_V41_FRESH_K_GROUP",gid,
              "early_actions_changed",sum(x["v27_keep"]!=x["v41_keep"] for x in r),
              "elapsed",round(time.monotonic()-t0,3),flush=True)
    report={
      "schema":SCHEMA,"status":"PASS","action":"K",
      "game_ids":[start,start+K_SHARD-1],"groups":K_SHARD,
      "stages":[0,1,2],"futures_per_stage":K_TRIALS,
      "source_v41_model_sha256":digest(MODELPATH),
      "source_v33b_model_sha256":kernel.v33b.MODEL_SHA,
      "source_v27_keep_and_v33b_bottom_frozen":True,
      "model_decision_made_before_futures":True,
      "full_99_card_slots_and_blind_unseen_shuffled":True,
      "strict_actual_beam160":True,
      "no_original_v5_calls":True,
      "prospective_groups_not_used_in_fit":True,
      "not_end_to_end_winrate":True,
      "rows":rows}
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,"wt") as f:json.dump(report,f,sort_keys=True)
    print("DACK_V41_FRESH_K_SHARD_PASS",start,len(rows),flush=True)

def run_C(seat,stage,out):
    if not (0<=seat<4 and 0<=stage<=2):raise ValueError("C seat 0-3 and stage 0-2")
    m,c=setup()
    ref=kernel.ref;turns=[];t0=time.monotonic()
    for trial in range(C_TRIALS):
        orders=kernel.later_orders(seat,stage,trial,"v41_new_148k_C_full99")
        ref.sim.reset_caches();ref.sim.root.install(kernel.DECK_KEY)
        ref.sim.m.set_trial_seed(kernel.stable_seed(
            "v41_new_148k_C_choose",seat,stage,trial))
        state,hist=kernel.continue_from(stage+1,seat,orders)
        assert hist and hist[0]["stage"]==stage+1
        assert hist[-1]["kept"]
        ref.sim.reset_caches();ref.sim.root.install(kernel.DECK_KEY)
        ref.sim.m.set_trial_seed(kernel.stable_seed(
            "v41_new_148k_C_blind_gameplay",seat,stage,trial))
        turn=int(ref.d._win_turn_from_unknown_order(
            state.hand,state.library,seat,beam=160,max_turn=3) or 0)
        assert turn in (0,1,2,3)
        turns.append(turn)
        if (trial+1)%16==0:
            print("DACK_V41_NEW_C_PROGRESS",seat,stage,trial+1,
                  "seconds",round(time.monotonic()-t0,2),flush=True)
    d={
     "schema":SCHEMA,"status":"PASS","action":"C","seat":seat,"stage":stage,
     "independent_full99_futures":C_TRIALS,
     "future_London_stage_starts_at":stage+1,
     "all_99_cards_returned_on_mull":True,
     "frozen_downstream_v27_keep_v33b_bottom":True,
     "no_current_hand_used_for_C":True,
     "model_fixed_prior_to_C_futures":True,
     "source_v41_model_sha256":digest(MODELPATH),
     "source_v33b_model_sha256":kernel.v33b.MODEL_SHA,
     "strict_actual_beam160":True,
     "not_end_to_end_winrate":True,
     "turns":turns,
    }
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,"wt") as f:json.dump(d,f,sort_keys=True)
    print("DACK_V41_FRESH_C_CELL_PASS",seat,stage,len(turns),flush=True)

if __name__=="__main__":
    a=argparse.ArgumentParser()
    a.add_argument("--action",choices=("K","C"),required=True)
    a.add_argument("--start",type=int)
    a.add_argument("--seat",type=int)
    a.add_argument("--stage",type=int)
    a.add_argument("--out",required=True)
    v=a.parse_args()
    if v.action=="K":run_K(v.start,v.out)
    else:run_C(v.seat,v.stage,v.out)
