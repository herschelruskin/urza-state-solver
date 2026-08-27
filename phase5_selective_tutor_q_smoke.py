#!/usr/bin/env python3
"""Focused controller semantics for selective tutor-Q policy improvement."""

from dataclasses import dataclass

import urza_solver as solver
from non_oracle_rules_adapter_v2 import rules_decision_request
from non_oracle_runtime import make_runtime_state
from phase3_value_engine import WinDistributionValue
from phase5_monte_carlo import Phase5ActionEstimate,Phase5DecisionEvaluation
from phase5_selective_tutor_q import SelectiveTutorQController


class StubPolicy:
    policy_id="stub-tutor-policy"

    def choose(self,observation,actions,context):
        for action in actions:
            if action.label=="Use Mystical Tutor":
                return action
        return sorted(actions,key=lambda a:a.action_id)[0]


def value(p):
    return WinDistributionValue(
        horizon=6,
        exact_win=(0.0,0.0,0.0,0.0,0.0,float(p)),
        no_win=1.0-float(p),
        win_families=(),
    )


def estimate(action,p):
    return Phase5ActionEstimate(
        action=action,
        value=value(p),
        rollouts=4,
        terminal_reason_counts=(("horizon",4),),
        win_probability_wilson95=(0.0,1.0),
    )


class FakeEvaluator:
    def __init__(self,prob_by_kind):
        self.prob_by_kind=dict(prob_by_kind)

    def evaluate(self,runtime,*,candidate_actions=None):
        actions=tuple(candidate_actions)
        estimates=tuple(
            sorted(
                (estimate(a,self.prob_by_kind.get(a.kind,0.0)) for a in actions),
                key=lambda row:(
                    row.value.comparison_key(),
                    repr(row.action.strategic_key()),
                ),
                reverse=True,
            )
        )
        return Phase5DecisionEvaluation(
            best_action=estimates[0].action,
            estimates=estimates,
            rollout_count_per_action=4,
            mc_root_seed=1,
            horizon=6,
            continuation_policy_id="stub-tutor-policy",
        )


def runtime_and_request():
    state=solver.State(
        turn=4,
        library=("Sea Gate Restoration","Island","Sol Ring"),
        hand=("Mystical Tutor",),
        battlefield=(solver.Perm("Island"),),
        blue=1,
    )
    runtime=make_runtime_state(state)
    request=rules_decision_request(
        runtime,horizon=6,policy_id="stub-tutor-policy"
    )
    return runtime,request


def test_strict_improvement_overrides():
    runtime,request=runtime_and_request()
    controller=SelectiveTutorQController(
        continuation_policy=StubPolicy(),
        screen_rollouts=1,
        confirm_rollouts=1,
    )
    controller.screen=FakeEvaluator({
        "main_use_simple_tutor":0.0,
        "main_end_turn":0.25,
    })
    controller.confirm=FakeEvaluator({
        "main_use_simple_tutor":0.0,
        "main_end_turn":0.25,
    })
    chosen,meta=controller.choose(runtime,request,request.actions)
    assert chosen.kind=="main_end_turn",chosen
    assert meta is not None
    assert meta[0].label=="Use Mystical Tutor"
    assert meta[1].kind=="main_end_turn"
    print("strict downstream Q improvement overrides v6: PASS")


def test_equal_value_keeps_v6():
    runtime,request=runtime_and_request()
    controller=SelectiveTutorQController(
        continuation_policy=StubPolicy(),
        screen_rollouts=1,
        confirm_rollouts=1,
    )
    controller.screen=FakeEvaluator({
        "main_use_simple_tutor":0.5,
        "main_end_turn":0.5,
    })
    controller.confirm=FakeEvaluator({
        "main_use_simple_tutor":0.5,
        "main_end_turn":0.5,
    })
    chosen,meta=controller.choose(runtime,request,request.actions)
    assert chosen.label=="Use Mystical Tutor",chosen
    assert meta is not None
    assert meta[4]==meta[5]
    print("equal Q value preserves deterministic v6 choice: PASS")


