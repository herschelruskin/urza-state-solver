#!/usr/bin/env python3
"""Focused Phase-2 smokes for Sewer-veillance Cam ETB/LTB staging."""

import urza_solver as solver
import non_oracle_rules_adapter as rules
from non_oracle_cam_runtime import (
    DECISION_CAM_EFFECT,
    DECISION_CAM_TARGET,
    queue_cam_ltb,
)
from non_oracle_runtime import ACTION_PASS_PRIORITY, make_runtime_state, record_artifact_entry


def _choose_kind(runtime, kind):
    request = rules.rules_decision_request(runtime, horizon=6)
    return next(action for action in request.actions if action.kind == kind)


def test_cam_target_is_chosen_before_simultaneous_stack_order():
    runtime = make_runtime_state(
        solver.State(
            turn=2,
            library=("SECRET",),
            hand=(),
            battlefield=(
                solver.Perm("Grinding Station", tapped=True),
                solver.Perm("Battered Golem", tapped=True, sick=False),
                solver.Perm("Sewer-veillance Cam"),
            ),
        )
    )
    runtime = record_artifact_entry(runtime, ("Sewer-veillance Cam",), source="test Cam ETB")
    request = rules.rules_decision_request(runtime, horizon=6)
    assert request.actions and all(a.kind == DECISION_CAM_TARGET for a in request.actions)
    assert "SECRET" not in repr(request.actions)
    target = next(
        action for action in request.actions
        if tuple(dict(action.parameters)["target_signature"])[0] == "Battered Golem"
    )
    runtime = rules.apply_main_action(runtime, target)
    request = rules.rules_decision_request(runtime, horizon=6)
    assert request.actions and all(a.kind == "runtime_stack_order" for a in request.actions)
    labels = "\n".join(action.label for action in request.actions)
    assert "etb_cam" in labels and "etb_producer" in labels


def test_cam_target_request_is_hidden_future_invariant():
    def build(library):
        runtime = make_runtime_state(
            solver.State(
                turn=2,
                library=tuple(library),
                hand=(),
                battlefield=(
                    solver.Perm("Battered Golem", tapped=True, sick=False),
                    solver.Perm("Sewer-veillance Cam"),
                ),
            )
        )
        return record_artifact_entry(runtime, ("Sewer-veillance Cam",), source="Cam ETB")

    left = rules.rules_decision_request(build(("SECRET_A", "TAIL")), horizon=6)
    right = rules.rules_decision_request(build(("SECRET_B", "TAIL")), horizon=6)
    assert left.observation.key() == right.observation.key()
    assert tuple(a.strategic_key() for a in left.actions) == tuple(a.strategic_key() for a in right.actions)


def test_cam_resolution_exposes_may_tap_or_untap_then_applies_choice():
    runtime = make_runtime_state(
        solver.State(
            turn=2,
            library=(),
            hand=(),
            battlefield=(
                solver.Perm("Battered Golem", tapped=True, sick=False),
                solver.Perm("Sewer-veillance Cam"),
            ),
        )
    )
    runtime = record_artifact_entry(runtime, ("Sewer-veillance Cam",), source="Cam ETB")
    target = _choose_kind(runtime, DECISION_CAM_TARGET)
    runtime = rules.apply_main_action(runtime, target)
    request = rules.rules_decision_request(runtime, horizon=6)
    assert len(request.actions) == 1 and request.actions[0].action_id == ACTION_PASS_PRIORITY
    runtime = rules.apply_main_action(runtime, request.actions[0])
    request = rules.rules_decision_request(runtime, horizon=6)
    assert request.actions and all(a.kind == DECISION_CAM_EFFECT for a in request.actions)
    choices = {dict(a.parameters)["choice"] for a in request.actions}
    assert choices == {"decline", "untap"}
    untap = next(a for a in request.actions if dict(a.parameters)["choice"] == "untap")
    runtime = rules.apply_main_action(runtime, untap)
    golem = next(p for p in runtime.true_state.battlefield if p.name == "Battered Golem")
    assert not golem.tapped


def test_cam_ltb_uses_same_target_before_order_boundary():
    runtime = make_runtime_state(
        solver.State(
            turn=3,
            library=(),
            hand=(),
            battlefield=(solver.Perm("Spellseeker", tapped=False, sick=False),),
        )
    )
    runtime = queue_cam_ltb(runtime, count=1, source="test Cam LTB")
    request = rules.rules_decision_request(runtime, horizon=6)
    assert request.actions and all(a.kind == DECISION_CAM_TARGET for a in request.actions)
    runtime = rules.apply_main_action(runtime, request.actions[0])
    assert runtime.stack.top().kind == "ltb_cam"


def test_cam_with_no_legal_creature_target_creates_no_trigger():
    runtime = make_runtime_state(
        solver.State(
            turn=2,
            library=(),
            hand=(),
            battlefield=(solver.Perm("Sewer-veillance Cam"),),
        )
    )
    runtime = record_artifact_entry(runtime, ("Sewer-veillance Cam",), source="Cam ETB")
    assert runtime.pending is None
    assert runtime.stack.objects == ()


def main():
    tests = (
        test_cam_target_is_chosen_before_simultaneous_stack_order,
        test_cam_target_request_is_hidden_future_invariant,
        test_cam_resolution_exposes_may_tap_or_untap_then_applies_choice,
        test_cam_ltb_uses_same_target_before_order_boundary,
        test_cam_with_no_legal_creature_target_creates_no_trigger,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("CAM RUNTIME SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
