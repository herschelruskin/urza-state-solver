#!/usr/bin/env python3
"""Deterministic information-constrained Phase-2 episode runner.

This is the executable bridge from rules/policy infrastructure toward the
project's real outputs: per-hand trajectories and eventually P(win by T1..T6).
It deliberately keeps policy choice separate from rules execution; DP/Monte Carlo
can later replace/improve decisions without changing episode mechanics.

Phase 5 adds exact-world recurrent-state discipline.  The strategic V/Q key is not
suitable by itself for trajectory cycle detection because it intentionally forgets
hidden library order/RNG.  ``episode_cycle_key`` therefore combines:

* the concrete Markov true-state key (including hidden order and root RNG seed), and
* the semantic non-Oracle runtime value key (information, permissions, stack,
  window, pending decision; excluding execution/provenance IDs).

When an episode returns to that same concrete sampled world + semantic decision
state, a strategic action already attempted there is suppressed and the policy is
asked to choose among the remaining legal actions.  This prevents deterministic
zero-progress recurrences such as Knack/Golem/Mox bounce-recast loops without
altering V/Q identity or exposing hidden state to the policy.
"""

from __future__ import annotations

from collections import deque

from dataclasses import dataclass, replace
from typing import Optional, Tuple

import urza_solver as solver
from decision_observation import ActionIntent
from non_oracle_base_policy import DeterministicBasePolicy
from non_oracle_rules_adapter_v2 import apply_main_action, rules_decision_request
from non_oracle_runtime import NonOracleRuntimeState
from solver_architecture import canonical_markov_state_key, stable_key
from phase5_compact_runtime_encoding import compact_runtime_cycle_digest

EPISODE_RUNNER_VERSION = "urza-non-oracle-episode-v2-cycle-aware"
EPISODE_CYCLE_KEY_VERSION = "urza-episode-cycle-v1"


@dataclass(frozen=True)
class EpisodeStep:
    sequence: int
    turn_before: int
    window_kind: str
    observation_key: Tuple[object, ...]
    action_id: str
    action_kind: str
    action_label: str
    action_strategic_key: Tuple[object, ...]
    turn_after: int
    won_after: bool
    win_family_after: str


@dataclass(frozen=True)
class NonOracleEpisodeResult:
    runtime: NonOracleRuntimeState
    steps: Tuple[EpisodeStep, ...]
    horizon: int
    win_turn: Optional[int]
    win_family: str
    terminal_reason: str

    @property
    def won_by_horizon(self) -> bool:
        return self.win_turn is not None and self.win_turn <= self.horizon


def _checked_runtime(runtime: NonOracleRuntimeState) -> NonOracleRuntimeState:
    checked = solver.check_win(runtime.true_state)
    return runtime if checked is runtime.true_state else replace(runtime, true_state=checked)


def legacy_episode_cycle_key(runtime: NonOracleRuntimeState) -> Tuple[object, ...]:
    """Historical full tuple identity retained only for parity/regression tests."""
    return stable_key(
        (
            canonical_markov_state_key(runtime.true_state),
            runtime.value_key(),
        ),
        version=EPISODE_CYCLE_KEY_VERSION,
    )


def episode_cycle_key(runtime: NonOracleRuntimeState) -> bytes:
    """Exact sampled-world + semantic runtime identity for trajectory cycles.

    Production retains only a fixed 32-byte digest built from one-byte card IDs,
    packed scalar state, and semantic runtime sidecars.  The readable rules state
    remains unchanged; this only replaces the hot cycle-detection representation.
    """
    return compact_runtime_cycle_digest(runtime)


def _blocked_reason(runtime: NonOracleRuntimeState, horizon: int) -> str:
    state = runtime.true_state
    if state.won:
        return "win"
    if state.turn > horizon:
        return "horizon"
    if state.remora_upkeep_pending:
        return "unsupported_remora_upkeep"
    if state.saga3_pending:
        return "unsupported_saga3_window"
    if solver.has(state, "Chrome Dome"):
        return "unsupported_chrome_endstep_window"
    if runtime.pending is not None:
        return f"unsupported_pending:{runtime.pending.kind}"
    if runtime.stack.objects:
        return "unsupported_runtime_stack"
    return "no_legal_modeled_action"


def run_deterministic_episode(
    runtime: NonOracleRuntimeState,
    *,
    horizon: int = 6,
    policy: DeterministicBasePolicy | None = None,
    max_steps: int = 512,
    max_recorded_steps: int | None = None,
) -> NonOracleEpisodeResult:
    """Execute one policy trajectory until win, horizon, blocker, or exhausted cycle.

    For each exact recurrent episode state, each strategic action-equivalence class
    is attempted at most once.  The policy still ranks the available alternatives;
    the runner only removes an action after observing that the same concrete state
    has already taken that strategic action.  Thus cycle discipline is a controller
    invariant rather than a hand-written card heuristic.
    """
    if horizon < 1:
        raise ValueError("episode horizon must be >= 1")
    if max_recorded_steps is not None and int(max_recorded_steps) < 0:
        raise ValueError("max_recorded_steps must be >= 0 or None")
    policy = policy or DeterministicBasePolicy()
    runtime = _checked_runtime(runtime)
    steps = [] if max_recorded_steps is None else deque(maxlen=int(max_recorded_steps))
    attempted_by_cycle_state = {}

    for sequence in range(max_steps):
        state = runtime.true_state
        if state.won:
            return NonOracleEpisodeResult(
                runtime, tuple(steps), horizon, int(state.turn), state.win_family, "win"
            )
        if state.turn > horizon:
            return NonOracleEpisodeResult(
                runtime, tuple(steps), horizon, None, "", "horizon"
            )

        request = rules_decision_request(
            runtime,
            horizon=horizon,
            policy_id=policy.policy_id,
        )
        if not request.actions:
            return NonOracleEpisodeResult(
                runtime,
                tuple(steps),
                horizon,
                None,
                "",
                _blocked_reason(runtime, horizon),
            )

        cycle_key = episode_cycle_key(runtime)
        attempted = attempted_by_cycle_state.setdefault(cycle_key, set())
        fresh_actions = tuple(
            action for action in request.actions
            if action.strategic_key() not in attempted
        )
        if not fresh_actions:
            return NonOracleEpisodeResult(
                runtime,
                tuple(steps),
                horizon,
                None,
                "",
                "strategic_cycle_exhausted",
            )

        action = policy.choose(
            request.observation,
            fresh_actions,
            request.context,
        )
        attempted.add(action.strategic_key())
        before_turn = int(state.turn)
        before_window = runtime.window.kind
        observation_key = request.observation.key()
        runtime = apply_main_action(runtime, action)
        runtime = _checked_runtime(runtime)
        after = runtime.true_state
        if max_recorded_steps is None or int(max_recorded_steps) > 0:
            steps.append(
                EpisodeStep(
                    sequence=sequence,
                    turn_before=before_turn,
                    window_kind=before_window,
                    observation_key=observation_key,
                    action_id=action.action_id,
                    action_kind=action.kind,
                    action_label=action.label,
                    action_strategic_key=action.strategic_key(),
                    turn_after=int(after.turn),
                    won_after=bool(after.won),
                    win_family_after=str(after.win_family),
                )
            )

    return NonOracleEpisodeResult(
        runtime,
        tuple(steps),
        horizon,
        int(runtime.true_state.turn) if runtime.true_state.won else None,
        runtime.true_state.win_family if runtime.true_state.won else "",
        "step_limit",
    )
