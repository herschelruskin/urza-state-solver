#!/usr/bin/env python3
"""Prove bounded Phase-5 cache eviction preserves deterministic Q semantics."""

import urza_solver as solver

from non_oracle_runtime import make_runtime_state
from non_oracle_rules_adapter_v2 import rules_decision_request
from phase5_monte_carlo import Phase5DecisionCache, Phase5MonteCarloDecisionEvaluator
from phase5_rollout_policy_v6 import DeterministicRolloutPolicyV6


def signature(result):
    return (
        result.best_action.strategic_key(),
        tuple(
            (
                row.action.strategic_key(),
                row.value.comparison_key(),
                row.terminal_reason_counts,
            )
            for row in result.estimates
        ),
    )


def make_eval(cache):
    policy=DeterministicRolloutPolicyV6()
    return policy,Phase5MonteCarloDecisionEvaluator(
        rollout_count=1,
        mc_root_seed=20260826,
        horizon=2,
        continuation_policy=policy,
        max_episode_steps=128,
        strict_terminal_reasons=True,
        cache=cache,
    )


def main():
    state=solver.State(
        turn=1,
        library=("Transmute Artifact","Sea Gate Restoration","Island"),
        hand=("Mystical Tutor",),
        battlefield=(),
        blue=1,
        rng_root_seed=11,
    )
    runtime=make_runtime_state(state)

    _,reference_eval=make_eval(Phase5DecisionCache())
    reference=signature(reference_eval.evaluate(runtime))

    bounded=Phase5DecisionCache(max_entries=1)
    policy,bounded_eval=make_eval(bounded)
    first=signature(bounded_eval.evaluate(runtime))
    assert first==reference

    request=rules_decision_request(runtime,horizon=2,policy_id=policy.policy_id)
    tutor=tuple(a for a in request.actions if a.kind=="main_use_simple_tutor")
    assert tutor
    bounded_eval.evaluate(runtime,candidate_actions=tutor)
    assert bounded.stats.evictions>=1
    assert len(bounded)==1

    # The original row has been evicted. Its deterministic recomputation must be
    # bit-for-bit equivalent at the policy/value level.
    after_eviction=signature(bounded_eval.evaluate(runtime))
    assert after_eviction==reference
    assert bounded.stats.evictions>=2

    print("bounded Q cache eviction/recompute parity: PASS")


if __name__=="__main__":
    main()
