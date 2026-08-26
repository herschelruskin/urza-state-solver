#!/usr/bin/env python3
"""Phase-5 information-safe Monte Carlo evaluation for arbitrary visible decisions.

This is the parity-aware successor to the Phase-4 root evaluator.  It keeps the
same information boundary and common-random-number design but evaluates the current
Phase-5 production action surface (fetch/Knack/Chain/Offer/permission fixes included).

The evaluator is rules-side infrastructure, not a policy that receives raw State.
It derives a LibraryBeliefKey from the runtime + information state, samples hidden
worlds from that belief, verifies the policy-visible request is invariant across
worlds, applies one candidate action, and then delegates continuation to a fixed
information-constrained policy.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import sqrt
from typing import Iterable, Sequence, Tuple

from decision_observation import ActionIntent
from non_oracle_base_policy import DeterministicBasePolicy
from non_oracle_episode import NonOracleEpisodeResult, run_deterministic_episode
from non_oracle_rules_adapter_v2 import apply_main_action, rules_decision_request
from phase3_value_engine import PHASE3_OBJECTIVE_ID, WinDistributionValue
from phase4_hidden_world import HiddenWorldSampler, materialize_hidden_world
from solver_architecture import EpisodeOutcome
from strategic_value_state import LibraryBeliefKey

PHASE5_MC_VERSION = "urza-phase5-decision-monte-carlo-v1"

# A deterministic continuation policy can exhaust every strategic action from an
# exact recurrent sampled state. That is a legitimate leaf-policy failure/no-win
# outcome, not evidence that Magic mechanics are missing. Unsupported runtime
# windows, no-legal-action blockers, and step limits remain hard errors in strict
# mode so Q estimates cannot silently absorb missing rules coverage.
MODELED_NO_WIN_TERMINALS = frozenset({"horizon", "strategic_cycle_exhausted"})
MODELED_TERMINALS = MODELED_NO_WIN_TERMINALS | {"win"}


class Phase5MonteCarloError(RuntimeError):
    pass


@dataclass(frozen=True)
class Phase5ActionEstimate:
    action: ActionIntent
    value: WinDistributionValue
    rollouts: int
    terminal_reason_counts: Tuple[Tuple[str, int], ...]
    win_probability_wilson95: Tuple[float, float]

    @property
    def win_probability(self) -> float:
        return self.value.win_probability


@dataclass(frozen=True)
class Phase5DecisionEvaluation:
    best_action: ActionIntent
    estimates: Tuple[Phase5ActionEstimate, ...]
    rollout_count_per_action: int
    mc_root_seed: int
    horizon: int
    continuation_policy_id: str
    version: str = PHASE5_MC_VERSION


def _wilson(successes: int, trials: int, z: float = 1.959963984540054):
    if trials <= 0:
        return (0.0, 1.0)
    p = successes / trials
    z2 = z * z
    denom = 1.0 + z2 / trials
    center = (p + z2 / (2.0 * trials)) / denom
    half = z * sqrt(max(0.0, p * (1.0 - p) / trials + z2 / (4.0 * trials * trials))) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def _representatives(actions: Iterable[ActionIntent]) -> Tuple[ActionIntent, ...]:
    rows = {}
    for action in sorted(actions, key=lambda a: a.action_id):
        rows.setdefault(action.strategic_key(), action)
    return tuple(rows[key] for key in sorted(rows, key=repr))


def _episode_outcome(result: NonOracleEpisodeResult, *, horizon: int) -> EpisodeOutcome:
    won = bool(result.won_by_horizon)
    return EpisodeOutcome(
        won=won,
        win_turn=int(result.win_turn) if won and result.win_turn is not None else None,
        terminal_turn=min(max(0, int(result.runtime.true_state.turn)), int(horizon)),
        horizon=int(horizon),
        win_family=str(result.win_family) if won else "",
        terminal_reason=str(result.terminal_reason),
    )


def _value(outcomes: Sequence[EpisodeOutcome], *, horizon: int) -> WinDistributionValue:
    if not outcomes:
        raise ValueError("at least one rollout outcome is required")
    exact = [0] * horizon
    families: Counter[str] = Counter()
    wins = 0
    for outcome in outcomes:
        if not outcome.won:
            continue
        assert outcome.win_turn is not None
        exact[int(outcome.win_turn) - 1] += 1
        wins += 1
        if outcome.win_family:
            families[outcome.win_family] += 1
    n = len(outcomes)
    return WinDistributionValue(
        horizon=horizon,
        exact_win=tuple(x / n for x in exact),
        no_win=(n - wins) / n,
        win_families=tuple((name, count / n) for name, count in sorted(families.items())),
    )


class Phase5MonteCarloDecisionEvaluator:
    """Common-random-number Q estimate for the current visible decision."""

    def __init__(
        self,
        *,
        rollout_count: int = 8,
        mc_root_seed: int = 20260826,
        horizon: int = 6,
        objective: str = PHASE3_OBJECTIVE_ID,
        continuation_policy: DeterministicBasePolicy,
        max_episode_steps: int = 512,
        strict_terminal_reasons: bool = True,
    ):
        if rollout_count < 1:
            raise ValueError("rollout_count must be >= 1")
        self.rollout_count = int(rollout_count)
        self.mc_root_seed = int(mc_root_seed)
        self.horizon = int(horizon)
        self.objective = str(objective)
        self.continuation_policy = continuation_policy
        self.max_episode_steps = int(max_episode_steps)
        self.strict_terminal_reasons = bool(strict_terminal_reasons)
        self.sampler = HiddenWorldSampler(self.mc_root_seed)

    def _request(self, runtime):
        return rules_decision_request(
            runtime,
            horizon=self.horizon,
            objective=self.objective,
            policy_id=self.continuation_policy.policy_id,
        )

    @staticmethod
    def _map(actions):
        return {action.strategic_key(): action for action in _representatives(actions)}

    def evaluate(self, runtime, *, candidate_actions=None) -> Phase5DecisionEvaluation:
        root_request = self._request(runtime)
        all_root = _representatives(root_request.actions)
        if not all_root:
            raise Phase5MonteCarloError("decision has no modeled actions")

        if candidate_actions is None:
            root_actions = all_root
        else:
            allowed = {action.strategic_key() for action in candidate_actions}
            root_actions = tuple(a for a in all_root if a.strategic_key() in allowed)
            if not root_actions:
                raise Phase5MonteCarloError("candidate action subset is empty")

        root_observation_key = root_request.observation.key()
        root_keys = frozenset(action.strategic_key() for action in all_root)
        candidate_keys = frozenset(action.strategic_key() for action in root_actions)
        root_map = {action.strategic_key(): action for action in root_actions}
        belief = LibraryBeliefKey.from_state(runtime.true_state, runtime.information)

        outcomes = {key: [] for key in candidate_keys}
        reasons = {key: Counter() for key in candidate_keys}

        for sample_index in range(self.rollout_count):
            world = self.sampler.sample(
                belief,
                sample_id=("phase5-q", sample_index),
            )
            sampled_runtime = materialize_hidden_world(runtime, world)
            sampled_request = self._request(sampled_runtime)
            if sampled_request.observation.key() != root_observation_key:
                raise Phase5MonteCarloError(
                    "sampled hidden world changed current PolicyView before observation"
                )
            sampled_all = self._map(sampled_request.actions)
            if frozenset(sampled_all) != root_keys:
                raise Phase5MonteCarloError(
                    "sampled hidden world changed the policy-visible action set"
                )

            for key in sorted(candidate_keys, key=repr):
                after = apply_main_action(sampled_runtime, sampled_all[key])
                result = run_deterministic_episode(
                    after,
                    horizon=self.horizon,
                    policy=self.continuation_policy,
                    max_steps=self.max_episode_steps,
                )
                reason = str(result.terminal_reason)
                reasons[key][reason] += 1
                if self.strict_terminal_reasons and reason not in MODELED_TERMINALS:
                    tail = tuple(
                        (step.turn_before, step.action_kind, step.action_label)
                        for step in result.steps[-12:]
                    )
                    public_board = tuple(
                        (perm.name, bool(perm.tapped), int(perm.counters), perm.mode)
                        for perm in result.runtime.true_state.battlefield
                    )
                    raise Phase5MonteCarloError(
                        "rollout hard blocker: "
                        f"sample={sample_index}; "
                        f"root_action={sampled_all[key].label!r}; "
                        f"action_id={sampled_all[key].action_id!r}; "
                        f"reason={reason!r}; "
                        f"turn={result.runtime.true_state.turn}; "
                        f"hand={tuple(result.runtime.true_state.hand)!r}; "
                        f"battlefield={public_board!r}; "
                        f"tail={tail!r}"
                    )
                outcomes[key].append(_episode_outcome(result, horizon=self.horizon))

        estimates = []
        for key in sorted(candidate_keys, key=repr):
            rows = tuple(outcomes[key])
            value = _value(rows, horizon=self.horizon)
            wins = sum(x.won for x in rows)
            estimates.append(
                Phase5ActionEstimate(
                    action=root_map[key],
                    value=value,
                    rollouts=len(rows),
                    terminal_reason_counts=tuple(sorted(reasons[key].items())),
                    win_probability_wilson95=_wilson(wins, len(rows)),
                )
            )

        ranked = tuple(
            sorted(
                estimates,
                key=lambda est: (
                    est.value.comparison_key(),
                    repr(est.action.strategic_key()),
                ),
                reverse=True,
            )
        )
        return Phase5DecisionEvaluation(
            best_action=ranked[0].action,
            estimates=ranked,
            rollout_count_per_action=self.rollout_count,
            mc_root_seed=self.mc_root_seed,
            horizon=self.horizon,
            continuation_policy_id=self.continuation_policy.policy_id,
        )
