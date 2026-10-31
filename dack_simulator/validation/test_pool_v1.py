"""Strict shard pool parity and duplicate/missing-seed tests with synthetic outcomes."""
from __future__ import annotations
import gzip
import json
import tempfile
import unittest
from pathlib import Path

import dack_paired_counterfactual_v1_20261030 as run
import pool_dack_paired_counterfactual_v1_20261030 as pooling


def make_shard(path, start, games=1):
    rows = []
    for i in range(games):
        rows.append({
            "game_id": start + i, "seat": 0,
            "arms": {name: {"win_turn": 2 if name == run.SPEC["control"] else 3,
                             "keep_n": 7} for name in run.VARIANTS}
        })
    obj = {
        "schema": pooling.SCHEMA, "status": "PASS",
        "seed_start": start, "games": games, "rows": rows,
        "elapsed_seconds": 0.0, "spec": run.SPEC,
        "audit": {
            "manifest_sha256": run.source_sha(run.MANIFEST_PATH),
            "spec_sha256": run.source_sha(run.SPEC_PATH),
            "rules_version": run.RULES_VERSION,
        },
    }
    with gzip.open(path, "wt", encoding="utf8") as f:
        json.dump(obj, f)


class PoolingContracts(unittest.TestCase):
    def test_sums_raw_game_rows_not_shard_percentages(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            make_shard(folder / "a.json.gz", 0, 1)
            make_shard(folder / "b.json.gz", 1, 2)
            result = pooling.pool(folder, folder / "report.json",
                                  expected_games=3)
            self.assertEqual(result["n"], 3)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["results"]["arms"]["one_key_34"]["T2_pct"], 100.0)
            self.assertEqual(result["results"]["arms"]["staff_plains_35"]["T2_pct"], 0.0)
            self.assertEqual(result["results"]["paired_vs_control"]
                             ["staff_plains_35"]["T2"]["losses"], 3)

    def test_duplicate_game_ids_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            make_shard(folder / "a.json.gz", 0)
            make_shard(folder / "b.json.gz", 0)
            with self.assertRaisesRegex(ValueError, "duplicate game ID"):
                pooling.pool(folder, folder / "report.json", expected_games=2)

    def test_missing_game_ids_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            make_shard(folder / "a.json.gz", 0)
            make_shard(folder / "b.json.gz", 2)
            with self.assertRaisesRegex(ValueError, "missing/noncontiguous"):
                pooling.pool(folder, folder / "report.json", expected_games=3)


if __name__ == "__main__":
    unittest.main()
