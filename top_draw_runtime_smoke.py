#!/usr/bin/env python3
"""Focused Phase-2 smokes for Top draw and priority-time Key sequencing."""

import urza_solver as solver
import non_oracle_rules_adapter as rules
from non_oracle_base_policy import DeterministicBasePolicy
from non_oracle_runtime import ACTION_PASS_PRIORITY, make_runtime_state
from non_oracle_top_draw_runtime import (
    ACT_KEY_UNTAP,
    ACT_TOP_DRAW,
    MAIN_ACTIVATE_TOP_DRAW,
    PRIORITY_ACTIVATE_KEY,
    PRIORITY_ACTIVATE_TOP_DRAW,
)


def _request(runtime):
    return rules.rules_decision_request(runtime, horizon=6)


def _actions(runtime, kind):
    return [action for action in _request(runtime).actions if action.kind == kind]


def _pass(runtime):
    return next(action for action in _request(runtime).actions if action.action_id == ACTION_PASS_PRIORITY)


def test_top_draw_commit_is_hidden_future_invariant():
    def build(library):
        return make_runtime_state(solver.State(
            turn=2,
            library=tuple(library),
            hand=(),
            battlefield=(
                solver.Perm("Sensei's Divining Top"),
                solver.Perm("Voltaic Key"),
            ),
            colorless=1,
        ))

    left = _request(build(("SECRET_A", "SECRET_B", "TAIL")))
    right = _request(build(("SECRET_B", "SECRET_A", "TAIL")))
    la = tuple(a.strategic_key() for a in left.actions if a.kind == MAIN_ACTIVATE_TOP_DRAW)
    ra = tuple(a.strategic_key() for a in right.actions if a.kind == MAIN_ACTIVATE_TOP_DRAW)
    assert la == ra and la
    assert "SECRET_A" not in repr(la) and "SECRET_B" not in repr(la)


def test_single_top_draw_is_a_real_stack_ability_and_observes_only_on_resolution():
    runtime = make_runtime_state(solver.State(
        turn=2,
        library=("A", "B", "C"),
        hand=(),
        battlefield=(solver.Perm("Sensei's Divining Top"),),
    ))
    action = _actions(runtime, MAIN_ACTIVATE_TOP_DRAW)[0]
    runtime = rules.apply_main_action(runtime, action)
    top = next(p for p in runtime.true_state.battlefield if p.name == "Sensei's Divining Top")
    assert top.tapped
    assert runtime.stack.top().kind == ACT_TOP_DRAW
    assert runtime.true_state.hand == ()
    assert runtime.information.known_top == ()

    runtime = rules.apply_main_action(runtime, _pass(runtime))
    assert runtime.true_state.hand == ("A",)
    assert runtime.true_state.library == ("Sensei's Divining Top", "B", "C")
    assert not solver.has(runtime.true_state, "Sensei's Divining Top")
    assert runtime.information.known_top[:1] == ("Sensei's Divining Top",)


