#!/usr/bin/env python3
"""Focused Phase-2 smokes for Grinding Station and Codex self-mill."""

import urza_solver as solver
import non_oracle_rules_adapter as rules
from non_oracle_base_policy import DeterministicBasePolicy
from non_oracle_mill_runtime import (
    ACT_CODEX_MILL,
    ACT_STATION_MILL,
    MAIN_ACTIVATE_CODEX_MILL,
    MAIN_ACTIVATE_STATION_MILL,
    PRIORITY_ACTIVATE_STATION_MILL,
)
from non_oracle_runtime import ACTION_PASS_PRIORITY, make_runtime_state
from solver_architecture import InformationState


def _request(runtime):
    return rules.rules_decision_request(runtime, horizon=6)


def _actions(runtime, kind):
    return [action for action in _request(runtime).actions if action.kind == kind]


def _pass(runtime):
    return next(action for action in _request(runtime).actions if action.action_id == ACTION_PASS_PRIORITY)


def _chip_board(*extras):
    return (
        solver.Perm("The Reality Chip", mode="chip_attached"),
        solver.Perm("Artificer's Assistant"),
    ) + tuple(extras)


def test_station_main_actions_are_hidden_future_invariant():
    def build(library):
        return make_runtime_state(solver.State(
            turn=2,
            library=tuple(library),
            hand=(),
            battlefield=_chip_board(
                solver.Perm("Grinding Station"),
                solver.Perm("Clue", mode="clue"),
            ),
            chip_attached=True,
            chip_target="Artificer's Assistant",
        ))
    left = _request(build(("SECRET_A", "SECRET_B", "TAIL")))
    right = _request(build(("SECRET_B", "SECRET_A", "TAIL")))
    la = tuple(a.strategic_key() for a in left.actions if a.kind == MAIN_ACTIVATE_STATION_MILL)
    ra = tuple(a.strategic_key() for a in right.actions if a.kind == MAIN_ACTIVATE_STATION_MILL)
    assert la == ra and la
    assert "SECRET_A" not in repr(la) and "SECRET_B" not in repr(la)


def test_station_taps_and_sacrifices_as_cost_then_mills_only_on_resolution():
    runtime = make_runtime_state(solver.State(
        turn=2,
        library=("A", "B", "C", "D"),
        hand=(),
        battlefield=_chip_board(
            solver.Perm("Grinding Station"),
            solver.Perm("Clue", mode="clue"),
        ),
        chip_attached=True,
        chip_target="Artificer's Assistant",
    ))
    action = next(
        a for a in _actions(runtime, MAIN_ACTIVATE_STATION_MILL)
        if dict(a.parameters)["sacrifice_name"] == "Clue"
    )
    runtime = rules.apply_main_action(runtime, action)
    station = next(p for p in runtime.true_state.battlefield if p.name == "Grinding Station")
    assert station.tapped
    assert not any(p.mode == "clue" for p in runtime.true_state.battlefield)
    assert runtime.true_state.library == ("A", "B", "C", "D")
    assert runtime.stack.top().kind == ACT_STATION_MILL

    runtime = rules.apply_main_action(runtime, _pass(runtime))
    assert runtime.true_state.library == ("D",)
    assert runtime.true_state.graveyard[-3:] == ("A", "B", "C")


def test_station_can_sacrifice_itself_and_pending_ability_still_resolves():
    runtime = make_runtime_state(solver.State(
        turn=2,
        library=("A", "B", "C"),
        hand=("Scour for Scrap",),
        battlefield=(solver.Perm("Grinding Station"),),
    ))
    action = next(
        a for a in _actions(runtime, MAIN_ACTIVATE_STATION_MILL)
        if dict(a.parameters)["sacrifice_name"] == "Grinding Station"
    )
    runtime = rules.apply_main_action(runtime, action)
    assert not solver.has(runtime.true_state, "Grinding Station")
    assert "Grinding Station" in runtime.true_state.graveyard
    assert runtime.stack.top().kind == ACT_STATION_MILL
    runtime = rules.apply_main_action(runtime, _pass(runtime))
    assert runtime.true_state.library == ()
    assert runtime.true_state.graveyard[-3:] == ("A", "B", "C")


def test_prized_statue_death_trigger_is_above_pending_station_mill():
    runtime = make_runtime_state(solver.State(
        turn=2,
        library=("A", "B", "C", "D"),
        hand=("Scour for Scrap",),
        battlefield=(
            solver.Perm("Grinding Station"),
            solver.Perm("Prized Statue"),
        ),
    ))
    action = next(
        a for a in _actions(runtime, MAIN_ACTIVATE_STATION_MILL)
        if dict(a.parameters)["sacrifice_name"] == "Prized Statue"
    )
    runtime = rules.apply_main_action(runtime, action)
    assert tuple(obj.kind for obj in runtime.stack.objects)[:2] == (
        "prized_dies_treasure",
        ACT_STATION_MILL,
    )
    assert runtime.true_state.library == ("A", "B", "C", "D")

    runtime = rules.apply_main_action(runtime, _pass(runtime))
    assert any(p.mode == "treasure" for p in runtime.true_state.battlefield)
    assert runtime.true_state.library == ("A", "B", "C", "D")
    # Treasure entry creates a new producer trigger above the older mill ability.
    assert runtime.stack.objects and runtime.stack.objects[-1].kind == ACT_STATION_MILL


