#!/usr/bin/env python3
"""v37 train DIRECT signed T2/T3 action regret, grouping physical games.

No old keep-probability blending, no student-v5 imitation labels.
True action regret = physical Qkeep(T2/T3) - shared physical C(T2/T3)
for one exact frozen v33b bottom and v27 future. Each of 12
bootstrap ensemble members resamples outer physical training
groups WITHIN predeclared strata, then separately resamples each
shared seat-stage C lottery exactly once per model fit.
"""
from __future__ import annotations
from collections import defaultdict,Counter
import glob,gzip,hashlib,json,random,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import dack_mulligan_v37_direct_regret as run
import dack_mulligan_v37_features as feats

SCHEMA="dack_v37_train_direct_true_action_regret_126k_v1"
MANIFEST=ROOT/"datasets/v37_preoutcome_training_manifest.json"

def readz(path):
    with gzip.open(path,"rt") as f:return json.load(f)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def fit(kpattern,cpattern):
    import numpy as np
    from sklearn.ensemble import RandomForestRegressor
    m=json.loads(MANIFEST.read_text())
    assert m["status"]=="PASS" and m["schema"]=="dack_v37_outcome_blind_three_strata_manifest_v1"
    assert m["selection_outcome_blind"] and m["v13_is_proxy_NOT_original_v5"]
    expected={x["game_id"]:x for x in m["random_groups"]+m["enriched_groups"]}
    assert len(expected)==384
    cfiles=sorted(glob.glob(cpattern))
    assert len(cfiles)==12
    C={};shas={}
    for path in cfiles:
        d=readz(path)
        assert d["schema"]=="dack_v37_real_physical_shared_frozen_v33b_Qmull_1"
        assert d["status"]=="PASS" and d["physical_full99_futures"]==256
        assert d["source_v33b_sha256"]==m["v33b_frozen_sha256"]
        assert d["reject_seven_restored_and_all_99_reshuffled"]
        key=(d["seat"],d["stage"])
        assert key not in C and key[0] in range(4) and key[1] in (0,1,2)
        arr=d["true_turns"];assert len(arr)==256
        C[key]=arr;shas["C:"+str(key)]=sha(path)
    assert len(C)==12
    files=sorted(glob.glob(kpattern));assert len(files)==96
    groups={}
    for path in files:
        d=readz(path)
        assert d["schema"]=="dack_v37_real_physical_126k_direct_regret_KEEP_source_v1"
        assert d["status"]=="PASS" and d["strict_gameplay_beam160"]
        assert d["selection_manifest_sha256"]==sha(MANIFEST)
        assert d["source_v33b_sha256"]==m["v33b_frozen_sha256"]
        assert d["feature_sha256"]==feats.feature_hash()
        assert d["no_v5_action_as_training_label"]
        for row in d["rows"]:
            gid=row["game_id"]
            assert gid in expected and gid in d["game_ids"]
            assert row["group_source"]==expected[gid]["sample"]
            assert row["physical_source_partition"]==d["part"]
            assert row["stage"] in (0,1,2) and row["seat"] in range(4)
            assert len(row["features"])==len(feats.NAMES)
            assert len(row["true_turns"])==d["futures_per_stage"]
            assert 0<=row["true_K_T2"]<=row["true_K_T3"]<=1
            assert all(x in (0,1,2,3) for x in row["true_turns"])
            if d["part"]=="random":
                assert expected[gid]["sample"]=="unconditional_random"
                assert d["futures_per_stage"]==8
            else:
                assert expected[gid]["sample"] in ("discordant_boundary","discordant_confident")
                assert d["futures_per_stage"]==48
                assert row["stage"]==expected[gid]["stage"]
            groups.setdefault(gid,[]).append(row)
        shas["K:"+d["part"]+":"+str(d["index"])]=sha(path)
    assert sorted(groups)==sorted(expected)
    assert all(len(groups[gid])==(3 if expected[gid]["sample"]=="unconditional_random" else 1)
               for gid in groups)
    bysrc=defaultdict(list)
    for gid,meta in expected.items():bysrc[meta["sample"]].append(gid)
    assert set(bysrc)=={"unconditional_random","discordant_boundary","discordant_confident"}
    assert [len(bysrc[k]) for k in ("unconditional_random","discordant_boundary","discordant_confident")]==[256,64,64]
    rng=random.Random(371261)
    models=[]
    for k in range(run.N):
        # Common C lottery resampled ONCE per seat-stage, separately for
        # the T2 and T3 labels from the SAME physical future turn.
        cmean={}
        for key,arr in C.items():
            draw=[arr[rng.randrange(256)] for _ in range(256)]
            cmean[key]=(
                sum(0<t<=2 for t in draw)/256,
                sum(0<t<=3 for t in draw)/256)
        sampled=[]
        for category in ("unconditional_random","discordant_boundary","discordant_confident"):
            ids=bysrc[category]
            sampled += [ids[rng.randrange(len(ids))] for _ in ids]
        R=[x for gid in sampled for x in groups[gid]]
        X=np.asarray([r["features"] for r in R],dtype=np.float32)
        Y2=np.asarray([r["true_K_T2"]-cmean[(r["seat"],r["stage"])][0]
                        for r in R],dtype=float)
        Y3=np.asarray([r["true_K_T3"]-cmean[(r["seat"],r["stage"])][1]
                        for r in R],dtype=float)
        weights=np.asarray([
             (1./3 if r["group_source"]=="unconditional_random" else .6)
             for r in R],dtype=float)
        assert len(R)==896 and len(X)==896
        def train(y,head):
            clf=RandomForestRegressor(
                 n_estimators=32,max_depth=9,min_samples_leaf=6,
                 max_features=.85,random_state=370000+k*121+head*11,
                 n_jobs=2)
            clf.fit(X,y,sample_weight=weights)
            return clf,[{
               "left":t.tree_.children_left.tolist(),
               "right":t.tree_.children_right.tolist(),
               "feature":t.tree_.feature.tolist(),
               "threshold":t.tree_.threshold.tolist(),
               "value":t.tree_.value[:,0,0].tolist()
            } for t in clf.estimators_]
        model2,tree2=train(Y2,2);model3,tree3=train(Y3,3)
        if k==0:
            for row in R[:12]:
                x=np.asarray([row["features"]],dtype=np.float32)
                assert abs(float(model2.predict(x)[0])-
                           run.forest_value(tree2,row["features"]))<1e-9
                assert abs(float(model3.predict(x)[0])-
                           run.forest_value(tree3,row["features"]))<1e-9
        models.append({"T2":tree2,"T3":tree3})
        print("DACK_V37_DIRECT_GROUP_AND_SHARED_C_BOOTSTRAP_FIT_PASS",k+1,flush=True)
    model={
      "schema":run.SCHEMA,"feature_hash":feats.feature_hash(),
      "feature_names":list(feats.NAMES),
      "ensemble":models,
      "stages_eligible":[0,1,2],
      "T2_deadband":run.T2_DEADBAND,"T3_max_loss":run.T3_ALLOWED_LOSS,
      "physical_99_deck":"one_key_34",
      "under_frozen_future_v27_keep_v33b_bottom":True,
      "DIRECT_signed_Qkeep_MINUS_real_Qmull_no_v27_blend":True,
      "shared_C_sampled_once_per_seat_stage_in_each_bootstrap":True,
      "training_K_real_physical_outcomes":12288,
      "training_C_full99_real_physical_outcomes":3072,
      "training_group_n":384,"training_state_n":896,
      "source_manifest_sha256":sha(MANIFEST),
      "source_physical_shard_sha256":shas,
      "source_v33b_sha256":m["v33b_frozen_sha256"],
      "source_v27_q_sha256":sha(ROOT/"models/dack_v27_expanded_T2_only_value_EXPERIMENTAL.json"),
      "source_v27_C_sha256":sha(ROOT/"models/dack_v27_T2_only_continuations_EXPERIMENTAL.json"),
      "127k_validation_unseen":True,
      "128k_prospective_unseen":True,
      "policy_approved":False}
    run.validate(model)
    dest=ROOT/"models/dack_v37_direct_regret_EXPERIMENTAL.json"
    dest.write_text(json.dumps(model,sort_keys=True,separators=(",",":"))+"\n")
    changed=Counter()
    for gid in sorted(groups):
        for r in groups[gid]:
            new,trace=run.decide(model,r["features"],r["stage"],r["old_keep"])
            changed[(r["group_source"],trace["reason"])]+=1
    result={
      "schema":SCHEMA,"status":"PASS",
      "model_sha256":sha(dest),"groups":384,"states":896,
      "train_K":12288,"train_C":3072,
      "train_only_action_counts_not_validation":{
          str(k):v for k,v in sorted(changed.items())},
      "shared_C_resampled_per_group_bootstrap":True,
      "no_v5_action_teacher_supervision":True,
      "policy_approved":False}
    (ROOT/"benchmark_results/v37_train_only_direct_regret.json").write_text(
        json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("DACK_V37_REAL_PHYSICAL_DIRECT_ACTION_REGRET_TRAIN_PASS",
          json.dumps(result,sort_keys=True),flush=True)

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--K",default="collected/v37_K_*.json.gz")
    p.add_argument("--C",default="collected/v37_C_*.json.gz")
    a=p.parse_args();fit(a.K,a.C)
