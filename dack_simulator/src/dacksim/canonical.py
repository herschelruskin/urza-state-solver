"""Canonical hashing used by cache keys and GUI-visible deck identities."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any


def _normalize(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _normalize(value[k]) for k in sorted(value, key=lambda x: str(x))}
    if isinstance(value, (list, tuple)):
        return [_normalize(v) for v in value]
    if isinstance(value, set):
        return [_normalize(v) for v in sorted(value, key=lambda x: repr(x))]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported canonical value: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    return json.dumps(
        _normalize(value),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    )


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def canonical_deck(cards: Sequence[str] | Mapping[str, int], commander: str | None = None) -> dict[str, Any]:
    if isinstance(cards, Mapping):
        counts = Counter()
        for name, n in cards.items():
            n = int(n)
            if n < 0:
                raise ValueError(f"negative card count for {name!r}")
            if n:
                counts[str(name)] += n
    else:
        counts = Counter(str(name) for name in cards)

    payload = {
        "commander": commander,
        "cards": [[name, counts[name]] for name in sorted(counts)],
        "card_count": sum(counts.values()),
    }
    return payload


def deck_hash(cards: Sequence[str] | Mapping[str, int], commander: str | None = None) -> str:
    return canonical_hash(canonical_deck(cards, commander=commander))


def run_key(
    *,
    deck_hash_value: str,
    engine_hash: str,
    policy_hash: str,
    seed_start: int,
    seed_count: int,
    outcome_schema: str = "outcome_u8_v1",
) -> str:
    if int(seed_start) < 0 or int(seed_count) <= 0:
        raise ValueError("seed_start must be >=0 and seed_count must be >0")
    return canonical_hash({
        "deck_hash": str(deck_hash_value),
        "engine_hash": str(engine_hash),
        "policy_hash": str(policy_hash),
        "seed_start": int(seed_start),
        "seed_count": int(seed_count),
        "outcome_schema": str(outcome_schema),
    })
