#!/usr/bin/env python3
"""v40: collect ORIGINAL v5 teacher decisions on independent physical London deals.

For each independent full-99-slot group, collect all first three London stage
decisions, even if the original v5 naturally retained earlier. These are
COUNTERFACTUAL STAGE ACTIONS, not counterfactual game win outcomes. Also save
all naturally visited later stages. Actual v5 is installed unmodified;
no student proxy supplies labels, and no physical outer future order is passed
to v5's decision evaluator.

Never infer independent sample size from the number of sampled teacher rollouts.
The physical GAME ID is the source group for all its recorded stage decisions.
"""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import dack_paired_counterfactual_v5_stable_chance_20261031 as teacher
from dack_simulator.validation.collect_teacher_london_v13 import finalists

ref = teacher.reference
DECK = "one_key_34"
SCHEMA = "dack_v40_actual_v5_early_stage_teacher_census_v1"
TRAIN = (140000, 144095)  # exactly 4096 independent physical deals
DEV = (144096, 144607)    # exactly 512 further independent deals
EARLY = (0, 1, 2)
STAGES = (7, 7, 6, 5, 4, 3, 2, 1)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def teacher_stage(seven, unknown, seat, stage):
    """Original v5 stage evaluator + EXACT original assertive KEEP cutoff.

    This stage may be counterfactual if v5 naturally kept at an earlier stage.
    It is still a genuine v5 call, NOT a cheap student or an outcome oracle.
    """
    keep_n = STAGES[stage]
    assert len(seven) == 7 and len(unknown) == 92
    raw, ev, structural, hand, bottom, remainder, ignored, refined = (
        ref.batch.evaluate_keep(list(seven), keep_n, list(unknown), seat)
    )
    assert len(remainder) == 92
    assert Counter(remainder) == Counter(unknown)
    standard = 0.0 if keep_n == 1 else ref.batch.FROZEN_CONTINUATION[keep_n - 1]
    native = (keep_n == 1 or float(raw) >= standard)
    t1 = float(ev["t1"])
    bump = ref.sim.ASSERTIVE_BUMPS.get(keep_n, 0.0)
    cutoff = standard + (0.0 if native and t1 > 0 else bump)
    keep = bool(keep_n == 1 or float(raw) >= cutoff)
    return {
        "stage": stage, "keep_n": keep_n, "kept": keep,
        "raw": round(float(raw), 7), "sampled_t1": round(t1, 7),
        "threshold": round(float(cutoff), 7),
        "refined": bool(refined), "hand": list(hand), "bottom": list(bottom),
    }


def stage_row(gid, seat, stage, seven, unknown, event, natural):
    keep_n = STAGES[stage]
    assert int(event["stage"]) == stage and int(event["keep_n"]) == keep_n
    assert Counter(event["hand"]) + Counter(event["bottom"]) == Counter(seven)
    opts = finalists(tuple(seven), keep_n, tuple(unknown))
    matches = [
        i for i, opt in enumerate(opts)
        if tuple(opt["hand"]) == tuple(event["hand"])
        and tuple(opt["bottom"]) == tuple(event["bottom"])
    ]
    if not matches:
        raise AssertionError(("actual v5 bottom missing from original top12",
                              gid, stage, event["hand"], event["bottom"]))
    assert len(unknown) == 92 and len(opts) <= 12
    return {
        "type": "stage", "schema": SCHEMA, "game_id": gid,
        "group_id": f"{DECK}:{gid}", "seat": seat, "stage": stage,
        "keep_n": keep_n, "seven": list(seven),
        "unknown_counts": dict(sorted(Counter(unknown).items())),
        "sampling_stratum": ("unconditional_stage0_2" if stage in EARLY
                             else "naturally_reached_later"),
        "actually_reached_by_v5": bool(natural),
        "teacher_keep": bool(event["kept"]),
        "teacher_raw": float(event["raw"]),
        "teacher_threshold": float(event["threshold"]),
        "teacher_sampled_t1": float(event["sampled_t1"]),
        "teacher_refined": bool(event["refined"]),
        "teacher_bottom_candidate_index": matches[0],
        "teacher_structural_first": bool(matches[0] == 0),
        "teacher_selected_hand": list(event["hand"]),
        "teacher_selected_bottom": list(event["bottom"]),
        "candidate_rows": opts,
        "no_realized_unknown_future_order_in_model_input": True,
        "student_proxy_used_as_label": False,
    }


