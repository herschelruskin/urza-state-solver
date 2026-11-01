#!/usr/bin/env python3
"""Physical stage0/1 Qkeep residual calibration, frozen before dev outcomes.

Train 128 independent physical groups (2 seven-card stages each) with 24
strict real beam160 future trials. 64 disjoint dev groups also have K24.
SHARED C128 per seat/stage: first 64 estimate frozen training C reference,
second 64 never used to fit the model / make policy decisions and evaluate
actual dev action regret. All group resampling pairs stage0 and stage1,
but latter is a hypothetical state if first stage kept.
No original v5 labels, no hand-bottom choice, no 155k test access.
"""
from __future__ import annotations
import argparse,gzip,glob,hashlib,json,random,sys
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import numpy as np
from sklearn.ensemble import RandomForestRegressor
import dack_mulligan_teacher_features_v13_20261031 as f

SCHEMA="dack_v46_train_frozen_early_seven_physical_Q2_residual_v1"
SOURCE="dack_v46_independent_first_two_sevens_K24_C128_physical_source_v1"
TREES=80;DEPTH=7;LEAF=8;SHRINK=0.5;CLIP=0.25;DEADBAND=0.06
INDICES=tuple(i for i,s in enumerate(f.FEATURES) if not s.startswith(("seven:","bottom:")))
NINPUT=len(INDICES)+1
def by(t,h):return int(0<int(t)<=h)
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def read_k(pattern):
    paths=sorted(glob.glob(pattern));assert len(paths)==24,("need 24 complete shards",len(paths))
    groups={};fp=[]
    for path in paths:
        with gzip.open(path,"rt") as file:z=json.load(file)
        assert z["schema"]==SOURCE and z["status"]=="PASS" and z["kind"]=="K"
        assert z["K_futures_each"]==24 and z["physical_state_rows"]==16
        assert z["real_99_cards_and_physical_beam160"] and z["full_seven_kept_no_bottom_choice"]
        assert z["K_hidden_order_blind_to_decisions"] and z["train_dev_disjoint_source_groups"]
        assert z["stage1_is_hypothetical_not_always_reached"] and z["v5_teacher_not_used"]
        fp.append((Path(path).name,digest(path)))
        for r in z["rows"]:
            gid=int(r["gid"])
            assert len(r["seven"])==7 and len(r["keep_turns"])==24
            assert sum(r["unknown_counts"].values())==92
            assert len(set((gid,int(r["stage"])) for r in [r]))==1
            assert r["stage"] in (0,1)
            target="train" if gid<160128 else "dev"
            assert z["split"]==target
            assert (gid,r["stage"]) not in groups
            groups[(gid,r["stage"])]=r
    assert len(groups)==384
    assert {g for g,s in groups}==set(range(160000,160192))
    assert all((g,0) in groups and (g,1) in groups for g in range(160000,160192))
    return groups,fp

def read_c(pattern):
    paths=sorted(glob.glob(pattern));assert len(paths)==8
    cells={};sha=[]
    for path in paths:
        with gzip.open(path,"rt") as file:z=json.load(file)
        assert z["status"]=="PASS" and z["schema"]==SOURCE and z["kind"]=="C"
        assert z["true_v43_frozen_full99_continuation"]
        assert z["restores_all_99_cards_and_new_london_shuffles"]
        assert z["seat_stage_C_shared_not_independent_per_hand"]
        assert z["C_futures"]==128 and len(z["turns"])==128
        assert z["v5_teacher_not_used"]
        key=(int(z["seat"]),int(z["stage"]))
        assert key not in cells and key[0] in range(4) and key[1] in (0,1)
        cells[key]=z["turns"]
        sha.append((Path(path).name,digest(path)))
    assert len(cells)==8
    return cells,sha

def feats(row):
    seven=row["seven"]
    unknown=Counter(row["unknown_counts"])
    assert sum(unknown.values())==92
    from dack_simulator.validation.collect_teacher_london_v13 import finalists
    finalists_=finalists(seven,7,unknown)
    assert len(finalists_)==1
    c=finalists_[0]
    assert not c["bottom"] and list(c["hand"])==list(seven)
    full=f.extract(seven,c["hand"],c["bottom"],unknown,
          row["seat"],7,row["stage"],c["struct_rank"],0)
    assert len(full)==len(f.FEATURES)
    q=float(row["v43_raw_Q2"])
    x=[float(full[i]) for i in INDICES]+[q]
    assert len(x)==NINPUT
    return x