def test_top_key_double_activation_uses_real_priority_and_lifo_resolution():
    runtime = make_runtime_state(solver.State(
        turn=2,
        library=("A", "B", "C"),
        hand=(),
        battlefield=(
            solver.Perm("Sensei's Divining Top"),
            solver.Perm("Voltaic Key"),
        ),
        colorless=1,
    ))

    # A1: Top draw ability.
    runtime = rules.apply_main_action(runtime, _actions(runtime, MAIN_ACTIVATE_TOP_DRAW)[0])
    assert tuple(obj.kind for obj in runtime.stack.objects) == (ACT_TOP_DRAW,)

    # With A1 waiting, Key may be activated targeting the tapped Top.
    key_actions = _actions(runtime, PRIORITY_ACTIVATE_KEY)
    key = next(a for a in key_actions if dict(a.parameters)["target_name"] == "Sensei's Divining Top")
    assert "A" not in repr(key.parameters)
    runtime = rules.apply_main_action(runtime, key)
    assert tuple(obj.kind for obj in runtime.stack.objects) == (ACT_KEY_UNTAP, ACT_TOP_DRAW)
    assert runtime.true_state.colorless == 0

    # Resolve Key, returning priority with A1 still waiting and Top untapped.
    runtime = rules.apply_main_action(runtime, _pass(runtime))
    top = next(p for p in runtime.true_state.battlefield if p.name == "Sensei's Divining Top")
    assert not top.tapped
    assert tuple(obj.kind for obj in runtime.stack.objects) == (ACT_TOP_DRAW,)

    # A2 is now legal and is stacked over A1.
    a2 = _actions(runtime, PRIORITY_ACTIVATE_TOP_DRAW)[0]
    runtime = rules.apply_main_action(runtime, a2)
    assert tuple(obj.kind for obj in runtime.stack.objects) == (ACT_TOP_DRAW, ACT_TOP_DRAW)

    # A2 resolves first: draw A and move Top to library top.
    runtime = rules.apply_main_action(runtime, _pass(runtime))
    assert runtime.true_state.hand == ("A",)
    assert runtime.true_state.library == ("Sensei's Divining Top", "B", "C")
    assert not solver.has(runtime.true_state, "Sensei's Divining Top")
    assert tuple(obj.kind for obj in runtime.stack.objects) == (ACT_TOP_DRAW,)

    # A1 resolves next: draw the Top; its source is already gone, so nothing moves again.
    runtime = rules.apply_main_action(runtime, _pass(runtime))
    assert runtime.true_state.hand == ("A", "Sensei's Divining Top")
    assert runtime.true_state.library == ("B", "C")
    assert runtime.information.known_top == ()
    assert not runtime.stack.objects


def test_priority_key_can_untap_other_artifact_above_an_unrelated_spell():
    runtime = make_runtime_state(solver.State(
        turn=2,
        library=("A",),
        hand=("Sol Ring",),
        battlefield=(
            solver.Perm("Voltaic Key"),
            solver.Perm("Mana Vault", tapped=True),
        ),
        colorless=2,
    ))
    cast = next(a for a in _request(runtime).actions if a.kind == "main_cast_artifact" and dict(a.parameters)["card"] == "Sol Ring")
    runtime = rules.apply_main_action(runtime, cast)
    assert runtime.true_state.colorless == 1

    key = next(
        a for a in _actions(runtime, PRIORITY_ACTIVATE_KEY)
        if dict(a.parameters)["target_name"] == "Mana Vault"
    )
    runtime = rules.apply_main_action(runtime, key)
    assert runtime.stack.top().kind == ACT_KEY_UNTAP
    runtime = rules.apply_main_action(runtime, _pass(runtime))
    vault = next(p for p in runtime.true_state.battlefield if p.name == "Mana Vault")
    assert not vault.tapped
    assert runtime.stack.objects and runtime.stack.top().card == "Sol Ring"


def test_base_policy_follows_productive_top_key_sequence():
    policy = DeterministicBasePolicy()
    runtime = make_runtime_state(solver.State(
        turn=2,
        library=("A", "B", "C"),
        hand=(),
        battlefield=(
            solver.Perm("Sensei's Divining Top"),
            solver.Perm("Voltaic Key"),
        ),
        colorless=1,
    ))

    request = rules.rules_decision_request(runtime, horizon=6, policy_id=policy.policy_id)
    choice = policy.choose_request(request)
    assert choice.kind == MAIN_ACTIVATE_TOP_DRAW
    runtime = rules.apply_main_action(runtime, choice)

    request = rules.rules_decision_request(runtime, horizon=6, policy_id=policy.policy_id)
    choice = policy.choose_request(request)
    assert choice.kind == PRIORITY_ACTIVATE_KEY
    assert dict(choice.parameters)["target_name"] == "Sensei's Divining Top"
    runtime = rules.apply_main_action(runtime, choice)

    runtime = rules.apply_main_action(runtime, _pass(runtime))
    request = rules.rules_decision_request(runtime, horizon=6, policy_id=policy.policy_id)
    choice = policy.choose_request(request)
    assert choice.kind == PRIORITY_ACTIVATE_TOP_DRAW


def main():
    tests = (
        test_top_draw_commit_is_hidden_future_invariant,
        test_single_top_draw_is_a_real_stack_ability_and_observes_only_on_resolution,
        test_top_key_double_activation_uses_real_priority_and_lifo_resolution,
        test_priority_key_can_untap_other_artifact_above_an_unrelated_spell,
        test_base_policy_follows_productive_top_key_sequence,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("TOP DRAW / PRIORITY KEY RUNTIME SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
