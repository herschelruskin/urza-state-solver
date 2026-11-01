#!/usr/bin/env python3
"""Train a small nonlinear teacher-DISTILLATION forest; NOT win probability.

Student learns: (a) original v5 choice among <=12 structural candidates;
(b) original v5 keep/reject from that chosen hand at a specified London stage.
Train and validation groups must be disjoint at the OUTER game ID level.
The validation set is for engineering/model selection; a third untouched
imitation test and independent full-game outcome tests are required.

The export is pure JSON split-node trees; no sklearn is needed for games.
"""
from __future__ import annotations
from collections import Counter
import argparse,gzip,json,sys,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import dack_mulligan_teacher_features_v13_20261031 as f

def read(files,split):
    rows=[];groups=set();sha=set()
    for file in files:
        with gzip.open(file,"rt",encoding="utf8") as src:
            meta=json.loads(next(src))
            if meta.get("schema")!="dack_v13_v5_london_teacher_stages_v1":
                raise ValueError("bad teacher stage schema")
            if meta["split"]!=split or meta["teacher"]!="dack_stable_dice_strict_bounded_witness_v5":
                raise ValueError("inconsistent teacher/split")
            sha.add(meta["source_manifest_sha256"])
            for line in src:
                row=json.loads(line)
                assert row["type"]=="stage"
                if not row["candidate_rows"] or row["teacher_chosen_candidate"]>=len(row["candidate_rows"]):
                    raise ValueError("teacher candidate not in shortlist")
                rows.append(row);groups.add(row["game_id"])
    if not rows or len(sha)!=1:raise ValueError("missing data or mixed deck manifest")
    return rows,groups,sha.pop()

def transform(rows):
    import numpy as np
    cx=[];cy=[];cw=[];kx=[];ky=[]
    stage_indices=[]
    for rec in rows:
        inputs=[]
        for i,cand in enumerate(rec["candidate_rows"]):
            x=f.extract(rec["seven"],cand["hand"],cand["bottom"],
                        rec["unknown_counts"],rec["seat"],rec["keep_n"],
                        rec["stage"],cand["struct_rank"],i)
            inputs.append(x)
            cx.append(x);cy.append(int(i==rec["teacher_chosen_candidate"]))
            # Weight each sampled stage equally despite different shortlist length.
            cw.append(1.0/len(rec["candidate_rows"]))
        kx.append(inputs[rec["teacher_chosen_candidate"]])
        ky.append(int(rec["teacher_keep"]))
        stage_indices.append(len(rec["candidate_rows"]))
    return (np.asarray(cx,dtype=float),np.asarray(cy,dtype=int),
            np.asarray(cw,dtype=float),np.asarray(kx,dtype=float),
            np.asarray(ky,dtype=int),stage_indices)

def to_json_forest(clf):
    if list(clf.classes_)!=[0,1]:raise ValueError("both teacher decision labels required")
    trees=[]
    for estimator in clf.estimators_:
        tree=estimator.tree_
        val=tree.value[:,0,:]
        prob=(val[:,1]/val.sum(axis=1)).tolist()
        trees.append({
            "left":tree.children_left.tolist(),
            "right":tree.children_right.tolist(),
            "feature":tree.feature.tolist(),
            "threshold":tree.threshold.tolist(),
            "positive":prob,
        })
    return trees

def evaluate(rows,model):
    n=len(rows)
    bottom_ok=0;keep_ok=0;joint_ok=0;first_rank_selected=0
    pos=0;predpos=0
    details=[]
    for rec in rows:
        scores=[]
        feats=[]
        for i,c in enumerate(rec["candidate_rows"]):
            x=f.extract(rec["seven"],c["hand"],c["bottom"],
                        rec["unknown_counts"],rec["seat"],rec["keep_n"],
                        rec["stage"],c["struct_rank"],i)
            feats.append(x);scores.append(f.score_head(model,"choice_trees",x))
        # Stable first candidate tie break is intentional and teacher-consistent.
        chosen=max(range(len(scores)),key=lambda i:scores[i])
        keep=(rec["keep_n"]==1 or
              f.score_head(model,"keep_trees",feats[chosen])>=model["keep_cutoff"])
        teacher_choice=rec["teacher_chosen_candidate"]
        teacher_keep=rec["teacher_keep"]
        bottom_ok+=int(chosen==teacher_choice)
        keep_ok+=int(keep==teacher_keep)
        joint_ok+=int(chosen==teacher_choice and keep==teacher_keep)
        first_rank_selected+=int(teacher_choice==0)
        pos+=int(teacher_keep);predpos+=int(keep)
        details.append({"id":rec["game_id"],"stage":rec["stage"],
                        "teacher_candidate":teacher_choice,"student_candidate":chosen,
                        "teacher_keep":teacher_keep,"student_keep":keep,
                        "student_score_selected":scores[chosen]})
    return {
        "visited_teacher_stages":n,
        "candidate_top1_accuracy":bottom_ok/n,
        "keep_decision_accuracy_under_student_selected_bottom":keep_ok/n,
        "joint_stage_accuracy":joint_ok/n,
        "teacher_selects_structural_first_rate":first_rank_selected/n,
        "teacher_keep_rate":pos/n,"student_keep_rate":predpos/n,
        "distinct_game_groups":len(set(x["game_id"] for x in rows)),
        "per_stage_results":details
    }

