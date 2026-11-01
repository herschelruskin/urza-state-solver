#!/usr/bin/env python3
"""v41 early-stage real-physical KEEP probability model, group-fold diagnostics.

Research only: all 115k/116k/117k source cohorts are previously consumed.
No prospective validation or model promotion. Uses exactly frozen v33b KEEP
hand/bottom, v27/v33b continuation; v5 labels are not used in training.
"""
from __future__ import annotations
import argparse, gzip, hashlib, json, math, random, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from dack_simulator.validation import v34_pool_consistent_regret as source
from dack_simulator.validation import v34c_pool_actual_disagreement as conflict
import dack_mulligan_learned_features_v8_20261031 as base

SCHEMA="dack_v41_consumed_physical_early_KminusC_grouped_ridge_1"
FEATURE_NAMES=tuple(s for s in base.FEATURES if not s.startswith("hand:"))
FEATURE_EXTRA=(
 "stage0","stage1","stage2","seven_land_count","seven_white_count",
 "seven_ramp_count","bottom_artifact_count","bottom_land_count",
 "v27_pred_Qkeep","v27_DP","v27_margin",
)
ALL_NAMES=FEATURE_NAMES+FEATURE_EXTRA
MODES={
 "capability":tuple(i for i,n in enumerate(ALL_NAMES) if n not in (
     "v27_pred_Qkeep","v27_DP","v27_margin")),
 "anchored":tuple(range(len(ALL_NAMES))),
}
SEED=410012
ALPHA=12.0
FOLDS=5
DEADBAND=0.05
MAX_T3_PROB_LOSS=0.10

