#!/usr/bin/env python3
"""v27 T2-only real-outcome fit on frozen 93k training, 94k validation.

The previous v26 blended utility was adequate by T3 but lagged v5 by T2.
No v25 96k or v26 97k full-game results enter features, labels or training.
"""
from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from dack_simulator.validation.train_expanded_keep_value_v26 import read_split
import dack_mulligan_keep_value_v22_20261101 as runtime
import dack_mulligan_teacher_features_v13_20261031 as feats
from dack_simulator.validation.train_T2_only_keep_value_v23 import evaluate

def fit(trainpaths,valpaths,outmodel,outreport):
    import numpy as np
    from sklearn.ensemble import RandomForestRegressor
    tr,sha,trfiles=read_split(trainpaths,"train")
    va,vsha,vafiles=read_split(valpaths,"validation")
    assert sha==vsha and len(tr)==2048 and len(va)==512
    old=json.loads(Path("models/dack_v23_T2_only_real_keep_value_EXPERIMENTAL.json").read_text())
    assert old["T3_reward_is_exactly_zero"] is True and old["source_student_model_sha256"]==sha
    tr=[dict(r,real_u=r["real_by_T2"]) for r in tr]
    va=[dict(r,real_u=r["real_by_T2"]) for r in va]
    X=np.asarray([r["input"] for r in tr],dtype=np.float32)
    Y=np.asarray([r["real_u"] for r in tr],dtype=float)
    forest=RandomForestRegressor(n_estimators=192,max_depth=9,min_samples_leaf=6,
                                 max_features=.65,random_state=272727,n_jobs=2)
    forest.fit(X,Y)
    baseline={str(s):sum(r["real_u"] for r in tr if r["stage"]==s)/256 for s in range(8)}
    model={
      "schema":runtime.SCHEMA,
      "feature_hash":feats.feature_hash(),
      "feature_count":len(feats.FEATURES),
      "source_student_model_sha256":sha,
      "trained_on_all_eight_stages_including_rejected":True,
      "trained_for_v14_128_candidate_bottom_selection":True,
      "policy_kept_only_bias_removed_at_training":True,
      "T3_reward_is_exactly_zero":True,
      "primary_goal":"maximize_deployment_by_turn_2",
      "training_games":256,"validation_games":64,
      "training_states":2048,"validation_states":512,
      "true_gameplay_futures_per_state":4,
      "utility":"P(T1 exact)+P(T2 exact); P(T3) weight zero",
      "prior_by_stage_from_train":baseline,
      "deployed_policy_approved":False,"diagnostic_only":True,
      "trees":[{
        "left":t.tree_.children_left.tolist(),
        "right":t.tree_.children_right.tolist(),
        "feature":t.tree_.feature.tolist(),
        "threshold":t.tree_.threshold.tolist(),
        "value":t.tree_.value[:,0,0].tolist(),
      } for t in forest.estimators_],
    }
    for r in va[:64]:
        a=runtime.predict(model,r["input"])
        b=float(forest.predict(np.asarray([r["input"]],dtype=np.float32))[0])
        assert abs(a-max(0.,min(1.,b)))<1e-9
    score_new=evaluate(va,model,baseline)
    score_old=evaluate(va,old,baseline)
    report={
      "schema":"dack_v27_T2_only_expanded_value_fit_94k_validation",
      "status":"PASS","model_unapproved":True,
      "frozen_training_game_ids":[93000,93255],
      "separate_validation_game_ids":[94000,94063],
      "new_prospective_full_game_ids_reserved":[98000,98255],
      "no_96k_or_97k_game_label_training":True,
      "same_immutable_v14_candidate_bottom_selector":True,
      "actual_beam160_physical_futures_in_training":8192,
      "training_states":2048,"validation_states":512,
      "v27_T2_only_94k_validation":score_new,
      "v23_T2_only_94k_validation":score_old,
      "original_train_checksums":trfiles,
      "independent_val_checksums":vafiles,
      "model_sha256":runtime.model_hash(model),
      "hyperparameters_fixed_before_98k":{"n_estimators":192,"max_depth":9,
                  "min_samples_leaf":6,"max_features":.65,"random_state":272727},
      "warning":"Independent 94k conditional prediction accuracy is not full-game rate. v23 previously failed a small-game T2 test. This model remains unapproved pending fresh 98k N256."
    }
    Path(outmodel).write_text(json.dumps(model,sort_keys=True,separators=(",",":"))+"\n")
    Path(outreport).write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print("DACK_V27_T2_ONLY_FIT_PASS",json.dumps({
      "T2_94k_MSE_v27":score_new["nonlinear_forest"]["MSE"],
      "T2_94k_MSE_v23":score_old["nonlinear_forest"]["MSE"],
      "models_approved":False}),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--train",nargs="+",required=True)
    p.add_argument("--validation",nargs="+",required=True)
    p.add_argument("--model",default="models/dack_v27_expanded_T2_only_value_EXPERIMENTAL.json")
    p.add_argument("--report",default="benchmark_results/v27_T2_only_94k_validation.json")
    a=p.parse_args()
    fit(a.train,a.validation,a.model,a.report)
