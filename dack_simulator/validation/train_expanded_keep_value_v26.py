#!/usr/bin/env python3
"""v26 enlarged real-utility forest, fixed config, zero 96k evaluation usage."""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import dack_mulligan_teacher_features_v13_20261031 as features
import dack_mulligan_keep_value_v22_20261101 as runtime
from dack_simulator.validation.train_all_stage_keep_value_v22 import evaluate

SCHEMA="dack_v26_expanded_all_stage_counterfactual_keep_values"
SPLITS={"train":(93000,93255),"validation":(94000,94063)}

def read_split(paths, split):
    assert split in SPLITS
    low, high=SPLITS[split]
    expected=set(range(low,high+1))
    ids=set();states=[];files=[];source_sha=None
    for path in sorted(paths):
        with gzip.open(path,"rt") as f:
            metadata=json.loads(next(f))
            raw=[json.loads(line) for line in f]
        assert metadata["schema"]==SCHEMA and metadata["split"]==split
        assert metadata["games"]==8 and metadata["draws_per_stage"]==4
        assert metadata["actual_beam"]==160 and metadata["new_unseen_library_order_never_saved"]
        assert len(raw)==256
        if source_sha is None: source_sha=metadata["source_student_model_sha256"]
        assert source_sha==metadata["source_student_model_sha256"]
        fid=set(x["game_id"] for x in raw)
        assert len(fid)==8 and ids.isdisjoint(fid) and fid.issubset(expected)
        ids|=fid
        groups=defaultdict(list)
        for line in raw:
            assert line["schema"]==SCHEMA and line["label_turn"] in (0,1,2,3)
            assert "actual_library" not in line and "hidden_order" not in line
            groups[(line["game_id"],line["stage"])].append(line)
        assert len(groups)==64
        for (gid, stage),rows in groups.items():
            rows.sort(key=lambda z:z["future_index"])
            assert [z["future_index"] for z in rows]==[0,1,2,3]
            first=rows[0]
            for second in rows[1:]:
                assert all(second[k]==first[k] for k in
                      ("seven","hand","bottom","seat","keep_n","unknown_counts","candidate_index"))
            assert first["keep_n"]==[7,7,6,5,4,3,2,1][stage]
            labels=[z["label_turn"] for z in rows]
            value=sum(1.0 if t in (1,2) else 0.5 if t==3 else 0.0 for t in labels)/4
            x=features.extract(first["seven"],first["hand"],first["bottom"],
                first["unknown_counts"],first["seat"],first["keep_n"],stage,
                first["candidate_struct_rank"],first["candidate_index"])
            counts=Counter(labels)
            states.append({
                "game_id":gid,"stage":stage,"seat":first["seat"],
                "keep_n":first["keep_n"],"input":x,"real_u":value,
                "student_would_keep":first["student_would_keep"],
                "real_T1":counts[1]/4,
                "real_by_T2":(counts[1]+counts[2])/4,
                "real_by_T3":(counts[1]+counts[2]+counts[3])/4,
            })
        files.append({"path":path,"sha256":hashlib.sha256(Path(path).read_bytes()).hexdigest()})
    assert ids==expected,(split,len(ids),sorted(expected-ids)[:6])
    assert len(states)==len(expected)*8
    return states,source_sha,files

