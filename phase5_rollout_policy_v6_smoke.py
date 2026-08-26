#!/usr/bin/env python3
"""Focused regressions for Phase-5 rollout policy V6."""

import urza_solver as solver
from non_oracle_rules_adapter_v2 import rules_decision_request
from non_oracle_runtime import make_runtime_state
from non_oracle_urza_runtime import MAIN_USE_URZA_PERMISSION
from phase5_rollout_policy_v6 import DeterministicRolloutPolicyV6
from urza_permission_adapter import UrzaPermissionState

POLICY = DeterministicRolloutPolicyV6()


def _request(runtime):
    return rules_decision_request(runtime, horizon=6, policy_id=POLICY.policy_id)


def _score(runtime, action):
    request = _request(runtime)
    return POLICY.action_score(request.observation, action, request.context)


def test_urza_permission_power_artifact_requires_meaningful_target():
    def build(target):
        permissions = UrzaPermissionState().grant("Power Artifact", 2)
        return make_runtime_state(
            solver.State(
                turn=2,
                library=(),
                hand=(),
                battlefield=(
                    solver.Perm(solver.COMMANDER, sick=False),
                    solver.Perm(target),
                ),
                exile=("Power Artifact",),
                urza=True,
                commander_in_command_zone=False,
            ),
            permissions=permissions,
        )

    bad = build("Giant's Boulder")
    bad_action = next(
        action for action in _request(bad).actions
        if action.kind == MAIN_USE_URZA_PERMISSION
        and dict(action.parameters).get("card") == "Power Artifact"
    )
    assert _score(bad, bad_action) < 0

    good = build("Basalt Monolith")
    good_action = next(
        action for action in _request(good).actions
        if action.kind == MAIN_USE_URZA_PERMISSION
        and dict(action.parameters).get("card") == "Power Artifact"
    )
    assert _score(good, good_action) > 200
    print("V6 Urza-permission Power Artifact target discipline: PASS")


def test_reshape_protects_visible_knack_producer():
    runtime = make_runtime_state(solver.State(
        turn=3,
        library=("Tormod's Crypt", "Island"),
        hand=("Reshape",),
        battlefield=(
            solver.Perm("Battered Golem", sick=False, knack_granted=True),
            solver.Perm("Mox Opal"),
        ),
        blue=2,
    ))
    actions = [
        action for action in _request(runtime).actions
        if action.kind == "main_use_x_artifact_tutor"
        and dict(action.parameters).get("source") == "Reshape"
        and int(dict(action.parameters).get("x", -1)) == 0
    ]
    golem = next(a for a in actions if dict(a.parameters).get("sacrifice_name") == "Battered Golem")
    mox = next(a for a in actions if dict(a.parameters).get("sacrifice_name") == "Mox Opal")
    assert _score(runtime, golem) < -100
    assert _score(runtime, mox) > _score(runtime, golem)
    print("V6 Reshape protects visible Knack producer: PASS")


def test_mox_diamond_without_land_needs_cast_trigger_payoff():
    plain = make_runtime_state(solver.State(
        turn=2,
        library=("Island",),
        hand=("Mox Diamond",),
        battlefield=(),
    ))
    plain_action = next(
        action for action in _request(plain).actions
        if action.kind == "main_cast_utility_artifact"
        and dict(action.parameters).get("card") == "Mox Diamond"
    )
    assert _score(plain, plain_action) < 0

    triggered = make_runtime_state(solver.State(
        turn=2,
        library=("Island",),
        hand=("Mox Diamond",),
        battlefield=(solver.Perm("Artificer's Assistant", sick=False),),
    ))
    triggered_action = next(
        action for action in _request(triggered).actions
        if action.kind == "main_cast_utility_artifact"
        and dict(action.parameters).get("card") == "Mox Diamond"
    )
    assert _score(triggered, triggered_action) > _score(plain, plain_action)
    print("V6 no-land Mox Diamond requires visible cast-trigger value: PASS")


def main():
    test_urza_permission_power_artifact_requires_meaningful_target()
    test_reshape_protects_visible_knack_producer()
    test_mox_diamond_without_land_needs_cast_trigger_payoff()
    print("PHASE5 ROLLOUT V6 SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
