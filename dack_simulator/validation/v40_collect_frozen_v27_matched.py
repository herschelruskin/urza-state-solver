#!/usr/bin/env python3
"""v40: independent-process frozen v27/v33b baseline census for the v5 hands.

Use the same physical gid -> 99-slot London orders as actual-v5 collector,
but never import v5 in this interpreter (shared mutable simulator globals).
Outcome-blind observational decisions; NO physical gameplay and NO model fit.
"""
from __future__ import annotations
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from dack_simulator.validation import v34_frozen_v33b_continuation as kernel

REF = kernel.ref
DECK = kernel.DECK_KEY
SCHEMA = "dack_v40_frozen_v27_v33b_stage_census_v1"
SPLITS = {"train": (140000, 144095), "dev": (144096, 144607)}
EARLY = (0, 1, 2)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(start, games, out, split):
    lo, hi = SPLITS[split]
    if games < 1 or start < lo or start + games - 1 > hi:
        raise ValueError("physical IDs outside v40 teacher source partition")
    kernel.initialize()
    assert tuple(REF.sim.STAGES) == (7, 7, 6, 5, 4, 3, 2, 1)
    deck = REF.SLOT_VARIANTS[DECK]
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        meta = {
            "type": "metadata", "schema": SCHEMA, "split": split,
            "start": start, "games": games, "deck": DECK,
            "source_manifest_sha256": sha(REF.MANIFEST_PATH),
            "source_spec_sha256": sha(REF.SPEC_PATH),
            "v33b_model_sha256": kernel.v33b.MODEL_SHA,
            "v27_frozen_reference": True,
            "student_v13_proxy_not_used_as_label": True,
            "all_first_three_london_stages_even_if_not_reached": True,
            "no_hidden_order_features": True,
            "no_physical_games": True,
            "policy_approved": False,
        }
        f.write(json.dumps(meta, sort_keys=True, separators=(",", ":")) + "\n")
        for gid in range(start, start + games):
            seed = int(REF.SPEC["seed_base"]) + gid * REF.SEED_STRIDE
            seat, orders = REF.stage_slots(seed)
            REF.sim.reset_caches()
            REF.sim.root.install(DECK)
            REF.sim.m.set_trial_seed(seed)
            _, history = REF.choose_keep(deck, seat, orders)
            assert history and history[-1]["kept"]
            reached = {int(row["stage"]) for row in history}
            assert reached == set(range(len(reached)))
            for stage in EARLY:
                order = orders[stage]
                seven = tuple(deck[slot] for slot in order[:7])
                unknown = tuple(deck[slot] for slot in order[7:])
                assert len(unknown) == 92
                assert Counter(seven) + Counter(unknown) == Counter(deck.values())
                x = kernel.current(seven, unknown, seat, stage)
                row = {
                    "type": "stage", "schema": SCHEMA,
                    "group_id": f"{DECK}:{gid}", "game_id": gid,
                    "seat": seat, "stage": stage, "keep_n": x["keep_n"],
                    "seven": list(seven),
                    "old_v27_keep": bool(x["old_v27_keep"]),
                    "old_v27_qkeep": float(x["old_v27_Qkeep"]),
                    "old_v27_continuation": float(x["old_v27_DP"]),
                    "old_v27_margin": float(x["old_v27_Qkeep"]-x["old_v27_DP"]),
                    "v14_hand": list(x["v14_hand"]),
                    "v14_bottom": list(x["v14_bottom"]),
                    "v33b_hand": list(x["hand"]),
                    "v33b_bottom": list(x["bottom"]),
                    "v33b_bottom_changed": bool(x["v33b_overrode_bottom"]),
                    "naturally_reached_by_v27": stage in reached,
                    "student_proxy_keep_action_not_used": True,
                }
                assert Counter(row["v33b_hand"]) + Counter(row["v33b_bottom"]) == Counter(seven)
                f.write(json.dumps(row, sort_keys=True, separators=(",", ":"))+"\n")
            print("V40_V27_MATCHED_GID", gid, "natural_stages", len(reached), flush=True)
    print("DACK_V40_V27_MATCHED_STAGE_CENSUS_PASS", start, games, flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--split", choices=tuple(SPLITS), default="train")
    p.add_argument("--start", type=int, required=True)
    p.add_argument("--games", type=int, required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    run(a.start, a.games, a.out, a.split)
