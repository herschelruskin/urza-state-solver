#!/usr/bin/env python3
"""Phase-5 overlay for reproduced public-action parity gaps.

Phase 2 remains frozen. This adapter delegates all established decisions and
transitions to ``non_oracle_rules_adapter`` and merges only mechanically evidenced
public surfaces that the Oracle can use but the frozen adapter did not expose:

* fetchland activation;
* Banishing Knack / Retraction Helix granted-bounce activation;
* Fortune Teller's Talent class-level actions (implementation already existed,
  but was orphaned from the action surface).
"""

from __future__ import annotations

from decision_observation import DecisionRequest
import non_oracle_rules_adapter as base
from non_oracle_ftt_runtime import MAIN_LEVEL_FTT, apply_ftt_level_action, ftt_level_main_intents
from non_oracle_public_parity_runtime import (
    PUBLIC_PARITY_KINDS,
    apply_public_parity_action,
    public_parity_main_intents,
    public_parity_priority_actions,
)


def _merge_request(request: DecisionRequest, extra_actions) -> DecisionRequest:
    by_key = {action.canonical_key(): action for action in request.actions}
    for action in extra_actions:
        by_key.setdefault(action.canonical_key(), action)
    return DecisionRequest(
        observation=request.observation,
        actions=tuple(sorted(by_key.values(), key=lambda action: action.action_id)),
        context=request.context,
    )


def _phase5_main_actions(runtime):
    rows = list(public_parity_main_intents(runtime))
    rows.extend(ftt_level_main_intents(runtime))
    return tuple(sorted(rows, key=lambda action: action.action_id))


def main_phase_intents(runtime):
    rows = list(base.main_phase_intents(runtime))
    rows.extend(_phase5_main_actions(runtime))
    by_key = {action.canonical_key(): action for action in rows}
    return tuple(sorted(by_key.values(), key=lambda action: action.action_id))


def rules_decision_request(
    runtime,
    *,
    horizon: int,
    objective: str = "win_by_horizon",
    policy_id: str = "urza-deterministic-base-v1",
    caverns_live=None,
):
    request = base.rules_decision_request(
        runtime,
        horizon=horizon,
        objective=objective,
        policy_id=policy_id,
        caverns_live=caverns_live,
    )
    if runtime.pending is not None:
        return request
    if runtime.stack.objects:
        return _merge_request(request, public_parity_priority_actions(runtime))
    if runtime.true_state.remora_upkeep_pending:
        return request
    return _merge_request(request, _phase5_main_actions(runtime))


def apply_main_action(runtime, action):
    if action.kind in PUBLIC_PARITY_KINDS:
        return apply_public_parity_action(runtime, action)
    if action.kind == MAIN_LEVEL_FTT:
        return apply_ftt_level_action(runtime, action)
    return base.apply_main_action(runtime, action)
