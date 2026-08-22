#!/usr/bin/env python3
"""Regression tests for London-bottom and persistent known-bottom information."""

from solver_architecture import InformationState
from information_state_propagation import propagate_information
from opening_information_state import (
    seed_london_bottom_information,
    unknown_draw_pool_size,
)
import urza_solver as solver


def test_keep_five_seeds_exact_london_bottom_order():
    deck = [f"C{i:02d}" for i in range(12)]
    bottom = ["C01", "C05"]
    hand, library = solver.london_opening_zones(deck, 5, bottom)
    state = solver.State(turn=1, library=library, hand=tuple(hand), battlefield=())
    info = seed_london_bottom_information(state, bottom)
    assert info.known_bottom == tuple(bottom)
    assert tuple(state.library[-2:]) == tuple(bottom)
    assert unknown_draw_pool_size(state, info) == len(state.library) - 2


def test_natural_draw_preserves_london_bottom_suffix():
    deck = [f"C{i:02d}" for i in range(12)]
    bottom = ["C01", "C05"]
    hand, library = solver.london_opening_zones(deck, 5, bottom)
    before = solver.State(turn=1, library=library, hand=tuple(hand), battlefield=())
    info = seed_london_bottom_information(before, bottom)
    after, drawn = solver.draw_from_library(before, 1)
    assert drawn
    next_info = propagate_information(before, after, info)
    assert next_info.known_bottom == tuple(bottom)
    assert unknown_draw_pool_size(after, next_info) == len(after.library) - 2


def test_scry_appends_new_bottom_below_existing_london_bottom():
    before = solver.State(
        turn=2,
        library=(
            "Force of Will",
            "Chrome Dome",
            "Tail",
            "London A",
            "London B",
        ),
        hand=(),
        battlefield=(),
    )
    prior = InformationState(known_bottom=("London A", "London B"))
    after = solver.apply_scry(before, 2, "post-mulligan scry")
    info = propagate_information(before, after, prior)
    assert info.known_top == ("Chrome Dome",)
    assert info.known_bottom == ("London A", "London B", "Force of Will")
    assert tuple(after.library[-3:]) == info.known_bottom


def test_shuffle_erases_london_and_scry_bottom_knowledge():
    before = solver.State(
        turn=2,
        library=("Island", "Tail", "London A", "London B", "Force of Will"),
        hand=(),
        battlefield=(solver.Perm("Flooded Strand"),),
        rng_root_seed=17,
    )
    prior = InformationState(
        known_bottom=("London A", "London B", "Force of Will"),
        shuffle_epoch=4,
    )
    after = solver.fetch_actions(before)[0]
    info = propagate_information(before, after, prior)
    assert info.known_bottom == ()
    assert info.known_top == ()
    assert info.shuffle_epoch == 5


def test_wrong_claimed_london_bottom_is_rejected():
    deck = [f"C{i:02d}" for i in range(12)]
    bottom = ["C01", "C05"]
    hand, library = solver.london_opening_zones(deck, 5, bottom)
    state = solver.State(turn=1, library=library, hand=tuple(hand), battlefield=())
    try:
        seed_london_bottom_information(state, ["C05", "C01"])
    except Exception:
        return
    raise AssertionError("mismatched claimed London bottom order was accepted")


def main():
    tests = [
        test_keep_five_seeds_exact_london_bottom_order,
        test_natural_draw_preserves_london_bottom_suffix,
        test_scry_appends_new_bottom_below_existing_london_bottom,
        test_shuffle_erases_london_and_scry_bottom_knowledge,
        test_wrong_claimed_london_bottom_is_rejected,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("OPENING INFORMATION STATE SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
