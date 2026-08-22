#!/usr/bin/env python3
"""Focused Phase-2 smokes for Reality Chip reconfigure and Uthros Station."""

import urza_solver as solver
import non_oracle_rules_adapter as rules
from non_oracle_base_policy import DeterministicBasePolicy
from non_oracle_engine_activation_runtime import (
    ACT_CHIP_RECONFIGURE,
    ACT_UTHROS_STATION,
    MAIN_ACTIVATE_CHIP_RECONFIGURE,
    MAIN_ACTIVATE_UTHROS_STATION,
)
from non_oracle_runtime import ACTION_PASS_PRIORITY, make_runtime_state


def _request(runtime):
    return rules.rules_decision_request(runtime, horizon=6)


def _actions(runtime, kind):
    return [action for action in _request(runtime).actions if action.kind == kind]


def _pass(runtime):
    return next(action for action in _request(runtime).actions if action.action_id == ACTION_PASS_PRIORITY)


def test_chip_reconfigure_actions_are_hidden_future_invariant():
    def build(library):
        return make_runtime_state(solver.State(
            turn=2,
            library=tuple(library),
            hand=(),
            battlefield=(
                solver.Perm("The Reality Chip"),
                solver.Perm("Artificer's Assistant"),
            ),
            blue=1,
            colorless=2,
        ))
    left = _request(build(("SECRET_A", "SECRET_B")))
    right = _request(build(("SECRET_B", "SECRET_A")))
    la = tuple(a.strategic_key() for a in left.actions if a.kind == MAIN_ACTIVATE_CHIP_RECONFIGURE)
    ra = tuple(a.strategic_key() for a in right.actions if a.kind == MAIN_ACTIVATE_CHIP_RECONFIGURE)
    assert la == ra and la
    assert "SECRET_A" not in repr(la) and "SECRET_B" not in repr(la)


def test_chip_pays_and_commits_target_before_attachment_resolves():
    runtime = make_runtime_state(solver.State(
        turn=2,
        library=("A", "B"),
        hand=(),
        battlefield=(
            solver.Perm("The Reality Chip"),
            solver.Perm("Artificer's Assistant"),
        ),
        blue=1,
        colorless=2,
    ))
    action = _actions(runtime, MAIN_ACTIVATE_CHIP_RECONFIGURE)[0]
    runtime = rules.apply_main_action(runtime, action)
    assert runtime.true_state.blue == 0 and runtime.true_state.colorless == 0
    assert not runtime.true_state.chip_attached
    assert runtime.stack.top().kind == ACT_CHIP_RECONFIGURE
    assert dict(runtime.stack.top().public_payload)["target_name"] == "Artificer's Assistant"

    runtime = rules.apply_main_action(runtime, _pass(runtime))
    assert runtime.true_state.chip_attached
    assert runtime.true_state.chip_target == "Artificer's Assistant"
    chip = next(p for p in runtime.true_state.battlefield if p.name == "The Reality Chip")
    assert chip.mode == "chip_attached"
    assert not solver.is_creature_perm(chip)


def test_chip_reconfigure_can_unattach_and_become_creature_again():
    runtime = make_runtime_state(solver.State(
        turn=2,
        library=("A",),
        hand=(),
        battlefield=(
            solver.Perm("The Reality Chip", mode="chip_attached"),
            solver.Perm("Artificer's Assistant"),
        ),
        chip_attached=True,
        chip_target="Artificer's Assistant",
        blue=1,
        colorless=2,
    ))
    action = next(
        a for a in _actions(runtime, MAIN_ACTIVATE_CHIP_RECONFIGURE)
        if dict(a.parameters)["choice"] == "unattach"
    )
    runtime = rules.apply_main_action(runtime, action)
    assert runtime.true_state.chip_attached
    runtime = rules.apply_main_action(runtime, _pass(runtime))
    assert not runtime.true_state.chip_attached and runtime.true_state.chip_target == ""
    chip = next(p for p in runtime.true_state.battlefield if p.name == "The Reality Chip")
    assert chip.mode == ""
    assert solver.is_creature_perm(chip)


def test_chip_resolution_completes_existing_top_producer_win():
    runtime = make_runtime_state(solver.State(
        turn=3,
        library=("A",),
        hand=(),
        battlefield=(
            solver.Perm(solver.COMMANDER),
            solver.Perm("The Reality Chip"),
            solver.Perm("Artificer's Assistant"),
            solver.Perm("Sensei's Divining Top"),
            solver.Perm("Grinding Station"),
        ),
        urza=True,
        commander_in_command_zone=False,
        blue=1,
        colorless=2,
    ))
    action = _actions(runtime, MAIN_ACTIVATE_CHIP_RECONFIGURE)[0]
    runtime = rules.apply_main_action(runtime, action)
    assert not runtime.true_state.won
    runtime = rules.apply_main_action(runtime, _pass(runtime))
    assert runtime.true_state.won
    assert runtime.true_state.win_family == "Top + Reality Chip"


