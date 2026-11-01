#!/usr/bin/env python3
"""Fit conditional expected keep utility from actual counterfactual London futures.

Each *physical* outer game contributes all 8 London stages, regardless of
whether frozen v14 would keep or reject at any stage. Four independently
shuffled library futures per stage yield a noisy empirical U for that one
candidate hand. Train and validation games never overlap. No rollout
future order, label, or teacher oracle decision is an input feature.

This regression supplies a proposed value for KEEP, NOT a keep/mull
decision by itself: continuations are derived via offline London DP.
"""
from __future__ import annotations
import argparse,gzip,json,hashlib,random,sys,math
from collections import defaultdict,Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import dack_mulligan_teacher_features_v13_20261031 as features
import dack_mulligan_keep_value_v22_20261101 as runtime

def read(paths,split):
    states=[];ids=set();sha=None
    for path in paths:
        with gzip.open(path,"rt") as fp:
            m=json.loads(next(fp));rows=[json.loads(s) for s in fp]
        if m["schema"]!="dack_v21_counterfactual_london_keep_values":
            raise ValueError("wrong keep dataset")
        if m["split"]!=split or m["games"]!=8 or m["draws_per_stage"]!=4:
            raise ValueError("wrong split or rollout protocol")
        if sha is None:sha=m["source_student_model_sha256"]
        if sha!=m["source_student_model_sha256"]:
            raise ValueError("mixed student-source data")
        if len(rows)!=256:
            raise ValueError("not 8 games x 8 stages x 4 actual futures")
        grouped=defaultdict(list)
        for x in rows:
            if x["schema"]!="dack_v21_counterfactual_london_keep_values":
                raise ValueError("row schema")
            grouped[(x["game_id"],x["stage"])].append(x)
        newids=set()
        for (gid,stage),rows4 in grouped.items():
            newids.add(gid)
            rows4.sort(key=lambda r:r["future_index"])
            if [r["future_index"] for r in rows4]!=[0,1,2,3]:
                raise ValueError("missing independent true future")
            base=rows4[0]
            for r in rows4[1:]:
                if (r["hand"]!=base["hand"] or r["bottom"]!=base["bottom"] or
                    r["seven"]!=base["seven"] or r["seat"]!=base["seat"] or
                    r["student_would_keep"]!=base["student_would_keep"]):
                    raise ValueError("future leaked into student selection")
            expected_n=[7,7,6,5,4,3,2,1][stage]
            if base["keep_n"]!=expected_n or len(base["hand"])!=expected_n:
                raise ValueError("bad London stage")
            u=sum(1. if x["label_turn"] in (1,2) else .5 if x["label_turn"]==3 else 0.
                  for x in rows4)/4
            counts=Counter(r["label_turn"] for r in rows4)
            x=features.extract(base["seven"],base["hand"],base["bottom"],
                base["unknown_counts"],base["seat"],base["keep_n"],stage,
                base["candidate_struct_rank"],base["candidate_index"])
            states.append({
                "game_id":gid,"stage":stage,"seat":base["seat"],
                "keep_n":base["keep_n"],"input":x,"real_u":u,
                "student_would_keep":base["student_would_keep"],
                "real_T1":counts[1]/4,
                "real_by_T2":(counts[1]+counts[2])/4,
                "real_by_T3":(counts[1]+counts[2]+counts[3])/4,
            })
        if len(newids)!=8:raise ValueError("wrong game group count per file")
        if ids&newids:raise ValueError("same game in multiple files")
        ids.update(newids)
    if not states:raise ValueError("empty counterfactual data")
    if any(sum(x["game_id"]==gid for x in states)!=8 for gid in ids):
        raise ValueError("game must contribute all eight stages")
    if split=="train" and ids!=set(range(82000,82064)):
        raise ValueError("incomplete 64 game train split")
    if split=="validation" and ids!=set(range(83000,83016)):
        raise ValueError("incomplete 16 game validation split")
    return states,ids,sha

