#!/usr/bin/env python3
"""Pool v34c causal KEEP-vs-MULL comparisons on all actual 115k disagreements.

Under EXACT common fixed v33b downstream continuation, estimate
the per-hand causal advantage of the earliest-stage v5 action over
v27 action from 32 NEW keep futures and independent v34 shared
Qmull distributions. Bootstrap BOTH physical groups and shared
seat-stage C lotteries. This is NOT a full v5-v27 winrate contrast.
"""
from __future__ import annotations
from collections import Counter,defaultdict
import argparse,gzip,glob,json,random
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
K_SPLITS=("calibration","replication")
Q_SPLITS={"calibration":"train","replication":"untouched_validation"}
TOTAL=100

def y(t,turn):
    return int(0<int(turn)<=t)

def load(kpattern,cpattern):
    files=sorted(glob.glob(kpattern))
    assert len(files)==8,("need 8 replay shards",len(files))
    groups=[];sha=None
    for f in files:
        with gzip.open(f,"rt") as z:d=json.load(z)
        assert d["schema"]=="dack_v34c_115k_earliest_actual_stage_disagreement_forced_keep"
        assert d["status"]=="PASS" and d["total_eligible_groups"]==TOTAL
        assert d["selected_only_on_actual_policy_stage_disagreement"]
        assert d["original_115k_win_turn_never_read_for_selection"]
        assert d["actual_beam160"] and d["futures_per_split"]==16
        assert d["Qmull_rollouts_here"]==0 and not d["policy_approved"]
        if sha is None:sha=d["frozen_v33b_model_sha256"]
        assert sha==d["frozen_v33b_model_sha256"]
        groups+=d["rows"]
    groups.sort(key=lambda r:r["game_id"])
    assert len(groups)==TOTAL and len(set(r["game_id"] for r in groups))==TOTAL
    for r in groups:
        assert r["v5_kept_stage"]!=r["v27_kept_stage"]
        assert r["stage"]==min(r["v5_kept_stage"],r["v27_kept_stage"])<7
        assert r["v5_first_keeps"]==(r["v5_kept_stage"]<r["v27_kept_stage"])
        assert r["original_115k_result_not_used_in_selection_or_label"]
        assert all(len(r["fresh_keep_futures_by_split"][s])==16 for s in K_SPLITS)
    cf=sorted(glob.glob(cpattern))
    assert len(cf)==28,("all v34 shared continuation groups required",len(cf))
    cont={}
    for path in cf:
        with gzip.open(path,"rt") as f:d=json.load(f)
        assert d["schema"]=="dack_v34_shared_Qmull_exact_frozen_v33b_downstream"
        assert d["status"]=="PASS" and d["strict_beam160"]
        assert d["all_99_returned_each_future_stage"]
        assert d["downstream_policy_matched_for_training_validation"]
        assert d["v33b_model_sha256"]==sha
        key=(int(d["seat"]),int(d["stage"]))
        assert key not in cont
        assert len(d["results"])==96
        cont[key]={
          "calibration":[r["turn"] for r in d["results"] if r["split"]=="train"],
          "replication":[r["turn"] for r in d["results"] if r["split"]=="untouched_validation"],
        }
        assert len(cont[key]["calibration"])==64
        assert len(cont[key]["replication"])==32
    assert len(cont)==28
    return groups,cont,sha

def turns(group,split):
    a=group["fresh_keep_futures_by_split"]
    if split=="pooled":
        return a["calibration"]+a["replication"]
    return a[split]

def continuations(cont,cell,split):
    cc=cont[cell]
    if split=="pooled":return cc["calibration"]+cc["replication"]
    return cc[split]

def one(group,cont,split,t):
    seat=group["seat"];stage=group["stage"]
    k=turns(group,split)
    c=continuations(cont,(seat,stage),split)
    pk=sum(y(turn,t) for turn in k)/len(k)
    pm=sum(y(turn,t) for turn in c)/len(c)
    signed=(1 if group["v5_first_keeps"] else -1)*(pk-pm)
    return {"game_id":group["game_id"],"seat":seat,"stage":stage,
         "v5_keeps_first":group["v5_first_keeps"],
         "Pkeep":pk,"Pmull":pm,
         "Qkeep_minus_Qmull":pk-pm,
         "v5_action_minus_v27_action":signed}

def summary(details):
    n=len(details)
    if not n:return None
    return {
       "N_independent_disagreement_groups":n,
       "mean_v5_action_minus_v27_action_T2_or_T3_pp":
             100*sum(z["v5_action_minus_v27_action"] for z in details)/n,
       "mean_unsigned_Qkeep_minus_Qmull_pp":
             100*sum(z["Qkeep_minus_Qmull"] for z in details)/n,
       "positive_observed_groups":sum(z["v5_action_minus_v27_action"]>0 for z in details),
       "negative_observed_groups":sum(z["v5_action_minus_v27_action"]<0 for z in details),
       "observed_tied_groups":sum(z["v5_action_minus_v27_action"]==0 for z in details),
       "mean_Pkeep":sum(z["Pkeep"] for z in details)/n,
       "mean_Pmull":sum(z["Pmull"] for z in details)/n
    }