def train(trainfiles,valfiles,out,reportout,n_trees=64,max_depth=7):
    from sklearn.ensemble import RandomForestClassifier
    import numpy as np
    tr,tgroups,msha=read(trainfiles,"train")
    va,vgroups,vsha=read(valfiles,"validation")
    if tgroups&vgroups:raise AssertionError("teacher group leakage")
    if len(tgroups)<8 or len(vgroups)<8:raise ValueError("need >=8 train and independent val groups")
    if msha!=vsha:raise ValueError("different physical deck specs")
    cx,cy,cw,kx,ky,_=transform(tr)
    for label,y in (("choice",cy),("keep",ky)):
        if sorted(set(y))!=[0,1]:raise ValueError("missing both teacher labels in "+label)
    choice=RandomForestClassifier(
        n_estimators=n_trees,max_depth=max_depth,min_samples_leaf=2,
        max_features=.75,class_weight="balanced_subsample",
        random_state=1337,n_jobs=2)
    choice.fit(cx,cy,sample_weight=cw)
    keep=RandomForestClassifier(
        n_estimators=n_trees,max_depth=max_depth,min_samples_leaf=2,
        max_features=.75,class_weight="balanced_subsample",
        random_state=31337,n_jobs=2)
    keep.fit(kx,ky)
    model={
        "schema":f.EXPORT_SCHEMA,
        "model_purpose":"behavior_cloning_OF_original_v5_london_teacher_decisions",
        "feature_hash":f.feature_hash(),
        "feature_count":len(f.FEATURES),
        "source_manifest_sha256":msha,
        "source_teacher_version":"dack_stable_dice_strict_bounded_witness_v5",
        "choice_trees":to_json_forest(choice),
        "keep_trees":to_json_forest(keep),
        "keep_cutoff":0.5,
        "training_groups":len(tgroups),
        "validation_groups":len(vgroups),
        "training_stage_rows":len(tr),
        "validation_stage_rows":len(va),
        "teacher_outcomes_not_used_as_predictor_inputs":True,
        "teacher_probabilities_NOT_deployment_probabilities":True,
        "deployed_policy_approved":False,
        "diagnostic_only":True,
        "n_trees_per_head":n_trees,
        "max_depth":max_depth,
        "note":"Imitate teacher choices, not outcome P(T1/T2/T3). Validation is off-policy, evaluated on v5-visited stages."
    }
    # Cross-framework numerical parity on the SAME selected candidates.
    for i in range(min(30,len(va))):
        rec=va[i]
        for j,c in enumerate(rec["candidate_rows"][:3]):
            x=f.extract(rec["seven"],c["hand"],c["bottom"],
                        rec["unknown_counts"],rec["seat"],rec["keep_n"],
                        rec["stage"],c["struct_rank"],j)
            forest=f.score_head(model,"choice_trees",x)
            sklearn=float(choice.predict_proba(np.asarray([x]))[0,1])
            if abs(forest-sklearn)>1e-9:raise AssertionError("exported candidate scorer mismatch")
    train_metrics=evaluate(tr,model)
    val_metrics=evaluate(va,model)
    report={
        "schema":"dack_v13_teacher_policy_imitation_metrics_v1",
        "train_groups":len(tgroups),"validation_groups":len(vgroups),
        "frozen_validation_not_full_gameplay":True,
        "train_metrics":{k:v for k,v in train_metrics.items() if k!="per_stage_results"},
        "validation_metrics":{k:v for k,v in val_metrics.items() if k!="per_stage_results"},
        "validation_stage_examples":val_metrics["per_stage_results"],
        "model_needs_independent_holdout_and_full_gameplay":True,
        "model_approved":False
    }
    a=Path(out);a.parent.mkdir(parents=True,exist_ok=True)
    a.write_text(json.dumps(model,separators=(",",":"),sort_keys=True)+"\n")
    b=Path(reportout);b.parent.mkdir(parents=True,exist_ok=True)
    b.write_text(json.dumps(report,indent=2)+"\n")
    print("DISTILLED_V13_MODEL_FIT_PASS",json.dumps({
        "train":report["train_metrics"],"validation":report["validation_metrics"],
        "feature_count":len(f.FEATURES),
        "train_game_groups":len(tgroups),
        "validation_game_groups":len(vgroups),
        "model_approved":False
    }),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--train",nargs="+",required=True)
    p.add_argument("--validation",nargs="+",required=True)
    p.add_argument("--model",default="models/dack_teacher_distill_v13_EXPERIMENTAL.json")
    p.add_argument("--report",default="benchmark_results/teacher_distill_v13_validation.json")
    p.add_argument("--trees",type=int,default=64)
    p.add_argument("--depth",type=int,default=7)
    a=p.parse_args()
    train(a.train,a.validation,a.model,a.report,a.trees,a.depth)
