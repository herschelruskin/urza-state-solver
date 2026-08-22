#!/usr/bin/env python3
"""Policy-facing public view of non-Oracle runtime sidecars.

PolicyView intentionally omits hidden concrete state.  Policy-mode execution also
has public temporary rules resources not represented in the legacy Oracle State:
Urza play permissions, pending trigger stack, and current timing window.  A policy
needs these facts to make sequencing decisions even when a permission is not
currently usable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from solver_architecture import InformationState, PolicyView, make_policy_view, stable_key
from non_oracle_runtime_value_key import RuntimeDecisionWindow
from trigger_order_adapter import PendingTriggerStack
from urza_permission_adapter import UrzaPermissionState

RUNTIME_POLICY_VIEW_VERSION = "urza-runtime-policy-view-v1"


@dataclass(frozen=True, order=True)
class PublicPlayPermissionView:
    card: str
    expires_turn: int
    source: str
    without_paying_mana_cost: bool

    def key(self) -> Tuple[object, ...]:
        return (
            self.card,
            self.expires_turn,
            self.source,
            self.without_paying_mana_cost,
        )


@dataclass(frozen=True, order=True)
class PublicPendingTriggerView:
    kind: str
    source: str
    payload: Tuple[Tuple[str, object], ...] = ()

    def key(self) -> Tuple[object, ...]:
        return (self.kind, self.source, tuple(self.payload))


@dataclass(frozen=True)
class RuntimePolicyView:
    base: PolicyView
    play_permissions: Tuple[PublicPlayPermissionView, ...] = ()
    pending_triggers: Tuple[PublicPendingTriggerView, ...] = ()
    window_kind: str = "main_empty"

    def key(self) -> Tuple[object, ...]:
        return stable_key(
            (
                self.base.key(),
                tuple(permission.key() for permission in self.play_permissions),
                tuple(trigger.key() for trigger in self.pending_triggers),
                self.window_kind,
            ),
            version=RUNTIME_POLICY_VIEW_VERSION,
        )


def make_runtime_policy_view(
    state,
    information: InformationState,
    *,
    permissions: UrzaPermissionState | None = None,
    trigger_stack: PendingTriggerStack | None = None,
    window: RuntimeDecisionWindow | None = None,
    caverns_live=None,
) -> RuntimePolicyView:
    permissions = permissions or UrzaPermissionState()
    trigger_stack = trigger_stack or PendingTriggerStack()
    window = window or RuntimeDecisionWindow()

    # Permission IDs/sequence counters are execution provenance.  Repeated views
    # preserve multiplicity while exposing only strategic public facts.
    play_permissions = tuple(
        sorted(
            PublicPlayPermissionView(
                permission.card,
                permission.expires_turn,
                permission.source,
                permission.without_paying_mana_cost,
            )
            for permission in permissions.permissions
        )
    )
    pending_triggers = tuple(
        PublicPendingTriggerView(
            trigger.kind,
            trigger.source,
            tuple(trigger.payload),
        )
        for trigger in trigger_stack.triggers
    )
    return RuntimePolicyView(
        base=make_policy_view(state, information, caverns_live=caverns_live),
        play_permissions=play_permissions,
        pending_triggers=pending_triggers,
        window_kind=window.kind,
    )
