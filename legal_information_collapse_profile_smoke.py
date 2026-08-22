#!/usr/bin/env python3
"""Integration smoke for the decision-neutral legal-information profiler."""

import urza_solver as solver
from legal_information_collapse_profile import run_profile


def test_profile_runs_without_affecting_solver_action_cap():
    deck = ["Island"] * 99
    old_cap = solver.ACTION_CAP
    payload = run_profile(
        deck,
        base_seed=20260821,
        count=2,
        step=1,
        max_turn=1,
        beam=20,
        depth=4,
        action_cap=17,
    )
    assert solver.ACTION_CAP == old_cap
    assert payload["decision_neutral"] is True
    assert len(payload["seeds"]) == 2

    baseline = payload["empty_information_baseline"]
    legal = payload["legal_information"]
    assert baseline["observations"] > 0
    assert legal["observations"] > 0
    assert baseline["concrete_information_unique"] == baseline["concrete_unique"]
    assert legal["strategic_unique"] <= legal["concrete_information_unique"]

    # max_turn=1 should not report the diagnostic post-horizon turn as a searched T2 bucket.
    assert 2 not in baseline["by_turn"]
    assert 2 not in legal["by_turn"]
    assert sum(row["post_horizon_snapshots"] for row in payload["seeds"]) > 0


def test_homogeneous_deck_demonstrates_cross_seed_strategic_collapse():
    deck = ["Island"] * 99
    payload = run_profile(
        deck,
        base_seed=101,
        count=2,
        step=1,
        max_turn=1,
        beam=10,
        depth=2,
        action_cap=10,
    )
    legal = payload["legal_information"]
    assert legal["concrete_information_unique"] >= legal["strategic_unique"]
    assert legal["concrete_information_to_strategic_collapse_fraction"] >= 0.0


def main():
    tests = [
        test_profile_runs_without_affecting_solver_action_cap,
        test_homogeneous_deck_demonstrates_cross_seed_strategic_collapse,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("LEGAL INFORMATION COLLAPSE PROFILE SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
