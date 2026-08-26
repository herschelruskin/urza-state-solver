#!/usr/bin/env python3
"""Production-import regression for search effects that put Cam onto the battlefield.

Phase 5 must install Cam's typed runtime dispatch before Urza permission extensions
import Transmute/Bay/search modules. Otherwise those modules bind the core pre-Cam
artifact-entry helper by name and a searched Sewer-veillance Cam hits the old
NotImplementedError instead of staging its required ETB target choice.

This smoke executes the real Transmute path through ``non_oracle_rules_adapter_v2``:
cast -> resolve -> sacrifice Sol Ring (MV1) -> find Cam (MV1) -> Cam enters -> choose
its ETB target -> resolve -> choose tap/untap effect.
"""

import urza_solver as solver
from non_oracle_rules_adapter_v2 import apply_main_action, rules_decision_request
from non_oracle_runtime import make_runtime_state
from non_oracle_cam_runtime import DECISION_CAM_EFFECT, DECISION_CAM_TARGET


def _request(runtime):
    return rules_decision_request(runtime, horizon=6, policy_id="cam-search-entry-smoke")


def _action(runtime, *, kind, label_contains="", target=""):
    rows = [action for action in _request(runtime).actions if action.kind == kind]
    if label_contains:
        rows = [action for action in rows if label_contains in action.label]
    if target:
        rows = [action for action in rows if dict(action.parameters).get("target") == target]
    if not rows:
        raise AssertionError(
            f"no action kind={kind!r} label={label_contains!r} target={target!r}"
        )
    return sorted(rows, key=lambda action: action.action_id)[0]


def test_transmute_cam_entry_uses_typed_target_boundary():
    runtime = make_runtime_state(solver.State(
        turn=2,
        library=("Sewer-veillance Cam", "Island"),
        hand=("Transmute Artifact",),
        battlefield=(
            solver.Perm("Sol Ring"),
            solver.Perm("Artificer's Assistant", sick=False),
        ),
        blue=2,
        rng_root_seed=20260826,
    ))

    runtime = apply_main_action(
        runtime,
        _action(runtime, kind="main_use_transmute_artifact"),
    )
    runtime = apply_main_action(runtime, _action(runtime, kind="pass_priority"))
    runtime = apply_main_action(
        runtime,
        _action(runtime, kind="transmute_choose_sacrifice", label_contains="Sol Ring"),
    )
    runtime = apply_main_action(
        runtime,
        _action(runtime, kind="transmute_choose_target", target="Sewer-veillance Cam"),
    )

    assert any(p.name == "Sewer-veillance Cam" for p in runtime.true_state.battlefield)
    assert runtime.pending is not None
    assert runtime.pending.kind == DECISION_CAM_TARGET

    target = _action(runtime, kind=DECISION_CAM_TARGET, label_contains="Artificer's Assistant")
    runtime = apply_main_action(runtime, target)
    assert runtime.pending is None
    assert runtime.stack.objects
    assert runtime.stack.top().kind == "etb_cam"

    runtime = apply_main_action(runtime, _action(runtime, kind="pass_priority"))
    assert runtime.pending is not None
    assert runtime.pending.kind == DECISION_CAM_EFFECT
    effect = _action(runtime, kind=DECISION_CAM_EFFECT, label_contains="tap Artificer's Assistant")
    runtime = apply_main_action(runtime, effect)
    assistant = next(p for p in runtime.true_state.battlefield if p.name == "Artificer's Assistant")
    assert assistant.tapped
    print("Transmute -> Cam ETB typed target/effect boundary: PASS")


def main():
    test_transmute_cam_entry_uses_typed_target_boundary()
    print("PHASE5 CAM SEARCH-ENTRY SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
