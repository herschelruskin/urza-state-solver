#!/usr/bin/env python3
"""Focused regressions for persistent Urza {5} exile permissions."""

from dataclasses import replace

import urza_solver as solver
from solver_architecture import InformationState
from urza_permission_adapter import (
    TIMING_MAIN_EMPTY,
    TIMING_PRIORITY,
    UrzaPermissionState,
    information_after_urza_spin,
    resolve_urza_permission_use,
    resolve_urza_spin,
    urza_permission_intents,
    urza_spin_request,
    validate_urza_permissions_against_state,
)


def urza_state(library, *, mana=10):
    return solver.State(
        turn=3,
        library=tuple(library),
        hand=(),
        battlefield=(solver.Perm(solver.COMMANDER), solver.Perm("Sol Ring")),
        urza=True,
        colorless=mana,
        rng_root_seed=20260822,
    )


def choose_permission(actions, card, use):
    return next(
        action
        for action in actions
        if dict(action.parameters).get("card") == card
        and dict(action.parameters).get("use") == use
    )


def test_spin_grants_permission_without_forcing_immediate_play_decision():
    state = urza_state(("Mana Vault", "Island", "Tail"), mana=5)
    prior_info = InformationState(known_top=("Mana Vault",), known_bottom=("Tail",), shuffle_epoch=2)
    action = urza_spin_request(state, prior_info, horizon=6).actions[0]
    result = resolve_urza_spin(state, UrzaPermissionState(), action)

    assert result.transition.pending_decision is None
    assert len(result.permissions.permissions) == 1
    assert result.granted.card in result.transition.true_state.exile
    assert result.granted.created_turn == 3
    assert result.granted.expires_turn == 3

    info = information_after_urza_spin(prior_info, result)
    assert info.known_top == ()
    assert info.known_bottom == ()
    assert info.shuffle_epoch == 3


def test_permission_survives_unrelated_action_and_remains_available_later():
    state = solver.State(
        turn=3,
        library=("Tail",),
        hand=(),
        exile=("Mana Vault",),
        battlefield=(solver.Perm(solver.COMMANDER), solver.Perm("Sol Ring")),
        urza=True,
    )
    permissions = UrzaPermissionState().grant("Mana Vault", 3)
    before = urza_permission_intents(state, permissions, timing_window=TIMING_MAIN_EMPTY)
    assert choose_permission(before, "Mana Vault", "cast_spell")

    # Take an unrelated public mana action. The Urza permission is not consumed.
    after = next(
        successor for successor in solver.intrinsic_mana_actions(state)
        if successor.trace[-1].startswith("tap Sol Ring")
    )
    validate_urza_permissions_against_state(after, permissions)
    later = urza_permission_intents(after, permissions, timing_window=TIMING_MAIN_EMPTY)
    assert choose_permission(later, "Mana Vault", "cast_spell")


def test_multiple_spins_accumulate_independent_permissions():
    state = urza_state(("Mana Vault", "Island", "Sol Ring", "Tail"), mana=10)
    info = InformationState()
    permissions = UrzaPermissionState()

    first_action = urza_spin_request(state, info, horizon=6).actions[0]
    first = resolve_urza_spin(state, permissions, first_action)
    second_state = first.transition.true_state
    second_info = information_after_urza_spin(info, first)
    second_action = urza_spin_request(second_state, second_info, horizon=6).actions[0]
    second = resolve_urza_spin(second_state, first.permissions, second_action)

    assert len(second.permissions.permissions) == 2
    assert second.permissions.permissions[0].permission_id != second.permissions.permissions[1].permission_id
    assert all(
        permission.card in second.transition.true_state.exile
        for permission in second.permissions.permissions
    )


def test_normal_timing_is_preserved_for_delayed_permissions():
    state = solver.State(
        turn=3,
        library=("Tail",),
        hand=(),
        exile=("Mana Vault", "An Offer You Can't Refuse"),
        battlefield=(solver.Perm(solver.COMMANDER),),
        urza=True,
    )
    permissions = UrzaPermissionState().grant("Mana Vault", 3).grant(
        "An Offer You Can't Refuse", 3
    )

    priority = urza_permission_intents(state, permissions, timing_window=TIMING_PRIORITY)
    priority_cards = {dict(action.parameters)["card"] for action in priority}
    assert "An Offer You Can't Refuse" in priority_cards
    assert "Mana Vault" not in priority_cards

    main = urza_permission_intents(state, permissions, timing_window=TIMING_MAIN_EMPTY)
    main_cards = {dict(action.parameters)["card"] for action in main}
    assert {"Mana Vault", "An Offer You Can't Refuse"} <= main_cards


def test_cast_selection_does_not_prematurely_move_card_or_consume_permission():
    state = solver.State(
        turn=3,
        library=("Tail",),
        hand=(),
        exile=("Mana Vault",),
        battlefield=(solver.Perm(solver.COMMANDER),),
        urza=True,
    )
    permissions = UrzaPermissionState().grant("Mana Vault", 3)
    action = choose_permission(
        urza_permission_intents(state, permissions, timing_window=TIMING_MAIN_EMPTY),
        "Mana Vault",
        "cast_spell",
    )
    use = resolve_urza_permission_use(
        state, permissions, action, timing_window=TIMING_MAIN_EMPTY
    )
    assert use.transition.true_state.exile == ("Mana Vault",)
    assert use.permissions == permissions
    assert use.transition.pending_decision is not None
    assert use.transition.pending_decision.kind == "cast_urza_permission_card"


def test_land_use_consumes_exact_permission_and_card():
    state = solver.State(
        turn=3,
        library=("Tail",),
        hand=(),
        exile=("Island", "Island"),
        battlefield=(),
        land_played=False,
    )
    permissions = UrzaPermissionState().grant("Island", 3).grant("Island", 3)
    actions = urza_permission_intents(state, permissions, timing_window=TIMING_MAIN_EMPTY)
    first = actions[0]
    use = resolve_urza_permission_use(
        state, permissions, first, timing_window=TIMING_MAIN_EMPTY
    )
    assert use.transition.true_state.exile == ("Island",)
    assert len(use.permissions.permissions) == 1
    assert any(p.name == "Island" for p in use.transition.true_state.battlefield)
    assert use.transition.true_state.land_played is True


def test_unused_permission_expires_at_end_of_turn_but_card_remains_exiled():
    state = solver.State(turn=3, library=("Tail",), hand=(), exile=("Mana Vault",))
    permissions = UrzaPermissionState().grant("Mana Vault", 3)
    expired = permissions.expire_end_of_turn(3)
    assert expired.permissions == ()
    assert state.exile == ("Mana Vault",)


def main():
    tests = (
        test_spin_grants_permission_without_forcing_immediate_play_decision,
        test_permission_survives_unrelated_action_and_remains_available_later,
        test_multiple_spins_accumulate_independent_permissions,
        test_normal_timing_is_preserved_for_delayed_permissions,
        test_cast_selection_does_not_prematurely_move_card_or_consume_permission,
        test_land_use_consumes_exact_permission_and_card,
        test_unused_permission_expires_at_end_of_turn_but_card_remains_exiled,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("URZA PERMISSION ADAPTER SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
