#!/usr/bin/env python3
"""Sewer-veillance Cam extension for the Phase-2 typed runtime.

Cam is timing-sensitive in two separate places:

* its ETB/LTB trigger chooses a target when the trigger is put on the stack;
* only when that targeted trigger resolves do we choose whether to tap or untap.

The core runtime predates this card-specific boundary.  Rather than letting the
Oracle shortcut choose a target, this module installs a narrow extension into the
runtime dispatch before the other Phase-2 adapters import it.  The extension keeps
all target selection policy-visible and uses only public permanent signatures.
Exact instance tags remain rules-side execution coordinates.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Dict, Iterable, Tuple

import urza_solver as solver
import non_oracle_runtime as core
from decision_observation import (
    ActionIntent,
    DECISION_MECHANICAL,
    DecisionRequest,
    PendingDecisionSpec,
    PolicyDecisionContext,
)
from non_oracle_runtime_value_key import (
    RuntimeDecisionWindow,
    WINDOW_POST_OBSERVATION,
    WINDOW_PRIORITY,
)

CAM = "Sewer-veillance Cam"
DECISION_CAM_TARGET = "runtime_cam_target"
DECISION_CAM_EFFECT = "runtime_cam_effect"
UNASSIGNED_KINDS = frozenset({"etb_cam_unassigned", "ltb_cam_unassigned"})
ASSIGNED_KINDS = frozenset({"etb_cam", "ltb_cam"})

_INSTALLED = False
_ORIGINAL_ARTIFACT_ENTRY_TRIGGER_OBJECTS = core._artifact_entry_trigger_objects
_ORIGINAL_QUEUE_SIMULTANEOUS_OBJECTS = core._queue_simultaneous_objects
_ORIGINAL_RUNTIME_DECISION_REQUEST = core.runtime_decision_request
_ORIGINAL_APPLY_PENDING_ACTION = core._apply_pending_action
_ORIGINAL_RESOLVE_RUNTIME_STACK_TOP = core._resolve_runtime_stack_top


def _public_signature(perm) -> Tuple[object, ...]:
    return core._perm_public_signature(perm)


def _creature_groups(state: solver.State) -> Dict[Tuple[object, ...], Tuple[object, ...]]:
    groups = {}
    for perm in state.battlefield:
        if not solver.is_creature_perm(perm):
            continue
        signature = _public_signature(perm)
        groups.setdefault(signature, []).append(perm)
    return {
        signature: tuple(sorted(perms, key=lambda p: int(p.instance_tag)))
        for signature, perms in groups.items()
    }


def _first_unassigned(objects):
    return next((obj for obj in objects if obj.kind in UNASSIGNED_KINDS), None)


def _target_actions(runtime: core.NonOracleRuntimeState, pending) -> Tuple[ActionIntent, ...]:
    groups = _creature_groups(runtime.true_state)
    rows = []
    for index, signature in enumerate(sorted(groups, key=repr)):
        name = str(signature[0]) if signature else "creature"
        rows.append(ActionIntent(
            action_id=f"runtime.cam.target.{index:03d}",
            kind=DECISION_CAM_TARGET,
            parameters=(("target_signature", signature),),
            equivalence_key=(DECISION_CAM_TARGET, signature),
            label=f"Cam target {name}",
            decision_stage=DECISION_MECHANICAL,
            source=CAM,
        ))
    return tuple(rows)


def _effect_actions(runtime: core.NonOracleRuntimeState, pending) -> Tuple[ActionIntent, ...]:
    obj = dict(pending.payload)["object"]
    params = dict(obj.payload)
    tag = int(params["target_tag"])
    idx = core._perm_index_for_tag(runtime.true_state, tag)
    if idx is None or not solver.is_creature_perm(runtime.true_state.battlefield[idx]):
        return ()
    target = runtime.true_state.battlefield[idx]
    rows = [ActionIntent(
        action_id=f"{obj.object_id}.cam.decline",
        kind=DECISION_CAM_EFFECT,
        parameters=(("choice", "decline"),),
        equivalence_key=(DECISION_CAM_EFFECT, "decline", obj.strategic_key()),
        label=f"Cam: leave {target.name or target.mode} unchanged",
        decision_stage=DECISION_MECHANICAL,
        source=CAM,
    )]
    choice = "untap" if target.tapped else "tap"
    rows.append(ActionIntent(
        action_id=f"{obj.object_id}.cam.{choice}",
        kind=DECISION_CAM_EFFECT,
        parameters=(("choice", choice),),
        equivalence_key=(DECISION_CAM_EFFECT, choice, obj.strategic_key()),
        label=f"Cam: {choice} {target.name or target.mode}",
        decision_stage=DECISION_MECHANICAL,
        source=CAM,
    ))
    return tuple(rows)


def _stage_target_assignment(
    runtime: core.NonOracleRuntimeState,
    objects: Tuple[core.RuntimeStackObject, ...],
    *,
    source: str,
) -> core.NonOracleRuntimeState:
    unassigned = _first_unassigned(objects)
    if unassigned is None:
        return _ORIGINAL_QUEUE_SIMULTANEOUS_OBJECTS(runtime, objects, source=source)

    groups = _creature_groups(runtime.true_state)
    if not groups:
        # A targeted trigger with no legal target is removed rather than stacked.
        remaining = tuple(obj for obj in objects if obj.object_id != unassigned.object_id)
        return _stage_target_assignment(runtime, remaining, source=source)

    spec = PendingDecisionSpec(
        decision_id=f"{unassigned.object_id}.cam.target",
        kind=DECISION_CAM_TARGET,
        source=CAM,
        decision_stage=DECISION_MECHANICAL,
        contingent_on=source,
    )
    return replace(
        runtime,
        pending=core.RuntimePendingDecision(
            spec=spec,
            kind=DECISION_CAM_TARGET,
            payload=(("objects", objects), ("source", source)),
        ),
        window=RuntimeDecisionWindow(WINDOW_POST_OBSERVATION),
    )


def _patched_queue_simultaneous_objects(runtime, objects, *, source):
    objects = tuple(objects)
    if any(obj.kind in UNASSIGNED_KINDS for obj in objects):
        return _stage_target_assignment(runtime, objects, source=source)
    return _ORIGINAL_QUEUE_SIMULTANEOUS_OBJECTS(runtime, objects, source=source)


def _patched_artifact_entry_trigger_objects(runtime, entered_cards):
    entered_cards = tuple(str(card) for card in entered_cards)
    cam_count = sum(card == CAM for card in entered_cards)
    if not cam_count:
        return _ORIGINAL_ARTIFACT_ENTRY_TRIGGER_OBJECTS(runtime, entered_cards)

    # A neutral placeholder preserves the number of artifacts in the entry event,
    # so Tezzeret/Station/Golem trigger counts stay exact without asking the old
    # helper to resolve Cam's target-selection shortcut.
    neutral_cards = tuple("__PHASE2_CAM_ENTRY__" if card == CAM else card for card in entered_cards)
    objects, stack = _ORIGINAL_ARTIFACT_ENTRY_TRIGGER_OBJECTS(runtime, neutral_cards)
    entry_label = " + ".join(entered_cards)
    objects = tuple(
        replace(obj, card=entry_label)
        if obj.kind in {"etb_tezz", "etb_producer"}
        else obj
        for obj in objects
    )

    rows = list(objects)
    for _ in range(cam_count):
        obj, stack = core._alloc_trigger(
            stack,
            kind="etb_cam_unassigned",
            source=CAM,
            card=CAM,
            public_payload=(("event", "ETB"),),
        )
        rows.append(obj)
    return tuple(rows), stack


def queue_cam_ltb(
    runtime: core.NonOracleRuntimeState,
    *,
    extra_objects: Iterable[core.RuntimeStackObject] = (),
    count: int = 1,
    source: str = "Cam leaves battlefield",
) -> core.NonOracleRuntimeState:
    """Queue one or more Cam LTB triggers with target choice before stack order."""
    stack = runtime.stack
    objects = list(extra_objects)
    for _ in range(max(0, int(count))):
        obj, stack = core._alloc_trigger(
            stack,
            kind="ltb_cam_unassigned",
            source=CAM,
            card=CAM,
            public_payload=(("event", "LTB"),),
        )
        objects.append(obj)
    runtime = replace(runtime, stack=stack)
    return _patched_queue_simultaneous_objects(runtime, tuple(objects), source=source)


def _patched_runtime_decision_request(
    runtime,
    *,
    horizon,
    objective="win_by_horizon",
    policy_id="base-v1",
    caverns_live=None,
):
    pending = runtime.pending
    if pending is not None and pending.kind in {DECISION_CAM_TARGET, DECISION_CAM_EFFECT}:
        actions = (
            _target_actions(runtime, pending)
            if pending.kind == DECISION_CAM_TARGET
            else _effect_actions(runtime, pending)
        )
        return DecisionRequest(
            observation=runtime.policy_view(caverns_live=caverns_live),
            actions=actions,
            context=PolicyDecisionContext(
                horizon=horizon,
                objective=objective,
                policy_id=policy_id,
                decision_id=pending.spec.decision_id,
                decision_stage=pending.spec.decision_stage,
            ),
        )
    return _ORIGINAL_RUNTIME_DECISION_REQUEST(
        runtime,
        horizon=horizon,
        objective=objective,
        policy_id=policy_id,
        caverns_live=caverns_live,
    )


def _apply_target_assignment(runtime, action):
    pending = runtime.pending
    request = _patched_runtime_decision_request(
        runtime,
        horizon=max(1, int(runtime.true_state.turn)),
        objective="win_by_horizon",
        policy_id="runtime",
    )
    legal = {candidate.canonical_key() for candidate in request.actions}
    if action.canonical_key() not in legal:
        raise ValueError("Cam target is not legal in the current public battlefield")

    data = dict(pending.payload)
    objects = tuple(data["objects"])
    source = str(data["source"])
    unassigned = _first_unassigned(objects)
    if unassigned is None:
        raise ValueError("Cam target decision has no unassigned trigger")

    signature = tuple(dict(action.parameters)["target_signature"])
    groups = _creature_groups(runtime.true_state)
    candidates = groups.get(signature, ())
    if not candidates:
        raise ValueError("chosen Cam target is no longer legal")
    target = candidates[0]
    assigned_kind = "etb_cam" if unassigned.kind.startswith("etb_") else "ltb_cam"
    assigned = replace(
        unassigned,
        kind=assigned_kind,
        payload=(("target_tag", int(target.instance_tag)),),
        public_payload=(("target_state", signature),),
        strategic_payload=(("target_state", signature),),
    )
    replaced_objects = tuple(
        assigned if obj.object_id == unassigned.object_id else obj
        for obj in objects
    )
    runtime = replace(runtime, pending=None)
    return _stage_target_assignment(runtime, replaced_objects, source=source)


def _apply_effect(runtime, action):
    pending = runtime.pending
    request = _patched_runtime_decision_request(
        runtime,
        horizon=max(1, int(runtime.true_state.turn)),
        objective="win_by_horizon",
        policy_id="runtime",
    )
    legal = {candidate.canonical_key() for candidate in request.actions}
    if action.canonical_key() not in legal:
        raise ValueError("Cam tap/untap choice is no longer legal")
    obj = dict(pending.payload)["object"]
    tag = int(dict(obj.payload)["target_tag"])
    idx = core._perm_index_for_tag(runtime.true_state, tag)
    state = runtime.true_state
    choice = str(dict(action.parameters)["choice"])
    if idx is not None and solver.is_creature_perm(state.battlefield[idx]):
        target = state.battlefield[idx]
        if choice == "tap" and not target.tapped:
            state = solver.update_perm(state, idx, tapped=True)
        elif choice == "untap" and target.tapped:
            state = solver.update_perm(state, idx, tapped=False)
        elif choice != "decline":
            raise ValueError("Cam effect choice no longer matches target state")
        state = solver.add_trace(
            state,
            f"Phase2 Cam {obj.kind}: {choice} {target.name or target.mode}",
        )
    state = solver.check_win(state)
    return replace(
        runtime,
        true_state=state,
        pending=None,
        window=RuntimeDecisionWindow(WINDOW_PRIORITY),
    )


def _patched_apply_pending_action(runtime, action):
    if runtime.pending is not None:
        if runtime.pending.kind == DECISION_CAM_TARGET:
            return _apply_target_assignment(runtime, action)
        if runtime.pending.kind == DECISION_CAM_EFFECT:
            return _apply_effect(runtime, action)
    return _ORIGINAL_APPLY_PENDING_ACTION(runtime, action)


def _patched_resolve_runtime_stack_top(runtime):
    top = runtime.stack.top()
    if top is None or top.kind not in ASSIGNED_KINDS:
        return _ORIGINAL_RESOLVE_RUNTIME_STACK_TOP(runtime)

    obj, remaining = runtime.stack.pop_top()
    runtime = replace(runtime, stack=remaining)
    tag = int(dict(obj.payload)["target_tag"])
    idx = core._perm_index_for_tag(runtime.true_state, tag)
    if idx is None or not solver.is_creature_perm(runtime.true_state.battlefield[idx]):
        state = solver.add_trace(runtime.true_state, f"Phase2 Cam {obj.kind}: target absent")
        return replace(
            runtime,
            true_state=state,
            window=RuntimeDecisionWindow(WINDOW_PRIORITY),
        )

    spec = PendingDecisionSpec(
        decision_id=f"{obj.object_id}.cam.effect",
        kind=DECISION_CAM_EFFECT,
        source=CAM,
        decision_stage=DECISION_MECHANICAL,
        contingent_on=obj.object_id,
    )
    return replace(
        runtime,
        pending=core.RuntimePendingDecision(
            spec=spec,
            kind=DECISION_CAM_EFFECT,
            payload=(("object", obj),),
        ),
        window=RuntimeDecisionWindow(WINDOW_POST_OBSERVATION),
    )


def install_cam_runtime_extension() -> None:
    """Install the Cam dispatch exactly once before other Phase-2 adapters import."""
    global _INSTALLED
    if _INSTALLED:
        return
    core._artifact_entry_trigger_objects = _patched_artifact_entry_trigger_objects
    core._queue_simultaneous_objects = _patched_queue_simultaneous_objects
    core.runtime_decision_request = _patched_runtime_decision_request
    core._apply_pending_action = _patched_apply_pending_action
    core._resolve_runtime_stack_top = _patched_resolve_runtime_stack_top
    _INSTALLED = True
