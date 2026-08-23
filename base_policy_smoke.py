#!/usr/bin/env python3
"""Focused smokes for the deterministic information-constrained base policy."""

import inspect

import urza_solver as solver
from non_oracle_base_policy import DeterministicBasePolicy
from non_oracle_runtime import (
    apply_runtime_action,
    begin_committed_artifact_cast,
    make_runtime_state,
    record_artifact_entry,
    runtime_decision_request,
    sacrifice_permanent,
)
from solver_architecture import InformationState


def run_until_no_choice(runtime, policy, *, limit=64):
    for _ in range(limit):
        request = runtime_decision_request(runtime, horizon=6, policy_id=policy.policy_id)
        if not request.actions:
            return runtime
        action = policy.choose_request(request)
        runtime = apply_runtime_action(runtime, action)
    raise AssertionError("base-policy runtime segment exceeded step limit")


def test_policy_api_has_no_raw_state_parameter():
    params = tuple(inspect.signature(DeterministicBasePolicy.choose).parameters)
    assert params == ("self", "observation", "actions", "context")
    source = inspect.getsource(DeterministicBasePolicy.choose)
    assert "true_state" not in source
    assert "library" not in source
    assert "root_seed" not in source


def test_same_public_request_same_choice_across_hidden_futures():
    policy = DeterministicBasePolicy()
    battlefield = (
        solver.Perm("Grinding Station", tapped=True),
        solver.Perm("Prized Statue"),
    )
    left = make_runtime_state(
        solver.State(turn=2, library=("A", "B", "C"), hand=(), battlefield=battlefield)
    )
    right = make_runtime_state(
        solver.State(turn=2, library=("C", "A", "B"), hand=(), battlefield=battlefield)
    )
    left = record_artifact_entry(left, ("Prized Statue",), source="fixture")
    right = record_artifact_entry(right, ("Prized Statue",), source="fixture")
    lreq = runtime_decision_request(left, horizon=6, policy_id=policy.policy_id)
    rreq = runtime_decision_request(right, horizon=6, policy_id=policy.policy_id)
    assert lreq.observation.key() == rreq.observation.key()
    assert policy.choose_request(lreq).strategic_key() == policy.choose_request(rreq).strategic_key()


def test_policy_uses_legally_known_top_for_assistant_uthros_order_only():
    policy = DeterministicBasePolicy()
    state = solver.State(
        turn=3,
        library=("Power Artifact", "Junk", "Tail"),
        hand=("Welding Jar",),
        battlefield=(
            solver.Perm("Artificer's Assistant"),
            solver.Perm("Uthros Research Craft"),
        ),
        uthros_counters=3,
    )

    unknown = make_runtime_state(state, InformationState())
    unknown = begin_committed_artifact_cast(unknown, "Welding Jar", mana_spent=0)
    ureq = runtime_decision_request(unknown, horizon=6, policy_id=policy.policy_id)
    unknown_choice = policy.choose_request(ureq)
    assert unknown_choice.label.startswith("Resolve: assistant_scry_1 -> uthros_draw_and_counter")

    known = make_runtime_state(state, InformationState(known_top=("Power Artifact",)))
    known = begin_committed_artifact_cast(known, "Welding Jar", mana_spent=0)
    kreq = runtime_decision_request(known, horizon=6, policy_id=policy.policy_id)
    known_choice = policy.choose_request(kreq)
    assert known_choice.label.startswith("Resolve: uthros_draw_and_counter -> assistant_scry_1")


def test_scry_policy_uses_only_revealed_cards_and_keeps_high_value_card():
    policy = DeterministicBasePolicy()
    runtime = make_runtime_state(
        solver.State(
            turn=2,
            library=("Power Artifact", "Junk", "HIDDEN"),
            hand=(),
            battlefield=(solver.Perm("Witching Well"),),
        )
    )
    runtime = record_artifact_entry(runtime, ("Witching Well",), source="Well enters")
    runtime = apply_runtime_action(
        runtime,
        policy.choose_request(runtime_decision_request(runtime, horizon=6)),
    )
    request = runtime_decision_request(runtime, horizon=6, policy_id=policy.policy_id)
    choice = policy.choose_request(request)
    assert "HIDDEN" not in choice.label
    assert dict(choice.parameters)["top"][0] == "Power Artifact"


def test_base_policy_can_finish_committed_artifact_stack_without_oracle_search():
    policy = DeterministicBasePolicy()
    runtime = make_runtime_state(
        solver.State(
            turn=3,
            library=("Power Artifact", "Junk", "Tail"),
            hand=("Welding Jar",),
            battlefield=(
                solver.Perm("Artificer's Assistant"),
                solver.Perm("Uthros Research Craft"),
            ),
            uthros_counters=3,
        )
    )
    runtime = begin_committed_artifact_cast(runtime, "Welding Jar", mana_spent=0)
    runtime = run_until_no_choice(runtime, policy)
    assert not runtime.stack.objects
    assert runtime.pending is None
    assert any(p.name == "Welding Jar" for p in runtime.true_state.battlefield)
    assert "Power Artifact" in runtime.true_state.hand


def test_base_policy_resolves_statue_death_treasure_and_producer_untap():
    policy = DeterministicBasePolicy()
    runtime = make_runtime_state(
        solver.State(
            turn=3,
            library=(),
            hand=(),
            battlefield=(
                solver.Perm("Grinding Station", tapped=True),
                solver.Perm("Prized Statue"),
            ),
        )
    )
    statue = next(p for p in runtime.true_state.battlefield if p.name == "Prized Statue")
    runtime = sacrifice_permanent(
        runtime,
        instance_tag=statue.instance_tag,
        source="Reshape fixture",
    )
    runtime = run_until_no_choice(runtime, policy)
    station = next(p for p in runtime.true_state.battlefield if p.name == "Grinding Station")
    assert not station.tapped
    assert any(p.name == "Treasure" for p in runtime.true_state.battlefield)
    assert "Prized Statue" in runtime.true_state.graveyard


def test_choice_is_repeatable_for_fixed_request():
    policy = DeterministicBasePolicy()
    runtime = make_runtime_state(
        solver.State(
            turn=2,
            library=("A",),
            hand=(),
            battlefield=(
                solver.Perm("Grinding Station", tapped=True),
                solver.Perm("Prized Statue"),
            ),
        )
    )
    runtime = record_artifact_entry(runtime, ("Prized Statue",), source="fixture")
    request = runtime_decision_request(runtime, horizon=6, policy_id=policy.policy_id)
    keys = [policy.choose_request(request).canonical_key() for _ in range(10)]
    assert len(set(keys)) == 1


def main():
    tests = (
        test_policy_api_has_no_raw_state_parameter,
        test_same_public_request_same_choice_across_hidden_futures,
        test_policy_uses_legally_known_top_for_assistant_uthros_order_only,
        test_scry_policy_uses_only_revealed_cards_and_keeps_high_value_card,
        test_base_policy_can_finish_committed_artifact_stack_without_oracle_search,
        test_base_policy_resolves_statue_death_treasure_and_producer_untap,
        test_choice_is_repeatable_for_fixed_request,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("DETERMINISTIC BASE POLICY SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
