#!/usr/bin/env python3
"""Policy-facing public view of non-Oracle runtime sidecars.

PolicyView intentionally omits hidden concrete state.  Policy-mode execution also
has public temporary rules resources not represented by the strategic public board:
Urza play permissions, the pending stack, and the current timing window.  A policy
needs these facts to make sequencing decisions even when a permission is not
currently usable.

Phase 1 exposed only controlled pending triggers.  Phase 2 extends that contract to
spell + trigger stack objects while keeping the old trigger-only view for backwards
compatibility with the Phase-1 smokes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from solver_architecture import InformationState, PolicyView, make_policy_view, stable_key
from non_oracle_runtime_value_key import RuntimeDecisionWindow
from trigger_order_adapter import PendingTriggerStack
from urza_permission_adapter import UrzaPermissionState

RUNTIME_POLICY_VIEW_VERSION = "urza-runtime-policy-view-v2"


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


@dataclass(frozen=True, order=True)
class PublicRuntimeStackObjectView:
    """Policy-safe top-first stack object.

    Runtime/execution IDs are deliberately omitted.  ``payload`` may contain only
    public rules facts chosen by the rules adapter; concrete hidden state is never
    copied here.
    """

    object_type: str
    kind: str
    source: str
    card: str = ""
    payload: Tuple[Tuple[str, object], ...] = ()

    def key(self) -> Tuple[object, ...]:
        return (
            self.object_type,
            self.kind,
            self.source,
            self.card,
            tuple(self.payload),
        )


@dataclass(frozen=True)
class RuntimePolicyView:
    base: PolicyView
    play_permissions: Tuple[PublicPlayPermissionView, ...] = ()
    pending_triggers: Tuple[PublicPendingTriggerView, ...] = ()
    pending_stack_objects: Tuple[PublicRuntimeStackObjectView, ...] = ()
    window_kind: str = "main_empty"

    def key(self) -> Tuple[object, ...]:
        return stable_key(
            (
                self.base.key(),
                tuple(permission.key() for permission in self.play_permissions),
                tuple(trigger.key() for trigger in self.pending_triggers),
                tuple(obj.key() for obj in self.pending_stack_objects),
                self.window_kind,
            ),
            version=RUNTIME_POLICY_VIEW_VERSION,
        )


def _stack_object_views(runtime_stack) -> Tuple[PublicRuntimeStackObjectView, ...]:
    if runtime_stack is None:
        return ()
    rows = []
    for obj in getattr(runtime_stack, "objects", ()):
        public_payload = getattr(obj, "public_payload", None)
        if public_payload is None:
            public_payload = getattr(obj, "payload", ())
        rows.append(
            PublicRuntimeStackObjectView(
                object_type=str(getattr(obj, "object_type", "trigger")),
                kind=str(getattr(obj, "kind", "")),
                source=str(getattr(obj, "source", "")),
                card=str(getattr(obj, "card", "")),
                payload=tuple(public_payload),
            )
        )
    return tuple(rows)


def make_runtime_policy_view(
    state,
    information: InformationState,
    *,
    permissions: UrzaPermissionState | None = None,
    trigger_stack: PendingTriggerStack | None = None,
    runtime_stack=None,
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

    stack_objects = _stack_object_views(runtime_stack)
    if runtime_stack is None:
        pending_triggers = tuple(
            PublicPendingTriggerView(
                trigger.kind,
                trigger.source,
                tuple(trigger.payload),
            )
            for trigger in trigger_stack.triggers
        )
    else:
        pending_triggers = tuple(
            PublicPendingTriggerView(obj.kind, obj.source, obj.payload)
            for obj in stack_objects
            if obj.object_type == "trigger"
        )

    return RuntimePolicyView(
        base=make_policy_view(state, information, caverns_live=caverns_live),
        play_permissions=play_permissions,
        pending_triggers=pending_triggers,
        pending_stack_objects=stack_objects,
        window_kind=window.kind,
    )
