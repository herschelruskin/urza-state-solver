#!/usr/bin/env python3
"""Controlled tests for information-safe Phase-4 hidden-world sampling."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from phase4_hidden_world import (
    HiddenWorldSampler,
    HiddenWorldSamplingError,
    materialize_hidden_world,
)
from solver_architecture import InformationState
from strategic_value_state import LibraryBeliefKey


@dataclass(frozen=True)
class FakeState:
    library: tuple[str, ...]
    rng_root_seed: int = 999


@dataclass(frozen=True)
class FakeRuntime:
    true_state: FakeState


def assert_raises(fn, exc_type) -> None:
    try:
        fn()
    except exc_type:
        return
    raise AssertionError(f"expected {exc_type.__name__}")


def main() -> None:
    # Two different concrete hidden permutations with identical legal information
    # must induce the same strategic belief and therefore the same sampled world.
    state_a = FakeState(("A", "B", "C", "A", "D", "E"), rng_root_seed=101)
    state_b = FakeState(("C", "A", "E", "B", "A", "D"), rng_root_seed=202)
    info = InformationState(
        known_top=("A",),
        known_bottom=("D",),
        known_library_counts=(("A", 1),),
    )
    belief_a = LibraryBeliefKey.from_state(state_a, info)
    belief_b = LibraryBeliefKey.from_state(state_b, info)
    assert belief_a == belief_b

    sampler = HiddenWorldSampler(root_seed=424242)
    world_a = sampler.sample(belief_a, sample_id=7)
    world_b = sampler.sample(belief_b, sample_id=7)
    assert world_a == world_b
    assert world_a.library[0] == "A"
    assert world_a.library[-1] == "D"
    assert Counter(world_a.library) == Counter(state_a.library)

    # Common-random-number coordinate is stable and independent of actual-game RNG.
    assert world_a.rng_root_seed != state_a.rng_root_seed
    assert world_a.rng_root_seed != state_b.rng_root_seed
    assert sampler.sample(belief_a, sample_id=7) == world_a

    # Different MC coordinates should explore more than one middle permutation.
    sampled_orders = {sampler.sample(belief_a, sample_id=i).library for i in range(12)}
    assert len(sampled_orders) > 1
    for library in sampled_orders:
        assert library[0] == "A"
        assert library[-1] == "D"
        assert Counter(library) == Counter(state_a.library)

    # Materialization is copy-on-write: actual runtime/order/seed are unchanged.
    actual = FakeRuntime(state_a)
    rollout = materialize_hidden_world(actual, world_a)
    assert actual.true_state == state_a
    assert rollout is not actual
    assert rollout.true_state.library == world_a.library
    assert rollout.true_state.rng_root_seed == world_a.rng_root_seed

    # Invalid legal-information constraints fail loudly rather than silently leak
    # or invent cards.
    bad_top = LibraryBeliefKey(
        remaining_counts=(("A", 1),),
        known_top=("B",),
    )
    assert_raises(lambda: sampler.sample(bad_top, 0), HiddenWorldSamplingError)
    bad_count = LibraryBeliefKey(
        remaining_counts=(("A", 1),),
        known_library_counts=(("A", 2),),
    )
    assert_raises(lambda: sampler.sample(bad_count, 0), HiddenWorldSamplingError)

    print("PASS exact hidden-order independence")
    print("PASS known top/bottom and multiset preservation")
    print("PASS isolated rollout RNG + copy-on-write materialization")
    print("PASS malformed belief rejection")
    print("PHASE 4 HIDDEN-WORLD SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
