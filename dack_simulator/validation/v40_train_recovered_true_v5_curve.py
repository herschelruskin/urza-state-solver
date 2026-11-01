#!/usr/bin/env python3
"""v40 group-separated true-v5 behavior cloning learning curve.

Reuses archived 1592 physical-group / 6101-stage corpus; NO expensive v5
or goldfish rollouts, no use of historical win outcomes. The 115k historical
cohort is an *internal diagnostics-only replay test*: it has already been
inspected in earlier experiments, NOT a novel prospective holdout.

We compare full v13 observable features versus a more deck-portable ablation
dropping literal 'seven:' and 'bottom:' one-card indicators. Both retain real
capability and known synergy/pair features, so transfer to a different deck
remains a hypothesis awaiting actual card-change evaluation.

Per-stage teacher-choice candidates share one label; per-game groups, not
stages or candidate rows, are the statistical units.
"""
from __future__ import annotations

import argparse, gzip, hashlib, json, random, time
from collections import Counter, defaultdict
from pathlib import Path
import sys
import numpy as np
from sklearn.ensemble import RandomForestClassifier

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import dack_mulligan_teacher_features_v13_20261031 as feat
from dack_simulator.validation.train_teacher_distillation_v13 import to_json_forest

SCHEMA="dack_v40_archived_actual_v5_grouped_learning_curve_1"
SRC="datasets/v40_recovered_original_v5_history_1592.jsonl.gz"
SUMMARY="benchmark_results/v40_recovered_original_v5_1592_summary.json"
SEED=406153
SIZES=(128,384,768,1288)
TREES=48
DEPTH=10
MIN_LEAF=4
FEATURE_SETS={
    "full": tuple(range(len(feat.FEATURES))),
    "portable": tuple(i for i,name in enumerate(feat.FEATURES)
        if not (name.startswith("seven:") or name.startswith("bottom:"))),
}
# One historical N256 cohort kept wholly out of train; an independent
# student's visited-state distribution is a stress set.
TEST_SOURCE="v33b_115k"
STRESS_SOURCE="v15_student_visited"

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def load():
    expect=json.loads((ROOT/SUMMARY).read_text())
    path=ROOT/SRC
    assert sha(path)==expect["data_sha256"], "archived source changed"
    with gzip.open(path,"rt",encoding="utf-8") as f:
        meta=json.loads(next(f));rows=[json.loads(line) for line in f]
    assert meta["independent_physical_groups"]==expect["group_n"]==1592
    assert len(rows)==expect["stage_n"]==6101
    groups=defaultdict(list)
    for r in rows:
        assert r["type"]=="stage" and r["schema"]==meta["schema"]
        assert r["no_historical_game_result_exported"]
        assert r["no_hidden_92_order_exported"]
        assert len(r["seven"])==7 and sum(r["unknown_counts"].values())==92
        groups[r["game_id"]].append(r)
    assert len(groups)==1592
    train=sorted(g for g,z in groups.items() if z[0]["source"] not in
                 (TEST_SOURCE,STRESS_SOURCE))
    test=sorted(g for g,z in groups.items() if z[0]["source"]==TEST_SOURCE)
    stress=sorted(g for g,z in groups.items() if z[0]["source"]==STRESS_SOURCE)
    assert len(train)==1288 and len(test)==256 and len(stress)==48
    assert not set(train)&set(test) and not set(train)&set(stress) and not set(test)&set(stress)
    assert all(len({z["source"] for z in rs})==1 for rs in groups.values())
    assert all(len({z["stage"] for z in rs})==len(rs) for rs in groups.values())
    # Freeze nested order independent of data/teacher predictions.
    rng=random.Random(SEED)
    rng.shuffle(train)
    return groups,train,test,stress,sha(path)

