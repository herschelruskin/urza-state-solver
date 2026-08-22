#!/usr/bin/env python3
"""Focused Phase-2 smokes for Bay, Saga III, Scour, and Tezzeret -3."""

import urza_solver as solver
from non_oracle_base_policy import DeterministicBasePolicy
from non_oracle_remaining_search_runtime import (
    MAIN_ACTIVATE_BAY,
    MAIN_ACTIVATE_TEZZ_MINUS3,
    MAIN_CAST_SCOUR,
)
from non_oracle_rules_adapter import MAIN_END_TURN, apply_main_action, rules_decision_request
from non_oracle_runtime import ACTION_PASS_PRIORITY, make_runtime_state


def action_of_kind(runtime, kind):
    return next(a for a in rules_decision_request(runtime, horizon=6).actions if a.kind == kind)


def pass_action(runtime):
    return next(
        a for a in rules_decision_request(runtime, horizon=6).actions
        if a.action_id == ACTION_PASS_PRIORITY
    )


def target_action(runtime, target):
    return next(
        a for a in rules_decision_request(runtime, horizon=6).actions
        if a.kind == "remaining_search_target" and dict(a.parameters).get("target") == target
    )


def test_bay_commit_is_hidden_future_invariant_and_does_not_expose_target():
    def runtime(library):
        return make_runtime_state(solver.State(
            turn=3,
            library=library,
            hand=(),
            battlefield=(solver.Perm("Repurposing Bay"), solver.Perm("Prized Statue")),
            colorless=2,
        ))
    left = runtime(("Basalt Monolith", "Island", "Sensei's Divining Top"))
    right = runtime(("Sensei's Divining Top", "Island", "Basalt Monolith"))
    la = [a for a in rules_decision_request(left, horizon=6).actions if a.kind == MAIN_ACTIVATE_BAY]
    ra = [a for a in rules_decision_request(right, horizon=6).actions if a.kind == MAIN_ACTIVATE_BAY]
    assert tuple(a.strategic_key() for a in la) == tuple(a.strategic_key() for a in ra)
    assert "Basalt Monolith" not in repr(la)


def test_bay_prized_death_trigger_resolves_before_bay_search():
    runtime = make_runtime_state(solver.State(
        turn=3,
        library=("Basalt Monolith", "Island"),
        hand=(),
        battlefield=(solver.Perm("Repurposing Bay"), solver.Perm("Prized Statue")),
        colorless=2,
        rng_root_seed=13,
    ))
    action = next(
        a for a in rules_decision_request(runtime, horizon=6).actions
        if a.kind == MAIN_ACTIVATE_BAY and dict(a.parameters).get("sacrifice_name") == "Prized Statue"
    )
    runtime = apply_main_action(runtime, action)
    assert [o.kind for o in runtime.stack.objects] == [
        "prized_dies_treasure", "repurposing_bay_search_ability"
    ]
    assert not any(p.mode == "treasure" for p in runtime.true_state.battlefield)

    runtime = apply_main_action(runtime, pass_action(runtime))
    assert any(p.mode == "treasure" for p in runtime.true_state.battlefield)
    assert runtime.stack.top().kind == "repurposing_bay_search_ability"
    assert "Basalt Monolith" not in repr(rules_decision_request(runtime, horizon=6).actions)

    runtime = apply_main_action(runtime, pass_action(runtime))
    request = rules_decision_request(runtime, horizon=6)
    targets = {dict(a.parameters).get("target") for a in request.actions}
    assert "Basalt Monolith" in targets
    runtime = apply_main_action(runtime, target_action(runtime, "Basalt Monolith"))
    assert any(p.name == "Basalt Monolith" for p in runtime.true_state.battlefield)


def test_saga_three_is_mandatory_stack_search_then_final_sacrifice():
    runtime = make_runtime_state(solver.State(
        turn=1,
        library=("Natural", "Sol Ring", "Island"),
        hand=(),
        battlefield=(solver.Perm("Urza's Saga", counters=2),),
        rng_root_seed=21,
    ))
    runtime = apply_main_action(runtime, action_of_kind(runtime, MAIN_END_TURN))
    assert runtime.stack.top().kind == "saga3_search_trigger"
    assert any(p.name == "Urza's Saga" for p in runtime.true_state.battlefield)

    runtime = apply_main_action(runtime, pass_action(runtime))
    request = rules_decision_request(runtime, horizon=6)
    assert request.actions and all(a.kind == "remaining_search_target" for a in request.actions)
    assert "Sol Ring" in {dict(a.parameters).get("target") for a in request.actions}

    runtime = apply_main_action(runtime, target_action(runtime, "Sol Ring"))
    assert not any(p.name == "Urza's Saga" for p in runtime.true_state.battlefield)
    assert any(p.name == "Sol Ring" for p in runtime.true_state.battlefield)
    assert "Urza's Saga" in runtime.true_state.graveyard


