#!/usr/bin/env python3
"""v33 bounded diagnostic: NO new policy, no gameplay calls, no training.

Separate observed paired full-game gaps by the first descriptive distinction
(final London stage versus bottom at same stage), then triangulate against
independent *actual intervention* archives: v28 paired bottom counterfactuals
and v31 forced KEEP/MULL. Descriptive partitions are NOT causal attribution.
No 110k data may enter fitting or threshold selection.
"""
from __future__ import annotations

import argparse
from collections import Counter
import glob
import gzip
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "benchmark_results"
POLICIES = ("v5", "v27_frozen", "v32_shared_C")
PAIRS = (("v5", "v27_frozen"), ("v5", "v32_shared_C"),
         ("v32_shared_C", "v27_frozen"))
EXPECTED_GIDS = list(range(110000, 110256))
BOOT_SEED = 3301101


def passed(turn, t):
    return int(0 < int(turn) <= t)


def category(a, b):
    if a["keep_n"] != b["keep_n"]:
        return "different_london_stage_confounded"
    ah = a["history"][-1]["hand"]
    bh = b["history"][-1]["hand"]
    if Counter(ah) != Counter(bh):
        return "same_stage_different_hand"
    return "same_final_hand"


def summarize(rows, a, b):
    results = {}
    for cat in ("all_games", "same_final_hand", "same_stage_different_hand",
                "different_london_stage_confounded"):
        subset = (rows if cat == "all_games"
                  else [r for r in rows if category(r[a], r[b]) == cat])
        n = len(subset)
        metrics = {}
        for t in (1, 2, 3):
            diffs = [passed(r[a]["turn"], t) - passed(r[b]["turn"], t)
                     for r in subset]
            gains, losses = diffs.count(1), diffs.count(-1)
            mean = 100 * sum(diffs) / n if n else None
            ci = None
            if n:
                rng = random.Random(BOOT_SEED + 41*t + len(cat) + n
                                    + sum(map(ord, a+b)))
                sims = sorted(100 * sum(diffs[rng.randrange(n)] for _ in range(n))/n
                              for _ in range(3000))
                ci = [sims[74], sims[2924]]
            metrics["T"+str(t)] = {
                "a_successes":sum(passed(r[a]["turn"], t) for r in subset),
                "b_successes":sum(passed(r[b]["turn"], t) for r in subset),
                "gains":gains,"losses":losses,
                "delta_pp":mean,"paired_bootstrap_95ci_pp":ci}
        results[cat] = {"N":n, "endpoints":metrics}
    assert sum(results[c]["N"] for c in results if c != "all_games") == 256
    return results


def load_full_games():
    files = sorted(glob.glob(str(ARCHIVE / "v32_110k_shards" / "v32_110k_*.json.gz")))
    if len(files) != 64:
        raise ValueError("need all 64 immutable v32 prospective shards; found %d" % len(files))
    rows = []
    sha = None
    for file in files:
        with gzip.open(file, "rt") as inp:
            doc = json.load(inp)
        assert doc["schema"] == "dack_v32_prospective_110k_three_policy_strict"
        assert doc["status"] == "PASS" and doc["n_game_groups"] == 4
        assert doc["actual_gameplay_beam"] == 160
        assert doc["same_physical_first_seven_and_seat"]
        assert doc["test_cohort_never_in_training_or_threshold_calibration"]
        assert tuple(doc["policies"]) == POLICIES
        if sha is None:
            sha = doc["source_sha256"]
        assert doc["source_sha256"] == sha
        rows.extend(doc["rows"])
    rows.sort(key=lambda x: x["game_id"])
    assert [r["game_id"] for r in rows] == EXPECTED_GIDS
    for r in rows:
        assert len(set(r[p]["seat"] for p in POLICIES)) == 1
        assert len(set(tuple(r[p]["history"][0]["seven_slots"]) for p in POLICIES)) == 1
        for p in POLICIES:
            assert r[p]["turn"] in (0,1,2,3)
            assert r[p]["history"][-1]["kept"]
            assert r[p]["keep_n"] == r[p]["history"][-1]["keep_n"]
    return rows, sha


