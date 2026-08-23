#!/usr/bin/env python3
"""Phase-2 Urza spin and persistent permission runtime.

Urza's {5} activation is a real stack object. The policy commits and pays before
any random card is known; only resolution shuffles the library, exiles the new top
card, emits typed public observations, and grants a persistent permission lasting
until end of turn. Because this is an activated ability, the spin is available both
in an empty main phase and while holding priority over another stack object.

Permission coverage in this slice:
- land plays in an empty main phase;
- artifact spells for free, including Chalice multikicker and Mox Diamond entry;
- already-typed proactive nonartifact spells for free, preserving public targets;
- Gitaxian Probe for free;
- priority-time casts only when normal timing permits (native instant/flash or
  Valley Floodcaller granting flash to noncreature spells).

Search/tutor permission casts are intentionally a separate follow-up slice because
their post-resolution observation boundaries require their staged search adapters.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Tuple

import urza_solver as solver
import non_oracle_runtime as core
from decision_observation import (
    ActionIntent,
    DECISION_COMMIT,
    DECISION_MECHANICAL,
    ObservationBatch,
    PublicZoneChangeObservation,
    ShuffleObservation,
    apply_observation_batch,
)
from non_oracle_draw_engine_runtime import PROBE, SPELL_PROBE
from non_oracle_proactive_spell_adapter import (
    KNUCK_SPELLS,
    SUPPORTED_PROACTIVE,
    _knack_targets,
    _power_artifact_targets,
    _spell_kind,
    _target_from_signature,
)
from non_oracle_runtime_value_key import RuntimeDecisionWindow, WINDOW_PRIORITY
from non_oracle_turn_engine import _refresh_continuous_top
from non_oracle_utility_artifact_runtime import (
    CHALICE,
    MOX_DIAMOND,
    UTILITY_ARTIFACT_SPELL,
)
from trigger_order_adapter import post_cast_observations
from urza_permission_adapter import validate_urza_permissions_against_state

MAIN_ACTIVATE_URZA_SPIN = "main_activate_urza_spin"
MAIN_USE_URZA_PERMISSION = "main_use_urza_permission"
ACT_URZA_SPIN = "activated_urza_spin"

USE_PLAY_LAND = "play_land"
USE_CAST_ARTIFACT = "cast_artifact"
USE_CAST_PROACTIVE = "cast_proactive_nonartifact"
USE_CAST_PROBE = "cast_gitaxian_probe"


def _current_permissions(runtime: core.NonOracleRuntimeState):
    turn = int(runtime.true_state.turn)
    return tuple(
        permission
        for permission in runtime.permissions.permissions
        if permission.created_turn <= turn <= permission.expires_turn
        and permission.card in runtime.true_state.exile
    )


def _stage(priority: bool) -> str:
    return DECISION_MECHANICAL if priority else DECISION_COMMIT


def _spin_intents(
    runtime: core.NonOracleRuntimeState,
    *,
    priority: bool = False,
) -> Tuple[ActionIntent, ...]:
    state = runtime.true_state
    if not state.urza or not state.library or not solver.can_pay(state, 5, 0):
        return ()
    if priority and (runtime.pending is not None or not runtime.stack.objects or runtime.window.kind != WINDOW_PRIORITY):
        return ()
    prefix = "priority" if priority else "main"
    return (ActionIntent(
        action_id=f"{prefix}.urza.spin",
        kind=MAIN_ACTIVATE_URZA_SPIN,
        parameters=(("generic_cost", 5), ("priority", bool(priority))),
        equivalence_key=(MAIN_ACTIVATE_URZA_SPIN, bool(priority)),
        label="Urza: pay 5, shuffle, exile top card",
        decision_stage=_stage(priority),
        source=solver.COMMANDER,
    ),)


def _permission_land_action(permission) -> ActionIntent:
    return ActionIntent(
        action_id=f"main.urza.permission.{permission.permission_id}.land",
        kind=MAIN_USE_URZA_PERMISSION,
        parameters=(
            ("card", permission.card),
            ("kicks", 0),
            ("permission_id", permission.permission_id),
            ("priority", False),
            ("use", USE_PLAY_LAND),
        ),
        equivalence_key=(
            MAIN_USE_URZA_PERMISSION,
            USE_PLAY_LAND,
            permission.card,
            permission.expires_turn,
        ),
        label=f"Urza permission: play {permission.card} as land",
        decision_stage=DECISION_COMMIT,
        source=solver.COMMANDER,
    )


def _permission_artifact_actions(
    runtime,
    permission,
    *,
    priority: bool = False,
) -> Tuple[ActionIntent, ...]:
    state = runtime.true_state
    card = permission.card
    if card not in solver.ARTIFACTS or card in solver.TRUE_LAND_CARDS:
        return ()
    if priority and not solver._can_cast_card_at_priority(state, card):
        return ()

    kicks = (0,)
    if card == CHALICE:
        max_k = min(8, max(0, (int(state.blue) + int(state.colorless)) // 2))
        kicks = tuple(range(max_k + 1))

    prefix = "priority" if priority else "main"
    rows = []
    for kick_count in kicks:
        additional = 2 * int(kick_count) if card == CHALICE else 0
        if additional and not solver.can_pay(state, additional, 0):
            continue
        rows.append(ActionIntent(
            action_id=f"{prefix}.urza.permission.{permission.permission_id}.artifact.k{kick_count}",
            kind=MAIN_USE_URZA_PERMISSION,
            parameters=(
                ("card", card),
                ("kicks", int(kick_count)),
                ("mana_spent", int(additional)),
                ("permission_id", permission.permission_id),
                ("priority", bool(priority)),
                ("use", USE_CAST_ARTIFACT),
            ),
            equivalence_key=(
                MAIN_USE_URZA_PERMISSION,
                USE_CAST_ARTIFACT,
                card,
                int(kick_count),
                permission.expires_turn,
                bool(priority),
            ),
            label=(
                f"Urza permission: cast {card} free"
                + (f"; multikicker {kick_count}" if card == CHALICE else "")
            ),
            decision_stage=_stage(priority),
            source=card,
        ))
    return tuple(rows)


def _permission_proactive_actions(
    runtime,
    permission,
    *,
    priority: bool = False,
) -> Tuple[ActionIntent, ...]:
    state = runtime.true_state
    card = permission.card
    if card not in SUPPORTED_PROACTIVE:
        return ()
    if priority and not solver._can_cast_card_at_priority(state, card):
        return ()
    if card == "Power Artifact":
        targets = _power_artifact_targets(state)
    elif card in KNUCK_SPELLS:
        targets = _knack_targets(state)
    else:
        targets = (None,)

    prefix = "priority" if priority else "main"
    rows = []
    for index, target in enumerate(targets):
        signature = () if target is None else core._perm_public_signature(target)
        target_label = "" if target is None else f" -> {target.name or target.mode}"
        rows.append(ActionIntent(
            action_id=f"{prefix}.urza.permission.{permission.permission_id}.proactive.{index:02d}",
            kind=MAIN_USE_URZA_PERMISSION,
            parameters=(
                ("card", card),
                ("mana_spent", 0),
                ("permission_id", permission.permission_id),
                ("priority", bool(priority)),
                ("target_signature", signature),
                ("use", USE_CAST_PROACTIVE),
            ),
            equivalence_key=(
                MAIN_USE_URZA_PERMISSION,
                USE_CAST_PROACTIVE,
                card,
                signature,
                permission.expires_turn,
                bool(priority),
            ),
            label=f"Urza permission: cast {card} free{target_label}",
            decision_stage=_stage(priority),
            source=card,
        ))
    return tuple(rows)


def _permission_probe_actions(runtime, permission, *, priority: bool = False) -> Tuple[ActionIntent, ...]:
    if permission.card != PROBE:
        return ()
    if priority and not solver._can_cast_card_at_priority(runtime.true_state, PROBE):
        return ()
    prefix = "priority" if priority else "main"
    countered = bool(solver.has(runtime.true_state, "Vexing Bauble"))
    return (ActionIntent(
        action_id=f"{prefix}.urza.permission.{permission.permission_id}.probe",
        kind=MAIN_USE_URZA_PERMISSION,
        parameters=(
            ("card", PROBE),
            ("mana_spent", 0),
            ("permission_id", permission.permission_id),
            ("priority", bool(priority)),
            ("use", USE_CAST_PROBE),
            ("will_be_countered_by_own_bauble", countered),
        ),
        equivalence_key=(
            MAIN_USE_URZA_PERMISSION,
            USE_CAST_PROBE,
            permission.expires_turn,
            countered,
            bool(priority),
        ),
        label="Urza permission: cast Gitaxian Probe free",
        decision_stage=_stage(priority),
        source=PROBE,
    ),)


def urza_main_intents(runtime: core.NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    state = runtime.true_state
    rows = list(_spin_intents(runtime, priority=False))
    validate_urza_permissions_against_state(state, runtime.permissions)
    for permission in _current_permissions(runtime):
        card = permission.card
        if card in solver.ALL_LANDS and not state.land_played:
            rows.append(_permission_land_action(permission))
        rows.extend(_permission_artifact_actions(runtime, permission, priority=False))
        rows.extend(_permission_proactive_actions(runtime, permission, priority=False))
        rows.extend(_permission_probe_actions(runtime, permission, priority=False))
    return tuple(sorted(rows, key=lambda action: action.action_id))


def urza_priority_intents(runtime: core.NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    if runtime.pending is not None or not runtime.stack.objects or runtime.window.kind != WINDOW_PRIORITY:
        return ()
    state = runtime.true_state
    rows = list(_spin_intents(runtime, priority=True))
    validate_urza_permissions_against_state(state, runtime.permissions)
    for permission in _current_permissions(runtime):
        rows.extend(_permission_artifact_actions(runtime, permission, priority=True))
        rows.extend(_permission_proactive_actions(runtime, permission, priority=True))
        rows.extend(_permission_probe_actions(runtime, permission, priority=True))
    return tuple(sorted(rows, key=lambda action: action.action_id))


def _permission_by_id(runtime: core.NonOracleRuntimeState, permission_id: str):
    for permission in runtime.permissions.permissions:
        if permission.permission_id == str(permission_id):
            return permission
    return None


def _begin_spin(runtime: core.NonOracleRuntimeState, action: ActionIntent) -> core.NonOracleRuntimeState:
    priority = bool(dict(action.parameters).get("priority", False))
    legal = {candidate.canonical_key() for candidate in _spin_intents(runtime, priority=priority)}
    if action.canonical_key() not in legal:
        raise ValueError("Urza spin activation is no longer legal")
    paid = solver.pay(runtime.true_state, 5, 0)
    if paid is None:
        raise ValueError("Urza spin activation cost can no longer be paid")
    paid = solver.add_trace(paid, "Phase2 activate Urza spin: pay {5}")
    obj, stack = runtime.stack.allocate(
        object_type=core.STACK_TRIGGER,
        kind=ACT_URZA_SPIN,
        source=solver.COMMANDER,
        card=solver.COMMANDER,
        public_payload=(("generic_cost", 5),),
        strategic_payload=(("generic_cost", 5),),
    )
    return replace(
        runtime,
        true_state=paid,
        stack=stack.push_existing((obj,)),
        window=RuntimeDecisionWindow(WINDOW_PRIORITY),
    )


def _begin_special_permission_artifact(
    runtime: core.NonOracleRuntimeState,
    *,
    permission_id: str,
    card: str,
    kicks: int,
    mana_spent: int,
) -> core.NonOracleRuntimeState:
    state = runtime.true_state
    permission = _permission_by_id(runtime, permission_id)
    if permission is None or permission.card != card or card not in state.exile:
        raise ValueError("Urza artifact permission is no longer live")
    paid = solver.pay(state, int(mana_spent), 0)
    if paid is None:
        raise ValueError("Urza permission additional cost can no longer be paid")
    exile = list(paid.exile)
    exile.remove(card)
    state = replace(paid, exile=tuple(exile), spell_cast_this_turn=True)
    permissions = runtime.permissions.consume(permission_id)
    validate_urza_permissions_against_state(state, permissions)
    runtime = replace(runtime, true_state=state, permissions=permissions)

    spell, stack = runtime.stack.allocate(
        object_type=core.STACK_SPELL,
        kind=UTILITY_ARTIFACT_SPELL,
        source="exile",
        card=card,
        payload=(("kicks", int(kicks)), ("mana_spent", int(mana_spent))),
        public_payload=(("kicks", int(kicks)), ("mana_spent", int(mana_spent))),
        strategic_payload=(("kicks", int(kicks)), ("mana_spent", int(mana_spent))),
    )
    runtime = replace(runtime, stack=stack.push_existing((spell,)))
    info = apply_observation_batch(
        runtime.information,
        post_cast_observations(state, card, cast_from_library_top=False),
    )
    runtime = replace(runtime, information=info)
    triggers, allocated = core._cast_trigger_objects(runtime, card, int(mana_spent), spell.object_id)
    runtime = replace(runtime, stack=allocated)
    return core._queue_simultaneous_objects(runtime, triggers, source=f"Urza permission cast {card}")


def _use_land_permission(runtime, *, permission_id: str, card: str) -> core.NonOracleRuntimeState:
    state = runtime.true_state
    permission = _permission_by_id(runtime, permission_id)
    if permission is None or permission.card != card or card not in state.exile:
        raise ValueError("Urza land permission is no longer live")
    if state.land_played or card not in solver.ALL_LANDS:
        raise ValueError("Urza-exiled card cannot currently be played as a land")
    exile = list(state.exile)
    exile.remove(card)
    staged = replace(state, exile=tuple(exile), hand=state.hand + (card,))
    physical = solver._play_land_physical(staged, card)
    if physical is None:
        raise ValueError("Urza-exiled land could not be physically played")
    next_state, message = physical
    next_state = solver.add_trace(next_state, message + f"; use {permission_id} from exile")
    permissions = runtime.permissions.consume(permission_id)
    validate_urza_permissions_against_state(next_state, permissions)
    runtime = replace(
        runtime,
        true_state=solver._ensure_oracle_instance_tags(next_state),
        permissions=permissions,
    )
    if card == "Seat of the Synod":
        runtime = core.record_artifact_entry(runtime, (card,), source="Urza permission play Seat of the Synod")
    return runtime


def _use_artifact_permission(
    runtime,
    *,
    permission_id: str,
    card: str,
    kicks: int,
    mana_spent: int,
) -> core.NonOracleRuntimeState:
    permission = _permission_by_id(runtime, permission_id)
    if permission is None or permission.card != card or card not in runtime.true_state.exile:
        raise ValueError("Urza artifact permission is no longer live")
    if card not in solver.ARTIFACTS or card in solver.TRUE_LAND_CARDS:
        raise ValueError("Urza permission card is not a supported artifact spell")
    if card == CHALICE:
        expected = 2 * int(kicks)
        if kicks < 0 or int(mana_spent) != expected:
            raise ValueError("Urza Chalice multikicker commitment is malformed")
        return _begin_special_permission_artifact(
            runtime, permission_id=permission_id, card=card, kicks=kicks, mana_spent=expected
        )
    if card == MOX_DIAMOND:
        if kicks != 0 or mana_spent != 0:
            raise ValueError("Urza Mox Diamond commitment is malformed")
        return _begin_special_permission_artifact(
            runtime, permission_id=permission_id, card=card, kicks=0, mana_spent=0
        )
    if kicks != 0 or mana_spent != 0:
        raise ValueError("ordinary free Urza artifact cast has unexpected additional cost")
    out = core.begin_committed_artifact_cast(runtime, card, mana_spent=0, from_zone="exile")
    permissions = out.permissions.consume(permission_id)
    validate_urza_permissions_against_state(out.true_state, permissions)
    return replace(out, permissions=permissions)


def _remove_exiled_permission_card(runtime, *, permission_id: str, card: str):
    permission = _permission_by_id(runtime, permission_id)
    if permission is None or permission.card != card or card not in runtime.true_state.exile:
        raise ValueError("Urza permission is no longer live")
    exile = list(runtime.true_state.exile)
    exile.remove(card)
    state = replace(runtime.true_state, exile=tuple(exile), spell_cast_this_turn=True)
    permissions = runtime.permissions.consume(permission_id)
    validate_urza_permissions_against_state(state, permissions)
    return state, permissions


def _use_proactive_permission(
    runtime,
    *,
    permission_id: str,
    card: str,
    target_signature: Tuple[object, ...],
) -> core.NonOracleRuntimeState:
    if card not in SUPPORTED_PROACTIVE:
        raise ValueError("Urza permission card is not a typed proactive spell")
    target = _target_from_signature(runtime.true_state, target_signature)
    if target_signature and target is None:
        raise ValueError("Urza proactive permission target is no longer present")
    state, permissions = _remove_exiled_permission_card(
        runtime, permission_id=permission_id, card=card
    )
    state = solver.add_trace(state, f"Phase2 Urza permission casts {card} free from exile")
    runtime = replace(runtime, true_state=state, permissions=permissions)

    payload = (("mana_spent", 0),)
    public = (("mana_spent", 0),)
    strategic = list(public)
    if target is not None:
        payload += (("target_tag", int(target.instance_tag)),)
        public += (("target_state", target_signature),)
        strategic.append(("target_state", target_signature))
    spell, stack = runtime.stack.allocate(
        object_type=core.STACK_SPELL,
        kind=_spell_kind(card),
        source="exile",
        card=card,
        payload=payload,
        public_payload=public,
        strategic_payload=tuple(strategic),
    )
    runtime = replace(runtime, stack=stack.push_existing((spell,)))
    info = apply_observation_batch(
        runtime.information,
        post_cast_observations(state, card, cast_from_library_top=False),
    )
    runtime = replace(runtime, information=info)
    triggers, allocated = core._cast_trigger_objects(runtime, card, 0, spell.object_id)
    runtime = replace(runtime, stack=allocated)
    return core._queue_simultaneous_objects(runtime, triggers, source=f"Urza permission cast {card}")


def _use_probe_permission(runtime, *, permission_id: str) -> core.NonOracleRuntimeState:
    state, permissions = _remove_exiled_permission_card(
        runtime, permission_id=permission_id, card=PROBE
    )
    state = solver.add_trace(state, "Phase2 Urza permission casts Gitaxian Probe free from exile")
    runtime = replace(runtime, true_state=state, permissions=permissions)
    spell, stack = runtime.stack.allocate(
        object_type=core.STACK_SPELL,
        kind=SPELL_PROBE,
        source="exile",
        card=PROBE,
        payload=(("mana_spent", 0),),
        public_payload=(("mana_spent", 0),),
        strategic_payload=(("mana_spent", 0),),
    )
    runtime = replace(runtime, stack=stack.push_existing((spell,)))
    info = apply_observation_batch(
        runtime.information,
        post_cast_observations(state, PROBE, cast_from_library_top=False),
    )
    runtime = replace(runtime, information=info)
    triggers, allocated = core._cast_trigger_objects(runtime, PROBE, 0, spell.object_id)
    runtime = replace(runtime, stack=allocated)
    return core._queue_simultaneous_objects(runtime, triggers, source="Urza permission cast Gitaxian Probe")


def _apply_permission_action(runtime, action: ActionIntent) -> core.NonOracleRuntimeState:
    params = dict(action.parameters)
    permission_id = str(params["permission_id"])
    card = str(params["card"])
    use = str(params["use"])
    if use == USE_PLAY_LAND:
        return _use_land_permission(runtime, permission_id=permission_id, card=card)
    if use == USE_CAST_ARTIFACT:
        return _use_artifact_permission(
            runtime,
            permission_id=permission_id,
            card=card,
            kicks=int(params.get("kicks", 0)),
            mana_spent=int(params.get("mana_spent", 0)),
        )
    if use == USE_CAST_PROACTIVE:
        return _use_proactive_permission(
            runtime,
            permission_id=permission_id,
            card=card,
            target_signature=tuple(params.get("target_signature", ())),
        )
    if use == USE_CAST_PROBE:
        return _use_probe_permission(runtime, permission_id=permission_id)
    raise ValueError(f"unsupported Urza permission use {use!r}")


def begin_urza_main_action(runtime, action: ActionIntent) -> core.NonOracleRuntimeState:
    legal = {candidate.canonical_key() for candidate in urza_main_intents(runtime)}
    if action.canonical_key() not in legal:
        raise ValueError("Urza main action is no longer legal")
    if action.kind == MAIN_ACTIVATE_URZA_SPIN:
        return _begin_spin(runtime, action)
    if action.kind == MAIN_USE_URZA_PERMISSION:
        return _apply_permission_action(runtime, action)
    raise ValueError(f"unsupported Urza main action {action.kind!r}")


def begin_urza_priority_action(runtime, action: ActionIntent) -> core.NonOracleRuntimeState:
    legal = {candidate.canonical_key() for candidate in urza_priority_intents(runtime)}
    if action.canonical_key() not in legal:
        raise ValueError("Urza priority action is no longer legal")
    if action.kind == MAIN_ACTIVATE_URZA_SPIN:
        return _begin_spin(runtime, action)
    if action.kind == MAIN_USE_URZA_PERMISSION:
        return _apply_permission_action(runtime, action)
    raise ValueError(f"unsupported Urza priority action {action.kind!r}")


def handles_urza_stack_top(runtime: core.NonOracleRuntimeState) -> bool:
    if runtime.pending is not None:
        return False
    top = runtime.stack.top()
    return bool(top and top.kind == ACT_URZA_SPIN)


def apply_urza_stack_action(runtime, action: ActionIntent) -> core.NonOracleRuntimeState:
    if action.action_id != core.ACTION_PASS_PRIORITY or action.kind != "pass_priority":
        raise ValueError("Urza spin resolves only after passing priority")
    obj, remaining = runtime.stack.pop_top()
    if obj is None or obj.kind != ACT_URZA_SPIN:
        raise ValueError("top runtime object is not Urza spin")
    runtime = replace(runtime, stack=remaining)
    state = runtime.true_state
    if not state.library:
        return replace(runtime, window=RuntimeDecisionWindow(WINDOW_PRIORITY))

    shuffled = replace(state, library=solver.shuffled_library(state, "urza-spin"))
    card = str(shuffled.library[0])
    state = replace(
        shuffled,
        library=tuple(shuffled.library[1:]),
        exile=tuple(shuffled.exile) + (card,),
    )
    state = solver.add_trace(state, f"Phase2 Urza spin resolves -> exile {card}")
    permissions = runtime.permissions.grant(card, int(state.turn))
    validate_urza_permissions_against_state(state, permissions)
    info = apply_observation_batch(
        runtime.information,
        ObservationBatch((
            ShuffleObservation("Urza spin"),
            PublicZoneChangeObservation(
                card,
                from_zone="library",
                to_zone="exile",
                source="Urza spin",
            ),
        )),
    )
    info = _refresh_continuous_top(state, info, source="post-Urza-spin continuous look")
    return replace(
        runtime,
        true_state=state,
        information=info,
        permissions=permissions,
        window=RuntimeDecisionWindow(WINDOW_PRIORITY),
    )
