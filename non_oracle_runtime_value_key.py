#!/usr/bin/env python3
"""Composite value identity for non-Oracle runtime sidecars.

The strategic state projection intentionally excludes provenance, exact hidden
permutation, and RNG.  Policy-mode execution additionally carries public rules
resources that are not part of the base strategic projection:

- live until-end-of-turn Urza play permissions;
- ordered pending stack objects;
- the current decision/priority window;
- a pending policy/mechanical decision that has not yet been committed.

Those resources change future legal actions and therefore MUST participate in
V/Q memoization identity.  In particular, two states in the same generic
``post_observation`` window are not equivalent if one is choosing a different
trigger order, scry arrangement, target, imprint, or other contingent action.

``canonical_runtime_object_value_key(runtime)`` is the authoritative Phase-2
entry point for future DP/MC.  It reads all runtime sidecars, including the
pending decision, without requiring the runtime kernel to duplicate key logic.
"""

from __future__ import annotations

from dataclasses import dataclass, is_dataclass, fields
from typing import Optional, Tuple

from solver_architecture import InformationState, stable_key
from strategic_value_state import canonical_strategic_state_key
from trigger_order_adapter import PendingTriggerStack
from urza_permission_adapter import UrzaPermissionState

NON_ORACLE_RUNTIME_VALUE_KEY_VERSION = "urza-non-oracle-runtime-value-v4"
WINDOW_MAIN_EMPTY = "main_empty"
WINDOW_UPKEEP = "upkeep"
WINDOW_PRIORITY = "priority"
WINDOW_POST_OBSERVATION = "post_observation"
VALID_RUNTIME_WINDOWS = frozenset(
    {WINDOW_MAIN_EMPTY, WINDOW_UPKEEP, WINDOW_PRIORITY, WINDOW_POST_OBSERVATION}
)

# Execution coordinates that must not fragment expected-value identity.  The
# strategic/public state of the referenced object remains represented elsewhere
# in well-formed pending payloads (for example RuntimeStackObject.strategic_key()).
_PENDING_PROVENANCE_KEYS = frozenset({
    "object_id", "object_ids", "permission_id", "source_tag", "target_tag",
    "instance_tag", "decision_id", "contingent_on",
})


@dataclass(frozen=True)
class RuntimeDecisionWindow:
    kind: str = WINDOW_MAIN_EMPTY

    def __post_init__(self) -> None:
        if self.kind not in VALID_RUNTIME_WINDOWS:
            raise ValueError(f"invalid runtime decision window {self.kind!r}")

    def strategic_key(self) -> Tuple[object, ...]:
        return ("runtime-window-v1", self.kind)


def urza_permissions_strategic_key(
    permissions: UrzaPermissionState,
) -> Tuple[object, ...]:
    """Value identity ignores permission IDs/sequence provenance but not multiplicity."""
    rows = tuple(
        sorted(
            (
                permission.card,
                permission.expires_turn,
                permission.without_paying_mana_cost,
                permission.source,
            )
            for permission in permissions.permissions
        )
    )
    return ("urza-permissions-strategic-v1", rows)


def _stack_strategic_key(
    trigger_stack: PendingTriggerStack,
    runtime_stack,
) -> Tuple[object, ...]:
    if runtime_stack is not None:
        method = getattr(runtime_stack, "strategic_key", None)
        if method is None:
            raise TypeError("runtime_stack must provide strategic_key()")
        return tuple(method())
    return trigger_stack.strategic_key()


def _project_pending_value(value):
    """Project exact pending payload values to deterministic strategic identity."""
    method = getattr(value, "strategic_key", None)
    if method is not None:
        return tuple(method())
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, tuple):
        # Most runtime payloads are tuples of (name, value) rows.  Drop only
        # explicit execution/provenance coordinates, recursively project the rest.
        if all(isinstance(row, tuple) and len(row) == 2 and isinstance(row[0], str) for row in value):
            rows = []
            for key, item in value:
                if key in _PENDING_PROVENANCE_KEYS:
                    continue
                rows.append((key, _project_pending_value(item)))
            return tuple(rows)
        return tuple(_project_pending_value(item) for item in value)
    if isinstance(value, list):
        return tuple(_project_pending_value(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return tuple(sorted((_project_pending_value(item) for item in value), key=repr))
    if isinstance(value, dict):
        return tuple(sorted(
            (
                str(key),
                _project_pending_value(item),
            )
            for key, item in value.items()
            if str(key) not in _PENDING_PROVENANCE_KEYS
        ))
    if is_dataclass(value):
        # PendingDecisionSpec has execution-ish decision_id/contingent_on fields;
        # retain semantic kind/source/stage and any future non-provenance fields.
        rows = []
        for field in fields(value):
            if field.name in _PENDING_PROVENANCE_KEYS:
                continue
            rows.append((field.name, _project_pending_value(getattr(value, field.name))))
        return (value.__class__.__qualname__, tuple(rows))
    raise TypeError(f"cannot strategically project pending value {type(value)!r}")


def _pending_strategic_key(pending) -> Tuple[object, ...]:
    if pending is None:
        return ("runtime-pending-v2", None)
    method = getattr(pending, "strategic_key", None)
    if method is not None:
        return ("runtime-pending-v2", tuple(method()))

    # RuntimePendingDecision intentionally remains a lightweight runtime object.
    # Duck-type its public semantic surface so value identity does not depend on
    # execution IDs while still distinguishing different decision kinds/payloads.
    spec = getattr(pending, "spec", None)
    kind = getattr(pending, "kind", None)
    payload = getattr(pending, "payload", None)
    if spec is None or kind is None or payload is None:
        raise TypeError("pending runtime decision lacks spec/kind/payload")
    return (
        "runtime-pending-v2",
        str(kind),
        _project_pending_value(spec),
        _project_pending_value(tuple(payload)),
    )


def canonical_non_oracle_runtime_value_key(
    state,
    information: InformationState,
    *,
    permissions: Optional[UrzaPermissionState] = None,
    trigger_stack: Optional[PendingTriggerStack] = None,
    runtime_stack=None,
    window: Optional[RuntimeDecisionWindow] = None,
    pending=None,
    objective_memory=None,
) -> Tuple[object, ...]:
    permissions = permissions or UrzaPermissionState()
    trigger_stack = trigger_stack or PendingTriggerStack()
    window = window or RuntimeDecisionWindow()

    return stable_key(
        (
            canonical_strategic_state_key(
                state,
                information,
                objective_memory=objective_memory,
            ),
            urza_permissions_strategic_key(permissions),
            _stack_strategic_key(trigger_stack, runtime_stack),
            window.strategic_key(),
            _pending_strategic_key(pending),
        ),
        version=NON_ORACLE_RUNTIME_VALUE_KEY_VERSION,
    )


def canonical_runtime_object_value_key(runtime, *, objective_memory=None) -> Tuple[object, ...]:
    """Authoritative V/Q key for a complete Phase-2 runtime object.

    Future DP/MC code should use this entry point rather than manually selecting
    sidecars.  It deliberately includes ``runtime.pending`` while excluding exact
    hidden permutation/RNG through the underlying strategic-state projection.
    """
    return canonical_non_oracle_runtime_value_key(
        runtime.true_state,
        runtime.information,
        permissions=runtime.permissions,
        runtime_stack=runtime.stack,
        window=runtime.window,
        pending=runtime.pending,
        objective_memory=objective_memory,
    )