def test_cam_sacrifice_stages_ltb_target_before_station_can_mill():
    runtime = make_runtime_state(solver.State(
        turn=2,
        library=("A", "B", "C"),
        hand=("Scour for Scrap",),
        battlefield=(
            solver.Perm("Grinding Station"),
            solver.Perm("Sewer-veillance Cam"),
            solver.Perm("Artificer's Assistant"),
        ),
    ))
    action = next(
        a for a in _actions(runtime, MAIN_ACTIVATE_STATION_MILL)
        if dict(a.parameters)["sacrifice_name"] == "Sewer-veillance Cam"
    )
    runtime = rules.apply_main_action(runtime, action)
    assert runtime.pending is not None
    assert runtime.pending.kind == "runtime_cam_target"
    assert runtime.true_state.library == ("A", "B", "C")
    assert any(obj.kind == ACT_STATION_MILL for obj in runtime.stack.objects)


def test_codex_mill_updates_known_top_only_when_ability_resolves():
    runtime = make_runtime_state(
        solver.State(
            turn=2,
            library=("A", "B", "C"),
            hand=(),
            battlefield=_chip_board(solver.Perm("Codex Shredder")),
            chip_attached=True,
            chip_target="Artificer's Assistant",
        ),
        InformationState(known_top=("A", "B", "C")),
    )
    action = _actions(runtime, MAIN_ACTIVATE_CODEX_MILL)[0]
    runtime = rules.apply_main_action(runtime, action)
    codex = next(p for p in runtime.true_state.battlefield if p.name == "Codex Shredder")
    assert codex.tapped
    assert runtime.true_state.library == ("A", "B", "C")
    assert runtime.information.known_top == ("A", "B", "C")
    assert runtime.stack.top().kind == ACT_CODEX_MILL

    runtime = rules.apply_main_action(runtime, _pass(runtime))
    assert runtime.true_state.library == ("B", "C")
    assert runtime.true_state.graveyard[-1:] == ("A",)
    assert runtime.information.known_top[:2] == ("B", "C")


def test_station_can_activate_at_priority_above_unrelated_spell():
    runtime = make_runtime_state(solver.State(
        turn=2,
        library=("A", "B", "C", "D"),
        hand=("Sol Ring", "Scour for Scrap"),
        battlefield=(
            solver.Perm("Grinding Station"),
            solver.Perm("Clue", mode="clue"),
        ),
        colorless=1,
    ))
    cast = next(
        a for a in _request(runtime).actions
        if a.kind == "main_cast_artifact" and dict(a.parameters)["card"] == "Sol Ring"
    )
    runtime = rules.apply_main_action(runtime, cast)
    station = next(
        a for a in _actions(runtime, PRIORITY_ACTIVATE_STATION_MILL)
        if dict(a.parameters)["sacrifice_name"] == "Clue"
    )
    runtime = rules.apply_main_action(runtime, station)
    assert runtime.stack.top().kind == ACT_STATION_MILL
    assert runtime.stack.objects[-1].card == "Sol Ring"
    runtime = rules.apply_main_action(runtime, _pass(runtime))
    assert runtime.true_state.library == ("D",)
    assert runtime.stack.objects and runtime.stack.objects[-1].card == "Sol Ring"


def test_base_policy_uses_codex_to_clear_a_known_low_value_top():
    runtime = make_runtime_state(
        solver.State(
            turn=2,
            library=("Force of Will", "Basalt Monolith"),
            hand=(),
            battlefield=_chip_board(solver.Perm("Codex Shredder")),
            chip_attached=True,
            chip_target="Artificer's Assistant",
        ),
        InformationState(known_top=("Force of Will", "Basalt Monolith")),
    )
    policy = DeterministicBasePolicy()
    request = rules.rules_decision_request(runtime, horizon=6, policy_id=policy.policy_id)
    choice = policy.choose_request(request)
    assert choice.kind == MAIN_ACTIVATE_CODEX_MILL


def main():
    tests = (
        test_station_main_actions_are_hidden_future_invariant,
        test_station_taps_and_sacrifices_as_cost_then_mills_only_on_resolution,
        test_station_can_sacrifice_itself_and_pending_ability_still_resolves,
        test_prized_statue_death_trigger_is_above_pending_station_mill,
        test_cam_sacrifice_stages_ltb_target_before_station_can_mill,
        test_codex_mill_updates_known_top_only_when_ability_resolves,
        test_station_can_activate_at_priority_above_unrelated_spell,
        test_base_policy_uses_codex_to_clear_a_known_low_value_top,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("MILL RUNTIME SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