def main(out):
    rows, sha = load_full_games()
    v28 = json.loads((ARCHIVE / "v28_bottom_hidden_order_and_unseen_value_N64.json").read_text())
    v31 = json.loads((ARCHIVE / "v31_Q_advantage_103k_holdout.json").read_text())
    v32 = json.loads((ARCHIVE / "v32_prospective_110k_N256.json").read_text())
    assert v28["status"] == "PASS" and v28["bottom_eligible_game_groups"] == 50
    assert v28["no_model_training_or_99k_tuning"]
    assert v31["status"] == "PASS" and v31["model_approved"] is False
    assert v32["status"] == "PASS" and v32["n_independent_physical_games"] == 256
    assert v32["source_sha256"] == sha
    assert v32["per_policy"]["v5"]["T2_count"] == 131
    assert v32["per_policy"]["v27_frozen"]["T2_count"] == 124
    assert v32["per_policy"]["v32_shared_C"]["T2_count"] == 121

    outcome = {
        "schema": "dack_v33_readonly_attribution_audit",
        "status": "PASS",
        "scope": "retrospective, no beam simulations, no fitting, no policy changes",
        "source_full_game_ids": [110000, 110255],
        "source_model_shas": sha,
        "matched_256_game_descriptive_partitions": {
            a + "_minus_" + b: summarize(rows, a, b) for a,b in PAIRS
        },
        "actual_bottom_intervention_v28": {
            "n_v5_selected_kept_decision_groups": 50,
            "futures_per_candidate": 16,
            "v5_vs_v14": v28["paired_independent_16_future_comparisons"][
                "v5_candidate_index_vs_v14_candidate_index"],
            "sample_selection_warning": "V5-selected decisions; conditional 99k, not population-wide causal effect."
        },
        "actual_keep_mull_intervention_v31": {
            "independent_103k_test": {
                k:v for k,v in v31["scores"]["untouched_103k_test"].items()
                if k != "details"
            },
            "stages_sampled": [0,1,3,5],
            "warning": "6 rollouts per arm; 16 physical groups, not sufficient for high-confidence individual-action regret."
        },
        "prior_prospective_counts": v32["per_policy"],
        "constraints": {
            "110k_heldout_games_never_retrained_on": True,
            "no_counterfactual_replay_claimed_for_stage_partitions": True,
            "same_final_hand_different_turn_is_an_audit_signal_not_performance_regret": True,
            "no_changes_to_gameplay_or_actual_99_card_shuffle": True,
            "actual_goldfish_not_multiplayer_win_probability": True,
            "policy_approved": False,
        },
    }
    dest = Path(out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(outcome, sort_keys=True, indent=2)+"\n")
    print("DACK_V33_READONLY_ATTRIBUTION_PASS", json.dumps({
        "out":str(dest),
        "v5_vs_v27":{c:x["N"] for c,x in outcome[
            "matched_256_game_descriptive_partitions"]["v5_minus_v27_frozen"].items()},
        "bottom_v28_T2":outcome["actual_bottom_intervention_v28"][
            "v5_vs_v14"]["heldout_by_T2"]["mean_paired_difference"],
        "bottom_v28_T3":outcome["actual_bottom_intervention_v28"][
            "v5_vs_v14"]["heldout_by_T3"]["mean_paired_difference"],
    },sort_keys=True),flush=True)


def selftest():
    a={"keep_n":4,"history":[{"hand":["Plains","Mana Vault"]}]}
    b={"keep_n":4,"history":[{"hand":["Mana Vault","Plains"]}]}
    assert category(a,b) == "same_final_hand"
    b["history"][-1]["hand"] = ["Plains","Sol Ring"]
    assert category(a,b) == "same_stage_different_hand"
    b["keep_n"]=3
    assert category(a,b) == "different_london_stage_confounded"
    assert passed(0,3)==0 and passed(3,2)==0 and passed(2,2)==1
    print("DACK_V33_READONLY_SELFTEST_PASS", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest",action="store_true")
    parser.add_argument("--out",default="benchmark_results/v33_attribution_first_readonly.json")
    args = parser.parse_args()
    if args.selftest:
        selftest()
    else:
        main(args.out)
