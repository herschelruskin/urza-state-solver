#!/usr/bin/env python3
"""Read-only v33b 115k v5/v27 gap audit against frozen 110k.

No new gameplay and NO training or threshold tuning. Distinguish actual
London stage index (0 and 1 both keep seven!) from kept-card count.
Exact kept-hand parity should imply the same strict stable-dice result.
Partitions are descriptive and never causal estimates.
"""
from __future__ import annotations
from collections import Counter,defaultdict
import gzip
import glob
import json
import random
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def load(pattern,expected_schema,first):
    files=sorted(glob.glob(str(ROOT/pattern)))
    assert len(files)==64,(pattern,len(files))
    rows=[];source=None
    for f in files:
        with gzip.open(f,"rt") as z:
            d=json.load(z)
        assert d["schema"]==expected_schema and d["status"]=="PASS"
        if source is None:source=d["source_sha256"]
        assert source==d["source_sha256"]
        rows+=d["rows"]
    rows.sort(key=lambda r:r["game_id"])
    assert [r["game_id"] for r in rows]==list(range(first,first+256))
    for r in rows:
        assert r["v5"]["seat"]==r["v27_frozen"]["seat"]
        assert tuple(r["v5"]["history"][0]["seven_slots"])==tuple(r["v27_frozen"]["history"][0]["seven_slots"])
    return rows

def kind(a,b):
    x=a["history"][-1];y=b["history"][-1]
    if x["stage"]!=y["stage"]:
        return "different_actual_london_stage"
    if Counter(x["hand"])!=Counter(y["hand"]):
        return "same_stage_different_cards"
    return "same_final_hand"

def p(turn,t):
    return int(0<int(turn)<=t)

def contrast(rows,na,nb,t):
    di=[p(r[na]["turn"],t)-p(r[nb]["turn"],t) for r in rows]
    return {"N":len(rows),"gains":di.count(1),"losses":di.count(-1),
            "net_games":sum(di),"delta_pp":100*sum(di)/256,
            "rate_within_subset_pp":100*sum(di)/len(di) if di else None}

def report_one(rows,cohort):
    kinds=defaultdict(list)
    for r in rows:
        kinds[kind(r["v5"],r["v27_frozen"])].append(r)
    cats={}
    for cat in ("same_final_hand","same_stage_different_cards","different_actual_london_stage"):
        rr=kinds[cat]
        cats[cat]={"N":len(rr),
             "T2":contrast(rr,"v5","v27_frozen",2),
             "T3":contrast(rr,"v5","v27_frozen",3)}
        if cat=="same_final_hand":
            assert all(r["v5"]["turn"]==r["v27_frozen"]["turn"] for r in rr)
    byseat={}
    for seat in range(4):
        rr=[r for r in rows if r["v5"]["seat"]==seat]
        byseat[str(seat)]={
          "N":len(rr),
          "v5_T1":sum(r["v5"]["turn"]==1 for r in rr),
          "v27_T1":sum(r["v27_frozen"]["turn"]==1 for r in rr),
          "v5_T2":sum(p(r["v5"]["turn"],2) for r in rr),
          "v27_T2":sum(p(r["v27_frozen"]["turn"],2) for r in rr)}
    stage_details={}
    for who in ("v5","v27_frozen"):
        stage_details[who]={}
        for s in range(8):
            rr=[r for r in rows if r[who]["history"][-1]["stage"]==s]
            stage_details[who][str(s)]={
               "N":len(rr),"T2":sum(p(r[who]["turn"],2) for r in rr),
               "T3":sum(p(r[who]["turn"],3) for r in rr)}
    stage_earliness=Counter()
    for r in kinds["different_actual_london_stage"]:
        a=r["v5"]["history"][-1]["stage"]
        b=r["v27_frozen"]["history"][-1]["stage"]
        stage_earliness["v27_keeps_earlier"]+=int(b<a)
        stage_earliness["v27_keeps_later"]+=int(b>a)
    assert sum(x["N"] for x in cats.values())==256
    return {
       "cohort":cohort,
       "v5_vs_v27_T2":contrast(rows,"v5","v27_frozen",2),
       "v5_vs_v27_T3":contrast(rows,"v5","v27_frozen",3),
       "v5_T1_exact":sum(r["v5"]["turn"]==1 for r in rows),
       "v27_T1_exact":sum(r["v27_frozen"]["turn"]==1 for r in rows),
       "categories":cats,"seat_strata":byseat,
       "stage_distribution":stage_details,
       "different_stage_direction_counts":dict(stage_earliness)}