def fit(rows):
    X=np.asarray([feats(r) for r in rows],dtype=np.float32)
    y=np.asarray([sum(by(t,2) for t in r["keep_turns"])/24.-
                  float(r["v43_raw_Q2"]) for r in rows],dtype=np.float64)
    model=RandomForestRegressor(n_estimators=TREES,max_depth=DEPTH,
       min_samples_leaf=LEAF,max_features=0.7,bootstrap=True,
       random_state=461046,n_jobs=2)
    model.fit(X,y)
    return model

def trees(model):
    out=[]
    for tree in model.estimators_:
        q=tree.tree_
        out.append({"left":q.children_left.tolist(),
                    "right":q.children_right.tolist(),
                    "feature":q.feature.tolist(),
                    "threshold":q.threshold.tolist(),
                    "value":q.value[:,0,0].tolist()})
    assert len(out)==TREES
    return out

def corrected(model,x,q):
    residual=float(model.predict(np.asarray([x],dtype=np.float32))[0])
    return max(0.,min(1.,q+SHRINK*max(-CLIP,min(CLIP,residual))))

def physical_C(cells,which):
    assert which in ("train","eval")
    lo,hi=(0,64) if which=="train" else (64,128)
    return {key:{h:sum(by(t,h) for t in turns[lo:hi])/64.
                 for h in (1,2,3)} for key,turns in cells.items()}

def choose(row,adjusted,c_reference):
    q0=float(row["v43_raw_Q2"])
    base=bool(row["v43_keep"])
    assert base==(q0>=float(row["v43_DP_threshold"]))
    c=float(c_reference[(row["seat"],row["stage"])][2])
    margin=adjusted-c
    # Small model-vs-C differences are inconclusive, preserve frozen v43.
    return base if abs(margin)<DEADBAND else margin>0

def test_dev(groups,cells,model):
    trainC=physical_C(cells,"train")
    evalC=physical_C(cells,"eval")
    allrows=[]
    for gid in range(160128,160192):
        for stage in (0,1):
            r=groups[(gid,stage)]
            q0=float(r["v43_raw_Q2"]);qp=corrected(model,feats(r),q0)
            candidate=choose(r,qp,trainC)
            old=bool(r["v43_keep"])
            state={"gid":gid,"stage":stage,"seat":r["seat"],
               "v43_keep":old,"new_keep":candidate,"changed":old!=candidate,
               "v43_pred_Q2":q0,"calibrated_pred_Q2":qp,
               "train_C_64_Q2":trainC[(r["seat"],stage)][2],
               "K_turns":r["keep_turns"]}
            for h in (1,2,3):
                K=sum(by(t,h) for t in r["keep_turns"])/24
                C=evalC[(r["seat"],stage)][h]
                state[f"physical_T{h}_delta"]=(int(candidate)-int(old))*(K-C)
            allrows.append(state)
    assert len(allrows)==128
    def summarize(rows):
        if not rows:return None
        return {"N_hypothetical_stage_states":len(rows),
            "N_source_groups":len({r["gid"] for r in rows}),
            "changed_actions":sum(r["changed"] for r in rows),
            "old_KEEP_to_new_MULL":sum(r["v43_keep"] and not r["new_keep"] for r in rows),
            "old_MULL_to_new_KEEP":sum(not r["v43_keep"] and r["new_keep"] for r in rows),
            **{f"physical_T{h}_one_step_gain_pp":
                100*sum(r[f"physical_T{h}_delta"] for r in rows)/len(rows)
                for h in (1,2,3)}}
    overall=summarize(allrows)
    rng=random.Random(461128)
    B=2400
    vals={2:[],3:[]}
    bygid={g:[r for r in allrows if r["gid"]==g] for g in range(160128,160192)}
    for _ in range(B):
        # One shared C lottery per seat+stage cell per bootstrap replicate.
        cboot={}
        for cell,ts in cells.items():
            sub=[ts[64+rng.randrange(64)] for z in range(64)]
            cboot[cell]={h:sum(by(t,h) for t in sub)/64 for h in (2,3)}
        delta={2:0.,3:0.}
        for _ in range(64):
            g=rng.randrange(160128,160192)
            for r in bygid[g]:
                sign=int(r["new_keep"])-int(r["v43_keep"])
                if sign==0:continue
                k=[r["K_turns"][rng.randrange(24)] for j in range(24)]
                for h in (2,3):
                    delta[h]+=sign*(sum(by(t,h) for t in k)/24-cboot[(r["seat"],r["stage"])][h])
        for h in (2,3):vals[h].append(100*delta[h]/128.)
    ci={}
    for h in (2,3):
        a=sorted(vals[h]);ci[f"T{h}"]=[a[59],a[2339]]
    return {"overall":overall,
            "stage0":summarize([r for r in allrows if r["stage"]==0]),
            "stage1_hypothetical":summarize([r for r in allrows if r["stage"]==1]),
            "direction_KEEP_to_MULL":summarize([r for r in allrows if r["v43_keep"] and not r["new_keep"]]),
            "direction_MULL_to_KEEP":summarize([r for r in allrows if not r["v43_keep"] and r["new_keep"]]),
            "C_reference_train_64":{f"{s}_{stage}":z for (s,stage),z in trainC.items()},
            "C_validation_eval_64":{f"{s}_{stage}":z for (s,stage),z in evalC.items()},
            "group_K_future_shared_C_bootstrap_95ci_pp":ci,
            "dev_action_comparisons":allrows}

