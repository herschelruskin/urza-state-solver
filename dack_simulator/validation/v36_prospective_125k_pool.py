#!/usr/bin/env python3
"""Pool strictly prospective 125k N256 four-policy comparison, if gate passed.

Unchanged physical rules, stable dice, canonical first seven and seat.
Paired per-game bootstrap is the only unit of independent inference.
No trained parameters or thresholds selected on prospective outcomes.
"""
from __future__ import annotations
from collections import Counter
import gzip,glob,json,math,random
from pathlib import Path
POLICIES=("v5","v27","v33b","v36")
N=256

def success(turn,t):
    return int(0<int(turn)<=t)

def exact_mcnemar(g,l):
    n=g+l
    if not n:return 1.
    return min(1.,2*sum(math.comb(n,k) for k in range(min(g,l)+1))/2**n)

def compare(rows,a,b,t):
    diff=[success(r[a]["turn"],t)-success(r[b]["turn"],t) for r in rows]
    rng=random.Random(351122+t+sum(map(ord,a+b)))
    boot=sorted(100*sum(diff[rng.randrange(N)] for _ in range(N))/N
                  for _ in range(12000))
    gains=diff.count(1);losses=diff.count(-1)
    return {"new_minus_old_delta_pp":100*sum(diff)/N,
       "paired_gains":gains,"paired_losses":losses,
       "identical_binary_outcomes":N-gains-losses,
       "independent_physical_game_bootstrap_95ci_pp":[boot[299],boot[11699]],
       "exploratory_two_sided_exact_McNemar_p":exact_mcnemar(gains,losses)}

def pool(source,out):
    files=sorted(glob.glob(source))
    assert len(files)==64,("must run 64 completed prospective shards",len(files))
    rows=[];sha=None
    for f in files:
        with gzip.open(f,"rt") as h:d=json.load(h)
        assert d["schema"]=="dack_v36_125k_four_policy_full_game_physical_prospective"
        assert d["status"]=="PASS" and d["physical_group_count"]==4
        assert tuple(d["policy_order"])==POLICIES and d["strict_actual_beam160"]
        assert d["matching_seat_sevens_across_policies"]
        assert d["original_v5_and_v27_reference_frozen"]
        assert d["unchanged_actions_reproduce_v33b_exact_game_turn"]
        assert d["all_125k_outcomes_untouched_during_training"]
        assert not d["policy_approved"]
        if sha is None:sha=d["source_sha256"]
        assert sha==d["source_sha256"]
        rows.extend(d["rows"])
    rows.sort(key=lambda r:r["game_id"])
    assert [r["game_id"] for r in rows]==list(range(125000,125256))
    per={}
    for p in POLICIES:
        xx=[r[p] for r in rows]
        per[p]={"N":N,
           "exact_T1_count":sum(x["turn"]==1 for x in xx),
           "by_T2_count":sum(success(x["turn"],2) for x in xx),
           "by_T3_count":sum(success(x["turn"],3) for x in xx),
           "mean_kept_n":sum(x["keep_n"] for x in xx)/N,
           "sum_actual_policy_and_gameplay_seconds":sum(x["seconds"] for x in xx)}
    interventions=Counter()
    for r in rows:
        a=r["v27"]["history"];b=r["v33b"]["history"]
        assert len(a)==len(b)
        assert all((x["stage"],x["keep_n"],x["kept"],x["seven_slots"])==
                   (y["stage"],y["keep_n"],y["kept"],y["seven_slots"])
                   for x,y in zip(a,b))
        q=r["v36"]["history"]
        changed=any(x["kept"]!=x["v36_frozen_v27_original_keep"] for x in q)
        interventions["v36_changed_keep_vs_v27_count"]+=int(changed)
        interventions["v36_same_keep_count"]+=int(not changed)
        interventions["v36_to_keep_decisions"]+=sum(
          z["v36_action_diagnostic"]["reason"]=="v36_real_action_keep" for z in q)
        interventions["v36_to_mull_decisions"]+=sum(
          z["v36_action_diagnostic"]["reason"]=="v36_real_action_mull" for z in q)
        if not changed:
            assert r["v36"]["turn"]==r["v33b"]["turn"]
    pairs={}
    for a,b in (("v36","v33b"),
                ("v36","v27"),
                ("v36","v5"),
                ("v33b","v27")):
        for t in (1,2,3):
            pairs[f"{a}_minus_{b}_T{t}"]=compare(rows,a,b,t)
    outdoc={
      "schema":"dack_v36_prospective_125k_N256_four_policy",
      "status":"PASS","policy_approved":False,
      "source_physical_ids":[125000,125255],
      "same_real_99_card_deals_and_seat":True,
      "strict_actual_beam160":True,
      "source_shas":sha,
      "v27_v33b_mulligan_decision_parity":True,
      "unchanged_v36_action_exact_v33b_gameplay_turn_parity":True,
      "no_prospective_training_or_tuning":True,
      "per_policy":per,"keep_decision_changes":dict(interventions),
      "paired_comparisons":pairs,
      "measured_speedup_v5_over_v36":
         per["v5"]["sum_actual_policy_and_gameplay_seconds"]/
         per["v36"]["sum_actual_policy_and_gameplay_seconds"],
      "measured_speedup_v5_over_v33b":
         per["v5"]["sum_actual_policy_and_gameplay_seconds"]/
         per["v33b"]["sum_actual_policy_and_gameplay_seconds"],
      "limitations":["N256 cannot establish small percentage-point differences precisely",
        "T2 primary with T1/T3 safeguards; no multiplayer opponents",
        "All N256 matched physical outer IDs are bootstrap resampling unit",
        "No self-consistency claimed from pre-deployment conditional screen",
        "Policies differ in hidden game paths after the first changed decision",
        "Provisional candidate only, no production promotion"] }
    dest=Path(out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(outdoc,sort_keys=True,indent=2)+"\n")
    print("DACK_V36_122K_N256_PROSPECTIVE_PASS",json.dumps({
      "per_policy":per,"changes":dict(interventions),
      "primary":pairs["v36_minus_v33b_T2"],
      "T3_safeguard":pairs["v36_minus_v33b_T3"],
      "speedup":outdoc["measured_speedup_v5_over_v36"]},sort_keys=True),flush=True)

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--source",default="collected/v36_125k_*.json.gz")
    p.add_argument("--out",default="benchmark_results/v36_125k_N256_prospective.json")
    a=p.parse_args();pool(a.source,a.out)
