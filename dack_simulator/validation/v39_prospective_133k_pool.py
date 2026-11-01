#!/usr/bin/env python3
"""v39 prospective 133k N1024 paired FULL POLICY physical beam160 results.

Independent original 99 card physical game ID is unit. Matched
v33b/v39 same seat, initial all 8 physical sevens, seed, stable
chance. Different final physical states both simulated; same final
ordered library + hand exactly same outcome with original game
simulated once. Paired group bootstrap for cumulative byT1/byT2/byT3.
This is actual new full-game deployment outcome, not 131k one-step Q.
"""
from __future__ import annotations
import argparse,glob,gzip,json,math,random,hashlib
from pathlib import Path
N=1024;LO=133000;HI=134023
POLICIES=("baseline_v33b","new_v39")

def hit(turn,t):return int(0<int(turn)<=t)

def mcnemar(gains,losses):
    n=gains+losses
    if n==0:return 1.
    return min(1.,2*sum(math.comb(n,k) for k in range(min(gains,losses)+1))/2**n)

def paired(rows,t):
    ds=[hit(r["new_v39"]["win_turn"],t)-hit(r["baseline_v33b"]["win_turn"],t) for r in rows]
    gains=ds.count(1);losses=ds.count(-1)
    rng=random.Random(391330+t)
    vals=[]
    for i in range(12000):
        vals.append(100*sum(ds[rng.randrange(N)] for _ in range(N))/N)
    vals.sort()
    return {"new_minus_old_deployment_by_T"+str(t)+"_percentage_points":100*sum(ds)/N,
      "paired_gain_games":gains,"paired_loss_games":losses,
      "identical_cumulative_outcomes":N-gains-losses,
      "paired_outer_game_bootstrap_95ci_pp":[vals[299],vals[11699]],
      "exploratory_exact_two_sided_McNemar_p":mcnemar(gains,losses)}

def pool(source,out):
    files=sorted(glob.glob(source))
    assert len(files)==64,("need 64 full physical 16-game shards",len(files))
    rows=[];model_sha=None;gate_sha=None
    for p in files:
        with gzip.open(p,"rt") as f:d=json.load(f)
        assert d["schema"]=="dack_v39_133k_N1024_matched_v33b_v39_real_full_game_v1"
        assert d["status"]=="PASS" and d["n_outer_independent_groups"]==16
        assert d["same_original_99_card_deal_and_seat"]
        assert d["same_state_same_seed_one_exact_gameplay_replay_allowed"]
        assert d["actual_rules_stable_dice_gameplay_beam160"]
        assert d["no_new_training_from_131k_or_133k"] and not d["policy_approved"]
        if model_sha is None:
            model_sha=d["source_frozen_direct_regret_model_sha256"]
            gate_sha=d["validated_131k_gate_file_sha256"]
        assert model_sha==d["source_frozen_direct_regret_model_sha256"]
        assert gate_sha==d["validated_131k_gate_file_sha256"]
        rows.extend(d["rows"])
    rows.sort(key=lambda r:r["game_id"])
    assert [r["game_id"] for r in rows]==list(range(LO,HI+1))
    same=0
    for r in rows:
        a=r["baseline_v33b"];b=r["new_v39"]
        assert a["win_turn"] in (0,1,2,3) and b["win_turn"] in (0,1,2,3)
        assert all(z["chooser_seconds"]>=0 and z["gameplay_seconds"]>=0 for z in (a,b))
        if r["same_physical_final_hand_and_ordered_library"]:
            same+=1
            assert a["win_turn"]==b["win_turn"]
            assert a["actual_final_stage"]==b["actual_final_stage"]
            assert a["keep_n"]==b["keep_n"]
    per={}
    for name in POLICIES:
        a=[r[name] for r in rows]
        per[name]={
           "N":N,
           "exact_T1_count":sum(z["win_turn"]==1 for z in a),
           "cumulative_T2_count":sum(hit(z["win_turn"],2) for z in a),
           "cumulative_T3_count":sum(hit(z["win_turn"],3) for z in a),
           "mean_kept_n":sum(z["keep_n"] for z in a)/N,
           "chooser_seconds_total":sum(z["chooser_seconds"] for z in a),
           "gameplay_seconds_total_reused_on_same_physical_state":sum(z["gameplay_seconds"] for z in a),
        }
        per[name]["estimated_policy_plus_gameplay_seconds_total"]=(
             per[name]["chooser_seconds_total"]+per[name]["gameplay_seconds_total_reused_on_same_physical_state"])
    report={
      "schema":"dack_v39_N1024_independent_133k_paired_prospective_physical_full_game",
      "status":"PASS","policy_approved":False,
      "source_physical_game_ids":[LO,HI],
      "n_outer_physical_games":N,
      "same_seat_and_all_eight_London_sevens":True,
      "same_actual_frozen_99_card_slots":True,
      "stable_dice_strict_actual_gameplay_beam160":True,
      "exactly_identical_final_physical_state_games":same,
      "changed_final_physical_state_games":N-same,
      "exact_same_state_win_turn_parity_asserted":True,
      "same_gameplay_work_per_identical_state_reused_not_statistical_imputation":True,
      "no_133k_model_selection_or_refit":True,
      "source_frozen_v37_regret_model_sha256":model_sha,
      "source_131k_gate_sha256":gate_sha,
      "per_policy":per,
      "paired_differences":{f"T{t}":paired(rows,t) for t in (1,2,3)},
      "two_policy_estimated_runtime_ratio_v33b_over_v39":
       per["baseline_v33b"]["estimated_policy_plus_gameplay_seconds_total"]/
       per["new_v39"]["estimated_policy_plus_gameplay_seconds_total"],
      "limitations":[
       "Goldfish Dack deployment by T2 is not multiplayer cEDH game win probability",
       "Paired 133k outer physical game is bootstrap unit, not individual simulator branch",
       "Same-state skipped v39 gameplay is logically identical when hand library and seed match",
       "Actual game uses strict beam160 physical-deck rules and stable seeded chance",
       "This branch and all model variants remain experimental until reviewed"]
    }
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print("DACK_V39_FRESH133K_N1024_FULL_GAME_PAIRED_PROSPECTIVE_PASS",
      json.dumps({"same_final_state":same,
        "t1":report["paired_differences"]["T1"],
        "t2":report["paired_differences"]["T2"],
        "t3":report["paired_differences"]["T3"],
        "runtime_ratio":report["two_policy_estimated_runtime_ratio_v33b_over_v39"],
        "per_policy":per},sort_keys=True),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source",default="collected/v39_133k_*.json.gz")
    p.add_argument("--out",default="benchmark_results/v39_133k_full_game_N1024.json")
    a=p.parse_args();pool(a.source,a.out)
