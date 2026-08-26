#!/usr/bin/env python3
"""Deterministic information-constrained Phase-2 episode runner.

This is the first executable bridge from rules/policy infrastructure toward the
project's real outputs: per-hand trajectories and eventually P(win by T1..T6).
It deliberately uses the deterministic base policy only; DP/Monte Carlo will later
replace/improve decisions without changing the episode mechanics.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional, Tuple

import urza_solver as solver
from decision_observation import ActionIntent
from non_oracle_base_policy import DeterministicBasePolicy
from non_oracle_rules_adapter_v2 import apply_main_action, rules_decision_request
from non_oracle_runtime import NonOracleRuntimeState

EPISODE_RUNNER_VERSION = "urza-non-oracle-episode-v1"


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
) -> NonOracleEpisodeResult:
    """Execute one base-policy trajectory until win, horizon, or explicit blocker."""
    if horizon < 1:
        raise ValueError("episode horizon must be >= 1")
    policy = policy or DeterministicBasePolicy()
    runtime = _checked_runtime(runtime)
    steps = []

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

        action = policy.choose_request(request)
        before_turn = int(state.turn)
        before_window = runtime.window.kind
        observation_key = request.observation.key()
        runtime = apply_main_action(runtime, action)
        runtime = _checked_runtime(runtime)
        after = runtime.true_state
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
