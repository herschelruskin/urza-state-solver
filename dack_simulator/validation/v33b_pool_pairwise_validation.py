#!/usr/bin/env python3
"""Pool 114k independent physical-game heldout pairwise-bottom validation.

Never tune on these outcomes. Report T1/T2/T3 conditional success, group
bootstrap and changed-action counts; do not claim prospective full-game
winrate or globally optimal bottom selection.
"""
from __future__ import annotations
from collections import Counter
import argparse
import gzip
import glob
import hashlib
import json
import random
from pathlib import Path

LO=114000;HI=114063;N=64;FUTURES=8

def result(rows,t,only_changed=False):
    records=[]
    for g in rows:
        if g["no_bottom"]:
            if not only_changed:records.append(0.)
            continue
        b=int(g["baseline_index"]);q=int(g["regret_index"])
        if only_changed and b==q:continue
        arms=g["outcomes_by_candidate"]
        base=arms[str(b)];new=arms[str(q)]
        assert len(base)==len(new)==FUTURES
        d=sum(int(0<k<=t)-int(0<v<=t) for k,v in zip(new,base))/FUTURES
        records.append(d)
    n=len(records)
    if not n:return {"N":0,"delta_pp":None,"bootstrap_95ci_pp":None}
    rng=random.Random(114008+t+(int(only_changed)*17))
    boot=sorted(100*sum(records[rng.randrange(n)] for _ in range(n))/n
                for _ in range(6000))
    return {
      "N_independent_physical_groups":n,
      "delta_pp":100*sum(records)/n,
      "bootstrap_95ci_pp":[boot[149],boot[5849]],
      "positive_groups":sum(x>0 for x in records),
      "negative_groups":sum(x<0 for x in records),
      "observed_tied_groups":sum(x==0 for x in records)
    }

def main(source,out):
    paths=sorted(glob.glob(source))
    assert len(paths)==16,("need 16 validation physical shards",len(paths))
    sha=None;rows=[]
    for file in paths:
        with gzip.open(file,"rt") as f:d=json.load(f)
        assert d["schema"]=="dack_v33b_pairwise_regret_114k_independent_validation"
        assert d["status"]=="PASS" and d["futures_per_selected_arm"]==8
        assert d["strict_beam"]==160 and d["physical_groups"]==4
        assert d["v27_keep_depth_frozen"] and d["v14_default_fallback"]
        assert d["new_hidden_futures_only"] and d["no_training_or_tuning_on_114k"]
        assert d["only_training_supported_candidate_generators"]
        assert d["policy_approved"] is False
        if sha is None:sha=d["model_sha256"]
        assert sha==d["model_sha256"]
        rows+=d["rows"]
    rows.sort(key=lambda x:x["game_id"])
    assert [r["game_id"] for r in rows]==list(range(LO,HI+1))
    changes=[r for r in rows if r["baseline_index"]!=r["regret_index"]]
    report={
       "schema":"dack_v33b_regret_114k_heldout_N64",
       "status":"PASS","group_ids":[LO,HI],
       "model_sha256":sha,
       "all_independent_physical_groups":N,
       "bottom_eligible_groups":sum(not r["no_bottom"] for r in rows),
       "no_bottom_groups":sum(r["no_bottom"] for r in rows),
       "changed_bottom_groups":len(changes),
       "stage_counts":dict(sorted(Counter(str(r["stage"]) for r in rows).items())),
       "change_stage_counts":dict(sorted(Counter(str(r["stage"]) for r in changes).items())),
       "not_prospective_end_to_end_policy":True,
       "no_validation_fit_or_threshold_tuning":True,
       "strict_actual_beam160":True,
       "policy_approved":False,
       "all_groups_T1T2T3":{f"T{t}":result(rows,t) for t in (1,2,3)},
       "changed_group_conditional_T1T2T3":{
           f"T{t}":result(rows,t,True) for t in (1,2,3)},
       "limitations":["Bootstrap grouped by independently dealt game not rollout",
                      "Only eight new futures per action",
                      "Unseen chance effects imperfectly coupled across different actions",
                      "Keep decisions are frozen v27 not re-optimized",
                      "Deployment is goldfish not opponent-interactive win probability"]}
    dest=Path(out);dest.parent.mkdir(exist_ok=True,parents=True)
    dest.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print("DACK_V33B_REGRET_INDEPENDENT_VALIDATION_PASS",
          json.dumps({k:v for k,v in report.items() if k in
          ("all_groups_T1T2T3","changed_bottom_groups","bottom_eligible_groups",
           "no_bottom_groups","changed_group_conditional_T1T2T3")},sort_keys=True),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source",default="collected/v33b_regret_*.json.gz")
    p.add_argument("--out",default="benchmark_results/v33b_regret_114k_validation_N64.json")
    a=p.parse_args();main(a.source,a.out)
