#!/usr/bin/env python3
"""v31 frozen-split action-regret fit/validation/test.

Learn the *residual conditional KEEP-MULL action advantage* relative to a
frozen v27 value-DP threshold. No exact bottom imitation. Train ONLY on 103000
..103047 groups; validate separately 103048..063, untouched final test
103064..079. No inference model promotion and no outcome-peeking.

Regret is computed from 6 paired sampled rollout outcomes per action and
has noisy winner's-curse bias. A tie in observed T2 is not a proof of true
equivalence; report held-out paired policy value directly with clustered CIs.
"""
from __future__ import annotations
import argparse,collections,gzip,hashlib,json,random,struct,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import dack_mulligan_teacher_features_v13_20261031 as features

SCHEMA="dack_v31_actual_two_action_regret_103k"
MODEL_SCHEMA="dack_v31_Qadvantage_residual_forest_EXPERIMENTAL"
PROTO="DACK_V31_ONE_STEP_Q_KEEP_MULL_UNSEEN_LONDON_ROLLOUT_V1"
SHRINK=.5
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read(paths,split):
    groups={}
    for p in paths:
        with gzip.open(p,"rt") as f:doc=json.load(f)
        assert doc["schema"]==SCHEMA and doc["status"]=="PASS"
        assert doc["split"]==split
        assert doc["physical_groups"]==4
        assert doc["futures_per_arm"]==6
        assert doc["actual_beam"]==160
        assert doc["downstream_mull_uses_frozen_v27_policy_only"]
        assert doc["no_hidden_order_in_model_inputs"]
        for row in doc["outcomes"]:
            gid=int(row["game_id"])
            groups.setdefault(gid,[]).append(row)
    limits={"train":(103000,103047),"validation":(103048,103063),
            "test":(103064,103079)}
    low,hi=limits[split]
    assert sorted(groups)==list(range(low,hi+1)),(split,len(groups))
    assert all(sorted([z["stage"] for z in rows])==[0,1,3,5]
               for rows in groups.values())
    assert all(len(z["rollouts"])==6 for rows in groups.values() for z in rows)
    return [z for gid in sorted(groups) for z in groups[gid]],list(sorted(groups))

def inputs(row):
    # v27's predicted keep vs continuation gap is a legitimate pre-action
    # baseline. Both are computed from the visible hand and learned priors.
    base=(float(row["original_v27_predicted_keep_T2"])-
          float(row["original_v27_continuation_T2"]))
    return [float(x) for x in row["features"]]+[
        base,float(row["original_v27_predicted_keep_T2"]),
        float(row["original_v27_continuation_T2"])
    ]

def base_gap(row):
    return (float(row["original_v27_predicted_keep_T2"])-
            float(row["original_v27_continuation_T2"]))

def f32(x):
    return struct.unpack("<f",struct.pack("<f",float(x)))[0]

def predict_residual(model,x):
    if model["schema"]!=MODEL_SCHEMA or model["features_count"]!=len(x):
        raise ValueError("wrong model schema/dimensions")
    assert model["trained_on_103k_train_only"]
    xf=[f32(v) for v in x]
    result=[]
    for tree in model["trees"]:
        idx=0
        while tree["left"][idx]>=0:
            j=int(tree["feature"][idx])
            idx=tree["left"][idx] if xf[j]<=tree["threshold"][idx] else tree["right"][idx]
        result.append(float(tree["value"][idx]))
    return sum(result)/len(result)

def policy_keep(row,model=None):
    b=base_gap(row)
    if model is None:return b>=0.
    # Predeclared shrinkage protects the frozen baseline from noisy Qgap
    # estimates. Not optimized on the validation or test outcomes.
    return b+SHRINK*predict_residual(model,inputs(row))>=0.

def evaluate(rows,model):
    by_gid=collections.defaultdict(list)
    allr=[]
    for r in rows:
        qk=float(r["empirical_Q_keep_T2"])
        qm=float(r["empirical_Q_mull_T2"])
        delta=qk-qm
        base=policy_keep(r)
        learned=policy_keep(r,model)
        ybase=qk if base else qm
        ylearn=qk if learned else qm
        ideal=max(qk,qm)
        result={
            "game_id":r["game_id"],"stage":r["stage"],
            "base_keep":bool(base),"corrected_keep":bool(learned),
            "Q_keep_T2":qk,"Q_mull_T2":qm,
            "observed_Qgap_keep_minus_mull":delta,
            "frozen_policy_empirical_T2":ybase,
            "corrected_policy_empirical_T2":ylearn,
            "corrected_minus_frozen_empirical_T2":ylearn-ybase,
            "frozen_empirical_regret":ideal-ybase,
            "corrected_empirical_regret":ideal-ylearn,
            "observed_T2_tie":qk==qm,
        }
        by_gid[r["game_id"]].append(result);allr.append(result)
    diff=[sum(z["corrected_minus_frozen_empirical_T2"] for z in group)/len(group)
          for group in by_gid.values()]
    rng=random.Random(313131)
    boot=sorted(sum(diff[rng.randrange(len(diff))] for _ in diff)/len(diff)
                for _ in range(10000))
    def mean(k):return sum(r[k] for r in allr)/len(allr)
    return {
        "physical_groups":len(by_gid),"stage_states":len(allr),
        "frozen_mean_actual_T2_of_paired_action":mean("frozen_policy_empirical_T2"),
        "corrected_mean_actual_T2_of_paired_action":mean("corrected_policy_empirical_T2"),
        "corrected_minus_frozen_mean_actual_T2":mean("corrected_minus_frozen_empirical_T2"),
        "paired_game_group_bootstrap_95ci_delta":[boot[249],boot[9749]],
        "frozen_mean_empirical_regret":mean("frozen_empirical_regret"),
        "corrected_mean_empirical_regret":mean("corrected_empirical_regret"),
        "corrected_changed_action_count":sum(z["base_keep"]!=z["corrected_keep"] for z in allr),
        "observed_T2_ties":sum(z["observed_T2_tie"] for z in allr),
        "corrected_improves_on_sampled_Q_n":sum(z["corrected_minus_frozen_empirical_T2"]>0 for z in allr),
        "corrected_worsens_on_sampled_Q_n":sum(z["corrected_minus_frozen_empirical_T2"]<0 for z in allr),
        "warning":"Six sampled futures each: per-state max Q is optimistic. This comparison is an off-policy counterfactual estimate, not prospective full-game performance. Stage draws are correlated within physical group.",
        "details":allr,
    }

