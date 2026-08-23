#!/usr/bin/env python3
"""Urza exile-permission extension for typed tutor/search spells.

The core Urza runtime owns the persistent permission resource and already supports
lands, artifacts, proactive nonartifact spells, Probe, and priority-time spins.
This narrow extension adds the search spells whose resolutions are already modeled
by the Phase-2 tutor/search adapters. It deliberately reuses those existing stack
object kinds, so hidden library targets do not become policy-visible until the
corresponding spell or Spellseeker ETB actually resolves.

Covered permission casts:
- Mystical Tutor, Merchant Scroll, and Spellseeker;
- Transmute Artifact as a free spell cast (not the unrelated transmute ability);
- Scour for Scrap with modes/graveyard target committed on cast.

Dizzy Spell and Muddle the Mixture are not included: their useful tutor route is
transmute, which requires discarding the card from hand and therefore cannot be
activated from exile. Reshape/Whir are kept for the next X-spell slice because
casting without paying the mana cost fixes X=0 and Reshape still has an additional
artifact-sacrifice cost that must be staged separately.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Tuple

import urza_solver as solver
import non_oracle_runtime as core
import non_oracle_urza_runtime as urza
from decision_observation import ActionIntent, apply_observation_batch
from non_oracle_remaining_search_runtime import SPELL_SCOUR
from non_oracle_simple_tutor_runtime import (
    SPELLSEEKER_SPELL,
    SPELL_SIMPLE_TUTOR,
    TUTOR_CONFIG,
)
from non_oracle_transmute_runtime import SPELL_TRANSMUTE
from remaining_search_adapters import SCOUR
from trigger_order_adapter import post_cast_observations

USE_CAST_SIMPLE_TUTOR = "cast_simple_tutor"
USE_CAST_TRANSMUTE_ARTIFACT = "cast_transmute_artifact"
USE_CAST_SCOUR = "cast_scour_for_scrap"
SEARCH_PERMISSION_USES = frozenset({
    USE_CAST_SIMPLE_TUTOR,
    USE_CAST_TRANSMUTE_ARTIFACT,
    USE_CAST_SCOUR,
})

SIMPLE_PERMISSION_TUTORS = frozenset({
    "Mystical Tutor",
    "Merchant Scroll",
    "Spellseeker",
})
TRANSMUTE_ARTIFACT = "Transmute Artifact"

_INSTALLED = False
_ORIGINAL_MAIN_INTENTS = urza.urza_main_intents
_ORIGINAL_PRIORITY_INTENTS = urza.urza_priority_intents
_ORIGINAL_BEGIN_MAIN = urza.begin_urza_main_action
_ORIGINAL_BEGIN_PRIORITY = urza.begin_urza_priority_action


def _current_permissions(runtime: core.NonOracleRuntimeState):
    return urza._current_permissions(runtime)


def _timing_allows(runtime: core.NonOracleRuntimeState, card: str, *, priority: bool) -> bool:
    if not priority:
        return True
    return bool(solver._can_cast_card_at_priority(runtime.true_state, card))


def _countered_by_own_bauble(state, mana_spent: int = 0) -> bool:
    return bool(solver.has(state, "Vexing Bauble") and int(mana_spent) == 0)


def _simple_tutor_permission_action(runtime, permission, *, priority: bool):
    card = permission.card
    if card not in SIMPLE_PERMISSION_TUTORS or not _timing_allows(runtime, card, priority=priority):
        return ()
    search_kind, _generic, _blue, mode, result_zone = TUTOR_CONFIG[card]
    prefix = "priority" if priority else "main"
    return (ActionIntent(
        action_id=f"{prefix}.urza.permission.{permission.permission_id}.search.{card}",
        kind=urza.MAIN_USE_URZA_PERMISSION,
        parameters=(
            ("card", card),
            ("mana_spent", 0),
            ("mode", mode),
            ("permission_id", permission.permission_id),
            ("priority", bool(priority)),
            ("result_zone", result_zone),
            ("search_kind", search_kind),
            ("use", USE_CAST_SIMPLE_TUTOR),
            ("will_be_countered_by_own_bauble", _countered_by_own_bauble(runtime.true_state)),
        ),
        equivalence_key=(
            urza.MAIN_USE_URZA_PERMISSION,
            USE_CAST_SIMPLE_TUTOR,
            card,
            mode,
            result_zone,
            permission.expires_turn,
            bool(priority),
        ),
        label=f"Urza permission: cast {card} free",
        decision_stage=urza._stage(priority),
        source=card,
    ),)


def _transmute_permission_action(runtime, permission, *, priority: bool):
    if permission.card != TRANSMUTE_ARTIFACT:
        return ()
    if not _timing_allows(runtime, TRANSMUTE_ARTIFACT, priority=priority):
        return ()
    # The spell itself is legal without an artifact to sacrifice, but that line
    # cannot advance this goldfish objective and the hand-cast Phase-2 adapter
    # already omits the same dominated dead action.
    if not any(solver.is_artifact_perm(p) for p in runtime.true_state.battlefield):
        return ()
    prefix = "priority" if priority else "main"
    return (ActionIntent(
        action_id=f"{prefix}.urza.permission.{permission.permission_id}.transmute_artifact",
        kind=urza.MAIN_USE_URZA_PERMISSION,
        parameters=(
            ("card", TRANSMUTE_ARTIFACT),
            ("mana_spent", 0),
            ("permission_id", permission.permission_id),
            ("priority", bool(priority)),
            ("use", USE_CAST_TRANSMUTE_ARTIFACT),
            ("will_be_countered_by_own_bauble", _countered_by_own_bauble(runtime.true_state)),
        ),
        equivalence_key=(
            urza.MAIN_USE_URZA_PERMISSION,
            USE_CAST_TRANSMUTE_ARTIFACT,
            permission.expires_turn,
            bool(priority),
        ),
        label="Urza permission: cast Transmute Artifact free",
        decision_stage=urza._stage(priority),
        source=TRANSMUTE_ARTIFACT,
    ),)


def _scour_permission_actions(runtime, permission, *, priority: bool):
    if permission.card != SCOUR or not _timing_allows(runtime, SCOUR, priority=priority):
        return ()
    gy_artifacts = tuple(sorted(set(runtime.true_state.graveyard) & solver.ARTIFACTS))
    choices = [("library", "")]
    for card in gy_artifacts:
        choices.append(("graveyard", card))
        choices.append(("both", card))
    prefix = "priority" if priority else "main"
    rows = []
    for index, (mode, graveyard_target) in enumerate(choices):
        rows.append(ActionIntent(
            action_id=f"{prefix}.urza.permission.{permission.permission_id}.scour.{index:02d}",
            kind=urza.MAIN_USE_URZA_PERMISSION,
            parameters=(
                ("card", SCOUR),
                ("graveyard_target", graveyard_target),
                ("mana_spent", 0),
                ("mode", mode),
                ("permission_id", permission.permission_id),
                ("priority", bool(priority)),
                ("use", USE_CAST_SCOUR),
                ("will_be_countered_by_own_bauble", _countered_by_own_bauble(runtime.true_state)),
            ),
            equivalence_key=(
                urza.MAIN_USE_URZA_PERMISSION,
                USE_CAST_SCOUR,
                mode,
                graveyard_target,
                permission.expires_turn,
                bool(priority),
            ),
            label=(
                f"Urza permission: cast Scour free ({mode})"
                + (f" targeting {graveyard_target}" if graveyard_target else "")
            ),
            decision_stage=urza._stage(priority),
            source=SCOUR,
        ))
    return tuple(rows)


def urza_search_permission_intents(
    runtime: core.NonOracleRuntimeState,
    *,
    priority: bool,
) -> Tuple[ActionIntent, ...]:
    rows = []
    for permission in _current_permissions(runtime):
        rows.extend(_simple_tutor_permission_action(runtime, permission, priority=priority))
        rows.extend(_transmute_permission_action(runtime, permission, priority=priority))
        rows.extend(_scour_permission_actions(runtime, permission, priority=priority))
    return tuple(sorted(rows, key=lambda action: action.action_id))


def _remove_permission_card(runtime, *, permission_id: str, card: str):
    return urza._remove_exiled_permission_card(
        runtime,
        permission_id=permission_id,
        card=card,
    )


def _queue_free_spell(
    runtime: core.NonOracleRuntimeState,
    *,
    card: str,
    spell_kind: str,
    payload=(),
    public_payload=(),
) -> core.NonOracleRuntimeState:
    spell, stack = runtime.stack.allocate(
        object_type=core.STACK_SPELL,
        kind=spell_kind,
        source="exile",
        card=card,
        payload=tuple(payload),
        public_payload=tuple(public_payload),
        strategic_payload=tuple(public_payload),
    )
    runtime = replace(runtime, stack=stack.push_existing((spell,)))
    info = apply_observation_batch(
        runtime.information,
        post_cast_observations(runtime.true_state, card, cast_from_library_top=False),
    )
    runtime = replace(runtime, information=info)
    triggers, allocated = core._cast_trigger_objects(runtime, card, 0, spell.object_id)
    runtime = replace(runtime, stack=allocated)
    return core._queue_simultaneous_objects(
        runtime,
        triggers,
        source=f"Urza permission cast {card}",
    )


def _begin_simple_tutor_permission(runtime, params):
    card = str(params["card"])
    if card not in SIMPLE_PERMISSION_TUTORS:
        raise ValueError("not an Urza simple-tutor permission card")
    state, permissions = _remove_permission_card(
        runtime,
        permission_id=str(params["permission_id"]),
        card=card,
    )
    state = solver.add_trace(state, f"Phase2 Urza permission casts {card} free from exile")
    runtime = replace(runtime, true_state=state, permissions=permissions)
    mode = str(params["mode"])
    spell_kind = SPELLSEEKER_SPELL if mode == "spellseeker" else SPELL_SIMPLE_TUTOR
    payload = (
        ("search_kind", str(params["search_kind"])),
        ("result_zone", str(params["result_zone"])),
        ("mana_spent", 0),
    )
    public = (
        ("search_kind", str(params["search_kind"])),
        ("result_zone", str(params["result_zone"])),
    )
    return _queue_free_spell(
        runtime,
        card=card,
        spell_kind=spell_kind,
        payload=payload,
        public_payload=public,
    )


def _begin_transmute_permission(runtime, params):
    state, permissions = _remove_permission_card(
        runtime,
        permission_id=str(params["permission_id"]),
        card=TRANSMUTE_ARTIFACT,
    )
    state = solver.add_trace(
        state,
        "Phase2 Urza permission casts Transmute Artifact free from exile",
    )
    runtime = replace(runtime, true_state=state, permissions=permissions)
    return _queue_free_spell(
        runtime,
        card=TRANSMUTE_ARTIFACT,
        spell_kind=SPELL_TRANSMUTE,
        payload=(("mana_spent", 0),),
        public_payload=(("mana_spent", 0),),
    )


def _begin_scour_permission(runtime, params):
    mode = str(params["mode"])
    graveyard_target = str(params["graveyard_target"])
    if mode not in {"library", "graveyard", "both"}:
        raise ValueError("invalid Scour mode")
    if mode in {"graveyard", "both"} and graveyard_target not in runtime.true_state.graveyard:
        raise ValueError("Scour graveyard target is no longer present")
    state, permissions = _remove_permission_card(
        runtime,
        permission_id=str(params["permission_id"]),
        card=SCOUR,
    )
    state = solver.add_trace(
        state,
        f"Phase2 Urza permission casts Scour free from exile; mode={mode}"
        + (f"; grave target={graveyard_target}" if graveyard_target else ""),
    )
    runtime = replace(runtime, true_state=state, permissions=permissions)
    payload = (
        ("graveyard_target", graveyard_target),
        ("mana_spent", 0),
        ("mode", mode),
    )
    public = (
        ("graveyard_target", graveyard_target),
        ("mode", mode),
    )
    return _queue_free_spell(
        runtime,
        card=SCOUR,
        spell_kind=SPELL_SCOUR,
        payload=payload,
        public_payload=public,
    )


def _is_search_permission_action(action: ActionIntent) -> bool:
    if action.kind != urza.MAIN_USE_URZA_PERMISSION:
        return False
    return str(dict(action.parameters).get("use", "")) in SEARCH_PERMISSION_USES


def begin_urza_search_permission_action(
    runtime: core.NonOracleRuntimeState,
    action: ActionIntent,
    *,
    priority: bool,
) -> core.NonOracleRuntimeState:
    legal = {
        candidate.canonical_key()
        for candidate in urza_search_permission_intents(runtime, priority=priority)
    }
    if action.canonical_key() not in legal:
        raise ValueError("Urza search permission action is no longer legal")
    params = dict(action.parameters)
    use = str(params["use"])
    if use == USE_CAST_SIMPLE_TUTOR:
        return _begin_simple_tutor_permission(runtime, params)
    if use == USE_CAST_TRANSMUTE_ARTIFACT:
        return _begin_transmute_permission(runtime, params)
    if use == USE_CAST_SCOUR:
        return _begin_scour_permission(runtime, params)
    raise ValueError(f"unsupported Urza search permission use {use!r}")


def _patched_main_intents(runtime):
    return tuple(sorted(
        _ORIGINAL_MAIN_INTENTS(runtime)
        + urza_search_permission_intents(runtime, priority=False),
        key=lambda action: action.action_id,
    ))


def _patched_priority_intents(runtime):
    return tuple(sorted(
        _ORIGINAL_PRIORITY_INTENTS(runtime)
        + urza_search_permission_intents(runtime, priority=True),
        key=lambda action: action.action_id,
    ))


def _patched_begin_main(runtime, action):
    if _is_search_permission_action(action):
        return begin_urza_search_permission_action(runtime, action, priority=False)
    return _ORIGINAL_BEGIN_MAIN(runtime, action)


def _patched_begin_priority(runtime, action):
    if _is_search_permission_action(action):
        return begin_urza_search_permission_action(runtime, action, priority=True)
    return _ORIGINAL_BEGIN_PRIORITY(runtime, action)


def install_urza_search_permission_extension() -> None:
    """Install the search-permission family before the rules adapter imports Urza."""
    global _INSTALLED
    if _INSTALLED:
        return
    urza.urza_main_intents = _patched_main_intents
    urza.urza_priority_intents = _patched_priority_intents
    urza.begin_urza_main_action = _patched_begin_main
    urza.begin_urza_priority_action = _patched_begin_priority
    _INSTALLED = True