def test_scour_commits_mode_and_grave_target_before_library_search():
    def runtime(library):
        return make_runtime_state(solver.State(
            turn=3,
            library=library,
            hand=("Scour for Scrap",),
            battlefield=(),
            graveyard=("Sol Ring",),
            blue=5,
            colorless=5,
            rng_root_seed=31,
        ))
    left = runtime(("Basalt Monolith", "Island", "Sensei's Divining Top"))
    right = runtime(("Sensei's Divining Top", "Island", "Basalt Monolith"))
    la = [a for a in rules_decision_request(left, horizon=6).actions if a.kind == MAIN_CAST_SCOUR]
    ra = [a for a in rules_decision_request(right, horizon=6).actions if a.kind == MAIN_CAST_SCOUR]
    assert tuple(a.strategic_key() for a in la) == tuple(a.strategic_key() for a in ra)
    assert "Basalt Monolith" not in repr(la)

    both = next(a for a in la if dict(a.parameters)["mode"] == "both")
    left = apply_main_action(left, both)
    assert left.stack.top().kind == "scour_for_scrap_spell"
    assert left.pending is None
    assert "Basalt Monolith" not in repr(rules_decision_request(left, horizon=6).actions)

    left = apply_main_action(left, pass_action(left))
    request = rules_decision_request(left, horizon=6)
    assert "Basalt Monolith" in {dict(a.parameters).get("target") for a in request.actions}
    left = apply_main_action(left, target_action(left, "Basalt Monolith"))
    assert "Basalt Monolith" in left.true_state.hand
    assert "Sol Ring" in left.true_state.hand
    assert "Scour for Scrap" in left.true_state.graveyard


def test_tezzeret_minus3_pays_loyalty_before_search_observation():
    runtime = make_runtime_state(solver.State(
        turn=3,
        library=("Sensei's Divining Top", "Sol Ring", "Basalt Monolith"),
        hand=(),
        battlefield=(solver.Perm("Tezzeret, Cruel Captain", counters=4, mode="tez_ready"),),
        rng_root_seed=41,
    ))
    action = action_of_kind(runtime, MAIN_ACTIVATE_TEZZ_MINUS3)
    runtime = apply_main_action(runtime, action)
    tezz = next(p for p in runtime.true_state.battlefield if p.name == "Tezzeret, Cruel Captain")
    assert tezz.counters == 1 and tezz.mode == "tez_used"
    assert runtime.stack.top().kind == "tezzeret_minus3_search_ability"
    assert "Sol Ring" not in repr(rules_decision_request(runtime, horizon=6).actions)

    runtime = apply_main_action(runtime, pass_action(runtime))
    request = rules_decision_request(runtime, horizon=6)
    targets = {dict(a.parameters).get("target") for a in request.actions}
    assert "Sol Ring" in targets and "Sensei's Divining Top" in targets
    assert "Basalt Monolith" not in targets


def test_base_policy_prefers_observed_remaining_search_target_over_fail():
    runtime = make_runtime_state(solver.State(
        turn=3,
        library=("Basalt Monolith", "Island"),
        hand=(),
        battlefield=(solver.Perm("Repurposing Bay"), solver.Perm("Prized Statue")),
        colorless=2,
    ))
    bay = next(
        a for a in rules_decision_request(runtime, horizon=6).actions
        if a.kind == MAIN_ACTIVATE_BAY and dict(a.parameters).get("sacrifice_name") == "Prized Statue"
    )
    runtime = apply_main_action(runtime, bay)
    runtime = apply_main_action(runtime, pass_action(runtime))
    runtime = apply_main_action(runtime, pass_action(runtime))
    request = rules_decision_request(runtime, horizon=6)
    chosen = DeterministicBasePolicy().choose_request(request)
    assert dict(chosen.parameters).get("target") == "Basalt Monolith"


def main():
    tests = (
        test_bay_commit_is_hidden_future_invariant_and_does_not_expose_target,
        test_bay_prized_death_trigger_resolves_before_bay_search,
        test_saga_three_is_mandatory_stack_search_then_final_sacrifice,
        test_scour_commits_mode_and_grave_target_before_library_search,
        test_tezzeret_minus3_pays_loyalty_before_search_observation,
        test_base_policy_prefers_observed_remaining_search_target_over_fail,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("REMAINING SEARCH RUNTIME SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
