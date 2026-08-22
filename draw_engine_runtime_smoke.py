#!/usr/bin/env python3
"""Focused Phase-2 smokes for cantrips and artifact draw engines."""

import urza_solver as solver
import non_oracle_rules_adapter as rules
from non_oracle_base_policy import DeterministicBasePolicy
from non_oracle_cam_runtime import DECISION_CAM_EFFECT, DECISION_CAM_TARGET
from non_oracle_draw_engine_runtime import (
    ACT_BAUBLE_DELAYED,
    ACT_CAM,
    ACT_CLUE,
    ACT_RING,
    MAIN_CAST_PROBE,
    MAIN_DRAW_ACTIVATION,
)
from non_oracle_runtime import ACTION_PASS_PRIORITY, make_runtime_state


def _actions(runtime, kind):
    return [a for a in rules.rules_decision_request(runtime, horizon=6).actions if a.kind == kind]


def _pass(runtime):
    return next(
        a for a in rules.rules_decision_request(runtime, horizon=6).actions
        if a.action_id == ACTION_PASS_PRIORITY
    )


def test_draw_commit_actions_are_hidden_future_invariant():
    def build(library):
        return make_runtime_state(solver.State(
            turn=2,
            library=tuple(library),
            hand=("Gitaxian Probe",),
            battlefield=(
                solver.Perm("The One Ring"),
                solver.Perm("Clue", mode="clue"),
            ),
            colorless=2,
        ))
    left = rules.rules_decision_request(build(("SECRET_A", "SECRET_B", "TAIL")), horizon=6)
    right = rules.rules_decision_request(build(("SECRET_B", "SECRET_A", "TAIL")), horizon=6)
    kinds = {MAIN_CAST_PROBE, MAIN_DRAW_ACTIVATION}
    la = tuple(a.strategic_key() for a in left.actions if a.kind in kinds)
    ra = tuple(a.strategic_key() for a in right.actions if a.kind in kinds)
    assert la == ra
    assert "SECRET_A" not in repr(la) and "SECRET_B" not in repr(la)


def test_probe_draw_is_observed_only_when_spell_resolves():
    runtime = make_runtime_state(solver.State(
        turn=2,
        library=("ObservedDraw", "Tail"),
        hand=("Gitaxian Probe",),
        battlefield=(),
    ))
    action = _actions(runtime, MAIN_CAST_PROBE)[0]
    runtime = rules.apply_main_action(runtime, action)
    assert runtime.true_state.hand == ()
    assert runtime.true_state.library == ("ObservedDraw", "Tail")
    assert runtime.information.known_top == ()
    runtime = rules.apply_main_action(runtime, _pass(runtime))
    assert runtime.true_state.hand == ("ObservedDraw",)
    assert runtime.true_state.library == ("Tail",)
    assert "Gitaxian Probe" in runtime.true_state.graveyard


def test_probe_pays_blue_through_own_vexing_bauble_when_available():
    runtime = make_runtime_state(solver.State(
        turn=2,
        library=("Draw",),
        hand=("Gitaxian Probe",),
        battlefield=(solver.Perm("Vexing Bauble"),),
        blue=1,
    ))
    action = _actions(runtime, MAIN_CAST_PROBE)[0]
    assert dict(action.parameters)["mana_spent"] == 1
    assert not dict(action.parameters)["will_be_countered_by_own_bauble"]
    runtime = rules.apply_main_action(runtime, action)
    assert runtime.true_state.blue == 0
    runtime = rules.apply_main_action(runtime, _pass(runtime))
    assert runtime.true_state.hand == ("Draw",)


def test_ring_taps_as_cost_then_adds_counter_and_draws_on_resolution():
    runtime = make_runtime_state(solver.State(
        turn=3,
        library=("A", "B", "C"),
        hand=(),
        battlefield=(solver.Perm("The One Ring"),),
        ring_counters=1,
    ))
    action = next(
        a for a in _actions(runtime, MAIN_DRAW_ACTIVATION)
        if dict(a.parameters)["ability_kind"] == ACT_RING
    )
    runtime = rules.apply_main_action(runtime, action)
    ring = next(p for p in runtime.true_state.battlefield if p.name == "The One Ring")
    assert ring.tapped
    assert runtime.true_state.ring_counters == 1
    assert runtime.true_state.hand == ()
    runtime = rules.apply_main_action(runtime, _pass(runtime))
    assert runtime.true_state.ring_counters == 2
    assert runtime.true_state.hand == ("A", "B")
    assert runtime.true_state.library == ("C",)


