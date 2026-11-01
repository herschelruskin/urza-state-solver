#!/usr/bin/env python3
"""v40 outcome-blind join of original v5 and frozen v27 stage observations.

No gameplay, no student fitting and no policy thresholds. Each independent
physical game ID contributes one group irrespective of repeated stages,
candidate bottoms, or teacher's many hypothetical Monte Carlo rollouts.
"""
from __future__ import annotations
import argparse
from collections import Counter
import glob
import gzip
import hashlib
import json
from pathlib import Path

SCHEMA = "dack_v40_matched_actual_v5_v27_teacher_census_v1"
TEACHER_SCHEMA = "dack_v40_actual_v5_early_stage_teacher_census_v1"
V27_SCHEMA = "dack_v40_frozen_v27_v33b_stage_census_v1"
SPLITS = {"train": (140000, 144095), "dev": (144096, 144607)}


def readz(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        items = [json.loads(line) for line in f if line.strip()]
    assert items and items[0]["type"] == "metadata", path
    assert all(r["type"] == "stage" for r in items[1:]), path
    return items[0], items[1:]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def collect(pattern, schema, split):
    paths = sorted(glob.glob(pattern))
    if not paths:
        raise ValueError("No shards found: " + pattern)
    seen = {}
    source = {}
    intervals = []
    hashes = {}
    for file in paths:
        meta, rows = readz(file)
        if meta["schema"] != schema or meta["split"] != split:
            raise AssertionError(("bad shard schema/split", file))
        start, games = int(meta["start"]), int(meta["games"])
        ids = set(range(start, start + games))
        if ids & set(seen):
            raise AssertionError(("duplicated physical game groups", file))
        for row in rows:
            gid = int(row["game_id"])
            assert gid in ids and row["schema"] == schema
            assert row["group_id"] == f"one_key_34:{gid}"
            assert row["seat"] in range(4)
            seen.setdefault(gid, []).append(row)
        assert ids <= set(seen)
        intervals.append((start, start + games - 1))
        for key in ("source_manifest_sha256", "source_spec_sha256"):
            if key in source and source[key] != meta[key]:
                raise AssertionError(("different fixed deck fingerprints", file, key))
            source[key] = meta[key]
        hashes[Path(file).name] = digest(file)
    return seen, source, intervals, hashes


def run(split, teacher_glob, v27_glob, out, expected_groups):
    a, deck_a, intervals_a, hashes_a = collect(
        teacher_glob, TEACHER_SCHEMA, split)
    b, deck_b, intervals_b, hashes_b = collect(
        v27_glob, V27_SCHEMA, split)
    assert deck_a == deck_b
    assert sorted(a) == sorted(b)
    lo, hi = SPLITS[split]
    gids = sorted(a)
    assert len(gids) == expected_groups
    assert gids == list(range(gids[0], gids[0] + expected_groups))
    assert lo <= gids[0] and gids[-1] <= hi
    assert intervals_a == intervals_b, "shards must use identical ID intervals"
    aggregate = Counter()
    by_stage = {str(stage): Counter() for stage in range(3)}
    selected = {}
    for gid in gids:
        A = {int(r["stage"]): r for r in a[gid]}
        B = {int(r["stage"]): r for r in b[gid]}
        assert len(A) == len(a[gid]) and len(B) == len(b[gid])
        assert set(A) >= {0, 1, 2} and set(B) == {0, 1, 2}
        assert all(A[s]["sampling_stratum"] == "unconditional_stage0_2"
                   for s in range(3))
        expected_later = set(A) - {0, 1, 2}
        assert all(s > 2 and A[s]["actually_reached_by_v5"]
                   for s in expected_later)
        for stage in range(3):
            t = A[stage];v = B[stage]
            for key in ("seat", "keep_n", "seven", "game_id", "group_id"):
                assert t[key] == v[key], (gid, stage, key)
            assert len(t["unknown_counts"]) > 0
            assert sum(t["unknown_counts"].values()) == 92
            stats = by_stage[str(stage)]
            stats["independent_observed_deals"] += 1
            stats["actual_v5_keeps"] += int(t["teacher_keep"])
            stats["frozen_v27_keeps"] += int(v["old_v27_keep"])
            stats["policy_disagreements"] += int(t["teacher_keep"] != v["old_v27_keep"])
            stats["v5_keep_v27_mull"] += int(t["teacher_keep"] and not v["old_v27_keep"])
            stats["v27_keep_v5_mull"] += int(v["old_v27_keep"] and not t["teacher_keep"])
            stats["v5_nonstructural_bottom"] += int(
                not t["teacher_structural_first"])
            stats["v33b_overrode_bottom"] += int(v["v33b_bottom_changed"])
            stats["v5_naturally_reached"] += int(t["actually_reached_by_v5"])
            stats["v27_naturally_reached"] += int(v["naturally_reached_by_v27"])
        active = [
            stage for stage in range(3)
            if A[stage]["actually_reached_by_v5"]
            and B[stage]["naturally_reached_by_v27"]
            and A[stage]["teacher_keep"] != B[stage]["old_v27_keep"]
        ]
        if active:
            s = active[0]
            # Both policies must have rejected earlier observed sevens.
            assert all(not A[k]["teacher_keep"] and not B[k]["old_v27_keep"]
                       for k in range(s))
            aggregate["groups_first_real_v5_v27_conflict_in_early"] += 1
            aggregate["first_conflict_at_stage_" + str(s)] += 1
            aggregate["first_conflict_v5_keep"] += int(A[s]["teacher_keep"])
            aggregate["first_conflict_v27_keep"] += int(B[s]["old_v27_keep"])
            selected[str(gid)] = {
                "stage": s, "seat": A[s]["seat"],
                "v5_keep": A[s]["teacher_keep"],
                "v27_keep": B[s]["old_v27_keep"],
                "v27_qkeep_minus_c": B[s]["old_v27_margin"],
                "teacher_raw_minus_cutoff":
                    A[s]["teacher_raw"] - A[s]["teacher_threshold"],
                "v5_chosen_bottom_candidate":
                    A[s]["teacher_bottom_candidate_index"],
                "v33b_bottom_changed":
                    B[s]["v33b_bottom_changed"],
            }
        aggregate["independent_physical_deals"] += 1
        aggregate["total_v5_stage_observations"] += len(A)
        aggregate["naturally_reached_later_v5_rows"] += len(expected_later)
    for s, stats in by_stage.items():
        assert stats["independent_observed_deals"] == expected_groups
        assert (stats["v5_keep_v27_mull"] + stats["v27_keep_v5_mull"]
                == stats["policy_disagreements"])
    report = {
        "schema": SCHEMA, "status": "PASS", "split": split,
        "group_ids": [gids[0], gids[-1]],
        "source_fingerprints": deck_a,
        "teacher_shard_sha256": hashes_a,
        "frozen_v27_shard_sha256": hashes_b,
        "counts": dict(aggregate),
        "by_early_stage": {s: dict(c) for s, c in by_stage.items()},
        "first_actual_early_disagreement": selected,
        "source_physical_game_ids_are_independent_groups": True,
        "all_first_three_stages_queried_even_if_counterfactual": True,
        "teacher_labels_are_real_original_v5": True,
        "student_v13_proxy_not_used": True,
        "no_physical_action_outcomes_or_fitting": True,
        "model_approved": False,
    }
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print("DACK_V40_TRUE_TEACHER_DISAGREEMENT_CENSUS_PASS",
          json.dumps({"group_ids": report["group_ids"],
                      "counts": dict(aggregate),
                      "by_stage": report["by_early_stage"]},
                     sort_keys=True), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--split", choices=tuple(SPLITS), default="train")
    p.add_argument("--teacher-glob", required=True)
    p.add_argument("--v27-glob", required=True)
    p.add_argument("--expected-groups", type=int, required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    run(a.split, a.teacher_glob, a.v27_glob, a.out, a.expected_groups)