def test_transmute_payment_not_q_controlled():
    # Candidate classifier is tested without needing to walk the full Transmute
    # stack: a fake action kind with the exact payment kind must return no Q set.
    runtime,request=runtime_and_request()
    controller=SelectiveTutorQController(
        continuation_policy=StubPolicy(),
        screen_rollouts=1,
        confirm_rollouts=1,
    )
    base=next(a for a in request.actions if a.label=="Use Mystical Tutor")
    payment=type(base)(
        action_id="test.transmute.pay",
        kind="transmute_pay_difference",
        parameters=(),
        equivalence_key=("transmute_pay_difference","pay"),
        label="Pay 1",
        decision_stage=base.decision_stage,
        source="Transmute Artifact",
    )

    class PayPolicy:
        policy_id="stub-pay-policy"
        def choose(self,observation,actions,context):
            return actions[0]

    controller.policy=PayPolicy()
    fake_request=type(request)(
        observation=request.observation,
        actions=(payment,),
        context=request.context,
    )
    chosen,meta=controller.choose(runtime,fake_request,(payment,))
    assert chosen.kind=="transmute_pay_difference"
    assert meta is None
    print("Transmute payment remains invariant outside tutor-Q: PASS")


def test_end_turn_with_live_tutor_is_q_evaluated():
    runtime,request=runtime_and_request()

    class EndPolicy:
        policy_id="stub-end-policy"
        def choose(self,observation,actions,context):
            return next(a for a in actions if a.kind=="main_end_turn")
        def action_score(self,observation,action,context):
            return 0.0

    controller=SelectiveTutorQController(
        continuation_policy=EndPolicy(),
        screen_rollouts=1,
        confirm_rollouts=1,
    )
    controller.screen=FakeEvaluator({
        "main_use_simple_tutor":0.75,
        "main_end_turn":0.0,
    })
    controller.confirm=FakeEvaluator({
        "main_use_simple_tutor":0.75,
        "main_end_turn":0.0,
    })
    chosen,meta=controller.choose(runtime,request,request.actions)
    assert chosen.kind=="main_use_simple_tutor",chosen
    assert meta is not None
    assert meta[0].kind=="main_end_turn"
    assert meta[1].kind=="main_use_simple_tutor"
    print("end-turn with castable tutor is eligible for Q rescue: PASS")


def test_screen_shortlist_preserves_exact_value_ties():
    runtime,request=runtime_and_request()
    base=next(a for a in request.actions if a.label=="Use Mystical Tutor")
    targets=tuple(
        type(base)(
            action_id=f"test.target.{i}",
            kind="choose_tutor_target",
            parameters=(("target",name),),
            equivalence_key=("tutor_target","Mystical Tutor",name),
            label=f"Mystical Tutor -> {name}",
            decision_stage=base.decision_stage,
            source="Mystical Tutor",
        )
        for i,name in enumerate(("Sea Gate Restoration","Transmute Artifact","Reshape"))
    )

    class TargetPolicy:
        policy_id="stub-target-policy"
        def choose(self,observation,actions,context):
            return actions[0]

    controller=SelectiveTutorQController(
        continuation_policy=TargetPolicy(),
        screen_rollouts=1,
        confirm_rollouts=1,
        shortlist_size=1,
    )
    controller.screen=FakeEvaluator({"choose_tutor_target":0.0})
    controller.confirm=FakeEvaluator({"choose_tutor_target":0.0})
    fake_request=type(request)(
        observation=request.observation,
        actions=targets,
        context=request.context,
    )
    chosen,meta=controller.choose(runtime,fake_request,targets)
    assert chosen.strategic_key()==targets[0].strategic_key()
    assert meta is not None
    assert meta[2]==3
    assert meta[3]==3,meta
    print("exact screen ties all survive tutor-Q confirmation: PASS")


def main():
    test_strict_improvement_overrides()
    test_equal_value_keeps_v6()
    test_transmute_payment_not_q_controlled()
    test_end_turn_with_live_tutor_is_q_evaluated()
    test_screen_shortlist_preserves_exact_value_ties()
    print("PHASE5 SELECTIVE TUTOR-Q SMOKE: ALL PASS")


if __name__=="__main__":
    main()
