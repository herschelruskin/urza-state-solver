#!/usr/bin/env python3
"""Regression for compact fixed-size Phase-5 cache identities."""

import urza_solver as solver

from non_oracle_runtime import make_runtime_state
from phase5_monte_carlo import Phase5DecisionCache, Phase5MonteCarloDecisionEvaluator
from phase5_rollout_policy_v6 import DeterministicRolloutPolicyV6


def signature(result):
    return (
        result.best_action.strategic_key(),
        tuple(
            (row.action.strategic_key(),row.value.comparison_key(),row.terminal_reason_counts)
            for row in result.estimates
        ),
    )


def main():
    policy=DeterministicRolloutPolicyV6()
    state=solver.State(
        turn=1,
        library=("Transmute Artifact","Sea Gate Restoration","Island"),
        hand=("Mystical Tutor",),
        battlefield=(),
        blue=1,
        rng_root_seed=11,
    )
    runtime=make_runtime_state(state)

    reference=Phase5MonteCarloDecisionEvaluator(
        rollout_count=1,
        mc_root_seed=20260826,
        horizon=2,
        continuation_policy=policy,
        max_episode_steps=128,
        strict_terminal_reasons=True,
        cache=None,
    ).evaluate(runtime)

    cache=Phase5DecisionCache(max_entries=512)
    evaluator=Phase5MonteCarloDecisionEvaluator(
        rollout_count=1,
        mc_root_seed=20260826,
        horizon=2,
        continuation_policy=policy,
        max_episode_steps=128,
        strict_terminal_reasons=True,
        cache=cache,
    )
    first=evaluator.evaluate(runtime)
    second=evaluator.evaluate(runtime)
    assert signature(first)==signature(reference)==signature(second)
    assert cache.stats.misses==1 and cache.stats.hits==1
    assert len(cache)==1
    retained_keys=tuple(cache._rows.keys())
    assert all(isinstance(key,bytes) and len(key)==32 for key in retained_keys)
    cached=next(iter(cache._rows.values()))
    assert isinstance(cached.best_strategic_action_key_digest,bytes)
    assert len(cached.best_strategic_action_key_digest)==32
    assert all(
        isinstance(row.strategic_action_key_digest,bytes)
        and len(row.strategic_action_key_digest)==32
        for row in cached.estimates
    )
    print("compact cache identity parity: PASS")
    print("retained Q state/action identities are fixed 32-byte digests: PASS")


if __name__=="__main__":
    main()