def bootstrap_gap_shift(old,new,t,seed):
    a=[p(r["v5"]["turn"],t)-p(r["v27_frozen"]["turn"],t) for r in old]
    b=[p(r["v5"]["turn"],t)-p(r["v27_frozen"]["turn"],t) for r in new]
    rng=random.Random(seed)
    out=sorted(100*(sum(b[rng.randrange(256)] for _ in b)-
                   sum(a[rng.randrange(256)] for _ in a))/256
               for _ in range(12000))
    return {"new_minus_old_gap_pp":100*(sum(b)-sum(a))/256,
            "independent_cohort_group_bootstrap_95ci_pp":[out[299],out[11699]]}

def main():
    old=load("benchmark_results/v32_110k_shards/v32_110k_*.json.gz",
        "dack_v32_prospective_110k_three_policy_strict",110000)
    new=load("benchmark_results/v33b_prospective_115k_shards/v33b_115k_*.json.gz",
        "dack_v33b_prospective_115k_three_policy_strict",115000)
    unchanged=0;changed=0
    for r in new:
        a=r["v27_frozen"];b=r["v33b_regret_bottom"]
        assert len(a["history"])==len(b["history"])
        assert all((x["stage"],x["keep_n"],x["kept"])==(
                   y["stage"],y["keep_n"],y["kept"])
                   for x,y in zip(a["history"],b["history"]))
        same=kind(a,b)=="same_final_hand"
        assert same== (not b["history"][-1]["v33b_bottom_only_override"])
        if same:
            unchanged+=1
            assert a["turn"]==b["turn"],("identical hand must replay same",r["game_id"])
        else:changed+=1
    out={
      "schema":"dack_v33b_readonly_two_cohort_london_attribution",
      "status":"PASS",
      "new_model_fitting":False,"new_beam160_evaluations":0,
      "110k_source":"archived v32 paired prospective",
      "115k_source":"archived v33b paired prospective",
      "110k":report_one(old,"110k"),
      "115k":report_one(new,"115k"),
      "independent_cohort_T2_gap_shift":bootstrap_gap_shift(old,new,2,3331152),
      "independent_cohort_T3_gap_shift":bootstrap_gap_shift(old,new,3,3331153),
      "v27_vs_v33b_same_hand_exact_turn_parity_verified":unchanged,
      "v27_vs_v33b_different_final_hands":changed,
      "policy_approved":False,
      "limitation":"Repeated seven card counts must use stage index; cohort variation and descriptive partitions are NOT causal keep/bottom regrets. n256 each has material sampling uncertainty."}
    dest=ROOT/"benchmark_results/v33b_two_cohort_london_attribution.json"
    dest.write_text(json.dumps(out,sort_keys=True,indent=2)+"\n")
    print("DACK_V33B_TWO_COHORT_ATTRIBUTION_PASS",json.dumps({
      "110k_T2_gap":out["110k"]["v5_vs_v27_T2"],
      "115k_T2_gap":out["115k"]["v5_vs_v27_T2"],
      "gap_shift_T2":out["independent_cohort_T2_gap_shift"],
      "115k_same_hand_parity":unchanged,
      "115k_by_class":{c:x["T2"] for c,x in out["115k"]["categories"].items()},
      "115k_stage_directions":out["115k"]["different_stage_direction_counts"]},
      sort_keys=True),flush=True)

if __name__=="__main__":
    main()
