#!/usr/bin/env python3
"""Focused Phase-2 smokes for utility artifacts."""

import urza_solver as solver
import non_oracle_rules_adapter as rules
from non_oracle_base_policy import DeterministicBasePolicy
from non_oracle_runtime import ACTION_PASS_PRIORITY, make_runtime_state
from non_oracle_utility_artifact_runtime import (
    DECISION_MOX_DIAMOND_ENTRY,
    MAIN_ACTIVATE_KEY,
    MAIN_ACTIVATE_TOP,
    MAIN_CAST_UTILITY_ARTIFACT,
    TOP_REORDER_DECISION_KIND,
)


def _actions(runtime, kind):
    return [
        action for action in rules.rules_decision_request(runtime, horizon=6).actions
        if action.kind == kind
    ]


def _pass(runtime):
    return next(
        action for action in rules.rules_decision_request(runtime, horizon=6).actions
        if action.action_id == ACTION_PASS_PRIORITY
    )


def test_utility_commit_actions_are_hidden_future_invariant():
    def build(library):
        return make_runtime_state(solver.State(
            turn=2,
            library=tuple(library),
            hand=("Mox Diamond", "Everflowing Chalice", "Island"),
            battlefield=(
                solver.Perm("Sensei's Divining Top"),
                solver.Perm("Voltaic Key"),
                solver.Perm("Mana Vault", tapped=True),
            ),
            colorless=3,
        ))
    left = rules.rules_decision_request(build(("SECRET_A", "SECRET_B", "TAIL")), horizon=6)
    right = rules.rules_decision_request(build(("SECRET_B", "SECRET_A", "TAIL")), horizon=6)
    kinds = {MAIN_CAST_UTILITY_ARTIFACT, MAIN_ACTIVATE_TOP, MAIN_ACTIVATE_KEY}
    la = tuple(a.strategic_key() for a in left.actions if a.kind in kinds)
    ra = tuple(a.strategic_key() for a in right.actions if a.kind in kinds)
    assert la == ra
    assert "SECRET_A" not in repr(la) and "SECRET_B" not in repr(la)


def test_mox_diamond_discards_land_only_as_spell_would_enter():
    runtime = make_runtime_state(solver.State(
        turn=2,
        library=(),
        hand=("Mox Diamond", "Island", "Force of Will"),
        battlefield=(),
    ))
    action = next(a for a in _actions(runtime, MAIN_CAST_UTILITY_ARTIFACT) if dict(a.parameters)["card"] == "Mox Diamond")
    runtime = rules.apply_main_action(runtime, action)
    assert "Mox Diamond" not in runtime.true_state.hand
    assert "Island" in runtime.true_state.hand
    assert not solver.has(runtime.true_state, "Mox Diamond")
    runtime = rules.apply_main_action(runtime, _pass(runtime))
    request = rules.rules_decision_request(runtime, horizon=6)
    assert request.actions and all(a.kind == DECISION_MOX_DIAMOND_ENTRY for a in request.actions)
    discard = next(a for a in request.actions if dict(a.parameters).get("land") == "Island")
    runtime = rules.apply_main_action(runtime, discard)
    diamond = next(p for p in runtime.true_state.battlefield if p.name == "Mox Diamond")
    assert diamond.mode == "diamond"
    assert "Island" not in runtime.true_state.hand and "Island" in runtime.true_state.graveyard


def test_mox_diamond_can_fail_to_enter_without_a_true_land():
    runtime = make_runtime_state(solver.State(
        turn=2, library=(), hand=("Mox Diamond", "Force of Will"), battlefield=()
    ))
    action = next(a for a in _actions(runtime, MAIN_CAST_UTILITY_ARTIFACT) if dict(a.parameters)["card"] == "Mox Diamond")
    runtime = rules.apply_main_action(runtime, action)
    runtime = rules.apply_main_action(runtime, _pass(runtime))
    request = rules.rules_decision_request(runtime, horizon=6)
    assert len(request.actions) == 1
    runtime = rules.apply_main_action(runtime, request.actions[0])
    assert not solver.has(runtime.true_state, "Mox Diamond")
    assert "Mox Diamond" in runtime.true_state.graveyard


