#!/usr/bin/env python3
"""v46 strict paired first-two-sevens model versus frozen v43 full-game N256.
One outer physical deal is the statistical unit; no double counting stages.
"""
from __future__ import annotations
import gzip,glob,json,random
from pathlib import Path
from collections import defaultdict
def by(t,h):return int(0<int(t)<=h)
def run():
    paths=sorted(glob.glob("collected/v46_157k_*.json.gz"))
    assert len(paths)==8,(len(paths),paths)
    rows=[];sha=None
    for p in paths:
        with gzip.open(p,"rt") as f:d=json.load(f)
        assert d["status"]=="PASS"
        assert d["schema"]=="dack_v46_new_157k_v43_v46_complete_game_paired_N256_shard"
        assert d["N_matched_deals"]==32 and d["predeclared_dev_gate_passed_before_157k_results"]
        assert d["strict_real_gameplay_beam160_99_cards"] and d["same_seat_and_first_seven"]
        assert d["only_first_two_seven_keep_decisions_may_differ"]
        if sha is None:sha=d["model_sha256"]
        assert sha==d["model_sha256"]
        rows+=d["rows"]
    rows.sort(key=lambda x:x["gid"])
    assert [x["gid"] for x in rows]==list(range(157000,157256))
    n=len(rows);rates={};paired={}
    for pol in ("v43","v46"):
        rates[pol]={f"byT{h}":sum(by(z[pol]["turn"],h) for z in rows) for h in (1,2,3)}
        rates[pol]["total_goldfish_seconds"]=round(sum(z[pol]["seconds"] for z in rows),3)
        rates[pol]["mean_keep_n"]=sum(z[pol]["keep_n"] for z in rows)/n
        rates[pol]["stage0_KEEP"]=sum(z[pol]["history"][0]["kept"] for z in rows)
        rates[pol]["stage1_reached"]=sum(len(z[pol]["history"])>1 for z in rows)
        rates[pol]["stage1_KEEP_when_reached"]=sum(len(z[pol]["history"])>1 and z[pol]["history"][1]["kept"] for z in rows)
    for h in (1,2,3):
        differences=[by(r["v46"]["turn"],h)-by(r["v43"]["turn"],h) for r in rows]
        rng=random.Random(157001+h)
        draws=sorted(100*sum(differences[rng.randrange(n)] for _ in range(n))/n for _ in range(12000))
        paired[f"T{h}"]={
            "net_game_deployments_v46_minus_v43":sum(differences),
            "paired_percentage_point_change":100*sum(differences)/n,
            "v46_only":differences.count(1),"v43_only":differences.count(-1),
            "paired_outer_game_bootstrap_95ci_pp":[draws[299],draws[11699]],
        }
    stages=defaultdict(list)
    for r in rows:
        a=r["v43"]["history"];b=r["v46"]["history"]
        diff=None
        for i in range(min(len(a),len(b))):
            assert a[i]["stage"]==b[i]["stage"]
            if a[i]["kept"]!=b[i]["kept"]:
                diff=i;break
        if diff is None:
            assert a[-1]["stage"]==b[-1]["stage"]
            assert a[-1]["bottom"]==b[-1]["bottom"]
            assert a[-1]["hand"]==b[-1]["hand"]
            assert r["v43"]["turn"]==r["v46"]["turn"]
            stages["no_different_KEEP_decision"].append(r)
        else:
            assert diff in (0,1),("later stage unexpectedly diverged",r["gid"],diff)
            stages[f"first_diff_stage{diff}"].append(r)
    strata={}
    for name,rr in stages.items():
        strata[name]={
           "N_groups":len(rr),
           **{f"T{h}_net_game_delta":sum(by(z["v46"]["turn"],h)-by(z["v43"]["turn"],h) for z in rr)
              for h in (1,2,3)},
        }
    assert sum(r["N_groups"] for r in strata.values())==n
    assert sum(r.get("T2_net_game_delta",0) for r in strata.values())==paired["T2"]["net_game_deployments_v46_minus_v43"]
    doc={
       "schema":"dack_v46_new157k_N256_frozen_v43_versus_early7_calibrated_strict",
       "status":"PASS","N_independent_physical_outer_games":256,
       "new_completely_separate_157k_full_game_cohort":True,
       "predeclared_156k_dev_gate_passed_prior_to_observation":True,
       "baseline_v43_frozen_unchanged":True,
       "student_v46_model_sha256":sha,"model_approved":False,
       "same_99_deck_seed_seat_and_initial_physical_seven":True,
       "strict_beam160_terminal_goldfish_not_multiplayer_win":True,
       "metrics":rates,"paired":paired,"first_changed_early_stage":strata,
    }
    p=Path("benchmark_results/v46_fresh_157k_N256_strict_full_game.json")
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print("DACK_V46_FRESH_157K_N256_TRUE_PAIRED_DEPLOYMENT_PASS",
        json.dumps(doc,sort_keys=True),flush=True)
if __name__=="__main__":run()
