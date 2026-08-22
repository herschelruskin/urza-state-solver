#!/usr/bin/env python3
"""Focused smoke tests for seed-independent strategic value identity."""

from dataclasses import replace

from solver_architecture import InformationState, canonical_markov_state_key
from strategic_value_state import (
    LibraryBeliefKey,
    StrategicKeyProfiler,
    canonical_strategic_state_key,
    project_strategic_value_state,
)
from urza_solver import Perm, State


def base_state(**kwargs):
    values = dict(
        turn=2,
        library=("Island", "Sol Ring", "Swan Song", "Mox Opal"),
        hand=("Mana Vault", "Island"),
        battlefield=(
            Perm("Island", tapped=True),
            Perm("Mox Opal", tapped=False),
        ),
        graveyard=("Gitaxian Probe",),
        exile=(),
        blue=1,
        colorless=0,
        land_played=True,
        rng_root_seed=11,
    )
    values.update(kwargs)
    return State(**values)


def key(state, info=None, **kwargs):
    return canonical_strategic_state_key(
        state,
        InformationState() if info is None else info,
        **kwargs,
    )


def test_hidden_order_and_seed_do_not_fragment_value_identity():
    a = base_state(rng_root_seed=1)
    b = replace(
        a,
        library=("Swan Song", "Island", "Mox Opal", "Sol Ring"),
        rng_root_seed=999,
    )
    assert canonical_markov_state_key(a) != canonical_markov_state_key(b)
    assert key(a) == key(b)


def test_reporting_history_and_legacy_flags_do_not_fragment_base_value():
    a = base_state()
    b = replace(
        a,
        trace=("different route",),
        interaction_seen=("Force of Will", "Swan Song"),
        urza_cast_turn=1,
        win_family="Chrome Dome",
        construct=not a.construct,
        top_access=not a.top_access,
    )
    assert key(a) == key(b)

    wa = replace(a, won=True, win_family="Chrome Dome")
    wb = replace(a, won=True, win_family="Top + Reality Chip")
    assert key(wa) == key(wb)


def test_information_constraints_change_belief_identity():
    s = base_state()
    no_knowledge = InformationState()
    top_known = InformationState(known_top=("Island",))
    other_top_known = InformationState(known_top=("Swan Song",))
    counted = InformationState(known_library_counts=(("Island", 1),))

    assert key(s, no_knowledge) != key(s, top_known)
    assert key(s, top_known) != key(s, other_top_known)
    assert key(s, no_knowledge) != key(s, counted)


def test_shuffle_epoch_alone_is_not_value_state():
    s = base_state()
    a = InformationState(shuffle_epoch=1)
    b = InformationState(shuffle_epoch=99)
    assert key(s, a) == key(s, b)


def test_real_resources_and_pending_state_remain_distinct():
    s = base_state()
    assert key(s) != key(replace(s, blue=2))
    assert key(s) != key(replace(s, land_played=False))
    assert key(s) != key(replace(s, remora_upkeep_pending=True))
    assert key(s) != key(replace(s, saga3_pending=True))
    assert key(s) != key(replace(s, commander_casts_from_zone=1))

    untapped = replace(s, battlefield=(Perm("Island", tapped=False), Perm("Mox Opal")))
    assert key(s) != key(untapped)


def test_perm_provenance_is_ignored_but_refund_credit_is_not():
    common = dict(
        name="Grinding Station",
        tapped=True,
        sick=False,
        knack_granted=True,
    )
    a = base_state(
        battlefield=(Perm(**common, knack_source="Banishing Knack", instance_tag=1),)
    )
    b = base_state(
        battlefield=(Perm(**common, knack_source="Retraction Helix", instance_tag=999),)
    )
    assert key(a) == key(b)

    credited = base_state(
        battlefield=(Perm(**common, producer_urza_ready=True),)
    )
    no_credit = base_state(
        battlefield=(Perm(**common, producer_urza_ready=False),)
    )
    assert key(credited) != key(no_credit)


def test_objective_memory_is_explicit_and_minimal():
    s = base_state()
    base = key(s)
    seen = key(s, objective_memory={"interaction_seen_by_t3": True})
    not_seen = key(s, objective_memory={"interaction_seen_by_t3": False})
    assert base != seen
    assert seen != not_seen


def test_library_belief_uses_multiset_not_order():
    a = base_state(library=("Island", "Island", "Sol Ring"))
    b = base_state(library=("Sol Ring", "Island", "Island"))
    ka = LibraryBeliefKey.from_state(a, InformationState())
    kb = LibraryBeliefKey.from_state(b, InformationState())
    assert ka == kb
    assert ka.remaining_counts == (("Island", 2), ("Sol Ring", 1))


def test_profiler_measures_collapse_without_changing_states():
    a = base_state(rng_root_seed=1)
    b = replace(
        a,
        library=("Mox Opal", "Swan Song", "Sol Ring", "Island"),
        rng_root_seed=2,
    )
    before_a = a
    before_b = b

    profiler = StrategicKeyProfiler()
    profiler.observe(a, InformationState())
    profiler.observe(b, InformationState())
    summary = profiler.summary()

    assert a == before_a and b == before_b
    assert summary["observations"] == 2
    assert summary["concrete_unique"] == 2
    assert summary["concrete_information_unique"] == 2
    assert summary["strategic_unique"] == 1
    assert summary["concrete_to_strategic_collapse_fraction"] == 0.5
    assert summary["concrete_information_to_strategic_collapse_fraction"] == 0.5
    assert summary["estimated_strategic_cache_hit_fraction"] == 0.5
    assert summary["by_turn"][2]["strategic_unique"] == 1


def test_profiler_keeps_same_concrete_state_with_different_information_distinct():
    state = base_state()
    profiler = StrategicKeyProfiler()
    profiler.observe(state, InformationState())
    profiler.observe(state, InformationState(known_top=("Island",)))
    summary = profiler.summary()

    assert summary["observations"] == 2
    assert summary["concrete_unique"] == 1
    assert summary["concrete_information_unique"] == 2
    assert summary["strategic_unique"] == 2
    assert summary["concrete_information_to_strategic_collapse_fraction"] == 0.0


def test_projection_is_a_separate_value_object_not_policy_view():
    s = base_state(construct=True, top_access=True)
    projection = project_strategic_value_state(s, InformationState())
    assert not hasattr(projection, "construct")
    assert not hasattr(projection, "top_access")
    assert not hasattr(projection, "rng_root_seed")
    assert not hasattr(projection, "trace")
    assert hasattr(projection, "library_belief")


def main():
    tests = [
        test_hidden_order_and_seed_do_not_fragment_value_identity,
        test_reporting_history_and_legacy_flags_do_not_fragment_base_value,
        test_information_constraints_change_belief_identity,
        test_shuffle_epoch_alone_is_not_value_state,
        test_real_resources_and_pending_state_remain_distinct,
        test_perm_provenance_is_ignored_but_refund_credit_is_not,
        test_objective_memory_is_explicit_and_minimal,
        test_library_belief_uses_multiset_not_order,
        test_profiler_measures_collapse_without_changing_states,
        test_profiler_keeps_same_concrete_state_with_different_information_distinct,
        test_projection_is_a_separate_value_object_not_policy_view,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("STRATEGIC VALUE STATE SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
