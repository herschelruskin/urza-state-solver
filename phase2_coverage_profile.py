#!/usr/bin/env python3
"""Profile Phase-2 episode coverage on real shuffled deck openings.

This diagnostic intentionally does NOT choose mulligans yet. Each sample is a fresh
shuffled seven plus the modeled multiplayer turn-one draw. The purpose is to measure
three different things separately:

1. hard runtime blockers that stop a trajectory before the requested horizon;
2. silent Phase-2 action-surface gaps still present in horizon states;
3. the deterministic base policy's observed win-turn distribution.

A horizon feature is not automatically a bug: modeled cards can remain unused because
they were uncastable, deprioritized, or drawn late. Rows ending in ``_unmodeled`` or
``_partial`` are implementation-audit signals. Reactive interaction is reported
separately because leaving a counterspell unused in a goldfish trajectory is expected.
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
MODELED_CANTRIP_CARDS = frozenset({"Gitaxian Probe"})
REACTIVE_INTERACTION_CARDS = frozenset(getattr(solver, "INTERACTION_CARDS", frozenset()))
SUCCESS_TERMINALS = frozenset({"horizon", "win"})


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
        families.add("hand_special_artifact_present")
    if hand & MODELED_CANTRIP_CARDS:
        families.add("hand_modeled_cantrip_present")

    generic_nonartifact = {
        card for card in hand
        if card not in solver.ARTIFACTS
        and card not in solver.ALL_LANDS
        and card != solver.COMMANDER
        and card not in SIMPLE_TUTOR_CARDS
        and card not in ARTIFACT_TUTOR_CARDS
        and card not in NONARTIFACT_ENGINE_CARDS
        and card not in COMBO_SPELL_CARDS
        and card not in MODELED_CANTRIP_CARDS
    }
    reactive = generic_nonartifact & REACTIVE_INTERACTION_CARDS
    other = generic_nonartifact - reactive
    if reactive:
        families.add("hand_reactive_interaction_present")
    if other:
        families.add("hand_other_nonartifact_unmodeled")

    top_live = "Sensei's Divining Top" in battlefield_names
    key_live = bool(battlefield_names & {"Voltaic Key", "Manifold Key"})
    if top_live:
        families.add("battlefield_top_reorder_modeled_present")
        families.add("battlefield_top_draw_activation_modeled_present")
    if "The One Ring" in battlefield_names:
        families.add("battlefield_one_ring_draw_modeled_present")
    if any(p.mode == "clue" for p in state.battlefield):
        families.add("battlefield_clue_draw_modeled_present")
    if "Grinding Station" in battlefield_names:
        families.add("battlefield_station_activation_modeled_present")
    if "Codex Shredder" in battlefield_names:
        families.add("battlefield_codex_mill_modeled_present")
    if state.urza:
        families.add("battlefield_urza_spin_main_modeled_present")
    if "The Reality Chip" in battlefield_names:
        families.add("battlefield_chip_reconfigure_modeled_present")
    if state.chip_attached or (state.ftt_level >= 2 and state.spell_cast_this_turn):
        # Main-phase land play and artifact casting from the legally known top are
        # modeled. Nonartifact spell faces and priority-time top casting remain an
        # explicit follow-up timing slice.
        families.add("top_access_land_artifact_main_modeled_nonartifact_priority_partial")
    if key_live:
        families.add("battlefield_key_activation_modeled_present")
    if top_live and key_live:
        families.add("top_key_double_activation_modeled_present")
    if "Uthros Research Craft" in battlefield_names:
        families.add("battlefield_uthros_station_modeled_present")
    if "Sewer-veillance Cam" in battlefield_names:
        families.add("battlefield_cam_draw_activation_modeled_present")
        if (
            "Reshape" in hand
            or "Transmute Artifact" in hand
            or "Repurposing Bay" in battlefield_names
        ):
            families.add("cam_tutor_sacrifice_ltb_partial")
    if "Chrome Dome" in battlefield_names:
        families.add("battlefield_chrome_main_activation_partial")

    return tuple(sorted(families))


def _horizon_nonartifact_cards(state: solver.State):
    return tuple(
        card for card in state.hand
        if card not in solver.ALL_LANDS and card not in solver.ARTIFACTS
    )


def _hard_blockers(reasons: Counter):
    return Counter({reason: count for reason, count in reasons.items() if reason not in SUCCESS_TERMINALS})


def profile(*, base_seed: int, count: int, horizon: int):
    deck = solver.load_deck(Path("decklist.txt"))
    reasons = Counter()
    win_turns = Counter()
    win_families = Counter()
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
            win_families[result.win_family or "unspecified"] += 1
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

    wins = reasons.get("win", 0)
    print(f"PHASE2 COVERAGE: seeds={base_seed}..{base_seed+count-1} horizon=T{horizon}")
    print("terminal reasons:")
    for reason, n in reasons.most_common():
        print(f"  {reason:36s} {n:4d}  {100*n/count:6.2f}%")
    print(f"wins by T{horizon}: {wins}/{count} = {100*wins/count:.2f}%")
    print("win turns:", dict(sorted(win_turns.items())))
    print("win families:", dict(win_families.most_common()))
    print(f"mean completed steps: {sum(steps)/len(steps):.2f}" if steps else "mean completed steps: 0")

    blockers = _hard_blockers(reasons)
    print("hard runtime blockers:", dict(blockers) if blockers else "none")

    horizon_n = reasons.get("horizon", 0)
    if horizon_n:
        print(f"horizon-state feature prevalence among {horizon_n} T{horizon} no-win trajectories:")
        print("  (_unmodeled/_partial rows are implementation signals; reactive interaction is separate)")
        for family, n in horizon_features.most_common():
            print(f"  {family:44s} {n:4d}  {100*n/horizon_n:6.2f}%")
        print(f"  {'urza_cast_or_left_command_zone':44s} {horizon_urza_cast:4d}  {100*horizon_urza_cast/horizon_n:6.2f}%")
        print("most common nonartifact hand cards at the horizon:")
        for card, n in horizon_cards.most_common(25):
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
    ap.add_argument(
        "--fail-on-blocker",
        action="store_true",
        help="exit nonzero if any trajectory terminates for a reason other than win/horizon",
    )
    args = ap.parse_args()
    if args.count <= 0:
        raise SystemExit("--count must be positive")
    reasons = profile(base_seed=args.seed, count=args.count, horizon=args.horizon)
    blockers = _hard_blockers(reasons)
    if args.fail_on_blocker and blockers:
        raise SystemExit(f"hard Phase-2 runtime blockers observed: {dict(blockers)}")


if __name__ == "__main__":
    main()
