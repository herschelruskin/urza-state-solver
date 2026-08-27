#!/usr/bin/env python3
"""Phase-5 overlay for reproduced public-action parity gaps.

Phase 2 remains frozen. This adapter delegates established decisions/transitions to
``non_oracle_rules_adapter`` and connects only mechanically evidenced public
surfaces that the Oracle can use but the production Phase-2 import path omitted:

* fetchland activation;
* Banishing Knack / Retraction Helix granted-bounce activation;
* Urza exile-permission casts for already-implemented search/tutor spells;
* Urza exile-permission Reshape/Whir X=0 casts;
* Chain of Vapor self-bounce/copy decisions;
* An Offer You Can't Refuse self-counter -> two-Treasure lines.

It also adds policy-safe legality/commitment normalization at two already-public
pending decisions:
- Transmute Artifact target choices are annotated with their deterministic public
  difference-payment consequence and stripped before Phase-2 execution;
- a Chrome Mox imprint trigger whose exact source has left the battlefield retains
  only its legal no-imprint branch, matching the Oracle instead of offering a card
  exile that cannot attach to any Chrome Mox.

Import order is part of the runtime contract. Cam's dispatch patch must be installed
first because Urza search-permission extensions import Transmute/Bay/search modules,
and those modules bind artifact-entry helpers by name. After Cam is installed, Urza
search permissions install, then the X-spell permission layer, and only then may the
frozen rules adapter import its function objects.
"""

from __future__ import annotations

from decision_observation import DecisionRequest

# Install Cam before ANY extension that imports search-resolution modules. This is
# deliberately idempotent; the frozen rules adapter will call the installer again.
from non_oracle_cam_runtime import install_cam_runtime_extension
install_cam_runtime_extension()

from non_oracle_urza_search_permission_runtime import install_urza_search_permission_extension
install_urza_search_permission_extension()

from non_oracle_urza_x_permission_runtime import install_urza_x_permission_extension
install_urza_x_permission_extension()

# Import only after the extension chain is installed; see module docstring.
import non_oracle_rules_adapter as base
from non_oracle_chain_offer_runtime import (
    CHAIN_COPY_CHOICE,
    CHAIN_OFFER_ACTION_KINDS,
    apply_chain_offer_stack_action,
    apply_chain_pending,
    begin_chain_offer_action,
    chain_offer_main_intents,
    chain_offer_priority_intents,
    chain_pending_request,
    handles_chain_offer_stack_top,
)
from non_oracle_public_parity_runtime import (
    PUBLIC_PARITY_KINDS,
    apply_public_parity_action,
    public_parity_main_intents,
    public_parity_priority_actions,
)
from phase5_chrome_trigger_adapter import (
    handles_chrome_imprint_request,
    normalize_chrome_imprint_request,
)
from phase5_transmute_commitment_adapter import (
    annotate_transmute_target_request,
    handles_transmute_target_request,
    strip_transmute_target_annotations,
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
    rows.extend(chain_offer_main_intents(runtime))
    return tuple(sorted(rows, key=lambda action: action.action_id))


def _phase5_priority_actions(runtime):
    rows = list(public_parity_priority_actions(runtime))
    rows.extend(chain_offer_priority_intents(runtime))
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
    if runtime.pending is not None and runtime.pending.kind == CHAIN_COPY_CHOICE:
        return chain_pending_request(
            runtime,
            horizon=horizon,
            objective=objective,
            policy_id=policy_id,
            caverns_live=caverns_live,
        )

    request = base.rules_decision_request(
        runtime,
        horizon=horizon,
        objective=objective,
        policy_id=policy_id,
        caverns_live=caverns_live,
    )
    if runtime.pending is not None:
        if handles_transmute_target_request(runtime):
            return annotate_transmute_target_request(runtime, request)
        if handles_chrome_imprint_request(runtime):
            return normalize_chrome_imprint_request(runtime, request)
        return request
    if runtime.stack.objects:
        return _merge_request(request, _phase5_priority_actions(runtime))
    if runtime.true_state.remora_upkeep_pending:
        return request
    return _merge_request(request, _phase5_main_actions(runtime))


def apply_main_action(runtime, action):
    if runtime.pending is not None and runtime.pending.kind == CHAIN_COPY_CHOICE:
        return apply_chain_pending(runtime, action)
    if action.kind in CHAIN_OFFER_ACTION_KINDS:
        if action.kind in {"chain_copy_decline", "chain_copy_commit"}:
            return apply_chain_pending(runtime, action)
        return begin_chain_offer_action(runtime, action)
    if action.kind in PUBLIC_PARITY_KINDS:
        return apply_public_parity_action(runtime, action)
    # A Chain/Offer object resolves only when the player actually passes
    # priority. Other legal priority actions (mana abilities, typed activations,
    # etc.) must remain available while that object sits on the stack.
    if handles_chain_offer_stack_top(runtime) and action.kind == "pass_priority":
        return apply_chain_offer_stack_action(runtime, action)
    return base.apply_main_action(runtime, strip_transmute_target_annotations(action))
