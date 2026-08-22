#!/usr/bin/env python3
"""Phase-2 Urza spin and main-phase permission runtime.

Urza's {5} activation is a real stack object.  The policy commits and pays before
any random card is known; only resolution shuffles the library, exiles the new top
card, emits typed public observations, and grants a persistent permission lasting
until end of turn.

This slice connects the permission to main-phase land plays and artifact spells.
Ordinary artifacts use the shared typed artifact-cast runtime.  Mox Diamond and
Everflowing Chalice retain their special entry/multikicker semantics, including the
fact that Chalice cast without paying its mana cost may still pay optional
multikicker.  Nonartifact permission casts are deliberately left for a later slice
rather than approximated here.
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


def _current_permissions(runtime: core.NonOracleRuntimeState):
    turn = int(runtime.true_state.turn)
    return tuple(
        permission
        for permission in runtime.permissions.permissions
        if permission.created_turn <= turn <= permission.expires_turn
        and permission.card in runtime.true_state.exile
    )


def _spin_intents(runtime: core.NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    state = runtime.true_state
    if not state.urza or not state.library or not solver.can_pay(state, 5, 0):
        return ()
    return (ActionIntent(
        action_id="main.urza.spin",
        kind=MAIN_ACTIVATE_URZA_SPIN,
        parameters=(("generic_cost", 5),),
        equivalence_key=(MAIN_ACTIVATE_URZA_SPIN,),
        label="Urza: pay 5, shuffle, exile top card",
        decision_stage=DECISION_COMMIT,
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


def _permission_artifact_actions(runtime, permission) -> Tuple[ActionIntent, ...]:
    state = runtime.true_state
    card = permission.card
    if card not in solver.ARTIFACTS or card in solver.TRUE_LAND_CARDS:
        return ()

    kicks = (0,)
    if card == CHALICE:
        max_k = min(8, max(0, (int(state.blue) + int(state.colorless)) // 2))
        kicks = tuple(range(max_k + 1))

    rows = []
    for kick_count in kicks:
        additional = 2 * int(kick_count) if card == CHALICE else 0
        if additional and not solver.can_pay(state, additional, 0):
            continue
        rows.append(ActionIntent(
            action_id=(
                f"main.urza.permission.{permission.permission_id}.artifact.k{kick_count}"
            ),
            kind=MAIN_USE_URZA_PERMISSION,
            parameters=(
                ("card", card),
                ("kicks", int(kick_count)),
                ("mana_spent", int(additional)),
                ("permission_id", permission.permission_id),
                ("use", USE_CAST_ARTIFACT),
            ),
            equivalence_key=(
                MAIN_USE_URZA_PERMISSION,
                USE_CAST_ARTIFACT,
                card,
                int(kick_count),
                permission.expires_turn,
            ),
            label=(
                f"Urza permission: cast {card} free"
                + (f"; multikicker {kick_count}" if card == CHALICE else "")
            ),
            decision_stage=DECISION_COMMIT,
            source=solver.COMMANDER,
        ))
    return tuple(rows)


def urza_main_intents(runtime: core.NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    state = runtime.true_state
    rows = list(_spin_intents(runtime))
    validate_urza_permissions_against_state(state, runtime.permissions)
    for permission in _current_permissions(runtime):
        card = permission.card
        if card in solver.ALL_LANDS and not state.land_played:
            rows.append(_permission_land_action(permission))
        # MDFCs may also have an artifact spell face only if the front card is an
        # artifact; currently none in this deck.  True lands never become spells.
        rows.extend(_permission_artifact_actions(runtime, permission))
    return tuple(sorted(rows, key=lambda action: action.action_id))


def _permission_by_id(runtime: core.NonOracleRuntimeState, permission_id: str):
    for permission in runtime.permissions.permissions:
        if permission.permission_id == str(permission_id):
            return permission
    return None


def _begin_spin(
    runtime: core.NonOracleRuntimeState,
    action: ActionIntent,
) -> core.NonOracleRuntimeState:
    legal = {candidate.canonical_key() for candidate in _spin_intents(runtime)}
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
    triggers, allocated = core._cast_trigger_objects(
        runtime, card, int(mana_spent), spell.object_id
    )
    runtime = replace(runtime, stack=allocated)
    return core._queue_simultaneous_objects(
        runtime, triggers, source=f"Urza permission cast {card}"
    )


def _use_land_permission(
    runtime: core.NonOracleRuntimeState,
    *,
    permission_id: str,
    card: str,
) -> core.NonOracleRuntimeState:
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
    next_state = solver.add_trace(
        next_state,
        message + f"; use {permission_id} from exile",
    )
    permissions = runtime.permissions.consume(permission_id)
    validate_urza_permissions_against_state(next_state, permissions)
    runtime = replace(
        runtime,
        true_state=solver._ensure_oracle_instance_tags(next_state),
        permissions=permissions,
    )
    if card == "Seat of the Synod":
        runtime = core.record_artifact_entry(
            runtime,
            (card,),
            source="Urza permission play Seat of the Synod",
        )
    return runtime


def _use_artifact_permission(
    runtime: core.NonOracleRuntimeState,
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
            runtime,
            permission_id=permission_id,
            card=card,
            kicks=kicks,
            mana_spent=expected,
        )
    if card == MOX_DIAMOND:
        if kicks != 0 or mana_spent != 0:
            raise ValueError("Urza Mox Diamond commitment is malformed")
        return _begin_special_permission_artifact(
            runtime,
            permission_id=permission_id,
            card=card,
            kicks=0,
            mana_spent=0,
        )
    if kicks != 0 or mana_spent != 0:
        raise ValueError("ordinary free Urza artifact cast has unexpected additional cost")

    # Shared artifact cast moves the card from exile directly to the typed stack.
    out = core.begin_committed_artifact_cast(
        runtime,
        card,
        mana_spent=0,
        from_zone="exile",
    )
    permissions = out.permissions.consume(permission_id)
    validate_urza_permissions_against_state(out.true_state, permissions)
    return replace(out, permissions=permissions)


def begin_urza_main_action(
    runtime: core.NonOracleRuntimeState,
    action: ActionIntent,
) -> core.NonOracleRuntimeState:
    legal = {candidate.canonical_key() for candidate in urza_main_intents(runtime)}
    if action.canonical_key() not in legal:
        raise ValueError("Urza main action is no longer legal")
    if action.kind == MAIN_ACTIVATE_URZA_SPIN:
        return _begin_spin(runtime, action)
    if action.kind != MAIN_USE_URZA_PERMISSION:
        raise ValueError(f"unsupported Urza main action {action.kind!r}")

    params = dict(action.parameters)
    permission_id = str(params["permission_id"])
    card = str(params["card"])
    use = str(params["use"])
    if use == USE_PLAY_LAND:
        return _use_land_permission(
            runtime,
            permission_id=permission_id,
            card=card,
        )
    if use == USE_CAST_ARTIFACT:
        return _use_artifact_permission(
            runtime,
            permission_id=permission_id,
            card=card,
            kicks=int(params.get("kicks", 0)),
            mana_spent=int(params.get("mana_spent", 0)),
        )
    raise ValueError(f"unsupported Urza permission use {use!r}")


def handles_urza_stack_top(runtime: core.NonOracleRuntimeState) -> bool:
    if runtime.pending is not None:
        return False
    top = runtime.stack.top()
    return bool(top and top.kind == ACT_URZA_SPIN)


def apply_urza_stack_action(
    runtime: core.NonOracleRuntimeState,
    action: ActionIntent,
) -> core.NonOracleRuntimeState:
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
    info = _refresh_continuous_top(
        state,
        info,
        source="post-Urza-spin continuous look",
    )
    return replace(
        runtime,
        true_state=state,
        information=info,
        permissions=permissions,
        window=RuntimeDecisionWindow(WINDOW_PRIORITY),
    )
