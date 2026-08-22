#!/usr/bin/env python3
"""Composite value identity for non-Oracle runtime sidecars.

The strategic state projection intentionally excludes provenance, exact hidden
permutation, and RNG.  Policy-mode execution additionally carries public rules
resources that are not part of the base strategic projection:

- live until-end-of-turn Urza play permissions;
- ordered pending stack objects;
- the current decision/priority window.

Those resources change future legal actions and therefore MUST participate in
V/Q memoization identity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from solver_architecture import InformationState, stable_key
from strategic_value_state import canonical_strategic_state_key
from trigger_order_adapter import PendingTriggerStack
from urza_permission_adapter import UrzaPermissionState

NON_ORACLE_RUNTIME_VALUE_KEY_VERSION = "urza-non-oracle-runtime-value-v2"
WINDOW_MAIN_EMPTY = "main_empty"
WINDOW_PRIORITY = "priority"
WINDOW_POST_OBSERVATION = "post_observation"
VALID_RUNTIME_WINDOWS = frozenset(
    {WINDOW_MAIN_EMPTY, WINDOW_PRIORITY, WINDOW_POST_OBSERVATION}
)


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


def canonical_non_oracle_runtime_value_key(
    state,
    information: InformationState,
    *,
    permissions: Optional[UrzaPermissionState] = None,
    trigger_stack: Optional[PendingTriggerStack] = None,
    runtime_stack=None,
    window: Optional[RuntimeDecisionWindow] = None,
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
        ),
        version=NON_ORACLE_RUNTIME_VALUE_KEY_VERSION,
    )
