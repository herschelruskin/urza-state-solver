#!/usr/bin/env python3
"""v36 fit frozen stratified direct real KEEP probabilities, no holdout data.

Uses only 123k TRAIN shards from pre-outcome fixed manifest:
128 unconditional groups and 128 boundary-enriched groups, all
actual stages0-2 and 16 independently shuffled unseen92 outcomes.
Q(MULL) from 128 independent actual full99 outcomes per seat-stage.
No 121k, 124k, 115k outcomes, v5 decisions or full-game result used.
"""
from __future__ import annotations
from collections import Counter,defaultdict
import gzip,glob,hashlib,json,random,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import dack_mulligan_v36_keep_value as modelrun
import dack_mulligan_v36_features as feat

def h(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def openz(f):
    with gzip.open(f,"rt") as q:return json.load(q)

def fit(kpattern,cpattern):
    import numpy as np
    from sklearn.ensemble import RandomForestRegressor
    manifest=ROOT/"datasets/v36_preoutcome_123k_manifest.json"
    doc=json.loads(manifest.read_text())
    assert doc["schema"]=="dack_v36_preoutcome_stratified_123k_physical_training_manifest_1"
    assert doc["status"]=="PASS" and doc["no_gameplay_rollouts_at_selection"]
    index={x["game_id"]:x for x in doc["groups"]}
    assert len(index)==256
    C={};shas={}
    cfiles=sorted(glob.glob(cpattern))
    assert len(cfiles)==12,("need 12 frozen source true Qmull",len(cfiles))
    for file in cfiles:
        x=openz(file)
        assert x["schema"]=="dack_v36_physical_shared_frozen_v33b_Qmull_1"
        assert x["status"]=="PASS" and x["split"]=="train"
        assert x["futures_per_cell"]==128 and x["strict_gameplay_beam160"]
        assert x["all_99_shuffled_at_each_later_stage"] and x["rejected_seven_not_visible_in_shared_C"]
        assert x["source_frozen_v33b_sha256"]==doc["frozen_v33b_bottom_sha256"]
        key=f'{x["seat"]}:{x["stage"]}'
        assert key not in C and x["seat"] in range(4) and x["stage"] in (0,1,2)
        a=x["physical_turns"];assert len(a)==128
        C[key]={"T2":sum(0<t<=2 for t in a)/128,"T3":sum(0<t<=3 for t in a)/128,
                "source_n":128}
        shas["C:"+key]=h(file)
    assert len(C)==12
    groups={}
    files=sorted(glob.glob(kpattern))
    assert len(files)==64,("need complete 64 training shards",len(files))
    for file in files:
        x=openz(file)
        assert x["schema"]=="dack_v36_real_keep_value_labels_1"
        assert x["status"]=="PASS" and x["split"]=="train"
        assert x["physical_groups"]==4 and x["futures_per_state"]==16
        assert x["strict_actual_gameplay_beam160"]
        assert x["v33b_bottom_sha256"]==doc["frozen_v33b_bottom_sha256"]
        assert x["v36_feature_schema_sha256"]==feat.feature_hash()
        assert x["manifest_sha256"]==h(manifest)
        for row in x["rows"]:
            gid=row["game_id"]
            assert gid in index and gid in x["game_ids"]
            assert row["source_stratum"]==index[gid]["sample"]
            assert row["selection_metadata"]==index[gid]["selection"]
            assert row["stage"] in (0,1,2) and 0<=row["seat"]<4
            assert len(row["features"])==len(feat.NAMES)
            assert len(row["true_turns"])==16
            assert len(row["hand"])==row["keep_n"]
            from collections import Counter as CC
            assert CC(row["seven"])==CC(row["hand"])+CC(row["bottom"])
            assert abs(row["cumulative_T2"]-sum(0<t<=2 for t in row["true_turns"])/16)<1e-12
            assert abs(row["cumulative_T3"]-sum(0<t<=3 for t in row["true_turns"])/16)<1e-12
            assert 0<=row["cumulative_T2"]<=row["cumulative_T3"]<=1
            groups.setdefault(gid,[]).append(row)
        shas["K:"+str(x["index"])]=h(file)
    assert sorted(groups)==sorted(index)
    assert all(sorted(x["stage"] for x in r)==[0,1,2] for r in groups.values())
    random_ids=[g for g in groups if index[g]["sample"]=="random"]
    biased_ids=[g for g in groups if index[g]["sample"]=="boundary_enriched"]
    assert len(random_ids)==len(biased_ids)==128
    ids=sorted(groups);rng=random.Random(361236)
    ensemble=[]
    for b in range(modelrun.ENSEMBLE):
        draws=[ids[rng.randrange(len(ids))] for _ in ids]
        R=[row for gid in draws for row in groups[gid]]
        X=np.asarray([r["features"] for r in R],dtype=np.float32)
        Y2=np.asarray([r["cumulative_T2"] for r in R],dtype=np.float64)
        Y3=np.asarray([r["cumulative_T3"] for r in R],dtype=np.float64)
        sw=np.asarray([(1./3)*(1. if r["source_stratum"]=="random" else .5)
                       for r in R],dtype=float)
        assert len(R)==256*3 and float(sw.sum())>0
        def build(y,head):
            forest=RandomForestRegressor(
              n_estimators=32,max_depth=8,min_samples_leaf=10,
              max_features=.8,random_state=36000+b*97+head*13,
              n_jobs=2)
            forest.fit(X,y,sample_weight=sw)
            return forest,[{
                "left":t.tree_.children_left.tolist(),
                "right":t.tree_.children_right.tolist(),
                "feature":t.tree_.feature.tolist(),
                "threshold":t.tree_.threshold.tolist(),
                "value":t.tree_.value[:,0,0].tolist(),
            } for t in forest.estimators_]
        m2,trees2=build(Y2,2)
        m3,trees3=build(Y3,3)
        if b==0:
            for r in R[:16]:
                xv=np.asarray([r["features"]],dtype=np.float32)
                a2=float(m2.predict(xv)[0])
                a3=float(m3.predict(xv)[0])
                assert abs(a2-modelrun.forest_value(trees2,r["features"]))<1e-9
                assert abs(a3-modelrun.forest_value(trees3,r["features"]))<1e-9
        ensemble.append({"trees_T2":trees2,"trees_T3":trees3})
        print("DACK_V36_GROUP_BOOTSTRAP_MODEL_PASS",b+1,len(R),flush=True)
    model={
       "schema":modelrun.SCHEMA,"feature_hash":feat.feature_hash(),
       "feature_names":list(feat.NAMES),"ensemble":ensemble,
       "C_by_seat_stage":C,"real_shared_C_futures_per_cell":128,
       "old_Qkeep_blend_weight":modelrun.ALPHA_OLD,
       "T2_deadband":modelrun.T2_DEADBAND,
       "T3_safeguard_max_loss":modelrun.T3_MAX_LOSS,
       "C_std_error_multiplier":modelrun.C_STDERR_MULT,
       "stages_eligible":[0,1,2],
       "forest_fixed_parameters":{
          "bootstrap_group_models":modelrun.ENSEMBLE,
          "trees_per_head":32,"max_depth":8,"min_samples_leaf":10,
          "max_features":.8,
          "train_random_group_weight":1.,
          "train_boundary_enriched_group_weight":.5,
          "each_of_3_stage_weights":1./3,
       },
       "source_training_manifest_sha256":h(manifest),
       "source_physical_training_file_shas":shas,
       "source_frozen_v33b_sha256":doc["frozen_v33b_bottom_sha256"],
       "source_v27_Q_model_sha256":h(ROOT/"models/dack_v27_expanded_T2_only_value_EXPERIMENTAL.json"),
       "source_v27_DP_sha256":h(ROOT/"models/dack_v27_T2_only_continuations_EXPERIMENTAL.json"),
       "training_outer_groups":256,"training_state_labels":768,
       "training_16_hidden_futures_per_state":True,
       "training_123k_128_unbiased_and_128_enriched":True,
       "all_124k_holdout_unseen":True,
       "all_125k_prospective_unseen":True,
       "policy_approved":False,
    }
    modelrun.read_model(model)
    dest=ROOT/"models/dack_v36_targeted_real_keep_EXPERIMENTAL.json"
    dest.write_text(json.dumps(model,sort_keys=True,separators=(",",":"))+"\n")
    changes={"random":Counter(),"boundary_enriched":Counter()}
    for gid in ids:
        for r in groups[gid]:
            _,d=modelrun.choose(model,r["features"],r["seat"],r["stage"],
                                r["frozen_v27_old_keep"],r["old_v27_Qkeep"])
            changes[r["source_stratum"]][d["reason"]]+=1
    report={
      "schema":"dack_v36_predeclared_train_only_123k_value_model",
      "status":"PASS","model_sha256":h(dest),
      "n_independent_group_ids":256,"n_early_stage_states":768,
      "n_true_physical_keep_rollouts":12288,
      "n_true_physical_mull_continuations":1536,
      "n_feature_dimensions":len(feat.NAMES),
      "unbiased_training_groups":len(random_ids),
      "boundary_enriched_training_groups":len(biased_ids),
      "training_descriptive_changes_not_holdout":{k:dict(v) for k,v in changes.items()},
      "no_training_outcomes_from_124k_121k_or_115k":True,
      "policy_approved":False}
    (ROOT/"benchmark_results/v36_train_only_diagnostic.json").write_text(
       json.dumps(report,sort_keys=True,indent=2)+"\n")
    print("DACK_V36_TRAIN_ONLY_FOREST_PASS",json.dumps(report,sort_keys=True),flush=True)

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--K",default="collected/v36_train_K_*.json.gz")
    p.add_argument("--C",default="collected/v36_train_C_*.json.gz")
    a=p.parse_args();fit(a.K,a.C)
