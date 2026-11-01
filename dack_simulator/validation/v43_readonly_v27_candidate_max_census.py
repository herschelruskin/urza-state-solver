#!/usr/bin/env python3
"""Read-only v43 v27 self-inconsistency audit, 256 archival 115k outer games.

At an archived visited London stage v27:
 - frozen v14 selector picks one candidate;
 - frozen v27 Q2 evaluator scores that one candidate;
 - compare its score to the *maximum* v27 Q2 score across the same legal
   structurally filtered v5 finalist set.
The second arm is a hypothetical MAX-Q candidate policy, NOT an approved
change or a claim of physically improved outcomes. Its Q2 model was trained
on v14-selected bottoms and can overestimate unseen bottom alternatives.
"""
from __future__ import annotations
import gzip,glob,json,sys,math
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import dack_paired_counterfactual_v27_T2_only_DP_20261101 as v27
import dack_mulligan_teacher_features_v13_20261031 as features
from dack_simulator.validation.collect_teacher_london_v13 import finalists
ref=v27.ref

def archive():
    a={}
    ps=sorted(glob.glob(str(ROOT/"benchmark_results/v33b_prospective_115k_shards/v33b_115k_*.json.gz")))
    assert len(ps)==64
    for p in ps:
        with gzip.open(p,"rt") as f:z=json.load(f)
        assert z["status"]=="PASS"
        for r in z["rows"]:
            gid=int(r["game_id"]);assert gid not in a;a[gid]=r
    assert set(a)==set(range(115000,115256))
    return a

def score(seven,unknown,seat,stage):
    keep_n=int(ref.sim.STAGES[stage])
    scored=[]
    for i,c in enumerate(finalists(seven,keep_n,unknown)):
        x=features.extract(seven,c["hand"],c["bottom"],Counter(unknown),
                           seat,keep_n,stage,c["struct_rank"],i)
        v14vote=features.score_head(v27.original.old.MODEL,"choice_trees",x)
        q2=v27.original.estimator.predict(v27.original.MODEL,x)
        scored.append(dict(idx=i,hand=c["hand"],bottom=c["bottom"],
                           Q2=q2,v14_vote=v14vote))
    v14=max(scored,key=lambda v:(v["v14_vote"],-v["idx"]))
    best=max(scored,key=lambda v:(v["Q2"],-v["idx"]))
    return scored,v14,best

