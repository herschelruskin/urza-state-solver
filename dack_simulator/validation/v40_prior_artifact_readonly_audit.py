#!/usr/bin/env python3
"""Read-only DACK v38/v39 archive integrity and reward-algebra check.

This DOES NOT produce new simulated game outcomes, fit a policy, or use
v38/v39 consumed evaluation cohorts for hyperparameter selection.
Optional --repool deterministically repeats the original v39 physical
pooling over the exact archived K and shared-C shards, into a TEMP file.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
C38 = ROOT / "datasets/v38_129k_frozen_outcome_blind_census.json"
C39 = ROOT / "datasets/v39_131k_frozen_outcome_blind_census.json"
R39 = ROOT / "benchmark_results/v39_131k_independent_action_regret.json"
U39 = ROOT / "benchmark_results/v39_131k_readonly_two_utility_comparison.json"
SHARDS = ROOT / "benchmark_results/v39_131k_physical_shards"


def read(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def near(a: float, b: float, tol: float = 1e-10) -> None:
    assert math.isclose(float(a), float(b), abs_tol=tol, rel_tol=0), (a, b)


def census_check(doc: dict, first: int, groups: int, expected_changed: int,
                 expected_reached: int):
    assert doc["status"] == "PASS" and doc["policy_approved"] is False
    assert doc["physical_random_outer_groups"] == groups
    assert doc["random_stage_state_denominator"] == 3 * groups
    assert doc["actual_action_changes"] == expected_changed
    assert doc["changed_actual_London_path_games"] == expected_reached
    assert doc["no_full_game_or_counterfactual_rollouts_at_selection"] is True
    rows = doc["all_early_stage_decisions"]
    assert len(rows) == 3 * groups
    assert len({(x["game_id"], x["stage"]) for x in rows}) == 3 * groups
    assert {x["game_id"] for x in rows} == set(range(first, first + groups))
    assert all(x["stage"] in (0, 1, 2) for x in rows)
    assert sum(bool(x["changed"]) for x in rows) == expected_changed
    assert all(bool(x["changed"]) == (x["old_keep"] != x["new_keep"])
               for x in rows)
    live = doc["real_actual_London_path_divergences"]
    assert len(live) == expected_reached
    assert len({x["game_id"] for x in live}) == expected_reached
    assert all(first <= x["game_id"] < first + groups for x in live)
    assert all(any(r["game_id"] == x["game_id"] and r["changed"] for r in rows)
               for x in live)
    return rows


def validate(repool=False):
    v38, v39, results, utility = map(read, (C38, C39, R39, U39))
    a = census_check(v38, 129000, 512, 3, 2)
    b = census_check(v39, 131000, 1024, 47, 30)
    assert sum(x["old_keep"] and not x["new_keep"] for x in a) == 0
    assert sum((not x["old_keep"]) and x["new_keep"] for x in a) == 3
    assert sum(x["old_keep"] and not x["new_keep"] for x in b) == 46
    assert sum((not x["old_keep"]) and x["new_keep"] for x in b) == 1

    assert results["status"] == "PASS"
    assert results["policy_approved"] is False
    assert results["predeclared_gate_passed"] is False
    assert results["prospective_133k"] == "STOP"
    assert results["n_outer_physical_groups"] == 1024
    assert results["n_early_stage_states"] == 3072
    assert results["n_changed_stage_states"] == 47
    assert results["n_changed_actual_London_games"] == 30
    assert results["actual_K_beam160_rollouts"] == 47 * 32 == 1504
    assert results["actual_C_beam160_rollouts"] == 1408
    assert results["all_3072_original_population_denominator_included"] is True
    assert results["physical_group_and_shared_C_lottery_bootstrap"] is True
    assert results["census_sha256"] == hashlib.sha256(C39.read_bytes()).hexdigest()
    assert utility["source_census_sha256"] == results["census_sha256"]
    assert utility["new_beam160_rollouts"] == 0
    assert utility["posthoc_descriptive_not_a_second_independent_validation"] is True
    assert utility["shared_outcome_turn_for_T2_and_T3_metric_in_every_bootstrap"] is True

    t = results["results"]
    for turn in ("T1", "T2", "T3"):
        r = t[turn]
        assert r["n_stage_states"] == 3072
        assert r["action_changes"] == 47
        assert r["changed_beneficial"] + r["changed_harmful"] + r["changed_tied"] == 47
        assert r["two_source_group_bootstrap_95ci_pp"][0] <= r["two_source_group_bootstrap_95ci_pp"][1]
        near(r["mean_population_action_gain_pp"],
             sum(r["by_stage"][str(s)]["mean_population_action_gain_pp"] for s in range(3)) / 3)
    t2 = t["T2"]["mean_population_action_gain_pp"]
    t3 = t["T3"]["mean_population_action_gain_pp"]
    near(utility["outcomes"]["cumulative"]["mean_action_policy_gain_pp"], t2 + .5 * t3)
    near(utility["outcomes"]["exact3"]["mean_action_policy_gain_pp"], .5 * (t2 + t3))
    assert t["T2"]["two_source_group_bootstrap_95ci_pp"][0] <= 0
    assert t["T3"]["two_source_group_bootstrap_95ci_pp"][1] < 0

    shards = sorted(SHARDS.glob("v39_K_*.json.gz"))
    cells = sorted(SHARDS.glob("v39_C_*.json.gz"))
    assert len(shards) == 16 and len(cells) == 12, (len(shards), len(cells))
    replay_equal = None
    if repool:
        from dack_simulator.validation import v39_131k_pool as pooling
        with tempfile.TemporaryDirectory(prefix="dack_v40_audit_") as temp:
            destination = Path(temp) / "readonly_repool.json"
            pooling.run(str(SHARDS / "v39_K_*.json.gz"),
                        str(SHARDS / "v39_C_*.json.gz"), str(destination))
            replay_equal = read(destination) == results
            assert replay_equal, "Original raw shard pooling disagrees with archived v39 result!"

    summary = {
        "status": "DACK_V40_V38_V39_READONLY_ARCHIVE_AUDIT_PASS",
        "v38_stage_changes": 3,
        "v38_reached_path_changes": 2,
        "v39_stage_changes": 47,
        "v39_reached_path_changes": 30,
        "v39_population_byT2_pp": t2,
        "v39_population_byT3_pp": t3,
        "v39_cumulative_utility_pp": utility["outcomes"]["cumulative"]["mean_action_policy_gain_pp"],
        "v39_exact_T3_utility_pp": utility["outcomes"]["exact3"]["mean_action_policy_gain_pp"],
        "v39_original_shards": len(shards) + len(cells),
        "physical_outcomes_created": 0,
        "repool_original_shards_exact_match": replay_equal,
        "promotion": False,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return summary


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--repool", action="store_true",
                   help="Recompute existing 4000-replicate group bootstrap; NO gameplay")
    args = p.parse_args()
    validate(args.repool)
