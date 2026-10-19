#!/usr/bin/env python3
"""Matched-game failure/transition audit of Dack Full Beam vs Realistic v1/v2.

Does not infer root cause from win_turn alone. Diagnostic flags identify where
a policy loses a game, not whether the loss is due to legitimate imperfect-
information constraints, candidate pruning, bad heuristic, or search limits.
No gameplay is resimulated; all rows from archived immutable workflow runs.
"""
from __future__ import annotations
import argparse,glob,gzip,hashlib,json,math,statistics
from collections import Counter,defaultdict
from pathlib import Path

VARIANTS=("current","buck_worldmap")
HASH={"current":"3a10a02e1aae070645129fa85ed94240f1ae9d5447e3711f7621f92064d9f129",
      "buck_worldmap":"f130ff4c9c0fbc888525070877fe820caba03e836e0be66ec60ea3410e950068"}
SEED_BASE=7604096001
SCHEMA={"full_current":"boonweaver_exact99_20261016",
        "full_buck":"bucknard_minimal_swaps_20261016",
        "v1":"realistic_info_beam_v1",
        "v2":"realistic_info_beam_v2"}

def get_rows(pattern,variant,required_n,expected_schema=None):
    paths=glob.glob(pattern,recursive=True)
    assert paths,(pattern,"No data files")
    rows={}
    considered=0
    for fn in paths:
        with gzip.open(fn,"rt") as f:q=json.load(f)
        if q["variant"]!=variant:continue
        assert q["deck_sha256"]==HASH[variant],(fn,"deck hash mismatch")
        if expected_schema:
            assert q["schema"]==expected_schema,(fn,q["schema"])
        for r in q["rows"]:
            gid=int(r["game_id"])
            if gid>=required_n:continue
            assert r["seed"]==SEED_BASE+gid*1000003,(fn,gid,"wrong seed")
            assert gid not in rows,(fn,gid,"duplicate")
            assert r["win_turn"] in (0,1,2,3)
            rows[gid]=r;considered+=1
    assert set(rows)==set(range(required_n)),(variant,pattern,len(rows),required_n)
    return rows,considered

def byturn(rows):
    n=len(rows)
    vals={f"T{turn}":round(sum(0<r["win_turn"]<=turn for r in rows.values())/n*100,3)
          for turn in (1,2,3)}
    vals["win_turn_counts"]={str(i):sum(q["win_turn"]==i for q in rows.values()) for i in range(4)}
    return vals

def audit_meta(rows):
    return {
      "n":len(rows),
      "mean_keep":round(statistics.mean(x["keep_n"] for x in rows.values()),3),
      "mean_planning_rollouts":round(statistics.mean(
          x.get("planning_counts",{}).get("rollout_calls",0) for x in rows.values()),2)
          if all("planning_counts" in x for x in rows.values()) else None,
      "mean_pass_candidates_by_turn":{
          str(t):round(statistics.mean(
             next((a.get("pass_candidates",0) for a in r.get("turn_audit",[]) if a["turn"]==t),0)
             for r in rows.values()),2) for t in (1,2,3)},
      "total_bucknard_rolls":sum(len(r.get("rolls",[])) for r in rows.values()),
      "bucknard_roll_histogram":{str(i):sum(y==i for r in rows.values() for y in r.get("rolls",[]))
                                 for i in (1,2,3,4)}
    }

def discordance(high,low):
    assert set(high)==set(low)
    n=len(high)
    out={}
    for turn in (1,2,3):
        both=high_only=low_only=neither=0
        ids_high=[];ids_low=[]
        for gid in sorted(high):
            h=0<high[gid]["win_turn"]<=turn
            l=0<low[gid]["win_turn"]<=turn
            if h and l:both+=1
            elif h:high_only+=1;ids_high.append(gid)
            elif l:low_only+=1;ids_low.append(gid)
            else:neither+=1
        gap=(high_only-low_only)/n*100
        # Include a normal paired difference CI as a descriptive metric.
        d=[int(0<high[i]["win_turn"]<=turn)-int(0<low[i]["win_turn"]<=turn)
           for i in sorted(high)]
        mean=sum(d)/n
        se=math.sqrt(sum((x-mean)**2 for x in d)/((n-1)*n))
        out[f"by_T{turn}"]={
           "both":both,"high_only":high_only,"low_only":low_only,"neither":neither,
           "high_minus_low_pp":round(gap,3),
           "paired_95pct_pp":[round((mean-1.96*se)*100,3),round((mean+1.96*se)*100,3)],
           "high_only_ids":ids_high,"low_only_ids":ids_low}
    return out