def test_uthros_station_action_is_hidden_future_invariant():
    def build(library):
        return make_runtime_state(solver.State(
            turn=2,
            library=tuple(library),
            hand=(),
            battlefield=(
                solver.Perm("Uthros Research Craft"),
                solver.Perm("Battered Golem", sick=True),
            ),
        ))
    left = _request(build(("SECRET_A", "SECRET_B")))
    right = _request(build(("SECRET_B", "SECRET_A")))
    la = tuple(a.strategic_key() for a in left.actions if a.kind == MAIN_ACTIVATE_UTHROS_STATION)
    ra = tuple(a.strategic_key() for a in right.actions if a.kind == MAIN_ACTIVATE_UTHROS_STATION)
    assert la == ra and la
    assert "SECRET_A" not in repr(la) and "SECRET_B" not in repr(la)


def test_uthros_taps_creature_as_cost_then_adds_counters_on_resolution():
    runtime = make_runtime_state(solver.State(
        turn=2,
        library=("A",),
        hand=(),
        battlefield=(
            solver.Perm("Uthros Research Craft"),
            solver.Perm("Battered Golem", sick=True),
        ),
        uthros_counters=0,
    ))
    action = _actions(runtime, MAIN_ACTIVATE_UTHROS_STATION)[0]
    assert dict(action.parameters)["power"] == 3
    runtime = rules.apply_main_action(runtime, action)
    golem = next(p for p in runtime.true_state.battlefield if p.name == "Battered Golem")
    assert golem.tapped  # cost is paid immediately; summoning sickness is irrelevant
    assert runtime.true_state.uthros_counters == 0
    assert runtime.stack.top().kind == ACT_UTHROS_STATION

    runtime = rules.apply_main_action(runtime, _pass(runtime))
    assert runtime.true_state.uthros_counters == 3


def test_uthros_threshold_immediately_enables_existing_artifact_cast_draw_trigger():
    runtime = make_runtime_state(solver.State(
        turn=2,
        library=("DRAW_ME", "TAIL"),
        hand=("Tormod's Crypt",),
        battlefield=(
            solver.Perm("Uthros Research Craft"),
            solver.Perm("Battered Golem"),
        ),
        uthros_counters=0,
    ))
    station = _actions(runtime, MAIN_ACTIVATE_UTHROS_STATION)[0]
    runtime = rules.apply_main_action(runtime, station)
    runtime = rules.apply_main_action(runtime, _pass(runtime))
    assert runtime.true_state.uthros_counters == 3

    cast = next(
        a for a in _request(runtime).actions
        if a.kind == "main_cast_artifact" and dict(a.parameters)["card"] == "Tormod's Crypt"
    )
    runtime = rules.apply_main_action(runtime, cast)
    assert runtime.stack.top().kind == "uthros_draw_and_counter"
    assert runtime.true_state.hand == ()

    runtime = rules.apply_main_action(runtime, _pass(runtime))
    assert runtime.true_state.hand == ("DRAW_ME",)
    assert runtime.true_state.uthros_counters == 4
    assert runtime.stack.objects and runtime.stack.top().card == "Tormod's Crypt"


def test_base_policy_prefers_crossing_uthros_draw_threshold_over_ending_turn():
    runtime = make_runtime_state(solver.State(
        turn=2,
        library=("A",),
        hand=(),
        battlefield=(
            solver.Perm("Uthros Research Craft"),
            solver.Perm("Battered Golem"),
        ),
        uthros_counters=0,
    ))
    policy = DeterministicBasePolicy()
    request = rules.rules_decision_request(runtime, horizon=6, policy_id=policy.policy_id)
    choice = policy.choose_request(request)
    assert choice.kind == MAIN_ACTIVATE_UTHROS_STATION
    assert int(dict(choice.parameters)["result_counters"]) >= 3


def main():
    tests = (
        test_chip_reconfigure_actions_are_hidden_future_invariant,
        test_chip_pays_and_commits_target_before_attachment_resolves,
        test_chip_reconfigure_can_unattach_and_become_creature_again,
        test_chip_resolution_completes_existing_top_producer_win,
        test_uthros_station_action_is_hidden_future_invariant,
        test_uthros_taps_creature_as_cost_then_adds_counters_on_resolution,
        test_uthros_threshold_immediately_enables_existing_artifact_cast_draw_trigger,
        test_base_policy_prefers_crossing_uthros_draw_threshold_over_ending_turn,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("ENGINE ACTIVATION RUNTIME SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