def train(trainpaths,valpaths,outmodel,outreport):
    import numpy as np
    from sklearn.ensemble import RandomForestRegressor
    tr,sha,trfiles=read_split(trainpaths,"train")
    va,vsha,vafiles=read_split(valpaths,"validation")
    assert sha==vsha
    frozen_sha=hashlib.sha256(Path("models/v14_curve/v14_teacher_groups_128.json").read_bytes()).hexdigest()
    assert frozen_sha==sha
    frozen_v22=json.loads(Path("models/dack_v22_real_all_stage_keep_value_EXPERIMENTAL.json").read_text())
    assert frozen_v22["source_student_model_sha256"]==sha and frozen_v22["deployed_policy_approved"] is False
    X=np.asarray([r["input"] for r in tr],dtype=np.float32)
    Y=np.asarray([r["real_u"] for r in tr],dtype=float)
    forest=RandomForestRegressor(n_estimators=192,max_depth=9,
          min_samples_leaf=6,max_features=0.65,random_state=262626,n_jobs=2)
    forest.fit(X,Y)
    baseline={str(s):sum(z["real_u"] for z in tr if z["stage"]==s)/256 for s in range(8)}
    model={
      "schema":runtime.SCHEMA,
      "feature_hash":features.feature_hash(),
      "feature_count":len(features.FEATURES),
      "source_student_model_sha256":sha,
      "trained_on_all_eight_stages_including_rejected":True,
      "trained_for_v14_128_candidate_bottom_selection":True,
      "policy_kept_only_bias_removed_at_training":True,
      "training_games":256,
      "validation_games":64,
      "training_states":2048,
      "validation_states":512,
      "true_gameplay_futures_per_state":4,
      "prior_by_stage_from_train":baseline,
      "utility":"P(T1 exact)+P(T2 exact)+0.5 P(T3 exact)",
      "v26_stage_sample_futures_protocol":"DACK_V26_93K_TRAIN_94K_VALID_INDEPENDENT_8_STAGE_FUTURES",
      "deployed_policy_approved":False,
      "diagnostic_only":True,
      "trees":[{
          "left":t.tree_.children_left.tolist(),
          "right":t.tree_.children_right.tolist(),
          "feature":t.tree_.feature.tolist(),
          "threshold":t.tree_.threshold.tolist(),
          "value":t.tree_.value[:,0,0].tolist(),
      } for t in forest.estimators_],
    }
    for rec in va[:min(64,len(va))]:
        x=rec["input"]
        actual=runtime.predict(model,x)
        expected=float(forest.predict(np.asarray([x],dtype=np.float32))[0])
        assert abs(actual-max(0.0,min(1.0,expected)))<1e-9,("sklearn parity",actual,expected)
    val_new=evaluate(va,model,baseline)
    val_old=evaluate(va,frozen_v22,baseline)
    trained=evaluate(tr,model,baseline)
    report={
      "schema":"dack_v26_expanded_real_keep_value_heldout_stage_validation",
      "status":"PASS",
      "train_id_range":[93000,93255],"validation_id_range":[94000,94063],
      "no_v25_96k_training_or_hyperparameter_selection":True,
      "training_games":256,"validation_games":64,
      "training_stage_states":2048,"validation_stage_states":512,
      "actual_full_beam160_future_labels":(256+64)*8*4,
      "frozen_bottom_policy_sha256":sha,
      "v22_model_sha256":runtime.model_hash(frozen_v22),
      "v26_model_sha256":runtime.model_hash(model),
      "new_forest_hyperparameters":{"n_estimators":192,"max_depth":9,"min_samples_leaf":6,
                                  "max_features":0.65,"random_state":262626},
      "training_file_checksums":trfiles,
      "validation_file_checksums":vafiles,
      "training_metrics_not_holdout":trained,
      "independent_94k_validation_v26":val_new,
      "independent_94k_validation_frozen_v22":val_old,
      "model_approved":False,
      "warning":"Value-model MSE improvement is not full-game improvement. Neither holdout nor 96k diagnosis was used to select model hyperparameters."
    }
    Path(outmodel).write_text(json.dumps(model,sort_keys=True,separators=(",",":"))+"\n")
    Path(outreport).write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print("DACK_V26_STAGE_VALUE_FIT_PASS",json.dumps({
         "training_games":256,"validation_games":64,
         "new_val_mse":val_new["nonlinear_forest"]["MSE"],
         "old_val_mse":val_old["nonlinear_forest"]["MSE"],
         "model_approved":False
    }),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--train",nargs="+",required=True)
    p.add_argument("--validation",nargs="+",required=True)
    p.add_argument("--model",default="models/dack_v26_expanded_real_keep_value_EXPERIMENTAL.json")
    p.add_argument("--report",default="benchmark_results/v26_real_keep_value_validation.json")
    a=p.parse_args()
    train(a.train,a.validation,a.model,a.report)
