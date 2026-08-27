#!/usr/bin/env python3
"""Regression for strategic Phase-5 Q memoization."""

import urza_solver as solver

from non_oracle_episode import run_deterministic_episode
from non_oracle_runtime import make_runtime_state
from non_oracle_rules_adapter_v2 import rules_decision_request
from phase5_monte_carlo import (
    Phase5DecisionCache,
    Phase5MonteCarloDecisionEvaluator,
)
from phase5_rollout_policy_v6 import DeterministicRolloutPolicyV6


def main():
    policy=DeterministicRolloutPolicyV6()
    cache=Phase5DecisionCache()
    evaluator=Phase5MonteCarloDecisionEvaluator(
        rollout_count=1,
        mc_root_seed=20260826,
        horizon=2,
        continuation_policy=policy,
        max_episode_steps=128,
        strict_terminal_reasons=True,
        cache=cache,
    )

    # Same strategic belief/public state, different concrete hidden order.
    state_a=solver.State(
        turn=1,
        library=("Transmute Artifact","Sea Gate Restoration","Island"),
        hand=("Mystical Tutor",),
        battlefield=(),
        blue=1,
        rng_root_seed=11,
    )
    state_b=solver.State(
        turn=1,
        library=("Island","Sea Gate Restoration","Transmute Artifact"),
        hand=("Mystical Tutor",),
        battlefield=(),
        blue=1,
        rng_root_seed=999,
    )
    a=make_runtime_state(state_a)
    b=make_runtime_state(state_b)

    first=evaluator.evaluate(a)
    assert cache.stats.misses==1 and cache.stats.hits==0
    second=evaluator.evaluate(b)
    assert cache.stats.misses==1 and cache.stats.hits==1
    assert first.best_action.strategic_key()==second.best_action.strategic_key()
    assert [x.value for x in first.estimates]==[x.value for x in second.estimates]

    # Candidate-set identity is part of the cache key.
    request=rules_decision_request(
        b,horizon=2,policy_id=policy.policy_id
    )
    tutor=tuple(
        action for action in request.actions
        if action.kind=="main_use_simple_tutor"
    )
    assert tutor
    evaluator.evaluate(b,candidate_actions=tutor)
    assert cache.stats.misses==2
    assert len(cache)==2

    # Continuation policy semantics are part of Q identity. A bounded contingent
    # evaluator must never hit a plain-v6 row merely because state/actions match.
    def equivalent_runner(runtime,*,root_action,horizon,policy,max_steps):
        return run_deterministic_episode(
            runtime,horizon=horizon,policy=policy,max_steps=max_steps
        )

    contingent_namespace=Phase5MonteCarloDecisionEvaluator(
        rollout_count=1,
        mc_root_seed=20260826,
        horizon=2,
        continuation_policy=policy,
        max_episode_steps=128,
        strict_terminal_reasons=True,
        cache=cache,
        continuation_runner=equivalent_runner,
        continuation_id="test-contingent-continuation-v1",
    )
    contingent_namespace.evaluate(b,candidate_actions=tutor)
    assert cache.stats.misses==3
    assert len(cache)==3

    # Screen and confirmation samples are deliberately disjoint namespaces.
    # They must not share a cached Q row even when every other evaluator input
    # is identical.
    screen_namespace=Phase5MonteCarloDecisionEvaluator(
        rollout_count=1,
        mc_root_seed=20260826,
        horizon=2,
        continuation_policy=policy,
        max_episode_steps=128,
        strict_terminal_reasons=True,
        cache=cache,
        sample_namespace="screen",
    )
    confirm_namespace=Phase5MonteCarloDecisionEvaluator(
        rollout_count=1,
        mc_root_seed=20260826,
        horizon=2,
        continuation_policy=policy,
        max_episode_steps=128,
        strict_terminal_reasons=True,
        cache=cache,
        sample_namespace="confirm",
    )
    screen_namespace.evaluate(b,candidate_actions=tutor)
    assert cache.stats.misses==4
    confirm_namespace.evaluate(b,candidate_actions=tutor)
    assert cache.stats.misses==5
    assert len(cache)==5

    print("strategic Q cache ignores hidden order/RNG provenance: PASS")
    print("candidate strategic-action set namespaces cache entries: PASS")
    print("continuation semantics namespace strategic Q cache entries: PASS")
    print("screen/confirm hidden-world namespaces are cache-distinct: PASS")
    print("PHASE5 MONTE CARLO CACHE SMOKE: ALL PASS")


if __name__=="__main__":
    main()
