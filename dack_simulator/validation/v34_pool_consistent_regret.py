#!/usr/bin/env python3
"""v34 pool true keep-vs-shared-mull, fit ONLY predeclared small correction.

Train: 116k QKEEP and independently generated train Q(MULL) lotteries.
Untouched conditional validation: 117k QKEEP and independent Q(MULL)
validation lotteries. Matched physical game group is bootstrap unit,
and shared-Qmull validation lottery is ALSO resampled in each iteration.
No refitting on validation, no game-engine or frozen-policy mutation.
"""
from __future__ import annotations
from collections import Counter,defaultdict
import gzip,glob,json,math,random
from pathlib import Path

STAGES=range(7)
SEATS=range(4)
N_TRAIN=64
N_VALID=32
K_FUTURES=8
SHRINK_KEEP=.50
SHRINK_MULL=.50
DEADBAND=.03

def yes(turn,t):
    return int(0<int(turn)<=t)

def load(source_c,source_k):
    cfiles=sorted(glob.glob(source_c))
    kfiles=sorted(glob.glob(source_k))
    if len(cfiles)!=28 or len(kfiles)!=24:
        raise ValueError(("need complete physical shards",len(cfiles),len(kfiles)))
    C={};source_sha=None;source_model=None
    for file in cfiles:
        with gzip.open(file,"rt") as f:d=json.load(f)
        assert d["schema"]=="dack_v34_shared_Qmull_exact_frozen_v33b_downstream"
        assert d["status"]=="PASS" and d["strict_beam160"]
        assert d["all_99_returned_each_future_stage"]
        assert d["downstream_policy_matched_for_training_validation"]
        assert d["policy_approved"] is False
        cell=(int(d["seat"]),int(d["stage"]))
        assert cell not in C and cell[0] in SEATS and cell[1] in STAGES
        if source_sha is None:
            source_sha=d["source_sha256"];source_model=d["v33b_model_sha256"]
        assert source_sha==d["source_sha256"]
        assert source_model==d["v33b_model_sha256"]
        assert len(d["results"])==N_TRAIN+N_VALID
        for split,n in (("train",N_TRAIN),("untouched_validation",N_VALID)):
            rows=[r for r in d["results"] if r["split"]==split]
            assert len(rows)==n and sorted(r["trial"] for r in rows)==list(range(n))
            assert all(0<=r["turn"]<=3 and r["kept_at_actual_london_stage"]>=cell[1]+1 for r in rows)
        C[cell]=d["results"]
    assert set(C)==set((seat,stage) for seat in SEATS for stage in STAGES)
    K={"train":[],"untouched_validation":[]}
    ids={"train":set(),"untouched_validation":set()}
    for file in kfiles:
        with gzip.open(file,"rt") as f:d=json.load(f)
        assert d["schema"]=="dack_v34_true_Qkeep_frozen_v33b_all_stages"
        assert d["status"]=="PASS" and d["actual_beam160"]
        assert d["futures_per_stage"]==K_FUTURES
        assert d["all_stages_sampled_independent_of_actual_keeping"]
        assert d["frozen_v27_Qkeep_and_bottom_v33b"]
        assert d["policy_approved"] is False
        assert source_model==d["v33b_model_sha256"]
        assert source_sha["v27_value"]==d["v27_model_sha256"]
        split=d["split"];assert split in K
        expected=(116000,116063) if split=="train" else (117000,117031)
        for r in d["rows"]:
            gid=int(r["game_id"])
            assert expected[0]<=gid<=expected[1]
            assert r["stage"] in STAGES and r["seat"] in SEATS
            assert 0<=r["v27_pred_Qkeep_T2"]<=1
            assert 0<=r["v27_DP_threshold"]<=1
            assert len(r["outcomes"])==K_FUTURES
            assert all(v in (0,1,2,3) for v in r["outcomes"])
            assert len(r["selected_v33b_hand"])==r["keep_n"]
            assert len(r["selected_v33b_bottom"])==7-r["keep_n"]
            assert abs(r["empirical_Qkeep_T2"]-
                    sum(yes(v,2) for v in r["outcomes"])/K_FUTURES)<1e-12
            K[split].append(r)
            ids[split].add(gid)
    assert ids["train"]==set(range(116000,116064))
    assert ids["untouched_validation"]==set(range(117000,117032))
    assert len(K["train"])==N_TRAIN*7 and len(K["untouched_validation"])==N_VALID*7
    for split in K:
        counts=Counter((r["game_id"],r["stage"]) for r in K[split])
        assert len(counts)==len(K[split]) and all(v==1 for v in counts.values())
    return C,K,source_sha,source_model

def cont_values(C,split,t):
    out={}
    for key,rows in C.items():
        sub=[r for r in rows if r["split"]==split]
        out[key]=sum(yes(r["turn"],t) for r in sub)/len(sub)
    return out

def old_thresholds(K):
    C={}
    for split in K:
        for r in K[split]:
            key=(r["seat"],r["stage"])
            val=r["v27_DP_threshold"]
            if key in C:assert abs(val-C[key])<1e-10
            else:C[key]=val
    assert set(C)==set((seat,stage) for seat in SEATS for stage in STAGES)
    return C

