#!/usr/bin/env python3
"""Focused smokes for committed end-turn and chance observations."""

import urza_solver as solver
from non_oracle_rules_adapter import MAIN_END_TURN, apply_main_action, rules_decision_request
from non_oracle_runtime import make_runtime_state
from non_oracle_turn_engine import can_commit_end_turn
from solver_architecture import InformationState
from urza_permission_adapter import UrzaPermissionState


def end_action(runtime):
    request = rules_decision_request(runtime, horizon=6)
    return next(action for action in request.actions if action.kind == MAIN_END_TURN)


def test_end_turn_commit_is_hidden_future_invariant():
    left = make_runtime_state(
        solver.State(
            turn=1,
            library=("SECRET_ALPHA_CARD", "SECRET_BETA_CARD"),
            hand=(), battlefield=(),
        )
    )
    right = make_runtime_state(
        solver.State(
            turn=1,
            library=("SECRET_BETA_CARD", "SECRET_ALPHA_CARD"),
            hand=(), battlefield=(),
        )
    )
    lreq = rules_decision_request(left, horizon=6)
    rreq = rules_decision_request(right, horizon=6)
    assert lreq.observation.key() == rreq.observation.key()
    la = next(a for a in lreq.actions if a.kind == MAIN_END_TURN)
    ra = next(a for a in rreq.actions if a.kind == MAIN_END_TURN)
    assert la.strategic_key() == ra.strategic_key()
    assert "SECRET_ALPHA_CARD" not in repr(la)
    assert "SECRET_BETA_CARD" not in repr(la)


def test_hidden_natural_draw_is_resolved_only_after_end_turn_choice():
    left = make_runtime_state(
        solver.State(turn=1, library=("A", "B"), hand=(), battlefield=())
    )
    right = make_runtime_state(
        solver.State(turn=1, library=("B", "A"), hand=(), battlefield=())
    )
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
        solver.State(
            turn=1,
            library=("Island",),
            hand=(),
            battlefield=(),
            exile=("Mana Vault",),
        ),
        permissions=permissions,
    )
    runtime = apply_main_action(runtime, end_action(runtime))
    assert runtime.permissions.permissions == ()
    assert runtime.true_state.exile == ("Mana Vault",)


def test_saga_lore_advances_after_natural_draw_and_blocks_main_at_chapter_three():
    runtime = make_runtime_state(
        solver.State(
            turn=1,
            library=("Draw", "Tail"),
            hand=(),
            battlefield=(solver.Perm("Urza's Saga", counters=2),),
        )
    )
    runtime = apply_main_action(runtime, end_action(runtime))
    saga = next(p for p in runtime.true_state.battlefield if p.name == "Urza's Saga")
    assert saga.counters == 3 and saga.mode == "saga3"
    assert runtime.true_state.saga3_pending
    assert rules_decision_request(runtime, horizon=6).actions == ()


def test_remora_upkeep_is_not_skipped_into_main_phase():
    runtime = make_runtime_state(
        solver.State(
            turn=1,
            library=("Env1", "Env2", "Natural"),
            hand=(),
            battlefield=(solver.Perm("Mystic Remora"),),
        )
    )
    runtime = apply_main_action(runtime, end_action(runtime))
    assert runtime.true_state.turn == 2
    assert runtime.true_state.remora_upkeep_pending
    assert runtime.true_state.hand == ("Env1", "Env2")
    assert runtime.true_state.library == ("Natural",)
    assert rules_decision_request(runtime, horizon=6).actions == ()


def test_chrome_dome_turn_boundary_is_explicitly_blocked_not_auto_oracled():
    runtime = make_runtime_state(
        solver.State(
            turn=1,
            library=("A",),
            hand=(),
            battlefield=(solver.Perm("Chrome Dome"), solver.Perm("Sol Ring")),
            colorless=5,
        )
    )
    assert not can_commit_end_turn(runtime)
    assert all(a.kind != MAIN_END_TURN for a in rules_decision_request(runtime, horizon=6).actions)


def main():
    tests = (
        test_end_turn_commit_is_hidden_future_invariant,
        test_hidden_natural_draw_is_resolved_only_after_end_turn_choice,
        test_known_top_is_consumed_by_natural_draw,
        test_end_turn_expires_urza_permission_but_keeps_exiled_card,
        test_saga_lore_advances_after_natural_draw_and_blocks_main_at_chapter_three,
        test_remora_upkeep_is_not_skipped_into_main_phase,
        test_chrome_dome_turn_boundary_is_explicitly_blocked_not_auto_oracled,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("NON-ORACLE TURN ENGINE SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
