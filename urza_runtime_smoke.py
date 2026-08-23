#!/usr/bin/env python3
"""Focused Phase-2 smokes for Urza spin and persistent permissions."""

import urza_solver as solver
import non_oracle_rules_adapter as rules
from non_oracle_base_policy import DeterministicBasePolicy
from non_oracle_runtime import ACTION_PASS_PRIORITY, make_runtime_state
from non_oracle_urza_runtime import (
    ACT_URZA_SPIN,
    MAIN_ACTIVATE_URZA_SPIN,
    MAIN_USE_URZA_PERMISSION,
    USE_CAST_PROACTIVE,
    USE_CAST_PROBE,
)
from solver_architecture import InformationState
from urza_permission_adapter import UrzaPermissionState


def _request(runtime):
    return rules.rules_decision_request(runtime, horizon=6)


def _actions(runtime, kind):
    return [action for action in _request(runtime).actions if action.kind == kind]


def _pass(runtime):
    return next(action for action in _request(runtime).actions if action.action_id == ACTION_PASS_PRIORITY)


def _permission_runtime(card, *, hand=(), battlefield=(), blue=0, colorless=0, land_played=False, library=("TAIL",)):
    permissions = UrzaPermissionState().grant(card, 2)
    return make_runtime_state(
        solver.State(
            turn=2,
            library=tuple(library),
            hand=tuple(hand),
            battlefield=tuple(battlefield),
            exile=(card,),
            blue=blue,
            colorless=colorless,
            land_played=land_played,
        ),
        permissions=permissions,
    )


def _permission_action(runtime, *, use=None, card=None):
    rows = _actions(runtime, MAIN_USE_URZA_PERMISSION)
    if use is not None:
        rows = [a for a in rows if dict(a.parameters).get("use") == use]
    if card is not None:
        rows = [a for a in rows if dict(a.parameters).get("card") == card]
    return rows


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


def test_proactive_nonartifact_permission_casts_free_from_exile():
    runtime = _permission_runtime("Rhystic Study")
    action = _permission_action(runtime, use=USE_CAST_PROACTIVE, card="Rhystic Study")[0]
    assert int(dict(action.parameters)["mana_spent"]) == 0
    runtime = rules.apply_main_action(runtime, action)
    assert "Rhystic Study" not in runtime.true_state.exile
    assert not runtime.permissions.permissions
    assert runtime.stack.top().card == "Rhystic Study"
    assert not solver.has(runtime.true_state, "Rhystic Study")

    runtime = rules.apply_main_action(runtime, _pass(runtime))
    assert solver.has(runtime.true_state, "Rhystic Study")


def test_targeted_proactive_permission_commits_public_target_before_resolution():
    runtime = _permission_runtime(
        "Power Artifact",
        battlefield=(solver.Perm("Grim Monolith"), solver.Perm("Basalt Monolith")),
    )
    actions = _permission_action(runtime, use=USE_CAST_PROACTIVE, card="Power Artifact")
    assert len(actions) == 2
    action = next(
        a for a in actions
        if tuple(dict(a.parameters)["target_signature"])[0] == "Grim Monolith"
    )
    runtime = rules.apply_main_action(runtime, action)
    assert runtime.stack.top().card == "Power Artifact"
    assert runtime.true_state.pa_target == ""
    runtime = rules.apply_main_action(runtime, _pass(runtime))
    assert runtime.true_state.pa_target == "Grim Monolith"


def test_probe_permission_draws_only_when_free_spell_resolves():
    runtime = _permission_runtime("Gitaxian Probe", library=("DRAW", "TAIL"))
    action = _permission_action(runtime, use=USE_CAST_PROBE, card="Gitaxian Probe")[0]
    assert int(dict(action.parameters)["mana_spent"]) == 0
    runtime = rules.apply_main_action(runtime, action)
    assert runtime.true_state.hand == ()
    assert runtime.stack.top().card == "Gitaxian Probe"
    assert "Gitaxian Probe" not in runtime.true_state.exile
    assert not runtime.permissions.permissions

    runtime = rules.apply_main_action(runtime, _pass(runtime))
    assert runtime.true_state.hand == ("DRAW",)
    assert "Gitaxian Probe" in runtime.true_state.graveyard