def train_model(K,C,old):
    train=K["train"]
    b={}
    for stage in STAGES:
        rr=[r for r in train if r["stage"]==stage]
        assert len(rr)==N_TRAIN
        b[str(stage)]=sum(r["empirical_Qkeep_T2"]-r["v27_pred_Qkeep_T2"]
                          for r in rr)/len(rr)
    ca=cont_values(C,"train",2)
    thresholds={}
    for (seat,stage),true_c in ca.items():
        thresholds[f"{seat}:{stage}"]=SHRINK_MULL*true_c+(1-SHRINK_MULL)*old[(seat,stage)]
    return {
       "schema":"dack_v34_fixed_shrunk_Qkeep_Qmull_policy_1",
       "trained_only_on_116k_true_keep_and_frozen_v33b_train_Qmull":True,
       "heldout_117k_not_used_for_coefficients":True,
       "v33b_bottom_fixed":True,
       "group_ids_train":[116000,116063],
       "seat_stage_Qmull_train_futures":N_TRAIN,
       "train_Qkeep_futures_per_stage":K_FUTURES,
       "bias_by_actual_stage":b,
       "C_by_seat_stage":thresholds,
       "shrink_Qkeep_bias":SHRINK_KEEP,
       "shrink_Qmull_true_vs_v27_DP":SHRINK_MULL,
       "decision_deadband":DEADBAND,
       "fixed_no_tuning_on_validation":True,
       "unapproved":True
    }

def decisions(r,model):
    old_keep=bool(r["v27_would_keep"])
    s=int(r["stage"]);seat=int(r["seat"])
    pred=max(0.,min(1.,r["v27_pred_Qkeep_T2"]+
                 SHRINK_KEEP*model["bias_by_actual_stage"][str(s)]))
    c=model["C_by_seat_stage"][f"{seat}:{s}"]
    diff=pred-c
    candidate=(True if diff>DEADBAND else
               False if diff < -DEADBAND else old_keep)
    return old_keep,candidate,pred,c,diff

def compare(rows,model,Cval):
    stats={"total_stage_states":len(rows),
        "stages":{},"changes":0,"keep_to_mull":0,"mull_to_keep":0,
        "sum_gain_T2":0.,"sum_gain_T3":0.,"sum_abs_gain_T2":0.}
    vals=[]
    for r in rows:
        old,new,pred,c,diff=decisions(r,model)
        k2=r["empirical_Qkeep_T2"]
        k3=r["empirical_Qkeep_T3"]
        m2=Cval[(r["seat"],r["stage"],2)]
        m3=Cval[(r["seat"],r["stage"],3)]
        d2=(int(new)-int(old))*(k2-m2)
        d3=(int(new)-int(old))*(k3-m3)
        vals.append((int(r["game_id"]),int(r["stage"]),d2,d3,int(new!=old),
                     int(old and not new),int(not old and new)))
        stats["sum_gain_T2"]+=d2;stats["sum_gain_T3"]+=d3
        stats["sum_abs_gain_T2"]+=abs(d2)
        stats["changes"]+=int(new!=old)
        stats["keep_to_mull"]+=int(old and not new)
        stats["mull_to_keep"]+=int(not old and new)
    n=len(rows)
    stats["mean_T2_gain_pp"]=100*stats["sum_gain_T2"]/n
    stats["mean_T3_gain_pp"]=100*stats["sum_gain_T3"]/n
    for stage in STAGES:
        xx=[q for q in vals if q[1]==stage]
        stats["stages"][str(stage)]={
          "N":len(xx),"changes":sum(q[4] for q in xx),
          "mean_T2_gain_pp":100*sum(q[2] for q in xx)/len(xx),
          "mean_T3_gain_pp":100*sum(q[3] for q in xx)/len(xx)}
    return stats,vals

def bootstrap(rows,model,C,n=4000):
    by_gid=defaultdict(list)
    for r in rows:by_gid[int(r["game_id"])].append(r)
    gids=sorted(by_gid)
    assert len(gids)==N_VALID
    for gid in gids:assert len(by_gid[gid])==7
    cr={}
    for cell,allrows in C.items():
        rr=[r["turn"] for r in allrows if r["split"]=="untouched_validation"]
        assert len(rr)==N_VALID
        cr[cell]=rr
    rng=random.Random(344101)
    mean2=[];mean3=[];changed=[]
    for i in range(n):
        Cval={}
        for (seat,stage),data in cr.items():
            draw=[data[rng.randrange(N_VALID)] for _ in range(N_VALID)]
            for t in (2,3):
                Cval[(seat,stage,t)]=sum(yes(v,t) for v in draw)/N_VALID
        sample=[r for _ in range(N_VALID)
                for r in by_gid[gids[rng.randrange(N_VALID)]]]
        result,_=compare(sample,model,Cval)
        mean2.append(result["mean_T2_gain_pp"])
        mean3.append(result["mean_T3_gain_pp"])
        changed.append(result["changes"])
    out={}
    for name,values in (("T2",mean2),("T3",mean3),("n_changes",changed)):
        values.sort()
        out[name]={"2.5_percentile":values[int(.025*n)],
                   "97.5_percentile":values[int(.975*n)-1]}
    return out

