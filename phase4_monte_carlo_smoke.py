#!/usr/bin/env python3
"""Acceptance smokes for common-world Monte Carlo root-action evaluation."""

from __future__ import annotations

from dataclasses import replace

import urza_solver as solver
from non_oracle_runtime import make_runtime_state
from phase4_monte_carlo import MonteCarloRootEvaluator


LIBRARY_A = (
    "Island",
    "Welding Jar",
    "Mox Opal",
    "Mana Vault",
    "Everflowing Chalice",
    "Sensei's Divining Top",
)
LIBRARY_B = (
    "Mana Vault",
    "Sensei's Divining Top",
    "Island",
    "Everflowing Chalice",
    "Welding Jar",
    "Mox Opal",
)


def simple_runtime(library, *, actual_seed):
    return make_runtime_state(
        solver.State(
            turn=1,
            library=tuple(library),
            hand=("Island", "Sol Ring", "Prized Statue"),
            battlefield=(),
            rng_root_seed=int(actual_seed),
        )
    )


def evaluation_signature(result):
    return (
        result.best_action.strategic_key(),
        tuple(
            (
                estimate.action.strategic_key(),
                estimate.value,
                estimate.rollouts,
                estimate.terminal_reason_counts,
                estimate.win_probability_wilson95,
                estimate.cumulative_wilson95,
            )
            for estimate in result.estimates
        ),
    )


def test_same_belief_ignores_actual_hidden_order_and_actual_game_seed():
    left_runtime = simple_runtime(LIBRARY_A, actual_seed=101)
    right_runtime = simple_runtime(LIBRARY_B, actual_seed=999999)
    evaluator = MonteCarloRootEvaluator(
        rollout_count=8,
        mc_root_seed=20260826,
        horizon=2,
    )
    left = evaluator.evaluate(left_runtime)
    right = evaluator.evaluate(right_runtime)
    assert evaluation_signature(left) == evaluation_signature(right)


def test_repeated_evaluation_is_deterministic_and_does_not_mutate_actual_runtime():
    runtime = simple_runtime(LIBRARY_A, actual_seed=777)
    before = runtime
    evaluator = MonteCarloRootEvaluator(
        rollout_count=8,
        mc_root_seed=424242,
        horizon=2,
    )
    one = evaluator.evaluate(runtime)
    two = evaluator.evaluate(runtime)
    assert evaluation_signature(one) == evaluation_signature(two)
    assert runtime == before
    assert runtime.true_state.library == LIBRARY_A
    assert runtime.true_state.rng_root_seed == 777


def test_all_root_actions_receive_same_budget_and_valid_distribution():
    runtime = simple_runtime(LIBRARY_A, actual_seed=0)
    result = MonteCarloRootEvaluator(
        rollout_count=6,
        mc_root_seed=12345,
        horizon=2,
    ).evaluate(runtime)
    assert len(result.estimates) >= 2
    assert result.rollout_count_per_action == 6
    assert result.best_action.strategic_key() == result.estimates[0].action.strategic_key()
    for estimate in result.estimates:
        assert estimate.rollouts == 6
        assert abs(sum(estimate.value.exact_win) + estimate.value.no_win - 1.0) < 1e-12
        low, high = estimate.win_probability_wilson95
        assert 0.0 <= low <= high <= 1.0
        assert len(estimate.cumulative_wilson95) == 2
        assert sum(count for _, count in estimate.terminal_reason_counts) == 6


def main():
    tests = (
        test_same_belief_ignores_actual_hidden_order_and_actual_game_seed,
        test_repeated_evaluation_is_deterministic_and_does_not_mutate_actual_runtime,
        test_all_root_actions_receive_same_budget_and_valid_distribution,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("PHASE 4 MONTE CARLO ROOT EVALUATION SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
