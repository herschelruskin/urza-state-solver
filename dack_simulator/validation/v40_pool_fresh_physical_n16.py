#!/usr/bin/env python3
"""Pool 16 untouched real physical policy game results, report paired differences.

N16 is an engineering/pilot check only, not statistically credible promotion.
"""
from __future__ import annotations
import argparse,glob,gzip,json,random
from pathlib import Path
POLICIES=("v5","v27","v40_full","v40_portable")
def by(t,h):return int(0<int(t)<=h)

def run(source,out):
    paths=sorted(glob.glob(source))
    assert len(paths)==4,(len(paths),"four N4 shards required")
    rows=[];sha=None
    for p in paths:
        with gzip.open(p,"rt") as f:d=json.load(f)
        assert d["schema"]=="dack_v40_paired_strict_beam160_physical_pilot_v1"
        assert d["status"]=="PASS" and d["pilot_only_not_approval"]
        assert d["no_training_or_threshold_tuning_on_147k"]
        assert tuple(d["policies"])==POLICIES and d["goldfish_beam"]==160
        if sha is None:sha=d["source_model_sha256"]
        assert sha==d["source_model_sha256"]
        rows.extend(d["rows"])
    rows.sort(key=lambda x:x["game_id"])
    assert [r["game_id"] for r in rows]==list(range(147000,147016))
    n=len(rows);summaries={};paired={}
    for p in POLICIES:
        turns=[r[p]["turn"] for r in rows]
        summaries[p]={f"by_T{h}":sum(by(t,h) for t in turns) for h in (1,2,3)}
        summaries[p]["mean_kept_n"]=sum(r[p]["keep_n"] for r in rows)/n
        summaries[p]["seconds"]=sum(r[p]["seconds"] for r in rows)
        assert summaries[p]["by_T1"]<=summaries[p]["by_T2"]<=summaries[p]["by_T3"]
    for p in ("v27","v40_full","v40_portable"):
        paired[p]={}
        for h in (1,2,3):
            diffs=[by(r[p]["turn"],h)-by(r["v5"]["turn"],h) for r in rows]
            rng=random.Random(147020+h+sum(ord(c) for c in p))
            boots=sorted(100*sum(diffs[rng.randrange(n)] for _ in range(n))/n
                         for _ in range(4000))
            paired[p][f"T{h}"]={
              "delta_vs_original_v5_pp":100*sum(diffs)/n,
              "gains":diffs.count(1),"losses":diffs.count(-1),
              "paired_bootstrap_95ci_pp":[boots[100],boots[3899]],
            }
    report={
      "schema":"dack_v40_frozen_student_vs_original_v5_147k_N16_engineering_pilot",
      "status":"PASS","N":n,"source_model_sha256":sha,
      "outcome":"goldfish Dack deployment, not multiplayer cEDH wins",
      "no_model_tuning_on_test":True,
      "small_N_uncertainty_not_a_model_promotion":True,
      "metrics":summaries,"paired":paired}
    o=Path(out);o.parent.mkdir(parents=True,exist_ok=True)
    o.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print("DACK_V40_N16_PROSPECTIVE_PILOT_POOL_PASS",
          json.dumps({"n":n,"metrics":summaries,"paired":paired},sort_keys=True),
          flush=True)

if __name__=="__main__":
    a=argparse.ArgumentParser()
    a.add_argument("--source",required=True)
    a.add_argument("--out",required=True)
    x=a.parse_args();run(x.source,x.out)
