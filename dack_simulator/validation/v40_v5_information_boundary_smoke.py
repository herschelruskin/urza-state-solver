#!/usr/bin/env python3
"""v40 v5 information-boundary regression without expensive gameplay.

The original bounded v5 teacher must evaluate the *unknown-card multiset*,
not the actual 92-card future library order from the physical outer game.
This smoke monkeypatches ONLY the rollout terminal evaluator, records its
requested hypothetical library draws, and compares them under two different
permutations of the same unknown 92 physical card names. It is NOT a
validation of teacher Q accuracy, game rules, or the complete keep policy.
"""
from __future__ import annotations

from collections import Counter
import random

import dack_mulligan_branchbound_v1_20261031 as bounded
import dack_paired_counterfactual_v5_stable_chance_20261031 as teacher


def run():
    ref = teacher.reference
    deck = list(ref.VARIANTS["one_key_34"])
    # Use a genuine 99-card multiset, including duplicate Plains copies.
    seven = (
        "Ancient Tomb", "Mana Vault", "Plains",
        "Enlightened Tutor", "Scroll Rack",
        "Mind Stone", "Voltaic Key",
    )
    pool = Counter(deck)
    for name in seven:
        assert pool[name] >= 1, name
        pool[name] -= 1
    unseen = [name for name, count in sorted(pool.items()) for _ in range(count)]
    assert len(unseen) == 92
    assert Counter(seven) + Counter(unseen) == Counter(deck)
    shuffled = unseen.copy()
    random.Random(401).shuffle(shuffled)
    assert unseen != shuffled
    hand = tuple(sorted(seven[:6]))
    bottom = (seven[6],)
    observed = []

    def fake_game(hand_arg, library_arg, seat, beam, max_turn=3):
        # The *requested* physical hypothetical future is observable to
        # this test; no beam search or physical wins are executed.
        assert int(seat) == 2 and int(beam) == 160
        assert int(max_turn) == 3
        observed.append((tuple(hand_arg), tuple(library_arg)))
        library = tuple(library_arg)
        assert len(library) == 93  # unknown92 plus one London bottom
        assert library[-1] == bottom[0]
        # Synthetic witness, deliberately dependent on top cards. It is
        # NOT a real Dack deployment simulation outcome.
        top = library[:3]
        return 2 if ("Mana Vault" in top or "Sol Ring" in top) else 3

    original = bounded.d._win_turn_from_unknown_order
    try:
        bounded.d._win_turn_from_unknown_order = fake_game
        a, count_a, pruned_a = bounded._rollout_prefix(
            hand, tuple(unseen), bottom, 2, 160, 8, .5,
            (0, 0, 0), -1., (-100, -100, -100)
        )
        future_a = tuple(observed)
        observed.clear()
        b, count_b, pruned_b = bounded._rollout_prefix(
            hand, tuple(shuffled), bottom, 2, 160, 8, .5,
            (0, 0, 0), -1., (-100, -100, -100)
        )
        future_b = tuple(observed)
    finally:
        bounded.d._win_turn_from_unknown_order = original

    assert not pruned_a and not pruned_b
    assert count_a == count_b == 8
    assert len(future_a) == len(future_b) == 8
    assert future_a == future_b, "v5 hypothetical futures depend on hidden92 order"
    assert a == b, "v5 hypothetical value depends on hidden92 order"
    assert a["utility"] == a["le2"] + .5 * a["t3"]
    assert a["le3"] == a["le2"] + a["t3"]
    assert bounded.d._win_turn_from_unknown_order is original
    print("DACK_V40_V5_BOUND_SAMPLER_INFORMATION_BOUNDARY_PASS", {
        "hypothetical_futures_per_permutation": 8,
        "hidden92_order_invariant": True,
        "same_hypothetical_libraries": True,
        "synthetic_no_physical_gameplay": True,
        "complete_v5_keep_policy_fidelity_not_proven": True,
    }, flush=True)


if __name__ == "__main__":
    run()
