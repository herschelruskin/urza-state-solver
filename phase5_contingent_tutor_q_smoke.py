#!/usr/bin/env python3
"""Focused regressions for bounded post-commit tutor-Q."""

from __future__ import annotations

import urza_solver as solver

from non_oracle_rules_adapter_v2 import apply_main_action, rules_decision_request
from non_oracle_runtime import make_runtime_state
from phase5_monte_carlo import Phase5DecisionCache, Phase5MonteCarloDecisionEvaluator
from phase5_rollout_policy_v6 import DeterministicRolloutPolicyV6
from phase5_selective_tutor_q import (
    CONTINGENT_DEPTH_AFTER_ACTION_KIND,
    contingent_depth_after_action,
    make_bounded_contingent_tutor_runner,
)


class FailTutorTargetPolicy:
    """v6 everywhere except deliberately choose a nonwinning simple target."""

    policy_id="test-v6-fail-simple-target"

    def __init__(self):
        self.base=DeterministicRolloutPolicyV6(policy_id=self.policy_id)

    def choose(self,observation,actions,context):
        targets=[a for a in actions if a.kind=="choose_tutor_target"]
        if targets:
            bad=[
                a for a in targets
                if str(dict(a.parameters).get("target",""))=="The Reality Chip"
            ]
            if bad:
                return sorted(bad,key=lambda a:a.action_id)[0]
        return self.base.choose(observation,actions,context)

    def action_score(self,observation,action,context):
        return self.base.action_score(observation,action,context)


def test_depth_map_is_strictly_bounded():
    assert CONTINGENT_DEPTH_AFTER_ACTION_KIND["main_use_simple_tutor"]==1
    assert CONTINGENT_DEPTH_AFTER_ACTION_KIND["main_use_x_artifact_tutor"]==1
    assert CONTINGENT_DEPTH_AFTER_ACTION_KIND["main_activate_repurposing_bay"]==1
    assert CONTINGENT_DEPTH_AFTER_ACTION_KIND["main_cast_scour_for_scrap"]==1
    assert CONTINGENT_DEPTH_AFTER_ACTION_KIND["main_activate_tezzeret_minus3"]==1
    assert CONTINGENT_DEPTH_AFTER_ACTION_KIND["main_use_transmute_artifact"]==2
    assert CONTINGENT_DEPTH_AFTER_ACTION_KIND["transmute_choose_sacrifice"]==1

    fake=type("A",(),{"kind":"transmute_choose_target"})()
    assert contingent_depth_after_action(fake)==0
    fake=type("A",(),{"kind":"transmute_pay_difference"})()
    assert contingent_depth_after_action(fake)==0
    print("contingent tutor depth map is finite and Transmute payment is leaf-policy only: PASS")


def simple_tutor_runtime():
    # Muddle transmute can find Power Artifact (MV2).  With Urza + Grim already
    # online, putting PA in hand and casting it is a deterministic terminal line.
    state=solver.State(
        turn=1,
        library=(
            "Power Artifact",
            "The Reality Chip",
            "Island",
            "Mana Vault",
        ),
        hand=("Muddle the Mixture",),
        battlefield=(solver.Perm("Grim Monolith"),),
        blue=8,
        urza=True,
    )
    runtime=make_runtime_state(state)
    request=rules_decision_request(
        runtime,horizon=2,policy_id=FailTutorTargetPolicy.policy_id
    )
    tutor=next(
        a for a in request.actions
        if a.kind=="main_use_simple_tutor" and a.source=="Muddle the Mixture"
    )
    return runtime,tutor


def test_post_commit_observation_can_be_q_improved():
    runtime,tutor=simple_tutor_runtime()
    policy=FailTutorTargetPolicy()

    # Plain one-step Q commits the tutor then lets the deliberately bad leaf
    # choose Reality Chip instead of the terminal Power Artifact target.
    plain=Phase5MonteCarloDecisionEvaluator(
        rollout_count=1,
        mc_root_seed=2026082703,
        horizon=2,
        continuation_policy=policy,
        max_episode_steps=128,
        strict_terminal_reasons=True,
    ).evaluate(runtime,candidate_actions=(tutor,))

    cache=Phase5DecisionCache()
    runner=make_bounded_contingent_tutor_runner(
        mc_root_seed=2026082703,
        screen_rollouts=1,
        confirm_rollouts=1,
        shortlist_size=8,
        decision_cache=cache,
    )
    contingent=Phase5MonteCarloDecisionEvaluator(
        rollout_count=1,
        mc_root_seed=2026082703,
        horizon=2,
        continuation_policy=policy,
        max_episode_steps=128,
        strict_terminal_reasons=True,
        cache=cache,
        continuation_runner=runner,
        continuation_id=runner.continuation_id,
    ).evaluate(runtime,candidate_actions=(tutor,))

    p_plain=plain.estimates[0].value.win_probability
    p_contingent=contingent.estimates[0].value.win_probability
    assert p_contingent>=p_plain
    assert p_contingent>0.0,(p_plain,p_contingent)
    print(
        "post-commit simple-tutor observation is Q-improved "
        f"(plain={p_plain:.3f}, contingent={p_contingent:.3f}): PASS"
    )


def test_runner_receives_committed_source_lineage():
    runtime,tutor=simple_tutor_runtime()
    policy=FailTutorTargetPolicy()
    after=apply_main_action(runtime,tutor)
    runner=make_bounded_contingent_tutor_runner(
        mc_root_seed=2026082704,
        screen_rollouts=1,
        confirm_rollouts=1,
        shortlist_size=8,
        decision_cache=Phase5DecisionCache(),
    )
    result=runner(
        after,
        root_action=tutor,
        horizon=2,
        policy=policy,
        max_steps=128,
    )
    # The test leaf intentionally chooses the nonwinning Chip target. A win therefore
    # proves the bounded runner reached the Muddle post-search decision and
    # improved it rather than merely delegating the whole line to the leaf.
    assert result.won_by_horizon,result
    assert result.win_family=="Power Artifact + Grim",result.win_family
    print("committed tutor source is followed through stack resolution to its target: PASS")


def main():
    test_depth_map_is_strictly_bounded()
    test_post_commit_observation_can_be_q_improved()
    test_runner_receives_committed_source_lineage()
    print("PHASE5 CONTINGENT TUTOR-Q SMOKE: ALL PASS")


if __name__=="__main__":
    main()
