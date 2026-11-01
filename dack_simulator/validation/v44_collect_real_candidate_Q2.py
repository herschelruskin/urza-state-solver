#!/usr/bin/env python3
"""v44 physical counterfactual value training for ALL legal London finalists.

Every independent physical 99-slot deal contributes ONE stage (2,3,4,5), its
exact seven and unknown 92-card *multiset*, and every original structural
top12 bottom candidate evaluated with 8 common unseen92 physical permutations
and common stable gameplay chance per future. No v5 teacher, proxy win
outcomes or actual game future order at feature extraction time.

Train: 154000..154191, dev: 154192..154255. 4-game smoke on 154000..154003
only; no smoke data added separately to the training corpus.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,random,sys,time
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import dack_paired_counterfactual_v27_T2_only_DP_20261101 as v27
import dack_mulligan_teacher_features_v13_20261031 as f
from dack_simulator.validation.collect_teacher_london_v13 import finalists
ref=v27.ref
PROTO="DACK_V44_TRUE_PHYSICAL_CANDIDATES_154K_V1"
SCHEMA="dack_v44_154k_candidate_physical_counterfactual_source_v1"
SPLITS={"train":(154000,154191),"dev":(154192,154255)}
FUTURES=8
STAGE_SEQUENCE=(2,3,4,5)

def seeded(*x):
    return int.from_bytes(hashlib.sha256(json.dumps(
        (PROTO,*x),separators=(",",":")).encode()).digest()[:8],"big")

def generate_one(gid):
    deck=ref.SLOT_VARIANTS["one_key_34"]
    assert len(deck)==99 and ref.SPEC["beam"]==160
    primary_seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
    seat,stage_orders=ref.stage_slots(primary_seed)
    stage=STAGE_SEQUENCE[(gid-SPLITS["train"][0])%len(STAGE_SEQUENCE)]
    kn=int(ref.sim.STAGES[stage])
    order=stage_orders[stage]
    seven=tuple(deck[s] for s in order[:7])
    unknown=tuple(deck[s] for s in order[7:])
    assert Counter(seven)+Counter(unknown)==Counter(deck.values())
    options=finalists(seven,kn,unknown)
    assert 7<=len(options)<=12
    pool=Counter(unknown)
    candidates=[]
    # Physically sample hidden draws once per hand/future, share across all
    # candidate bottoms; this reduces paired-comparison variance.
    permutations=[]
    for j in range(FUTURES):
        sh=list(unknown)
        random.Random(seeded("unseen_92_order",gid,stage,j)).shuffle(sh)
        assert Counter(sh)==Counter(unknown)
        permutations.append(tuple(sh))
    for i,opt in enumerate(options):
        hand=tuple(opt["hand"]);bottom=tuple(opt["bottom"])
        assert len(hand)==kn and len(bottom)==7-kn
        assert Counter(hand)+Counter(bottom)==Counter(seven)
        x=f.extract(seven,hand,bottom,pool,seat,kn,stage,opt["struct_rank"],i)
        baseline_q=float(v27.original.estimator.predict(v27.original.MODEL,x))
        turns=[]
        for j,sh in enumerate(permutations):
            ref.sim.reset_caches();ref.sim.root.install("one_key_34")
            ref.sim.m.set_trial_seed(seeded("common_physical_gameplay_chance",gid,stage,j))
            ref.d._WIN_CACHE.clear()
            val=ref.d._win_turn_from_unknown_order(
               hand,sh+bottom,seat,beam=160,max_turn=3)
            assert val is None or int(val) in (0,1,2,3)
            turns.append(int(val or 0))
        candidates.append({
           "idx":i,"struct_rank":opt["struct_rank"],
           "hand":list(hand),"bottom":list(bottom),
           "baseline_v27_pred_Q2":baseline_q,
           "turns":turns,
           "physical_Q2":sum(0<t<=2 for t in turns)/FUTURES,
           "physical_Q3":sum(0<t<=3 for t in turns)/FUTURES,
        })
    maxq=max(candidates,key=lambda c:(c["baseline_v27_pred_Q2"],-c["idx"]))
    cutoff=v27.original.DP["seat_continuations"][str(seat)]["thresholds_by_london_stage"][stage]
    return {
      "gid":gid,"seat":seat,"stage":stage,"keep_n":kn,
      "seven":list(seven),"unknown_counts":dict(sorted(pool.items())),
      "N_candidate_rows":len(candidates),
      "source_v27_maxq_index":maxq["idx"],
      "source_v27_maxq_pred_value":maxq["baseline_v27_pred_Q2"],
      "source_v27_DP":float(cutoff),"candidates":candidates
    }

def run(split,start,n,out):
    assert split in SPLITS
    lo,hi=SPLITS[split]
    assert n in (4,16) and lo<=start and start+n-1<=hi and (start-lo)%n==0
    if split=="dev":assert n==16
    a=v27.audit()
    assert a["status"]=="PASS"
    assert v27.original.MODEL["T3_reward_is_exactly_zero"]
    t0=time.monotonic();rows=[]
    for gid in range(start,start+n):
        rows.append(generate_one(gid))
        print("DACK_V44_REAL_CANDIDATE_GROUP",
          split,gid,"stage",rows[-1]["stage"],
          "candidates",rows[-1]["N_candidate_rows"],
          "actual_physical_games",rows[-1]["N_candidate_rows"]*FUTURES,
          "elapsed_seconds",round(time.monotonic()-t0,3),flush=True)
    report={
     "schema":SCHEMA,"status":"PASS","split":split,
     "range":[start,start+n-1],"independent_physical_groups":n,
     "one_stage_per_independent_group":True,
     "physical_futures_per_candidate":FUTURES,
     "strict_actual_99_card_deck_and_beam160":True,
     "all_structural_top12_candidates_evaluated":True,
     "same_physical_unseen92_futures_across_candidate_bottoms":True,
     "same_stable_chance_seed_across_candidate_bottoms":True,
     "no_v5_teacher_or_future_draw_information_used_in_selection":True,
     "source_v27_model_sha256":hashlib.sha256((ROOT/"models/dack_v27_expanded_T2_only_value_EXPERIMENTAL.json").read_bytes()).hexdigest(),
     "feature_schema_sha256":f.feature_hash(),
     "experimental_only_no_policy_approval":True,
     "rows":rows
    }
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,"wt") as g:json.dump(report,g,sort_keys=True)
    print("DACK_V44_PHYSICAL_CANDIDATE_SHARD_PASS",split,start,n,flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--split",choices=tuple(SPLITS),required=True)
    p.add_argument("--start",type=int,required=True)
    p.add_argument("--groups",type=int,default=16)
    p.add_argument("--out",required=True)
    x=p.parse_args()
    run(x.split,x.start,x.groups,x.out)
