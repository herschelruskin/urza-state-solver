#!/usr/bin/env python3
"""Profile current Phase-2 episode coverage on real shuffled deck openings.

Diagnostic only: this intentionally does NOT choose mulligans yet. Each sample is a
fresh shuffled seven plus the modeled multiplayer turn-one draw. The purpose is to
rank hard runtime blockers and expose both terminal failures and silent action gaps.

A horizon feature is not automatically a bug: modeled cards can remain unused
because they were uncastable, deprioritized, or drawn late. Rows explicitly ending
in ``_unmodeled`` or ``_partial`` are implementation audit signals and should be
worked down before Phase 2 is considered breadth-complete.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import random

import urza_solver as solver
from non_oracle_episode import run_deterministic_episode
from non_oracle_runtime import make_runtime_state

SIMPLE_TUTOR_CARDS = frozenset({
    "Dizzy Spell", "Muddle the Mixture", "Merchant Scroll", "Mystical Tutor",
    "Spellseeker",
})
ARTIFACT_TUTOR_CARDS = frozenset({
    "Reshape", "Transmute Artifact", "Whir of Invention", "Scour for Scrap",
})
NONARTIFACT_ENGINE_CARDS = frozenset({
    "Mystic Remora", "Rhystic Study", "Fortune Teller's Talent",
    "Faerie Mastermind", "Forensic Gadgeteer", "Artificer's Assistant",
    "Valley Floodcaller", "Spellseeker", "Tezzeret, Cruel Captain",
})
COMBO_SPELL_CARDS = frozenset({
    "Power Artifact", "Banishing Knack", "Retraction Helix", "Dramatic Reversal",
})
SPECIAL_ARTIFACT_CASTS = frozenset({"Mox Diamond", "Everflowing Chalice"})


def opening_runtime(seed: int, deck):
    cards = list(deck)
    random.Random(int(seed)).shuffle(cards)
    hand = tuple(cards[:7])
    library = tuple(cards[7:])
    if library:
        hand = hand + (library[0],)
        library = library[1:]
    return make_runtime_state(
        solver.State(
            turn=1,
            library=library,
            hand=hand,
            battlefield=(),
            rng_root_seed=int(seed),
            trace=("--- Turn 1 --- [Phase2 coverage]",),
        )
    )


def _unsupported_reason(exc: NotImplementedError) -> str:
    text = str(exc).strip().lower()
    if "cam etb target" in text:
        return "unsupported_cam_etb_target"
    if "cam ltb target" in text:
        return "unsupported_cam_ltb_target"
    if "mox diamond" in text:
        return "unsupported_mox_diamond"
    if "everflowing chalice" in text or "chalice" in text:
        return "unsupported_everflowing_chalice"
    compact = "_".join(text.split())[:80]
    return "unsupported_exception:" + (compact or exc.__class__.__name__.lower())


def _horizon_state_features(state: solver.State):
    """Strategic families still present at T7 after a T6 no-win trajectory."""
    hand = set(state.hand)
    battlefield_names = {p.name for p in state.battlefield}
    families = set()

    if hand & SIMPLE_TUTOR_CARDS:
        families.add("hand_simple_tutor_present")
    if hand & ARTIFACT_TUTOR_CARDS:
        families.add("hand_artifact_tutor_present")
    if hand & NONARTIFACT_ENGINE_CARDS:
        families.add("hand_nonartifact_engine_present")
    if hand & COMBO_SPELL_CARDS:
        families.add("hand_combo_nonartifact_present")
    if hand & SPECIAL_ARTIFACT_CASTS:
        families.add("hand_special_artifact_unmodeled")

    generic_nonartifact = {
        card for card in hand
        if card not in solver.ARTIFACTS
        and card not in solver.ALL_LANDS
        and card != solver.COMMANDER
        and card not in SIMPLE_TUTOR_CARDS
        and card not in ARTIFACT_TUTOR_CARDS
        and card not in NONARTIFACT_ENGINE_CARDS
        and card not in COMBO_SPELL_CARDS
    }
    if generic_nonartifact:
        families.add("hand_other_nonartifact_unmodeled")

    if "Sensei's Divining Top" in battlefield_names:
        families.add("battlefield_top_activation_unmodeled")
    if "The One Ring" in battlefield_names:
        families.add("battlefield_one_ring_draw_unmodeled")
    if any(p.mode == "clue" for p in state.battlefield):
        families.add("battlefield_clue_draw_unmodeled")
    if "Grinding Station" in battlefield_names:
        families.add("battlefield_station_activation_unmodeled")
    if state.urza:
        families.add("battlefield_urza_spin_unmodeled")
    if "The Reality Chip" in battlefield_names and not state.chip_attached:
        families.add("battlefield_chip_reconfigure_unmodeled")
    if any(name in battlefield_names for name in {"Voltaic Key", "Manifold Key"}):
        families.add("battlefield_key_activation_unmodeled")
    if "Uthros Research Craft" in battlefield_names:
        families.add("battlefield_uthros_activation_unmodeled")
    if "Sewer-veillance Cam" in battlefield_names:
        families.add("battlefield_cam_draw_activation_unmodeled")
        if (
            "Reshape" in hand
            or "Transmute Artifact" in hand
            or "Repurposing Bay" in battlefield_names
        ):
            families.add("cam_ltb_sacrifice_route_partial")
    if "Chrome Dome" in battlefield_names:
        # Opponent-before-us end-step copying is now modeled; arbitrary main/priority
        # Chrome activation remains a separate action-surface slice.
        families.add("battlefield_chrome_main_activation_partial")

    return tuple(sorted(families))


def _horizon_nonartifact_cards(state: solver.State):
    return tuple(
        card for card in state.hand
        if card not in solver.ALL_LANDS and card not in solver.ARTIFACTS
    )


def profile(*, base_seed: int, count: int, horizon: int):
    deck = solver.load_deck(Path("decklist.txt"))
    reasons = Counter()
    win_turns = Counter()
    steps = []
    examples = {}
    horizon_features = Counter()
    horizon_cards = Counter()
    horizon_urza_cast = 0

    for seed in range(int(base_seed), int(base_seed) + int(count)):
        runtime = opening_runtime(seed, deck)
        try:
            result = run_deterministic_episode(runtime, horizon=horizon)
        except NotImplementedError as exc:
            reason = _unsupported_reason(exc)
            reasons[reason] += 1
            examples.setdefault(
                reason,
                {
                    "seed": seed,
                    "turn": runtime.true_state.turn,
                    "hand": runtime.true_state.hand,
                    "battlefield": tuple(
                        (p.name, p.mode, p.tapped) for p in runtime.true_state.battlefield
                    ),
                    "steps": None,
                    "detail": str(exc),
                },
            )
            continue

        reasons[result.terminal_reason] += 1
        if result.win_turn is not None:
            win_turns[result.win_turn] += 1
        steps.append(len(result.steps))

        if result.terminal_reason == "horizon":
            state = result.runtime.true_state
            for family in _horizon_state_features(state):
                horizon_features[family] += 1
            horizon_cards.update(_horizon_nonartifact_cards(state))
            if state.urza or not state.commander_in_command_zone:
                horizon_urza_cast += 1

        examples.setdefault(
            result.terminal_reason,
            {
                "seed": seed,
                "turn": result.runtime.true_state.turn,
                "hand": result.runtime.true_state.hand,
                "battlefield": tuple(
                    (p.name, p.mode, p.tapped) for p in result.runtime.true_state.battlefield
                ),
                "steps": len(result.steps),
                "detail": "",
            },
        )

    print(f"PHASE2 COVERAGE: seeds={base_seed}..{base_seed+count-1} horizon=T{horizon}")
    print("terminal reasons:")
    for reason, n in reasons.most_common():
        print(f"  {reason:36s} {n:4d}  {100*n/count:6.2f}%")
    print("win turns:", dict(sorted(win_turns.items())))
    print(f"mean completed steps: {sum(steps)/len(steps):.2f}" if steps else "mean completed steps: 0")

    horizon_n = reasons.get("horizon", 0)
    if horizon_n:
        print(f"horizon-state feature prevalence among {horizon_n} T6 no-win trajectories:")
        print("  (_unmodeled/_partial rows are implementation audit signals)")
        for family, n in horizon_features.most_common():
            print(f"  {family:44s} {n:4d}  {100*n/horizon_n:6.2f}%")
        print(f"  {'urza_cast_or_left_command_zone':44s} {horizon_urza_cast:4d}  {100*horizon_urza_cast/horizon_n:6.2f}%")
        print("most common nonartifact hand cards at the horizon:")
        for card, n in horizon_cards.most_common(20):
            print(f"  {card:36s} {n:4d}")

    print("first example by terminal reason:")
    for reason in sorted(examples):
        row = examples[reason]
        detail = f" detail={row['detail']}" if row.get("detail") else ""
        print(
            f"  {reason}: seed={row['seed']} turn={row['turn']} steps={row['steps']} "
            f"hand={row['hand']} battlefield={row['battlefield']}{detail}"
        )
    return reasons


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20260821)
    ap.add_argument("--count", type=int, default=20)
    ap.add_argument("--horizon", type=int, default=6)
    args = ap.parse_args()
    if args.count <= 0:
        raise SystemExit("--count must be positive")
    profile(base_seed=args.seed, count=args.count, horizon=args.horizon)


if __name__ == "__main__":
    main()
