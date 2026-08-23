#!/usr/bin/env python3
"""Urza exile-permission extension for free Reshape/Whir casts.

Casting a spell without paying its mana cost forces X=0. That does not erase
additional casting costs, so Urza-exiled Reshape must still sacrifice an artifact
while casting. Whir has no additional cost here and does not need an improvise
payment plan because its mana cost is not being paid.

The extension reuses the existing Phase-2 X-artifact spell/search stack kinds. In
particular, a Reshape sacrifice of Prized Statue or Sewer-veillance Cam happens as
a casting cost; those triggers wait until casting finishes, Cam chooses its target
before simultaneous controlled-trigger ordering, and all of them sit above the
Reshape spell. Hidden library targets remain absent until the X=0 spell resolves.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Tuple

import urza_solver as solver
import non_oracle_runtime as core
import non_oracle_urza_runtime as urza
from decision_observation import ActionIntent
from non_oracle_x_artifact_tutor_runtime import (
    SPELL_RESHAPE,
    SPELL_WHIR,
    _finish_cast_triggers,
    _remove_artifact_for_reshape_cost,
)
from x_artifact_search_adapter import (
    RESHAPE,
    WHIR,
    _artifact_slots,
    _slot_from_parameter,
    _slot_index,
)

USE_CAST_RESHAPE = "cast_reshape_x0"
USE_CAST_WHIR = "cast_whir_x0"
X_PERMISSION_USES = frozenset({USE_CAST_RESHAPE, USE_CAST_WHIR})

_INSTALLED = False
_ORIGINAL_MAIN_INTENTS = urza.urza_main_intents
_ORIGINAL_PRIORITY_INTENTS = urza.urza_priority_intents
_ORIGINAL_BEGIN_MAIN = urza.begin_urza_main_action
_ORIGINAL_BEGIN_PRIORITY = urza.begin_urza_priority_action


def _current_permissions(runtime):
    return urza._current_permissions(runtime)


def _timing_allows(runtime, card: str, *, priority: bool) -> bool:
    if not priority:
        return True
    return bool(solver._can_cast_card_at_priority(runtime.true_state, card))


def _bauble_count(state) -> int:
    return sum(1 for perm in state.battlefield if perm.name == "Vexing Bauble")


def _reshape_actions(runtime, permission, *, priority: bool) -> Tuple[ActionIntent, ...]:
    if permission.card != RESHAPE or not _timing_allows(runtime, RESHAPE, priority=priority):
        return ()
    state = runtime.true_state
    slots = _artifact_slots(state)
    if not slots:
        return ()
    prefix = "priority" if priority else "main"
    rows = []
    for serial, slot in enumerate(slots):
        index = _slot_index(state, slot)
        perm = state.battlefield[index]
        baubles_after_cost = _bauble_count(state) - (1 if perm.name == "Vexing Bauble" else 0)
        rows.append(ActionIntent(
            action_id=f"{prefix}.urza.permission.{permission.permission_id}.reshape.{serial:03d}",
            kind=urza.MAIN_USE_URZA_PERMISSION,
            parameters=(
                ("card", RESHAPE),
                ("mana_spent", 0),
                ("permission_id", permission.permission_id),
                ("priority", bool(priority)),
                ("sacrifice", slot.key()),
                ("sacrifice_name", perm.name or perm.mode),
                ("use", USE_CAST_RESHAPE),
                ("will_be_countered_by_own_bauble", baubles_after_cost > 0),
                ("x", 0),
            ),
            equivalence_key=(
                urza.MAIN_USE_URZA_PERMISSION,
                USE_CAST_RESHAPE,
                slot.key(),
                permission.expires_turn,
                bool(priority),
            ),
            label=f"Urza permission: cast Reshape X=0 free; sacrifice {perm.name or perm.mode}",
            decision_stage=urza._stage(priority),
            source=RESHAPE,
        ))
    return tuple(rows)


def _whir_actions(runtime, permission, *, priority: bool) -> Tuple[ActionIntent, ...]:
    if permission.card != WHIR or not _timing_allows(runtime, WHIR, priority=priority):
        return ()
    prefix = "priority" if priority else "main"
    return (ActionIntent(
        action_id=f"{prefix}.urza.permission.{permission.permission_id}.whir",
        kind=urza.MAIN_USE_URZA_PERMISSION,
        parameters=(
            ("card", WHIR),
            ("mana_spent", 0),
            ("permission_id", permission.permission_id),
            ("priority", bool(priority)),
            ("use", USE_CAST_WHIR),
            ("will_be_countered_by_own_bauble", _bauble_count(runtime.true_state) > 0),
            ("x", 0),
        ),
        equivalence_key=(
            urza.MAIN_USE_URZA_PERMISSION,
            USE_CAST_WHIR,
            permission.expires_turn,
            bool(priority),
        ),
        label="Urza permission: cast Whir of Invention free with X=0",
        decision_stage=urza._stage(priority),
        source=WHIR,
    ),)


def urza_x_permission_intents(runtime, *, priority: bool) -> Tuple[ActionIntent, ...]:
    rows = []
    for permission in _current_permissions(runtime):
        rows.extend(_reshape_actions(runtime, permission, priority=priority))
        rows.extend(_whir_actions(runtime, permission, priority=priority))
    return tuple(sorted(rows, key=lambda action: action.action_id))


def _remove_permission_card(runtime, *, permission_id: str, card: str):
    return urza._remove_exiled_permission_card(
        runtime,
        permission_id=permission_id,
        card=card,
    )


def _allocate_x_spell(runtime, *, card: str, kind: str):
    spell, stack = runtime.stack.allocate(
        object_type=core.STACK_SPELL,
        kind=kind,
        source="exile",
        card=card,
        payload=(("x", 0), ("mana_spent", 0)),
        public_payload=(("x", 0), ("mana_spent", 0)),
        strategic_payload=(("x", 0), ("mana_spent", 0)),
    )
    return spell, replace(runtime, stack=stack.push_existing((spell,)))


def _begin_reshape(runtime, params):
    state, permissions = _remove_permission_card(
        runtime,
        permission_id=str(params["permission_id"]),
        card=RESHAPE,
    )
    slot = _slot_from_parameter(tuple(params["sacrifice"]))
    index = _slot_index(state, slot)
    if not solver.is_artifact_perm(state.battlefield[index]):
        raise ValueError("Urza-Reshape sacrifice is no longer an artifact")
    state, sacrificed = _remove_artifact_for_reshape_cost(state, index)
    state = solver.add_trace(
        state,
        f"Phase2 Urza permission casts Reshape X=0 free; sacrifice {sacrificed.name or sacrificed.mode} as additional cost",
    )
    runtime = replace(
        runtime,
        true_state=solver._ensure_oracle_instance_tags(state),
        permissions=permissions,
    )
    spell, runtime = _allocate_x_spell(runtime, card=RESHAPE, kind=SPELL_RESHAPE)
    return _finish_cast_triggers(
        runtime,
        source=RESHAPE,
        spell=spell,
        mana_spent=0,
        prized_died=sacrificed.name == "Prized Statue",
        cam_died=sacrificed.name == "Sewer-veillance Cam",
    )


def _begin_whir(runtime, params):
    state, permissions = _remove_permission_card(
        runtime,
        permission_id=str(params["permission_id"]),
        card=WHIR,
    )
    state = solver.add_trace(
        state,
        "Phase2 Urza permission casts Whir of Invention free with X=0",
    )
    runtime = replace(runtime, true_state=state, permissions=permissions)
    spell, runtime = _allocate_x_spell(runtime, card=WHIR, kind=SPELL_WHIR)
    return _finish_cast_triggers(
        runtime,
        source=WHIR,
        spell=spell,
        mana_spent=0,
        prized_died=False,
        cam_died=False,
    )


def _is_x_permission_action(action: ActionIntent) -> bool:
    if action.kind != urza.MAIN_USE_URZA_PERMISSION:
        return False
    return str(dict(action.parameters).get("use", "")) in X_PERMISSION_USES


def begin_urza_x_permission_action(runtime, action: ActionIntent, *, priority: bool):
    legal = {
        candidate.canonical_key()
        for candidate in urza_x_permission_intents(runtime, priority=priority)
    }
    if action.canonical_key() not in legal:
        raise ValueError("Urza X-spell permission action is no longer legal")
    params = dict(action.parameters)
    use = str(params["use"])
    if use == USE_CAST_RESHAPE:
        return _begin_reshape(runtime, params)
    if use == USE_CAST_WHIR:
        return _begin_whir(runtime, params)
    raise ValueError(f"unsupported Urza X-spell permission use {use!r}")


def _patched_main_intents(runtime):
    return tuple(sorted(
        _ORIGINAL_MAIN_INTENTS(runtime) + urza_x_permission_intents(runtime, priority=False),
        key=lambda action: action.action_id,
    ))


def _patched_priority_intents(runtime):
    return tuple(sorted(
        _ORIGINAL_PRIORITY_INTENTS(runtime) + urza_x_permission_intents(runtime, priority=True),
        key=lambda action: action.action_id,
    ))


def _patched_begin_main(runtime, action):
    if _is_x_permission_action(action):
        return begin_urza_x_permission_action(runtime, action, priority=False)
    return _ORIGINAL_BEGIN_MAIN(runtime, action)


def _patched_begin_priority(runtime, action):
    if _is_x_permission_action(action):
        return begin_urza_x_permission_action(runtime, action, priority=True)
    return _ORIGINAL_BEGIN_PRIORITY(runtime, action)


def install_urza_x_permission_extension() -> None:
    """Layer X=0 permission casts on top of the installed Urza search extension."""
    global _INSTALLED
    if _INSTALLED:
        return
    urza.urza_main_intents = _patched_main_intents
    urza.urza_priority_intents = _patched_priority_intents
    urza.begin_urza_main_action = _patched_begin_main
    urza.begin_urza_priority_action = _patched_begin_priority
    _INSTALLED = True
