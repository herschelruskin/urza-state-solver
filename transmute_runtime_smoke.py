#!/usr/bin/env python3
"""Focused Phase-2 smokes for Transmute Artifact runtime integration."""

import urza_solver as solver
from non_oracle_base_policy import DeterministicBasePolicy
from non_oracle_rules_adapter import apply_main_action, rules_decision_request
from non_oracle_runtime import ACTION_PASS_PRIORITY, make_runtime_state
from non_oracle_transmute_runtime import MAIN_USE_TRANSMUTE_ARTIFACT


def transmute_action(runtime):
    return next(
        action for action in rules_decision_request(runtime, horizon=6).actions
        if action.kind == MAIN_USE_TRANSMUTE_ARTIFACT
    )


def pass_action(runtime):
    return next(
        action for action in rules_decision_request(runtime, horizon=6).actions
        if action.action_id == ACTION_PASS_PRIORITY
    )


def choose_sacrifice(runtime, name):
    request = rules_decision_request(runtime, horizon=6)
    return next(
        action for action in request.actions
        if action.kind == "transmute_choose_sacrifice"
        and tuple(dict(action.parameters)["signature"])[0] == name
    )


def choose_target(runtime, target):
    request = rules_decision_request(runtime, horizon=6)
    return next(
        action for action in request.actions
        if action.kind == "transmute_choose_target"
        and dict(action.parameters).get("target") == target
    )


def test_cast_is_hidden_future_invariant_and_target_not_visible_early():
    left = make_runtime_state(solver.State(
        turn=3,
        library=("Basalt Monolith", "Sensei's Divining Top", "Island"),
        hand=("Transmute Artifact",),
        battlefield=(solver.Perm("Sol Ring"),),
        blue=2,
    ))
    right = make_runtime_state(solver.State(
        turn=3,
        library=("Island", "Sensei's Divining Top", "Basalt Monolith"),
        hand=("Transmute Artifact",),
        battlefield=(solver.Perm("Sol Ring"),),
        blue=2,
    ))
    la = transmute_action(left)
    ra = transmute_action(right)
    assert la.strategic_key() == ra.strategic_key()
    assert "Basalt Monolith" not in repr(la)

    left = apply_main_action(left, la)
    assert left.stack.top().kind == "transmute_artifact_spell"
    assert left.pending is None
    assert "Basalt Monolith" not in repr(rules_decision_request(left, horizon=6).actions)


def test_sacrifice_occurs_during_resolution_before_search_observation():
    runtime = make_runtime_state(solver.State(
        turn=3,
        library=("Basalt Monolith", "Sensei's Divining Top", "Island"),
        hand=("Transmute Artifact",),
        battlefield=(solver.Perm("Sol Ring"),),
        blue=2,
    ))
    runtime = apply_main_action(runtime, transmute_action(runtime))
    assert any(p.name == "Sol Ring" for p in runtime.true_state.battlefield)
    runtime = apply_main_action(runtime, pass_action(runtime))
    request = rules_decision_request(runtime, horizon=6)
    assert request.actions and all(a.kind == "transmute_choose_sacrifice" for a in request.actions)
    assert "Basalt Monolith" not in repr(request.actions)

    runtime = apply_main_action(runtime, choose_sacrifice(runtime, "Sol Ring"))
    assert not any(p.name == "Sol Ring" for p in runtime.true_state.battlefield)
    request = rules_decision_request(runtime, horizon=6)
    assert request.actions and all(a.kind == "transmute_choose_target" for a in request.actions)
    targets = {dict(a.parameters).get("target") for a in request.actions}
    assert "Basalt Monolith" in targets
    assert "Sensei's Divining Top" in targets


