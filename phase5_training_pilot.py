#!/usr/bin/env python3
"""Small deterministic Phase-5 training pilot.

This is intentionally underpowered statistically. Its purpose is to prove the
backward stage-value fit executes on the real deck/runtime without strategy fusion
or silent runtime blockers before larger calibration jobs are attempted.
"""

from __future__ import annotations

import json
from pathlib import Path

from phase5_mulligan import MulliganStageTrainer


def load_deck():
    cards = []
    for raw in Path("decklist.txt").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        count, name = line.split(" ", 1)
        if name == "Urza, Lord High Artificer":
            continue
        cards.extend([name] * int(count))
    if len(cards) != 99:
        raise ValueError(f"expected 99-card library, got {len(cards)}")
    return tuple(cards)


def main():
    deck = load_deck()
    trainer = MulliganStageTrainer(
        deck,
        hand_samples_per_stage=2,
        rollout_count_per_bottom=2,
        mc_root_seed=20260826,
        horizon=4,
        strict_terminal_reasons=True,
    )
    model = trainer.train()
    payload = {
        "kind": "phase5-training-pilot-not-calibration",
        "warning": "Tiny fixed budget; validate execution only. Do not interpret as stable mulligan thresholds.",
        "mc_root_seed": model.mc_root_seed,
        "horizon": model.horizon,
        "hand_samples_per_stage": model.hand_samples_per_stage,
        "rollout_count_per_bottom": model.rollout_count_per_bottom,
        "caverns_context": "inactive/unmodeled in this first pilot",
        "stages": [
            {
                "stage": row.stage,
                "keep_size": row.keep_size,
                "sampled_hands": row.sampled_hands,
                "kept_count": row.kept_count,
                "mulligan_count": row.mulligan_count,
                "keep_rate": row.keep_rate,
                "win_probability_by_t4": row.value.win_probability,
                "exact_win": list(row.value.exact_win),
                "no_win": row.value.no_win,
            }
            for row in model.stages
        ],
    }
    out = Path("phase5_training_pilot.json")
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    print(f"WROTE {out}")


if __name__ == "__main__":
    main()
