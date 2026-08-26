#!/usr/bin/env python3
"""Common-random-number Monte Carlo evaluation of visible root actions.

This is the first executable Phase-4 policy-improvement layer.  It deliberately
keeps a narrow boundary:

1. derive one legal-information library belief from the current runtime;
2. enumerate/collapse the policy-visible root actions;
3. sample the SAME hidden worlds for every competing root action;
4. take one root action in each sampled world;
5. continue with the deterministic information-constrained base policy;
6. aggregate full T1..Thorizon win distributions and uncertainty.

The evaluator never asks the Oracle search to choose a continuation and never
uses the actual unknown library permutation as a policy input.  Concrete sampled
worlds exist only inside the evaluator/rules side of the boundary.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import sqrt
from typing import Any, Iterable, Optional, Sequence, Tuple

from decision_observation import ActionIntent
from non_oracle_base_policy import DeterministicBasePolicy
from non_oracle_episode import NonOracleEpisodeResult, run_deterministic_episode
from non_oracle_rules_adapter import apply_main_action, rules_decision_request
from phase3_value_engine import PHASE3_OBJECTIVE_ID, WinDistributionValue
from phase4_hidden_world import HiddenWorldSampler, materialize_hidden_world
from solver_architecture import EpisodeOutcome
from strategic_value_state import LibraryBeliefKey


PHASE4_MC_VERSION = "urza-root-monte-carlo-v1"


class MonteCarloEvaluationError(RuntimeError):
    pass


@dataclass(frozen=True)
class MonteCarloActionEstimate:
    action: ActionIntent
    value: WinDistributionValue
    rollouts: int
    terminal_reason_counts: Tuple[Tuple[str, int], ...]
    win_probability_wilson95: Tuple[float, float]
    cumulative_wilson95: Tuple[Tuple[int, float, float], ...]

    @property
    def win_probability(self) -> float:
        return self.value.win_probability

    @property
    def win_probability_standard_error(self) -> float:
        if self.rollouts <= 0:
            return 0.0
        p = self.win_probability
        return sqrt(max(0.0, p * (1.0 - p) / self.rollouts))


@dataclass(frozen=True)
class MonteCarloRootEvaluation:
    best_action: ActionIntent
    estimates: Tuple[MonteCarloActionEstimate, ...]
    rollout_count_per_action: int
    mc_root_seed: int
    horizon: int
    objective: str
    continuation_policy_id: str
    version: str = PHASE4_MC_VERSION

    def estimate_for(self, action: ActionIntent) -> MonteCarloActionEstimate:
        key = action.strategic_key()
        for estimate in self.estimates:
            if estimate.action.strategic_key() == key:
                return estimate
        raise KeyError(action.action_id)


def _wilson_interval(successes: int, trials: int, z: float = 1.959963984540054) -> Tuple[float, float]:
    if trials <= 0:
        return (0.0, 1.0)
    p = successes / trials
    z2 = z * z
    denom = 1.0 + z2 / trials
    center = (p + z2 / (2.0 * trials)) / denom
    half = z * sqrt((p * (1.0 - p) + z2 / (4.0 * trials)) / trials) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def _action_representatives(actions: Iterable[ActionIntent]) -> Tuple[ActionIntent, ...]:
    """One deterministic representative per explicitly strategic-equivalent action."""
    representatives = {}
    for action in sorted(actions, key=lambda item: item.action_id):
        representatives.setdefault(action.strategic_key(), action)
    return tuple(
        representatives[key]
        for key in sorted(representatives, key=repr)
    )


def _episode_outcome(result: NonOracleEpisodeResult, *, horizon: int) -> EpisodeOutcome:
    won = bool(result.won_by_horizon)
    terminal_turn = min(max(0, int(result.runtime.true_state.turn)), int(horizon))
    return EpisodeOutcome(
        won=won,
        win_turn=int(result.win_turn) if won and result.win_turn is not None else None,
        terminal_turn=terminal_turn,
        horizon=int(horizon),
        win_family=str(result.win_family) if won else "",
        terminal_reason=str(result.terminal_reason),
    )


def _value_from_outcomes(outcomes: Sequence[EpisodeOutcome], *, horizon: int) -> WinDistributionValue:
    if not outcomes:
        raise ValueError("Monte Carlo estimate requires at least one outcome")
    exact = [0] * horizon
    family_counts: Counter[str] = Counter()
    wins = 0
    for outcome in outcomes:
        if outcome.won:
            assert outcome.win_turn is not None
            exact[outcome.win_turn - 1] += 1
            wins += 1
            if outcome.win_family:
                family_counts[outcome.win_family] += 1
    n = len(outcomes)
    return WinDistributionValue(
        horizon=horizon,
        exact_win=tuple(count / n for count in exact),
        no_win=(n - wins) / n,
        win_families=tuple(
            (family, count / n) for family, count in sorted(family_counts.items())
        ),
    )


class MonteCarloRootEvaluator:
    """Evaluate visible root actions using common sampled hidden worlds."""

    def __init__(
        self,
        *,
        rollout_count: int = 64,
        mc_root_seed: int = 0,
        horizon: int = 6,
        objective: str = PHASE3_OBJECTIVE_ID,
        continuation_policy: DeterministicBasePolicy | None = None,
        max_episode_steps: int = 512,
        strict_terminal_reasons: bool = True,
    ) -> None:
        if rollout_count < 1:
            raise ValueError("rollout_count must be >= 1")
        if horizon < 1:
            raise ValueError("horizon must be >= 1")
        self.rollout_count = int(rollout_count)
        self.mc_root_seed = int(mc_root_seed)
        self.horizon = int(horizon)
        self.objective = str(objective)
        self.continuation_policy = continuation_policy or DeterministicBasePolicy()
        self.max_episode_steps = int(max_episode_steps)
        self.strict_terminal_reasons = bool(strict_terminal_reasons)
        self.sampler = HiddenWorldSampler(self.mc_root_seed)

    def _root_request(self, runtime):
        return rules_decision_request(
            runtime,
            horizon=self.horizon,
            objective=self.objective,
            policy_id=self.continuation_policy.policy_id,
        )

    @staticmethod
    def _representative_map(request) -> dict[Tuple[object, ...], ActionIntent]:
        return {
            action.strategic_key(): action
            for action in _action_representatives(request.actions)
        }

    def evaluate(self, runtime) -> MonteCarloRootEvaluation:
        root_request = self._root_request(runtime)
        root_actions = _action_representatives(root_request.actions)
        if not root_actions:
            raise MonteCarloEvaluationError("root state has no modeled policy actions")

        root_observation_key = root_request.observation.key()
        root_action_map = {action.strategic_key(): action for action in root_actions}
        root_action_keys = frozenset(root_action_map)
        belief = LibraryBeliefKey.from_state(runtime.true_state, runtime.information)

        outcomes_by_action = {key: [] for key in root_action_keys}
        reasons_by_action = {key: Counter() for key in root_action_keys}

        for sample_index in range(self.rollout_count):
            world = self.sampler.sample(belief, sample_id=sample_index)
            sampled_runtime = materialize_hidden_world(runtime, world)
            sampled_request = self._root_request(sampled_runtime)

            # This is a hard strategy-fusion guard, not merely diagnostics. Before
            # any newly sampled card is legitimately observed, the visible root
            # decision must be identical across every hidden world.
            if sampled_request.observation.key() != root_observation_key:
                raise MonteCarloEvaluationError(
                    "sampled hidden world changed the root PolicyView before observation"
                )
            sampled_map = self._representative_map(sampled_request)
            if frozenset(sampled_map) != root_action_keys:
                raise MonteCarloEvaluationError(
                    "sampled hidden world changed policy-visible root action set"
                )

            # Reuse this exact sampled world for every contender: common random
            # numbers reduce action-difference variance without contaminating the
            # actual game RNG tape.
            for key in sorted(root_action_keys, key=repr):
                sampled_action = sampled_map[key]
                after_root = apply_main_action(sampled_runtime, sampled_action)
                result = run_deterministic_episode(
                    after_root,
                    horizon=self.horizon,
                    policy=self.continuation_policy,
                    max_steps=self.max_episode_steps,
                )
                reason = str(result.terminal_reason)
                reasons_by_action[key][reason] += 1
                if self.strict_terminal_reasons and reason not in {"win", "horizon"}:
                    raise MonteCarloEvaluationError(
                        f"rollout for {sampled_action.action_id!r} terminated with {reason!r}"
                    )
                outcomes_by_action[key].append(
                    _episode_outcome(result, horizon=self.horizon)
                )

        estimates = []
        for key in sorted(root_action_keys, key=repr):
            outcomes = tuple(outcomes_by_action[key])
            value = _value_from_outcomes(outcomes, horizon=self.horizon)
            win_count = sum(outcome.won for outcome in outcomes)
            cumulative_ci = []
            for turn in range(1, self.horizon + 1):
                successes = sum(outcome.win_by(turn) for outcome in outcomes)
                low, high = _wilson_interval(successes, len(outcomes))
                cumulative_ci.append((turn, low, high))
            estimates.append(
                MonteCarloActionEstimate(
                    action=root_action_map[key],
                    value=value,
                    rollouts=len(outcomes),
                    terminal_reason_counts=tuple(sorted(reasons_by_action[key].items())),
                    win_probability_wilson95=_wilson_interval(win_count, len(outcomes)),
                    cumulative_wilson95=tuple(cumulative_ci),
                )
            )

        ranked = tuple(
            sorted(
                estimates,
                key=lambda estimate: (
                    estimate.value.comparison_key(),
                    repr(estimate.action.strategic_key()),
                ),
                reverse=True,
            )
        )
        return MonteCarloRootEvaluation(
            best_action=ranked[0].action,
            estimates=ranked,
            rollout_count_per_action=self.rollout_count,
            mc_root_seed=self.mc_root_seed,
            horizon=self.horizon,
            objective=self.objective,
            continuation_policy_id=self.continuation_policy.policy_id,
        )
