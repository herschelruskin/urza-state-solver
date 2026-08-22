#!/usr/bin/env python3
"""Focused regressions for the Phase-2 public main-phase rules adapter."""

import inspect

import urza_solver as solver
from non_oracle_rules_adapter import (
    MAIN_CAST_ARTIFACT,
    MAIN_MANA_ACTION,
    MAIN_PLAY_LAND,
    apply_main_action,
    main_phase_intents,
    rules_decision_request,
)
from non_oracle_runtime import make_runtime_state


def action_strategic_keys(runtime):
    return tuple(action.strategic_key() for action in main_phase_intents(runtime))


def test_main_action_set_is_hidden_future_invariant():
    battlefield = (
        solver.Perm("Island"),
        solver.Perm("Sol Ring"),
    )
    hand = ("Island", "Welding Jar", "Prized Statue")
    left = make_runtime_state(
        solver.State(
            turn=2,
            library=("SECRET_A", "SECRET_B", "SECRET_C"),
            hand=hand,
            battlefield=battlefield,
            blue=0,
            colorless=0,
        )
    )
    right = make_runtime_state(
        solver.State(
            turn=2,
            library=("SECRET_C", "SECRET_A", "SECRET_B"),
            hand=hand,
            battlefield=battlefield,
            blue=0,
            colorless=0,
        )
    )
    lreq = rules_decision_request(left, horizon=6)
    rreq = rules_decision_request(right, horizon=6)
    assert lreq.observation.key() == rreq.observation.key()
    assert action_strategic_keys(left) == action_strategic_keys(right)
    assert "SECRET_A" not in repr(lreq)
    assert "SECRET_B" not in repr(lreq)


def test_public_land_and_mana_actions_are_exposed_without_oracle_successors():
    runtime = make_runtime_state(
        solver.State(
            turn=1,
            library=("Hidden",),
            hand=("Island",),
            battlefield=(solver.Perm("Sol Ring"),),
        )
    )
    actions = main_phase_intents(runtime)
    assert any(a.kind == MAIN_PLAY_LAND and dict(a.parameters)["card"] == "Island" for a in actions)
    assert any(a.kind == MAIN_MANA_ACTION and "Sol Ring" in a.label for a in actions)
    assert all(not hasattr(a, "true_state") for a in actions)


def test_seat_play_creates_typed_artifact_entry_stack():
    runtime = make_runtime_state(
        solver.State(
            turn=2,
            library=(),
            hand=("Seat of the Synod",),
            battlefield=(solver.Perm("Grinding Station", tapped=True),),
        )
    )
    action = next(
        a for a in main_phase_intents(runtime)
        if a.kind == MAIN_PLAY_LAND and dict(a.parameters)["card"] == "Seat of the Synod"
    )
    runtime = apply_main_action(runtime, action)
    assert runtime.true_state.land_played
    assert any(p.name == "Seat of the Synod" for p in runtime.true_state.battlefield)
    assert runtime.stack.top() is not None
    assert runtime.stack.top().kind == "etb_producer"
    assert runtime.true_state.oracle_stack == ()


def test_ordinary_artifact_cast_commits_payment_then_enters_runtime_stack():
    runtime = make_runtime_state(
        solver.State(
            turn=2,
            library=("Unseen", "Tail"),
            hand=("Prized Statue",),
            battlefield=(solver.Perm("Sol Ring"),),
            colorless=2,
        )
    )
    action = next(a for a in main_phase_intents(runtime) if a.kind == MAIN_CAST_ARTIFACT)
    assert dict(action.parameters)["card"] == "Prized Statue"
    assert "Unseen" not in repr(action)
    runtime = apply_main_action(runtime, action)
    assert runtime.true_state.colorless == 0
    assert "Prized Statue" not in runtime.true_state.hand
    assert runtime.stack.top() is not None
    assert any(obj.object_type == "spell" and obj.card == "Prized Statue" for obj in runtime.stack.objects)
    assert not any(p.name == "Prized Statue" for p in runtime.true_state.battlefield)


def test_mana_action_application_is_hidden_library_independent():
    def one(library):
        return make_runtime_state(
            solver.State(
                turn=1,
                library=library,
                hand=(),
                battlefield=(solver.Perm("Sol Ring"),),
            )
        )
    left = one(("A", "B"))
    right = one(("B", "A"))
    la = next(a for a in main_phase_intents(left) if a.kind == MAIN_MANA_ACTION)
    ra = next(a for a in main_phase_intents(right) if a.kind == MAIN_MANA_ACTION)
    assert la.strategic_key() == ra.strategic_key()
    left2 = apply_main_action(left, la)
    right2 = apply_main_action(right, ra)
    assert left2.true_state.colorless == right2.true_state.colorless == 2
    assert left2.true_state.battlefield == right2.true_state.battlefield
    assert left2.true_state.library == ("A", "B")
    assert right2.true_state.library == ("B", "A")


def test_special_artifact_casts_are_not_silently_misrepresented():
    runtime = make_runtime_state(
        solver.State(
            turn=2,
            library=(),
            hand=("Mox Diamond", "Everflowing Chalice", "Chrome Mox"),
            battlefield=(),
        )
    )
    casts = {
        dict(a.parameters)["card"]
        for a in main_phase_intents(runtime)
        if a.kind == MAIN_CAST_ARTIFACT
    }
    assert "Chrome Mox" in casts
    assert "Mox Diamond" not in casts
    assert "Everflowing Chalice" not in casts


def test_rules_request_switches_to_runtime_stack_request_after_cast():
    runtime = make_runtime_state(
        solver.State(
            turn=2,
            library=(),
            hand=("Welding Jar",),
            battlefield=(),
        )
    )
    request = rules_decision_request(runtime, horizon=6)
    cast = next(a for a in request.actions if a.kind == MAIN_CAST_ARTIFACT)
    runtime = apply_main_action(runtime, cast)
    stack_request = rules_decision_request(runtime, horizon=6)
    assert len(stack_request.actions) == 1
    assert stack_request.actions[0].kind == "pass_priority"
    assert stack_request.observation.pending_stack_objects


def test_adapter_policy_boundary_has_no_raw_state_in_request_api():
    params = tuple(inspect.signature(rules_decision_request).parameters)
    assert params[0] == "runtime"
    runtime = make_runtime_state(
        solver.State(turn=1, library=("Hidden",), hand=(), battlefield=())
    )
    request = rules_decision_request(runtime, horizon=6)
    assert not hasattr(request, "true_state")
    assert not hasattr(request.observation, "true_state")
    assert not hasattr(request.observation.base, "library")


def main():
    tests = (
        test_main_action_set_is_hidden_future_invariant,
        test_public_land_and_mana_actions_are_exposed_without_oracle_successors,
        test_seat_play_creates_typed_artifact_entry_stack,
        test_ordinary_artifact_cast_commits_payment_then_enters_runtime_stack,
        test_mana_action_application_is_hidden_library_independent,
        test_special_artifact_casts_are_not_silently_misrepresented,
        test_rules_request_switches_to_runtime_stack_request_after_cast,
        test_adapter_policy_boundary_has_no_raw_state_in_request_api,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("NON-ORACLE RULES ADAPTER SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
