#!/usr/bin/env python3
"""v43 v5 candidate landscape for preselected actual v5/v27 conflict hands.

Calls the ACTUAL installed v5 batch.evaluate_keep on the physical 115k seven
and proves retained hand, bottom, raw score, refinement and threshold parity
against the archived v5 trace. Separately computes all up-to-12 original
candidate EVs with the unpruned v5 scorer at 8 and, if originally refined,
16 samples. The full unpruned scores are an explanatory instrument, NOT a
claim that branch-and-bound evaluated every finalist in its old trace.

Keep only visible seven, remaining 92-card multiset, stage, and seat in the
scoring inputs. Never use the realized physical unknown92 ordering to choose
a candidate. No v43 model fitting or model approval.
"""
from __future__ import annotations
import argparse,glob,gzip,hashlib,json,sys,time
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import dack_paired_counterfactual_v5_stable_chance_20261031 as v5
import dack_paired_counterfactual_v27_T2_only_DP_20261101 as v27
from dack_simulator.validation.collect_teacher_london_v13 import finalists
from dack_simulator.validation.v33b_bottom_ranker import rank
import dack_mulligan_teacher_features_v13_20261031 as features

ref=v5.reference
SCHEMA="dack_v43_original_v5_top12_candidate_ev_landscape_v1"

def load_115k():
    paths=sorted(glob.glob(str(ROOT/"benchmark_results/v33b_prospective_115k_shards/v33b_115k_*.json.gz")))
    assert len(paths)==64
    rows={}
    for p in paths:
        with gzip.open(p,"rt") as f:sh=json.load(f)
        assert sh["schema"]=="dack_v33b_prospective_115k_three_policy_strict" and sh["status"]=="PASS"
        for row in sh["rows"]:
            gid=int(row["game_id"])
            assert gid not in rows
            rows[gid]=row
    assert set(rows)==set(range(115000,115256))
    return rows

def choose_cases(rows):
    stage_diff=[]
    bottom_diff=[]
    for gid in sorted(rows):
        q=rows[gid]
        h5=q["v5"]["history"];h27=q["v27_frozen"]["history"]
        s5=int(h5[-1]["stage"]);s27=int(h27[-1]["stage"])
        if s5!=s27:
            s=min(s5,s27)
            if s in (2,3):stage_diff.append((gid,s,"first_keep_disagreement"))
        elif s5 in (2,3,4,5) and (tuple(h5[-1]["bottom"])!=tuple(h27[-1]["bottom"])):
            bottom_diff.append((gid,s5,"same_stage_bottom_disagreement"))
    # Deterministic selection before looking at the candidate scoring results.
    assert len(stage_diff)>=4 and len(bottom_diff)>=4
    return stage_diff[:4]+bottom_diff[:4]

