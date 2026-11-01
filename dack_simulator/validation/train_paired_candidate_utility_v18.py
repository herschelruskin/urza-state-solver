#!/usr/bin/env python3
"""Train/validate expected T1/T2/T3 utility for *paired bottom choices*.

Training samples: v5-visited real physical hands, >=3 <=6 cards after
bottoming; each legal structural-top-three option and possibly v5's
additional preferred choice receives 8 independent identical future
shuffles and seed-matched dice across choices. Only *training split*
touches supervised fit. Validation labels are never used for feature
selection, thresholds or model fitting. Teacher choices are explicitly
NOT available to an inference policy.

Metrics measure expected utility/regret on COMMON RANDOM validation
rollouts, not a statistically proven full-game win rate.
"""
from __future__ import annotations
from collections import Counter,defaultdict
import argparse,gzip,hashlib,json,math,random,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import dack_mulligan_teacher_features_v13_20261031 as feats
import dack_mulligan_candidate_value_v18_20261101 as runtime
import dack_mulligan_outcome_forest_v16_20261031 as oldprob

def read(paths,split):
    records=[];groups=set();ineligible=[]
    for path in paths:
        with gzip.open(path,"rt",encoding="utf8") as f:
            meta=json.loads(next(f));rows=[json.loads(s) for s in f]
        if meta.get("schema")!="dack_v18_paired_candidate_values":
            raise ValueError("not an actual paired-candidate label shard")
        if meta.get("split")!=split or meta["status"]!="PASS":
            raise ValueError("wrong data split")
        if meta["paired_draws_per_option"]!=8 or meta["candidate_limit_structural_first_plus_teacher"]!=3:
            raise ValueError("inconsistent candidate rollout protocol")
        ineligible.extend(meta["ineligible_game_ids"])
        for row in rows:
            gid=int(row["source_teacher_game_id"])
            if gid in groups:raise ValueError("duplicate game group")
            if not (60000<=gid<60144 if split=="train" else 61000<=gid<61040):
                raise ValueError("unexpected group ID")
            if row["source_teacher_split"]!=split:
                raise ValueError("row split inconsistent")
            if row["protocol"]!="dack_v18_common_random_number_candidate_values":
                raise ValueError("row generated with other lottery")
            if not row["future_order_shared_across_candidates"]:
                raise ValueError("candidate outcomes not paired")
            if row["hidden_future_order_never_saved"] is not True:
                raise ValueError("oracle future exposed")
            if not 3<=int(row["keep_n"])<=6:
                raise ValueError("outside candidate bottoming regime")
            if len(row["candidate_indices"])!=len(row["candidates"]):
                raise ValueError("missing candidate")
            indices=[q["candidate_index"] for q in row["candidates"]]
            if indices!=row["candidate_indices"] or 0 not in indices:
                raise ValueError("candidates index order inconsistent")
            if int(row["teacher_chosen_index"]) not in indices:
                raise ValueError("teacher option absent")
            if any(len(q["outcomes"])!=8 for q in row["candidates"]):
                raise ValueError("nonuniform physical future count")
            groups.add(gid);records.append(row)
    if not records or groups & set(ineligible):
        raise ValueError("missing or contaminated candidate groups")
    return records,groups

def convert(row):
    from collections import Counter
    rest=row["unknown_counts"]
    seven=row["seven"]
    o=[]
    for candidate in row["candidates"]:
        index=int(candidate["candidate_index"])
        x=feats.extract(seven,candidate["hand"],candidate["bottom"],rest,
                        row["seat"],row["keep_n"],row["stage"],
                        candidate["struct_rank"],index)
        outcomes=candidate["outcomes"]
        utility=sum(1. if t in (1,2) else .5 if t==3 else 0. for t in outcomes)/len(outcomes)
        if abs(utility-candidate["empirical_U"])>1e-9:
            raise ValueError("stored utility mismatch")
        o.append({"index":index,"features":x,"real_u":utility,
                  "is_v5":bool(candidate["teacher_selected"]),
                  "outcomes":outcomes})
    if not o or o[0]["index"]!=0:
        raise ValueError("no structural baseline")
    return o

