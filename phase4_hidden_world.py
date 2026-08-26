#!/usr/bin/env python3
"""Information-safe hidden-library sampling for Phase-4 Monte Carlo rollouts.

This module samples a concrete hidden library from ``LibraryBeliefKey`` rather
than from the actual unknown library permutation.  It is deliberately separate
from policy choice and Magic rules execution.

Invariants:
- exact unknown order is never an input to sampling;
- known-top order and known-bottom order are preserved exactly;
- the remaining card multiset is preserved exactly;
- rollout game RNG roots are derived from an MC root seed, never the actual game
  ``rng_root_seed``;
- a (belief, sample_id) pair is deterministic, enabling common random numbers
  across competing root actions;
- materializing a rollout world returns a new runtime/state and never mutates the
  actual game state.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from typing import Any, Tuple

from solver_architecture import RandomStreams, stable_digest
from strategic_value_state import LibraryBeliefKey


PHASE4_HIDDEN_WORLD_VERSION = "urza-hidden-world-v1"


class HiddenWorldSamplingError(ValueError):
    pass


@dataclass(frozen=True)
class SampledHiddenWorld:
    sample_id: str
    library: Tuple[str, ...]
    rng_root_seed: int
    belief_digest: str
    version: str = PHASE4_HIDDEN_WORLD_VERSION


class HiddenWorldSampler:
    """Deterministic policy-RNG sampler keyed by legal information only."""

    def __init__(self, root_seed: int) -> None:
        self.root_seed = int(root_seed)
        self.streams = RandomStreams(self.root_seed)

    @staticmethod
    def _validated_counter(belief: LibraryBeliefKey) -> Counter[str]:
        counts: Counter[str] = Counter()
        for card, raw_count in belief.remaining_counts:
            count = int(raw_count)
            if count < 0:
                raise HiddenWorldSamplingError(
                    f"negative remaining count for {card!r}: {count}"
                )
            if count:
                counts[str(card)] += count

        total = sum(counts.values())
        if len(belief.known_top) + len(belief.known_bottom) > total:
            raise HiddenWorldSamplingError(
                "known top/bottom contain more cards than the remaining library"
            )

        for card, raw_count in belief.known_library_counts:
            count = int(raw_count)
            if count < 0:
                raise HiddenWorldSamplingError(
                    f"negative known library count for {card!r}: {count}"
                )
            if count > counts.get(str(card), 0):
                raise HiddenWorldSamplingError(
                    f"known library count {card!r}={count} exceeds remaining count "
                    f"{counts.get(str(card), 0)}"
                )

        for location, cards in (
            ("known_top", belief.known_top),
            ("known_bottom", belief.known_bottom),
        ):
            for card in cards:
                card = str(card)
                if counts.get(card, 0) <= 0:
                    raise HiddenWorldSamplingError(
                        f"{location} requires unavailable card {card!r}"
                    )
                counts[card] -= 1
                if counts[card] == 0:
                    del counts[card]
        return counts

    def sample(self, belief: LibraryBeliefKey, sample_id: Any) -> SampledHiddenWorld:
        """Sample one hidden world consistent with ``belief``.

        ``sample_id`` is an external Monte-Carlo coordinate. Reusing the same
        sample id for every competing root action gives common random numbers.
        """
        middle_counts = self._validated_counter(belief)
        belief_digest = stable_digest(
            belief,
            version=PHASE4_HIDDEN_WORLD_VERSION + "-belief",
        )
        coordinate = (belief_digest, repr(sample_id))
        rng = self.streams.policy_rng(("hidden-world-order", coordinate))

        middle = []
        for card, count in sorted(middle_counts.items()):
            middle.extend([card] * int(count))
        rng.shuffle(middle)

        library = (
            tuple(str(card) for card in belief.known_top)
            + tuple(middle)
            + tuple(str(card) for card in belief.known_bottom)
        )
        rollout_seed = self.streams.seed_for("rollout-game", coordinate)
        return SampledHiddenWorld(
            sample_id=str(sample_id),
            library=library,
            rng_root_seed=rollout_seed,
            belief_digest=belief_digest,
        )


def materialize_hidden_world(runtime: Any, world: SampledHiddenWorld) -> Any:
    """Return a rollout clone with sampled hidden order and isolated game RNG.

    This helper intentionally uses ``dataclasses.replace`` and does not mutate the
    actual runtime.  It is rules/evaluator-side infrastructure; policies must
    still receive only the normal policy observation.
    """
    true_state = getattr(runtime, "true_state", None)
    if true_state is None:
        raise TypeError("runtime must expose a dataclass true_state")
    sampled_state = replace(
        true_state,
        library=tuple(world.library),
        rng_root_seed=int(world.rng_root_seed),
    )
    return replace(runtime, true_state=sampled_state)