def main(trainpaths,valpaths,testpaths,modelpath,reportpath):
    import numpy as np
    from sklearn.ensemble import RandomForestRegressor
    tr,tids=read(trainpaths,"train")
    va,vids=read(valpaths,"validation")
    te,teids=read(testpaths,"test")
    assert len(set(tids)|set(vids)|set(teids))==80
    assert len(set(tids)&set(vids))==0
    assert len(set(vids)&set(teids))==0
    assert len(set(tids)&set(teids))==0
    assert len(tr)==192 and len(va)==64 and len(te)==64
    for r in tr+va+te:
        assert len(r["features"])==len(features.FEATURES)
        assert r["empirical_Q_keep_T2"]>=0 and r["empirical_Q_mull_T2"]>=0
        assert all(0<=q<=1 for q in (
            r["empirical_Q_keep_T2"],r["empirical_Q_mull_T2"],
            r["empirical_Q_keep_T3"],r["empirical_Q_mull_T3"]))
    X=np.asarray([inputs(r) for r in tr],dtype=np.float32)
    Y=np.asarray([r["empirical_advantage_keep_minus_mull_T2"]-base_gap(r)
                  for r in tr],dtype=float)
    forest=RandomForestRegressor(
        n_estimators=128,max_depth=6,min_samples_leaf=8,
        max_features=.65,random_state=313131,n_jobs=2)
    forest.fit(X,Y)
    model={
        "schema":MODEL_SCHEMA,"features_count":len(inputs(tr[0])),
        "input_visible_feature_hash":features.feature_hash(),
        "trained_on_103k_train_only":True,
        "train_groups":len(tids),"validation_groups":len(vids),"test_groups":len(teids),
        "source_v27_value_sha256":sha("models/dack_v27_expanded_T2_only_value_EXPERIMENTAL.json"),
        "source_v27_continuation_sha256":sha("models/dack_v27_T2_only_continuations_EXPERIMENTAL.json"),
        "primary_outcome":"regret in cumulative Dack deployment by T2",
        "training_label":"Q_KEEP_T2-Q_MULL_T2 minus frozen-v27 decision gap",
        "bottom_choice_head":"unchanged frozen v14-128 in both Q arms",
        "shrinkage_correction":SHRINK,
        "fit_hyperparameters":{"trees":128,"depth":6,"min_samples_leaf":8,
                         "max_features":.65,"random_state":313131},
        "candidate_policy_approved":False,
        "trees":[{
            "left":t.tree_.children_left.tolist(),
            "right":t.tree_.children_right.tolist(),
            "feature":t.tree_.feature.tolist(),
            "threshold":t.tree_.threshold.tolist(),
            "value":t.tree_.value[:,0,0].tolist(),
        } for t in forest.estimators_],
    }
    for r in va[:16]:
        a=predict_residual(model,inputs(r))
        b=float(forest.predict(np.asarray([inputs(r)],dtype=np.float32))[0])
        assert abs(a-b)<1e-9,(a,b)
    scores={
      "train_fit_only_not_holdout":evaluate(tr,model),
      "independent_validation_not_for_tuning":evaluate(va,model),
      "untouched_103k_test":evaluate(te,model)
    }
    report={
        "schema":"dack_v31_two_action_T2_regret_offpolicy_validation",
        "status":"PASS","model_approved":False,
        "training_physical_ids":[min(tids),max(tids)],
        "validation_physical_ids":[min(vids),max(vids)],
        "test_physical_ids":[min(teids),max(teids)],
        "all_inference_inputs_visible_seven_and_unknown_multiset_only":True,
        "zero_exact_bottom_card_imitation_labels":True,
        "frozen_v27_downstream_mulligan_policy":True,
        "independent_future_orders_used_as_labels_only":True,
        "frozen_prior_policy_unchanged":True,
        "candidate_cannot_be_promoted_without_independent_full_game_test":True,
        "note":"The same seeded stochastic game values across different actions are not exact matched-world realizations. Pay attention to uncertainty and game-group bootstrap.",
        "scores":scores,
    }
    dest=Path(modelpath);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(model,sort_keys=True,separators=(",",":"))+"\n")
    target=Path(reportpath);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print("DACK_V31_ACTION_REGRET_FIT_PASS",json.dumps({
        "validation":{k:v for k,v in scores["independent_validation_not_for_tuning"].items() if k!="details"},
        "test":{k:v for k,v in scores["untouched_103k_test"].items() if k!="details"},
        "model_approved":False,
    },sort_keys=True),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--train",nargs="+",required=True)
    p.add_argument("--validation",nargs="+",required=True)
    p.add_argument("--test",nargs="+",required=True)
    p.add_argument("--model",default="models/dack_v31_Q_advantage_residual_EXPERIMENTAL.json")
    p.add_argument("--report",default="benchmark_results/v31_Q_advantage_103k_holdout.json")
    a=p.parse_args();main(a.train,a.validation,a.test,a.model,a.report)
