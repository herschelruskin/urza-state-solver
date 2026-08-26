#!/usr/bin/env python3
"""Phase-5 overlay for reproduced public-action parity gaps.

Phase 2 remains frozen. This adapter delegates established decisions/transitions to
``non_oracle_rules_adapter`` and connects only mechanically evidenced public
surfaces that the Oracle can use but the production Phase-2 import path omitted:

* fetchland activation;
* Banishing Knack / Retraction Helix granted-bounce activation;
* Urza exile-permission casts for already-implemented search/tutor spells;
* Urza exile-permission Reshape/Whir X=0 casts.

The Urza extensions must be installed BEFORE importing the frozen rules adapter,
because that module imports function objects from ``non_oracle_urza_runtime`` by
name.  Search installs first; the X-spell extension deliberately layers on top.
FTT leveling, Chrome Dome, Top/Key, ordinary tutors, and other connected surfaces
remain owned by the frozen adapter and its existing submodules.
"""

from __future__ import annotations

from decision_observation import DecisionRequest
from non_oracle_urza_search_permission_runtime import install_urza_search_permission_extension

install_urza_search_permission_extension()

from non_oracle_urza_x_permission_runtime import install_urza_x_permission_extension

install_urza_x_permission_extension()

# Import only after the extension chain is installed; see module docstring.
import non_oracle_rules_adapter as base
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


def main_phase_intents(runtime):
    rows = list(base.main_phase_intents(runtime))
    rows.extend(public_parity_main_intents(runtime))
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
    return _merge_request(request, public_parity_main_intents(runtime))


def apply_main_action(runtime, action):
    if action.kind in PUBLIC_PARITY_KINDS:
        return apply_public_parity_action(runtime, action)
    return base.apply_main_action(runtime, action)