def dataset(groups):
    x=[]; choices=[]; c_targets=[]; c_weights=[]; kept_x=[]; kept_y=[]
    kept_weights=[]; records=[]; ids=[]
    for gid in sorted(groups):
        stage_count=len(groups[gid])
        assert stage_count>=1
        for row in groups[gid]:
            cand=row["candidate_rows"]
            beg=len(x); winner=row["teacher_candidate_index"]
            assert 0<=winner<len(cand)
            assert row["teacher_keep"] in (True,False)
            this=[]
            for j,item in enumerate(cand):
                features=feat.extract(
                    row["seven"],item["hand"],item["bottom"],
                    row["unknown_counts"],row["seat"],row["keep_n"],
                    row["stage"],item["struct_rank"],j)
                this.append(features)
                x.append(features)
                c_targets.append(int(j==winner))
                # Treat one original game as roughly one weight unit, not
                # many independent stage and bottom candidate observations.
                c_weights.append(1.0/(stage_count*len(cand)))
            end=len(x)
            kept_x.append(this[winner])
            kept_y.append(int(row["teacher_keep"]))
            kept_weights.append(1.0/stage_count)
            records.append(row)
            ids.append((beg,end))
    assert records and len(x)==sum(b-a for a,b in ids)
    return {
        "x":np.asarray(x,dtype=np.float32),
        "cy":np.asarray(c_targets,dtype=np.int8),
        "cw":np.asarray(c_weights,dtype=np.float64),
        "kx":np.asarray(kept_x,dtype=np.float32),
        "ky":np.asarray(kept_y,dtype=np.int8),
        "kw":np.asarray(kept_weights,dtype=np.float64),
        "rows":records,"ranges":ids,
    }

def fit(d, indices, mode, size):
    X=d["x"][:,indices]
    K=d["kx"][:,indices]
    choice=RandomForestClassifier(
        n_estimators=TREES,max_depth=DEPTH,min_samples_leaf=MIN_LEAF,
        max_features=.7,class_weight="balanced_subsample",
        random_state=SEED+size*3,n_jobs=2)
    keep=RandomForestClassifier(
        n_estimators=TREES,max_depth=DEPTH,min_samples_leaf=MIN_LEAF,
        max_features=.7,class_weight="balanced_subsample",
        random_state=SEED+size*5+1,n_jobs=2)
    assert set(d["cy"])=={0,1} and set(d["ky"])=={0,1}
    choice.fit(X,d["cy"],sample_weight=d["cw"])
    keep.fit(K,d["ky"],sample_weight=d["kw"])
    return choice,keep

def score(d,indices,choice,keep):
    cproba=choice.predict_proba(d["x"][:,indices])[:,list(choice.classes_).index(1)]
    kproba=keep.predict_proba(d["kx"][:,indices])[:,list(keep.classes_).index(1)]
    # A selected student's bottom affects the KEEP input. Compute keep on the
    # student-selected bottom, not the teacher-selected bottom, for policy path.
    selected=[]
    for a,b in d["ranges"]:
        selected.append(a+int(np.argmax(cproba[a:b])))
    candidate_kproba=keep.predict_proba(
        d["x"][selected][:,indices])[:,list(keep.classes_).index(1)]
    assert len(selected)==len(d["rows"])==len(candidate_kproba)
    return collect(d,selected,kproba,candidate_kproba)

