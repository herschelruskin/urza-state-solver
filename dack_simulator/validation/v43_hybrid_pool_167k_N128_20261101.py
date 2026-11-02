#!/usr/bin/env python3
"""Pool the pre-registered four 167k N32 shards; 128 independent source
deals are the only confidence units. No hybrid promotion on this pilot.
"""
from __future__ import annotations
import argparse,gzip,json,random,statistics
from pathlib import Path
N=128;START=167000
def paired(rows,left,right,turn):
    diffs=[int(0<r[right]["turn"]<=turn)-int(0<r[left]["turn"]<=turn) for r in rows]
    rng=random.Random(167043+turn+({"dp":1,"v43":2}.get(left,3)))
    bs=[]
    for _ in range(6000):
        bs.append(100*sum(diffs[rng.randrange(N)] for __ in range(N))/N)
    bs.sort()
    return {"baseline":sum(0<r[left]["turn"]<=turn for r in rows),
        "candidate":sum(0<r[right]["turn"]<=turn for r in rows),
        "gain":diffs.count(1),"loss":diffs.count(-1),
        "delta_pp":round(100*sum(diffs)/N,5),
        "paired_bootstrap95_pp":[bs[149],bs[5849]]}
def main(folder,out):
    shards=sorted(Path(folder).glob("v43hyb_167*.json.gz"))
    assert len(shards)==4,(len(shards),shards)
    rows=[]
    for p in shards:
        with gzip.open(p,"rt") as f:x=json.load(f)
        assert x["status"]=="PASS" and x["N_independent_outer_deals"]==32
        assert x["schema"]=="dack_v43_hybrid_selective_167k_matched_threearm_strict_physical_v1"
        rows+=x["rows"]
    rows.sort(key=lambda r:r["gid"])
    assert [r["gid"] for r in rows]==list(range(START,START+N))
    comparisons={}
    for l,r in (("v43","dp"),("dp","hybrid"),("v43","hybrid")):
        comparisons[f"{r}_vs_{l}"]={str(t):paired(rows,l,r,t) for t in (1,2,3)}
    same=sum((r["dp"]["keep_n"],r["dp"]["hand"],r["dp"]["bottom"])==
             (r["hybrid"]["keep_n"],r["hybrid"]["hand"],r["hybrid"]["bottom"]) for r in rows)
    invoked=sum(r["hybrid"]["fallback_stats"].get("fallback_invoked",0) for r in rows)
    changes=sum(r["hybrid"]["fallback_stats"].get("fallback_changed_keep",0) for r in rows)
    time_tot={mode:sum(r[mode]["elapsed"] for r in rows) for mode in ("v43","dp","hybrid")}
    stage_invocations={str(st):sum(
        int(a.get("fallback_trigger",False)) for r in rows
        for a in r["hybrid"]["history"] if a["stage"]==st) for st in (0,1)}
    report={"schema":"dack_v43_167k_three_arm_strict_real_physical_N128_pooled_v1",
      "status":"PASS","N_independent_outer_deals":N,"gids":[START,START+N-1],
      "units_independent_outer_groups_not_6_mc_policy_samples":True,
      "same_deal_seat_and_actual_chance":True,"physical_beam160":True,
      "reference_frozen_v43":True,
      "intermediate_consistent_model_only_DP":True,
      "fallback_n_sampled_futures":6,
      "hybrid_sampling_triggered_total":invoked,
      "hybrid_sampling_triggered_stage":stage_invocations,
      "hybrid_changed_keep_decisions_total":changes,
      "hybrid_exact_final_hand_parity_with_DP":same,
      "mean_keep":{mode:statistics.mean(r[mode]["keep_n"] for r in rows) for mode in time_tot},
      "children_total_seconds":time_tot,
      "hybrid_runtime_ratio_vs_dp":time_tot["hybrid"]/time_tot["dp"],
      "hybrid_runtime_ratio_vs_v43":time_tot["hybrid"]/time_tot["v43"],
      "paired":comparisons,
      "screening_gate":{
        "changed_at_least_5_full_games":(N-same)>=5,
        "T2_nonnegative_vs_dp":comparisons["hybrid_vs_dp"]["2"]["delta_pp"]>=0,
        "T3_no_more_than_3pp_loss_vs_dp":comparisons["hybrid_vs_dp"]["3"]["delta_pp"]>=-3,
        "hybrid_time_below_1point5x_dp":time_tot["hybrid"]/time_tot["dp"]<=1.5},
      "promoted":False,"not_an_acceptance_benchmark":True,
      "rows":rows}
    path=Path(out);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print("DACK_V43_HYBRID_FRESH_167K_N128_PASS",json.dumps({
      k:report[k] for k in ("hybrid_sampling_triggered_total","hybrid_sampling_triggered_stage",
        "hybrid_changed_keep_decisions_total","hybrid_exact_final_hand_parity_with_DP",
        "hybrid_runtime_ratio_vs_dp","paired","screening_gate")},sort_keys=True),flush=True)
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--folder",required=True);p.add_argument("--out",required=True)
    x=p.parse_args();main(x.folder,x.out)
