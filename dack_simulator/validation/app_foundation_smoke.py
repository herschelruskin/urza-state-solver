#!/usr/bin/env python3
"""Zero-dependency smoke test for the distributable app foundation."""

from __future__ import annotations

import tempfile
from pathlib import Path
import sys

HERE = Path(__file__).resolve()
SRC = HERE.parents[1] / "src"
sys.path.insert(0, str(SRC))

from dacksim.canonical import canonical_hash, deck_hash, run_key
from dacksim.codec import Outcome, pack_outcomes, unpack_outcomes
from dacksim.store import DackStore


def main() -> None:
    rows = [
        Outcome(0, 7, 1),
        Outcome(3, 4, 2),
        Outcome(1, 1, 0),
        Outcome(2, 5, 3),
    ]
    payload = pack_outcomes(rows)
    assert len(payload) == len(rows), "v1 encoding must be exactly one byte/game"
    assert unpack_outcomes(payload) == rows

    # Canonical deck identity is independent of list order.
    deck_a = ["A", "B", "A"]
    deck_b = ["B", "A", "A"]
    assert deck_hash(deck_a) == deck_hash(deck_b)

    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "dack.sqlite"
        with DackStore(path) as store:
            dh = store.register_deck(deck_a, commander="Dack")
            ph = store.register_policy({"lambda": 0.5, "mulligan": "stable"})
            eh = store.register_engine({"engine": "smoke", "sha256": "abc"})
            key = store.put_result_block(
                deck_hash_value=dh,
                engine_hash=eh,
                policy_hash=ph,
                seed_start=0,
                outcomes=rows,
            )
            assert store.get_result_block(key) == rows

            # Immutable duplicate succeeds only when bytes are identical.
            key2 = store.put_result_block(
                deck_hash_value=dh,
                engine_hash=eh,
                policy_hash=ph,
                seed_start=0,
                outcomes=rows,
            )
            assert key2 == key

            assert store.missing_intervals(
                deck_hash_value=dh,
                engine_hash=eh,
                policy_hash=ph,
                seed_start=0,
                seed_count=8,
            ) == [(4, 8)]

            exp = store.register_experiment(dh, {"objective": "leT2+0.5*T3"})
            store.add_experiment_variant(
                experiment_hash=exp,
                variant_deck_hash=dh,
                label="self",
                delta={"utility": 0.0},
            )
            stats = store.stats()
            assert stats["result_blocks"] == 1
            assert stats["experiments"] == 1

    print("APP_FOUNDATION_SMOKE_PASS")


if __name__ == "__main__":
    main()
