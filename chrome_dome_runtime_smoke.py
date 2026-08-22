#!/usr/bin/env python3
"""Focused Phase-2 smokes for Chrome Dome end-step timing."""

import urza_solver as solver
import non_oracle_rules_adapter as rules
from non_oracle_chrome_dome_runtime import DECISION_CHROME_ENDSTEP
from non_oracle_runtime import ACTION_PASS_PRIORITY, make_runtime_state


def _runtime(library=("Natural", "Tail"), *, enough_mana=True, extra=()):
    lands = 5 if enough_mana else 1
    battlefield = (
        solver.Perm("Chrome Dome", sick=False),
        solver.Perm("Sol Ring"),
    ) + tuple(solver.Perm("Island") for _ in range(lands)) + tuple(extra)
    return make_runtime_state(
        solver.State(
            turn=1,
            library=tuple(library),
            hand=(),
            battlefield=battlefield,
        )
    )


def _end_action(runtime):
    request = rules.rules_decision_request(runtime, horizon=6)
    return next(action for action in request.actions if action.kind == rules.MAIN_END_TURN)


def test_end_turn_commit_remains_hidden_future_invariant_with_chrome():
    left = _runtime(("SECRET_A", "SECRET_B"))
    right = _runtime(("SECRET_B", "SECRET_A"))
    lreq = rules.rules_decision_request(left, horizon=6)
    rreq = rules.rules_decision_request(right, horizon=6)
    assert lreq.observation.key() == rreq.observation.key()
    la = next(a for a in lreq.actions if a.kind == rules.MAIN_END_TURN)
    ra = next(a for a in rreq.actions if a.kind == rules.MAIN_END_TURN)
    assert la.strategic_key() == ra.strategic_key()
    assert "SECRET_A" not in repr(la) and "SECRET_B" not in repr(la)


def test_chrome_choice_occurs_after_opponent_cycle_observations():
    runtime = _runtime(
        ("Env1", "Env2", "Natural", "Tail"),
        extra=(solver.Perm("Rhystic Study"),),
    )
    runtime = rules.apply_main_action(runtime, _end_action(runtime))
    assert runtime.true_state.turn == 1
    assert runtime.true_state.hand == ("Env1", "Env2")
    assert runtime.true_state.library == ("Natural", "Tail")
    request = rules.rules_decision_request(runtime, horizon=6)
    assert request.actions and all(a.kind == DECISION_CHROME_ENDSTEP for a in request.actions)
    assert {dict(a.parameters)["target_name"] for a in request.actions} >= {"", "Sol Ring"}


def test_chrome_copy_survives_into_next_turn_then_dies_at_our_end_step():
    runtime = _runtime(("Natural", "Turn3Draw", "Tail"))
    runtime = rules.apply_main_action(runtime, _end_action(runtime))
    request = rules.rules_decision_request(runtime, horizon=6)
    copy = next(
        action for action in request.actions
        if dict(action.parameters).get("target_name") == "Sol Ring"
    )
    runtime = rules.apply_main_action(runtime, copy)
    assert any(p.name == "Sol Ring" and p.mode == "chrome_copy_preturn" for p in runtime.true_state.battlefield)
    request = rules.rules_decision_request(runtime, horizon=6)
    assert len(request.actions) == 1 and request.actions[0].action_id == ACTION_PASS_PRIORITY
    runtime = rules.apply_main_action(runtime, request.actions[0])
    assert runtime.true_state.turn == 2
    assert "Natural" in runtime.true_state.hand
    assert any(p.name == "Sol Ring" and p.mode == "chrome_copy_preturn" for p in runtime.true_state.battlefield)

    runtime = rules.apply_main_action(runtime, _end_action(runtime))
    assert not any(p.mode in {"chrome_copy", "chrome_copy_preturn"} for p in runtime.true_state.battlefield)
    request = rules.rules_decision_request(runtime, horizon=6)
    assert request.actions and all(a.kind == DECISION_CHROME_ENDSTEP for a in request.actions)
    decline = next(a for a in request.actions if not dict(a.parameters).get("target_name"))
    runtime = rules.apply_main_action(runtime, decline)
    assert runtime.true_state.turn == 3


def test_chrome_without_endstep_mana_advances_without_fake_choice():
    runtime = _runtime(("Natural", "Tail"), enough_mana=False)
    runtime = rules.apply_main_action(runtime, _end_action(runtime))
    assert runtime.pending is None
    assert runtime.true_state.turn == 2
    assert runtime.true_state.hand == ("Natural",)


def test_chrome_cannot_copy_itself_and_target_set_is_public():
    runtime = _runtime(("A", "B"))
    runtime = rules.apply_main_action(runtime, _end_action(runtime))
    request = rules.rules_decision_request(runtime, horizon=6)
    names = {str(dict(action.parameters).get("target_name", "")) for action in request.actions}
    assert "Chrome Dome" not in names
    assert "Sol Ring" in names


def main():
    tests = (
        test_end_turn_commit_remains_hidden_future_invariant_with_chrome,
        test_chrome_choice_occurs_after_opponent_cycle_observations,
        test_chrome_copy_survives_into_next_turn_then_dies_at_our_end_step,
        test_chrome_without_endstep_mana_advances_without_fake_choice,
        test_chrome_cannot_copy_itself_and_target_set_is_public,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("CHROME DOME RUNTIME SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
