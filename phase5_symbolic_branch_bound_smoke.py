#!/usr/bin/env python3
"""Exact Pareto/branch-bound parity regression for Phase-5 Monte Carlo."""

import urza_solver as solver

from non_oracle_episode import NonOracleEpisodeResult
from non_oracle_runtime import make_runtime_state
from non_oracle_rules_adapter_v2 import rules_decision_request
from phase5_monte_carlo import Phase5MonteCarloDecisionEvaluator
from phase5_rollout_policy_v6 import DeterministicRolloutPolicyV6


def main():
    policy=DeterministicRolloutPolicyV6()
    runtime=make_runtime_state(solver.State(
        turn=1,
        library=(
            "Mystical Tutor",
            "Transmute Artifact",
            "Island",
            "Mishra's Bauble",
            "Lotus Petal",
        ),
        hand=(
            "Island",
            "Mishra's Bauble",
            "Lotus Petal",
            "Sol Ring",
        ),
        battlefield=(),
        blue=4,
        colorless=4,
        rng_root_seed=424242,
    ))
    request=rules_decision_request(
        runtime,horizon=2,policy_id=policy.policy_id
    )
    candidates=tuple(request.actions[:min(6,len(request.actions))])
    assert len(candidates)>=4,len(candidates)

    winner_key=candidates[0].strategic_key()
    second_key=candidates[1].strategic_key()
    base=candidates[-1]

    calls={action.strategic_key():0 for action in candidates}

    def controlled_runner(after,*,root_action,horizon,policy,max_steps):
        key=root_action.strategic_key()
        calls[key]+=1
        if key==winner_key:
            return NonOracleEpisodeResult(
                after,(),horizon,1,"synthetic_t1","win"
            )
        if key==second_key:
            return NonOracleEpisodeResult(
                after,(),horizon,2,"synthetic_t2","win"
            )
        return NonOracleEpisodeResult(
            after,(),horizon,None,"","horizon"
        )

    full=Phase5MonteCarloDecisionEvaluator(
        rollout_count=4,
        mc_root_seed=20260828,
        horizon=2,
        continuation_policy=policy,
        max_episode_steps=32,
        strict_terminal_reasons=True,
        continuation_runner=controlled_runner,
        continuation_id="branch-bound-parity",
        sample_namespace="parity",
    ).evaluate(runtime,candidate_actions=candidates)

    full_calls=dict(calls)
    for key in calls:
        calls[key]=0

    pruned=Phase5MonteCarloDecisionEvaluator(
        rollout_count=4,
        mc_root_seed=20260828,
        horizon=2,
        continuation_policy=policy,
        max_episode_steps=32,
        strict_terminal_reasons=True,
        continuation_runner=controlled_runner,
        continuation_id="branch-bound-parity",
        sample_namespace="parity",
    ).evaluate(
        runtime,
        candidate_actions=candidates,
        retain_top_n=1,
        must_retain_actions=(base,),
        exact_branch_bound=True,
    )

    assert full.best_action.strategic_key()==pruned.best_action.strategic_key()
    full_map={
        row.action.strategic_key():row
        for row in full.estimates
    }
    for row in pruned.estimates:
        reference=full_map[row.action.strategic_key()]
        assert row.value==reference.value
        assert row.outcomes==reference.outcomes

    assert any(
        row.action.strategic_key()==base.strategic_key()
        for row in pruned.estimates
    )
    assert pruned.candidate_count==len(candidates)
    assert pruned.branch_pruned_count>=1
    assert pruned.pareto_pruned_count>=1

    pruned_calls=dict(calls)
    assert sum(pruned_calls.values())<sum(full_calls.values()),(
        full_calls,pruned_calls
    )
    assert calls[base.strategic_key()]==4
    assert calls[winner_key]==4

    # All returned rows have their complete fixed sample set. Pruned rows are
    # simply absent because their mathematical best case could not enter top-1.
    assert all(row.rollouts==4 for row in pruned.estimates)

    print(f"full rollout evaluations: {sum(full_calls.values())}")
    print(f"branch-bound rollout evaluations: {sum(pruned_calls.values())}")
    print(f"branch-pruned actions: {pruned.branch_pruned_count}")
    print(f"Pareto-proven pruned actions: {pruned.pareto_pruned_count}")
    print("best action/value identical to unpruned fixed-sample Q: PASS")
    print("must-retain baseline remains fully paired: PASS")
    print("exact branch-and-bound skips provable losers: PASS")


if __name__=="__main__":
    main()
