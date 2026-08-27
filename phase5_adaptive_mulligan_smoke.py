#!/usr/bin/env python3
"""Structural regression gates for adaptive Phase-5 mulligan Q."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace

from phase3_value_engine import WinDistributionValue
from phase5_adaptive_mulligan import (
    AdaptiveMulliganStageTrainer,
    AdaptiveOpeningKeepEvaluation,
    AdaptiveOpeningKeepEvaluator,
)
from phase5_selective_tutor_q import PHASE5H_PRODUCTION_TUTOR_Q_CONFIG
from phase5_mulligan import (
    OpeningKeepEstimate,
    OpeningKeepEvaluation,
    _opening_world,
    keep_size_for_stage,
    unique_bottom_subsets,
)


def value(pwin: float, *, horizon: int = 6) -> WinDistributionValue:
    return WinDistributionValue(
        horizon=horizon,
        exact_win=(0.0, 0.0, 0.0, 0.0, 0.0, float(pwin)),
        no_win=1.0-float(pwin),
    )


def estimate(bottom, pwin):
    return OpeningKeepEstimate(
        stage=2,
        keep_size=6,
        bottom=tuple(bottom),
        kept_hand=(),
        value=value(pwin),
        rollouts=1,
        win_probability_wilson95=(0.0, 1.0),
        terminal_reason_counts=(("horizon", 1),),
    )


class FakeOpeningEvaluator:
    def __init__(self, screen_rows=None):
        self.screen_rows=tuple(screen_rows or ())
        self.calls=[]

    def evaluate(self, seven, *, stage, candidate_bottoms=None, sample_start=0):
        self.calls.append((tuple(seven), int(stage), candidate_bottoms, int(sample_start)))
        if candidate_bottoms is None:
            rows=self.screen_rows
        else:
            wanted={tuple(x) for x in candidate_bottoms}
            by_bottom={row.bottom:row for row in self.screen_rows}
            rows=tuple(
                replace(by_bottom[b], rollouts=2)
                for b in sorted(wanted)
            )
        ranked=tuple(sorted(
            rows,
            key=lambda row:(row.value.comparison_key(),repr(row.bottom)),
            reverse=True,
        ))
        return OpeningKeepEvaluation(
            stage=int(stage),
            seven=tuple(seven),
            best=ranked[0],
            estimates=ranked,
            rollout_count_per_bottom=1,
            mc_root_seed=123,
            horizon=6,
        )


def test_opening_world_common_random_numbers_and_seed_namespace():
    deck=tuple(f"C{i}" for i in range(1,100))
    seven=deck[:7]
    a=_opening_world(
        deck=deck,seven=seven,bottom=(seven[0],),
        mc_root_seed=77,sample_id=3,
    )
    b=_opening_world(
        deck=deck,seven=seven,bottom=(seven[1],),
        mc_root_seed=77,sample_id=3,
    )
    assert a.rng_root_seed==b.rng_root_seed
    assert a.library[:-1]==b.library[:-1]
    assert a.library[-1]!=b.library[-1]

    seven2=deck[1:8]
    c=_opening_world(
        deck=deck,seven=seven2,bottom=(seven2[0],),
        mc_root_seed=77,sample_id=3,
    )
    assert c.rng_root_seed!=a.rng_root_seed
    print("opening CRN: same seven/bottom alternatives share RNG; different sevens do not: PASS")


def test_bottom_multiset_count_and_keep2_floor():
    seven=tuple(f"C{i}" for i in range(7))
    assert keep_size_for_stage(6)==2
    assert len(unique_bottom_subsets(seven,6))==21
    duplicate=("A","A","B","C","D","E","F")
    # Card-multiset collapsing is intentional; duplicate physical copies are not
    # distinct bottom actions when card identity is identical.
    assert len(unique_bottom_subsets(duplicate,2))==6
    print("London keep-2 floor and card-multiset bottom collapsing: PASS")


def test_screening_never_splits_exact_value_tie():
    seven=("A","B","C","D","E","F","G")
    legal=unique_bottom_subsets(seven,2)
    # Four candidates tie at the top. shortlist_size=2 must retain all four.
    rows=tuple(
        estimate(bottom, 1.0 if i<4 else 0.0)
        for i,bottom in enumerate(legal)
    )
    fake=FakeOpeningEvaluator(rows)
    obj=object.__new__(AdaptiveOpeningKeepEvaluator)
    obj.shortlist_size=2
    obj.screen_rollouts=1
    obj.confirm_rollouts=2
    obj.screen_evaluator=fake
    obj.confirm_evaluator=fake

    result=obj.evaluate(seven,stage=2)
    assert result.legal_bottom_count==7
    assert result.confirmed_bottom_count==4
    confirm_call=fake.calls[-1]
    assert confirm_call[3]==1  # fresh confirmation window
    assert len(confirm_call[2])==4
    print("adaptive racer preserves all exact ties at shortlist cutoff: PASS")


class FakeAdaptiveEvaluator:
    def __init__(self):
        self.calls=0

    def evaluate(self, seven, *, stage):
        self.calls+=1
        row=OpeningKeepEstimate(
            stage=stage,
            keep_size=keep_size_for_stage(stage),
            bottom=("dummy",),
            kept_hand=tuple(seven[:keep_size_for_stage(stage)]),
            value=value(0.25),
            rollouts=2,
            win_probability_wilson95=(0.0,1.0),
            terminal_reason_counts=(("horizon",1),("step_limit",1)),
        )
        opening=OpeningKeepEvaluation(
            stage=stage,
            seven=tuple(seven),
            best=row,
            estimates=(row,),
            rollout_count_per_bottom=2,
            mc_root_seed=1,
            horizon=6,
        )
        return AdaptiveOpeningKeepEvaluation(
            stage=stage,
            seven=tuple(seven),
            screen=None,
            confirmation=opening,
            shortlisted_bottoms=(("dummy",),),
            legal_bottom_count=21,
            screen_rollouts_per_bottom=1,
            confirm_rollouts_per_bottom=2,
            screen_sample_start=0,
            confirm_sample_start=1,
        )


def test_bottom_racer_uses_identical_frozen_phase5h_gameplay_policy():
    deck=tuple(f"C{i}" for i in range(99))
    evaluator=AdaptiveOpeningKeepEvaluator(
        deck,
        screen_rollouts=1,
        confirm_rollouts=2,
        shortlist_size=2,
        mc_root_seed=77,
        horizon=6,
    )
    screen_config=evaluator.screen_evaluator.episode_runner.q_policy_config
    confirm_config=evaluator.confirm_evaluator.episode_runner.q_policy_config
    assert screen_config==PHASE5H_PRODUCTION_TUTOR_Q_CONFIG
    assert confirm_config==PHASE5H_PRODUCTION_TUTOR_Q_CONFIG
    assert screen_config==confirm_config
    assert screen_config.mc_root_seed==2026082802
    assert evaluator.q_mc_root_seed==screen_config.mc_root_seed
    assert screen_config.confidence_gate
    assert screen_config.contingent
    assert screen_config.screen_rollouts==1
    assert screen_config.confirm_rollouts==2
    assert screen_config.validation_rollouts==2
    assert screen_config.max_validation_rollouts==8
    print("bottom screen/confirm share the frozen Phase 5H gameplay policy: PASS")


def test_forced_keep2_stage_is_terminal_mulligan_floor():
    deck=tuple(f"C{i}" for i in range(99))
    trainer=AdaptiveMulliganStageTrainer(
        deck,
        hand_samples_per_stage=2,
        earliest_stage=6,
        screen_rollouts_per_bottom=1,
        confirm_rollouts_per_bottom=1,
        shortlist_size=2,
        horizon=6,
    )
    trainer.evaluator=FakeAdaptiveEvaluator()
    model=trainer.train()
    assert len(model.stages)==1
    stage=model.stage_estimate(6)
    assert stage.keep_size==2
    assert stage.kept_count==2
    assert stage.mulligan_count==0
    assert all(row.decision=="Keep" for row in model.hand_decisions)
    assert dict(stage.evaluated_keep_terminal_reason_counts)=={"horizon":2,"step_limit":2}
    print("stage 6 is forced keep-2 and records leaf terminal reasons: PASS")


def main():
    test_opening_world_common_random_numbers_and_seed_namespace()
    test_bottom_multiset_count_and_keep2_floor()
    test_screening_never_splits_exact_value_tie()
    test_bottom_racer_uses_identical_frozen_phase5h_gameplay_policy()
    test_forced_keep2_stage_is_terminal_mulligan_floor()
    print("PHASE5 ADAPTIVE MULLIGAN SMOKE: ALL PASS")


if __name__=="__main__":
    main()
