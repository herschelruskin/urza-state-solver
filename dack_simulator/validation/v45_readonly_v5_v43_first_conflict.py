#!/usr/bin/env python3
"""Read-only N128 matched 151k v5 vs v43 exact London decomposition.

Same physical 99 slots, seat and stable dice. No new v5 or physical games.
Source cohort already inspected: no prospective inference. First actual
KEEP/MULL disagreement only: never count hypothetical later histories.
"""
from __future__ import annotations
import gzip,glob,json
from pathlib import Path
from collections import Counter,defaultdict

ROOT=Path(__file__).resolve().parents[2]
SCHEMA="dack_v45_original_v5_vs_coupled_v43_actual_151k_first_conflict_N128"
def success(t,h):return int(0<int(t)<=h)

def read():
    v5={}
    ps=sorted(glob.glob(str(ROOT/"benchmark_results/v43_v5_151k_N128_shards/v43_original_v5_151k_*.json.gz")))
    assert len(ps)==8,("original-v5 reference incomplete",len(ps))
    for p in ps:
        with gzip.open(p,"rt") as f:z=json.load(f)
        assert z["status"]=="PASS" and z["schema"]=="dack_v43_same_151k_original_v5_reference_N128_shard"
        assert z["original_v5_with_no_modifications"]
        for r in z["rows"]:
            gid=int(r["game_id"]);assert gid not in v5;v5[gid]=r
    assert set(v5)==set(range(151000,151128))
    v43={}
    ps=sorted(glob.glob(str(ROOT/"benchmark_results/v43_fresh_151k_maxQ2_shards/v43_151k_*.json.gz")))
    assert len(ps)==8
    for p in ps:
        with gzip.open(p,"rt") as f:z=json.load(f)
        assert z["status"]=="PASS" and z["schema"]=="dack_v43_fresh_151k_v27_vs_maxQ2_N256_paired_shard"
        for r in z["rows"]:
            gid=int(r["gid"])
            if gid in v5:
                assert gid not in v43
                v43[gid]=r["maxQ2"]
    assert set(v5)==set(v43)
    return v5,v43

def stage_buckets(rows):
    result={}
    for key in sorted({r["category"] for r in rows}):
        rr=[r for r in rows if r["category"]==key]
        out={"N_games":len(rr),
             "first_disagreement_by_stage":dict(Counter(str(r["first_disagreement_stage"]) for r in rr if r["first_disagreement_stage"] is not None)),
             "first_conflicts_v5_keeps_v43_mulls":sum(r["v5_keeps_first"] is True for r in rr),
             "first_conflicts_v43_keeps_v5_mulls":sum(r["v5_keeps_first"] is False for r in rr)}
        for h in (1,2,3):
            vals=[success(r["v5_turn"],h)-success(r["v43_turn"],h) for r in rr]
            out[f"v5_minus_v43_byT{h}_net_games"]=sum(vals)
            out[f"v5_only_byT{h}"]=vals.count(1)
            out[f"v43_only_byT{h}"]=vals.count(-1)
        result[key]=out
    return result