def run(start, games, out, split):
    lo, hi = {"train": TRAIN, "dev": DEV}[split]
    if games < 1 or start < lo or start + games - 1 > hi:
        raise ValueError("requested physical groups outside independent v40 split")
    if tuple(ref.sim.STAGES) != STAGES:
        raise AssertionError("original London stages changed")
    if teacher.audit()["status"] != "PASS":
        raise AssertionError("original v5 rules audit failed")
    deck = ref.SLOT_VARIANTS[DECK]
    assert len(deck) == 99 and ref.SPEC["beam"] == 160
    p = Path(out)
    p.parent.mkdir(parents=True, exist_ok=True)
    counts = Counter()
    t0 = time.monotonic()
    with gzip.open(p, "wt", encoding="utf-8") as f:
        meta = {
            "type": "metadata", "schema": SCHEMA, "split": split,
            "start": start, "games": games, "deck": DECK,
            "source_manifest_sha256": sha(ref.MANIFEST_PATH),
            "source_spec_sha256": sha(ref.SPEC_PATH),
            "teacher_v5_module_sha256": sha(ROOT / "dack_paired_counterfactual_v5_stable_chance_20261031.py"),
            "teacher_source": "actual_original_v5_not_v13_proxy",
            "full_physical_99_slots": True,
            "three_stage_unconditional_queries": True,
            "natural_later_stage_queries": True,
            "primary_group_unit": "original_game_id",
            "teacher_rollout_labels_are_not_independent_hands": True,
            "future_order_not_in_teacher_decision_inputs": True,
            "no_physical_keep_vs_mull_counterfactual_outcomes": True,
            "no_model_fitted_or_approved": True,
        }
        f.write(json.dumps(meta, sort_keys=True, separators=(",", ":")) + "\n")
        for gid in range(start, start + games):
            seed = int(ref.SPEC["seed_base"]) + gid * ref.SEED_STRIDE
            seat, orders = ref.stage_slots(seed)
            ref.sim.reset_caches()
            ref.sim.root.install(DECK)
            ref.sim.m.set_trial_seed(seed)
            _, natural_history = ref.choose_keep(deck, seat, orders)
            assert natural_history and natural_history[-1]["kept"]
            natural = {int(row["stage"]): row for row in natural_history}
            assert tuple(natural) == tuple(range(len(natural)))
            assert len(set(natural)) == len(natural)
            for stage in sorted(set(EARLY) | set(natural)):
                order = orders[stage]
                seven = tuple(deck[slot] for slot in order[:7])
                unknown = tuple(deck[slot] for slot in order[7:])
                assert Counter(seven) + Counter(unknown) == Counter(deck.values())
                if stage in natural:
                    row = natural[stage]
                    assert row["seven"] == list(seven)
                    assert row["seven_slots"] == list(order[:7])
                else:
                    ref.sim.reset_caches()
                    ref.sim.root.install(DECK)
                    ref.sim.m.set_trial_seed(seed)
                    row = teacher_stage(seven, unknown, seat, stage)
                    assert stage in EARLY
                line = stage_row(gid, seat, stage, seven, unknown, row,
                                 natural=stage in natural)
                f.write(json.dumps(line, sort_keys=True, separators=(",", ":")) + "\n")
                counts["stage_rows"] += 1
                counts["early_rows" if stage in EARLY else "later_natural_rows"] += 1
                counts["v5_keep"] += int(line["teacher_keep"])
                counts["v5_mull"] += int(not line["teacher_keep"])
                counts["bottom_not_structural_first"] += int(
                    not line["teacher_structural_first"])
                counts["candidate_rows"] += len(line["candidate_rows"])
            counts["independent_groups"] += 1
            print("V40_ACTUAL_V5_TEACHER_GROUP", gid,
                  "natural_stages", len(natural),
                  "elapsed_seconds", round(time.monotonic() - t0, 2),
                  flush=True)
    assert counts["early_rows"] == games * 3
    assert counts["stage_rows"] >= counts["early_rows"]
    print("DACK_V40_ACTUAL_V5_TEACHER_SHARD_PASS",
          json.dumps({"split": split, "start": start, "games": games,
                      "counts": dict(counts),
                      "elapsed_seconds": round(time.monotonic()-t0, 2)},
                     sort_keys=True), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("train", "dev"), default="train")
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--games", type=int, required=True)
    parser.add_argument("--out", required=True)
    a = parser.parse_args()
    run(a.start, a.games, a.out, a.split)