def test_prized_death_waits_until_transmute_finishes_then_orders_with_target_etb():
    runtime = make_runtime_state(solver.State(
        turn=3,
        library=("Witching Well", "Island"),
        hand=("Transmute Artifact",),
        battlefield=(solver.Perm("Prized Statue"),),
        blue=2,
        rng_root_seed=77,
    ))
    runtime = apply_main_action(runtime, transmute_action(runtime))
    runtime = apply_main_action(runtime, pass_action(runtime))
    runtime = apply_main_action(runtime, choose_sacrifice(runtime, "Prized Statue"))

    # Statue has died, but Transmute is still resolving: no Treasure and no death
    # trigger may be put on the stack yet.
    assert not any(p.mode == "treasure" for p in runtime.true_state.battlefield)
    assert not runtime.stack.objects
    assert runtime.pending is not None

    runtime = apply_main_action(runtime, choose_target(runtime, "Witching Well"))
    assert any(p.name == "Witching Well" for p in runtime.true_state.battlefield)
    assert "Transmute Artifact" in runtime.true_state.graveyard

    # Witching Well ETB and Prized Statue dies trigger both waited until the spell
    # finished, then became simultaneous controlled stack-order choices.
    request = rules_decision_request(runtime, horizon=6)
    assert request.actions and all(a.kind == "runtime_stack_order" for a in request.actions)
    labels = "\n".join(a.label for a in request.actions)
    assert "etb_scry_2" in labels
    assert "prized_dies_treasure" in labels


def test_difference_payment_can_activate_mana_ability_during_resolution():
    runtime = make_runtime_state(solver.State(
        turn=3,
        library=("Basalt Monolith", "Island"),
        hand=("Transmute Artifact",),
        battlefield=(
            solver.Perm("Clue", mode="clue"),
            solver.Perm("Mana Vault"),
        ),
        blue=2,
    ))
    runtime = apply_main_action(runtime, transmute_action(runtime))
    runtime = apply_main_action(runtime, pass_action(runtime))
    runtime = apply_main_action(runtime, choose_sacrifice(runtime, "Clue"))
    runtime = apply_main_action(runtime, choose_target(runtime, "Basalt Monolith"))

    request = rules_decision_request(runtime, horizon=6)
    assert request.actions and all(a.kind == "transmute_pay_difference" for a in request.actions)
    pay = next(a for a in request.actions if dict(a.parameters).get("choice") == "pay")
    assert dict(pay.parameters).get("mana_steps")
    runtime = apply_main_action(runtime, pay)
    assert any(p.name == "Basalt Monolith" for p in runtime.true_state.battlefield)
    assert next(p for p in runtime.true_state.battlefield if p.name == "Mana Vault").tapped
    assert "Transmute Artifact" in runtime.true_state.graveyard


def test_base_policy_prefers_real_target_and_prized_sacrifice():
    runtime = make_runtime_state(solver.State(
        turn=3,
        library=("Basalt Monolith", "Sensei's Divining Top", "Island"),
        hand=("Transmute Artifact",),
        battlefield=(solver.Perm("Prized Statue"), solver.Perm("Grim Monolith")),
        blue=2,
    ))
    runtime = apply_main_action(runtime, transmute_action(runtime))
    runtime = apply_main_action(runtime, pass_action(runtime))
    request = rules_decision_request(runtime, horizon=6)
    sacrifice = DeterministicBasePolicy().choose_request(request)
    assert tuple(dict(sacrifice.parameters)["signature"])[0] == "Prized Statue"
    runtime = apply_main_action(runtime, sacrifice)
    request = rules_decision_request(runtime, horizon=6)
    target = DeterministicBasePolicy().choose_request(request)
    assert dict(target.parameters).get("target") in {"Basalt Monolith", "Sensei's Divining Top"}


def main():
    tests = (
        test_cast_is_hidden_future_invariant_and_target_not_visible_early,
        test_sacrifice_occurs_during_resolution_before_search_observation,
        test_prized_death_waits_until_transmute_finishes_then_orders_with_target_etb,
        test_difference_payment_can_activate_mana_ability_during_resolution,
        test_base_policy_prefers_real_target_and_prized_sacrifice,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("TRANSMUTE ARTIFACT RUNTIME SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