def test_clue_is_sacrificed_as_cost_before_draw_resolves():
    runtime = make_runtime_state(solver.State(
        turn=2,
        library=("Draw",),
        hand=(),
        battlefield=(solver.Perm("Clue", mode="clue"),),
        colorless=2,
    ))
    action = next(
        a for a in _actions(runtime, MAIN_DRAW_ACTIVATION)
        if dict(a.parameters)["ability_kind"] == ACT_CLUE
    )
    runtime = rules.apply_main_action(runtime, action)
    assert not any(p.mode == "clue" for p in runtime.true_state.battlefield)
    assert runtime.true_state.hand == ()
    runtime = rules.apply_main_action(runtime, _pass(runtime))
    assert runtime.true_state.hand == ("Draw",)


def test_bauble_sacrifice_schedules_existing_turn_engine_delayed_draw():
    runtime = make_runtime_state(solver.State(
        turn=2,
        library=("Later",),
        hand=(),
        battlefield=(solver.Perm("Mishra's Bauble"),),
    ))
    action = next(
        a for a in _actions(runtime, MAIN_DRAW_ACTIVATION)
        if dict(a.parameters)["ability_kind"] == ACT_BAUBLE_DELAYED
    )
    runtime = rules.apply_main_action(runtime, action)
    assert not solver.has(runtime.true_state, "Mishra's Bauble")
    assert runtime.true_state.bauble_draws == 0
    runtime = rules.apply_main_action(runtime, _pass(runtime))
    assert runtime.true_state.bauble_draws == 1
    assert runtime.true_state.hand == ()


def test_cam_sacrifice_stages_ltb_target_above_draw_then_draws_two():
    runtime = make_runtime_state(solver.State(
        turn=3,
        library=("Draw1", "Draw2", "Tail"),
        hand=(),
        battlefield=(
            solver.Perm("Sewer-veillance Cam"),
            solver.Perm("Battered Golem", tapped=True, sick=False),
        ),
        blue=1,
        colorless=3,
    ))
    action = next(
        a for a in _actions(runtime, MAIN_DRAW_ACTIVATION)
        if dict(a.parameters)["ability_kind"] == ACT_CAM
    )
    runtime = rules.apply_main_action(runtime, action)
    assert not solver.has(runtime.true_state, "Sewer-veillance Cam")
    assert runtime.true_state.hand == ()
    request = rules.rules_decision_request(runtime, horizon=6)
    assert request.actions and all(a.kind == DECISION_CAM_TARGET for a in request.actions)
    runtime = rules.apply_main_action(runtime, request.actions[0])
    assert runtime.stack.top().kind == "ltb_cam"
    runtime = rules.apply_main_action(runtime, _pass(runtime))
    request = rules.rules_decision_request(runtime, horizon=6)
    assert request.actions and all(a.kind == DECISION_CAM_EFFECT for a in request.actions)
    untap = next(a for a in request.actions if dict(a.parameters)["choice"] == "untap")
    runtime = rules.apply_main_action(runtime, untap)
    golem = next(p for p in runtime.true_state.battlefield if p.name == "Battered Golem")
    assert not golem.tapped
    assert runtime.stack.top().kind == ACT_CAM
    runtime = rules.apply_main_action(runtime, _pass(runtime))
    assert runtime.true_state.hand == ("Draw1", "Draw2")
    assert runtime.true_state.library == ("Tail",)


def test_base_policy_uses_free_probe_and_ring_before_end_turn():
    policy = DeterministicBasePolicy()
    runtime = make_runtime_state(solver.State(
        turn=2,
        library=("A", "B"),
        hand=("Gitaxian Probe",),
        battlefield=(solver.Perm("The One Ring"),),
    ))
    request = rules.rules_decision_request(runtime, horizon=6, policy_id=policy.policy_id)
    first = policy.choose_request(request)
    assert first.kind == MAIN_CAST_PROBE
    runtime = rules.apply_main_action(runtime, first)
    runtime = rules.apply_main_action(runtime, _pass(runtime))
    request = rules.rules_decision_request(runtime, horizon=6, policy_id=policy.policy_id)
    second = policy.choose_request(request)
    assert second.kind == MAIN_DRAW_ACTIVATION
    assert dict(second.parameters)["ability_kind"] == ACT_RING


def main():
    tests = (
        test_draw_commit_actions_are_hidden_future_invariant,
        test_probe_draw_is_observed_only_when_spell_resolves,
        test_probe_pays_blue_through_own_vexing_bauble_when_available,
        test_ring_taps_as_cost_then_adds_counter_and_draws_on_resolution,
        test_clue_is_sacrificed_as_cost_before_draw_resolves,
        test_bauble_sacrifice_schedules_existing_turn_engine_delayed_draw,
        test_cam_sacrifice_stages_ltb_target_above_draw_then_draws_two,
        test_base_policy_uses_free_probe_and_ring_before_end_turn,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("DRAW ENGINE RUNTIME SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
