#!/usr/bin/env python3
"""Phase 5I London-mulligan valuation under the frozen Phase-5H player.

This module intentionally leaves phase5_adaptive_mulligan.py unchanged as an
experimental historical implementation.  Phase 5I defines the production path:

- every opening trajectory is played by PHASE5H_PRODUCTION_Q;
- bottom screening and confirmation use disjoint outer hidden-world windows;
- exact finite-sample ties at the screen cutoff are preserved;
- the same shared Q cache is reused across equivalent opening evaluations;
- human labels are never inputs to value estimation.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Sequence, Tuple

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
from phase5_production_policy import (
    FrozenTutorQConfig,
    PHASE5H_PRODUCTION_POLICY_VERSION,
    PHASE5H_PRODUCTION_Q,
    make_phase5h_production_decision_cache,
    make_phase5h_production_episode_runner,
)
from phase5_rollout_policy_v6 import (
    DeterministicRolloutPolicyV6,
    PHASE5_ROLLOUT_POLICY_V6,
)


PHASE5I_MULLIGAN_VERSION = "urza-phase5i-mulligan-frozen-q-v1"


@dataclass(frozen=True)
class Phase5IOpeningKeepEvaluation:
    stage: int
    seven: Tuple[str, ...]
    screen: OpeningKeepEvaluation | None
    confirmation: OpeningKeepEvaluation
    shortlisted_bottoms: Tuple[Tuple[str, ...], ...]
    legal_bottom_count: int
    screen_rollouts_per_bottom: int
    confirm_rollouts_per_bottom: int
    production_policy_version: str = PHASE5H_PRODUCTION_POLICY_VERSION

    @property
    def best(self):
        return self.confirmation.best

    @property
    def confirmed_bottom_count(self) -> int:
        return len(self.shortlisted_bottoms)


class Phase5IOpeningKeepEvaluator:
    """Two-pass bottom racing with the exact same frozen gameplay policy."""

    def __init__(
        self,
        deck: Sequence[str],
        *,
        screen_rollouts: int = 1,
        confirm_rollouts: int = 3,
        shortlist_size: int = 4,
        mc_root_seed: int = 20260826,
        q_mc_root_seed: int | None = None,
        horizon: int = 6,
        max_episode_steps: int = 512,
        strict_terminal_reasons: bool = True,
        decision_cache: Phase5DecisionCache | None = None,
        opening_environment: OpeningEnvironment | None = None,
        q_config: FrozenTutorQConfig = PHASE5H_PRODUCTION_Q,
    ) -> None:
        if int(screen_rollouts) < 1 or int(confirm_rollouts) < 1:
            raise ValueError("screen/confirm rollout counts must be >= 1")
        if int(shortlist_size) < 1:
            raise ValueError("shortlist_size must be >= 1")
        self.deck = tuple(str(card) for card in deck)
        self.screen_rollouts = int(screen_rollouts)
        self.confirm_rollouts = int(confirm_rollouts)
        self.shortlist_size = int(shortlist_size)
        self.mc_root_seed = int(mc_root_seed)
        self.q_mc_root_seed = int(
            q_mc_root_seed
            if q_mc_root_seed is not None
            else self.mc_root_seed + 1_000_003
        )
        self.horizon = int(horizon)
        self.q_config = q_config
        self.cache = (
            decision_cache
            if decision_cache is not None
            else make_phase5h_production_decision_cache()
        )
        self.opening_environment = opening_environment or OpeningEnvironment()
        self.policy = DeterministicRolloutPolicyV6(policy_id=PHASE5_ROLLOUT_POLICY_V6)

        # Both passes estimate the same production policy.  Only their OUTER
        # hidden-world budgets differ.  This avoids screening bottoms with a
        # weaker player than the one used for confirmation.
        screen_runner = make_phase5h_production_episode_runner(
            mc_root_seed=self.q_mc_root_seed,
            decision_cache=self.cache,
            config=self.q_config,
        )
        confirm_runner = make_phase5h_production_episode_runner(
            mc_root_seed=self.q_mc_root_seed,
            decision_cache=self.cache,
            config=self.q_config,
        )
        self.screen_evaluator = OpeningKeepEvaluator(
            self.deck,
            rollout_count=self.screen_rollouts,
            mc_root_seed=self.mc_root_seed,
            horizon=self.horizon,
            continuation_policy=self.policy,
            max_episode_steps=int(max_episode_steps),
            strict_terminal_reasons=bool(strict_terminal_reasons),
            episode_runner=screen_runner,
            opening_environment=self.opening_environment,
        )
        self.confirm_evaluator = OpeningKeepEvaluator(
            self.deck,
            rollout_count=self.confirm_rollouts,
            mc_root_seed=self.mc_root_seed,
            horizon=self.horizon,
            continuation_policy=self.policy,
            max_episode_steps=int(max_episode_steps),
            strict_terminal_reasons=bool(strict_terminal_reasons),
            episode_runner=confirm_runner,
            opening_environment=self.opening_environment,
        )

    def evaluate(self, seven: Sequence[str], *, stage: int) -> Phase5IOpeningKeepEvaluation:
        seven = tuple(str(card) for card in seven)
        legal = unique_bottom_subsets(seven, stage)

        # Stages 0/1 have no bottom decision, so no racing pass is useful.
        if len(legal) == 1:
            confirm = self.confirm_evaluator.evaluate(
                seven,
                stage=stage,
                candidate_bottoms=legal,
                sample_start=0,
            )
            return Phase5IOpeningKeepEvaluation(
                stage=int(stage),
                seven=seven,
                screen=None,
                confirmation=confirm,
                shortlisted_bottoms=legal,
                legal_bottom_count=1,
                screen_rollouts_per_bottom=0,
                confirm_rollouts_per_bottom=self.confirm_rollouts,
            )

        screen = self.screen_evaluator.evaluate(
            seven,
            stage=stage,
            sample_start=0,
        )
        cutoff_index = min(self.shortlist_size, len(screen.estimates)) - 1
        cutoff_key = screen.estimates[cutoff_index].value.comparison_key()
        shortlist = tuple(
            estimate.bottom
            for estimate in screen.estimates
            if estimate.value.comparison_key() >= cutoff_key
        )
        confirm = self.confirm_evaluator.evaluate(
            seven,
            stage=stage,
            candidate_bottoms=shortlist,
            sample_start=self.screen_rollouts,
        )
        return Phase5IOpeningKeepEvaluation(
            stage=int(stage),
            seven=seven,
            screen=screen,
            confirmation=confirm,
            shortlisted_bottoms=tuple(sorted(shortlist)),
            legal_bottom_count=len(legal),
            screen_rollouts_per_bottom=self.screen_rollouts,
            confirm_rollouts_per_bottom=self.confirm_rollouts,
        )


@dataclass(frozen=True)
class Phase5IHandDecision:
    stage: int
    sample_id: int
    seven: Tuple[str, ...]
    decision: str
    best_bottom: Tuple[str, ...]
    best_pregame_choice: OpeningPregameChoice
    keep_value_key: Tuple[float, ...]
    continuation_value_key: Tuple[float, ...] | None


@dataclass(frozen=True)
class Phase5IStageEstimate:
    stage: int
    keep_size: int
    value: WinDistributionValue
    sampled_hands: int
    kept_count: int
    mulligan_count: int
    legal_bottoms_screened: int
    bottoms_confirmed: int
    terminal_reason_counts: Tuple[Tuple[str, int], ...]

    @property
    def keep_rate(self) -> float:
        return self.kept_count / self.sampled_hands if self.sampled_hands else 0.0


@dataclass(frozen=True)
class Phase5IStageModel:
    stages: Tuple[Phase5IStageEstimate, ...]
    hand_decisions: Tuple[Phase5IHandDecision, ...]
    hand_samples_per_stage: int
    screen_rollouts_per_bottom: int
    confirm_rollouts_per_bottom: int
    shortlist_size: int
    mc_root_seed: int
    q_mc_root_seed: int
    horizon: int
    q_cache_hits: int
    q_cache_misses: int
    opening_environment: OpeningEnvironment
    production_policy_version: str = PHASE5H_PRODUCTION_POLICY_VERSION
    version: str = PHASE5I_MULLIGAN_VERSION

    def stage_estimate(self, stage: int) -> Phase5IStageEstimate:
        for estimate in self.stages:
            if estimate.stage == int(stage):
                return estimate
        raise KeyError(stage)

    def continuation_value(self, current_stage: int):
        next_stage = int(current_stage) + 1
        if next_stage > MULLIGAN_FLOOR_STAGE:
            return None
        return self.stage_estimate(next_stage).value


class Phase5IStageTrainer:
    """Backward London DP whose K_s(h) uses the frozen Phase-5H player."""

    def __init__(
        self,
        deck: Sequence[str],
        *,
        hand_samples_per_stage: int = 4,
        earliest_stage: int = 0,
        screen_rollouts_per_bottom: int = 1,
        confirm_rollouts_per_bottom: int = 3,
        shortlist_size: int = 4,
        mc_root_seed: int = 20260826,
        q_mc_root_seed: int | None = None,
        horizon: int = 6,
        max_episode_steps: int = 512,
        strict_terminal_reasons: bool = True,
        opening_environment: OpeningEnvironment | None = None,
        q_config: FrozenTutorQConfig = PHASE5H_PRODUCTION_Q,
    ) -> None:
        if int(hand_samples_per_stage) < 1:
            raise ValueError("hand_samples_per_stage must be >= 1")
        if int(earliest_stage) < 0 or int(earliest_stage) > MULLIGAN_FLOOR_STAGE:
            raise ValueError("earliest_stage outside London model")
        self.deck = tuple(str(card) for card in deck)
        self.hand_samples_per_stage = int(hand_samples_per_stage)
        self.earliest_stage = int(earliest_stage)
        self.screen_rollouts_per_bottom = int(screen_rollouts_per_bottom)
        self.confirm_rollouts_per_bottom = int(confirm_rollouts_per_bottom)
        self.shortlist_size = int(shortlist_size)
        self.mc_root_seed = int(mc_root_seed)
        self.q_mc_root_seed = int(
            q_mc_root_seed
            if q_mc_root_seed is not None
            else self.mc_root_seed + 1_000_003
        )
        self.horizon = int(horizon)
        self.cache = Phase5DecisionCache()
        self.opening_environment = opening_environment or OpeningEnvironment()
        self.evaluator = Phase5IOpeningKeepEvaluator(
            self.deck,
            screen_rollouts=self.screen_rollouts_per_bottom,
            confirm_rollouts=self.confirm_rollouts_per_bottom,
            shortlist_size=self.shortlist_size,
            mc_root_seed=self.mc_root_seed,
            q_mc_root_seed=self.q_mc_root_seed,
            horizon=self.horizon,
            max_episode_steps=int(max_episode_steps),
            strict_terminal_reasons=bool(strict_terminal_reasons),
            decision_cache=self.cache,
            opening_environment=self.opening_environment,
            q_config=q_config,
        )

    def train(self) -> Phase5IStageModel:
        fitted = {}
        decisions = []
        for stage in range(MULLIGAN_FLOOR_STAGE, self.earliest_stage - 1, -1):
            chosen_values = []
            kept = mulled = 0
            screened = confirmed = 0
            reasons = Counter()
            continuation = fitted.get(stage + 1)

            for sample_id in range(self.hand_samples_per_stage):
                seven = _sample_fresh_seven(
                    self.deck,
                    root_seed=self.mc_root_seed,
                    stage=stage,
                    sample_id=sample_id,
                )
                evaluation = self.evaluator.evaluate(seven, stage=stage)
                keep = evaluation.best.value
                screened += evaluation.legal_bottom_count
                confirmed += evaluation.confirmed_bottom_count
                reasons.update(dict(evaluation.best.terminal_reason_counts))
                continuation_value = None if continuation is None else continuation.value
                if continuation_value is None or value_at_least(keep, continuation_value):
                    selected = keep
                    decision = "Keep"
                    kept += 1
                else:
                    selected = continuation_value
                    decision = "Mulligan"
                    mulled += 1
                chosen_values.append(selected)
                decisions.append(Phase5IHandDecision(
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
                ))

            fitted[stage] = Phase5IStageEstimate(
                stage=stage,
                keep_size=keep_size_for_stage(stage),
                value=_mix_values(chosen_values),
                sampled_hands=self.hand_samples_per_stage,
                kept_count=kept,
                mulligan_count=mulled,
                legal_bottoms_screened=screened,
                bottoms_confirmed=confirmed,
                terminal_reason_counts=tuple(sorted(reasons.items())),
            )

        return Phase5IStageModel(
            stages=tuple(
                fitted[stage]
                for stage in range(self.earliest_stage, MULLIGAN_FLOOR_STAGE + 1)
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
