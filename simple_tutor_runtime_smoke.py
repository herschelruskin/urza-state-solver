#!/usr/bin/env python3
"""Focused Phase-2 smokes for the staged simple tutor runtime bridge."""

import urza_solver as solver
from non_oracle_base_policy import DeterministicBasePolicy
from non_oracle_rules_adapter import apply_main_action, rules_decision_request
from non_oracle_runtime import ACTION_PASS_PRIORITY, make_runtime_state
from non_oracle_simple_tutor_runtime import MAIN_USE_SIMPLE_TUTOR


def tutor_actions(runtime, source=None):
    rows = [
        action
        for action in rules_decision_request(runtime, horizon=6).actions
        if action.kind == MAIN_USE_SIMPLE_TUTOR
    ]
    if source is not None:
        rows = [action for action in rows if dict(action.parameters).get("source") == source]
    return rows


def pass_action(runtime):
    return next(
        action
        for action in rules_decision_request(runtime, horizon=6).actions
        if action.action_id == ACTION_PASS_PRIORITY
    )


def settle_until_target_or_main(runtime, limit=20):
    for _ in range(limit):
        request = rules_decision_request(runtime, horizon=6)
        if request.actions and all(action.kind == "choose_tutor_target" for action in request.actions):
            return runtime
        if runtime.pending is None and not runtime.stack.objects:
            return runtime
        if not request.actions:
            raise AssertionError("simple tutor runtime stopped with unresolved stack")
        runtime = apply_main_action(runtime, DeterministicBasePolicy().choose_request(request))
    raise AssertionError("simple tutor runtime did not settle")


def test_tutor_commit_actions_do_not_expose_hidden_targets_or_order():
    hand = ("Muddle the Mixture", "Mystical Tutor")
    left = make_runtime_state(solver.State(
        turn=3,
        library=("Power Artifact", "Grim Monolith", "Retraction Helix", "Island"),
        hand=hand,
        battlefield=(),
        blue=3,
        colorless=1,
    ))
    right = make_runtime_state(solver.State(
        turn=3,
        library=("Island", "Retraction Helix", "Grim Monolith", "Power Artifact"),
        hand=hand,
        battlefield=(),
        blue=3,
        colorless=1,
    ))
    la = tutor_actions(left)
    ra = tutor_actions(right)
    assert tuple(a.strategic_key() for a in la) == tuple(a.strategic_key() for a in ra)
    text = repr(la)
    for hidden in ("Power Artifact", "Grim Monolith", "Retraction Helix"):
        assert hidden not in text


def test_muddle_transmute_pays_and_discards_before_search_is_visible():
    runtime = make_runtime_state(solver.State(
        turn=3,
        library=("Power Artifact", "Grim Monolith", "Island"),
        hand=("Muddle the Mixture",),
        battlefield=(),
        blue=2,
        colorless=1,
    ))
    action = tutor_actions(runtime, "Muddle the Mixture")[0]
    runtime = apply_main_action(runtime, action)
    assert "Muddle the Mixture" not in runtime.true_state.hand
    assert "Muddle the Mixture" in runtime.true_state.graveyard
    assert runtime.true_state.blue == 0 and runtime.true_state.colorless == 0
    assert runtime.pending is None
    assert runtime.stack.top().kind == "simple_tutor_transmute"

    runtime = apply_main_action(runtime, pass_action(runtime))
    request = rules_decision_request(runtime, horizon=6)
    assert request.actions
    assert all(a.kind == "choose_tutor_target" for a in request.actions)
    targets = {dict(a.parameters)["target"] for a in request.actions}
    # Muddle searches mana value exactly 2.
    assert "Power Artifact" in targets
    assert "Grim Monolith" in targets
    assert "Island" not in targets


def test_same_multiset_different_order_exposes_same_targets_only_after_resolution():
    def reach(library):
        runtime = make_runtime_state(solver.State(
            turn=3,
            library=library,
            hand=("Muddle the Mixture",),
            battlefield=(),
            blue=2,
            colorless=1,
        ))
        runtime = apply_main_action(runtime, tutor_actions(runtime, "Muddle the Mixture")[0])
        runtime = apply_main_action(runtime, pass_action(runtime))
        return rules_decision_request(runtime, horizon=6)

    left = reach(("Power Artifact", "Grim Monolith", "Island"))
    right = reach(("Island", "Grim Monolith", "Power Artifact"))
    assert tuple(a.strategic_key() for a in left.actions) == tuple(
        a.strategic_key() for a in right.actions
    )


