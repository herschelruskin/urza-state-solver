#!/usr/bin/env python3
"""Profile current Phase-2 episode coverage on real shuffled deck openings.

Diagnostic only: this intentionally does NOT choose mulligans yet.  Each sample is a
fresh shuffled seven plus the modeled multiplayer turn-one draw.  The purpose is to
rank both hard runtime blockers and *silent* missing action families that otherwise
look like ordinary horizon losses because ending the turn remains legal.

Unsupported runtime slices are measurements, not profiler failures: a
NotImplementedError is converted into a stable blocker category so one missing card
adapter cannot hide the blocker distribution for the rest of the sample.
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
    "Reshape", "Transmute Artifact", "Whir of Invention",
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
    # Multiplayer Commander model draws on turn one.  This is a chance event
    # before the first policy decision, so putting the observed card in hand at
    # runtime construction is information-faithful.
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


def _stranded_action_families(state: solver.State):
    """Public opportunities absent from the current Phase-2 main action surface.

    This is intentionally diagnostic rather than a legality oracle.  Hand-family
    rows answer which missing adapters are repeatedly present at the horizon;
    battlefield rows flag common activated/engine surfaces that the current main
    loop cannot use at all.
    """
    hand = set(state.hand)
    battlefield_names = {p.name for p in state.battlefield}
    families = set()

    if hand & SIMPLE_TUTOR_CARDS:
        families.add("hand_simple_tutor")
    if hand & ARTIFACT_TUTOR_CARDS:
        families.add("hand_artifact_tutor")
    if hand & NONARTIFACT_ENGINE_CARDS:
        families.add("hand_nonartifact_engine_spell")
    if hand & COMBO_SPELL_CARDS:
        families.add("hand_combo_nonartifact_spell")
    if hand & SPECIAL_ARTIFACT_CASTS:
        families.add("hand_special_artifact_cast")

    # Other instant/sorcery cards currently have no generic Phase-2 cast route.
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
        families.add("hand_other_nonartifact_spell")

    if "Repurposing Bay" in battlefield_names:
        families.add("battlefield_bay_activation")
    if "Sensei's Divining Top" in battlefield_names:
        families.add("battlefield_top_activation")
    if "The One Ring" in battlefield_names:
        families.add("battlefield_one_ring_draw")
    if any(p.mode == "clue" for p in state.battlefield):
        families.add("battlefield_clue_draw")
    if "Grinding Station" in battlefield_names:
        families.add("battlefield_station_activation")
    if state.urza:
        families.add("battlefield_urza_spin")
    if "The Reality Chip" in battlefield_names and not state.chip_attached:
        families.add("battlefield_chip_reconfigure")
    if any(name in battlefield_names for name in {"Voltaic Key", "Manifold Key"}):
        families.add("battlefield_key_activation")
    if "Uthros Research Craft" in battlefield_names:
        families.add("battlefield_uthros_activation")

    return tuple(sorted(families))


def _stranded_cards(state: solver.State):
    """Count exact cards in hand that currently lack a generic main cast route."""
    rows = []
    for card in state.hand:
        if card in solver.ALL_LANDS or card in solver.ARTIFACTS:
            continue
        rows.append(card)
    return tuple(rows)


def profile(*, base_seed: int, count: int, horizon: int):
    deck = solver.load_deck(Path("decklist.txt"))
    reasons = Counter()
    win_turns = Counter()
    steps = []
    examples = {}
    horizon_gap_states = Counter()
    horizon_gap_cards = Counter()
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
            for family in _stranded_action_families(state):
                horizon_gap_states[family] += 1
            horizon_gap_cards.update(_stranded_cards(state))
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
        print(f"silent action gaps among {horizon_n} horizon states:")
        for family, n in horizon_gap_states.most_common():
            print(f"  {family:36s} {n:4d}  {100*n/horizon_n:6.2f}%")
        print(f"  {'urza_cast_or_left_command_zone':36s} {horizon_urza_cast:4d}  {100*horizon_urza_cast/horizon_n:6.2f}%")
        print("most common stranded nonartifact hand cards:")
        for card, n in horizon_gap_cards.most_common(20):
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