def collect(d, selected, oracle_proba, predicted_proba):
    total=defaultdict(Counter)
    for idx,(rec,(a,b),s,oracle,pred) in enumerate(zip(
            d["rows"],d["ranges"],selected,oracle_proba,predicted_proba)):
        truth=bool(rec["teacher_keep"])
        teacher_i=int(rec["teacher_candidate_index"])
        predicted_choice=s-a
        prediction=bool(rec["keep_n"]==1 or float(pred)>=0.5)
        oracle_keep=bool(rec["keep_n"]==1 or float(oracle)>=0.5)
        cats=("all", "early" if rec["stage"]<3 else "later",
              "stage_"+str(rec["stage"]),
              "natural" if rec["naturally_reached_by_v5"] else "student_visited")
        for cat in cats:
            p=total[cat]
            p["N"]+=1
            p["teacher_keep"]+=int(truth)
            p["pred_keep"]+=int(prediction)
            p["choice_correct"]+=int(predicted_choice==teacher_i)
            p["structural_first_correct"]+=int(teacher_i==0)
            p["joint_correct"]+=int(predicted_choice==teacher_i and prediction==truth)
            p["keep_correct"]+=int(prediction==truth)
            p["oracle_keep_correct"]+=int(oracle_keep==truth)
            p["TP"]+=int(prediction and truth)
            p["TN"]+=int(not prediction and not truth)
            p["FP"]+=int(prediction and not truth)
            p["FN"]+=int(not prediction and truth)
    out={}
    for cat,q in total.items():
        n=q["N"]; pos=q["teacher_keep"]; neg=n-pos
        sensitivity=q["TP"]/pos if pos else None
        specificity=q["TN"]/neg if neg else None
        out[cat]={
            "stage_rows":n,"teacher_keep_rate":pos/n,
            "student_keep_rate":q["pred_keep"]/n,
            "choice_top1_accuracy":q["choice_correct"]/n,
            "structural_first_baseline":q["structural_first_correct"]/n,
            "choice_gain_over_structural_first":
                (q["choice_correct"]-q["structural_first_correct"])/n,
            "keep_accuracy_on_student_selected_candidate":q["keep_correct"]/n,
            "keep_accuracy_on_teacher_selected_candidate_oracle":
                q["oracle_keep_correct"]/n,
            "joint_choice_keep_accuracy":q["joint_correct"]/n,
            "keep_sensitivity":sensitivity,
            "keep_specificity":specificity,
            "keep_balanced_accuracy":(sensitivity+specificity)/2
                 if sensitivity is not None and specificity is not None else None,
            "TP":q["TP"],"TN":q["TN"],"FP":q["FP"],"FN":q["FN"],
            "majority_mull_keep_accuracy_baseline":max(pos,neg)/n,
        }
    return out

def infer_one(trees,x):
    vals=[]
    for tree in trees:
        node=0
        while tree["left"][node]>=0:
            f=int(tree["feature"][node])
            node=tree["left"][node] if float(x[f])<=float(tree["threshold"][node]) \
                    else tree["right"][node]
        vals.append(float(tree["positive"][node]))
    return sum(vals)/len(vals)

def export(choice,keep,indices,mode,size,train_ids,source_hash):
    model={
        "schema":"dack_v40_true_v5_behavior_cloning_two_head_v1",
        "policy_approved":False,
        "teacher_labels_not_win_probabilities":True,
        "historical_validation_is_consumed":True,
        "feature_schema_sha256":feat.feature_hash(),
        "feature_indices":[int(i) for i in indices],
        "feature_names":[feat.FEATURES[k] for k in indices],
        "mode":mode,"train_group_n":size,
        "training_game_ids_sha256":hashlib.sha256(
            json.dumps(sorted(train_ids),separators=(",",":")).encode()).hexdigest(),
        "source_corpus_sha256":source_hash,
        "choice_trees":to_json_forest(choice),
        "keep_trees":to_json_forest(keep),
        "keep_threshold":0.5,
        "training_model_trees_per_head":TREES,
        "training_model_depth":DEPTH,
        "no_outcome_labels":True,
    }
    # Exported probabilities must reproduce sklearn on a real training example.
    return model

