#!/usr/bin/env python3
"""Phase 5H adaptive paired-confidence Q regressions."""

from __future__ import annotations

from phase5_selective_tutor_q_smoke import (
    FakeEvaluator,
    StubPolicy,
    runtime_and_request,
)
from phase5_monte_carlo import (
    Phase5ActionEstimate,
    Phase5DecisionEvaluation,
    _value,
    _wilson,
)
from phase5_selective_tutor_q import (
    SelectiveTutorQController,
    paired_q_evidence,
)
from solver_architecture import EpisodeOutcome


def outcome(*,won:bool,turn:int|None=None):
    return EpisodeOutcome(
        won=bool(won),
        win_turn=int(turn) if won and turn is not None else None,
        terminal_turn=int(turn) if won and turn is not None else 6,
        horizon=6,
        win_family="test" if won else "",
        terminal_reason="win" if won else "horizon",
    )


def estimate(action,outcomes):
    rows=tuple(outcomes)
    wins=sum(row.won for row in rows)
    return Phase5ActionEstimate(
        action=action,
        value=_value(rows,horizon=6),
        rollouts=len(rows),
        terminal_reason_counts=(
            ("win",wins),
            ("horizon",len(rows)-wins),
        ),
        win_probability_wilson95=_wilson(wins,len(rows)),
        outcomes=rows,
    )