def evaluate(rows,model,prior_model=None):
    groups=[]
    for row in rows:
        choices=convert(row)
        structural=choices[0]
        top3=[q for q in choices if q["index"]<3]
        teacher=[q for q in choices if q["is_v5"]]
        if len(teacher)!=1:raise ValueError("teacher choice not unique")
        v5=teacher[0]
        scores={q["index"]:runtime.predict(model,q["features"]) for q in choices}
        student=max(top3,key=lambda q:(scores[q["index"]],-q["index"]))
        # v16 is trained ONLY on v5-kept outcomes; deliberately include as
        # an off-distribution diagnostic, never assume it is calibrated.
        if prior_model is not None:
            oldscores={
                q["index"]:oldprob.deployment_summary(oldprob.predict(prior_model,q["features"]))["utility_T2_plus_half_T3"]
                for q in top3
            }
            old=max(top3,key=lambda q:(oldscores[q["index"]],-q["index"]))
        else:old=None
        oracle=max(top3,key=lambda q:(q["real_u"],-q["index"]))
        groups.append({
            "game_id":row["source_teacher_game_id"],
            "stage":row["stage"],
            "candidate_count":len(choices),
            "v5_only_candidate_outside_top3":bool(v5["index"]>=3),
            "structural_first_real_u":structural["real_u"],
            "v5_real_u":v5["real_u"],
            "student_real_u":student["real_u"],
            "student_predicted_u":scores[student["index"]],
            "best_top3_real_u":oracle["real_u"],
            "oracle_top3_index":oracle["index"],
            "student_index":student["index"],
            "v5_index":v5["index"],
            "student_T2_real":sum(t in (1,2) for t in student["outcomes"])/8,
            "structural_T2_real":sum(t in (1,2) for t in structural["outcomes"])/8,
            "v5_T2_real":sum(t in (1,2) for t in v5["outcomes"])/8,
            "student_minus_structural_real_u":student["real_u"]-structural["real_u"],
            "old_v16_real_u":None if old is None else old["real_u"],
            "old_v16_index":None if old is None else old["index"]
        })
    n=len(groups)
    def avg(k):return sum(r[k] for r in groups)/n
    stats={
        "independent_groups":n,
        "mean_utility_model_top3":avg("student_real_u"),
        "mean_utility_structural_first":avg("structural_first_real_u"),
        "mean_utility_v5_with_teacher_choice":avg("v5_real_u"),
        "mean_utility_empirical_best_top3_noisy_oracle":avg("best_top3_real_u"),
        "regret_student_vs_noisy_best_top3":avg("best_top3_real_u")-avg("student_real_u"),
        "student_minus_structural_mean_utility":avg("student_minus_structural_real_u"),
        "fraction_student_changes_structural_first":sum(r["student_index"]!=0 for r in groups)/n,
        "fraction_v5_outside_visible_top3":sum(r["v5_only_candidate_outside_top3"] for r in groups)/n,
        "mean_actual_T2_model_top3":avg("student_T2_real"),
        "mean_actual_T2_structural":avg("structural_T2_real"),
        "mean_actual_T2_v5":avg("v5_T2_real"),
    }
    if prior_model:
        stats["mean_utility_existing_v16_out_of_distribution"] = avg("old_v16_real_u")
    # Confidence by independent stage group; all candidate outcomes share
    # hidden order and seed. Student/structural differences use paired U.
    diffs=[r["student_minus_structural_real_u"] for r in groups]
    rng=random.Random(180018)
    boot=[]
    for _ in range(1000):
        boot.append(sum(diffs[rng.randrange(n)] for j in range(n))/n)
    boot.sort()
    stats["group_bootstrap_95ci_student_minus_structural"]=[
        boot[int(.025*len(boot))],boot[int(.975*len(boot))-1]]
    return stats,groups

