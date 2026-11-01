#!/usr/bin/env python3
"""v25 untouched 96k seed cohort: paired v5/v14/v22 full physical beam-160 games.

Do not train, tune, or approve any policy from this evaluation.
All policies are fixed imports on the isolated branch. Data are goldfish
Dack deployment turns, never four-player cEDH wins.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys
# Running a nested script directly places its directory, not the repo root, on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from dack_simulator.validation.compare_v22_real_keep_DP_n64 import run_game, POLICIES

ROOT = Path(__file__).resolve().parents[2]
START, STOP = 96000, 96256

def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()

def main(start, games, output):
    if not START <= start < STOP or not 1 <= games <= 4 or start + games > STOP:
        raise ValueError("v25 uses unique fresh 96k game IDs, shard size 1..4")
    rows = []
    hashes = {
        name: sha(name) for name in (
            "models/dack_v22_real_all_stage_keep_value_EXPERIMENTAL.json",
            "models/dack_v22_all_stage_continuations_EXPERIMENTAL.json",
            "models/v14_curve/v14_teacher_groups_128.json",
        )
    }
    for game_id in range(start, start + games):
        row = {"game_id": game_id}
        for p in POLICIES:
            row[p] = run_game(game_id, p)
            assert row[p]["turn"] in (0, 1, 2, 3)
        assert len({row[p]["seat"] for p in POLICIES}) == 1
        # All policies receive identical physical 99-slot shuffled seven.
        first = [row[p]["history"][0]["seven_slots"] for p in POLICIES]
        assert first[0] == first[1] == first[2], ("physical first seven mismatch", game_id)
        rows.append(row)
        print("V25_PAIRED_PHYSICAL", game_id,
              {p: (row[p]["turn"], row[p]["keep_n"]) for p in POLICIES},
              flush=True)
    data = {
        "schema": "dack_v25_fresh_reference_physical_shard",
        "status": "PASS", "game_ids": [start, start + games - 1],
        "actual_gameplay_beam": 160, "experimental_policy_approved": False,
        "physical_first_seven_parity": True, "model_sha256": hashes,
        "rows": rows,
    }
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(target, "wt", encoding="utf-8") as f:
        json.dump(data, f, sort_keys=True)
    print("V25_SHARD_PASS", start, games, flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--games", type=int, default=4)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    main(args.start, args.games, args.out)