def test_merchant_spell_resolves_before_search_and_vfc_trigger_sits_above_it():
    runtime = make_runtime_state(solver.State(
        turn=3,
        library=("Mystical Tutor", "Retraction Helix", "Island"),
        hand=("Merchant Scroll",),
        battlefield=(solver.Perm("Valley Floodcaller"),),
        blue=1,
        colorless=1,
    ))
    runtime = apply_main_action(runtime, tutor_actions(runtime, "Merchant Scroll")[0])
    assert runtime.pending is None
    assert [obj.kind for obj in runtime.stack.objects] == [
        "vfc_noncreature_cast", "simple_tutor_spell"
    ]
    runtime = apply_main_action(runtime, pass_action(runtime))
    assert runtime.pending is None
    assert runtime.stack.top().kind == "simple_tutor_spell"
    runtime = apply_main_action(runtime, pass_action(runtime))
    assert runtime.pending is not None
    targets = {
        dict(a.parameters)["target"]
        for a in rules_decision_request(runtime, horizon=6).actions
    }
    assert "Mystical Tutor" in targets and "Retraction Helix" in targets


def test_mystical_target_shuffle_then_known_top_is_preserved():
    runtime = make_runtime_state(solver.State(
        turn=3,
        library=("Island", "Power Artifact", "Retraction Helix"),
        hand=("Mystical Tutor",),
        battlefield=(),
        blue=1,
        colorless=0,
        rng_root_seed=123,
    ))
    runtime = apply_main_action(runtime, tutor_actions(runtime, "Mystical Tutor")[0])
    runtime = apply_main_action(runtime, pass_action(runtime))
    request = rules_decision_request(runtime, horizon=6)
    target = next(a for a in request.actions if dict(a.parameters)["target"] == "Retraction Helix")
    runtime = apply_main_action(runtime, target)
    assert runtime.true_state.library[0] == "Retraction Helix"
    assert runtime.information.known_top == ("Retraction Helix",)
    assert "Mystical Tutor" in runtime.true_state.graveyard


def test_spellseeker_resolves_then_etb_searches_as_separate_stack_object():
    runtime = make_runtime_state(solver.State(
        turn=3,
        library=("Power Artifact", "Retraction Helix", "Island"),
        hand=("Spellseeker",),
        battlefield=(),
        blue=1,
        colorless=2,
    ))
    runtime = apply_main_action(runtime, tutor_actions(runtime, "Spellseeker")[0])
    assert runtime.stack.top().kind == "simple_tutor_spellseeker_spell"
    assert not any(p.name == "Spellseeker" for p in runtime.true_state.battlefield)

    runtime = apply_main_action(runtime, pass_action(runtime))
    assert any(p.name == "Spellseeker" for p in runtime.true_state.battlefield)
    assert runtime.stack.top().kind == "simple_tutor_spellseeker_etb"
    assert runtime.pending is None

    runtime = apply_main_action(runtime, pass_action(runtime))
    request = rules_decision_request(runtime, horizon=6)
    assert request.actions and all(a.kind == "choose_tutor_target" for a in request.actions)
    targets = {dict(a.parameters)["target"] for a in request.actions}
    assert "Power Artifact" in targets and "Retraction Helix" in targets


def test_base_policy_target_choice_uses_revealed_target_value_not_library_order():
    def chosen(library):
        runtime = make_runtime_state(solver.State(
            turn=3,
            library=library,
            hand=("Muddle the Mixture",),
            battlefield=(),
            blue=2,
            colorless=1,
        ))
        runtime = apply_main_action(runtime, tutor_actions(runtime, "Muddle the Mixture")[0])
        runtime = apply_main_action(runtime, pass_action(runtime))
        request = rules_decision_request(runtime, horizon=6)
        return DeterministicBasePolicy().choose_request(request)

    left = chosen(("Power Artifact", "Grim Monolith", "Island"))
    right = chosen(("Island", "Grim Monolith", "Power Artifact"))
    assert dict(left.parameters)["target"] == dict(right.parameters)["target"]
    assert dict(left.parameters)["target"] in {"Power Artifact", "Grim Monolith"}


def main():
    tests = (
        test_tutor_commit_actions_do_not_expose_hidden_targets_or_order,
        test_muddle_transmute_pays_and_discards_before_search_is_visible,
        test_same_multiset_different_order_exposes_same_targets_only_after_resolution,
        test_merchant_spell_resolves_before_search_and_vfc_trigger_sits_above_it,
        test_mystical_target_shuffle_then_known_top_is_preserved,
        test_spellseeker_resolves_then_etb_searches_as_separate_stack_object,
        test_base_policy_target_choice_uses_revealed_target_value_not_library_order,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("SIMPLE TUTOR RUNTIME SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
