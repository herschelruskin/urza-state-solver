#!/usr/bin/env python3
"""Regressions for policy-facing runtime sidecars."""

from dataclasses import replace

import urza_solver as solver
from solver_architecture import InformationState
from non_oracle_runtime_value_key import RuntimeDecisionWindow, WINDOW_PRIORITY
from non_oracle_runtime_view import make_runtime_policy_view
from trigger_order_adapter import PendingTrigger, PendingTriggerStack
from urza_permission_adapter import UrzaPermissionState, UrzaPlayPermission


def base_state(library=("Hidden A", "Hidden B"), seed=1):
    return solver.State(
        turn=3,
        library=tuple(library),
        hand=("Island",),
        battlefield=(solver.Perm(solver.COMMANDER),),
        exile=("Mana Vault",),
        urza=True,
        rng_root_seed=seed,
    )


def test_runtime_view_exposes_permissions_and_stack_but_not_hidden_state_or_rng():
    state = base_state()
    permissions = UrzaPermissionState().grant("Mana Vault", 3)
    stack = PendingTriggerStack(
        (PendingTrigger("u", "uthros_draw_and_counter", "Uthros Research Craft"),)
    )
    view = make_runtime_policy_view(
        state,
        InformationState(),
        permissions=permissions,
        trigger_stack=stack,
        window=RuntimeDecisionWindow(WINDOW_PRIORITY),
    )
    assert view.play_permissions[0].card == "Mana Vault"
    assert view.pending_triggers[0].kind == "uthros_draw_and_counter"
    assert view.window_kind == WINDOW_PRIORITY
    assert not hasattr(view.base, "library")
    assert not hasattr(view, "root_seed")
    assert not hasattr(view, "true_state")


def test_permission_provenance_ids_do_not_change_policy_view():
    state = base_state()
    a = UrzaPermissionState(
        permissions=(UrzaPlayPermission("id-a", "Mana Vault", 3, 3, 0),),
        next_sequence=1,
    )
    b = UrzaPermissionState(
        permissions=(UrzaPlayPermission("id-b", "Mana Vault", 3, 3, 99),),
        next_sequence=100,
    )
    view_a = make_runtime_policy_view(state, InformationState(), permissions=a)
    view_b = make_runtime_policy_view(state, InformationState(), permissions=b)
    assert view_a == view_b
    assert view_a.key() == view_b.key()


def test_permission_multiplicity_is_visible():
    state = replace(base_state(), exile=("Mana Vault", "Mana Vault"))
    one = UrzaPermissionState().grant("Mana Vault", 3)
    two = one.grant("Mana Vault", 3)
    view_one = make_runtime_policy_view(state, InformationState(), permissions=one)
    view_two = make_runtime_policy_view(state, InformationState(), permissions=two)
    assert len(view_one.play_permissions) == 1
    assert len(view_two.play_permissions) == 2
    assert view_one.key() != view_two.key()


def test_unknown_library_permutation_and_root_seed_do_not_change_runtime_view():
    state = base_state(("Hidden A", "Hidden B"), seed=1)
    other = base_state(("Hidden B", "Hidden A"), seed=999)
    permissions = UrzaPermissionState().grant("Mana Vault", 3)
    view_a = make_runtime_policy_view(state, InformationState(), permissions=permissions)
    view_b = make_runtime_policy_view(other, InformationState(), permissions=permissions)
    assert view_a == view_b
    assert view_a.key() == view_b.key()


def test_pending_trigger_order_is_visible_to_policy():
    state = base_state()
    a = PendingTrigger("a", "assistant_scry_1", "Artificer's Assistant")
    u = PendingTrigger("u", "uthros_draw_and_counter", "Uthros Research Craft")
    view_a = make_runtime_policy_view(
        state, InformationState(), trigger_stack=PendingTriggerStack((a, u))
    )
    view_b = make_runtime_policy_view(
        state, InformationState(), trigger_stack=PendingTriggerStack((u, a))
    )
    assert view_a.pending_triggers != view_b.pending_triggers
    assert view_a.key() != view_b.key()


def main():
    tests = (
        test_runtime_view_exposes_permissions_and_stack_but_not_hidden_state_or_rng,
        test_permission_provenance_ids_do_not_change_policy_view,
        test_permission_multiplicity_is_visible,
        test_unknown_library_permutation_and_root_seed_do_not_change_runtime_view,
        test_pending_trigger_order_is_visible_to_policy,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("NON-ORACLE RUNTIME VIEW SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
