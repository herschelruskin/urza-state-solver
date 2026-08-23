#!/usr/bin/env python3
"""Focused Phase-2 smokes for Urza free X=0 Reshape/Whir permissions."""

import urza_solver as solver
import non_oracle_rules_adapter as rules
from non_oracle_runtime import ACTION_PASS_PRIORITY, make_runtime_state
from non_oracle_urza_runtime import MAIN_USE_URZA_PERMISSION
from non_oracle_urza_x_permission_runtime import USE_CAST_RESHAPE, USE_CAST_WHIR
from urza_permission_adapter import UrzaPermissionState


def _request(runtime):
    return rules.rules_decision_request(runtime, horizon=6)


def _pass(runtime):
    return next(a for a in _request(runtime).actions if a.action_id == ACTION_PASS_PRIORITY)


def _permission_runtime(
    card,
    *,
    library=("TAIL",),
    hand=(),
    battlefield=(),
    colorless=0,
):
    permissions = UrzaPermissionState().grant(card, 2)
    return make_runtime_state(
        solver.State(
            turn=2,
            library=tuple(library),
            hand=tuple(hand),
            battlefield=tuple(battlefield),
            exile=(card,),
            colorless=colorless,
        ),
        permissions=permissions,
    )


def _actions(runtime, use):
    return [
        a for a in _request(runtime).actions
        if a.kind == MAIN_USE_URZA_PERMISSION and dict(a.parameters).get("use") == use
    ]


def test_free_reshape_commits_x0_and_sacrifice_before_hidden_search():
    def build(library):
        return _permission_runtime(
            "Reshape",
            library=library,
            battlefield=(solver.Perm("Prized Statue"),),
        )

    left = build(("Mox Opal", "Sol Ring", "Island"))
    right = build(("Island", "Sol Ring", "Mox Opal"))
    la = _actions(left, USE_CAST_RESHAPE)
    ra = _actions(right, USE_CAST_RESHAPE)
    assert tuple(a.strategic_key() for a in la) == tuple(a.strategic_key() for a in ra)
    assert len(la) == 1
    assert int(dict(la[0].parameters)["x"]) == 0
    assert dict(la[0].parameters)["sacrifice_name"] == "Prized Statue"
    assert "Mox Opal" not in repr(la) and "Sol Ring" not in repr(la)

    left = rules.apply_main_action(left, la[0])
    assert "Reshape" not in left.true_state.exile
    assert not left.permissions.permissions
    assert not solver.has(left.true_state, "Prized Statue")
    assert [obj.kind for obj in left.stack.objects] == [
        "prized_dies_treasure", "x_artifact_reshape_spell"
    ]

    left = rules.apply_main_action(left, _pass(left))
    assert any(p.mode == "treasure" for p in left.true_state.battlefield)
    assert left.stack.top().kind == "x_artifact_reshape_spell"
    assert "Mox Opal" not in repr(_request(left).actions)

    left = rules.apply_main_action(left, _pass(left))
    request = _request(left)
    assert request.actions and all(a.kind == "x_artifact_search_target" for a in request.actions)
    targets = {dict(a.parameters).get("target") for a in request.actions}
    assert "Mox Opal" in targets
    assert "Sol Ring" not in targets


def test_free_reshape_cam_cost_stages_ltb_target_before_spell_resolution():
    runtime = _permission_runtime(
        "Reshape",
        library=("Mox Opal", "Island"),
        battlefield=(
            solver.Perm("Sewer-veillance Cam"),
            solver.Perm("Battered Golem"),
        ),
    )
    action = next(a for a in _actions(runtime, USE_CAST_RESHAPE) if dict(a.parameters)["sacrifice_name"] == "Sewer-veillance Cam")
    runtime = rules.apply_main_action(runtime, action)
    request = _request(runtime)
    assert request.actions and all(a.kind == "runtime_cam_target" for a in request.actions)
    assert runtime.stack.top().kind == "x_artifact_reshape_spell"
    target = next(
        a for a in request.actions
        if tuple(dict(a.parameters)["target_signature"])[0] == "Battered Golem"
    )
    runtime = rules.apply_main_action(runtime, target)
    assert runtime.stack.top().kind == "ltb_cam"
    assert runtime.stack.objects[-1].kind == "x_artifact_reshape_spell"