def run(out):
    assert v27.audit()["status"]=="PASS"
    deck=ref.SLOT_VARIANTS["one_key_34"]
    allrows=archive()
    outrows=[];cnt=Counter()
    for gid,row in sorted(allrows.items()):
        seat=int(row["v27_frozen"]["seat"])
        seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
        ss,orders=ref.stage_slots(seed)
        assert ss==seat
        h5=row["v5"]["history"];h27=row["v27_frozen"]["history"]
        s5=int(h5[-1]["stage"]);s27=int(h27[-1]["stage"])
        # first shared stage when actual keep differs; same-stage final
        # choice comparison is separate.
        s=min(s5,s27)
        known=h27[s]
        assert known["seven_slots"]==list(orders[s][:7])
        seven=tuple(deck[t] for t in orders[s][:7])
        unknown=tuple(deck[t] for t in orders[s][7:])
        assert seven==tuple(known["seven"])
        candidates,selection,best=score(seven,unknown,seat,s)
        cutoff=float(v27.original.DP["seat_continuations"][str(seat)]["thresholds_by_london_stage"][s])
        assert abs(float(known["raw"])-float(selection["Q2"]))<=1e-6,(
             "v27 Qkeep candidate parity",gid,s,known["raw"],selection["Q2"])
        assert abs(float(known["threshold"])-cutoff)<=1e-6
        assert Counter(selection["hand"])==Counter(known["hand"])
        assert tuple(selection["bottom"])==tuple(known["bottom"])
        v27keep=bool(known["kept"])
        assert v27keep==(s==7 or selection["Q2"]>=cutoff)
        hypothetical_keep=bool(s==7 or best["Q2"]>=cutoff)
        assert not (v27keep and not hypothetical_keep)
        type_=("different_stopping_stage" if s5!=s27 else
               "same_stopping_stage")
        record={
          "gid":gid,"stage":s,"seat":seat,"type":type_,
          "original_v5_keep":bool(h5[s]["kept"]),
          "original_v27_keep":v27keep,
          "hypothetical_best_Q2_keep":hypothetical_keep,
          "v27_threshold":cutoff,"original_v27_bottom_index":selection["idx"],
          "best_Q2_bottom_index":best["idx"],
          "original_v27_Q2":selection["Q2"],
          "best_Q2":best["Q2"],
          "best_minus_selected_Q2":best["Q2"]-selection["Q2"],
          "v5_archived_bottom_index":next(
            (c["idx"] for c in candidates if
             c["bottom"]==h5[s]["bottom"] and Counter(c["hand"])==Counter(h5[s]["hand"])),
             None),
          "candidate_count":len(candidates),
        }
        assert record["v5_archived_bottom_index"] is not None
        outrows.append(record)
        cnt["N"]=len(outrows)
        cnt["Q2_max_differs_from_v14_choice"]+=int(best["idx"]!=selection["idx"])
        cnt["hypothetical_maxQ2_changes_mull_to_keep"]+=int(hypothetical_keep and not v27keep)
        cnt["different_stopping_stage"]+=int(s5!=s27)
        cnt["same_stopping_stage"]+=int(s5==s27)
        cnt["v5_keeps_v27_mulls"]+=int(s5!=s27 and bool(h5[s]["kept"]))
        cnt["v5_keeps_v27_mulls_and_maxQ2_would_keep"]+=int(
             s5!=s27 and bool(h5[s]["kept"]) and hypothetical_keep)
        cnt["v5_mulls_v27_keeps"]+=int(s5!=s27 and not bool(h5[s]["kept"]))
        cnt["v5_mulls_v27_keeps_and_maxQ2_keeps"]+=int(
             s5!=s27 and not bool(h5[s]["kept"]) and hypothetical_keep)
        cnt["different_stopping_stage_bottom_possible"]+=int(s5!=s27 and s>=2)
        cnt["different_stage_ge2_v5_keeps_v27_mulls"]+=int(
             s5!=s27 and s>=2 and bool(h5[s]["kept"]))
        cnt["different_stage_ge2_v5_keeps_v27_mulls_and_maxQ2_keep"]+=int(
             s5!=s27 and s>=2 and bool(h5[s]["kept"]) and hypothetical_keep)
    assert len(outrows)==256 and cnt["different_stopping_stage"]==100
    assert cnt["v5_keeps_v27_mulls"]==39
    assert cnt["v5_mulls_v27_keeps"]==61
    assert all(r["best_minus_selected_Q2"]>=-1e-10 for r in outrows)
    report={
     "schema":"dack_v43_v27_fixed_bottom_then_keep_vs_internal_maxQ2_readonly_v1",
     "status":"PASS","all_256_physical_outer_games":256,
     "original_v27_Q2_and_decision_parity":True,
     "all_v5_bottom_candidates_in_original_legal_top12":True,
     "no_original_v5_gameplay_or_new_model":True,
     "no_outcome_labels_used_for_selection":True,
     "not_a_physical_gameplay_comparison":True,
     "old_115k_test_cohort_ALREADY_inspected":True,
     "warning":"max over v27 Qkeep is heavily OOD because Qkeep trained using the frozen v14 bottom selector; do not assume its max is calibrated or improves win rate",
     "counts":dict(cnt),"rows":outrows,
    }
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print("DACK_V43_V27_SELF_CONSISTENCY_CENSUS_PASS",json.dumps(dict(cnt),sort_keys=True),flush=True)

if __name__=="__main__":
    run(ROOT/"benchmark_results/v43_v27_candidate_maxQ2_readonly_115k_N256.json")
