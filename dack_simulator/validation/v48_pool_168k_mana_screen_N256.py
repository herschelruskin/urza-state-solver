#!/usr/bin/env python3
"""Summarize untouched 168k first-seven physical feature screen, no fitting.

All 256 source-deal independent observations are confidence units, even
though an individual physical future and a no-draw witness have different
interpretation. Pre-registered descriptive features only.
"""
from __future__ import annotations
import argparse,gzip,json,math,random
from collections import defaultdict
from pathlib import Path
N=256;START=168000
def rate(x):return round(sum(x)/len(x),5) if x else None
def table(rows,feat,t):
    groups={}
    for value in (False,True):
        sub=[r for r in rows if bool(r["feat"][feat])==value]
        groups[str(value)]={"n":len(sub),"physical_success_byT"+str(t):
         sum(0<r["physical_forced_keep_turn"]<=t for r in sub),
         "rate":rate([int(0<r["physical_forced_keep_turn"]<=t) for r in sub])}
    return groups
def brier(rows):
    return round(sum((r["stage0_Q2"]-r["physical_forced_keep_byT2"])**2 for r in rows)/len(rows),6)
def main(folder,out):
    paths=sorted(Path(folder).glob("mana168k_*.json.gz"))
    assert len(paths)==8,(len(paths),paths)
    rows=[]
    for p in paths:
        with gzip.open(p,"rt") as f:q=json.load(f)
        assert q["status"]=="PASS" and q["N_independent_deals"]==32
        assert q["schema"]=="dack_v48_initial7_168k_physical_label_and_legal_mana_features_independent_v1"
        rows+=q["rows"]
    rows.sort(key=lambda r:r["gid"])
    assert [r["gid"] for r in rows]==list(range(START,START+N))
    t2_all=sum(r["physical_forced_keep_byT2"] for r in rows)
    t1_all=sum(r["physical_forced_keep_byT1"] for r in rows)
    w1=sum(r["feat"]["mana_witness_T1_no_draw"] for r in rows)
    w2=sum(r["feat"]["mana_witness_T2_no_draw"] for r in rows)
    contradictions=[{"gid":r["gid"],"seat":r["seat"],"seven":r["seven"],
        "witness_T1":r["feat"]["mana_witness_T1_no_draw"],
        "witness_T2":r["feat"]["mana_witness_T2_no_draw"],
        "physical_turn":r["physical_forced_keep_turn"],
        "T1":r["feat"]["T1"],"T2":r["feat"]["T2"]}
        for r in rows if (r["feat"]["mana_witness_T1_no_draw"] and r["physical_forced_keep_turn"]!=1)
            or (r["feat"]["mana_witness_T2_no_draw"] and not r["physical_forced_keep_byT2"])]
    # Adjacent within-frozen-model-score quartile descriptive comparison.
    # This is not an out-of-sample fitted residual model.
    by_q=sorted(rows,key=lambda r:(r["stage0_Q2"],r["gid"]))
    quart=[]
    for k in range(4):
        rr=by_q[k*64:(k+1)*64]
        quart.append({"quartile":k+1,"n":len(rr),
         "Q2_range":[rr[0]["stage0_Q2"],rr[-1]["stage0_Q2"]],
         "physical_t2":sum(r["physical_forced_keep_byT2"] for r in rr),
         "no_draw_t2_witness":sum(r["feat"]["mana_witness_T2_no_draw"] for r in rr),
         "witness_vs_physical":table(rr,"mana_witness_T2_no_draw",2)})
    # Paired bootstrap of mean T2 outcome difference when a witnessed
    # positive is present. Descriptive association, not causal effect.
    rng=random.Random(16800001)
    rate_diff=rate([r["physical_forced_keep_byT2"] for r in rows if r["feat"]["mana_witness_T2_no_draw"]])
    rate_other=rate([r["physical_forced_keep_byT2"] for r in rows if not r["feat"]["mana_witness_T2_no_draw"]])
    bootstrap=[]
    for _ in range(3000):
        sampled=[rows[rng.randrange(N)] for __ in range(N)]
        pos=[r["physical_forced_keep_byT2"] for r in sampled if r["feat"]["mana_witness_T2_no_draw"]]
        neg=[r["physical_forced_keep_byT2"] for r in sampled if not r["feat"]["mana_witness_T2_no_draw"]]
        if pos and neg:bootstrap.append(100*(rate(pos)-rate(neg)))
    bootstrap.sort()
    result={"schema":"dack_v48_n256_first_seven_legal_mana_feature_research_screen_v1",
       "status":"PASS","n_independent_outer_source_deals":N,
       "gids":[START,START+N-1],"frozen_v43_model":True,
       "forced_keep_T1_count":t1_all,"forced_keep_T2_count":t2_all,
       "first_seven_v43_would_keep":sum(r["stage0_frozen_v43_kept"] for r in rows),
       "T1_no_draw_positive_witness":w1,"T2_no_draw_positive_witness":w2,
       "T1_witness_vs_physical":table(rows,"mana_witness_T1_no_draw",1),
       "T2_witness_vs_physical":table(rows,"mana_witness_T2_no_draw",2),
       "witness_discordance_count":len(contradictions),
       "witness_discordances":contradictions,
       "physical_t2_rate_witness_minus_no_witness_pp":None if rate_diff is None or rate_other is None
          else round(100*(rate_diff-rate_other),5),
       "conditional_association_bootstrap95_pp":
         [round(bootstrap[int(.025*len(bootstrap))],5),round(bootstrap[int(.975*len(bootstrap))-1],5)]
             if bootstrap else None,
       "frozen_v43_Q2_brier_first_seven_conditional_physical":brier(rows),
       "quartiles":quart,
       "mean_feature_seconds":sum(r["feature_seconds"] for r in rows)/N,
       "mean_physical_seconds":sum(r["physical_seconds"] for r in rows)/N,
       "new_features_are_not_probability_calibrated":True,
       "no_teacher_label_training":True,"no_model_train":True,
       "no_155k_or_historical_set":True,
       "not_a_promotion":True,"rows":rows}
    path=Path(out);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print("DACK_V48_N256_FIRST_SEVEN_MANA_SCREEN_PASS",json.dumps({
       k:result[k] for k in ("n_independent_outer_source_deals","forced_keep_T1_count",
         "forced_keep_T2_count","T1_no_draw_positive_witness",
         "T2_no_draw_positive_witness","T1_witness_vs_physical","T2_witness_vs_physical",
         "witness_discordance_count","physical_t2_rate_witness_minus_no_witness_pp",
         "conditional_association_bootstrap95_pp",
         "frozen_v43_Q2_brier_first_seven_conditional_physical",
         "quartiles","mean_feature_seconds")},sort_keys=True),flush=True)
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--folder",required=True);p.add_argument("--out",required=True)
    z=p.parse_args();main(z.folder,z.out)
