#!/usr/bin/env python3
"""Priority-time Chrome Dome activation and priority extension bridge for Phase 2.

Chrome Dome's ordinary copy ability is not sorcery-speed. The main-phase bridge
models the same ability when the stack is empty; this module exposes it while we
hold priority over an existing stack object without conflating that timing with the
opponent-end-step turn-boundary shortcut.

The policy sees only public target signatures and the public activation cost. Exact
permanent tags remain rules-side. Paying the cost and choosing the target happen
before the activated ability is pushed above the older stack; the existing Chrome
stack resolver creates the temporary copy only when that ability resolves.

The legacy combined-priority aggregator imports ``chrome_priority_actions`` from this
module, so the aggregation function also appends the other typed priority extensions
that do not own the central request: Reality Chip/FTT top casts and Urza spin/exile
permissions. Each extension still validates/applies its own action family.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Tuple

import urza_solver as solver
import non_oracle_runtime as core
from decision_observation import ActionIntent, DECISION_MECHANICAL
from non_oracle_chrome_dome_runtime import ACT_CHROME_COPY, CHROME, _artifact_groups
from non_oracle_runtime_value_key import RuntimeDecisionWindow, WINDOW_PRIORITY

PRIORITY_ACTIVATE_CHROME = "priority_activate_chrome_dome"


def _chrome_only_priority_actions(runtime: core.NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    if (
        runtime.pending is not None
        or not runtime.stack.objects
        or runtime.window.kind != WINDOW_PRIORITY
    ):
        return ()
    state = runtime.true_state
    if not solver.has(state, CHROME):
        return ()
    cost = int(solver.chrome_activation_cost(state))
    if not solver.can_pay(state, cost, 0):
        return ()
    groups = _artifact_groups(state)
    rows = []
    for index, signature in enumerate(sorted(groups, key=repr)):
        name = str(signature[0]) if signature else "artifact"
        rows.append(ActionIntent(
            action_id=f"priority.chrome.copy.{index:03d}",
            kind=PRIORITY_ACTIVATE_CHROME,
            parameters=(
                ("activation_cost", cost),
                ("target_name", name),
                ("target_signature", signature),
            ),
            equivalence_key=(PRIORITY_ACTIVATE_CHROME, cost, signature),
            label=f"Chrome Dome at priority: pay {{{cost}}} to copy {name}",
            decision_stage=DECISION_MECHANICAL,
            source=CHROME,
        ))
    return tuple(rows)


def chrome_priority_actions(runtime: core.NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    rows = list(_chrome_only_priority_actions(runtime))
    # Local imports avoid module cycles; each adapter owns validation/application.
    from non_oracle_top_access_runtime import top_access_priority_intents
    from non_oracle_urza_runtime import urza_priority_intents
    rows.extend(top_access_priority_intents(runtime))
    rows.extend(urza_priority_intents(runtime))
    return tuple(sorted(rows, key=lambda action: action.action_id))


def apply_chrome_priority_action(
    runtime: core.NonOracleRuntimeState,
    action: ActionIntent,
) -> core.NonOracleRuntimeState:
    legal = {candidate.canonical_key() for candidate in _chrome_only_priority_actions(runtime)}
    if action.canonical_key() not in legal:
        raise ValueError("Chrome Dome priority activation is no longer legal")
    params = dict(action.parameters)
    cost = int(params["activation_cost"])
    signature = tuple(params["target_signature"])
    groups = _artifact_groups(runtime.true_state)
    candidates = groups.get(signature, ())
    if not candidates:
        raise ValueError("Chrome Dome priority target is no longer a legal artifact")
    target = candidates[0]
    paid = solver.pay(runtime.true_state, cost, 0)
    if paid is None:
        raise ValueError("Chrome Dome priority activation cost can no longer be paid")
    paid = solver.add_trace(
        paid,
        f"Phase2 priority Chrome Dome activation: pay {{{cost}}}, target {target.name or target.mode}",
    )
    exact = (
        ("activation_cost", cost),
        ("target_tag", int(target.instance_tag)),
    )
    public = (
        ("activation_cost", cost),
        ("target_name", target.name or target.mode),
        ("target_state", signature),
    )
    obj, stack = runtime.stack.allocate(
        object_type=core.STACK_TRIGGER,
        kind=ACT_CHROME_COPY,
        source=CHROME,
        card=CHROME,
        payload=exact,
        public_payload=public,
        strategic_payload=public,
    )
    return replace(
        runtime,
        true_state=paid,
        stack=stack.push_existing((obj,)),
        window=RuntimeDecisionWindow(WINDOW_PRIORITY),
    )
