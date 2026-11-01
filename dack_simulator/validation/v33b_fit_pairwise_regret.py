#!/usr/bin/env python3
"""Fit 16 regularized, group-bootstrap linear T2/T3 action-regret models.

ONLY 112k physical train group labels; no 113k observed validation and
no 110k outcome labels. Sample actions exactly from four predeclared
zero-beam candidate rankers; no added imaginary oracle candidate.
"""
from __future__ import annotations
import gzip
import glob
import hashlib
import json
import math
import random
import sys
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import dack_mulligan_v33b_capability_regret_features as feats
import dack_mulligan_v33b_pairwise_regret as reg
import dack_paired_counterfactual_v27_T2_only_DP_20261101 as frozen

def run(source,out,report):
    assert frozen.audit()["status"]=="PASS"
    files=sorted(glob.glob(source))
    assert len(files)==32,("need 32 archived training shards",len(files))
    deck=Counter(frozen.ref.VARIANTS["one_key_34"])
    by_gid=defaultdict(list)
    source_sha=None;file_shas={}
    n_eligible=0
    for file in files:
        data=Path(file).read_bytes()
        file_shas[Path(file).name]=hashlib.sha256(data).hexdigest()
        with gzip.open(file,"rt") as f:r=json.load(f)
        assert r["schema"]=="dack_v33b_bottom_screen_fresh_physical_futures"
        assert r["split"]=="train" and r["status"]=="PASS"
        assert r["futures_per_arm"]==8 and r["actual_gameplay_beam"]==160
        assert r["same_92_unknown_shuffle_and_chance_seed_between_candidates"]
        assert r["no_training_on_archived_110k_diagnostics"]
        if source_sha is None:source_sha=r["source_sha"]
        assert r["source_sha"]==source_sha
        for group in r["rows"]:
            gid=int(group["game_id"])
            assert 112000<=gid<112128
            assert gid not in by_gid
            by_gid[gid]=[]  # Include zero-alternative and seven-card physical groups.
            if group["no_bottom"]:
                continue
            n_eligible+=1
            seven=tuple(group["seven"])
            remain=deck-Counter(seven)
            assert sum(remain.values())==92
            unknown=tuple(c for c,n in remain.items() for _ in range(n))
            base=group["selected"]["v14_frozen"]
            baseline_hand=tuple((Counter(seven)-Counter(group["selected_bottoms"]["v14_frozen"])).elements())
            base_rollouts=group["outcomes_by_candidate_index"][str(base)]
            assert len(base_rollouts)==8
            for idx in sorted(set(group["selected"].values())):
                if idx==base:continue
                method=next(m for m,v in group["selected"].items() if v==idx)
                bh=tuple((Counter(seven)-Counter(group["selected_bottoms"][method])).elements())
                delta=feats.difference(baseline_hand,bh,unknown,int(group["seat"]))
                future=group["outcomes_by_candidate_index"][str(idx)]
                assert len(future)==8
                y2=sum(int(0<x<=2)-int(0<z<=2)
                       for x,z in zip(future,base_rollouts))/8
                y3=sum(int(0<x<=3)-int(0<z<=3)
                       for x,z in zip(future,base_rollouts))/8
                by_gid[gid].append((delta,y2,y3))
    assert sorted(by_gid)==list(range(112000,112128))
    assert n_eligible>32
    groups=[gid for gid,v in by_gid.items() if v]
    assert len(groups)>32
    samples=[x[0] for gid in groups for x in by_gid[gid]]
    scales=[max(.25,math.sqrt(sum(x[i]*x[i] for x in samples)/len(samples)))
            for i in range(len(feats.NAMES))]
    rng=random.Random(330128)
    ensemble=[]
    for b in range(reg.BOOTS):
        chosen=[groups[rng.randrange(len(groups))] for _ in groups]
        training_rows=[]
        for gid in chosen:
            records=by_gid[gid]
            for delta,y2,y3 in records:
                training_rows.append((delta,y2,y3,1./len(records)))
        beta2,beta3=reg.solve_ridge(training_rows,scales)
        ensemble.append({"T2":beta2,"T3":beta3})
    model={
       "schema":reg.SCHEMA,
       "feature_sha256":feats.feature_hash(),
       "feature_names":list(feats.NAMES),
       "feature_scales":scales,
       "lambda_ridge":reg.LAMBDA,
       "group_bootstrap_models":reg.BOOTS,
       "training_source_ids":[112000,112127],
       "physical_training_groups":128,
       "bottom_eligible_groups":n_eligible,
       "training_groups_with_alternative":len(groups),
       "training_pairs":len(samples),
       "training_futures_per_candidate":8,
       "training_source_model_shas":source_sha,
       "training_source_files_sha256":file_shas,
       "prediction_type":"paired relative T2,T3 values, not absolute keep probability",
       "supported_proposals":["v14_frozen","v27_Qkeep","v18_top3","analytic_t2"],
       "T2_lower_quartile_override_min":reg.T2_MIN_LOWER,
       "T3_median_guard_min":reg.T3_MIN_MEDIAN,
       "not_a_formal_uncertainty_interval":True,
       "not_Bellman_recalibrated":True,
       "heldout_113k_not_used":True,
       "heldout_114k_reserved_for_validation":True,
       "policy_approved":False,"ensemble":ensemble}
    dest=Path(out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(model,sort_keys=True,separators=(",",":"))+"\n")
    meta={
       "schema":"dack_v33b_training_diagnostic",
       "status":"PASS","models_fit":reg.BOOTS,
       "physical_groups":128,"eligible":n_eligible,
       "groups_with_paired_signal":len(groups),"pairs":len(samples),
       "nonzero_empirical_T2_pair_labels":sum(int(abs(y2)>1e-8)
                     for gid in groups for _,y2,_ in by_gid[gid]),
       "nonzero_empirical_T3_pair_labels":sum(int(abs(y3)>1e-8)
                     for gid in groups for _,_,y3 in by_gid[gid]),
       "model_hash_sha256":hashlib.sha256(dest.read_bytes()).hexdigest(),
       "no_validation_data_fit":True,"policy_approved":False}
    dst=Path(report);dst.parent.mkdir(exist_ok=True,parents=True)
    dst.write_text(json.dumps(meta,sort_keys=True,indent=2)+"\n")
    print("DACK_V33B_RIDGE_REGRET_FIT_PASS",json.dumps(meta,sort_keys=True),flush=True)

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--source",default="benchmark_results/v33b_bottom_screen_shards/v33b_train_*.json.gz")
    p.add_argument("--model",default="models/dack_v33b_ridge_regret_EXPERIMENTAL.json")
    p.add_argument("--report",default="benchmark_results/v33b_ridge_fit_diagnostic.json")
    a=p.parse_args();run(a.source,a.model,a.report)
