#!/usr/bin/env python3
"""Pool sealed v43 vs v46 N256 full gameplay on 161k independent deals."""
from __future__ import annotations
import glob,gzip,json,random
from pathlib import Path
N=256
SCHEMA="dack_v46_161k_independent_full_goldfish_v43_v46_paired_shard_v1"
def win(t,h):return int(0<int(t)<=h)
def run():
    paths=sorted(glob.glob("collected/v46_161k_*.json.gz"))
    assert len(paths)==8
    rows=[];sha=None
    for path in paths:
        with gzip.open(path,"rt") as f:q=json.load(f)
        assert q["schema"]==SCHEMA and q["status"]=="PASS"
        assert q["dev_gate_passed_before_opening_161k"]
        assert q["exact_99_slot_strict_beam160_goldfish"]
        assert q["no_model_fit_on_161k"] and not q["policy_approved"]
        if sha is None:sha=q["model_sha256"]
        assert q["model_sha256"]==sha
        rows+=q["rows"]
    rows.sort(key=lambda q:q["gid"])
    assert [r["gid"] for r in rows]==list(range(161000,161256))
    totals={}
    for p in ("v43","v46"):
        a=[r[p] for r in rows]
        totals[p]={f"by_T{h}":sum(win(z["turn"],h) for z in a) for h in (1,2,3)}
        totals[p]["mean_cards_kept"]=sum(z["keep_n"] for z in a)/N
        totals[p]["seconds_gameplay_only"]=sum(z["seconds"] for z in a)
    paired={}
    for h in (1,2,3):
        ds=[win(r["v46"]["turn"],h)-win(r["v43"]["turn"],h) for r in rows]
        rng=random.Random(46161+h)
        boot=sorted(100*sum(ds[rng.randrange(N)] for _ in range(N))/N for _ in range(9000))
        paired[f"T{h}"]={
          "v46_minus_v43_pp":100*sum(ds)/N,
          "net_games":sum(ds),"v46_only":ds.count(1),"v43_only":ds.count(-1),
          "paired_bootstrap_95ci_pp":[boot[224],boot[8774]],
        }
    def stopstage(pol,r):return int(r[pol]["history"][-1]["stage"])
    change=[r for r in rows if stopstage("v43",r)!=stopstage("v46",r)]
    source_reach={
       "v43_n_reaches_second_seven":sum(len(r["v43"]["history"])>1 for r in rows),
       "v46_n_reaches_second_seven":sum(len(r["v46"]["history"])>1 for r in rows),
       "same_final_london_stage":N-len(change),
       "different_final_london_stage":len(change),
       "v46_earlier_keep":sum(stopstage("v46",r)<stopstage("v43",r) for r in change),
       "v43_earlier_keep":sum(stopstage("v43",r)<stopstage("v46",r) for r in change),
       "both_same_stage_same_hand":sum(
           stopstage("v43",r)==stopstage("v46",r)
           and r["v43"]["history"][-1]["hand"]==r["v46"]["history"][-1]["hand"]
           and r["v43"]["history"][-1]["bottom"]==r["v46"]["history"][-1]["bottom"]
           for r in rows),
    }
    for r in rows:
        if stopstage("v43",r)==stopstage("v46",r):
            assert r["v43"]["history"][-1]["hand"]==r["v46"]["history"][-1]["hand"]
            assert r["v43"]["history"][-1]["bottom"]==r["v46"]["history"][-1]["bottom"]
            assert r["v43"]["turn"]==r["v46"]["turn"]
    report={
      "schema":"dack_v46_v43_vs_early_Q2_corrected_161k_N256_paired_full_policy",
      "status":"PASS","N_independent_real_games":N,
      "predeclared_dev_gate_verified":True,
      "actual_full_game_goldfish_not_population_mull_state_estimate":True,
      "same_physical_source_groups_deck_seat_and_stable_dice":True,
      "strict_beam160_original_game_engine":True,
      "no_v5_gameplay_lookahead_at_runtime":True,
      "research_only_not_promoted":True,
      "model_sha256":sha,
      "policy_metrics":totals,"paired":paired,
      "stage_0_1_reach_and_change":source_reach,
    }
    p=Path("benchmark_results/v46_161k_N256_full_policy_paired.json")
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print("DACK_V46_INDEPENDENT_161K_FULL_POLICY_N256_PASS",json.dumps(report,sort_keys=True),flush=True)
if __name__=="__main__":run()