def train(trainpaths,valpaths,modelpath,reportpath):
    from sklearn.ensemble import RandomForestRegressor
    import numpy as np
    tr,tgroups=read(trainpaths,"train")
    va,vgroups=read(valpaths,"validation")
    if tgroups & vgroups:raise ValueError("game group overlap")
    if len(tgroups)<40 or len(vgroups)<12:
        raise ValueError("insufficient independent candidate decision groups")
    X=[];Y=[];W=[]
    for row in tr:
        candidates=convert(row)
        for c in candidates:
            X.append(c["features"]);Y.append(c["real_u"])
            W.append(1./len(candidates))
    rf=RandomForestRegressor(
        n_estimators=128,max_depth=7,min_samples_leaf=4,
        max_features=.65,bootstrap=True,random_state=181818,n_jobs=2)
    rf.fit(np.asarray(X,dtype=float),np.asarray(Y,dtype=float),
           sample_weight=np.asarray(W,dtype=float))
    model={
        "schema":runtime.SCHEMA,
        "feature_hash":runtime.feature_hash(),
        "feature_count":len(feats.FEATURES),
        "training_protocol":"real_beam160_8_paired_futures_per_candidate",
        "source_v5_stage_sampling":True,
        "training_groups":len(tgroups),
        "training_candidate_options":len(X),
        "training_draws_per_candidate":8,
        "validation_groups":len(vgroups),
        "teacher_only_candidate_is_never_inference_visible":True,
        "selection_uses_structural_first_three_only":True,
        "utility":"P(T1 exact)+P(T2 exact)+0.5 P(T3 exact)",
        "uncalibrated_for_unvisited_policy_states":True,
        "deployed_policy_approved":False,
        "diagnostic_only":True,
        "trees":[{
            "left":e.tree_.children_left.tolist(),
            "right":e.tree_.children_right.tolist(),
            "feature":e.tree_.feature.tolist(),
            "threshold":e.tree_.threshold.tolist(),
            "value":e.tree_.value[:,0,0].tolist()
        } for e in rf.estimators_],
    }
    for r in va[:min(len(va),7)]:
        for c in convert(r):
            a=runtime.predict(model,c["features"])
            b=float(rf.predict(np.asarray([c["features"]]))[0])
            if abs(a-max(0.,min(1.,b)))>1e-9:
                raise AssertionError(("forest export parity error",a,b))
    oldpath=Path("models/dack_v16_conditional_outcomes_EXPERIMENTAL.json")
    prior=json.loads(oldpath.read_text()) if oldpath.exists() else None
    train_metrics,_=evaluate(tr,model)
    val_metrics,details=evaluate(va,model,prior)
    report={
        "schema":"dack_v18_candidate_value_forest_research_validation",
        "status":"PASS",
        "train_independent_groups":len(tgroups),
        "validation_independent_groups":len(vgroups),
        "train_candidate_options":len(X),
        "model_approved":False,
        "metric_is_paired_value_not_correct_v5_index":True,
        "selected_options_do_not_use_v5_teacher_index":True,
        "training_metrics_not_holdout":train_metrics,
        "separate_validation_metrics":val_metrics,
        "validation_group_details":details,
        "limitations":[
            "Only v5-visited London stages with 3..6 keep cards sampled.",
            "Eight matched real futures per candidate yield noisy empirical values.",
            "Teacher candidate outside top3 used as offline extra label only.",
            "Empirical-best utility is an optimistic noisy oracle, not achievable goldfish expectation.",
            "Validation differences are not full-policy wins or evidence of noninferiority.",
        ],
    }
    a=Path(modelpath);a.parent.mkdir(parents=True,exist_ok=True)
    a.write_text(json.dumps(model,sort_keys=True,separators=(",",":"))+"\n")
    b=Path(reportpath);b.parent.mkdir(parents=True,exist_ok=True)
    b.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print("V18_CANDIDATE_UTILITY_MODEL_PASS",json.dumps({
        "groups_train":len(tgroups),"groups_validation":len(vgroups),
        "training_options":len(X),
        "training_metrics":train_metrics,
        "validation_metrics":val_metrics,
        "model_approved":False
    },sort_keys=True),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--train",nargs="+",required=True)
    p.add_argument("--validation",nargs="+",required=True)
    p.add_argument("--model",default="models/dack_v18_paired_candidate_utility_EXPERIMENTAL.json")
    p.add_argument("--report",default="benchmark_results/v18_paired_candidate_utility_validation.json")
    a=p.parse_args()
    train(a.train,a.validation,a.model,a.report)
