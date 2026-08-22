#!/usr/bin/env python3
"""Persistent non-Oracle permissions created by Urza's {5} ability.

Urza does NOT ask its controller to play the exiled card during resolution.  The
ability creates a public permission lasting until end of turn.  Policy mode must
therefore return to the normal action loop after the spin and may sequence other
actions, additional spins, trigger resolutions, or priority decisions before
using any still-live permission.

This module keeps that permission as a sidecar instead of overloading
InformationState: the exiled card is public information, while the temporary
permission is a value-relevant rules resource.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from typing import Optional, Tuple

import urza_solver as solver
from solver_architecture import InformationState, make_policy_view
from decision_observation import (
    ActionIntent,
    DECISION_COMMIT,
    DECISION_MECHANICAL,
    DecisionRequest,
    ObservationBatch,
    PendingDecisionSpec,
    PolicyDecisionContext,
    PublicZoneChangeObservation,
    ShuffleObservation,
    TransitionEnvelope,
    apply_observation_batch,
)

URZA = solver.COMMANDER
URZA_SPIN_ACTION_ID = "urza.spin.activate"
TIMING_MAIN_EMPTY = "main_empty"
TIMING_PRIORITY = "priority"
VALID_TIMING_WINDOWS = frozenset({TIMING_MAIN_EMPTY, TIMING_PRIORITY})


@dataclass(frozen=True, order=True)
class UrzaPlayPermission:
    permission_id: str
    card: str
    created_turn: int
    expires_turn: int
    sequence: int
    source: str = URZA
    without_paying_mana_cost: bool = True

    def key(self) -> Tuple[object, ...]:
        return (
            self.permission_id,
            self.card,
            self.created_turn,
            self.expires_turn,
            self.sequence,
            self.source,
            self.without_paying_mana_cost,
        )


@dataclass(frozen=True)
class UrzaPermissionState:
    permissions: Tuple[UrzaPlayPermission, ...] = ()
    next_sequence: int = 0

    def key(self) -> Tuple[object, ...]:
        return (
            "urza-permission-state-v1",
            tuple(permission.key() for permission in self.permissions),
            int(self.next_sequence),
        )

    def grant(self, card: str, turn: int) -> "UrzaPermissionState":
        sequence = int(self.next_sequence)
        permission = UrzaPlayPermission(
            permission_id=f"urza:{int(turn)}:{sequence}",
            card=str(card),
            created_turn=int(turn),
            expires_turn=int(turn),
            sequence=sequence,
        )
        return UrzaPermissionState(
            permissions=self.permissions + (permission,),
            next_sequence=sequence + 1,
        )

    def consume(self, permission_id: str) -> "UrzaPermissionState":
        remaining = tuple(
            permission
            for permission in self.permissions
            if permission.permission_id != str(permission_id)
        )
        if len(remaining) == len(self.permissions):
            raise ValueError(f"unknown Urza permission {permission_id!r}")
        return UrzaPermissionState(remaining, self.next_sequence)

    def expire_end_of_turn(self, ending_turn: int) -> "UrzaPermissionState":
        remaining = tuple(
            permission
            for permission in self.permissions
            if permission.expires_turn > int(ending_turn)
        )
        return UrzaPermissionState(remaining, self.next_sequence)


@dataclass(frozen=True)
class UrzaSpinResolution:
    transition: TransitionEnvelope
    permissions: UrzaPermissionState
    granted: UrzaPlayPermission


@dataclass(frozen=True)
class UrzaPermissionUse:
    transition: TransitionEnvelope
    permissions: UrzaPermissionState
    permission: UrzaPlayPermission
    use_kind: str


def validate_urza_permissions_against_state(
    state,
    permissions: UrzaPermissionState,
) -> None:
    """Every live permission must still have a corresponding public exile card."""
    exile_counts = Counter(str(card) for card in state.exile)
    permission_counts = Counter(permission.card for permission in permissions.permissions)
    for card, count in permission_counts.items():
        if count > exile_counts[card]:
            raise ValueError(
                f"{count} live Urza permission(s) for {card!r} but only "
                f"{exile_counts[card]} matching card(s) in exile"
            )


def urza_spin_intents(state) -> Tuple[ActionIntent, ...]:
    if not state.urza or not solver.can_pay(state, 5, 0) or not state.library:
        return ()
    return (
        ActionIntent(
            action_id=URZA_SPIN_ACTION_ID,
            kind="activate_urza_spin",
            parameters=(("generic_cost", 5),),
            equivalence_key=("urza_spin",),
            label="Activate Urza for 5",
            decision_stage=DECISION_COMMIT,
            source=URZA,
        ),
    )


def urza_spin_request(
    state,
    information: InformationState,
    *,
    horizon: int,
    objective: str = "win_by_horizon",
    policy_id: str = "base",
    caverns_live: Optional[bool] = None,
) -> DecisionRequest:
    return DecisionRequest(
        observation=make_policy_view(state, information, caverns_live=caverns_live),
        actions=urza_spin_intents(state),
        context=PolicyDecisionContext(
            horizon=horizon,
            objective=objective,
            policy_id=policy_id,
            decision_id="urza.spin.activation",
            decision_stage=DECISION_COMMIT,
        ),
    )


def resolve_urza_spin(
    state,
    permissions: UrzaPermissionState,
    action: ActionIntent,
) -> UrzaSpinResolution:
    """Resolve the spin and grant a lasting permission; do not force play now."""
    legal = {candidate.canonical_key(): candidate for candidate in urza_spin_intents(state)}
    if action.canonical_key() not in legal:
        raise ValueError("Urza spin activation is not legal")
    validate_urza_permissions_against_state(state, permissions)

    paid = solver.pay(state, 5, 0)
    shuffled = replace(paid, library=solver.shuffled_library(paid, "urza-spin"))
    card = str(shuffled.library[0])
    observed = replace(
        shuffled,
        library=tuple(shuffled.library[1:]),
        exile=tuple(shuffled.exile) + (card,),
    )
    observed = solver.add_trace(observed, f"Urza spin -> exile {card}; playable until end of turn")

    updated = permissions.grant(card, int(state.turn))
    granted = updated.permissions[-1]
    validate_urza_permissions_against_state(observed, updated)
    transition = TransitionEnvelope(
        true_state=observed,
        observations=ObservationBatch(
            (
                ShuffleObservation("Urza spin"),
                PublicZoneChangeObservation(
                    card,
                    from_zone="library",
                    to_zone="exile",
                    source="Urza spin",
                ),
            )
        ),
        pending_decision=None,
        trace_note=(
            f"Urza spin granted {granted.permission_id} for {card}; "
            "normal policy sequencing resumes"
        ),
    )
    return UrzaSpinResolution(transition, updated, granted)


def information_after_urza_spin(
    prior: InformationState,
    resolution: UrzaSpinResolution,
) -> InformationState:
    return apply_observation_batch(prior, resolution.transition.observations)


def _permission_is_current(permission: UrzaPlayPermission, turn: int) -> bool:
    return permission.created_turn <= int(turn) <= permission.expires_turn


def _is_creature_spell(card: str) -> bool:
    return card == solver.COMMANDER or card in solver.CREATURES


def _normal_timing_allows_spell(state, card: str, timing_window: str) -> bool:
    if timing_window == TIMING_MAIN_EMPTY:
        return True
    if timing_window != TIMING_PRIORITY:
        raise ValueError(f"unknown timing window {timing_window!r}")

    if card in solver.INSTANTS:
        return True
    if card == "Valley Floodcaller":
        return True  # printed flash

    # Valley Floodcaller lets noncreature spells be cast as though they had flash,
    # including cards cast from exile through Urza's permission.
    if solver.has(state, "Valley Floodcaller") and not _is_creature_spell(card):
        return True
    return False


def _action_parameters(
    permission: UrzaPlayPermission,
    use_kind: str,
) -> Tuple[Tuple[str, object], ...]:
    rows = [
        ("permission_id", permission.permission_id),
        ("card", permission.card),
        ("use", use_kind),
        ("without_paying_mana_cost", True),
    ]
    # If a spell has X in its mana cost, casting it without paying its mana cost
    # forces X=0.  Additional costs (for example multikicker) remain a later
    # cast-time choice in the shared resolver.
    if permission.card in {"Reshape", "Whir of Invention"}:
        rows.append(("x_value", 0))
    return tuple(rows)


def urza_permission_intents(
    state,
    permissions: UrzaPermissionState,
    *,
    timing_window: str,
) -> Tuple[ActionIntent, ...]:
    """Generate currently legal uses of all still-live Urza permissions.

    No explicit "decline" action exists: not using a permission now is represented
    by choosing some other ordinary policy action / passing priority.  MDFCs may
    offer both a land-face play and a spell-face cast when each is currently legal.
    """
    if timing_window not in VALID_TIMING_WINDOWS:
        raise ValueError(f"invalid timing window {timing_window!r}")
    validate_urza_permissions_against_state(state, permissions)

    exile_counts = Counter(str(card) for card in state.exile)
    rows = []
    for permission in permissions.permissions:
        if not _permission_is_current(permission, int(state.turn)):
            continue
        if exile_counts[permission.card] <= 0:
            continue
        card = permission.card

        # Land face.  True lands have only this route; MDFCs may also offer their
        # spell-face route below.
        if card in solver.ALL_LANDS and timing_window == TIMING_MAIN_EMPTY and not state.land_played:
            rows.append(
                ActionIntent(
                    action_id=f"urza.permission.{permission.permission_id}.play_land",
                    kind="use_urza_permission",
                    parameters=_action_parameters(permission, "play_land"),
                    equivalence_key=(
                        "urza_permission",
                        "play_land",
                        card,
                        permission.expires_turn,
                    ),
                    label=f"Play Urza-exiled {card} as land",
                    decision_stage=DECISION_COMMIT,
                    source=URZA,
                )
            )

        # Spell face.  True land cards have no spell face; MDFCs do.
        if card not in solver.TRUE_LAND_CARDS and _normal_timing_allows_spell(
            state, card, timing_window
        ):
            rows.append(
                ActionIntent(
                    action_id=f"urza.permission.{permission.permission_id}.cast_spell",
                    kind="use_urza_permission",
                    parameters=_action_parameters(permission, "cast_spell"),
                    equivalence_key=(
                        "urza_permission",
                        "cast_spell",
                        card,
                        permission.expires_turn,
                    ),
                    label=f"Cast Urza-exiled {card} without paying its mana cost",
                    decision_stage=DECISION_COMMIT,
                    source=URZA,
                )
            )
    return tuple(rows)


def _permission_from_action(
    permissions: UrzaPermissionState,
    action: ActionIntent,
) -> UrzaPlayPermission:
    params = dict(action.parameters)
    permission_id = str(params.get("permission_id", ""))
    for permission in permissions.permissions:
        if permission.permission_id == permission_id:
            if str(params.get("card", "")) != permission.card:
                raise ValueError("Urza permission action card mismatch")
            return permission
    raise ValueError("Urza permission action references no live permission")


def _remove_one_exiled(state, card: str):
    exile = list(state.exile)
    try:
        exile.remove(card)
    except ValueError as exc:
        raise ValueError(f"Urza-permission card {card!r} is not in exile") from exc
    return replace(state, exile=tuple(exile))


def resolve_urza_permission_use(
    state,
    permissions: UrzaPermissionState,
    action: ActionIntent,
    *,
    timing_window: str,
) -> UrzaPermissionUse:
    legal = {
        candidate.canonical_key(): candidate
        for candidate in urza_permission_intents(
            state, permissions, timing_window=timing_window
        )
    }
    if action.canonical_key() not in legal:
        raise ValueError("Urza permission use is not currently legal")
    permission = _permission_from_action(permissions, action)
    use = str(dict(action.parameters)["use"])

    if use == "play_land":
        staged = _remove_one_exiled(state, permission.card)
        staged = replace(staged, hand=tuple(staged.hand) + (permission.card,))
        played = solver.play_land(staged, permission.card)
        if played is None:
            raise ValueError("Urza-exiled land could not be legally played")
        updated = permissions.consume(permission.permission_id)
        played = solver.add_trace(
            played, f"use {permission.permission_id}: play {permission.card} from exile"
        )
        return UrzaPermissionUse(
            TransitionEnvelope(true_state=played), updated, permission, use
        )

    if use == "cast_spell":
        # Keep the card in exile and the permission live until the shared cast
        # resolver actually begins casting it.  Moving it to hand here would be a
        # rules lie and could affect zone-sensitive legality/effects.
        transition = TransitionEnvelope(
            true_state=state,
            pending_decision=PendingDecisionSpec(
                decision_id=f"{permission.permission_id}.cast",
                kind="cast_urza_permission_card",
                source=permission.card,
                decision_stage=DECISION_MECHANICAL,
                contingent_on=action.action_id,
            ),
            trace_note=(
                f"Begin free cast of {permission.card} from exile via "
                f"{permission.permission_id}; shared cast resolver must consume "
                "the permission when the card moves to the stack"
            ),
        )
        return UrzaPermissionUse(
            transition, permissions, permission, use
        )

    raise ValueError(f"unknown Urza permission use {use!r}")


def consume_permission_for_cast(
    state_after_card_left_exile,
    permissions: UrzaPermissionState,
    permission_id: str,
) -> UrzaPermissionState:
    """Phase-2 hook called once the shared cast resolver moves card to the stack."""
    updated = permissions.consume(permission_id)
    validate_urza_permissions_against_state(state_after_card_left_exile, updated)
    return updated
