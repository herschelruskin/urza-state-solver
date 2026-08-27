#!/usr/bin/env python3
"""Adaptive Monte-Carlo London mulligan evaluation with selective tutor-Q leaves.

The Phase-5 London recursion is retained exactly given the estimated keep values:

    V_6 = E[K_6(h)]
    V_s = E[max(K_s(h), V_{s+1})]

What changes is how the expensive keep value K_s(h) is estimated.  Every legal
bottom multiset is screened with common hidden worlds; only a bounded shortlist is
confirmed on a disjoint set of hidden worlds using a larger selective-tutor-Q
budget.  This is an explicitly approximate *racing* layer, not a claim that bottom
selection is exact under finite Monte Carlo. Exact-value ties at the screening
cutoff are never split by deterministic card-name ordering.

Human mulligan labels are not inputs to this module.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Sequence, Tuple

from non_oracle_base_policy import DeterministicBasePolicy
from phase3_value_engine import WinDistributionValue
from phase5_monte_carlo import Phase5DecisionCache
from phase5_mulligan import (
    MULLIGAN_FLOOR_STAGE,
    OpeningEnvironment,
    OpeningKeepEvaluation,
    OpeningPregameChoice,
    OpeningKeepEvaluator,
    _mix_values,
    _sample_fresh_seven,
    keep_size_for_stage,
    unique_bottom_subsets,
    value_at_least,
)
from phase5_rollout_policy_v6 import (
    DeterministicRolloutPolicyV6,
    PHASE5_ROLLOUT_POLICY_V6,
)
from phase5_selective_tutor_q import (
    PHASE5H_PRODUCTION_TUTOR_Q_CONFIG,
    make_phase5h_production_tutor_q_episode_runner,
)

PHASE5_ADAPTIVE_MULLIGAN_VERSION="urza-adaptive-mulligan-q-v2-phase5h-production"


@dataclass(frozen=True)
class AdaptiveOpeningKeepEvaluation:
    stage:int
    seven:Tuple[str,...]
    screen:OpeningKeepEvaluation|None
    confirmation:OpeningKeepEvaluation
    shortlisted_bottoms:Tuple[Tuple[str,...],...]
    legal_bottom_count:int
    screen_rollouts_per_bottom:int
    confirm_rollouts_per_bottom:int
    screen_sample_start:int
    confirm_sample_start:int

    @property
    def best(self):
        return self.confirmation.best

    @property
    def confirmed_bottom_count(self)->int:
        return len(self.shortlisted_bottoms)


@dataclass(frozen=True)
class AdaptiveHandDecision:
    stage:int
    sample_id:int
    seven:Tuple[str,...]
    decision:str
    best_bottom:Tuple[str,...]
    best_pregame_choice:OpeningPregameChoice
    keep_value_key:Tuple[float,...]
    continuation_value_key:Tuple[float,...]|None
    legal_bottom_count:int
    confirmed_bottom_count:int


@dataclass(frozen=True)
class AdaptiveMulliganStageEstimate:
    stage:int
    keep_size:int
    value:WinDistributionValue
    sampled_hands:int
    kept_count:int
    mulligan_count:int
    legal_bottoms_screened:int
    bottoms_confirmed:int
    evaluated_keep_terminal_reason_counts:Tuple[Tuple[str,int],...]

    @property
    def keep_rate(self)->float:
        return self.kept_count/self.sampled_hands if self.sampled_hands else 0.0


@dataclass(frozen=True)
class AdaptiveMulliganStageModel:
    stages:Tuple[AdaptiveMulliganStageEstimate,...]
    hand_decisions:Tuple[AdaptiveHandDecision,...]
    hand_samples_per_stage:int
    screen_rollouts_per_bottom:int
    confirm_rollouts_per_bottom:int
    shortlist_size:int
    mc_root_seed:int
    q_mc_root_seed:int
    horizon:int
    q_cache_hits:int
    q_cache_misses:int
    opening_environment:OpeningEnvironment=OpeningEnvironment()
    version:str=PHASE5_ADAPTIVE_MULLIGAN_VERSION

    def stage_estimate(self,stage:int)->AdaptiveMulliganStageEstimate:
        for row in self.stages:
            if row.stage==int(stage):
                return row
        raise KeyError(stage)


class AdaptiveOpeningKeepEvaluator:
    """Two-pass bottom racing with disjoint common-world sample windows."""

    def __init__(
        self,
        deck:Sequence[str],
        *,
        screen_rollouts:int=1,
        confirm_rollouts:int=4,
        shortlist_size:int=4,
        mc_root_seed:int=20260826,
        q_mc_root_seed:int|None=None,
        horizon:int=6,
        continuation_policy:DeterministicBasePolicy|None=None,
        max_episode_steps:int=512,
        strict_terminal_reasons:bool=True,
        decision_cache:Phase5DecisionCache|None=None,
        opening_environment:OpeningEnvironment|None=None,
    ):
        if screen_rollouts<1 or confirm_rollouts<1:
            raise ValueError("screen/confirm rollout counts must be >= 1")
        if shortlist_size<1:
            raise ValueError("shortlist_size must be >= 1")
        self.deck=tuple(str(card) for card in deck)
        self.screen_rollouts=int(screen_rollouts)
        self.confirm_rollouts=int(confirm_rollouts)
        self.shortlist_size=int(shortlist_size)
        self.mc_root_seed=int(mc_root_seed)
        self.q_mc_root_seed=int(
            q_mc_root_seed if q_mc_root_seed is not None
            else self.mc_root_seed + 1_000_003
        )
        self.horizon=int(horizon)
        self.policy=continuation_policy or DeterministicRolloutPolicyV6(
            policy_id=PHASE5_ROLLOUT_POLICY_V6
        )
        self.cache=decision_cache if decision_cache is not None else Phase5DecisionCache()
        self.opening_environment=opening_environment or OpeningEnvironment()

        # Outer bottom screening and confirmation may use different numbers of
        # hidden worlds, but they must value bottoms under the SAME gameplay
        # policy.  Phase 5H is frozen here so a cheap bottom screen cannot silently
        # use a weaker tutor policy and discard the bottom that production Q would
        # actually prefer.
        screen_runner=make_phase5h_production_tutor_q_episode_runner(
            mc_root_seed=self.q_mc_root_seed,
            decision_cache=self.cache,
        )
        confirm_runner=make_phase5h_production_tutor_q_episode_runner(
            mc_root_seed=self.q_mc_root_seed,
            decision_cache=self.cache,
        )
        assert screen_runner.q_policy_config==PHASE5H_PRODUCTION_TUTOR_Q_CONFIG
        assert confirm_runner.q_policy_config==PHASE5H_PRODUCTION_TUTOR_Q_CONFIG
        self.screen_evaluator=OpeningKeepEvaluator(
            self.deck,
            rollout_count=self.screen_rollouts,
            mc_root_seed=self.mc_root_seed,
            horizon=self.horizon,
            continuation_policy=self.policy,
            max_episode_steps=max_episode_steps,
            strict_terminal_reasons=strict_terminal_reasons,
            episode_runner=screen_runner,
            opening_environment=self.opening_environment,
        )
        self.confirm_evaluator=OpeningKeepEvaluator(
            self.deck,
            rollout_count=self.confirm_rollouts,
            mc_root_seed=self.mc_root_seed,
            horizon=self.horizon,
            continuation_policy=self.policy,
            max_episode_steps=max_episode_steps,
            strict_terminal_reasons=strict_terminal_reasons,
            episode_runner=confirm_runner,
            opening_environment=self.opening_environment,
        )

    def evaluate(self,seven:Sequence[str],*,stage:int)->AdaptiveOpeningKeepEvaluation:
        seven=tuple(str(card) for card in seven)
        legal=unique_bottom_subsets(seven,stage)

        # Stages 0/1 have no bottom choice. Do not waste a screening pass.
        if len(legal)==1:
            confirm=self.confirm_evaluator.evaluate(
                seven,
                stage=stage,
                candidate_bottoms=legal,
                sample_start=0,
            )
            return AdaptiveOpeningKeepEvaluation(
                stage=int(stage),
                seven=seven,
                screen=None,
                confirmation=confirm,
                shortlisted_bottoms=legal,
                legal_bottom_count=1,
                screen_rollouts_per_bottom=0,
                confirm_rollouts_per_bottom=self.confirm_rollouts,
                screen_sample_start=0,
                confirm_sample_start=0,
            )

        screen=self.screen_evaluator.evaluate(
            seven,
            stage=stage,
            sample_start=0,
        )
        cutoff_index=min(self.shortlist_size,len(screen.estimates))-1
        cutoff_key=screen.estimates[cutoff_index].value.comparison_key()
        # Never prune through an exact finite-sample value tie. With tiny screens,
        # especially all-zero weak hands, deterministic bottom-name ordering must
        # not masquerade as evidence that one tied bottom is better than another.
        shortlist=tuple(
            estimate.bottom
            for estimate in screen.estimates
            if estimate.value.comparison_key()>=cutoff_key
        )
        confirm=self.confirm_evaluator.evaluate(
            seven,
            stage=stage,
            candidate_bottoms=shortlist,
            sample_start=self.screen_rollouts,
        )
        return AdaptiveOpeningKeepEvaluation(
            stage=int(stage),
            seven=seven,
            screen=screen,
            confirmation=confirm,
            shortlisted_bottoms=tuple(sorted(shortlist)),
            legal_bottom_count=len(legal),
            screen_rollouts_per_bottom=self.screen_rollouts,
            confirm_rollouts_per_bottom=self.confirm_rollouts,
            screen_sample_start=0,
            confirm_sample_start=self.screen_rollouts,
        )


class AdaptiveMulliganStageTrainer:
    """Backward London DP using adaptive keep-value estimates."""

    def __init__(
        self,
        deck:Sequence[str],
        *,
        hand_samples_per_stage:int=4,
        earliest_stage:int=0,
        screen_rollouts_per_bottom:int=1,
        confirm_rollouts_per_bottom:int=3,
        shortlist_size:int=4,
        mc_root_seed:int=20260826,
        q_mc_root_seed:int|None=None,
        horizon:int=6,
        continuation_policy:DeterministicBasePolicy|None=None,
        max_episode_steps:int=512,
        strict_terminal_reasons:bool=True,
        opening_environment:OpeningEnvironment|None=None,
    ):
        if hand_samples_per_stage<1:
            raise ValueError("hand_samples_per_stage must be >= 1")
        if earliest_stage<0 or earliest_stage>MULLIGAN_FLOOR_STAGE:
            raise ValueError("earliest_stage must be between 0 and the mulligan floor")
        self.deck=tuple(str(card) for card in deck)
        self.hand_samples_per_stage=int(hand_samples_per_stage)
        self.earliest_stage=int(earliest_stage)
        self.screen_rollouts_per_bottom=int(screen_rollouts_per_bottom)
        self.confirm_rollouts_per_bottom=int(confirm_rollouts_per_bottom)
        self.shortlist_size=int(shortlist_size)
        self.mc_root_seed=int(mc_root_seed)
        self.q_mc_root_seed=int(
            q_mc_root_seed if q_mc_root_seed is not None
            else self.mc_root_seed + 1_000_003
        )
        self.horizon=int(horizon)
        self.policy=continuation_policy or DeterministicRolloutPolicyV6(
            policy_id=PHASE5_ROLLOUT_POLICY_V6
        )
        self.cache=Phase5DecisionCache()
        self.opening_environment=opening_environment or OpeningEnvironment()
        self.evaluator=AdaptiveOpeningKeepEvaluator(
            self.deck,
            screen_rollouts=self.screen_rollouts_per_bottom,
            confirm_rollouts=self.confirm_rollouts_per_bottom,
            shortlist_size=self.shortlist_size,
            mc_root_seed=self.mc_root_seed,
            q_mc_root_seed=self.q_mc_root_seed,
            horizon=self.horizon,
            continuation_policy=self.policy,
            max_episode_steps=max_episode_steps,
            strict_terminal_reasons=strict_terminal_reasons,
            decision_cache=self.cache,
            opening_environment=self.opening_environment,
        )

    def train(self)->AdaptiveMulliganStageModel:
        fitted={}
        decisions=[]
        for stage in range(MULLIGAN_FLOOR_STAGE,self.earliest_stage-1,-1):
            chosen_values=[]
            kept=mulled=0
            screened=confirmed=0
            reason_counts=Counter()
            continuation=fitted.get(stage+1)

            for sample_id in range(self.hand_samples_per_stage):
                seven=_sample_fresh_seven(
                    self.deck,
                    root_seed=self.mc_root_seed,
                    stage=stage,
                    sample_id=sample_id,
                )
                evaluation=self.evaluator.evaluate(seven,stage=stage)
                keep=evaluation.best.value
                screened += evaluation.legal_bottom_count
                confirmed += evaluation.confirmed_bottom_count
                reason_counts.update(dict(evaluation.best.terminal_reason_counts))

                continuation_value=(
                    None if continuation is None else continuation.value
                )
                if (
                    continuation_value is None
                    or value_at_least(keep,continuation_value)
                ):
                    choice=keep
                    decision="Keep"
                    kept += 1
                else:
                    choice=continuation_value
                    decision="Mulligan"
                    mulled += 1
                chosen_values.append(choice)
                decisions.append(AdaptiveHandDecision(
                    stage=stage,
                    sample_id=sample_id,
                    seven=seven,
                    decision=decision,
                    best_bottom=evaluation.best.bottom,
                    best_pregame_choice=evaluation.best.pregame_choice,
                    keep_value_key=keep.comparison_key(),
                    continuation_value_key=(
                        None if continuation_value is None
                        else continuation_value.comparison_key()
                    ),
                    legal_bottom_count=evaluation.legal_bottom_count,
                    confirmed_bottom_count=evaluation.confirmed_bottom_count,
                ))

            fitted[stage]=AdaptiveMulliganStageEstimate(
                stage=stage,
                keep_size=keep_size_for_stage(stage),
                value=_mix_values(chosen_values),
                sampled_hands=self.hand_samples_per_stage,
                kept_count=kept,
                mulligan_count=mulled,
                legal_bottoms_screened=screened,
                bottoms_confirmed=confirmed,
                evaluated_keep_terminal_reason_counts=tuple(sorted(reason_counts.items())),
            )

        return AdaptiveMulliganStageModel(
            stages=tuple(
                fitted[stage]
                for stage in range(self.earliest_stage,MULLIGAN_FLOOR_STAGE+1)
            ),
            hand_decisions=tuple(decisions),
            hand_samples_per_stage=self.hand_samples_per_stage,
            screen_rollouts_per_bottom=self.screen_rollouts_per_bottom,
            confirm_rollouts_per_bottom=self.confirm_rollouts_per_bottom,
            shortlist_size=self.shortlist_size,
            mc_root_seed=self.mc_root_seed,
            q_mc_root_seed=self.q_mc_root_seed,
            horizon=self.horizon,
            q_cache_hits=self.cache.stats.hits,
            q_cache_misses=self.cache.stats.misses,
            opening_environment=self.opening_environment,
        )