def test_free_whir_x0_searches_only_zero_mv_artifacts():
    runtime = _permission_runtime(
        "Whir of Invention",
        library=("Mox Opal", "Sol Ring", "Island"),
    )
    actions = _actions(runtime, USE_CAST_WHIR)
    assert len(actions) == 1
    assert int(dict(actions[0].parameters)["x"]) == 0
    assert int(dict(actions[0].parameters)["mana_spent"]) == 0
    runtime = rules.apply_main_action(runtime, actions[0])
    assert runtime.stack.top().kind == "x_artifact_whir_spell"
    assert "Mox Opal" not in repr(_request(runtime).actions)

    runtime = rules.apply_main_action(runtime, _pass(runtime))
    request = _request(runtime)
    assert request.actions and all(a.kind == "x_artifact_search_target" for a in request.actions)
    targets = {dict(a.parameters).get("target") for a in request.actions}
    assert "Mox Opal" in targets
    assert "Sol Ring" not in targets


def test_whir_is_native_priority_but_reshape_needs_floodcaller():
    # Whir is an instant, so an Urza permission may be used over another spell.
    whir = _permission_runtime(
        "Whir of Invention",
        library=("Mox Opal", "Island"),
        hand=("Sol Ring",),
        colorless=1,
    )
    cast = next(a for a in _request(whir).actions if a.kind == "main_cast_artifact")
    whir = rules.apply_main_action(whir, cast)
    whir_actions = _actions(whir, USE_CAST_WHIR)
    assert whir_actions and all(bool(dict(a.parameters).get("priority")) for a in whir_actions)

    # Reshape is a sorcery and cannot be cast at priority without Floodcaller.
    plain = _permission_runtime(
        "Reshape",
        library=("Mox Opal", "Island"),
        hand=("Sol Ring",),
        battlefield=(solver.Perm("Prized Statue"),),
        colorless=1,
    )
    cast = next(a for a in _request(plain).actions if a.kind == "main_cast_artifact")
    plain = rules.apply_main_action(plain, cast)
    assert not _actions(plain, USE_CAST_RESHAPE)

    flashed = _permission_runtime(
        "Reshape",
        library=("Mox Opal", "Island"),
        hand=("Sol Ring",),
        battlefield=(solver.Perm("Prized Statue"), solver.Perm("Valley Floodcaller")),
        colorless=1,
    )
    cast = next(a for a in _request(flashed).actions if a.kind == "main_cast_artifact")
    flashed = rules.apply_main_action(flashed, cast)
    reshape_actions = _actions(flashed, USE_CAST_RESHAPE)
    assert reshape_actions and all(bool(dict(a.parameters).get("priority")) for a in reshape_actions)


def test_sacrificing_only_vexing_bauble_avoids_its_free_spell_trigger():
    runtime = _permission_runtime(
        "Reshape",
        library=("Mox Opal", "Island"),
        battlefield=(solver.Perm("Vexing Bauble"),),
    )
    action = _actions(runtime, USE_CAST_RESHAPE)[0]
    assert not bool(dict(action.parameters)["will_be_countered_by_own_bauble"])
    runtime = rules.apply_main_action(runtime, action)
    assert not any(obj.kind == "vexing_bauble_counter" for obj in runtime.stack.objects)
    assert runtime.stack.top().kind == "x_artifact_reshape_spell"


def main():
    tests = (
        test_free_reshape_commits_x0_and_sacrifice_before_hidden_search,
        test_free_reshape_cam_cost_stages_ltb_target_before_spell_resolution,
        test_free_whir_x0_searches_only_zero_mv_artifacts,
        test_whir_is_native_priority_but_reshape_needs_floodcaller,
        test_sacrificing_only_vexing_bauble_avoids_its_free_spell_trigger,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("URZA X=0 PERMISSION RUNTIME SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