def main(out,models_dir):
    start=time.monotonic()
    groups,order,test,stress,source_sha=load()
    print("V40_CORPUS_GROUP_PARTITION",len(order),len(test),len(stress),flush=True)
    # Only compute features ONCE, then train on increasing nested groups.
    ds_train=dataset({g:groups[g] for g in order})
    ds_test=dataset({g:groups[g] for g in test})
    ds_stress=dataset({g:groups[g] for g in stress})
    d_by_group={g:dataset({g:groups[g]}) for g in ()}  # no hidden eval
    order_set=set(order)
    assert len(order_set)==1288
    indices={mode:np.asarray(idx,dtype=int) for mode,idx in FEATURE_SETS.items()}
    report={
      "schema":SCHEMA,"status":"PASS","source_corpus_sha256":source_sha,
      "feature_source_sha256":feat.feature_hash(),
      "full_dim":len(feat.FEATURES),
      "portable_dim":len(FEATURE_SETS["portable"]),
      "portable_excludes_only_literal_card_presence_flags":True,
      "full_training_groups":len(order),"historical_test_groups":len(test),
      "student_visited_stress_groups":len(stress),
      "train_groups_by_source":dict(Counter(groups[g][0]["source"] for g in order)),
      "internal_historical_test_is_NOT_fresh_prospective_validation":True,
      "test_groups_never_in_fit":True,"stress_groups_never_in_fit":True,
      "historical_win_outcomes_not_used":True,
      "student_predicted_keep_uses_student_bottom":True,
      "training_stages_weighted_inverse_within_original_game":True,
      "sample_unit":"independent original game_id",
      "primary_eval":"genuine_v5_choice_keep_joint_agreement_not_winrate",
      "model_approved":False,"curves":[],
    }
    models_dir=Path(models_dir);models_dir.mkdir(parents=True,exist_ok=True)
    for size in SIZES:
        chosen=set(order[:size])
        subset=[i for i,r in enumerate(ds_train["rows"]) if r["game_id"] in chosen]
        # Convert a sparse whole-dataset slice to all-candidate contiguous arrays.
        included_x=[k for i in subset for k in range(*ds_train["ranges"][i])]
        prefix=0;sel_ranges=[]
        for i in subset:
            length=ds_train["ranges"][i][1]-ds_train["ranges"][i][0]
            sel_ranges.append((prefix,prefix+length))
            prefix+=length
        d={
          "x":ds_train["x"][included_x],
          "cy":ds_train["cy"][included_x],
          "cw":ds_train["cw"][included_x],
          "kx":ds_train["kx"][subset],
          "ky":ds_train["ky"][subset],
          "kw":ds_train["kw"][subset],
          "rows":[ds_train["rows"][i] for i in subset],
          "ranges":sel_ranges,
        }
        assert len({r["game_id"] for r in d["rows"]})==size
        for mode,idx in indices.items():
            t0=time.monotonic()
            choice,keep=fit(d,idx,mode,size)
            m=export(choice,keep,idx,mode,size,order[:size],source_sha)
            for head,estimator,values in (
                    ("choice_trees",choice,ds_test["x"][:3,idx]),
                    ("keep_trees",keep,ds_test["kx"][:3,idx])):
                prob=estimator.predict_proba(values)[:,1]
                for x,v in zip(values,prob):
                    assert abs(infer_one(m[head],x)-float(v)) < 1e-8, (
                        "JSON scorer parity",mode,head,size)
            scores_test=score(ds_test,idx,choice,keep)
            scores_stress=score(ds_stress,idx,choice,keep)
            scores_train=score(d,idx,choice,keep)
            path=models_dir/f"v40_archived_actual_v5_{mode}_{size}_RESEARCH.json"
            # Archive final per-mode nested size ONLY; keep learning-curve JSON tiny.
            if size==max(SIZES):
                path.write_text(json.dumps(m,sort_keys=True,separators=(",",":"))+"\n")
                model_sha=sha(path)
            else:
                model_sha=None
            rec={
                "train_groups":size,"train_stage_rows":len(d["rows"]),
                "train_candidate_rows":len(d["x"]),
                "feature_mode":mode,"feature_count":len(idx),
                "training_metrics":scores_train["all"],
                "historical_test_metrics":scores_test,
                "student_visited_stress_metrics":scores_stress,
                "exported_model":str(path) if model_sha else None,
                "exported_model_sha256":model_sha,
                "seconds":round(time.monotonic()-t0,2),
            }
            report["curves"].append(rec)
            print("DACK_V40_TEACHER_LEARNING_CURVE_POINT",json.dumps({
                "groups":size,"mode":mode,"test":scores_test["all"],
                "test_early":scores_test["early"],
                "stress":scores_stress["all"],
                "seconds":rec["seconds"]},sort_keys=True),flush=True)
    dest=Path(out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print("DACK_V40_REUSED_TEACHER_LEARNING_CURVES_PASS",json.dumps({
       "train_groups":len(order),"test_groups":len(test),
       "stress_groups":len(stress),
       "curve_points":len(report["curves"]),
       "report":str(dest),"elapsed_seconds":round(time.monotonic()-start,2)
    }),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--out",default="benchmark_results/v40_true_v5_teacher_learning_curve.json")
    p.add_argument("--models-dir",default="models/v40_true_v5_archived")
    a=p.parse_args()
    main(a.out,a.models_dir)
