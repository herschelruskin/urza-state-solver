#!/usr/bin/env python3
"""Regressions for non-Oracle runtime value identity."""

from dataclasses import replace

import urza_solver as solver
from solver_architecture import InformationState
from non_oracle_runtime_value_key import (
    RuntimeDecisionWindow,
    WINDOW_MAIN_EMPTY,
    WINDOW_PRIORITY,
    canonical_non_oracle_runtime_value_key,
    urza_permissions_strategic_key,
)
from trigger_order_adapter import PendingTrigger, PendingTriggerStack
from urza_permission_adapter import UrzaPermissionState, UrzaPlayPermission


def base_state():
    return solver.State(
        turn=3,
        library=("A", "B", "Tail"),
        hand=("Island",),
        battlefield=(solver.Perm(solver.COMMANDER),),
        urza=True,
        rng_root_seed=111,
    )


def test_live_urza_permission_changes_value_identity():
    state = base_state()
    info = InformationState()
    empty = canonical_non_oracle_runtime_value_key(state, info)
    permission = UrzaPermissionState().grant("Mana Vault", 3)
    with_permission = canonical_non_oracle_runtime_value_key(
        replace(state, exile=("Mana Vault",)),
        info,
        permissions=permission,
    )
    assert empty != with_permission


def test_permission_ids_are_provenance_but_multiplicity_is_value_relevant():
    a = UrzaPermissionState(
        permissions=(UrzaPlayPermission("id-a", "Mana Vault", 3, 3, 0),),
        next_sequence=1,
    )
    b = UrzaPermissionState(
        permissions=(UrzaPlayPermission("id-b", "Mana Vault", 3, 3, 99),),
        next_sequence=100,
    )
    two = UrzaPermissionState(
        permissions=(
            UrzaPlayPermission("id-a", "Mana Vault", 3, 3, 0),
            UrzaPlayPermission("id-b", "Mana Vault", 3, 3, 1),
        ),
        next_sequence=2,
    )
    assert urza_permissions_strategic_key(a) == urza_permissions_strategic_key(b)
    assert urza_permissions_strategic_key(a) != urza_permissions_strategic_key(two)


def test_trigger_resolution_order_changes_value_identity():
    a = PendingTrigger("a", "assistant_scry_1", "Artificer's Assistant")
    u = PendingTrigger("u", "uthros_draw_and_counter", "Uthros Research Craft")
    stack_a = PendingTriggerStack((a, u))
    stack_b = PendingTriggerStack((u, a))
    state = base_state()
    info = InformationState()
    key_a = canonical_non_oracle_runtime_value_key(state, info, trigger_stack=stack_a)
    key_b = canonical_non_oracle_runtime_value_key(state, info, trigger_stack=stack_b)
    assert key_a != key_b


def test_priority_window_changes_value_identity():
    state = base_state()
    info = InformationState()
    main = canonical_non_oracle_runtime_value_key(
        state,
        info,
        window=RuntimeDecisionWindow(WINDOW_MAIN_EMPTY),
    )
    priority = canonical_non_oracle_runtime_value_key(
        state,
        info,
        window=RuntimeDecisionWindow(WINDOW_PRIORITY),
    )
    assert main != priority


def test_root_rng_seed_remains_outside_strategic_runtime_identity():
    state = base_state()
    other = replace(state, rng_root_seed=999999)
    info = InformationState()
    assert canonical_non_oracle_runtime_value_key(state, info) == canonical_non_oracle_runtime_value_key(other, info)


def main():
    tests = (
        test_live_urza_permission_changes_value_identity,
        test_permission_ids_are_provenance_but_multiplicity_is_value_relevant,
        test_trigger_resolution_order_changes_value_identity,
        test_priority_window_changes_value_identity,
        test_root_rng_seed_remains_outside_strategic_runtime_identity,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("NON-ORACLE RUNTIME VALUE KEY SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
