#!/usr/bin/env python3
"""Pool v33b frozen candidate screening by independent outer physical game.

Primary analysis is Qkeep bottom choice minus v14, preregistered; v18 and
analytic scores are controls and require multiplicity caution. Training
and independent validation bands are never merged for model fitting.
Conditional comparisons are NOT full game policy results.
"""
from __future__ import annotations
import argparse
from collections import Counter
import gzip
import glob
import json
import random
from pathlib import Path
from dack_simulator.validation.v33b_bottom_ranker import METHODS

EXPECTED={"train":list(range(112000,112128)),
          "validation":list(range(113000,113064))}
def group_bootstrap(diffs,seed,n=4000):
    if not diffs:return None
    r=random.Random(seed);m=len(diffs)
    b=sorted(100*sum(diffs[r.randrange(m)] for _ in range(m))/m
             for _ in range(n))
    return [b[99],b[3899]]

def evaluate(rows,method,t,include_no_bottom=False):
    diffs=[];changed=0;wins=0;losses=0;ties=0
    for r in rows:
        if r["no_bottom"]:
            if include_no_bottom:diffs.append(0.)
            continue
        base=r["selected"]["v14_frozen"]
        other=r["selected"][method]
        changed+=int(base!=other)
        outcomes=r["outcomes_by_candidate_index"]
        aa=outcomes[str(other)];bb=outcomes[str(base)]
        assert len(aa)==len(bb)==8
        d=sum((0<x<=t)-(0<y<=t) for x,y in zip(aa,bb))/8
        diffs.append(d)
        wins+=int(d>0);losses+=int(d<0);ties+=int(d==0)
    n=len(diffs)
    return {
       "physical_groups":n,
       "changed_bottom_groups":changed,
       "changed_fraction":changed/n if n else None,
       "mean_delta_pp":100*sum(diffs)/n if n else None,
       "paired_group_bootstrap_95ci_pp":group_bootstrap(diffs,11233+t+len(method)),
       "positive_group_differences":wins,
       "negative_group_differences":losses,
       "observed_group_ties":ties}

def main(source,out):
    files=sorted(glob.glob(source))
    if len(files)!=48:
        raise ValueError("expected 32 train + 16 validation shards, got %d" % len(files))
    rows={"train":[],"validation":[]}
    source_sha=None
    seen=set()
    for path in files:
        with gzip.open(path,"rt") as f:doc=json.load(f)
        assert doc["schema"]=="dack_v33b_bottom_screen_fresh_physical_futures"
        assert doc["status"]=="PASS" and doc["futures_per_arm"]==8
        assert doc["physical_groups"]==4
        assert doc["actual_gameplay_beam"]==160
        assert tuple(doc["methods"])==METHODS
        assert doc["same_92_unknown_shuffle_and_chance_seed_between_candidates"]
        assert doc["no_actual_future_order_visible_to_bottom_selector"]
        assert doc["no_training_on_archived_110k_diagnostics"]
        assert not doc["policy_approved"]
        if source_sha is None:source_sha=doc["source_sha"]
        assert doc["source_sha"]==source_sha
        split=doc["split"]
        assert split in rows
        for x in doc["rows"]:
            gid=x["game_id"]
            assert gid in EXPECTED[split] and gid not in seen
            seen.add(gid);rows[split].append(x)
    for split,expected in EXPECTED.items():
        rows[split].sort(key=lambda r:r["game_id"])
        assert [x["game_id"] for x in rows[split]]==expected
    outdoc={"schema":"dack_v33b_existing_bottom_ranker_conditional_screen",
            "status":"PASS","primary_predeclared":"v27_Qkeep vs v14_frozen",
            "methods":METHODS,"source_sha":source_sha,
            "source_ids":{k:[v[0],v[-1]] for k,v in EXPECTED.items()},
            "actual_beam160":True,"model_fitting":False,
            "no_110k_training":True,"not_full_policy_deployment":True,
            "winner_selection_is_not_training":True,
            "prior_bottom_v18_is_oob_beyond_top3":False,
            "limits":["8 paired futures per hand; uncertainty near zero",
                      "Selection under frozen v27 natural kept hands, not v5",
                      "v27 Qkeep is off-policy when used to pick other bottoms",
                      "Chance coupling not perfect across action paths",
                      "T2 primary, T1/T3 safeguards, not multiplayer cEDH"],
            "splits":{}}
    for split,data in rows.items():
        outdoc["splits"][split]={
           "total_groups":len(data),"no_bottom_groups":sum(r["no_bottom"] for r in data),
           "bottom_eligible_groups":sum(not r["no_bottom"] for r in data),
           "metrics":{m:{f"T{t}":evaluate(data,m,t)
                     for t in (1,2,3)}
                   for m in METHODS if m!="v14_frozen"}}
    dest=Path(out);dest.parent.mkdir(exist_ok=True,parents=True)
    dest.write_text(json.dumps(outdoc,sort_keys=True,indent=2)+"\n")
    print("DACK_V33B_CONDITIONAL_SCREEN_POOL_PASS",
          json.dumps({s:{"N":v["bottom_eligible_groups"],
                 "primary_T2":v["metrics"]["v27_Qkeep"]["T2"],
                 "primary_T3":v["metrics"]["v27_Qkeep"]["T3"]}
                 for s,v in outdoc["splits"].items()},sort_keys=True),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source",default="collected/v33b_*.json.gz")
    p.add_argument("--out",default="benchmark_results/v33b_existing_bottom_ranker_screen.json")
    a=p.parse_args();main(a.source,a.out)
