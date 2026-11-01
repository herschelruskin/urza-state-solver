#!/usr/bin/env python3
"""Fit a frozen v44 physical candidate-value residual model from *all* 154k
legal-bottom counterfactual outcomes, with 192 distinct training deals and
64 distinct dev deals; NEVER train on observed dev gameplay.

Predeclared 96-tree depth8 min_leaf12 RF on the physical T2 minus Q27
residual. Sample weights inverse to finalist count, one physical game group
= one weight unit. Model predicts observed deployment PbyT2 after keeping
the exact candidate hand; not teacher choice or a guaranteed win probability.
The independent dev set is a *diagnostic candidate-choice counterfactual
test*, not a prospective full-game deployment benchmark.
"""
from __future__ import annotations
import argparse,gzip,glob,hashlib,json,random,sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np
from sklearn.ensemble import RandomForestRegressor
import dack_mulligan_teacher_features_v13_20261031 as f
import dack_mulligan_v44_candidate_residual_20261101 as runtime

SCHEMA="dack_v44_full_candidate_physical_Q2_residual_training_dev_1"
SOURCE_SCHEMA="dack_v44_154k_candidate_physical_counterfactual_source_v1"

def load(paths,split,lo,hi):
    paths=sorted(glob.glob(paths))
    assert len(paths)==((hi-lo+1)//16),(split,len(paths))
    groups={};source=[]
    for p in paths:
        raw=Path(p).read_bytes()
        source.append((Path(p).name,hashlib.sha256(raw).hexdigest()))
        with gzip.open(p,"rt") as gz:z=json.load(gz)
        assert z["schema"]==SOURCE_SCHEMA and z["status"]=="PASS"
        assert z["split"]==split and z["independent_physical_groups"]==16
        assert z["physical_futures_per_candidate"]==8
        assert z["all_structural_top12_candidates_evaluated"]
        assert z["same_physical_unseen92_futures_across_candidate_bottoms"]
        assert z["same_stable_chance_seed_across_candidate_bottoms"]
        assert z["strict_actual_99_card_deck_and_beam160"]
        assert z["feature_schema_sha256"]==f.feature_hash()
        assert z["experimental_only_no_policy_approval"]
        assert z["source_v27_model_sha256"]==hashlib.sha256(
             (ROOT/"models/dack_v27_expanded_T2_only_value_EXPERIMENTAL.json").read_bytes()).hexdigest()
        for row in z["rows"]:
            gid=row["gid"]
            assert lo<=gid<=hi and gid not in groups
            assert row["stage"] in (2,3,4,5)
            assert row["stage"]==2+((gid-154000)%4)
            assert sum(row["unknown_counts"].values())==92
            assert len(row["candidates"])==row["N_candidate_rows"]
            assert 7<=len(row["candidates"])<=12
            assert [c["idx"] for c in row["candidates"]]==list(range(len(row["candidates"])))
            for c in row["candidates"]:
                assert len(c["turns"])==8
                assert all(t in (0,1,2,3) for t in c["turns"])
                assert abs(sum(0<t<=2 for t in c["turns"])/8-c["physical_Q2"])<1e-12
                assert abs(sum(0<t<=3 for t in c["turns"])/8-c["physical_Q3"])<1e-12
                assert Counter(row["seven"])==Counter(c["hand"])+Counter(c["bottom"])
            groups[gid]=row
    assert sorted(groups)==list(range(lo,hi+1))
    assert len(set(r["stage"] for r in groups.values()))==4
    return groups,source

def matrix(groups):
    allx=[];y=[];w=[];q=[]
    for row in groups.values():
        candidates=row["candidates"]
        for c in candidates:
            x=f.extract(row["seven"],c["hand"],c["bottom"],
                        Counter(row["unknown_counts"]),
                        row["seat"],row["keep_n"],row["stage"],
                        c["struct_rank"],c["idx"])
            assert len(x)==len(f.FEATURES)
            allx.append([x[k] for k in runtime.FEATURE_INDICES])
            y.append(c["physical_Q2"]-c["baseline_v27_pred_Q2"])
            w.append(1/len(candidates))
            q.append(c["baseline_v27_pred_Q2"])
    return (np.asarray(allx,dtype=np.float32),
            np.asarray(y,dtype=float),np.asarray(w,dtype=float),
            np.asarray(q,dtype=float))

def sklearn_predict(model,x,baseline):
    raw=float(model.predict(np.asarray([x],dtype=np.float32))[0])
    raw=max(-runtime.CLIP_ABS,min(runtime.CLIP_ABS,raw))
    return max(0.,min(1.,baseline+runtime.SHRINKAGE*raw))

def selection(row,model):
    old_idx=row["source_v27_maxq_index"]
    pred=[]
    for c in row["candidates"]:
        x=f.extract(row["seven"],c["hand"],c["bottom"],
            Counter(row["unknown_counts"]),row["seat"],row["keep_n"],
            row["stage"],c["struct_rank"],c["idx"])
        new=runtime.adjusted(model,x,c["baseline_v27_pred_Q2"])
        pred.append(new)
    new_idx=max(range(len(pred)),key=lambda j:(pred[j],-j))
    assert old_idx==max(range(len(pred)),key=lambda i:(
        row["candidates"][i]["baseline_v27_pred_Q2"],-i))
    return old_idx,new_idx,pred

def estimate(data,model):
    detail=[];stages={}
    for gid,row in data.items():
        a,b,pred=selection(row,model)
        ca=row["candidates"][a];cb=row["candidates"][b]
        d={
           "gid":gid,"stage":row["stage"],"seat":row["seat"],
           "old_index":a,"new_index":b,
           "changed":a!=b,
           "baseline_Q2":ca["baseline_v27_pred_Q2"],
           "adjusted_Q2":pred[b],
           "old_physical_Q2":ca["physical_Q2"],
           "new_physical_Q2":cb["physical_Q2"],
           "old_physical_Q3":ca["physical_Q3"],
           "new_physical_Q3":cb["physical_Q3"],
           "old_keeponsame_v27_threshold":ca["baseline_v27_pred_Q2"]>=row["source_v27_DP"],
           "new_keep_on_adjusted_score":pred[b]>=row["source_v27_DP"],
           "old_turns":ca["turns"],"new_turns":cb["turns"],
        }
        detail.append(d)
    N=len(detail);assert N==64
    changed=[z for z in detail if z["changed"]]
    def group(a):
        n=len(a)
        if not n:return None
        return {
            "groups":n,"changed_bottoms":sum(z["changed"] for z in a),
            "physical_T2_candidate_value_delta_pp":
                 100*sum(z["new_physical_Q2"]-z["old_physical_Q2"] for z in a)/n,
            "physical_T3_candidate_value_delta_pp":
                 100*sum(z["new_physical_Q3"]-z["old_physical_Q3"] for z in a)/n,
            "old_keep_decisions":sum(z["old_keeponsame_v27_threshold"] for z in a),
            "new_keep_decisions":sum(z["new_keep_on_adjusted_score"] for z in a),
            "changed_keep_decisions":sum(z["old_keeponsame_v27_threshold"]!=z["new_keep_on_adjusted_score"] for z in a),
        }
    report={"all":group(detail),"changed":group(changed)}
    for stage in (2,3,4,5):
        report[f"stage_{stage}"]=group([z for z in detail if z["stage"]==stage])
    rng=random.Random(440154)
    B=5000
    boot={h:[] for h in (2,3)}
    for it in range(B):
        totals={h:0. for h in (2,3)}
        for _ in range(N):
            r=detail[rng.randrange(N)]
            # Reuse exactly the *same future index* for paired alternatives.
            j=rng.randrange(8)
            for h in (2,3):
                totals[h]+=int(0<r["new_turns"][j]<=h)-int(0<r["old_turns"][j]<=h)
        for h in (2,3):boot[h].append(100*totals[h]/N)
    for h in (2,3):
        b=sorted(boot[h])
        report[f"T{h}_group_and_shared_future_bootstrap95_pp"]=[b[124],b[4874]]
    return report,detail

def train(source_dir,output,report):
    a,filestrain=load(str(Path(source_dir)/"v44_train_*.json.gz"),"train",154000,154191)
    b,filesdev=load(str(Path(source_dir)/"v44_dev_*.json.gz"),"dev",154192,154255)
    assert not set(a)&set(b)
    X,Y,W,Q=matrix(a)
    rf=RandomForestRegressor(n_estimators=runtime.ESTIMATORS,
       max_depth=runtime.MAX_DEPTH,min_samples_leaf=runtime.MIN_LEAF,
       max_features=0.65,bootstrap=True,random_state=441920,n_jobs=2)
    rf.fit(X,Y,sample_weight=W)
    trees=[]
    for est in rf.estimators_:
        t=est.tree_
        trees.append({
           "left":t.children_left.tolist(),
           "right":t.children_right.tolist(),
           "feature":t.feature.tolist(),
           "threshold":t.threshold.tolist(),
           "value":t.value[:,0,0].tolist(),
        })
    model={
      "schema":runtime.SCHEMA,"policy_approved":False,
      "original_deck":"one_key_34",
      "feature_hash":f.feature_hash(),
      "feature_indices":list(runtime.FEATURE_INDICES),
      "feature_names":[f.FEATURES[j] for j in runtime.FEATURE_INDICES],
      "excluded_literal_onehot_cards":True,
      "training_physical_game_groups":192,
      "physical_futures_per_candidate":8,
      "model_trained_on_all_legal_bottom_alternatives_not_only_v14":True,
      "true_physical_beam160_T2_residual_not_teacher_labels":True,
      "shrinkage":runtime.SHRINKAGE,"residual_clip_abs":runtime.CLIP_ABS,
      "max_depth":runtime.MAX_DEPTH,"min_leaf":runtime.MIN_LEAF,
      "train_game_ids":[154000,154191],
      "dev_game_ids_excluded_from_fit":[154192,154255],
      "source_sha256_by_shard":filestrain,
      "forest_random_state":441920,
      "trees":trees,
    }
    assert len(trees)==runtime.ESTIMATORS
    # Unconditional parity against sklearn for actual observed candidate
    # features, before dev calculation.
    for i in range(min(60,len(X))):
        q=sklearn_predict(rf,X[i],Q[i])
        xx=[0.]*len(f.FEATURES)
        for ii,j in enumerate(runtime.FEATURE_INDICES):xx[j]=float(X[i,ii])
        exported=runtime.adjusted(model,xx,Q[i])
        assert abs(q-exported)<1e-8,(i,q,exported)
    modp=Path(output);modp.parent.mkdir(parents=True,exist_ok=True)
    modp.write_text(json.dumps(model,sort_keys=True,separators=(",",":"))+"\n")
    reportdev,detail=estimate(b,model)
    document={
      "schema":SCHEMA,"status":"PASS","model_approved":False,
      "train_independent_groups":192,"dev_independent_groups":64,
      "train_candidate_rows":len(Y),"train_independent_physical_rollouts":len(Y)*8,
      "dev_candidate_rows":sum(len(g["candidates"]) for g in b.values()),
      "dev_independent_physical_rollouts":8*sum(len(g["candidates"]) for g in b.values()),
      "distinct_game_ids_between_train_and_dev":True,
      "complete_original_candidate_top12_not_just_v14_winners":True,
      "dev_not_in_fit_or_model_hyperparameter_selection":True,
      "comparison":"new physically supervised coupled score vs frozen v43 best v27 predicted Q2",
      "dev_is_candidate_value_NOT_full_game_outcome":True,
      "new_physical_seed_group_and_future_paired_bootstrap":True,
      "baseline_v27_DP_not_recalibrated_on_dev":True,
      "not_a_prospective_policy_promotion":True,
      "model_sha256":runtime.sha(modp),
      "train_source_shards":filestrain,
      "dev_source_shards":filesdev,
      "dev":reportdev,
      "dev_per_group":detail,
    }
    rp=Path(report);rp.parent.mkdir(parents=True,exist_ok=True)
    rp.write_text(json.dumps(document,sort_keys=True,indent=2)+"\n")
    print("DACK_V44_TRUE_PHYSICAL_CANDIDATE_RESIDUAL_TRAIN_DEV_PASS",
      json.dumps({"train_groups":192,"dev_groups":64,
        "candidate_rows":len(Y),"dev_results":reportdev},sort_keys=True),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source-dir",required=True)
    p.add_argument("--model",default="models/v44_all_candidate_Q2_residual_RESEARCH.json")
    p.add_argument("--report",default="benchmark_results/v44_all_candidate_Q2_residual_dev_N64.json")
    z=p.parse_args();train(z.source_dir,z.model,z.report)