def dual_bootstrap(groups,cont,split,t,iters=5000):
    rng=random.Random(34134+t+(len(split)*100))
    n=len(groups)
    assert n==TOTAL
    boot=[]
    cells=set((g["seat"],g["stage"]) for g in groups)
    src={cell:continuations(cont,cell,split) for cell in cells}
    nkeep=len(turns(groups[0],split))
    base=[turns(g,split) for g in groups]
    for rep in range(iters):
        cdict={}
        for cell,arr in src.items():
            nc=len(arr)
            # Resample source continuing policy lottery ONCE per cell,
            # reusing that shared value across all selected hands.
            cdict[cell]=sum(y(arr[rng.randrange(nc)],t) for _ in range(nc))/nc
        tot=0.
        for _ in range(n):
            idx=rng.randrange(n)
            g=groups[idx]
            aa=base[idx]
            # Keep within-hand replay variance explicit alongside
            # outer independent physical-game uncertainty.
            pk=sum(y(aa[rng.randrange(nkeep)],t) for _ in range(nkeep))/nkeep
            c=cdict[(g["seat"],g["stage"])]
            sign=1 if g["v5_first_keeps"] else -1
            tot+=sign*(pk-c)
        boot.append(100*tot/n)
    boot.sort()
    return {
      "2.5_percentile_pp":boot[int(.025*iters)],
      "97.5_percentile_pp":boot[int(.975*iters)-1],
      "bootstrap_physical_group_and_keep_future_and_shared_C":True}

def pool(K,C,out):
    groups,cont,sha=load(K,C)
    bydirection=Counter("v5_keeps_first" if r["v5_first_keeps"]
                        else "v27_keeps_first" for r in groups)
    counts=Counter(r["stage"] for r in groups)
    assert sum(bydirection.values())==100
    report={
       "schema":"dack_v34c_actual_policy_disagreement_two_action_value",
       "status":"PASS","policy_approved":False,
       "selection_source_115k_ids":[115000,115255],
       "n_selected_policy_disagreement_groups":len(groups),
       "selected_only_on_different_KEPT_ACTUAL_LONDON_STAGE":True,
       "source_frozen_v33b_model_sha256":sha,
       "selection_not_based_on_realized_outcome":True,
       "frozen_common_downstream_v27_keep_v33b_bottom":True,
       "keep_futures_per_group_per_split":16,
       "shared_earlier_v34_Qmull_futures_per_cell":{
          "calibration":64,"replication":32,"pooled":96},
       "different_stage_first_action_counts":dict(bydirection),
       "earliest_disagreement_stage_counts":{str(k):v for k,v in sorted(counts.items())},
       "no_new_Qmull_or_v5_beam":True,
       "no_fit_no_new_policy":True,"analyses":{}}
    for split in ("calibration","replication","pooled"):
        this={"splits_independent_action_simulations":split!="pooled"}
        for t in (1,2,3):
            details=[one(g,cont,split,t) for g in groups]
            all_stats=summary(details)
            all_stats["two_source_group_bootstrap_95ci_pp"]=dual_bootstrap(groups,cont,split,t)
            all_stats["by_v5_kept_first"]=summary([z for z in details if z["v5_keeps_first"]])
            all_stats["by_v27_kept_first"]=summary([z for z in details if not z["v5_keeps_first"]])
            all_stats["by_earliest_stage"]={
                str(s):summary([z for z in details if z["stage"]==s])
                for s in sorted(counts)}
            this[f"T{t}"]=all_stats
        report["analyses"][split]=this
    report["limitations"]=[
      "This is a SAME-continuation one-step action causal contrast, not original v5 full policy outcome",
      "Original 115k cohort was already inspected; this is a targeted diagnostic not unselected prospective generalization",
      "Current v33b bottom differs from v5 teacher's choice",
      "Future v33b policy is fixed after forced MULL, not an optimized new Bellman policy",
      "Shared continuation values reuse archived but independent 116k/117k physical results",
      "The first two seven-card stages remain distinct",
      "Chance coupling is statistical across independently seeded physical futures",
      "No model tuning or decision policy promotion"]
    dest=Path(out);dest.parent.mkdir(exist_ok=True,parents=True)
    dest.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print("DACK_V34C_CAUSAL_DISAGREEMENT_REGRET_PASS",json.dumps({
      "selected":len(groups),
      "directions":dict(bydirection),
      "calibration_T2":report["analyses"]["calibration"]["T2"],
      "replication_T2":report["analyses"]["replication"]["T2"],
      "pooled_T2":report["analyses"]["pooled"]["T2"],
      "pooled_T3":report["analyses"]["pooled"]["T3"],
    },sort_keys=True),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--K",default="collected/v34c_keep_*.json.gz")
    p.add_argument("--C",default="benchmark_results/v34_consistent_regret_shards/v34_C_*.json.gz")
    p.add_argument("--out",default="benchmark_results/v34c_actual_keep_mull_disagreement_regret.json")
    a=p.parse_args();pool(a.K,a.C,a.out)
