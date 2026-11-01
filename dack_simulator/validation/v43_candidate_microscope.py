#!/usr/bin/env python3
"""v43 exact original-v5 candidate-value microscope, research-only.

Profiles original structural top-12 for a *fixed small set of previously
inspected* v5/v27 disagreement sevens. Native teacher evaluator is first
run with archived exact seat/stage/99-card opening slot seed and compared to
the archived winner, raw value, cutoff and refinement flag. Then every
candidate's actual original 8-sample beam60 utility is computed (and a
separate 16-sample view), without using the externally realized future
card order. The v14/v27 candidate scores are computed on identical options.

This is NOT new unbiased validation, student training or policy promotion.
A candidate table of original v5 scores does not prove true out-of-sample
expected success. Later experiments can force physical trials for competing
candidates after these predeclared labels are frozen.
"""
from __future__ import annotations
import argparse, gzip, glob, json, hashlib, math, sys, time
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import dack_paired_counterfactual_v5_stable_chance_20261031 as teacher
from dack_simulator.validation.collect_teacher_london_v13 import finalists
import dack_mulligan_teacher_features_v13_20261031 as feats

ref=teacher.reference
SCHEMA="dack_v43_real_original_v5_top12_candidate_profile_v1"
SAMPLE={
 115003:2, 115004:2, 115119:2, 115153:2,
 115066:2, 115086:2, 115005:0, 115025:0,
}
def archives():
    paths=sorted(glob.glob(str(ROOT/"benchmark_results/v33b_prospective_115k_shards/v33b_115k_*.json.gz")))
    assert len(paths)==64
    rows={}
    for p in paths:
        with gzip.open(p,"rt") as f:z=json.load(f)
        assert z["status"]=="PASS" and z["schema"]=="dack_v33b_prospective_115k_three_policy_strict"
        for r in z["rows"]:
            gid=int(r["game_id"])
            assert gid not in rows
            if gid in SAMPLE:rows[gid]=r
    assert set(rows)==set(SAMPLE)
    return rows

def ev_score(h,b,rest,seat,samples):
    v=ref.d.keep_weighted_ev_seat(
          tuple(h),tuple(rest),seat=seat,beam=60,
          samples=samples,bottom=tuple(b),t3_weight=.5)
    assert all(0<=float(v[k])<=1 for k in ("t1","t2","t3","le2"))
    assert abs(v["utility"]-(v["le2"]+.5*v["t3"]))<1e-9
    return {k:float(v[k]) for k in ("utility","t1","t2","t3","le2","le3")}