def main(csource,ksource,out,modelpath):
    C,K,sha,modelsha=load(csource,ksource)
    old=old_thresholds(K)
    model=train_model(K,C,old)
    train2=cont_values(C,"train",2)
    val2=cont_values(C,"untouched_validation",2)
    val3=cont_values(C,"untouched_validation",3)
    Cval={(seat,stage,2):val2[(seat,stage)]
          for seat in SEATS for stage in STAGES}
    Cval.update({(seat,stage,3):val3[(seat,stage)]
          for seat in SEATS for stage in STAGES})
    # Training comparison is not an unbiased acceptance statistic.
    Ctrain3=cont_values(C,"train",3)
    T={(seat,stage,2):train2[(seat,stage)]
       for seat in SEATS for stage in STAGES}
    T.update({(seat,stage,3):Ctrain3[(seat,stage)]
       for seat in SEATS for stage in STAGES})
    train_diag,_=compare(K["train"],model,T)
    heldout,details=compare(K["untouched_validation"],model,Cval)
    uncertainty=bootstrap(K["untouched_validation"],model,C)
    old_pred={
      str(s):{
        "mean_original_Qkeep":sum(r["v27_pred_Qkeep_T2"]
                 for r in K["train"] if r["stage"]==s)/N_TRAIN,
        "mean_true_Qkeep_train":sum(r["empirical_Qkeep_T2"]
                 for r in K["train"] if r["stage"]==s)/N_TRAIN,
        "mean_true_Qkeep_untouched":sum(r["empirical_Qkeep_T2"]
                 for r in K["untouched_validation"] if r["stage"]==s)/N_VALID,
        "mean_original_Qkeep_untouched":sum(r["v27_pred_Qkeep_T2"]
                 for r in K["untouched_validation"] if r["stage"]==s)/N_VALID
      } for s in STAGES}
    model["downstream_v33b_model_sha256"]=modelsha
    model["source_v27_shas"]=sha
    p=Path(modelpath);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(model,sort_keys=True,indent=2)+"\n")
    result={
       "schema":"dack_v34_shared_consistent_keep_mull_conditional_117k_validation",
       "status":"PASS","policy_approved":False,
       "training_true_Qkeep_physical_groups":N_TRAIN,
       "untouched_validation_Qkeep_physical_groups":N_VALID,
       "train_Qmull_futures_per_seat_stage":N_TRAIN,
       "validation_Qmull_futures_per_seat_stage":N_VALID,
       "stage_count":7,"seat_count":4,
       "physical_rollouts_keep":(N_TRAIN+N_VALID)*7*K_FUTURES,
       "physical_rollouts_mull":28*(N_TRAIN+N_VALID),
       "no_simulator_beam_policy_search":True,
       "no_model_tuning_on_117k":True,
       "sampled_all_stages_not_actual_path_distribution":True,
       "model_not_Bellman_refit_for_new_keep_decisions":True,
       "brier_calibration_source":"direct actual physical T2 outcome, no v5 action labels",
       "stage_Qkeep_calibration":old_pred,
       "old_seat_stage_C_T2":{f"{a}:{b}":c for (a,b),c in old.items()},
       "train_seat_stage_C_T2":{f"{a}:{b}":c for (a,b),c in train2.items()},
       "heldout_seat_stage_C_T2":{f"{a}:{b}":c for (a,b),c in val2.items()},
       "train_conditional_not_for_acceptance":train_diag,
       "heldout_conditional_action_comparison":heldout,
       "heldout_two_source_group_bootstrap_95ci":uncertainty,
       "heldout_one_step_group_differences":details,
       "caveats":[
         "One-step conditional action value across all hypothetical stages",
         "Do not call it a prospective end-to-end mulligan winrate",
         "32 future draws per seat-stage continuation validation cell",
         "Qkeep labels have only eight independent hidden-92 trials per hand",
         "No candidate may be promoted if validation gain is uncertain or negative",
         "T3 only a safeguard; original objective strictly T2"]
    }
    q=Path(out);q.parent.mkdir(parents=True,exist_ok=True)
    q.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("DACK_V34_CONSISTENT_REGRET_SCREEN_PASS",json.dumps({
       "train":train_diag,"heldout":heldout,"uncertainty":uncertainty,
       "calibration":old_pred},sort_keys=True),flush=True)

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--C",default="collected/v34_C_*.json.gz")
    p.add_argument("--K",default="collected/v34_K_*.json.gz")
    p.add_argument("--out",default="benchmark_results/v34_consistent_keep_mull_117k_screen.json")
    p.add_argument("--model",default="models/dack_v34_fixed_shrunk_keep_mull_EXPERIMENTAL.json")
    a=p.parse_args();main(a.C,a.K,a.out,a.model)
