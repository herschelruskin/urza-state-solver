#!/usr/bin/env python3
"""Train a lightweight, calibrated 4-class London outcome model offline.

Requires numpy, scipy, scikit-learn for TRAINING ONLY, not for inference.
Consumes independent game-id bands for train and calibration. All different
bottom choices and rollout labels from the same game ID stay in one band.
Evaluation must use a THIRD untouched set of independent game seeds.

Class 0: no deployment by T3; 1: T1; 2: T2; 3: T3 (exact event times).
Logistic regression is an interpretable low-capacity baseline, not a
promise that interaction-heavy Magic cards can be modeled linearly.

Multiclass temperature scaling uses INDEPENDENT calibration labels.
Brier and log loss are reported for every set, but only untouched
policy-level gameplay can determine whether the London policy is useful.
"""
from __future__ import annotations
import argparse
import gzip
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))

import dack_mulligan_learned_features_v8_20261031 as feat

def read_rows(paths, expected_split):
    rows=[];gid_seen=set();metas=[]
    for path in paths:
        with gzip.open(path,"rt",encoding="utf8") as f:
            meta=json.loads(next(f))
            assert meta["type"]=="metadata"
            assert meta["schema"]=="dack_offline_london_outcomes_v1"
            assert meta["split"]==expected_split
            assert meta["beam"]==160
            assert meta["rules"]=="strict_state_stable_dice_actual_beam160"
            metas.append(meta)
            for line in f:
                item=json.loads(line)
                assert item["type"]=="label"
                assert item["label_turn"] in (0,1,2,3)
                assert item["variant"]==meta["variant"]
                rows.append(item)
                gid_seen.add(item["game_id"])
    if not rows:raise ValueError("empty dataset")
    return rows,metas,gid_seen

def make_x_y(rows):
    import numpy as np
    x=np.asarray([feat.extract(
        row["hand"],row["bottom"],row["unknown_counts"],
        row["seat"],row["keep_n"]) for row in rows],dtype=float)
    y=np.asarray([row["label_turn"] for row in rows],dtype=int)
    if not np.isfinite(x).all():raise ValueError("bad features")
    return x,y

def multiclass_metrics(prob,y):
    import numpy as np
    p=np.clip(prob,1e-12,1.)
    onehot=np.eye(4)[y]
    return {
        "brier_multiclass":float(np.mean(np.sum((p-onehot)**2,axis=1))),
        "log_loss":float(-np.mean(np.log(p[np.arange(len(y)),y]))),
        "accuracy":float(np.mean(np.argmax(p,axis=1)==y)),
        "t1_expected":float(p[:,1].mean()),
        "t1_observed":float((y==1).mean()),
        "t2_or_earlier_expected":float((p[:,1]+p[:,2]).mean()),
        "t2_or_earlier_observed":float(((y==1)|(y==2)).mean()),
        "t3_or_earlier_expected":float((1.-p[:,0]).mean()),
        "t3_or_earlier_observed":float((y>0).mean()),
    }

def fit(train_files,calibration_files,model_file,report_file):
    import numpy as np
    from scipy.special import softmax,logsumexp
    from scipy.optimize import minimize_scalar
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    train,training_meta,tgroups=read_rows(train_files,"train")
    calibration,calibration_meta,cgroups=read_rows(calibration_files,"calibration")
    if tgroups&cgroups:
        raise ValueError("DATA LEAKAGE: game IDs shared between train/calibration")
    X,y=make_x_y(train)
    CX,cy=make_x_y(calibration)
    classes=sorted(set(int(x) for x in y))
    if classes!=[0,1,2,3]:
        raise ValueError("Need all four deployment time classes for probabilistic fit")
    if len(tgroups)<16 or len(cgroups)<16:
        raise ValueError("Need >=16 independent game groups in EACH split even for pilot training")
    scale=StandardScaler()
    z=scale.fit_transform(X)
    model=LogisticRegression(max_iter=1000,C=.5)
    model.fit(z,y)
    if model.classes_.tolist()!=[0,1,2,3]:
        raise ValueError("Unexpected class order")
    divisor=np.where(scale.scale_==0,1.,scale.scale_)
    raw_coef=model.coef_/divisor
    raw_intercept=model.intercept_-np.sum(raw_coef*scale.mean_,axis=1)
    cal_logits=CX@raw_coef.T+raw_intercept
    def negll(logtemp):
        s=cal_logits/np.exp(logtemp)
        return float(np.mean(logsumexp(s,axis=1)-s[np.arange(len(cy)),cy]))
    res=minimize_scalar(negll,bounds=(-2,2),method="bounded",
                        options={"xatol":1e-5})
    if not res.success:raise RuntimeError("temperature calibration failed")
    temp=float(np.exp(res.x))
    export={
        "schema":"dack_london_multiclass_softmax_v8",
        "feature_sha256":feat.feature_hash(),"feature_names":list(feat.FEATURES),
        "classes":[0,1,2,3],"coef":raw_coef.tolist(),
        "intercept":raw_intercept.tolist(),"temperature":temp,
        "train_game_count":len(tgroups),
        "calibration_game_count":len(cgroups),
        "train_rollouts":len(train),"calibration_rollouts":len(calibration),
        "training_sources":[m["source_physical_sha256"] for m in training_meta],
        "model_description":"low-capacity four-class multinomial logistic + independent temperature",
        "warning":"predictions conditional on beam-160 optimistic goldfish, not multiplayer wins"
    }
    # IMPORTANT: verify pure-Python exported inference matches sklearn.
    for i in range(min(30,len(calibration))):
        pure=feat.probability_from_export(export,CX[i].tolist())
        direct=softmax(cal_logits[i]/temp)
        if max(abs(float(a)-float(b)) for a,b in zip(pure,direct))>1e-9:
            raise AssertionError("runtime model export differs from training framework")

    train_logits=X@raw_coef.T+raw_intercept
    p_train=softmax(train_logits/temp,axis=1)
    p_cal=softmax(cal_logits/temp,axis=1)
    report={
        "schema":"dack_london_model_calibration_report_v8",
        "separate_training_and_calibration_game_ids":True,
        "no_hidden_draws_as_model_inputs":True,
        "n_train_groups":len(tgroups),"n_calibration_groups":len(cgroups),
        "train_rollouts":len(train),"calibration_rollouts":len(calibration),
        "temperature":temp,
        "training_metrics_resubstitution_not_holdout":multiclass_metrics(p_train,y),
        "calibration_metrics_used_to_choose_temperature_not_holdout":multiclass_metrics(p_cal,cy),
        "policy_evaluation_status":"NOT RUN",
        "warning":"train and calibration scores are not an independent final evaluation"
    }
    out=Path(model_file);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(export,sort_keys=True,separators=(",",":"))+"\n")
    to=Path(report_file);to.parent.mkdir(parents=True,exist_ok=True)
    to.write_text(json.dumps(report,indent=2)+"\n")
    print("OFFLINE_MODEL_FIT_PASS",json.dumps(report,sort_keys=True),flush=True)
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--train",nargs="+",required=True)
    p.add_argument("--calibration",nargs="+",required=True)
    p.add_argument("--model",default="models/dack_london_v8.json")
    p.add_argument("--report",default="benchmark_results/dack_london_v8_calibration.json")
    a=p.parse_args()
    fit(a.train,a.calibration,a.model,a.report)