def run(gid,out):
    if gid not in SAMPLE:raise ValueError("predeclared source only")
    teacher.audit()
    row=archives()[gid]
    stage=SAMPLE[gid]
    archived=row["v5"]["history"][stage]
    v27=row["v27_frozen"]["history"][stage]
    assert archived["stage"]==v27["stage"]==stage
    assert archived["seven"]==v27["seven"]
    kn=ref.sim.STAGES[stage]
    seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
    seat,stages=ref.stage_slots(seed)
    assert seat==row["v5"]["seat"]==row["v27_frozen"]["seat"]
    order=stages[stage]
    deck=ref.SLOT_VARIANTS["one_key_34"]
    seven=[deck[s] for s in order[:7]]
    rest=[deck[s] for s in order[7:]]
    assert seven==archived["seven"] and list(order[:7])==archived["seven_slots"]
    assert len(rest)==92 and Counter(seven)+Counter(rest)==Counter(deck.values())
    assert len(archived["hand"])==kn
    original = list(archived["hand"]),list(archived["bottom"])
    ref.sim.reset_caches()
    ref.sim.root.install("one_key_34")
    ref.sim.m.set_trial_seed(seed)
    t0=time.monotonic()
    raw,ev,struct,hand,bottom,unknown,ignored,refined=ref.batch.evaluate_keep(
       seven,kn,rest,seat)
    assert Counter(hand)==Counter(archived["hand"])
    assert tuple(bottom)==tuple(archived["bottom"])
    assert abs(float(raw)-float(archived["raw"]))<1e-7
    assert bool(refined)==bool(archived["refined"])
    assert tuple(unknown)==tuple(rest)
    assert abs(float(ev["t1"])-float(archived["sampled_t1"]))<1e-7
    # From this point, using only features available to a real policy.
    options=finalists(seven,kn,rest)
    assert len(options)>0
    teacher_index=next((i for i,c in enumerate(options)
       if Counter(c["hand"])==Counter(hand) and
          tuple(c["bottom"])==tuple(bottom)),None)
    assert teacher_index is not None
    assert len(options)==(1 if kn==7 else min(12,math.comb(7,7-kn)))
    # Evaluate full 8 vs full 16 separately; branchbound can have pruned
    # losing candidates, so don't claim unexecuted teacher profiles are logs.
    profiles=[]
    for i,c in enumerate(options):
        q8=ev_score(c["hand"],c["bottom"],rest,seat,8)
        q16=ev_score(c["hand"],c["bottom"],rest,seat,16)
        profiles.append({
          "index":i,"struct_rank":c["struct_rank"],
          "hand":c["hand"],"bottom":c["bottom"],
          "original_sampler_beam60_8":q8,
          "original_sampler_beam60_16":q16,
        })
    rank8=sorted(range(len(profiles)),key=lambda i:(
      profiles[i]["original_sampler_beam60_8"]["utility"],
      tuple(profiles[i]["struct_rank"]),-i),reverse=True)
    rank16=sorted(range(len(profiles)),key=lambda i:(
      profiles[i]["original_sampler_beam60_16"]["utility"],
      tuple(profiles[i]["struct_rank"]),-i),reverse=True)
    # We DO NOT enforce simple full8/full16 top1 == original bounded winner
    # because batch's refinement near threshold may have a different scope.
    teacher_raw8=profiles[teacher_index]["original_sampler_beam60_8"]["utility"]
    teacher_raw16=profiles[teacher_index]["original_sampler_beam60_16"]["utility"]
    # Later model deployment has frozen original v14 bottom chooser and
    # T2-only real-outcome forest; only read those predicted rankings after
    # original teacher values and archived parity have been verified.
    import dack_paired_counterfactual_v27_T2_only_DP_20261101 as new
    new.audit()
    import dack_paired_counterfactual_v22_all_stage_real_keep_DP_20261101 as ctl
    from dack_simulator.validation.v33b_bottom_ranker import rank as ranker
    opts,vals,methods=ranker(
         tuple(seven),kn,tuple(sorted(rest)),seat,stage,
         ctl.old.MODEL,ctl.MODEL)
    assert len(opts)==len(profiles)==len(vals)
    for i,(a,b) in enumerate(zip(opts,profiles)):
        assert Counter(a["hand"])==Counter(b["hand"])
        assert tuple(a["bottom"])==tuple(b["bottom"])
        b["v14_teacher_choice_vote"]=float(vals[i]["v14_vote"])
        b["v27_pred_T2_keep_value"]=float(vals[i]["Qkeep_T2"])
        b["v18_pred_U"]=vals[i]["v18_U"]
        b["analytic_T2_index"]=float(vals[i]["analytic_T2"])
    original_v27_idx=next(i for i,c in enumerate(profiles)
       if Counter(c["hand"])==Counter(v27["hand"])
       and tuple(c["bottom"])==tuple(v27["bottom"]))
    assert methods["v14_frozen"]==original_v27_idx
    v27_value=float(v27["raw"])
    assert abs(v27_value-vals[original_v27_idx]["Qkeep_T2"])<1e-6
    output={
     "schema":SCHEMA,"status":"PASS","game_id":gid,"stage":stage,
     "seat":seat,"keep_n":kn,"opening_seven":seven,
     "hidden_92_multiset_sha256":hashlib.sha256(json.dumps(
         sorted(Counter(rest).items())).encode()).hexdigest(),
     "v5_archived_winner_and_raw_score_reproduced_exactly":True,
     "v5_lookahead_evaluated_only_on_opening_seven_not_hindsight":True,
     "original_physical_future_order_not_used_in_candidate_scoring":True,
     "source_historical_115k_previously_inspected":True,
     "no_model_training_or_promotion":True,
     "v5_kept":bool(archived["kept"]),
     "v27_kept":bool(v27["kept"]),
     "v5_real_selected_index":teacher_index,
     "v27_real_selected_index":original_v27_idx,
     "v5_raw":float(raw),"v5_threshold":float(archived["threshold"]),
     "v5_refined":bool(refined),
     "v5_winner_8_full_score":teacher_raw8,
     "v5_winner_16_full_score":teacher_raw16,
     "v5_full_8_utility_argmax":rank8[0],
     "v5_full_16_utility_argmax":rank16[0],
     "v27_stage_raw":v27_value,
     "v27_stage_threshold":float(v27["threshold"]),
     "model_candidate_methods":methods,
     "stage_profile_evaluation_seconds":round(time.monotonic()-t0,3),
     "candidate_table":profiles,
     "warning":"8/16 small deterministic teacher sampler and max-over-candidates are noisy. Do not interpret teacher scores or predicted q27 values as calibrated or comparable; independent physical K futures required.",
    }
    dest=Path(out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(output,indent=2,sort_keys=True)+"\n")
    print("DACK_V43_EXACT_V5_CANDIDATE_MICROSCOPE_PASS",
      json.dumps({"gid":gid,"stage":stage,"teacher_index":teacher_index,
         "v27_index":original_v27_idx,"v5_keep":archived["kept"],
         "v27_keep":v27["kept"],"teacher_raw":raw,
         "teacher_winner_ev8":teacher_raw8,"teacher_winner_ev16":teacher_raw16,
         "rank8":rank8[:4],"rank16":rank16[:4],
         "seconds":output["stage_profile_evaluation_seconds"]},sort_keys=True),
      flush=True)

if __name__=="__main__":
    a=argparse.ArgumentParser()
    a.add_argument("--gid",type=int,required=True)
    a.add_argument("--out",required=True)
    args=a.parse_args()
    run(args.gid,args.out)
