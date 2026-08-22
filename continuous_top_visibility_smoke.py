#!/usr/bin/env python3
"""Regressions for continuous top-card look permissions.

Reality Chip and Fortune Teller's Talent both let their controller look at the
current top card independently of whether the separate play-from-top permission
is active.  This matters at trigger-order / priority boundaries after a cast.
"""

import urza_solver as solver
from information_state_propagation import initial_information, propagate_information


def test_unattached_reality_chip_still_reveals_current_top():
    state = solver.State(
        turn=2,
        library=("Hidden A", "Hidden B"),
        hand=(),
        battlefield=(solver.Perm("The Reality Chip"),),
        chip_attached=False,
    )
    info = initial_information(state)
    assert info.known_top == ("Hidden A",)


def test_level_one_ftt_reveals_top_before_play_permission_is_active():
    state = solver.State(
        turn=2,
        library=("Hidden A", "Hidden B"),
        hand=(),
        battlefield=(solver.Perm("Fortune Teller's Talent"),),
        ftt_level=1,
        spell_cast_this_turn=False,
    )
    info = initial_information(state)
    assert info.known_top == ("Hidden A",)


def test_look_permission_refreshes_after_known_top_changes():
    before = solver.State(
        turn=2,
        library=("Hidden A", "Hidden B", "Hidden C"),
        hand=(),
        battlefield=(solver.Perm("The Reality Chip"),),
    )
    prior = initial_information(before)
    after, drawn = solver.draw_from_library(before, 1)
    assert drawn == ("Hidden A",)
    info = propagate_information(before, after, prior)
    assert info.known_top == ("Hidden B",)


def test_memory_survives_source_leaving_but_new_unknown_top_does_not_leak():
    before = solver.State(
        turn=2,
        library=("Known A", "Unknown B", "Unknown C"),
        hand=(),
        battlefield=(solver.Perm("Fortune Teller's Talent"),),
    )
    prior = initial_information(before)
    # Remove FTT without changing the library. Remembering Known A remains legal.
    without = solver.remove_perm(before, 0, to_grave=True)
    info_without = propagate_information(before, without, prior)
    assert info_without.known_top == ("Known A",)

    # Once Known A is consumed with no look source remaining, Unknown B is not
    # automatically exposed.
    after, drawn = solver.draw_from_library(without, 1)
    assert drawn == ("Known A",)
    info_after = propagate_information(without, after, info_without)
    assert info_after.known_top == ()


def main():
    tests = (
        test_unattached_reality_chip_still_reveals_current_top,
        test_level_one_ftt_reveals_top_before_play_permission_is_active,
        test_look_permission_refreshes_after_known_top_changes,
        test_memory_survives_source_leaving_but_new_unknown_top_does_not_leak,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("CONTINUOUS TOP VISIBILITY SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
