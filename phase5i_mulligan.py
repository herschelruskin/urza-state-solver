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
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from typing import Sequence, Tuple

from phase3_value_engine import WinDistributionValue
from phase4_monte_carlo import _wilson_interval
from phase5_monte_carlo import Phase5DecisionCache
from phase5_mulligan import (
    MULLIGAN_FLOOR_STAGE,
    OpeningEnvironment,
    OpeningKeepEvaluation,
    OpeningKeepEstimate,
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


PHASE5I_MULLIGAN_VERSION = "urza-phase5i-mulligan-frozen-q-v2-parallel-racing"


@dataclass(frozen=True)
class _BottomTaskResult:
    estimate: OpeningKeepEstimate
    completed: bool
    samples_requested: int
    samples_evaluated: int
    q_hits: int
    q_misses: int
    q_evictions: int


def _merge_keep_estimates(rows: Sequence[OpeningKeepEstimate]) -> OpeningKeepEstimate:
    rows = tuple(rows)
    if not rows:
        raise ValueError("cannot merge zero opening estimates")
    first = rows[0]
    if any(row.bottom != first.bottom for row in rows):
        raise ValueError("cannot merge estimates for different bottoms")
    if any(row.pregame_choice != first.pregame_choice for row in rows):
        raise ValueError("cannot merge estimates with different pregame choices")
    total = sum(int(row.rollouts) for row in rows)
    value = WinDistributionValue.mixture(
        tuple((float(row.rollouts) / total, row.value) for row in rows),
        horizon=first.value.horizon,
    )
    reasons = Counter()
    for row in rows:
        reasons.update(dict(row.terminal_reason_counts))
    wins = int(round(value.win_probability * total))
    return OpeningKeepEstimate(
        stage=int(first.stage),
        keep_size=int(first.keep_size),
        bottom=tuple(first.bottom),
        kept_hand=tuple(first.kept_hand),
        value=value,
        rollouts=total,
        win_probability_wilson95=_wilson_interval(wins, total),
        terminal_reason_counts=tuple(sorted(reasons.items())),
        pregame_choice=first.pregame_choice,
    )


def _optimistic_completion_key(
    estimate: OpeningKeepEstimate,
    *,
    total_rollouts: int,
) -> Tuple[float, ...]:
    """Best lexicographic value still reachable if every unseen world wins T1."""

    observed = int(estimate.rollouts)
    total = int(total_rollouts)
    if observed < 1 or observed > total:
        raise ValueError("invalid partial confirmation rollout count")
    remaining = total - observed
    key = estimate.value.comparison_key()
    return tuple(
        round((float(coord) * observed + remaining) / total, 15)
        for coord in key
    )


def _rank_keep_estimates(
    estimates: Sequence[OpeningKeepEstimate],
) -> Tuple[OpeningKeepEstimate, ...]:
    return tuple(sorted(
        estimates,
        key=lambda estimate: (estimate.value.comparison_key(), repr(estimate.bottom)),
        reverse=True,
    ))


def _opening_evaluation_from_estimates(
    *,
    stage: int,
    seven: Tuple[str, ...],
    estimates: Sequence[OpeningKeepEstimate],
    rollout_count_per_bottom: int,
    mc_root_seed: int,
    horizon: int,
    opening_environment: OpeningEnvironment,
) -> OpeningKeepEvaluation:
    ranked = _rank_keep_estimates(tuple(estimates))
    if not ranked:
        raise ValueError("opening evaluation requires at least one complete estimate")
    return OpeningKeepEvaluation(
        stage=int(stage),
        seven=tuple(seven),
        best=ranked[0],
        estimates=ranked,
        rollout_count_per_bottom=int(rollout_count_per_bottom),
        mc_root_seed=int(mc_root_seed),
        horizon=int(horizon),
        opening_environment=opening_environment,
        pregame_variants_evaluated=len(ranked),
    )


def _phase5i_bottom_task(payload) -> _BottomTaskResult:
    """Evaluate one exact bottom over a contiguous outer-world window.

    The worker keeps one bounded Phase-5H Q cache for the whole bottom, preserving
    cache locality across that bottom's worlds while allowing independent bottoms
    to run in separate processes.  This path is used only when the opening has one
    pregame variant per bottom (currently every hand except live Gemstone Caverns).
    """

    deck = tuple(payload["deck"])
    seven = tuple(payload["seven"])
    bottom = tuple(payload["bottom"])
    stage = int(payload["stage"])
    sample_start = int(payload["sample_start"])
    sample_count = int(payload["sample_count"])
    incumbent_key = payload.get("incumbent_key")
    cache = make_phase5h_production_decision_cache()
    runner = make_phase5h_production_episode_runner(
        mc_root_seed=int(payload["q_mc_root_seed"]),
        decision_cache=cache,
        config=payload["q_config"],
    )
    evaluator = OpeningKeepEvaluator(
        deck,
        rollout_count=1,
        mc_root_seed=int(payload["mc_root_seed"]),
        horizon=int(payload["horizon"]),
        continuation_policy=DeterministicRolloutPolicyV6(
            policy_id=PHASE5_ROLLOUT_POLICY_V6
        ),
        max_episode_steps=int(payload["max_episode_steps"]),
        strict_terminal_reasons=bool(payload["strict_terminal_reasons"]),
        episode_runner=runner,
        opening_environment=payload["opening_environment"],
    )
    rows = []
    for sample_id in range(sample_start, sample_start + sample_count):
        one = evaluator.evaluate(
            seven,
            stage=stage,
            candidate_bottoms=(bottom,),
            sample_start=sample_id,
        )
        rows.append(one.best)
        merged = _merge_keep_estimates(rows)
        if incumbent_key is not None and len(rows) < sample_count:
            if _optimistic_completion_key(
                merged, total_rollouts=sample_count
            ) < tuple(incumbent_key):
                break

    merged = _merge_keep_estimates(rows)
    return _BottomTaskResult(
        estimate=merged,
        completed=len(rows) == sample_count,
        samples_requested=sample_count,
        samples_evaluated=len(rows),
        q_hits=int(cache.stats.hits),
        q_misses=int(cache.stats.misses),
        q_evictions=int(cache.stats.evictions),
    )


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
    screen_tie_break_rollouts: int = 0
    confirmation_early_eliminated_bottoms: Tuple[Tuple[str, ...], ...] = ()
    parallel_workers: int = 1
    confirmation_start_sample: int = 0
    production_policy_version: str = PHASE5H_PRODUCTION_POLICY_VERSION

    @property
    def best(self):
        return self.confirmation.best

    @property
    def confirmed_bottom_count(self) -> int:
        return len(self.shortlisted_bottoms)

    @property
    def fully_confirmed_bottom_count(self) -> int:
        return len(self.confirmation.estimates)


class Phase5IOpeningKeepEvaluator:
    """Adaptive exact-safe bottom racing under the frozen Phase-5H player.

    Gameplay policy is unchanged.  Runtime reductions happen only outside the
    game tree:
      * independent bottom candidates may run in separate processes;
      * exact screen-cutoff ties receive paired extra outer worlds only as needed;
      * after one confirmation incumbent is fully known, another bottom stops only
        when an all-T1-win optimistic completion cannot catch that incumbent.

    Live Gemstone Caverns hands retain the legacy evaluator because they have
    multiple pregame choices per bottom; this keeps pregame optimization exact.
    """

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
        parallel_workers: int = 1,
        max_screen_tie_break_rollouts: int = 2,
    ) -> None:
        if int(screen_rollouts) < 1 or int(confirm_rollouts) < 1:
            raise ValueError("screen/confirm rollout counts must be >= 1")
        if int(shortlist_size) < 1:
            raise ValueError("shortlist_size must be >= 1")
        if int(parallel_workers) < 1:
            raise ValueError("parallel_workers must be >= 1")
        if int(max_screen_tie_break_rollouts) < 0:
            raise ValueError("max_screen_tie_break_rollouts must be >= 0")
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
        self.parallel_workers = int(parallel_workers)
        self.max_screen_tie_break_rollouts = int(max_screen_tie_break_rollouts)
        self.max_episode_steps = int(max_episode_steps)
        self.strict_terminal_reasons = bool(strict_terminal_reasons)
        self.cache = (
            decision_cache
            if decision_cache is not None
            else make_phase5h_production_decision_cache()
        )
        self.opening_environment = opening_environment or OpeningEnvironment()
        self.policy = DeterministicRolloutPolicyV6(policy_id=PHASE5_ROLLOUT_POLICY_V6)

        # Legacy exact path remains available for single-bottom states and live
        # Gemstone Caverns, where multiple pregame choices must be optimized over
        # the complete outer-world window rather than independently per world.
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
            max_episode_steps=self.max_episode_steps,
            strict_terminal_reasons=self.strict_terminal_reasons,
            episode_runner=screen_runner,
            opening_environment=self.opening_environment,
        )
        self.confirm_evaluator = OpeningKeepEvaluator(
            self.deck,
            rollout_count=self.confirm_rollouts,
            mc_root_seed=self.mc_root_seed,
            horizon=self.horizon,
            continuation_policy=self.policy,
            max_episode_steps=self.max_episode_steps,
            strict_terminal_reasons=self.strict_terminal_reasons,
            episode_runner=confirm_runner,
            opening_environment=self.opening_environment,
        )

    def _task_payload(
        self,
        seven: Tuple[str, ...],
        *,
        stage: int,
        bottom: Tuple[str, ...],
        sample_start: int,
        sample_count: int,
        incumbent_key=None,
    ):
        return {
            "deck": self.deck,
            "seven": seven,
            "stage": int(stage),
            "bottom": tuple(bottom),
            "sample_start": int(sample_start),
            "sample_count": int(sample_count),
            "mc_root_seed": self.mc_root_seed,
            "q_mc_root_seed": self.q_mc_root_seed,
            "horizon": self.horizon,
            "max_episode_steps": self.max_episode_steps,
            "strict_terminal_reasons": self.strict_terminal_reasons,
            "opening_environment": self.opening_environment,
            "q_config": self.q_config,
            "incumbent_key": None if incumbent_key is None else tuple(incumbent_key),
        }

    def _record_worker_stats(self, results: Sequence[_BottomTaskResult]) -> None:
        for result in results:
            self.cache.stats.hits += int(result.q_hits)
            self.cache.stats.misses += int(result.q_misses)
            self.cache.stats.evictions += int(result.q_evictions)

    def _run_payloads(self, payloads, *, pool=None):
        payloads = tuple(payloads)
        if not payloads:
            return ()
        if pool is None:
            rows = tuple(_phase5i_bottom_task(payload) for payload in payloads)
        else:
            rows = tuple(pool.map(_phase5i_bottom_task, payloads))
        self._record_worker_stats(rows)
        return rows

    def _legacy_evaluate(
        self,
        seven: Tuple[str, ...],
        *,
        stage: int,
        legal: Tuple[Tuple[str, ...], ...],
    ) -> Phase5IOpeningKeepEvaluation:
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
            parallel_workers=1,
            confirmation_start_sample=self.screen_rollouts,
        )

    def _adaptive_evaluate(
        self,
        seven: Tuple[str, ...],
        *,
        stage: int,
        legal: Tuple[Tuple[str, ...], ...],
    ) -> Phase5IOpeningKeepEvaluation:
        worker_count = min(self.parallel_workers, len(legal))
        executor = (
            ProcessPoolExecutor(max_workers=worker_count)
            if worker_count > 1
            else None
        )
        try:
            initial = self._run_payloads(
                (
                    self._task_payload(
                        seven,
                        stage=stage,
                        bottom=bottom,
                        sample_start=0,
                        sample_count=self.screen_rollouts,
                    )
                    for bottom in legal
                ),
                pool=executor,
            )
            screen_rows = {row.estimate.bottom: row.estimate for row in initial}
            initial_ranked = _rank_keep_estimates(tuple(screen_rows.values()))
            cutoff_index = min(self.shortlist_size, len(initial_ranked)) - 1
            cutoff_key = initial_ranked[cutoff_index].value.comparison_key()
            above = [
                row.bottom
                for row in initial_ranked
                if row.value.comparison_key() > cutoff_key
            ]
            contenders = [
                row.bottom
                for row in initial_ranked
                if row.value.comparison_key() == cutoff_key
            ]
            locked = []
            slots_remaining = self.shortlist_size - len(above)
            tie_rounds = 0

            # Only the exact boundary tie group receives extra paired worlds.
            # Candidates already below the original cutoff never re-enter.
            while (
                len(contenders) > slots_remaining
                and tie_rounds < self.max_screen_tie_break_rollouts
            ):
                sample_id = self.screen_rollouts + tie_rounds
                extra = self._run_payloads(
                    (
                        self._task_payload(
                            seven,
                            stage=stage,
                            bottom=bottom,
                            sample_start=sample_id,
                            sample_count=1,
                        )
                        for bottom in contenders
                    ),
                    pool=executor,
                )
                for row in extra:
                    screen_rows[row.estimate.bottom] = _merge_keep_estimates(
                        (screen_rows[row.estimate.bottom], row.estimate)
                    )
                tie_rounds += 1
                ranked_contenders = _rank_keep_estimates(
                    tuple(screen_rows[bottom] for bottom in contenders)
                )
                boundary_key = ranked_contenders[
                    min(slots_remaining, len(ranked_contenders)) - 1
                ].value.comparison_key()
                newly_locked = [
                    row.bottom
                    for row in ranked_contenders
                    if row.value.comparison_key() > boundary_key
                ]
                locked.extend(newly_locked)
                slots_remaining -= len(newly_locked)
                contenders = [
                    row.bottom
                    for row in ranked_contenders
                    if row.value.comparison_key() == boundary_key
                ]

            if len(contenders) <= slots_remaining:
                chosen_boundary = locked + contenders
            else:
                # Still tied after the bounded paired re-screen: preserve every
                # exact boundary tie, matching the conservative legacy contract.
                chosen_boundary = locked + contenders
            shortlist = tuple(dict.fromkeys(tuple(above) + tuple(chosen_boundary)))
            screen = _opening_evaluation_from_estimates(
                stage=stage,
                seven=seven,
                estimates=tuple(screen_rows.values()),
                rollout_count_per_bottom=self.screen_rollouts,
                mc_root_seed=self.mc_root_seed,
                horizon=self.horizon,
                opening_environment=self.opening_environment,
            )

            confirmation_start = self.screen_rollouts + tie_rounds
            screen_rank = _rank_keep_estimates(
                tuple(screen_rows[bottom] for bottom in shortlist)
            )
            leader_bottom = screen_rank[0].bottom
            leader_result = self._run_payloads(
                (
                    self._task_payload(
                        seven,
                        stage=stage,
                        bottom=leader_bottom,
                        sample_start=confirmation_start,
                        sample_count=self.confirm_rollouts,
                    ),
                ),
                pool=executor,
            )[0]
            if not leader_result.completed:
                raise AssertionError("unbounded confirmation leader stopped early")
            incumbent_key = leader_result.estimate.value.comparison_key()

            remaining = tuple(
                bottom for bottom in shortlist if bottom != leader_bottom
            )
            challengers = self._run_payloads(
                (
                    self._task_payload(
                        seven,
                        stage=stage,
                        bottom=bottom,
                        sample_start=confirmation_start,
                        sample_count=self.confirm_rollouts,
                        incumbent_key=incumbent_key,
                    )
                    for bottom in remaining
                ),
                pool=executor,
            )
            complete = [leader_result.estimate]
            early_eliminated = []
            for row in challengers:
                if row.completed:
                    complete.append(row.estimate)
                else:
                    early_eliminated.append(row.estimate.bottom)

            confirmation = _opening_evaluation_from_estimates(
                stage=stage,
                seven=seven,
                estimates=complete,
                rollout_count_per_bottom=self.confirm_rollouts,
                mc_root_seed=self.mc_root_seed,
                horizon=self.horizon,
                opening_environment=self.opening_environment,
            )
            return Phase5IOpeningKeepEvaluation(
                stage=int(stage),
                seven=seven,
                screen=screen,
                confirmation=confirmation,
                shortlisted_bottoms=tuple(sorted(shortlist)),
                legal_bottom_count=len(legal),
                screen_rollouts_per_bottom=self.screen_rollouts,
                confirm_rollouts_per_bottom=self.confirm_rollouts,
                screen_tie_break_rollouts=tie_rounds,
                confirmation_early_eliminated_bottoms=tuple(sorted(early_eliminated)),
                parallel_workers=worker_count,
                confirmation_start_sample=confirmation_start,
            )
        finally:
            if executor is not None:
                executor.shutdown(wait=True)

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
                parallel_workers=1,
                confirmation_start_sample=0,
            )

        # A live Gemstone opening can have multiple pregame exile choices for one
        # bottom.  Keep the old aggregate evaluator there until a future worker
        # protocol carries per-pregame-variant outcomes across adaptive rounds.
        if (
            "Gemstone Caverns" in seven
            and self.opening_environment.caverns_live
        ):
            return self._legacy_evaluate(seven, stage=stage, legal=legal)

        return self._adaptive_evaluate(seven, stage=stage, legal=legal)


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
