#!/usr/bin/env python3
"""Focused smokes for committed end-turn and chance observations."""

import urza_solver as solver
from non_oracle_base_policy import DeterministicBasePolicy
from non_oracle_rules_adapter import (
    MAIN_END_TURN,
    MAIN_MANA_ACTION,
    UPKEEP_DECLINE_REMORA,
    UPKEEP_PAY_REMORA,
    apply_main_action,
    rules_decision_request,
)
from non_oracle_runtime import ACTION_PASS_PRIORITY, make_runtime_state
from non_oracle_turn_engine import can_commit_end_turn
from solver_architecture import InformationState
from urza_permission_adapter import UrzaPermissionState


def end_action(runtime):
    request = rules_decision_request(runtime, horizon=6)
    return next(action for action in request.actions if action.kind == MAIN_END_TURN)


def test_end_turn_commit_is_hidden_future_invariant():
    left = make_runtime_state(solver.State(turn=1, library=("SECRET_ALPHA_CARD", "SECRET_BETA_CARD"), hand=(), battlefield=()))
    right = make_runtime_state(solver.State(turn=1, library=("SECRET_BETA_CARD", "SECRET_ALPHA_CARD"), hand=(), battlefield=()))
    lreq = rules_decision_request(left, horizon=6)
    rreq = rules_decision_request(right, horizon=6)
    assert lreq.observation.key() == rreq.observation.key()
    la = next(a for a in lreq.actions if a.kind == MAIN_END_TURN)
    ra = next(a for a in rreq.actions if a.kind == MAIN_END_TURN)
    assert la.strategic_key() == ra.strategic_key()
    assert "SECRET_ALPHA_CARD" not in repr(la)
    assert "SECRET_BETA_CARD" not in repr(la)


def test_hidden_natural_draw_is_resolved_only_after_end_turn_choice():
    left = make_runtime_state(solver.State(turn=1, library=("A", "B"), hand=(), battlefield=()))
    right = make_runtime_state(solver.State(turn=1, library=("B", "A"), hand=(), battlefield=()))
    left2 = apply_main_action(left, end_action(left))
    right2 = apply_main_action(right, end_action(right))
    assert left2.true_state.turn == right2.true_state.turn == 2
    assert left2.true_state.hand == ("A",)
    assert right2.true_state.hand == ("B",)
    assert left2.true_state.library == ("B",)
    assert right2.true_state.library == ("A",)


def test_known_top_is_consumed_by_natural_draw():
    runtime = make_runtime_state(
        solver.State(turn=1, library=("Known", "Next"), hand=(), battlefield=()),
        InformationState(known_top=("Known", "Next")),
    )
    runtime = apply_main_action(runtime, end_action(runtime))
    assert runtime.true_state.hand == ("Known",)
    assert runtime.information.known_top == ("Next",)


def test_end_turn_expires_urza_permission_but_keeps_exiled_card():
    permissions = UrzaPermissionState().grant("Mana Vault", 1)
    runtime = make_runtime_state(
        solver.State(turn=1, library=("Island",), hand=(), battlefield=(), exile=("Mana Vault",)),
        permissions=permissions,
    )
    runtime = apply_main_action(runtime, end_action(runtime))
    assert runtime.permissions.permissions == ()
    assert runtime.true_state.exile == ("Mana Vault",)


def test_saga_lore_advances_after_natural_draw_and_creates_mandatory_stack_trigger():
    runtime = make_runtime_state(
        solver.State(
            turn=1,
            library=("Draw", "Sol Ring", "Tail"),
            hand=(),
            battlefield=(solver.Perm("Urza's Saga", counters=2),),
        )
    )
    runtime = apply_main_action(runtime, end_action(runtime))
    saga = next(p for p in runtime.true_state.battlefield if p.name == "Urza's Saga")
    assert saga.counters == 3 and saga.mode == "saga3"
    assert not runtime.true_state.saga3_pending
    assert runtime.stack.top().kind == "saga3_search_trigger"
    request = rules_decision_request(runtime, horizon=6)
    assert len(request.actions) == 1
    assert request.actions[0].action_id == ACTION_PASS_PRIORITY
    assert "Sol Ring" not in repr(request.actions)
    runtime = apply_main_action(runtime, request.actions[0])
    request = rules_decision_request(runtime, horizon=6)
    assert request.actions and all(a.kind == "remaining_search_target" for a in request.actions)
    targets = {dict(a.parameters).get("target") for a in request.actions}
    assert "Sol Ring" in targets


