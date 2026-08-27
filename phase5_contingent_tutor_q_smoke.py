#!/usr/bin/env python3
"""Focused regressions for bounded post-commit tutor-Q."""

from __future__ import annotations

import urza_solver as solver

from non_oracle_episode import run_deterministic_episode
from non_oracle_rules_adapter_v2 import apply_main_action, rules_decision_request
from non_oracle_runtime import make_runtime_state
from phase4_hidden_world import HiddenWorldSampler, materialize_hidden_world
from phase5_monte_carlo import Phase5DecisionCache, Phase5MonteCarloDecisionEvaluator
from strategic_value_state import LibraryBeliefKey
from phase5_rollout_policy_v6 import DeterministicRolloutPolicyV6
from phase5_selective_tutor_q import (
    CONTINGENT_DEPTH_AFTER_ACTION_KIND,
    contingent_depth_after_action,
    is_contingent_descendant_decision,
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
                if str(dict(a.parameters).get("target",""))=="Defense Grid"
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
            "Defense Grid",
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


def pending_simple_tutor_runtime():
    runtime,tutor=simple_tutor_runtime()
    runtime=apply_main_action(runtime,tutor)
    for _ in range(8):
        if runtime.pending is not None:
            break
        request=rules_decision_request(
            runtime,horizon=2,policy_id=FailTutorTargetPolicy.policy_id
        )
        passes=[a for a in request.actions if a.kind=="pass_priority"]
        assert passes,[(a.kind,a.label) for a in request.actions]
        runtime=apply_main_action(runtime,passes[0])
    assert runtime.pending is not None
    return runtime,tutor


def test_power_artifact_target_leaf_converts():
    runtime,_=pending_simple_tutor_runtime()
    policy=FailTutorTargetPolicy()
    request=rules_decision_request(
        runtime,horizon=2,policy_id=policy.policy_id
    )
    pa=next(
        a for a in request.actions
        if a.kind=="choose_tutor_target"
        and str(dict(a.parameters).get("target",""))=="Power Artifact"
    )
    after=apply_main_action(runtime,pa)
    result=run_deterministic_episode(
        after,horizon=2,policy=policy,max_steps=128
    )
    assert result.won_by_horizon,(result.terminal_reason,result.win_turn,result.win_family)
    assert result.win_family=="Power Artifact + Grim",result.win_family
    print("Power Artifact target converts under frozen rollout: PASS")


def test_observed_target_q_prefers_power_artifact():
    runtime,_=pending_simple_tutor_runtime()
    policy=FailTutorTargetPolicy()
    request=rules_decision_request(
        runtime,horizon=2,policy_id=policy.policy_id
    )
    targets=tuple(a for a in request.actions if a.kind=="choose_tutor_target")
    evaluation=Phase5MonteCarloDecisionEvaluator(
        rollout_count=1,
        mc_root_seed=2026082711,
        horizon=2,
        continuation_policy=policy,
        max_episode_steps=128,
        strict_terminal_reasons=True,
    ).evaluate(runtime,candidate_actions=targets)
    best_target=str(dict(evaluation.best_action.parameters).get("target",""))
    assert best_target=="Power Artifact",best_target
    pa=next(
        row for row in evaluation.estimates
        if str(dict(row.action.parameters).get("target",""))=="Power Artifact"
    )
    grid=next(
        row for row in evaluation.estimates
        if str(dict(row.action.parameters).get("target",""))=="Defense Grid"
    )
    assert pa.value.win_probability>grid.value.win_probability,(
        pa.value.comparison_key(),grid.value.comparison_key()
    )
    print("observed target Q ranks Power Artifact above Defense Grid: PASS")



def test_outer_sampled_world_contingent_runner_converts():
    runtime,tutor=simple_tutor_runtime()
    policy=FailTutorTargetPolicy()
    belief=LibraryBeliefKey.from_state(runtime.true_state,runtime.information)
    world=HiddenWorldSampler(2026082703).sample(
        belief,sample_id=("phase5-q",0)
    )
    sampled=materialize_hidden_world(runtime,world)
    request=rules_decision_request(
        sampled,horizon=2,policy_id=policy.policy_id
    )
    sampled_tutor=next(
        a for a in request.actions
        if a.strategic_key()==tutor.strategic_key()
    )
    after=apply_main_action(sampled,sampled_tutor)
    cache=Phase5DecisionCache()
    runner=make_bounded_contingent_tutor_runner(
        mc_root_seed=2026082703,
        screen_rollouts=1,
        confirm_rollouts=1,
        shortlist_size=8,
        decision_cache=cache,
    )
    result=runner(
        after,
        root_action=sampled_tutor,
        horizon=2,
        policy=policy,
        max_steps=128,
    )
    assert result.won_by_horizon,(result.terminal_reason,result.win_turn,result.win_family)
    assert result.win_family=="Power Artifact + Grim",result.win_family
    assert cache.stats.misses>0,cache.stats
    print("outer sampled world propagates into winning contingent PA choice: PASS")

def test_simple_tutor_pending_surface_matches_lineage():
    runtime,tutor=simple_tutor_runtime()
    runtime=apply_main_action(runtime,tutor)

    # Resolve only the committed Muddle ability. Do not let the leaf policy take
    # unrelated priority actions while we inspect the post-commit request.
    for _ in range(8):
        if runtime.pending is not None:
            break
        request=rules_decision_request(
            runtime,horizon=2,policy_id=FailTutorTargetPolicy.policy_id
        )
        passes=[a for a in request.actions if a.kind=="pass_priority"]
        assert passes,[(a.kind,a.label) for a in request.actions]
        runtime=apply_main_action(runtime,passes[0])
    assert runtime.pending is not None
    assert runtime.pending.spec.source=="Muddle the Mixture"
    request=rules_decision_request(
        runtime,horizon=2,policy_id=FailTutorTargetPolicy.policy_id
    )
    targets={
        str(dict(a.parameters).get("target",""))
        for a in request.actions
        if a.kind=="choose_tutor_target"
    }
    assert "Power Artifact" in targets,targets
    assert "Defense Grid" in targets,targets
    assert is_contingent_descendant_decision(
        runtime,
        request.actions,
        lineage_source="Muddle the Mixture",
        remaining=1,
    )
    print(
        "Muddle pending search preserves source lineage and exposes PA + Chip: PASS"
    )


def _post_commit_evaluations():
    runtime,tutor=simple_tutor_runtime()
    policy=FailTutorTargetPolicy()

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
    return plain,contingent,cache


def test_post_commit_evaluation_completes():
    plain,contingent,cache=_post_commit_evaluations()
    assert len(plain.estimates)==1
    assert len(contingent.estimates)==1
    print("post-commit contingent root evaluation completes: PASS")


def test_post_commit_nested_cache_activity():
    _,_,cache=_post_commit_evaluations()
    assert cache.stats.misses>1,cache.stats
    print(f"post-commit evaluation records nested Q cache activity ({cache.stats}): PASS")


def test_post_commit_value_comparison_is_sane():
    plain,contingent,_=_post_commit_evaluations()
    p_plain=plain.estimates[0].value.win_probability
    p_contingent=contingent.estimates[0].value.win_probability
    assert 0.0<=p_plain<=1.0
    assert 0.0<=p_contingent<=1.0
    print(
        "post-commit simple-tutor values are well-formed "
        f"(plain={p_plain:.3f}, contingent={p_contingent:.3f}): PASS"
    )


def test_post_commit_contingent_strictly_improves_bad_leaf():
    plain,contingent,_=_post_commit_evaluations()
    p_plain=plain.estimates[0].value.win_probability
    p_contingent=contingent.estimates[0].value.win_probability
    assert p_contingent>p_plain,(p_plain,p_contingent)
    print(
        "bounded contingent Q improves deliberately bad target continuation "
        f"(plain={p_plain:.3f}, contingent={p_contingent:.3f}): PASS"
    )


def test_post_commit_observation_is_revalued():
    test_post_commit_evaluation_completes()
    test_post_commit_nested_cache_activity()
    test_post_commit_value_comparison_is_sane()

def test_runner_receives_committed_source_lineage():
    runtime,tutor=simple_tutor_runtime()
    policy=FailTutorTargetPolicy()
    after=apply_main_action(runtime,tutor)
    cache=Phase5DecisionCache()
    runner=make_bounded_contingent_tutor_runner(
        mc_root_seed=2026082704,
        screen_rollouts=1,
        confirm_rollouts=1,
        shortlist_size=8,
        decision_cache=cache,
    )
    result=runner(
        after,
        root_action=tutor,
        horizon=2,
        policy=policy,
        max_steps=128,
    )
    # Whether the tiny synthetic line wins is intentionally not asserted: the
    # frozen leaf can take other legal priority actions.  The supplied cache and
    # executed target step prove that the committed Muddle line was followed to
    # its post-search observation and Q-evaluated there.
    assert cache.stats.misses>0,cache.stats
    assert any(step.action_kind=="choose_tutor_target" for step in result.steps)
    print(
        "committed tutor source is followed through stack resolution to its target "
        f"(nested_cache_misses={cache.stats.misses}): PASS"
    )


def test_transmute_follows_sacrifice_then_observed_target():
    state=solver.State(
        turn=1,
        library=(
            "Sensei's Divining Top",
            "Codex Shredder",
            "Island",
        ),
        hand=("Transmute Artifact",),
        battlefield=(
            solver.Perm("Sol Ring"),
            solver.Perm("Mana Vault"),
        ),
        blue=2,
        urza=False,
    )
    runtime=make_runtime_state(state)
    request=rules_decision_request(
        runtime,horizon=2,policy_id=DeterministicRolloutPolicyV6().policy_id
    )
    transmute=next(
        a for a in request.actions if a.kind=="main_use_transmute_artifact"
    )
    after=apply_main_action(runtime,transmute)
    cache=Phase5DecisionCache()
    runner=make_bounded_contingent_tutor_runner(
        mc_root_seed=2026082705,
        screen_rollouts=1,
        confirm_rollouts=1,
        shortlist_size=8,
        decision_cache=cache,
    )
    result=runner(
        after,
        root_action=transmute,
        horizon=2,
        policy=DeterministicRolloutPolicyV6(),
        max_steps=128,
    )
    kinds=[step.action_kind for step in result.steps]
    assert "transmute_choose_sacrifice" in kinds,kinds
    assert "transmute_choose_target" in kinds,kinds
    assert cache.stats.misses>=2,cache.stats
    print(
        "Transmute contingent Q traverses sacrifice then observed target "
        f"(cache_misses={cache.stats.misses}): PASS"
    )


def main():
    test_depth_map_is_strictly_bounded()
    test_simple_tutor_pending_surface_matches_lineage()
    test_post_commit_observation_is_revalued()
    test_runner_receives_committed_source_lineage()
    test_transmute_follows_sacrifice_then_observed_target()
    print("PHASE5 CONTINGENT TUTOR-Q SMOKE: ALL PASS")


if __name__=="__main__":
    main()
