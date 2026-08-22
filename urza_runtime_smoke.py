#!/usr/bin/env python3
"""Focused Phase-2 smokes for Urza spin and persistent main-phase permissions."""

import urza_solver as solver
import non_oracle_rules_adapter as rules
from non_oracle_base_policy import DeterministicBasePolicy
from non_oracle_runtime import ACTION_PASS_PRIORITY, make_runtime_state
from non_oracle_urza_runtime import (
    ACT_URZA_SPIN,
    MAIN_ACTIVATE_URZA_SPIN,
    MAIN_USE_URZA_PERMISSION,
)
from solver_architecture import InformationState
from urza_permission_adapter import UrzaPermissionState


def _request(runtime):
    return rules.rules_decision_request(runtime, horizon=6)


def _actions(runtime, kind):
    return [action for action in _request(runtime).actions if action.kind == kind]


def _pass(runtime):
    return next(action for action in _request(runtime).actions if action.action_id == ACTION_PASS_PRIORITY)


def _permission_runtime(card, *, hand=(), battlefield=(), blue=0, colorless=0, land_played=False):
    permissions = UrzaPermissionState().grant(card, 2)
    return make_runtime_state(
        solver.State(
            turn=2,
            library=("TAIL",),
            hand=tuple(hand),
            battlefield=tuple(battlefield),
            exile=(card,),
            blue=blue,
            colorless=colorless,
            land_played=land_played,
        ),
        permissions=permissions,
    )


def test_spin_commit_action_is_hidden_future_invariant():
    def build(library):
        return make_runtime_state(solver.State(
            turn=2,
            library=tuple(library),
            hand=(),
            battlefield=(solver.Perm(solver.COMMANDER),),
            urza=True,
            commander_in_command_zone=False,
            colorless=5,
        ))
    left = _request(build(("SECRET_A", "SECRET_B", "TAIL")))
    right = _request(build(("SECRET_B", "SECRET_A", "TAIL")))
    la = tuple(a.strategic_key() for a in left.actions if a.kind == MAIN_ACTIVATE_URZA_SPIN)
    ra = tuple(a.strategic_key() for a in right.actions if a.kind == MAIN_ACTIVATE_URZA_SPIN)
    assert la == ra and la
    assert "SECRET_A" not in repr(la) and "SECRET_B" not in repr(la)


def test_spin_pays_before_stack_and_reveals_only_on_resolution():
    runtime = make_runtime_state(
        solver.State(
            turn=2,
            library=("Sol Ring",),
            hand=(),
            battlefield=(solver.Perm(solver.COMMANDER),),
            urza=True,
            commander_in_command_zone=False,
            colorless=5,
        ),
        InformationState(known_top=("Sol Ring",)),
    )
    action = _actions(runtime, MAIN_ACTIVATE_URZA_SPIN)[0]
    runtime = rules.apply_main_action(runtime, action)
    assert runtime.true_state.colorless == 0
    assert runtime.true_state.exile == ()
    assert runtime.permissions.permissions == ()
    assert runtime.stack.top().kind == ACT_URZA_SPIN
    assert runtime.information.known_top == ("Sol Ring",)

    before_epoch = runtime.information.shuffle_epoch
    runtime = rules.apply_main_action(runtime, _pass(runtime))
    assert runtime.true_state.exile == ("Sol Ring",)
    assert runtime.true_state.library == ()
    assert len(runtime.permissions.permissions) == 1
    assert runtime.permissions.permissions[0].card == "Sol Ring"
    assert runtime.information.known_top == ()
    assert runtime.information.shuffle_epoch == before_epoch + 1


def test_land_permission_consumes_exact_permission_and_seat_uses_typed_etb_stack():
    runtime = _permission_runtime(
        "Seat of the Synod",
        battlefield=(solver.Perm("Grinding Station", tapped=True),),
    )
    action = next(
        a for a in _actions(runtime, MAIN_USE_URZA_PERMISSION)
        if dict(a.parameters)["use"] == "play_land"
    )
    runtime = rules.apply_main_action(runtime, action)
    assert "Seat of the Synod" not in runtime.true_state.exile
    assert not runtime.permissions.permissions
    assert runtime.true_state.land_played
    assert solver.has(runtime.true_state, "Seat of the Synod")
    assert runtime.stack.objects
    assert runtime.stack.top().kind == "etb_producer"