def checksum(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def pass_by(turn,h):
    return int(0<int(turn)<=h)

def features(seven,hand,bottom,unknown,seat,stage,old_q,old_c):
    keep_n=(7,7,6)[stage]
    assert len(seven)==7 and len(hand)==keep_n
    assert Counter(seven)==Counter(hand)+Counter(bottom)
    assert sum(Counter(unknown).values())==92
    arr=base.extract(hand,bottom,Counter(unknown),seat,keep_n)
    initial=dict(zip(base.FEATURES,arr))
    d=base.analytic.d
    more={
      "stage0":float(stage==0),"stage1":float(stage==1),
      "stage2":float(stage==2),
      "seven_land_count":float(sum(base.analytic.is_land(c) for c in seven)),
      "seven_white_count":float(sum(c in base.analytic.WHITE_LANDS for c in seven)),
      "seven_ramp_count":float(sum(c in d.RAMP_PROTECTED for c in seven)),
      "bottom_artifact_count":float(sum(d.is_artifact_perm(c) for c in bottom)),
      "bottom_land_count":float(sum(base.analytic.is_land(c) for c in bottom)),
      "v27_pred_Qkeep":float(old_q),"v27_DP":float(old_c),
      "v27_margin":float(old_q)-float(old_c),
    }
    x=[float(initial[k]) for k in FEATURE_NAMES]+[more[k] for k in FEATURE_EXTRA]
    assert len(x)==len(ALL_NAMES)
    assert all(math.isfinite(v) for v in x)
    return x

def load_data():
    # The old split names do not grant fresh holdout status in v41.
    C,K,sha,v33b_sha=source.load(
        str(ROOT/"benchmark_results/v34_consistent_regret_shards/v34_C_*.json.gz"),
        str(ROOT/"benchmark_results/v34_consistent_regret_shards/v34_K_*.json.gz"))
    selected,continuations,third_sha=conflict.load(
        str(ROOT/"benchmark_results/v34c_forced_keep_shards/v34c_keep_*.json.gz"),
        str(ROOT/"benchmark_results/v34_consistent_regret_shards/v34_C_*.json.gz"))
    assert third_sha==v33b_sha
    assert len(K["train"])==448 and len(selected)==100
    assert len(C)==len(continuations)==28
    # Shared-C is a SINGLE lottery per seat/stage, not 96 independent labels
    # on each selected source hand. Old 'validation' futures already consumed.
    means={}
    for cell,arr in continuations.items():
        allc=arr["calibration"]+arr["replication"]
        assert len(allc)==96
        means[cell]={
          1:sum(pass_by(v,1) for v in allc)/96.,
          2:sum(pass_by(v,2) for v in allc)/96.,
          3:sum(pass_by(v,3) for v in allc)/96.,
        }
    import dack_paired_counterfactual_v1_20261030 as ref
    deck=ref.SLOT_VARIANTS["one_key_34"]
    assert len(deck)==99
    rows=[]
    for q in K["train"]:
        stage=int(q["stage"]);seat=int(q["seat"]);gid=int(q["game_id"])
        if stage>2:continue
        sd=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
        checkseat,orders=ref.stage_slots(sd)
        assert checkseat==seat
        order=orders[stage]
        seven=[deck[slot] for slot in order[:7]]
        unknown=[deck[slot] for slot in order[7:]]
        assert seven==q["seven"]
        assert Counter(seven)==Counter(q["selected_v33b_hand"])+Counter(q["selected_v33b_bottom"])
        outcomes=q["outcomes"]
        assert len(outcomes)==8
        old=float(q["v27_pred_Qkeep_T2"])
        dp=float(q["v27_DP_threshold"])
        x=features(seven,q["selected_v33b_hand"],q["selected_v33b_bottom"],
                   unknown,seat,stage,old,dp)
        rows.append({
           "gid":gid,"seat":seat,"stage":stage,"source":"unbiased_116k_all_stages",
           "x":x,"old_keep":bool(q["v27_would_keep"]),
           "old_q":old,"old_dp":dp,
           "k2":sum(pass_by(t,2) for t in outcomes)/8.,
           "k3":sum(pass_by(t,3) for t in outcomes)/8.,
           "C2":means[(seat,stage)][2],"C3":means[(seat,stage)][3],
           "weight":1/3.,"k_rollouts":8,
           "teacher_action":None,
        })
    for q in selected:
        stage=int(q["stage"]);seat=int(q["seat"]);gid=int(q["game_id"])
        if stage>2:continue
        sd=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
        checkseat,orders=ref.stage_slots(sd)
        assert seat==checkseat
        order=orders[stage]
        seven=[deck[slot] for slot in order[:7]]
        unknown=[deck[slot] for slot in order[7:]]
        assert seven==q["seven"]
        assert Counter(seven)==Counter(q["v33b_hand"])+Counter(q["v33b_bottom"])
        outcomes=q["fresh_keep_futures_by_split"]["calibration"]+q["fresh_keep_futures_by_split"]["replication"]
        assert len(outcomes)==32
        old=float(q["v27_absolute_Qkeep_prediction"])
        dp=float(q["v27_original_DP_threshold"])
        x=features(seven,q["v33b_hand"],q["v33b_bottom"],
                   unknown,seat,stage,old,dp)
        rows.append({
           "gid":gid,"seat":seat,"stage":stage,"source":"selected_v5_v27_115k_first_disagreement",
           "x":x,"old_keep":not bool(q["v5_first_keeps"]),
           "old_q":old,"old_dp":dp,
           "k2":sum(pass_by(t,2) for t in outcomes)/32.,
           "k3":sum(pass_by(t,3) for t in outcomes)/32.,
           "C2":means[(seat,stage)][2],"C3":means[(seat,stage)][3],
           "weight":1.,"k_rollouts":32,
           "teacher_action":bool(q["v5_first_keeps"]),
        })
    assert len(rows)==192+61
    gids=set(r["gid"] for r in rows)
    assert len(gids)==125 and len(set(r["gid"] for r in rows if r["source"].startswith("selected")))==61
    for gid in gids:
        g=[r for r in rows if r["gid"]==gid]
        assert len({q["source"] for q in g})==1
        assert abs(sum(q["weight"] for q in g)-1)<1e-12
    return rows,means,sha,v33b_sha

def fit(train,mode,horizon):
    idx=MODES[mode]
    X=np.asarray([r["x"] for r in train],dtype=float)[:,idx]
    y=np.asarray([r[f"k{horizon}"] for r in train],dtype=float)
    w=np.asarray([r["weight"] for r in train],dtype=float)
    scaler=StandardScaler().fit(X,sample_weight=w)
    z=scaler.transform(X)
    reg=Ridge(alpha=ALPHA).fit(z,y,sample_weight=w)
    return scaler,reg,idx

def predict(fitted,row):
    scaler,reg,idx=fitted
    z=scaler.transform(np.asarray([row["x"]],dtype=float)[:,idx])
    return min(1.,max(0.,float(reg.predict(z)[0])))

def decide(row,p2,p3):
    # If T2 advantage is smaller than deadband, keep the ORIGINAL frozen v27
    # choice; do not turn uncertain model predictions into a mass override.
    old=row["old_keep"]
    diff=p2-row["C2"]
    candidate=(True if diff>DEADBAND else
               False if diff< -DEADBAND else old)
    # Prediction-based safeguard: switching to a T3-worse action by >10pp
    # is prohibited, regardless of T2 signal. The physical T3 label is never
    # used to make a prediction on a heldout row.
    t3signed=(int(candidate)-int(old))*(p3-row["C3"])
    if t3signed < -MAX_T3_PROB_LOSS:
        candidate=old
    return bool(candidate)

def one_fold(rows,train_idx,test_idx,mode):
    train=[rows[i] for i in train_idx]
    f2=fit(train,mode,2);f3=fit(train,mode,3)
    pred=[]
    for i in test_idx:
        r=rows[i];p2=predict(f2,r);p3=predict(f3,r)
        proposed=decide(r,p2,p3)
        pred.append({"gid":r["gid"],"stage":r["stage"],
             "seat":r["seat"],"source":r["source"],"weight":r["weight"],
             "old_keep":r["old_keep"],"new_keep":proposed,
             "teacher_action":r["teacher_action"],
             "pred_K2":p2,"pred_K3":p3,
             "K2":r["k2"],"K3":r["k3"],"C2":r["C2"],"C3":r["C3"],
             "T2_gain":(int(proposed)-int(r["old_keep"]))*(r["k2"]-r["C2"]),
             "T3_gain":(int(proposed)-int(r["old_keep"]))*(r["k3"]-r["C3"])})
    return pred

def summary(rows):
    N=len({r["gid"] for r in rows})
    w=sum(r["weight"] for r in rows)
    changes=[r for r in rows if r["new_keep"]!=r["old_keep"]]
    if not w:return None
    return {
       "outer_groups":N,"stage_states":len(rows),"weighted_groups":w,
       "action_changes":len(changes),
       "keep_to_mull":sum(r["old_keep"] and not r["new_keep"] for r in rows),
       "mull_to_keep":sum(not r["old_keep"] and r["new_keep"] for r in rows),
       "mean_physical_T2_one_step_delta_pp":100*sum(r["weight"]*r["T2_gain"] for r in rows)/w,
       "mean_physical_T3_one_step_delta_pp":100*sum(r["weight"]*r["T3_gain"] for r in rows)/w,
       "selected_source_v5_agreement":(
          sum(r["new_keep"]==r["teacher_action"] for r in rows)/len(rows)
          if all(r["teacher_action"] is not None for r in rows) else None),
    }

def cv(rows,mode):
    rng=random.Random(SEED)
    ids=sorted(set(r["gid"] for r in rows))
    rng.shuffle(ids)
    fold_by_id={gid:i%FOLDS for i,gid in enumerate(ids)}
    assert len(fold_by_id)==125
    outputs=[]
    for fold in range(FOLDS):
        train=[i for i,r in enumerate(rows) if fold_by_id[r["gid"]]!=fold]
        test=[i for i,r in enumerate(rows) if fold_by_id[r["gid"]]==fold]
        assert set(rows[i]["gid"] for i in train).isdisjoint(
               set(rows[i]["gid"] for i in test))
        outputs+=one_fold(rows,train,test,mode)
    assert len(outputs)==len(rows)
    assert len(set((z["gid"],z["stage"]) for z in outputs))==len(rows)
    return outputs

def export(rows,mode,sha,v33b_sha):
    models={}
    for horizon in (2,3):
        scaler,reg,idx=fit(rows,mode,horizon)
        models[f"K{horizon}"]={
          "feature_indices":[int(j) for j in idx],
          "feature_names":[ALL_NAMES[int(j)] for j in idx],
          "scale_mean":[float(z) for z in scaler.mean_],
          "scale":[float(z) for z in scaler.scale_],
          "coefficients":[float(z) for z in reg.coef_],
          "intercept":float(reg.intercept_),
        }
    return {
      "schema":SCHEMA,"status":"EXPERIMENTAL_UNAPPROVED",
      "mode":mode,"model_approved":False,
      "source_physical_groups":125,"stage_states":253,
      "source_v33b_model_sha256":v33b_sha,
      "source_v27_model_hashes":sha,
      "feature_schema":list(ALL_NAMES),
      "gamma_stage_deployment_only":(0,1,2),
      "original_v27_v33b_later_stage_baseline":True,
      "per_game_stage_weighting":True,
      "no_v5_teacher_features_or_labels_in_fit":True,
      "keep_threshold_deadband":DEADBAND,
      "max_predicted_T3_loss":MAX_T3_PROB_LOSS,
      "C_reference":"historical pooled 96 independent C rolls per seat-stage (prior consumed)",
      "models":models,
    }

def run(out,modeldir):
    rows,means,sha,v33b_sha=load_data()
    report={"schema":SCHEMA,"status":"PASS",
       "research_only_no_outcome_acceptance":True,
       "original_v5_teacher_labels_not_fit":True,
       "goldfish_not_multiplayer_wins":True,
       "old_cohorts_115k_116k_117k_ALREADY_consumed":True,
       "all_99_cards_and_v33b_bottom_physically_matched":True,
       "N_original_groups":125,"N_observed_stage_states":253,
       "n_unbiased_groups":64,"n_selected_disagreement_groups":61,
       "K_per_unbiased_stage":8,"K_per_selected_stage":32,
       "C_shared_lottery_per_seat_stage":96,
       "validation_is_exploratory_group_separated_CV_not_prospective":True,
       "feature_count":len(ALL_NAMES),
       "train_teacher_label_used":False,"modes":{}}
    d=Path(modeldir);d.mkdir(parents=True,exist_ok=True)
    for mode in MODES:
        oof=cv(rows,mode)
        strata={name:summary([r for r in oof if r["source"]==name])
                for name in ("unbiased_116k_all_stages",
                             "selected_v5_v27_115k_first_disagreement")}
        strata["all"]=summary(oof)
        strata["stages_0_2"]={str(s):summary([r for r in oof if r["stage"]==s])
                               for s in (0,1,2)}
        m=export(rows,mode,sha,v33b_sha)
        p=d/f"v41_{mode}_early_physical_regret_RESEARCH.json"
        p.write_text(json.dumps(m,indent=2,sort_keys=True)+"\n")
        report["modes"][mode]={
           "source_group_OOF":strata,
           "exported_model":str(p),
           "exported_sha256":checksum(p),
           "confidence_interval_estimated":False,
           "unseen_prospective_validation_passed":False,
           "model_approved":False,
        }
        print("DACK_V41_GROUP_OUT_OF_FOLD_MODE",mode,
              json.dumps(strata,sort_keys=True),flush=True)
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print("DACK_V41_EARLY_PHYSICAL_REGRET_CV_PASS",
          json.dumps({"report":str(p),"n_groups":125,"states":253,
              "modes":list(MODES)},sort_keys=True),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--out",default="benchmark_results/v41_early_physical_regret_cv.json")
    p.add_argument("--models-dir",default="models/v41_early_physical_regret")
    a=p.parse_args();run(a.out,a.models_dir)
