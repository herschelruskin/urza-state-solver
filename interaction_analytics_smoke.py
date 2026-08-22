#!/usr/bin/env python3
"""Focused smoke tests for interaction/protection episode analytics.

Run:
    py -3 interaction_analytics_smoke.py
"""

from dataclasses import replace

from urza_solver import Perm, State
from interaction_analytics import (
    BOUNCE,
    BROAD_COUNTER,
    COUNTERSPELL,
    FREE_SPELL_LOCK,
    PROACTIVE_PROTECTION,
    InteractionEpisodeTracker,
    castable_counterspells,
    interaction_classes,
    interaction_snapshot,
    zero_mana_counterspells,
)


def blue_for_smoke(card: str) -> bool:
    return card in {
        "Swan Song",
        "Force of Negation",
        "Fierce Guardianship",
        "Mana Drain",
    }


def state(**kwargs) -> State:
    base = State(turn=1, library=("A", "B"), hand=(), battlefield=())
    return replace(base, **kwargs)


def test_taxonomy_is_explicit():
    assert COUNTERSPELL in interaction_classes("Force of Will")
    assert BROAD_COUNTER in interaction_classes("Force of Will")
    assert PROACTIVE_PROTECTION in interaction_classes("Defense Grid")
    assert FREE_SPELL_LOCK in interaction_classes("Vexing Bauble")
    assert BOUNCE in interaction_classes("Sink into Stupor")


def test_own_turn_counter_availability():
    s = state(
        turn=4,
        hand=(
            "Force of Will",
            "Swan Song",
            "Force of Negation",
            "Pact of Negation",
            "Fierce Guardianship",
            "Mental Misstep",
        ),
        blue=1,
        colorless=0,
        urza=True,
    )
    live = set(castable_counterspells(s, blue_card_predicate=blue_for_smoke))
    assert {
        "Force of Will",
        "Swan Song",
        "Pact of Negation",
        "Fierce Guardianship",
        "Mental Misstep",
    } <= live
    assert "Force of Negation" not in live, "FoN alternate cost is not live on our turn"

    zero = set(zero_mana_counterspells(s, blue_card_predicate=blue_for_smoke))
    assert zero == {
        "Force of Will",
        "Pact of Negation",
        "Fierce Guardianship",
        "Mental Misstep",
    }


def test_vexing_bauble_blanks_our_no_mana_protection():
    s = state(
        turn=4,
        hand=(
            "Force of Will",
            "Swan Song",
            "Pact of Negation",
            "Fierce Guardianship",
            "Mental Misstep",
        ),
        battlefield=(Perm("Vexing Bauble"),),
        blue=1,
        colorless=0,
        urza=True,
    )
    live = set(castable_counterspells(s, blue_card_predicate=blue_for_smoke))
    assert "Pact of Negation" not in live
    assert "Force of Will" not in live
    assert "Fierce Guardianship" not in live
    assert "Swan Song" in live
    assert "Mental Misstep" in live  # pay U instead of 2 life
    assert zero_mana_counterspells(s, blue_card_predicate=blue_for_smoke) == ()

    snap = interaction_snapshot(s, blue_card_predicate=blue_for_smoke)
    assert snap.vexing_bauble_online
    assert snap.protected_line_capable


def test_defense_grid_is_distinct_proactive_protection():
    s = state(turn=4, battlefield=(Perm("Defense Grid"),), blue=0, colorless=0)
    snap = interaction_snapshot(s)
    assert snap.defense_grid_online
    assert not snap.counterspell_available
    assert snap.protected_line_capable
    assert snap.protection_piece_count_available == 1


def test_episode_tracker_records_type_count_and_first_seen_turn():
    tracker = InteractionEpisodeTracker(blue_card_predicate=blue_for_smoke)

    t1 = state(turn=1, hand=("Swan Song",), blue=0)
    tracker.observe(t1)

    t2 = state(
        turn=2,
        hand=("Defense Grid",),
        interaction_seen=("Swan Song", "Defense Grid"),
        blue=0,
    )
    tracker.observe(t2)

    t3 = state(
        turn=3,
        hand=("Pact of Negation",),
        battlefield=(Perm("Defense Grid"),),
        interaction_seen=("Swan Song", "Defense Grid", "Pact of Negation"),
        won=True,
        win_family="fixture",
    )
    before = t3
    summary = tracker.finalize(t3)
    assert t3 == before, "analytics mutated the solver state"

    first_cards = dict(summary.first_seen_turn_by_card)
    assert first_cards["Swan Song"] == 1
    assert first_cards["Defense Grid"] == 2
    assert first_cards["Pact of Negation"] == 3

    counts = dict(summary.seen_class_counts)
    assert counts[COUNTERSPELL] == 2
    assert counts[PROACTIVE_PROTECTION] == 1
    assert summary.seen_count == 3
    assert summary.win_turn == 3
    assert summary.protected_at_win
    assert summary.counterspell_at_win
    assert summary.defense_grid_at_win
    assert summary.terminal_snapshot.protection_piece_count_available == 2


def main():
    tests = [
        test_taxonomy_is_explicit,
        test_own_turn_counter_availability,
        test_vexing_bauble_blanks_our_no_mana_protection,
        test_defense_grid_is_distinct_proactive_protection,
        test_episode_tracker_records_type_count_and_first_seen_turn,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("INTERACTION ANALYTICS SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