def test_remora_upkeep_request_precedes_natural_draw_and_is_hidden_future_invariant():
    left = make_runtime_state(
        solver.State(
            turn=1,
            library=("Env1", "Env2", "NATURAL_A"),
            hand=(),
            battlefield=(solver.Perm("Mystic Remora"), solver.Perm("Island")),
        )
    )
    right = make_runtime_state(
        solver.State(
            turn=1,
            library=("Env1", "Env2", "NATURAL_B"),
            hand=(),
            battlefield=(solver.Perm("Mystic Remora"), solver.Perm("Island")),
        )
    )
    left = apply_main_action(left, end_action(left))
    right = apply_main_action(right, end_action(right))
    assert left.true_state.hand == right.true_state.hand == ("Env1", "Env2")
    assert left.true_state.library == ("NATURAL_A",)
    assert right.true_state.library == ("NATURAL_B",)
    lreq = rules_decision_request(left, horizon=6)
    rreq = rules_decision_request(right, horizon=6)
    assert lreq.observation.key() == rreq.observation.key()
    assert tuple(a.strategic_key() for a in lreq.actions) == tuple(a.strategic_key() for a in rreq.actions)
    assert "NATURAL_A" not in repr(lreq.actions)
    assert "NATURAL_B" not in repr(rreq.actions)
    assert any(a.kind == MAIN_MANA_ACTION for a in lreq.actions)
    assert any(a.kind == UPKEEP_DECLINE_REMORA for a in lreq.actions)


def test_remora_policy_floats_mana_pays_then_draws_and_ages():
    runtime = make_runtime_state(
        solver.State(
            turn=1,
            library=("Env1", "Env2", "Natural", "Tail"),
            hand=(),
            battlefield=(solver.Perm("Mystic Remora"), solver.Perm("Island")),
        )
    )
    runtime = apply_main_action(runtime, end_action(runtime))
    policy = DeterministicBasePolicy()
    request = rules_decision_request(runtime, horizon=6, policy_id=policy.policy_id)
    first = policy.choose_request(request)
    assert first.kind == MAIN_MANA_ACTION
    runtime = apply_main_action(runtime, first)
    request = rules_decision_request(runtime, horizon=6, policy_id=policy.policy_id)
    assert any(a.kind == UPKEEP_PAY_REMORA for a in request.actions)
    second = policy.choose_request(request)
    assert second.kind == UPKEEP_PAY_REMORA
    runtime = apply_main_action(runtime, second)
    assert not runtime.true_state.remora_upkeep_pending
    assert runtime.true_state.remora_age == 1
    assert runtime.true_state.hand == ("Env1", "Env2", "Natural")
    assert runtime.true_state.library == ("Tail",)
    assert runtime.true_state.blue == 0 and runtime.true_state.colorless == 0


def test_remora_decline_sacrifices_before_natural_draw():
    runtime = make_runtime_state(
        solver.State(
            turn=1,
            library=("Env1", "Env2", "Natural"),
            hand=(),
            battlefield=(solver.Perm("Mystic Remora"),),
        )
    )
    runtime = apply_main_action(runtime, end_action(runtime))
    request = rules_decision_request(runtime, horizon=6)
    decline = next(a for a in request.actions if a.kind == UPKEEP_DECLINE_REMORA)
    runtime = apply_main_action(runtime, decline)
    assert not solver.has(runtime.true_state, "Mystic Remora")
    assert "Mystic Remora" in runtime.true_state.graveyard
    assert runtime.true_state.hand == ("Env1", "Env2", "Natural")


def test_chrome_dome_uses_explicit_specialized_turn_boundary():
    runtime = make_runtime_state(
        solver.State(
            turn=1,
            library=("A",),
            hand=(),
            battlefield=(solver.Perm("Chrome Dome"), solver.Perm("Sol Ring")),
            colorless=5,
        )
    )
    # The generic turn engine still refuses Chrome; the rules adapter must route
    # it through the dedicated end-step timing adapter instead of auto-Oracling it.
    assert not can_commit_end_turn(runtime)
    request = rules_decision_request(runtime, horizon=6)
    assert any(a.kind == MAIN_END_TURN for a in request.actions)
    runtime = apply_main_action(runtime, end_action(runtime))
    assert runtime.true_state.turn == 2
    assert runtime.true_state.hand == ("A",)


def main():
    tests = (
        test_end_turn_commit_is_hidden_future_invariant,
        test_hidden_natural_draw_is_resolved_only_after_end_turn_choice,
        test_known_top_is_consumed_by_natural_draw,
        test_end_turn_expires_urza_permission_but_keeps_exiled_card,
        test_saga_lore_advances_after_natural_draw_and_creates_mandatory_stack_trigger,
        test_remora_upkeep_request_precedes_natural_draw_and_is_hidden_future_invariant,
        test_remora_policy_floats_mana_pays_then_draws_and_ages,
        test_remora_decline_sacrifices_before_natural_draw,
        test_chrome_dome_uses_explicit_specialized_turn_boundary,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("NON-ORACLE TURN ENGINE SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
