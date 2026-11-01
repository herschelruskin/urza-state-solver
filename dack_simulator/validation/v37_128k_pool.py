#!/usr/bin/env python3
"""v37 GATED 128k N256 four-policy actual full game paired benchmark pool.

Only valid when 127k independent conditional direct-regret and actual
London reachability gates BOTH passed. Original v5/v27/v33b and v37
run separate interpreters per physical game, matched physical 99-slot
deals, seat and stable dice. Independent game IDs are paired inference
unit. No source policy promotion without additional rules review.
"""
from __future__ import annotations
from collections import Counter
import gzip,glob,json,math,random,argparse
from pathlib import Path
N=256;POLICIES=("v5","v27","v33b","v37")
def y(t,turn):return int(0<int(turn)<=t)
def exact_mcnemar(g,l):
    n=g+l
    if n==0:return 1.
    return min(1.,2*sum(math.comb(n,i) for i in range(min(g,l)+1))/2**n)
def paired(data,a,b,t):
    deltas=[y(t,r[a]["turn"])-y(t,r[b]["turn"]) for r in data]
    gain=deltas.count(1);loss=deltas.count(-1)
    rng=random.Random(371280+t+sum(map(ord,a+b)))
    boot=sorted(100*sum(deltas[rng.randrange(N)] for j in range(N))/N
                for _ in range(5000))
    return {"new_minus_comparator_pp":100*sum(deltas)/N,
      "paired_gains":gain,"paired_losses":loss,
      "physical_group_bootstrap_95ci_pp":[boot[125],boot[4874]],
      "exploratory_exact_McNemar_p":exact_mcnemar(gain,loss)}
def run(source,out):
    gate=json.loads(Path("benchmark_results/v37_127k_independent_direct_regret.json").read_text())
    assert gate["precommitted_full_gate_passed"] and gate["status"]=="PASS"
    paths=sorted(glob.glob(source))
    assert len(paths)==64,("missing all 128k N256 prospective physical shards",len(paths))
    rows=[];modelsha=None
    for path in paths:
        with gzip.open(path,"rt") as f:d=json.load(f)
        assert d["schema"]=="dack_v37_128k_strict_prospective_four_policy_game"
        assert d["status"]=="PASS" and not d["policy_approved"]
        assert tuple(d["policies"])==POLICIES and d["physical_outer_groups"]==4
        assert d["strict_actual_gameplay_beam160"] and d["identical_99_card_outer_deals_and_seat"]
        assert d["v37_no_action_change_has_exact_v33b_game_turn"]
        assert d["full_game_prospective_precommitted_127k_gate_passed"]
        if modelsha is None:modelsha=d["model_sha256"]
        assert modelsha==d["model_sha256"]==gate["model_sha256"]
        rows+=d["rows"]
    rows.sort(key=lambda r:r["game_id"])
    assert [r["game_id"] for r in rows]==list(range(128000,128256))
    summary={}
    for p in POLICIES:
        games=[r[p] for r in rows]
        summary[p]={
          "N":N,"T1_exact_count":sum(r["turn"]==1 for r in games),
          "T2_cumulative_count":sum(y(2,r["turn"]) for r in games),
          "T3_cumulative_count":sum(y(3,r["turn"]) for r in games),
          "mean_final_keep_n":sum(r["keep_n"] for r in games)/N,
          "sum_actual_london_plus_gameplay_seconds":sum(r["elapsed"] for r in games)}
    intervention=Counter()
    for r in rows:
        a=r["v37"]["history"]
        newactions=[h for h in a if h["kept"]!=h["v37_frozen_v27_original_keep"]]
        intervention["actual_games_with_v37_keep_action_changes"]+=int(bool(newactions))
        intervention["actual_games_identical_v33b_final_game_turn"]+=int(not newactions)
        intervention["v37_action_early_to_KEEP"]+=sum(h["v37_action_diagnostic"]["reason"]=="v37_true_regret_keep" for h in a)
        intervention["v37_action_early_to_MULL"]+=sum(h["v37_action_diagnostic"]["reason"]=="v37_true_regret_mull" for h in a)
        if not newactions:assert r["v37"]["turn"]==r["v33b"]["turn"]
    pairs={}
    for a,b in (("v37","v33b"),("v37","v27"),("v37","v5"),("v33b","v27")):
        for t in (1,2,3):
            pairs[f"{a}_minus_{b}_by_T{t}"]=paired(rows,a,b,t)
    report={
      "schema":"dack_v37_paired_N256_128k_full_game_prospective_1",
      "status":"PASS","policy_approved":False,
      "all_new_outer_game_ids":[128000,128255],
      "same_99_physical_cards_and_seat":True,
      "stable_dice_strict_beam160":True,
      "no_training_or_tuning_on_128k":True,
      "only_started_after_127k_conditional_gate":True,
      "model_sha256":modelsha,
      "per_policy":summary,"decision_changes":dict(intervention),
      "paired_comparisons":pairs,
      "full_game_runtime_speedup_v5_over_v37":
         summary["v5"]["sum_actual_london_plus_gameplay_seconds"]/
         summary["v37"]["sum_actual_london_plus_gameplay_seconds"],
      "caveat":"Actual full-game deploy-by-T2 in goldfish solver, not multiplayer win probability"
    }
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print("DACK_V37_FRESH_128K_ACTUAL_FULL_GAME_BENCHMARK_PASS",json.dumps({
       "per_policy":summary,
       "T2_v37_vs_v33b":pairs["v37_minus_v33b_by_T2"],
       "runtime_v5_to_v37":report["full_game_runtime_speedup_v5_over_v37"],
       "changes":dict(intervention)},sort_keys=True),flush=True)
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source",default="collected/v37_128k_*.json.gz")
    p.add_argument("--out",default="benchmark_results/v37_128k_N256_prospective.json")
    a=p.parse_args();run(a.source,a.out)
