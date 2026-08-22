#!/usr/bin/env python3
"""Additional timing regressions for persistent Urza permissions."""

import urza_solver as solver
from urza_permission_adapter import (
    TIMING_MAIN_EMPTY,
    TIMING_PRIORITY,
    UrzaPermissionState,
    urza_permission_intents,
)


def actions_for(card, *, battlefield=()):
    state = solver.State(
        turn=3,
        library=("Tail",),
        hand=(),
        exile=(card,),
        battlefield=tuple(battlefield),
        land_played=False,
    )
    permissions = UrzaPermissionState().grant(card, 3)
    return state, permissions


def uses(actions):
    return {(dict(action.parameters)["use"], dict(action.parameters)["card"]) for action in actions}


def test_floodcaller_allows_noncreature_urza_spell_at_priority():
    state, permissions = actions_for(
        "Mana Vault",
        battlefield=(solver.Perm("Valley Floodcaller"),),
    )
    priority = urza_permission_intents(
        state, permissions, timing_window=TIMING_PRIORITY
    )
    assert ("cast_spell", "Mana Vault") in uses(priority)


def test_mdfc_can_offer_both_land_and_spell_faces_in_main_window():
    state, permissions = actions_for("Hydroelectric Specimen")
    main = urza_permission_intents(
        state, permissions, timing_window=TIMING_MAIN_EMPTY
    )
    assert ("play_land", "Hydroelectric Specimen") in uses(main)
    assert ("cast_spell", "Hydroelectric Specimen") in uses(main)


def test_instant_mdfc_spell_face_remains_available_at_priority():
    state, permissions = actions_for("Sink into Stupor")
    priority = urza_permission_intents(
        state, permissions, timing_window=TIMING_PRIORITY
    )
    assert ("cast_spell", "Sink into Stupor") in uses(priority)
    assert ("play_land", "Sink into Stupor") not in uses(priority)


def test_free_x_spell_records_x_zero_before_shared_cast_resolution():
    state, permissions = actions_for(
        "Reshape",
        battlefield=(solver.Perm("Valley Floodcaller"),),
    )
    priority = urza_permission_intents(
        state, permissions, timing_window=TIMING_PRIORITY
    )
    action = next(
        action for action in priority
        if dict(action.parameters)["card"] == "Reshape"
    )
    assert dict(action.parameters)["x_value"] == 0
    assert dict(action.parameters)["without_paying_mana_cost"] is True


def main():
    tests = (
        test_floodcaller_allows_noncreature_urza_spell_at_priority,
        test_mdfc_can_offer_both_land_and_spell_faces_in_main_window,
        test_instant_mdfc_spell_face_remains_available_at_priority,
        test_free_x_spell_records_x_zero_before_shared_cast_resolution,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("URZA PERMISSION TIMING SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