def test_priority_spin_is_hidden_future_invariant_and_sits_above_older_spell():
    def build(library):
        return make_runtime_state(solver.State(
            turn=2,
            library=tuple(library),
            hand=("Sol Ring",),
            battlefield=(solver.Perm(solver.COMMANDER),),
            urza=True,
            commander_in_command_zone=False,
            colorless=6,
        ))

    left = build(("SECRET_A", "SECRET_B"))
    right = build(("SECRET_B", "SECRET_A"))
    left_cast = next(a for a in _request(left).actions if a.kind == "main_cast_artifact" and dict(a.parameters)["card"] == "Sol Ring")
    right_cast = next(a for a in _request(right).actions if a.kind == "main_cast_artifact" and dict(a.parameters)["card"] == "Sol Ring")
    left = rules.apply_main_action(left, left_cast)
    right = rules.apply_main_action(right, right_cast)

    la = [a for a in _actions(left, MAIN_ACTIVATE_URZA_SPIN) if bool(dict(a.parameters).get("priority"))]
    ra = [a for a in _actions(right, MAIN_ACTIVATE_URZA_SPIN) if bool(dict(a.parameters).get("priority"))]
    assert tuple(a.strategic_key() for a in la) == tuple(a.strategic_key() for a in ra)
    assert len(la) == 1
    left = rules.apply_main_action(left, la[0])
    assert left.true_state.colorless == 0
    assert tuple(obj.kind for obj in left.stack.objects) == (ACT_URZA_SPIN, "artifact_spell")
    assert left.true_state.exile == ()


def test_priority_permission_respects_native_and_floodcaller_flash_timing():
    # Banishing Knack is an instant and may be used over an older spell.
    runtime = _permission_runtime(
        "Banishing Knack",
        hand=("Sol Ring",),
        battlefield=(solver.Perm("Battered Golem"),),
        colorless=1,
    )
    cast = next(a for a in _request(runtime).actions if a.kind == "main_cast_artifact" and dict(a.parameters)["card"] == "Sol Ring")
    runtime = rules.apply_main_action(runtime, cast)
    instant = _permission_action(runtime, use=USE_CAST_PROACTIVE, card="Banishing Knack")
    assert instant and all(bool(dict(a.parameters).get("priority")) for a in instant)
    runtime = rules.apply_main_action(runtime, instant[0])
    assert runtime.stack.top().card == "Banishing Knack"
    runtime = rules.apply_main_action(runtime, _pass(runtime))
    assert any(p.knack_granted for p in runtime.true_state.battlefield if p.name == "Battered Golem")
    assert runtime.stack.top().card == "Sol Ring"

    # Rhystic Study is not normally instant-speed.
    runtime = _permission_runtime("Rhystic Study", hand=("Sol Ring",), colorless=1)
    cast = next(a for a in _request(runtime).actions if a.kind == "main_cast_artifact")
    runtime = rules.apply_main_action(runtime, cast)
    assert not _permission_action(runtime, use=USE_CAST_PROACTIVE, card="Rhystic Study")

    # Floodcaller grants flash to that noncreature spell.
    runtime = _permission_runtime(
        "Rhystic Study",
        hand=("Sol Ring",),
        battlefield=(solver.Perm("Valley Floodcaller"),),
        colorless=1,
    )
    cast = next(a for a in _request(runtime).actions if a.kind == "main_cast_artifact")
    runtime = rules.apply_main_action(runtime, cast)
    flashed = _permission_action(runtime, use=USE_CAST_PROACTIVE, card="Rhystic Study")
    assert flashed and all(bool(dict(a.parameters).get("priority")) for a in flashed)

    # Floodcaller does not grant flash to creature spells.
    runtime = _permission_runtime(
        "Forensic Gadgeteer",
        hand=("Sol Ring",),
        battlefield=(solver.Perm("Valley Floodcaller"),),
        colorless=1,
    )
    cast = next(a for a in _request(runtime).actions if a.kind == "main_cast_artifact")
    runtime = rules.apply_main_action(runtime, cast)
    assert not _permission_action(runtime, use=USE_CAST_PROACTIVE, card="Forensic Gadgeteer")


def test_unsupported_reactive_permission_remains_public_but_not_falsely_castable():
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
        test_proactive_nonartifact_permission_casts_free_from_exile,
        test_targeted_proactive_permission_commits_public_target_before_resolution,
        test_probe_permission_draws_only_when_free_spell_resolves,
        test_priority_spin_is_hidden_future_invariant_and_sits_above_older_spell,
        test_priority_permission_respects_native_and_floodcaller_flash_timing,
        test_unsupported_reactive_permission_remains_public_but_not_falsely_castable,
        test_base_policy_uses_known_artifact_permission_before_spinning_again,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("URZA SPIN / PERMISSION RUNTIME SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