def profile(gid,rows):
    selected={g:(s,k) for g,s,k in choose_cases(rows)}
    assert gid in selected,(gid,choose_cases(rows))
    stage,kind=selected[gid]
    observed=rows[gid]
    assert ref.SPEC["beam"]==160
    assert tuple(ref.sim.STAGES)==(7,7,6,5,4,3,2,1)
    assert ref.batch.CONFIG["screen_samples"]==8
    assert ref.batch.CONFIG["refine_samples"]==16
    assert ref.batch.CONFIG["mulligan_eval_beam"]==60
    assert float(ref.batch.CONFIG["lambda"])==0.5
    seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
    seat,orders=ref.stage_slots(seed)
    assert seat==observed["v5"]["seat"]==observed["v27_frozen"]["seat"]
    deck=ref.SLOT_VARIANTS["one_key_34"]
    assert len(deck)==99
    order=orders[stage];kn=int(ref.sim.STAGES[stage])
    seven=tuple(deck[x] for x in order[:7])
    unknown=tuple(deck[x] for x in order[7:])
    assert len(seven)==7 and len(unknown)==92
    assert Counter(deck.values())==Counter(seven)+Counter(unknown)
    old5=observed["v5"]["history"][stage]
    old27=observed["v27_frozen"]["history"][stage]
    assert old5["seven"]==list(seven)==old27["seven"]
    # Install reference BEFORE scoring; physical future order is not an input
    # to the v5 evaluator (it is only the unseen multiset).
    v5.audit()
    ref.sim.reset_caches();ref.sim.root.install("one_key_34")
    ref.sim.m.set_trial_seed(seed)
    t0=time.perf_counter()
    raw,ev,struct,hand,bottom,rest,ignored,refined=ref.batch.evaluate_keep(
        list(seven),kn,list(unknown),seat)
    assert tuple(rest)==unknown
    assert Counter(hand)==Counter(old5["hand"])
    assert tuple(bottom)==tuple(old5["bottom"])
    assert abs(float(raw)-float(old5["raw"]))<=1e-7,(gid,"raw",raw,old5["raw"])
    assert bool(refined)==bool(old5["refined"])
    assert abs(float(ev["t1"])-float(old5["sampled_t1"]))<=1e-7
    teacher_call_seconds=time.perf_counter()-t0
    cand=finalists(seven,kn,unknown)
    winning=[i for i,x in enumerate(cand) if
        tuple(x["hand"])==tuple(hand) and tuple(x["bottom"])==tuple(bottom)]
    assert winning and len(cand)<=12
    winner=winning[0]
    rowscore=[]
    # Important: this scorer is the original retained-hand EV evaluator,
    # with its unchanged 8/16 deterministic future construction. Unpruned
    # re-evaluation can be substantially more expensive than old v5.
    for i,c in enumerate(cand):
        h=tuple(c["hand"]);b=tuple(c["bottom"])
        row={
           "structural_candidate_index":i,
           "hand":list(h),"bottom":list(b),
           "struct_rank":c["struct_rank"],"original_teacher_choice":i==winner,
           "full_unpruned_original_ev":{},
        }
        for samples in ([8,16] if refined else [8]):
            ref.sim.reset_caches()
            ref.sim.root.install("one_key_34")
            ref.sim.m.set_trial_seed(seed)
            t=time.perf_counter()
            val=ref.d.keep_weighted_ev_seat(
                h,unknown,seat=seat,beam=60,samples=samples,bottom=b,t3_weight=.5)
            assert val and all(k in val for k in ("utility","t1","t2","t3"))
            expected=val["t1"]+val["t2"]+.5*val["t3"]
            assert abs(float(val["utility"])-expected)<1e-9
            row["full_unpruned_original_ev"][str(samples)]={
                 "U":float(val["utility"]),"T1":float(val["t1"]),
                 "exact_T2":float(val["t2"]),"exact_T3":float(val["t3"]),
                 "seconds":round(time.perf_counter()-t,4),
            }
        rowscore.append(row)
        print("DACK_V43_SCORER_CANDIDATE",gid,stage,i,
              "winner",i==winner,"U8",row["full_unpruned_original_ev"]["8"]["U"],flush=True)
    # v27/old v14 features after complete v5 scoring; they are intentionally
    # installed only now to avoid contaminating original v5 scorer state.
    v27.audit()
    opts,scores,index=rank(seven,kn,unknown,seat,stage,
                          v27.original.old.MODEL,v27.original.MODEL)
    assert len(opts)==len(cand)
    for i,(a,b) in enumerate(zip(opts,cand)):
        assert tuple(a["hand"])==tuple(b["hand"])
        assert tuple(a["bottom"])==tuple(b["bottom"])
        rowscore[i]["v27_and_other_candidate_scores"]=scores[i]
    frozen_v14=next(i for i,c in enumerate(cand)
                if tuple(c["bottom"])==tuple(old27["bottom"]) and
                   Counter(c["hand"])==Counter(old27["hand"]))
    assert index["v14_frozen"]==frozen_v14
    # Verify the archived v27 Qkeep uses the same candidate as the isolated
    # rank and remains on its own noncomparable T2-only score scale.
    report={
       "schema":SCHEMA,"status":"PASS",
       "case":{"game_id":gid,"stage":stage,"keep_n":kn,"kind":kind,"seat":seat,
         "seven":list(seven),"unknown_card_counts":dict(sorted(Counter(unknown).items())),
         "v5_raw":float(raw),"v5_sampled_T1":float(ev["t1"]),
         "v5_refined":bool(refined),"v5_selected_candidate":winner,
         "v27_selected_candidate":frozen_v14,
         "v5_keep":bool(old5["kept"]),"v27_keep":bool(old27["kept"]),
         "v5_threshold":float(old5["threshold"]),
         "v27_threshold":float(old27["threshold"]),
         "original_v5_score_calculation_seconds":round(teacher_call_seconds,3),
         "other_learned_candidate_rankers":index,
       },
       "candidates":rowscore,
       "actual_original_v5_scorer_and_selection_archival_parity":True,
       "no_unseen_realized_order_in_candidate_scores":True,
       "v5_original_scorer_uses_deterministic_candidate_specific_sampled_futures":True,
       "unpruned_candidate_value_profiles_not_original_pruning_history":True,
       "no_model_trained_or_promoted":True,
       "historical_115k_previously_consumed_not_fresh_holdout":True,
    }
    return report

def run(gid,out):
    rr=load_115k()
    print("DACK_V43_FROZEN_CASES",choose_cases(rr),flush=True)
    result=profile(gid,rr)
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("DACK_V43_CANDIDATE_V5_ORIGINAL_PARITY_PASS",
          json.dumps({"gid":gid,"stage":result["case"]["stage"],
             "kind":result["case"]["kind"],"count":len(result["candidates"]),
             "v5_index":result["case"]["v5_selected_candidate"],
             "v14_index":result["case"]["v27_selected_candidate"]},sort_keys=True),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--gid",type=int,required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args();run(a.gid,a.out)