def run(kpat,cpat,model_out,report_out):
    groups,ksha=read_k(kpat)
    cells,csha=read_c(cpat)
    train=[groups[(g,s)] for g in range(160000,160128) for s in (0,1)]
    rf=fit(train)
    o={
      "schema":SCHEMA,"status":"EXPERIMENTAL_UNAPPROVED",
      "policy_approved":False,"original_deck":"one_key_34",
      "train_groups":128,"training_stage_states":256,
      "train_ids":[160000,160127],"dev_excluded_ids":[160128,160191],
      "K_futures_per_stage":24,"C_futures_per_seat_stage":128,
      "source_shards_sha256":ksha+csha,
      "feature_hash":f.feature_hash(),
      "feature_indices":list(INDICES),
      "feature_names":[f.FEATURES[i] for i in INDICES]+["v43_predicted_Q2"],
      "model_input_n":NINPUT,
      "T2_physical_residual_vs_frozen_v43_Q2":True,
      "stage0_1_only_no_bottom_choices":True,
      "shrinkage":SHRINK,"residual_clip_abs":CLIP,"deadband":DEADBAND,
      "C_train_64_futures_only":{f"{a}_{b}":z for (a,b),z in physical_C(cells,"train").items()},
      "forest_trees":trees(rf),
    }
    assert all(x["feature"] for x in o["forest_trees"])
    # Exported scorer parity tested elsewhere before any deployment.
    modelp=Path(model_out);modelp.parent.mkdir(parents=True,exist_ok=True)
    modelp.write_text(json.dumps(o,sort_keys=True,separators=(",",":"))+"\n")
    dev=test_dev(groups,cells,rf)
    gain=dev["overall"]["physical_T2_one_step_gain_pp"]
    t3=dev["overall"]["physical_T3_one_step_gain_pp"]
    # Directional diagnostic, not yet a full-game success or approval.
    gate=bool(gain>0.0 and t3>=-2.0 and dev["overall"]["changed_actions"]>0)
    report={
       "schema":SCHEMA,"status":"PASS","N_training_source_deals":128,
       "N_development_source_deals":64,
       "N_dev_hypothetical_early_stage_states":128,
       "model_approved":False,
       "train_and_dev_K_source_groups_disjoint":True,
       "C_train_first64_distinct_from_C_dev_eval_last64":True,
       "C_shared_one_lottery_per_seat_stage_not_per_hand":True,
       "second_seven_hypothetical_not_naturally_always_reached":True,
       "no_teacher_action_or_original_v5_labels":True,
       "frozen_v43_base_and_later_stage_policy_unchanged":True,
       "dev_not_used_for_fit_or_hyperparameter_selection":True,
       "not_a_prospective_full_game_winrate":True,
       "model_sha256":digest(modelp),
       "predeclared_directional_dev_gate_passed":gate,
       "gate":"mean conditional T2 >0 and mean conditional T3 >=-2pp and nonzero changes",
       "dev":dev,
    }
    reportp=Path(report_out);reportp.parent.mkdir(parents=True,exist_ok=True)
    reportp.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print("DACK_V46_EARLY_SEVEN_GROUP_DISJOINT_TRAIN_DEV_PASS",
       json.dumps({"gate":gate,"all":dev["overall"],
         "stage0":dev["stage0"],"stage1":dev["stage1_hypothetical"],
         "CI":dev["group_K_future_shared_C_bootstrap_95ci_pp"]},sort_keys=True),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--K",required=True);p.add_argument("--C",required=True)
    p.add_argument("--model",required=True);p.add_argument("--out",required=True)
    q=p.parse_args();run(q.K,q.C,q.model,q.out)
