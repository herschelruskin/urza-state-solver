#!/usr/bin/env python3
"""Fast regression for the decision-neutral strategic collapse profiler."""

import urza_solver as solver
from strategic_collapse_profile import run_profile


def test_two_seed_profile_exposes_cross_seed_strategic_collapse():
    # Identical-card library makes hidden order irrelevant by construction. The
    # concrete keys still differ across root seeds, so the aggregate profiler
    # must show strategic collapse without relying on card-specific gameplay.
    deck = ["Island"] * 99
    old_cap = solver.ACTION_CAP
    payload = run_profile(
        deck,
        base_seed=101,
        count=2,
        step=1,
        max_turn=1,
        beam=8,
        depth=2,
        action_cap=8,
    )

    assert solver.ACTION_CAP == old_cap
    assert payload["decision_neutral"] is True
    assert "upper-bound" in payload["information_assumption"]
    assert len(payload["seeds"]) == 2

    overall = payload["overall"]
    assert overall["observations"] > 0
    assert overall["concrete_unique"] > overall["strategic_unique"]
    assert overall["concrete_to_strategic_collapse_fraction"] > 0.0
    assert overall["estimated_strategic_cache_hit_fraction"] > 0.0
    assert overall["by_turn_depth"]
    assert any(key.startswith("T1D") for key in overall["by_turn_depth"])


def test_profile_rows_preserve_search_outcome_shape():
    payload = run_profile(
        ["Island"] * 99,
        base_seed=303,
        count=1,
        step=1,
        max_turn=1,
        beam=4,
        depth=1,
        action_cap=4,
    )
    row = payload["seeds"][0]
    assert row["seed"] == 303
    assert row["win_turn"] is None
    assert row["family"] == ""
    assert row["searched"] >= 1
    assert "graph" in row
    assert "strategic" in row


def main():
    tests = [
        test_two_seed_profile_exposes_cross_seed_strategic_collapse,
        test_profile_rows_preserve_search_outcome_shape,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("STRATEGIC COLLAPSE PROFILE SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