class PairedFakeEvaluator:
    def __init__(self,rows_by_kind):
        self.rows_by_kind={
            str(kind):tuple(rows)
            for kind,rows in rows_by_kind.items()
        }

    def evaluate(self,runtime,*,candidate_actions=None):
        actions=tuple(candidate_actions)
        estimates=tuple(
            sorted(
                (
                    estimate(
                        action,
                        self.rows_by_kind[str(action.kind)],
                    )
                    for action in actions
                ),
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
            rollout_count_per_action=len(estimates[0].outcomes),
            mc_root_seed=1,
            horizon=6,
            continuation_policy_id="stub-tutor-policy",
        )


def configured_controller(*,max_validation_rollouts=8):
    runtime,request=runtime_and_request()
    controller=SelectiveTutorQController(
        continuation_policy=StubPolicy(),
        screen_rollouts=1,
        confirm_rollouts=2,
        confidence_gate=True,
        validation_rollouts=2,
        max_validation_rollouts=max_validation_rollouts,
        confidence_alpha=0.25,
        contingent=False,
    )
    # Screening and selection confirmation deliberately prefer end turn over the
    # v6 Mystical Tutor choice.  The paired validation worlds decide whether that
    # proposal is actually allowed to override v6.
    controller.screen=FakeEvaluator({
        "main_use_simple_tutor":0.0,
        "main_end_turn":1.0,
    })
    controller.confirm=FakeEvaluator({
        "main_use_simple_tutor":0.0,
        "main_end_turn":1.0,
    })
    return runtime,request,controller


def install_validation_rounds(controller,rounds):
    def evaluator(*,rollout_count,round_index):
        rows=rounds[int(round_index)]
        expected=len(next(iter(rows.values())))
        assert int(rollout_count)==expected,(rollout_count,expected,round_index)
        return PairedFakeEvaluator(rows)
    controller._validation_evaluator=evaluator


def test_paired_evidence_counts_earlier_wins():
    runtime,request=runtime_and_request()
    base=next(a for a in request.actions if a.kind=="main_use_simple_tutor")
    alt=next(a for a in request.actions if a.kind=="main_end_turn")
    cand=estimate(alt,(outcome(won=True,turn=3),outcome(won=True,turn=4)))
    ref=estimate(base,(outcome(won=True,turn=4),outcome(won=True,turn=5)))
    ev=paired_q_evidence(cand,ref)
    assert (ev.better,ev.worse,ev.ties)==(2,0,0),ev
    assert abs(ev.sign_p_one_sided-0.25)<1e-12,ev
    print("paired Q evidence treats earlier wins as better: PASS")


def test_strong_pair_accepts_after_first_validation_batch():
    runtime,request,controller=configured_controller()
    install_validation_rounds(controller,(
        {
            "main_use_simple_tutor":(outcome(won=False),outcome(won=False)),
            "main_end_turn":(outcome(won=True,turn=4),outcome(won=True,turn=5)),
        },
    ))
    chosen,meta=controller.choose(runtime,request,request.actions)
    assert chosen.kind=="main_end_turn",chosen
    assert meta[8]==2,meta
    assert (meta[9],meta[10],meta[11])==(2,0,0),meta
    assert abs(meta[12]-0.25)<1e-12,meta
    assert meta[13]=="paired_confidence_override",meta
    print("2-0 paired evidence accepts override after two fresh validation worlds: PASS")


def test_strong_pair_rejects_bad_proposal_early():
    runtime,request,controller=configured_controller()
    install_validation_rounds(controller,(
        {
            "main_use_simple_tutor":(outcome(won=True,turn=4),outcome(won=True,turn=5)),
            "main_end_turn":(outcome(won=False),outcome(won=False)),
        },
    ))
    chosen,meta=controller.choose(runtime,request,request.actions)
    assert chosen.kind=="main_use_simple_tutor",chosen
    assert meta[8]==2,meta
    assert (meta[9],meta[10],meta[11])==(0,2,0),meta
    assert meta[13]=="paired_confidence_reject",meta
    print("0-2 paired evidence rejects proposal after two fresh validation worlds: PASS")


def test_mixed_evidence_expands_budget_then_falls_back_to_v6():
    runtime,request,controller=configured_controller()
    install_validation_rounds(controller,(
        {
            "main_use_simple_tutor":(outcome(won=False),outcome(won=True,turn=4)),
            "main_end_turn":(outcome(won=True,turn=4),outcome(won=False)),
        },
        {
            "main_use_simple_tutor":(outcome(won=False),outcome(won=True,turn=4)),
            "main_end_turn":(outcome(won=True,turn=4),outcome(won=False)),
        },
        {
            "main_use_simple_tutor":(
                outcome(won=False),outcome(won=True,turn=4),
                outcome(won=False),outcome(won=True,turn=4),
            ),
            "main_end_turn":(
                outcome(won=True,turn=4),outcome(won=False),
                outcome(won=True,turn=4),outcome(won=False),
            ),
        },
    ))
    chosen,meta=controller.choose(runtime,request,request.actions)
    assert chosen.kind=="main_use_simple_tutor",chosen
    assert meta[8]==8,meta
    assert (meta[9],meta[10])==(4,4),meta
    assert meta[13]=="paired_confidence_unresolved",meta
    print("mixed paired evidence expands 2 -> 4 -> 8 then falls back to v6: PASS")


def test_exact_confirm_tie_spends_no_validation_budget():
    runtime,request=runtime_and_request()
    controller=SelectiveTutorQController(
        continuation_policy=StubPolicy(),
        screen_rollouts=1,
        confirm_rollouts=2,
        confidence_gate=True,
        contingent=False,
    )
    controller.screen=FakeEvaluator({
        "main_use_simple_tutor":0.5,
        "main_end_turn":0.5,
    })
    controller.confirm=FakeEvaluator({
        "main_use_simple_tutor":0.5,
        "main_end_turn":0.5,
    })
    def fail_validation(**kwargs):
        raise AssertionError("validation must not run on an exact confirmation tie")
    controller._validation_evaluator=fail_validation
    chosen,meta=controller.choose(runtime,request,request.actions)
    assert chosen.kind=="main_use_simple_tutor",chosen
    assert meta[8]==0,meta
    assert meta[13]=="confirm_no_strict_improvement",meta
    print("confirmation tie preserves v6 without extra sampling: PASS")


def main():
    test_paired_evidence_counts_earlier_wins()
    test_strong_pair_accepts_after_first_validation_batch()
    test_strong_pair_rejects_bad_proposal_early()
    test_mixed_evidence_expands_budget_then_falls_back_to_v6()
    test_exact_confirm_tie_spends_no_validation_budget()
    print("PHASE5 ADAPTIVE CONFIDENCE Q SMOKE: ALL PASS")


if __name__=="__main__":
    main()
