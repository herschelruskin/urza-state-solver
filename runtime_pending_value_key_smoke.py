#!/usr/bin/env python3
"""DP-critical pending-decision identity smokes."""

import urza_solver as solver
from decision_observation import DECISION_POST_OBSERVATION, PendingDecisionSpec
from non_oracle_runtime import RuntimePendingDecision, make_runtime_state
from non_oracle_runtime_value_key import (
    RuntimeDecisionWindow,
    WINDOW_POST_OBSERVATION,
    canonical_runtime_object_value_key,
)
from dataclasses import replace


def pending(decision_id, *, target, contingent_on="source.execution.1"):
    return RuntimePendingDecision(
        spec=PendingDecisionSpec(
            decision_id=decision_id,
            kind="choose_target",
            source="Test Source",
            decision_stage=DECISION_POST_OBSERVATION,
            contingent_on=contingent_on,
        ),
        kind="choose_target",
        payload=(("target_card", target),),
    )


def root():
    return replace(
        make_runtime_state(
            solver.State(turn=3, library=("A", "B"), hand=("Island",), battlefield=())
        ),
        window=RuntimeDecisionWindow(WINDOW_POST_OBSERVATION),
    )


def test_different_pending_semantic_choices_do_not_merge():
    a = replace(root(), pending=pending("decision.exec.1", target="Grinding Station"))
    b = replace(root(), pending=pending("decision.exec.2", target="Battered Golem"))
    assert canonical_runtime_object_value_key(a) != canonical_runtime_object_value_key(b)


def test_pending_execution_ids_do_not_fragment_same_value_state():
    a = replace(
        root(),
        pending=pending(
            "decision.exec.111",
            target="Grinding Station",
            contingent_on="action.execution.111",
        ),
    )
    b = replace(
        root(),
        pending=pending(
            "decision.exec.999",
            target="Grinding Station",
            contingent_on="action.execution.999",
        ),
    )
    assert canonical_runtime_object_value_key(a) == canonical_runtime_object_value_key(b)


def test_pending_vs_no_pending_are_distinct_even_in_same_window():
    live = replace(root(), pending=pending("decision.exec.1", target="Grinding Station"))
    none = root()
    assert canonical_runtime_object_value_key(live) != canonical_runtime_object_value_key(none)


def test_hidden_library_permutation_and_rng_still_do_not_fragment_runtime_object_key():
    base = root()
    left = replace(
        base,
        true_state=replace(base.true_state, library=("A", "B"), rng_root_seed=1),
        pending=pending("decision.exec.1", target="Grinding Station"),
    )
    right = replace(
        base,
        true_state=replace(base.true_state, library=("B", "A"), rng_root_seed=999),
        pending=pending("decision.exec.2", target="Grinding Station"),
    )
    assert canonical_runtime_object_value_key(left) == canonical_runtime_object_value_key(right)


def main():
    tests = (
        test_different_pending_semantic_choices_do_not_merge,
        test_pending_execution_ids_do_not_fragment_same_value_state,
        test_pending_vs_no_pending_are_distinct_even_in_same_window,
        test_hidden_library_permutation_and_rng_still_do_not_fragment_runtime_object_key,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("RUNTIME PENDING VALUE KEY SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
