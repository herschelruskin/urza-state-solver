"""SQLite-backed content-addressed cache for DACK.

The database is designed for a local distributable application:
- metadata stays relational and queryable;
- hot per-game results are packed into one byte/game BLOBs;
- traces are sparse and optional;
- a deck+engine+policy+seed block has one immutable content key;
- WAL mode supports a GUI reader while worker processes finish blocks.

SQLite is the first distribution target because it has zero server/admin burden.
A later DuckDB/Parquet export can be added without changing the canonical IDs.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

from .canonical import canonical_deck, canonical_hash, canonical_json, deck_hash, run_key
from .codec import SCHEMA as OUTCOME_SCHEMA, Outcome, pack_outcomes, unpack_outcomes

SCHEMA_VERSION = 1


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class DackStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=30.0)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self._init_schema()

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> "DackStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _init_schema(self) -> None:
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS decks (
                deck_hash TEXT PRIMARY KEY,
                commander TEXT,
                card_count INTEGER NOT NULL,
                cards_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS policies (
                policy_hash TEXT PRIMARY KEY,
                policy_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS engines (
                engine_hash TEXT PRIMARY KEY,
                engine_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS result_blocks (
                run_key TEXT PRIMARY KEY,
                deck_hash TEXT NOT NULL REFERENCES decks(deck_hash),
                engine_hash TEXT NOT NULL REFERENCES engines(engine_hash),
                policy_hash TEXT NOT NULL REFERENCES policies(policy_hash),
                seed_start INTEGER NOT NULL,
                seed_count INTEGER NOT NULL,
                outcome_schema TEXT NOT NULL,
                outcomes BLOB NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(deck_hash, engine_hash, policy_hash, seed_start, seed_count, outcome_schema)
            );
            CREATE INDEX IF NOT EXISTS idx_result_lookup
                ON result_blocks(deck_hash, engine_hash, policy_hash, seed_start);

            CREATE TABLE IF NOT EXISTS traces (
                run_key TEXT NOT NULL REFERENCES result_blocks(run_key) ON DELETE CASCADE,
                game_offset INTEGER NOT NULL,
                trace_kind TEXT NOT NULL,
                codec TEXT NOT NULL,
                payload BLOB NOT NULL,
                PRIMARY KEY(run_key, game_offset, trace_kind)
            );

            CREATE TABLE IF NOT EXISTS experiments (
                experiment_hash TEXT PRIMARY KEY,
                baseline_deck_hash TEXT NOT NULL REFERENCES decks(deck_hash),
                config_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS experiment_variants (
                experiment_hash TEXT NOT NULL REFERENCES experiments(experiment_hash) ON DELETE CASCADE,
                variant_deck_hash TEXT NOT NULL REFERENCES decks(deck_hash),
                label TEXT NOT NULL,
                delta_json TEXT NOT NULL,
                PRIMARY KEY(experiment_hash, variant_deck_hash)
            );
            """
        )
        row = self.db.execute(
            "SELECT value FROM schema_meta WHERE key='schema_version'"
        ).fetchone()
        if row is None:
            self.db.execute(
                "INSERT INTO schema_meta(key,value) VALUES('schema_version',?)",
                (str(SCHEMA_VERSION),),
            )
        elif int(row["value"]) != SCHEMA_VERSION:
            raise RuntimeError(
                f"database schema {row['value']} != supported {SCHEMA_VERSION}"
            )
        self.db.commit()

    def register_deck(self, cards: Sequence[str] | dict[str, int], commander: str | None = None) -> str:
        payload = canonical_deck(cards, commander=commander)
        h = canonical_hash(payload)
        self.db.execute(
            """
            INSERT OR IGNORE INTO decks(deck_hash,commander,card_count,cards_json,created_at)
            VALUES(?,?,?,?,?)
            """,
            (h, commander, payload["card_count"], canonical_json(payload["cards"]), _utcnow()),
        )
        self.db.commit()
        return h

    def register_policy(self, policy: dict) -> str:
        h = canonical_hash(policy)
        self.db.execute(
            "INSERT OR IGNORE INTO policies(policy_hash,policy_json,created_at) VALUES(?,?,?)",
            (h, canonical_json(policy), _utcnow()),
        )
        self.db.commit()
        return h

    def register_engine(self, engine_manifest: dict) -> str:
        h = canonical_hash(engine_manifest)
        self.db.execute(
            "INSERT OR IGNORE INTO engines(engine_hash,engine_json,created_at) VALUES(?,?,?)",
            (h, canonical_json(engine_manifest), _utcnow()),
        )
        self.db.commit()
        return h

    def put_result_block(
        self,
        *,
        deck_hash_value: str,
        engine_hash: str,
        policy_hash: str,
        seed_start: int,
        outcomes: Iterable[Outcome],
    ) -> str:
        rows = list(outcomes)
        if not rows:
            raise ValueError("result block cannot be empty")
        payload = pack_outcomes(rows)
        key = run_key(
            deck_hash_value=deck_hash_value,
            engine_hash=engine_hash,
            policy_hash=policy_hash,
            seed_start=int(seed_start),
            seed_count=len(rows),
            outcome_schema=OUTCOME_SCHEMA,
        )
        try:
            self.db.execute(
                """
                INSERT INTO result_blocks(
                    run_key,deck_hash,engine_hash,policy_hash,seed_start,seed_count,
                    outcome_schema,outcomes,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?)
                """,
                (
                    key, deck_hash_value, engine_hash, policy_hash, int(seed_start), len(rows),
                    OUTCOME_SCHEMA, sqlite3.Binary(payload), _utcnow(),
                ),
            )
            self.db.commit()
        except sqlite3.IntegrityError:
            old = self.db.execute(
                "SELECT outcomes FROM result_blocks WHERE run_key=?", (key,)
            ).fetchone()
            if old is None or bytes(old["outcomes"]) != payload:
                raise RuntimeError(
                    "content-addressed result collision/non-determinism for run key " + key
                )
        return key

    def get_result_block(self, key: str) -> list[Outcome] | None:
        row = self.db.execute(
            "SELECT outcome_schema,outcomes FROM result_blocks WHERE run_key=?", (key,)
        ).fetchone()
        if row is None:
            return None
        if row["outcome_schema"] != OUTCOME_SCHEMA:
            raise RuntimeError(f"unsupported outcome schema {row['outcome_schema']}")
        return unpack_outcomes(row["outcomes"])

    def coverage_intervals(
        self,
        *,
        deck_hash_value: str,
        engine_hash: str,
        policy_hash: str,
    ) -> list[tuple[int, int]]:
        rows = self.db.execute(
            """
            SELECT seed_start,seed_count
            FROM result_blocks
            WHERE deck_hash=? AND engine_hash=? AND policy_hash=? AND outcome_schema=?
            ORDER BY seed_start
            """,
            (deck_hash_value, engine_hash, policy_hash, OUTCOME_SCHEMA),
        ).fetchall()
        spans = [(int(r["seed_start"]), int(r["seed_start"]) + int(r["seed_count"])) for r in rows]
        merged: list[list[int]] = []
        for start, end in spans:
            if not merged or start > merged[-1][1]:
                merged.append([start, end])
            else:
                merged[-1][1] = max(merged[-1][1], end)
        return [(a, b) for a, b in merged]

    def missing_intervals(
        self,
        *,
        deck_hash_value: str,
        engine_hash: str,
        policy_hash: str,
        seed_start: int,
        seed_count: int,
    ) -> list[tuple[int, int]]:
        """Return missing half-open [start,end) intervals for a requested seed range."""
        start = int(seed_start)
        end = start + int(seed_count)
        if start < 0 or end <= start:
            raise ValueError("invalid requested seed range")

        cursor = start
        missing: list[tuple[int, int]] = []
        for have_start, have_end in self.coverage_intervals(
            deck_hash_value=deck_hash_value,
            engine_hash=engine_hash,
            policy_hash=policy_hash,
        ):
            if have_end <= cursor:
                continue
            if have_start >= end:
                break
            if have_start > cursor:
                missing.append((cursor, min(have_start, end)))
            cursor = max(cursor, have_end)
            if cursor >= end:
                break
        if cursor < end:
            missing.append((cursor, end))
        return missing

    def put_trace(
        self,
        *,
        run_key_value: str,
        game_offset: int,
        trace_kind: str,
        codec: str,
        payload: bytes,
    ) -> None:
        self.db.execute(
            """
            INSERT OR REPLACE INTO traces(run_key,game_offset,trace_kind,codec,payload)
            VALUES(?,?,?,?,?)
            """,
            (run_key_value, int(game_offset), str(trace_kind), str(codec), sqlite3.Binary(payload)),
        )
        self.db.commit()

    def register_experiment(self, baseline_deck_hash: str, config: dict) -> str:
        h = canonical_hash({
            "baseline_deck_hash": baseline_deck_hash,
            "config": config,
        })
        self.db.execute(
            """
            INSERT OR IGNORE INTO experiments(experiment_hash,baseline_deck_hash,config_json,created_at)
            VALUES(?,?,?,?)
            """,
            (h, baseline_deck_hash, canonical_json(config), _utcnow()),
        )
        self.db.commit()
        return h

    def add_experiment_variant(
        self,
        *,
        experiment_hash: str,
        variant_deck_hash: str,
        label: str,
        delta: dict,
    ) -> None:
        self.db.execute(
            """
            INSERT OR REPLACE INTO experiment_variants(
                experiment_hash,variant_deck_hash,label,delta_json
            ) VALUES(?,?,?,?)
            """,
            (experiment_hash, variant_deck_hash, str(label), canonical_json(delta)),
        )
        self.db.commit()

    def stats(self) -> dict[str, int]:
        tables = ("decks", "policies", "engines", "result_blocks", "traces", "experiments", "experiment_variants")
        return {
            table: int(self.db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in tables
        }