def test_ordinary_artifact_permission_casts_directly_from_exile_then_resolves():
    runtime = _permission_runtime("Sol Ring")
    action = next(
        a for a in _actions(runtime, MAIN_USE_URZA_PERMISSION)
        if dict(a.parameters)["use"] == "cast_artifact"
    )
    runtime = rules.apply_main_action(runtime, action)
    assert "Sol Ring" not in runtime.true_state.exile
    assert not runtime.permissions.permissions
    assert not solver.has(runtime.true_state, "Sol Ring")
    assert runtime.stack.objects and runtime.stack.top().card == "Sol Ring"

    runtime = rules.apply_main_action(runtime, _pass(runtime))
    assert solver.has(runtime.true_state, "Sol Ring")


def test_chalice_permission_keeps_optional_multikicker_and_exact_counters():
    runtime = _permission_runtime("Everflowing Chalice", colorless=4)
    actions = [
        a for a in _actions(runtime, MAIN_USE_URZA_PERMISSION)
        if dict(a.parameters)["card"] == "Everflowing Chalice"
    ]
    assert {int(dict(a.parameters)["kicks"]) for a in actions} == {0, 1, 2}
    action = next(a for a in actions if int(dict(a.parameters)["kicks"]) == 1)
    runtime = rules.apply_main_action(runtime, action)
    assert runtime.true_state.colorless == 2
    assert not runtime.permissions.permissions
    assert "Everflowing Chalice" not in runtime.true_state.exile
    runtime = rules.apply_main_action(runtime, _pass(runtime))
    chalice = next(p for p in runtime.true_state.battlefield if p.name == "Everflowing Chalice")
    assert chalice.counters == 1


def test_mox_diamond_permission_still_stages_entry_replacement_choice():
    runtime = _permission_runtime("Mox Diamond", hand=("Island",))
    action = next(
        a for a in _actions(runtime, MAIN_USE_URZA_PERMISSION)
        if dict(a.parameters)["card"] == "Mox Diamond"
    )
    runtime = rules.apply_main_action(runtime, action)
    assert "Mox Diamond" not in runtime.true_state.exile
    assert not runtime.permissions.permissions
    runtime = rules.apply_main_action(runtime, _pass(runtime))
    request = _request(runtime)
    discard = next(a for a in request.actions if dict(a.parameters).get("land") == "Island")
    runtime = rules.apply_main_action(runtime, discard)
    diamond = next(p for p in runtime.true_state.battlefield if p.name == "Mox Diamond")
    assert diamond.mode == "diamond"
    assert "Island" in runtime.true_state.graveyard


def test_nonartifact_permission_is_not_falsely_offered_in_this_slice():
    runtime = _permission_runtime("Force of Will")
    assert not _actions(runtime, MAIN_USE_URZA_PERMISSION)
    assert runtime.permissions.permissions and runtime.true_state.exile == ("Force of Will",)


def test_base_policy_uses_known_artifact_permission_before_spinning_again():
    permissions = UrzaPermissionState().grant("Sol Ring", 2)
    runtime = make_runtime_state(
        solver.State(
            turn=2,
            library=("A", "B"),
            hand=(),
            battlefield=(solver.Perm(solver.COMMANDER),),
            exile=("Sol Ring",),
            urza=True,
            commander_in_command_zone=False,
            colorless=5,
        ),
        permissions=permissions,
    )
    policy = DeterministicBasePolicy()
    request = rules.rules_decision_request(runtime, horizon=6, policy_id=policy.policy_id)
    choice = policy.choose_request(request)
    assert choice.kind == MAIN_USE_URZA_PERMISSION
    assert dict(choice.parameters)["card"] == "Sol Ring"


def main():
    tests = (
        test_spin_commit_action_is_hidden_future_invariant,
        test_spin_pays_before_stack_and_reveals_only_on_resolution,
        test_land_permission_consumes_exact_permission_and_seat_uses_typed_etb_stack,
        test_ordinary_artifact_permission_casts_directly_from_exile_then_resolves,
        test_chalice_permission_keeps_optional_multikicker_and_exact_counters,
        test_mox_diamond_permission_still_stages_entry_replacement_choice,
        test_nonartifact_permission_is_not_falsely_offered_in_this_slice,
        test_base_policy_uses_known_artifact_permission_before_spinning_again,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("URZA SPIN / PERMISSION RUNTIME SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