def explicit_cases(full,v1,v2,n):
    cases=[]
    for gid in range(n):
        f=full[gid];x=v1[gid];y=v2[gid]
        cases.append({
            "id":gid,"seat":f["seat"],"full":f["win_turn"],
            "v1":x["win_turn"],"v2":y["win_turn"],
            "keep_full":f["keep_n"],"keep_v1":x["keep_n"],
            "keep_v2":y["keep_n"],
            "full_T2_but_v2_not":0<f["win_turn"]<=2 and not 0<y["win_turn"]<=2,
            "full_T3_but_v2_not":0<f["win_turn"]<=3 and not 0<y["win_turn"]<=3,
            "v1_T3_failure_recovered_v2":not 0<x["win_turn"]<=3 and 0<y["win_turn"]<=3,
            "v2_lost_v1_T3":0<x["win_turn"]<=3 and not 0<y["win_turn"]<=3,
            "v2_turn_audit":y.get("turn_audit",[]),
            "v2_rollouts":y.get("planning_counts",{}).get("rollout_calls"),
            "v2_rolls":y.get("rolls",[])
        })
    return cases

def breakdown(cases):
    def picked(flag):
        return [x for x in cases if x[flag]]
    categories={}
    for attr in ("full_T2_but_v2_not","full_T3_but_v2_not",
                 "v1_T3_failure_recovered_v2","v2_lost_v1_T3"):
        subset=picked(attr)
        categories[attr]={
            "n":len(subset),"ids":[r["id"] for r in subset],
            "no_bucknard_rolls_in_v2":sum(not r["v2_rolls"] for r in subset),
            "same_mulligan_keep_size_as_full":sum(r["keep_full"]==r["keep_v2"] for r in subset),
            "mean_v2_rollouts":round(statistics.mean(r["v2_rollouts"] for r in subset),2) if subset else None,
            "mean_v2_T1_pass_candidates":round(statistics.mean(
              next((m.get("pass_candidates",0) for m in r["v2_turn_audit"]
                    if m["turn"]==1),0) for r in subset),2) if subset else None}
    return categories

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--full-current",default="full_current/**/*.json.gz")
    p.add_argument("--full-buck",default="full_buck/**/*.json.gz")
    p.add_argument("--v1",default="v1/**/*.json.gz")
    p.add_argument("--v2",default="v2/**/*.json.gz")
    p.add_argument("--n",type=int,default=32)
    p.add_argument("--n-v1",type=int,default=64)
    p.add_argument("--out",default="dack_realistic_beam_failure_audit_n32_20261019.json")
    a=p.parse_args()
    assert a.n>=2 and a.n_v1>=a.n
    arms={}
    for v in VARIANTS:
        full,fn=get_rows(a.full_current if v=="current" else a.full_buck,
                         v,a.n,SCHEMA["full_current" if v=="current" else "full_buck"])
        v1,ns1=get_rows(a.v1,v,a.n_v1,SCHEMA["v1"])
        v2,ns2=get_rows(a.v2,v,a.n,SCHEMA["v2"])
        s1={i:v1[i] for i in range(a.n)}
        s1_64=v1
        cases=explicit_cases(full,s1,v2,a.n)
        arms[v]={
          "n":a.n,
          "win_rates":{
            "full_beam":byturn(full),"realistic_v1":byturn(s1),
            "realistic_v2":byturn(v2),
            "realistic_v1_all64":byturn(s1_64)},
          "full_minus_v2":discordance(full,v2),
          "v2_minus_v1":discordance(v2,s1),
          "full_minus_v1":discordance(full,s1),
          "v1_64_meta":audit_meta(s1_64),
          "v2_meta":audit_meta(v2),
          "gap_categories":breakdown(cases),
          "per_game_trace_summaries":cases,
          "audited_rows":{"full":fn,"v1":ns1,"v2":ns2}
        }
    # Only direct paired contrasts, no claim of a causal source of gap.
    report={
      "status":"PASS","date":"2026-10-19","n_paired":a.n,
      "design":"Exact same game IDs Full Beam vs Realistic v1 vs Realistic v2, turn thresholds and per-game failure cases",
      "arm_results":arms,
      "interpretation_constraints":[
          "Failure classification is descriptive: a Full-only success does not prove illicit hindsight.",
          "Realistic v2 and Full Beam use different beam widths and future-planning budgets.",
          "Full Beam and Realistic Beam use different mulligan evaluations on Bucknard; keep_n differences can confound comparisons.",
          "Game scripts lack complete action traces; no reliable card-by-card root cause can be inferred from these archives alone.",
          "Most Realistic v2 game outcomes do not activate Bucknard; no-roll games do not imply equivalent performance in both arms.",
          "An oracle can pick the best turn-1 path conditioned on the exact unseen turn-2 draw even with zero tutors.",
          "Post-scry/tutorial revealed cards and shuffle/draw action boundaries are not completely information-safe.",
          "Do not promote this audit or small-N differences to a calibrated live-game win rate."
       ]
    }
    Path(a.out).write_text(json.dumps(report,indent=2)+"\n")
    print("DACK_MATCHED_FAILURE_AUDIT_PASS",json.dumps({
       v:{"rates":arms[v]["win_rates"],
          "T2_full_minus_v2":{k:z for k,z in arms[v]["full_minus_v2"]["by_T2"].items() if not k.endswith("_ids")},
          "T3_full_minus_v2":{k:z for k,z in arms[v]["full_minus_v2"]["by_T3"].items() if not k.endswith("_ids")},
          "categories":arms[v]["gap_categories"]}
       for v in VARIANTS}),flush=True)

if __name__=="__main__":main()
