#!/usr/bin/env python3
"""Focused smokes for the information-safe Urza permission policy layer."""

import urza_solver as solver
import non_oracle_rules_adapter as rules
from non_oracle_base_policy import DeterministicBasePolicy
from non_oracle_runtime import make_runtime_state
from non_oracle_urza_runtime import MAIN_ACTIVATE_URZA_SPIN, MAIN_USE_URZA_PERMISSION
from urza_permission_adapter import UrzaPermissionState


def _request(runtime, policy):
    return rules.rules_decision_request(runtime, horizon=6, policy_id=policy.policy_id)


def _permission_runtime(cards, *, library=("TAIL",), battlefield=(), colorless=0, hand=()):
    permissions = UrzaPermissionState()
    for card in cards:
        permissions = permissions.grant(card, 2)
    return make_runtime_state(
        solver.State(
            turn=2,
            library=tuple(library),
            hand=tuple(hand),
            battlefield=tuple(battlefield),
            exile=tuple(cards),
            colorless=colorless,
        ),
        permissions=permissions,
    )


def test_free_tutor_permission_beats_another_blind_urza_spin_in_main():
    policy = DeterministicBasePolicy()
    runtime = _permission_runtime(
        ("Mystical Tutor",),
        library=("A", "B", "C"),
        battlefield=(solver.Perm(solver.COMMANDER),),
        colorless=5,
    )
    runtime = make_runtime_state(
        solver.State(
            turn=2,
            library=runtime.true_state.library,
            hand=(),
            battlefield=runtime.true_state.battlefield,
            exile=runtime.true_state.exile,
            urza=True,
            commander_in_command_zone=False,
            colorless=5,
        ),
        permissions=runtime.permissions,
    )
    request = _request(runtime, policy)
    choice = policy.choose_request(request)
    assert choice.kind == MAIN_USE_URZA_PERMISSION
    assert dict(choice.parameters).get("card") == "Mystical Tutor"
    assert dict(choice.parameters).get("use") == "cast_simple_tutor"


def test_own_bauble_free_probe_is_worse_than_ending_turn():
    policy = DeterministicBasePolicy()
    runtime = _permission_runtime(
        ("Gitaxian Probe",),
        battlefield=(solver.Perm("Vexing Bauble"),),
    )
    request = _request(runtime, policy)
    probe = next(
        a for a in request.actions
        if a.kind == MAIN_USE_URZA_PERMISSION and dict(a.parameters).get("card") == "Gitaxian Probe"
    )
    end = next(a for a in request.actions if a.kind == "main_end_turn")
    assert policy.action_score(request.observation, probe, request.context) < policy.action_score(
        request.observation, end, request.context
    )
    assert policy.choose_request(request).canonical_key() != probe.canonical_key()


def test_priority_spin_is_deferred_until_current_stack_clears():
    policy = DeterministicBasePolicy()
    runtime = make_runtime_state(solver.State(
        turn=2,
        library=("A", "B", "C"),
        hand=("Sol Ring",),
        battlefield=(solver.Perm(solver.COMMANDER),),
        urza=True,
        commander_in_command_zone=False,
        colorless=6,
    ))
    cast = next(
        a for a in _request(runtime, policy).actions
        if a.kind == "main_cast_artifact" and dict(a.parameters).get("card") == "Sol Ring"
    )
    runtime = rules.apply_main_action(runtime, cast)
    request = _request(runtime, policy)
    spins = [
        a for a in request.actions
        if a.kind == MAIN_ACTIVATE_URZA_SPIN and bool(dict(a.parameters).get("priority", False))
    ]
    assert len(spins) == 1
    choice = policy.choose_request(request)
    assert choice.kind == "pass_priority"


def test_x0_reshape_is_real_but_lower_priority_than_free_mystical_tutor():
    policy = DeterministicBasePolicy()
    runtime = _permission_runtime(
        ("Reshape", "Mystical Tutor"),
        library=("Mox Opal", "Island", "Dramatic Reversal"),
        battlefield=(solver.Perm("Prized Statue"),),
    )
    request = _request(runtime, policy)
    reshape = next(
        a for a in request.actions
        if a.kind == MAIN_USE_URZA_PERMISSION and dict(a.parameters).get("use") == "cast_reshape_x0"
    )
    mystical = next(
        a for a in request.actions
        if a.kind == MAIN_USE_URZA_PERMISSION and dict(a.parameters).get("card") == "Mystical Tutor"
    )
    assert policy.action_score(request.observation, reshape, request.context) > 0
    assert policy.action_score(request.observation, mystical, request.context) > policy.action_score(
        request.observation, reshape, request.context
    )
    assert policy.choose_request(request).canonical_key() == mystical.canonical_key()


def test_permission_choice_is_hidden_future_invariant():
    policy = DeterministicBasePolicy()
    left = _permission_runtime(
        ("Mystical Tutor",),
        library=("Dramatic Reversal", "Island", "Sol Ring"),
    )
    right = _permission_runtime(
        ("Mystical Tutor",),
        library=("Sol Ring", "Island", "Dramatic Reversal"),
    )
    lr = _request(left, policy)
    rr = _request(right, policy)
    assert tuple(a.strategic_key() for a in lr.actions) == tuple(a.strategic_key() for a in rr.actions)
    assert policy.choose_request(lr).strategic_key() == policy.choose_request(rr).strategic_key()


def main():
    tests = (
        test_free_tutor_permission_beats_another_blind_urza_spin_in_main,
        test_own_bauble_free_probe_is_worse_than_ending_turn,
        test_priority_spin_is_deferred_until_current_stack_clears,
        test_x0_reshape_is_real_but_lower_priority_than_free_mystical_tutor,
        test_permission_choice_is_hidden_future_invariant,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("URZA POLICY EXTENSION SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