def run(out):
    v5,v43=read()
    rows=[]
    for gid in sorted(v5):
        a=v5[gid];b=v43[gid]
        aa=a["history"];bb=b["history"]
        assert aa and bb and aa[-1]["kept"] and bb[-1]["kept"]
        assert int(a["seat"])==int(b["seat"])
        assert [q["stage"] for q in aa]==list(range(len(aa)))
        assert [q["stage"] for q in bb]==list(range(len(bb)))
        assert aa[0]["seven_slots"]==bb[0]["seven_slots"]
        s5=int(aa[-1]["stage"]);s43=int(bb[-1]["stage"])
        if s5!=s43:
            category="different_final_keep_stage"
            s=min(s5,s43)
            assert s<7
            q5=aa[s];q43=bb[s]
            assert q5["seven_slots"]==q43["seven_slots"] and q5["seven"]==q43["seven"]
            assert bool(q5["kept"])!=bool(q43["kept"])
            assert all(not x["kept"] for x in aa[:s])
            assert all(not x["kept"] for x in bb[:s])
            first=s
            v5first=(s5<s43)
            exact=(Counter(aa[-1]["hand"])==Counter(bb[-1]["hand"]) and
                   tuple(aa[-1]["bottom"])==tuple(bb[-1]["bottom"]))
            assert not exact
        else:
            first=None;v5first=None
            q5=aa[-1];q43=bb[-1]
            assert q5["seven_slots"]==q43["seven_slots"]
            exact=(Counter(q5["hand"])==Counter(q43["hand"]) and
                   tuple(q5["bottom"])==tuple(q43["bottom"]))
            if exact:
                category="same_stage_identical_final_hand_bottom"
                assert int(a["turn"])==int(b["turn"]),("same state gameplay parity",gid)
            else:category="same_stage_different_final_hand_bottom"
        rows.append({
          "gid":gid,"seat":int(a["seat"]),
          "category":category,"v5_final_keep_stage":s5,"v43_final_keep_stage":s43,
          "first_disagreement_stage":first,"v5_keeps_first":v5first,
          "v5_turn":int(a["turn"]),"v43_turn":int(b["turn"]),
          "v5_selected_hand_at_comparison":q5["hand"],
          "v5_selected_bottom_at_comparison":q5["bottom"],
          "v43_selected_hand_at_comparison":q43["hand"],
          "v43_selected_bottom_at_comparison":q43["bottom"],
          "v5_raw_internal_utility":q5.get("raw"),
          "v5_internal_threshold":q5.get("threshold"),
          "v5_sampled_T1":q5.get("sampled_t1"),
          "v43_predicted_T2":q43.get("raw"),
          "v43_DP_continuation":q43.get("threshold"),
          "v5_and_v43_scales_not_comparable":True,
        })
    assert len(rows)==128
    cats=stage_buckets(rows)
    assert sum(z["N_games"] for z in cats.values())==128
    assert cats["same_stage_identical_final_hand_bottom"]["v5_minus_v43_byT2_net_games"]==0
    overall={"N":128,"v5_byT2":sum(success(r["v5_turn"],2) for r in rows),
             "v43_byT2":sum(success(r["v43_turn"],2) for r in rows)}
    assert overall["v5_byT2"]==73 and overall["v43_byT2"]==65
    assert sum(x["v5_minus_v43_byT2_net_games"] for x in cats.values())==8
    diff=[r for r in rows if r["first_disagreement_stage"] is not None]
    report={
      "schema":SCHEMA,"status":"PASS",
      "already_inspected_151k_not_fresh_validation":True,
      "original_v5_and_v43_same_physical_deal_and_seat":True,
      "identical_final_hand_ensures_physical_gameplay_parity":True,
      "no_new_simulation_or_model_tuning":True,
      "no_original_v5_lookahead_invoked":True,
      "same_stage_bottom_difference_not_total_causal_attribution":True,
      "counts":overall,
      "categories":cats,
      "first_conflict_stage_counts":dict(Counter(str(r["first_disagreement_stage"]) for r in diff)),
      "early_conflicts_0_2":sum(r["first_disagreement_stage"]<=2 for r in diff),
      "first_stage_selected_only_if_actually_both_policies_reached":True,
      "cases":rows,
    }
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print("DACK_V45_V5_V43_EXACT_FIRST_CONFLICT_AND_STAGE_BOTTOM_SPLIT_PASS",
          json.dumps({"counts":overall,"categories":cats,
           "first_conflict_stage_counts":report["first_conflict_stage_counts"]},
           sort_keys=True),flush=True)

if __name__=="__main__":
    run(ROOT/"benchmark_results/v45_v5_v43_matched_151k_N128_first_conflict.json")
