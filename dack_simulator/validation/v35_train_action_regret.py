#!/usr/bin/env python3
"""v35 fit model only from 116k all-stage and 115k disagreement CALIBRATION.

No 117k validation (already inspected), no v34c replication,
no original 115k win-turn labels. No model selection or tuning.
"""
from __future__ import annotations
from collections import Counter,defaultdict
import gzip,glob,hashlib,json,math,random,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import dack_mulligan_v35_action_regret as mdl
import dack_mulligan_v35_action_features as feats
import dack_paired_counterfactual_v33b_regret_bottom_only_20261101 as v33b

def read_gz(path):
    with gzip.open(path,"rt") as f:return json.load(f)

def source_data():
    assert v33b.audit()["status"]=="PASS"
    ref=v33b.ref;deck=Counter(ref.VARIANTS["one_key_34"])
    C={}
    files=sorted(glob.glob(str(ROOT/"benchmark_results/v34_consistent_regret_shards/v34_C_*.json.gz")))
    assert len(files)==28
    for file in files:
        d=read_gz(file)
        assert d["schema"]=="dack_v34_shared_Qmull_exact_frozen_v33b_downstream"
        assert d["status"]=="PASS" and d["strict_beam160"]
        assert d["v33b_model_sha256"]==v33b.MODEL_SHA
        cell=(d["seat"],d["stage"])
        assert cell not in C
        data=[r["turn"] for r in d["results"] if r["split"]=="train"]
        assert len(data)==64
        C[cell]={t:sum(0<x<=t for x in data)/64 for t in (2,3)}
    groups={}
    kfiles=sorted(glob.glob(str(ROOT/"benchmark_results/v34_consistent_regret_shards/v34_K_train_*.json.gz")))
    assert len(kfiles)==16
    for f in kfiles:
        d=read_gz(f)
        assert d["status"]=="PASS" and d["schema"]=="dack_v34_true_Qkeep_frozen_v33b_all_stages"
        assert d["split"]=="train" and d["futures_per_stage"]==8
        for row in d["rows"]:
            gid=int(row["game_id"]);s=int(row["stage"]);seat=int(row["seat"])
            assert 116000<=gid<116064 and s in range(7)
            hand=tuple(row["selected_v33b_hand"]);seven=tuple(row["seven"])
            unknown=tuple(c for c,n in (deck-Counter(seven)).items() for _ in range(n))
            assert len(unknown)==92
            q=float(row["v27_pred_Qkeep_T2"]);old=float(row["v27_DP_threshold"])
            x=feats.extract(s,seat,seven,hand,unknown,q,old)
            trials=row["outcomes"]
            assert len(trials)==8
            y2=sum(0<t<=2 for t in trials)/8-C[(seat,s)][2]-x[1]
            y3=sum(0<t<=3 for t in trials)/8-C[(seat,s)][3]
            key=("uniform116",gid)
            groups.setdefault(key,[]).append((x,y2,y3,1./7*(mdl.EARLY_WEIGHT if s in feats.EARLY else 1.)))
    assert len([k for k in groups if k[0]=="uniform116"])==64
    assert all(len(v)==7 for k,v in groups.items())
    selected=sorted(glob.glob(str(ROOT/"benchmark_results/v34c_forced_keep_shards/v34c_keep_*.json.gz")))
    assert len(selected)==8
    for file in selected:
        d=read_gz(file)
        assert d["status"]=="PASS" and d["schema"]=="dack_v34c_115k_earliest_actual_stage_disagreement_forced_keep"
        assert d["futures_per_split"]==16
        assert d["frozen_v33b_model_sha256"]==v33b.MODEL_SHA
        for row in d["rows"]:
            gid=int(row["game_id"]);s=int(row["stage"]);seat=int(row["seat"])
            assert 115000<=gid<115256 and s in range(7)
            seven=tuple(row["seven"]);hand=tuple(row["v33b_hand"])
            unknown=tuple(c for c,n in (deck-Counter(seven)).items() for _ in range(n))
            assert len(unknown)==92
            q=float(row["v27_absolute_Qkeep_prediction"])
            old=float(row["v27_original_DP_threshold"])
            x=feats.extract(s,seat,seven,hand,unknown,q,old)
            # Absolutely NO use of v34c replication or v5 action label.
            future=row["fresh_keep_futures_by_split"]["calibration"]
            assert len(future)==16
            y2=sum(0<t<=2 for t in future)/16-C[(seat,s)][2]-x[1]
            y3=sum(0<t<=3 for t in future)/16-C[(seat,s)][3]
            key=("selected115",gid)
            assert key not in groups
            groups[key]=[(x,y2,y3,mdl.SELECTED_DISAGREEMENT_GROUP_WEIGHT*
                (mdl.EARLY_WEIGHT if s in feats.EARLY else 1.))]
    assert len([k for k in groups if k[0]=="selected115"])==100
    return groups,C,{"training_116k_physical_games":64,
                     "training_115k_selected_disagreement_games":100,
                     "v34c_CALIBRATION_only_keep_futures":16,
                     "v34_uniform_train_keep_futures":8,
                     "v34_shared_C_train_futures_per_cell":64,
                     "not_used":["117k validation","v34c replication",
                       "115k realized full-game win turns","v5 action imitation"]}

