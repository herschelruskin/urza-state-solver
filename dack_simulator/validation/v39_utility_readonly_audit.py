#!/usr/bin/env python3
"""Read-only v39 posterior multi-objective utility on the exact SAME 131k outcomes.

No new beam; no model, threshold, or candidate tuning. Ucum =
PbyT2 + .5 PbyT3 and Uexact =
PbyT2 + .5 PexactlyT3 = .5(PbyT2+PbyT3).
Use SAME resampled physical game turn for both cumulative metrics
within each hand or shared C future: never add marginal confidence
intervals or separately shuffle T2/T3 rollouts.
All 3072 physical game-stage states remain in denominator.
"""
from __future__ import annotations
import argparse,json,random,hashlib
from collections import defaultdict
from pathlib import Path
from dack_simulator.validation import v39_131k_pool as base

def by2(t):return int(0<int(t)<=2)
def by3(t):return int(0<int(t)<=3)
def util(t,kind):
    if kind=="cumulative":return by2(t)+.5*by3(t)
    if kind=="exact3":return by2(t)+.5*int(t==3)
    raise ValueError(kind)

def records(allstates,keep,C,kind):
    c={key:sum(util(t,kind) for t in vals)/len(vals)
       for key,vals in C.items() if vals}
    out=[]
    for r in allstates:
        k=(r["game_id"],r["stage"])
        sign=int(r["new_keep"])-int(r["old_keep"])
        z=(sign*(sum(util(t,kind) for t in keep[k])/len(keep[k])-
                 c[(r["seat"],r["stage"])])) if sign else 0.
        out.append({"gid":r["game_id"],"stage":r["stage"],"seat":r["seat"],
          "changed":bool(sign),"gain":z,
          "direction":"to_MULL" if sign==-1 else "to_KEEP" if sign==1 else "same"})
    return out

def boot(states,keep,C,kind,B=5000):
    seed=390133 if kind=="cumulative" else 390134
    rng=random.Random(seed)
    bygid=defaultdict(list)
    for r in states:
        if r["changed"]:bygid[r["game_id"]].append(r)
    ids=list(range(base.LO,base.HI+1))
    arr=[]
    for _ in range(B):
        cmean={}
        for cell,turns in C.items():
            if turns:
                cmean[cell]=sum(util(turns[rng.randrange(len(turns))],kind)
                    for _ in range(len(turns)))/len(turns)
        diff=0.
        for _ in range(base.GROUPS):
            gid=ids[rng.randrange(len(ids))]
            for r in bygid.get(gid,()):
                k=(gid,r["stage"]);terms=keep[k]
                observed=sum(util(terms[rng.randrange(len(terms))],kind)
                    for _ in range(len(terms)))/len(terms)
                sign=int(r["new_keep"])-int(r["old_keep"])
                diff+=sign*(observed-cmean[(r["seat"],r["stage"])])
        arr.append(100*diff/(base.GROUPS*len(base.STAGES)))
    arr.sort()
    return [arr[int(.025*B)],arr[int(.975*B)-1]]

def mean(rows):
    return 100*sum(x["gain"] for x in rows)/len(rows)

def run(K,C,out):
    census,states,changed,keep,shared=base.load(K,C)
    assert census["actual_action_changes"]==47
    assert len(states)==3072 and len(changed)==47
    assert all(abs(util(t,"cumulative")-(1.5*by2(t)+.5*int(t==3)))<1e-12
               for t in range(4))
    assert all(abs(util(t,"exact3")-.5*(by2(t)+by3(t)))<1e-12
               for t in range(4))
    result={
      "schema":"dack_v39_131k_POSTHOC_readonly_correlated_two_utility_comparison",
      "status":"PASS","policy_approved":False,
      "posthoc_descriptive_not_a_second_independent_validation":True,
      "reused_all_original_131k_true_physical_outcomes":True,
      "new_beam160_rollouts":0,
      "full_random_outer_physical_games":1024,
      "all_population_stage_states":3072,
      "policy_changes":47,
      "shared_outcome_turn_for_T2_and_T3_metric_in_every_bootstrap":True,
      "two_independent_reward_definitions_not_interchangeable":True,
      "source_census_sha256":hashlib.sha256(base.CENSUS.read_bytes()).hexdigest(),
      "outcomes":{}
    }
    for kind in ("cumulative","exact3"):
        rows=records(states,keep,shared,kind)
        rr={
          "mean_action_policy_gain_pp":mean(rows),
          "physical_outer_group_shared_C_two_source_95ci_pp":boot(states,keep,shared,kind),
          "changed_action_count":sum(z["changed"] for z in rows),
          "beneficial_changed":sum(z["gain"]>0 for z in rows),
          "harmful_changed":sum(z["gain"]<0 for z in rows),
          "by_stage":{str(stage):{"mean_gain_pp":mean([z for z in rows if z["stage"]==stage]),
              "changes":sum(z["changed"] for z in rows if z["stage"]==stage)}
              for stage in base.STAGES}
        }
        result["outcomes"][kind]=rr
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("DACK_V39_NEW131K_READONLY_CORRELATED_UTILITY_AUDIT_PASS",
          json.dumps(result["outcomes"],sort_keys=True),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--K",default="benchmark_results/v39_131k_physical_shards/v39_K_*.json.gz")
    p.add_argument("--C",default="benchmark_results/v39_131k_physical_shards/v39_C_*.json.gz")
    p.add_argument("--out",default="benchmark_results/v39_131k_readonly_two_utility_comparison.json")
    a=p.parse_args();run(a.K,a.C,a.out)
