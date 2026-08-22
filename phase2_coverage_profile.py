#!/usr/bin/env python3
"""Profile current Phase-2 episode coverage on real shuffled deck openings.

Diagnostic only: this intentionally does NOT choose mulligans yet.  Each sample is a
fresh shuffled seven plus the modeled multiplayer turn-one draw.  The purpose is to
rank missing runtime adapters by how often they actually stop a deterministic
base-policy trajectory.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import random

import urza_solver as solver
from non_oracle_episode import run_deterministic_episode
from non_oracle_runtime import make_runtime_state


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


def profile(*, base_seed: int, count: int, horizon: int):
    deck = solver.load_deck(Path("decklist.txt"))
    reasons = Counter()
    win_turns = Counter()
    steps = []
    examples = {}

    for seed in range(int(base_seed), int(base_seed) + int(count)):
        result = run_deterministic_episode(opening_runtime(seed, deck), horizon=horizon)
        reasons[result.terminal_reason] += 1
        if result.win_turn is not None:
            win_turns[result.win_turn] += 1
        steps.append(len(result.steps))
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
            },
        )

    print(f"PHASE2 COVERAGE: seeds={base_seed}..{base_seed+count-1} horizon=T{horizon}")
    print("terminal reasons:")
    for reason, n in reasons.most_common():
        print(f"  {reason:36s} {n:4d}  {100*n/count:6.2f}%")
    print("win turns:", dict(sorted(win_turns.items())))
    print(f"mean steps: {sum(steps)/len(steps):.2f}" if steps else "mean steps: 0")
    print("first example by terminal reason:")
    for reason in sorted(examples):
        row = examples[reason]
        print(
            f"  {reason}: seed={row['seed']} turn={row['turn']} steps={row['steps']} "
            f"hand={row['hand']} battlefield={row['battlefield']}"
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
