#!/usr/bin/env python3
"""Focused Phase-2 smokes for command-zone Urza casting."""

import urza_solver as solver
from non_oracle_base_policy import DeterministicBasePolicy
from non_oracle_commander_adapter import MAIN_CAST_COMMANDER, commander_cast_cost
from non_oracle_rules_adapter import apply_main_action, rules_decision_request
from non_oracle_runtime import ACTION_PASS_PRIORITY, make_runtime_state


def action_of_kind(runtime, kind):
    request = rules_decision_request(runtime, horizon=6)
    return next(action for action in request.actions if action.kind == kind)


def pass_action(runtime):
    request = rules_decision_request(runtime, horizon=6)
    action = next(action for action in request.actions if action.action_id == ACTION_PASS_PRIORITY)
    return action


def test_commander_cast_intent_is_hidden_future_invariant():
    left = make_runtime_state(
        solver.State(turn=2, library=("SECRET_A", "SECRET_B"), hand=(), battlefield=(), blue=2, colorless=2)
    )
    right = make_runtime_state(
        solver.State(turn=2, library=("SECRET_B", "SECRET_A"), hand=(), battlefield=(), blue=2, colorless=2)
    )
    la = action_of_kind(left, MAIN_CAST_COMMANDER)
    ra = action_of_kind(right, MAIN_CAST_COMMANDER)
    assert la.strategic_key() == ra.strategic_key()
    assert "SECRET_A" not in repr(la) and "SECRET_B" not in repr(la)


def test_commander_tax_and_medallion_cost_are_public_and_correct():
    base = solver.State(turn=4, library=(), hand=(), battlefield=(), commander_casts_from_zone=1)
    assert commander_cast_cost(base) == (4, 2)
    reduced = solver.State(
        turn=4,
        library=(),
        hand=(),
        battlefield=(solver.Perm("Sapphire Medallion"),),
        commander_casts_from_zone=1,
    )
    assert commander_cast_cost(reduced) == (3, 2)


def test_cast_commit_moves_urza_to_stack_without_premature_battlefield_effects():
    runtime = make_runtime_state(
        solver.State(turn=2, library=("Island",), hand=(), battlefield=(), blue=2, colorless=2)
    )
    runtime = apply_main_action(runtime, action_of_kind(runtime, MAIN_CAST_COMMANDER))
    assert not runtime.true_state.commander_in_command_zone
    assert runtime.true_state.commander_casts_from_zone == 1
    assert runtime.true_state.spell_cast_this_turn
    assert not runtime.true_state.urza
    assert not any(p.name == solver.COMMANDER for p in runtime.true_state.battlefield)
    assert not any(p.name == "Construct" for p in runtime.true_state.battlefield)
    assert runtime.stack.top().kind == "commander_spell"


def test_assistant_trigger_is_above_commander_spell_and_scry_is_staged():
    runtime = make_runtime_state(
        solver.State(
            turn=3,
            library=("GOOD", "TAIL"),
            hand=(),
            battlefield=(solver.Perm("Artificer's Assistant"),),
            blue=2,
            colorless=2,
        )
    )
    runtime = apply_main_action(runtime, action_of_kind(runtime, MAIN_CAST_COMMANDER))
    assert [obj.kind for obj in runtime.stack.objects] == ["assistant_scry_1", "commander_spell"]
    runtime = apply_main_action(runtime, pass_action(runtime))
    assert runtime.pending is not None
    assert runtime.information.known_top[0] == "GOOD"
    assert not runtime.true_state.urza


def test_urza_resolves_then_construct_etb_resolves_then_artifact_triggers():
    runtime = make_runtime_state(
        solver.State(
            turn=3,
            library=("Island",),
            hand=(),
            battlefield=(solver.Perm("Grinding Station", tapped=True),),
            blue=2,
            colorless=2,
        )
    )
    runtime = apply_main_action(runtime, action_of_kind(runtime, MAIN_CAST_COMMANDER))

    # Urza spell resolves first when there are no cast triggers.
    runtime = apply_main_action(runtime, pass_action(runtime))
    assert runtime.true_state.urza
    assert any(p.name == solver.COMMANDER for p in runtime.true_state.battlefield)
    assert not any(p.name == "Construct" for p in runtime.true_state.battlefield)
    assert runtime.stack.top().kind == "urza_construct_etb"

    # The ETB trigger creates Construct; the Construct is a new artifact-entry
    # event and therefore creates the Station trigger above older objects.
    runtime = apply_main_action(runtime, pass_action(runtime))
    assert any(p.name == "Construct" for p in runtime.true_state.battlefield)
    assert runtime.stack.top().kind == "etb_producer"


def test_base_policy_prioritizes_payable_commander_over_end_turn():
    runtime = make_runtime_state(
        solver.State(turn=3, library=("Island",), hand=(), battlefield=(), blue=2, colorless=2)
    )
    request = rules_decision_request(runtime, horizon=6)
    chosen = DeterministicBasePolicy().choose_request(request)
    assert chosen.kind == MAIN_CAST_COMMANDER


def main():
    tests = (
        test_commander_cast_intent_is_hidden_future_invariant,
        test_commander_tax_and_medallion_cost_are_public_and_correct,
        test_cast_commit_moves_urza_to_stack_without_premature_battlefield_effects,
        test_assistant_trigger_is_above_commander_spell_and_scry_is_staged,
        test_urza_resolves_then_construct_etb_resolves_then_artifact_triggers,
        test_base_policy_prioritizes_payable_commander_over_end_turn,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("NON-ORACLE COMMANDER ADAPTER SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