def test_chalice_commits_kicks_before_cast_and_enters_with_exact_counters():
    runtime = make_runtime_state(solver.State(
        turn=2,
        library=(),
        hand=("Everflowing Chalice",),
        battlefield=(),
        colorless=4,
    ))
    actions = _actions(runtime, MAIN_CAST_UTILITY_ARTIFACT)
    kick_counts = {int(dict(a.parameters)["kicks"]) for a in actions if dict(a.parameters)["card"] == "Everflowing Chalice"}
    assert kick_counts == {0, 1, 2}
    action = next(a for a in actions if dict(a.parameters).get("kicks") == 1)
    runtime = rules.apply_main_action(runtime, action)
    assert runtime.true_state.colorless == 2
    assert "Everflowing Chalice" not in runtime.true_state.hand
    runtime = rules.apply_main_action(runtime, _pass(runtime))
    chalice = next(p for p in runtime.true_state.battlefield if p.name == "Everflowing Chalice")
    assert chalice.counters == 1


def test_top_reveals_only_after_activation_then_reorders_from_observation():
    runtime = make_runtime_state(solver.State(
        turn=2,
        library=("A", "B", "C", "D"),
        hand=(),
        battlefield=(solver.Perm("Sensei's Divining Top"),),
        colorless=1,
    ))
    request = rules.rules_decision_request(runtime, horizon=6)
    action = next(a for a in request.actions if a.kind == MAIN_ACTIVATE_TOP)
    assert "A" not in repr(action.parameters) and "B" not in repr(action.parameters)
    runtime = rules.apply_main_action(runtime, action)
    assert runtime.true_state.colorless == 0
    assert runtime.information.known_top[:3] == ("A", "B", "C")
    request = rules.rules_decision_request(runtime, horizon=6)
    assert request.actions and all(a.kind == TOP_REORDER_DECISION_KIND for a in request.actions)
    chosen = next(a for a in request.actions if tuple(dict(a.parameters)["order"]) == ("C", "B", "A"))
    runtime = rules.apply_main_action(runtime, chosen)
    assert runtime.true_state.library[:4] == ("C", "B", "A", "D")
    assert runtime.information.known_top[:3] == ("C", "B", "A")


def test_key_spends_one_taps_itself_and_untaps_public_artifact_target():
    runtime = make_runtime_state(solver.State(
        turn=2,
        library=(),
        hand=(),
        battlefield=(
            solver.Perm("Voltaic Key", tapped=False),
            solver.Perm("Mana Vault", tapped=True),
        ),
        colorless=1,
    ))
    request = rules.rules_decision_request(runtime, horizon=6)
    actions = [a for a in request.actions if a.kind == MAIN_ACTIVATE_KEY]
    assert len(actions) == 1
    assert dict(actions[0].parameters)["target_name"] == "Mana Vault"
    runtime = rules.apply_main_action(runtime, actions[0])
    key = next(p for p in runtime.true_state.battlefield if p.name == "Voltaic Key")
    vault = next(p for p in runtime.true_state.battlefield if p.name == "Mana Vault")
    assert key.tapped and not vault.tapped and runtime.true_state.colorless == 0


def test_base_policy_prefers_productive_key_and_real_chalice_over_ending_turn():
    policy = DeterministicBasePolicy()
    runtime = make_runtime_state(solver.State(
        turn=2,
        library=("A", "B", "C"),
        hand=("Everflowing Chalice",),
        battlefield=(
            solver.Perm("Voltaic Key", tapped=False),
            solver.Perm("Mana Vault", tapped=True),
        ),
        colorless=3,
    ))
    request = rules.rules_decision_request(runtime, horizon=6, policy_id=policy.policy_id)
    choice = policy.choose_request(request)
    assert choice.kind in {MAIN_ACTIVATE_KEY, MAIN_CAST_UTILITY_ARTIFACT}


def main():
    tests = (
        test_utility_commit_actions_are_hidden_future_invariant,
        test_mox_diamond_discards_land_only_as_spell_would_enter,
        test_mox_diamond_can_fail_to_enter_without_a_true_land,
        test_chalice_commits_kicks_before_cast_and_enters_with_exact_counters,
        test_top_reveals_only_after_activation_then_reorders_from_observation,
        test_key_spends_one_taps_itself_and_untaps_public_artifact_target,
        test_base_policy_prefers_productive_key_and_real_chalice_over_ending_turn,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("UTILITY ARTIFACT RUNTIME SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
