#!/usr/bin/env python3
"""Strict shard pooling for the physical-99 paired full-replay reference runner.

Rejects missing, duplicate or differently-versioned seeds. No averaging of
per-shard percentages. Pool raw game-level outcomes and recompute paired CIs.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

import dack_paired_counterfactual_v1_20261030 as runner

SCHEMA = "dack_paired_counterfactual_full_replay_v1"

def pool(folder, out, expected_games=None, expected_start=0):
    files = sorted(Path(folder).glob("*.json.gz"))
    if not files:
        raise ValueError("no paired shard .json.gz files in " + str(folder))
    rows = {}
    source_files = []
    provenance = None
    elapsed = 0.0
    for path in files:
        with gzip.open(path, "rt", encoding="utf8") as f:
            data = json.load(f)
        if data.get("schema") != SCHEMA or data.get("status") != "PASS":
            raise ValueError("bad shard schema/status: " + str(path))
        audit = data["audit"]
        identity = (audit["manifest_sha256"], audit["spec_sha256"],
                    audit["rules_version"])
        if provenance is None:
            provenance = identity
        elif identity != provenance:
            raise ValueError("mixed manifest/spec/rules across shard files")
        if data["spec"] != runner.SPEC:
            raise ValueError("shard experiment configuration has drifted")
        if data["games"] != len(data["rows"]):
            raise ValueError("incomplete shard records: " + str(path))
        for j, row in enumerate(data["rows"]):
            game_id = int(row["game_id"])
            if game_id != data["seed_start"] + j:
                raise ValueError("bad shard game ID: " + str(path))
            if game_id in rows:
                raise ValueError("duplicate game ID across shards: " + str(game_id))
            if set(row["arms"]) != set(runner.VARIANTS):
                raise ValueError("missing variant from " + str(path))
            rows[game_id] = row
        source_files.append({"name": path.name,
                             "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                             "games": len(data["rows"])})
        elapsed += data["elapsed_seconds"]
    ids = sorted(rows)
    expected = list(range(expected_start,
                          expected_start + (expected_games if expected_games is not None
                                            else len(ids))))
    if ids != expected:
        raise ValueError("missing/noncontiguous seeds: expected %d..%d, actual %d IDs" %
                         (expected[0], expected[-1], len(ids)))
    ordered = [rows[i] for i in ids]
    metrics = runner.metrics(ordered)
    base = runner.SPEC["control"]
    t2_discordances = sum(
        any(runner.t2_success(row["arms"][name]["win_turn"]) !=
            runner.t2_success(row["arms"][base]["win_turn"])
            for name in runner.VARIANTS if name != base)
        for row in ordered)
    reasons = Counter()
    for row in ordered:
        for name, trace in row.get("discordant_trace", {}).items():
            if name == base:
                continue
            reasons[trace["first_divergence"]["kind"]] += 1
    result = {
        "schema": "dack_paired_counterfactual_pooled_v1",
        "status": "PASS", "n": len(ordered),
        "seed_start": expected_start, "rules_version": provenance[2],
        "manifest_sha256": provenance[0], "spec_sha256": provenance[1],
        "source_files": source_files, "aggregate_shard_wall_seconds": round(elapsed, 3),
        "t2_discordant_games_any_arm": t2_discordances,
        "first_divergence_counts": dict(reasons), "results": metrics,
        "scope": "Optimistic goldfish Dack cast with combo library eligibility; "
                 "not validated full combo wins or 4-player win rates. "
                 "Inherited nested-EV randomness is not canonical-slot paired.",
    }
    target = Path(out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf8")
    print("PAIRED_POOL_PASS", target, "N", len(ordered),
          "T2", {k:v["T2_pct"] for k,v in metrics["arms"].items()}, flush=True)
    return result

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--folder", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--expected-games", type=int, default=None)
    p.add_argument("--expected-start", type=int, default=0)
    a = p.parse_args()
    pool(a.folder, a.out, a.expected_games, a.expected_start)