def train():
    groups,C,meta=source_data()
    ids=sorted(groups)
    allx=[r[0] for k in ids for r in groups[k]]
    scales=[max(.35,(sum(x[i]*x[i] for x in allx)/len(allx))**.5)
            for i in range(feats.N)]
    assert all(math.isfinite(s) and s>0 for s in scales)
    ensemble=[];rng=random.Random(350121)
    for b in range(mdl.BOOTS):
        records=[]
        for _ in ids:
            k=ids[rng.randrange(len(ids))]
            records.extend(groups[k])
        w2,w3=mdl.ridge(records,scales)
        ensemble.append({"residual_T2":w2,"direct_T3":w3})
    model={
      "schema":mdl.SCHEMA,"feature_hash":feats.hash_names(),
      "feature_names":list(feats.NAMES),"scales":scales,
      "ensemble":ensemble,"lambda_ridge":mdl.LAMBDA,
      "group_bootstrap_ensemble_size":mdl.BOOTS,
      "training_groups_total":len(ids),
      "training_states_total":len(allx),
      "training_physical_protocol":meta,
      "early_stage_weight":mdl.EARLY_WEIGHT,
      "selected_disagreement_group_weight":mdl.SELECTED_DISAGREEMENT_GROUP_WEIGHT,
      "T2_action_override_margin":mdl.T2_MIN_ACTION_MARGIN,
      "T3_safeguard_max_loss":mdl.T3_MAX_ALLOWED_LOSS,
      "max_T2_residual_correction":mdl.MAX_RESIDUAL_CORRECTION,
      "override_stages":[0,1,2],
      "v27_keep_margin_as_prior":True,
      "heldout_121k_never_seen":True,
      "source_v33b_bottom_sha256":v33b.MODEL_SHA,
      "source_v27_keep_model_sha256":hashlib.sha256(
             (ROOT/"models/dack_v27_expanded_T2_only_value_EXPERIMENTAL.json").read_bytes()).hexdigest(),
      "source_v27_dp_sha256":hashlib.sha256(
             (ROOT/"models/dack_v27_T2_only_continuations_EXPERIMENTAL.json").read_bytes()).hexdigest(),
      "policy_approved":False
    }
    # Deliberately do not report training success rates as policy validation.
    out=ROOT/"models/dack_v35_early_action_regret_EXPERIMENTAL.json"
    out.write_text(json.dumps(model,sort_keys=True,separators=(",",":"))+"\n")
    result={
       "schema":"dack_v35_train_only_group_bootstrap_ridge",
       "status":"PASS","model_sha256":hashlib.sha256(out.read_bytes()).hexdigest(),
       "training_source":meta,
       "groups":len(ids),"states":len(allx),
       "feature_dim":feats.N,
       "group_bootstrap_models":mdl.BOOTS,
       "T2_training_label_nonzero":sum(int(abs(y2)>1.e-9) for k in ids for _,y2,_,_ in groups[k]),
       "117k_and_115k_replication_excluded":True,
       "policy_approved":False
    }
    (ROOT/"benchmark_results/v35_train_only_diagnostic.json").write_text(
       json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("DACK_V35_TRAIN_ONLY_RIDGE_PASS",json.dumps(result,sort_keys=True),flush=True)

if __name__=="__main__":
    mdl.selftest();feats.selftest();train()
