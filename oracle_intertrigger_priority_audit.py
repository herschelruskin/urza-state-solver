#!/usr/bin/env python3
"""Demonstrate material Oracle states lost by atomic cast-trigger resolution.

This is an audit, not the final stack implementation.  It proves that merely
permuting Assistant/Uthros/Gadgeteer/VFC triggers is not enough for a strict
clairvoyant ceiling because legal priority actions can occur between individual
trigger resolutions.
"""

from dataclasses import replace

import urza_solver as solver
from solver_architecture import canonical_markov_state_key


def _atomic_keys(state, card):
    return {
        canonical_markov_state_key(x)
        for x in solver.artifact_cast_trigger_variants(state, card)
    }


def test_gadgeteer_clue_can_be_cracked_before_uthros():
    # Cast trigger stack can legally put Gadgeteer above Uthros.  Once Gadgeteer
    # resolves, the Clue exists and priority returns before Uthros resolves.
    # Cracking that Clue changes which card Uthros subsequently draws.
    base = solver.State(
        turn=3,
        library=("A", "B", "C", "Tail"),
        hand=(),
        battlefield=(
            solver.Perm("Forensic Gadgeteer"),
            solver.Perm("Uthros Research Craft"),
        ),
        uthros_counters=3,
        colorless=1,  # Gadgeteer reduces Clue activation from 2 to 1.
    )

    after_gadget = solver._resolve_artifact_cast_trigger_order(
        base, "Welding Jar", ("gadgeteer",)
    )
    clues = [p for p in after_gadget.battlefield if p.mode == "clue"]
    assert len(clues) == 1

    cracked = solver.clue_draw_actions(after_gadget)
    assert cracked, "new Gadgeteer Clue must be activatable in the priority window"
    after_clue = cracked[0]
    assert after_clue.hand == ("A",)
    assert after_clue.library == ("B", "C", "Tail")

    final = solver._resolve_artifact_cast_trigger_order(
        after_clue, "Welding Jar", ("uthros",)
    )
    assert final.hand == ("A", "B")
    assert final.library == ("C", "Tail")
    assert final.uthros_counters == 4

    # Atomic trigger permutation cannot represent the intervening Clue crack.
    assert canonical_markov_state_key(final) not in _atomic_keys(base, "Welding Jar")


def test_top_can_reorder_between_gadgeteer_and_uthros():
    base = solver.State(
        turn=3,
        library=("A", "B", "C", "Tail"),
        hand=(),
        battlefield=(
            solver.Perm("Forensic Gadgeteer"),
            solver.Perm("Uthros Research Craft"),
            solver.Perm("Sensei's Divining Top"),
        ),
        uthros_counters=3,
        colorless=1,
    )
    after_gadget = solver._resolve_artifact_cast_trigger_order(
        base, "Welding Jar", ("gadgeteer",)
    )
    top_variants = [
        x for x in solver.top_actions(after_gadget)
        if x.trace and x.trace[-1] == "Top reorder"
    ]
    assert top_variants
    chosen = next(x for x in top_variants if x.library[:3] == ("C", "B", "A"))
    final = solver._resolve_artifact_cast_trigger_order(
        chosen, "Welding Jar", ("uthros",)
    )
    assert final.hand == ("C",)
    assert final.library[:2] == ("B", "A")
    assert canonical_markov_state_key(final) not in _atomic_keys(base, "Welding Jar")


def test_bauble_position_matters_when_pending_spell_can_be_targeted():
    # This test records the logical precondition the final stack implementation
    # must preserve: a zero-mana spell is still on the stack until Bauble's
    # trigger actually resolves.  Therefore ordering Bauble below other triggers
    # leaves priority windows in which An Offer You Can't Refuse may still target
    # the pending spell.  The current atomic helper has no representation for
    # that pending spell, which is exactly the gap under audit.
    base = solver.State(
        turn=3,
        library=("A", "B", "Tail"),
        hand=("An Offer You Can't Refuse",),
        battlefield=(
            solver.Perm("Vexing Bauble"),
            solver.Perm("Artificer's Assistant"),
            solver.Perm("Uthros Research Craft"),
        ),
        uthros_counters=3,
        blue=1,
    )
    # Existing helper intentionally excludes Bauble from its trigger multiset;
    # the final stack model must no longer do so.
    tokens = solver._artifact_cast_trigger_tokens(base, "Welding Jar")
    assert "assistant" in tokens and "uthros" in tokens
    assert "bauble" not in tokens
    assert "An Offer You Can't Refuse" in base.hand


def main():
    tests = (
        test_gadgeteer_clue_can_be_cracked_before_uthros,
        test_top_can_reorder_between_gadgeteer_and_uthros,
        test_bauble_position_matters_when_pending_spell_can_be_targeted,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("ORACLE INTER-TRIGGER PRIORITY AUDIT: MATERIAL GAP CONFIRMED")


if __name__ == "__main__":
    main()