def evaluate(rows,model,stage_baselines):
    grouped=defaultdict(list)
    n=len(rows)
    predictions=[]
    for r in rows:
        pred=runtime.predict(model,r["input"])
        prior=stage_baselines[str(r["stage"])]
        predictions.append((r,pred,prior))
        grouped[r["game_id"]].append((r,pred,prior))
    def metric(predindex):
        mse=sum((v[predindex]-v[0]["real_u"])**2 for v in predictions)/n
        mae=sum(abs(v[predindex]-v[0]["real_u"]) for v in predictions)/n
        return {"MSE":mse,"MAE":mae}
    forest=metric(1);baseline=metric(2)
    by_stage={}
    for stage in range(8):
        vals=[v for v in predictions if v[0]["stage"]==stage]
        by_stage[str(stage)]={
            "keep_n":[7,7,6,5,4,3,2,1][stage],
            "n_independent_games":len(vals),
            "observed_mean_u":sum(v[0]["real_u"] for v in vals)/len(vals),
            "predicted_mean_u":sum(v[1] for v in vals)/len(vals),
            "baseline_train_stage_mean":stage_baselines[str(stage)],
            "student_classifier_keep_fraction":sum(v[0]["student_would_keep"] for v in vals)/len(vals),
            "rejected_stages_with_observed_T2_positive":sum(
                (not v[0]["student_would_keep"]) and v[0]["real_by_T2"]>0 for v in vals)
        }
    diffs={gid:sum((pred-r["real_u"])**2-(base-r["real_u"])**2
                   for r,pred,base in values)/len(values)
           for gid,values in grouped.items()}
    ids=sorted(diffs)
    rng=random.Random(224466)
    boot=[]
    for _ in range(1000):
        boot.append(sum(diffs[ids[rng.randrange(len(ids))]] for j in ids)/len(ids))
    boot.sort()
    return {
        "independent_outer_groups":len(ids),
        "stage_state_groups":n,
        "nonlinear_forest":forest,
        "stage_specific_constant_prior":baseline,
        "forest_minus_prior_MSE":forest["MSE"]-baseline["MSE"],
        "group_bootstrap_95ci_forest_minus_prior_MSE":[boot[25],boot[974]],
        "stage_diagnostics":by_stage,
        "rejected_stage_fraction":sum(not x[0]["student_would_keep"] for x in predictions)/n,
    }

def train(trainpaths,valpaths,modelpath,reportpath):
    import numpy as np
    from sklearn.ensemble import RandomForestRegressor
    tr,tids,sha=read(trainpaths,"train")
    va,vids,vsha=read(valpaths,"validation")
    if tids&vids or sha!=vsha:raise AssertionError("physical source or group leak")
    if len(tr)!=512 or len(va)!=128:raise AssertionError("wrong stage counts")
    X=np.asarray([x["input"] for x in tr],dtype=float)
    Y=np.asarray([x["real_u"] for x in tr],dtype=float)
    rf=RandomForestRegressor(
        n_estimators=128,max_depth=8,min_samples_leaf=4,
        max_features=.65,random_state=222222,n_jobs=2)
    rf.fit(X,Y)
    baseline={
        str(stage):sum(x["real_u"] for x in tr if x["stage"]==stage)/64.
        for stage in range(8)
    }
    model={
        "schema":runtime.SCHEMA,
        "feature_hash":features.feature_hash(),
        "feature_count":len(features.FEATURES),
        "source_student_model_sha256":sha,
        "trained_on_all_eight_stages_including_rejected":True,
        "policy_kept_only_bias_removed_at_training":True,
        "trained_for_v14_128_candidate_bottom_selection":True,
        "training_games":64,"validation_games":16,
        "training_states":512,"validation_states":128,
        "true_gameplay_futures_per_state":4,
        "prior_by_stage_from_train":baseline,
        "utility":"P(T1 exact)+P(T2 exact)+0.5 P(T3 exact)",
        "deployed_policy_approved":False,
        "diagnostic_only":True,
        "trees":[{
            "left":t.tree_.children_left.tolist(),
            "right":t.tree_.children_right.tolist(),
            "feature":t.tree_.feature.tolist(),
            "threshold":t.tree_.threshold.tolist(),
            "value":t.tree_.value[:,0,0].tolist()
        } for t in rf.estimators_
        ],
    }
    for rec in va[:min(len(va),16)]:
        a=runtime.predict(model,rec["input"])
        b=float(rf.predict(np.asarray([rec["input"]]))[0])
        if abs(a-max(0.,min(1.,b)))>1e-9:
            raise AssertionError("pure Python exported score parity failure")
    trscore=evaluate(tr,model,baseline)
    valscore=evaluate(va,model,baseline)
    report={
        "schema":"dack_v22_all_london_keep_value_regression_diagnostic",
        "status":"PASS",
        "training_game_groups":64,"validation_game_groups":16,
        "training_states":512,"validation_states":128,
        "includes_first_free_seven":True,
        "rejected_hands_are_labeled_directly":True,
        "no_future_order_in_model_inputs":True,
        "model_approved":False,
        "training_metrics_not_holdout":trscore,
        "independent_validation_metrics":valscore,
        "warning":"Only four actual futures per state and 16 validation games. All values are conditional on v14-128 chosen bottoms, not universally calibrated for every legal hand or multiplayer win rate."
    }
    output=Path(modelpath);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(model,sort_keys=True,separators=(",",":"))+"\n")
    path=Path(reportpath);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print("V22_ALL_STAGE_REAL_KEEP_VALUE_FIT_PASS",json.dumps({
        "training_games":64,"validation_games":16,
        "validation":valscore,"model_approved":False},flush=True))
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--train",nargs="+",required=True)
    p.add_argument("--validation",nargs="+",required=True)
    p.add_argument("--model",default="models/dack_v22_real_all_stage_keep_value_EXPERIMENTAL.json")
    p.add_argument("--report",default="benchmark_results/v22_real_keep_value_validation.json")
    a=p.parse_args()
    train(a.train,a.validation,a.model,a.report)
