"""Compact stable encoding for the hot-path per-game result.

One byte stores everything required for the primary deployment endpoints:

bits 0..1: seat      0..3
bits 2..4: keep_n-1  0..6 (represents keeps 1..7)
bits 5..6: win_turn  0..3 (0 = no win through T3)
bit 7:     reserved  must be zero in v1

Therefore 4096 games require exactly 4096 bytes before database/page overhead.
Game id and seed are implicit from the containing seed block manifest.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator

SCHEMA = "outcome_u8_v1"


@dataclass(frozen=True, slots=True)
class Outcome:
    seat: int
    keep_n: int
    win_turn: int

    def validate(self) -> None:
        if not 0 <= int(self.seat) <= 3:
            raise ValueError(f"seat out of range: {self.seat}")
        if not 1 <= int(self.keep_n) <= 7:
            raise ValueError(f"keep_n out of range: {self.keep_n}")
        if not 0 <= int(self.win_turn) <= 3:
            raise ValueError(f"win_turn out of range: {self.win_turn}")


def encode_outcome(outcome: Outcome) -> int:
    outcome.validate()
    return (
        int(outcome.seat)
        | ((int(outcome.keep_n) - 1) << 2)
        | (int(outcome.win_turn) << 5)
    )


def decode_outcome(value: int) -> Outcome:
    value = int(value)
    if not 0 <= value <= 255:
        raise ValueError(f"encoded byte out of range: {value}")
    if value & 0x80:
        raise ValueError("reserved outcome bit is set; unsupported schema/version")
    return Outcome(
        seat=value & 0x03,
        keep_n=((value >> 2) & 0x07) + 1,
        win_turn=(value >> 5) & 0x03,
    )


def pack_outcomes(rows: Iterable[Outcome]) -> bytes:
    return bytes(encode_outcome(row) for row in rows)


def iter_outcomes(payload: bytes | bytearray | memoryview) -> Iterator[Outcome]:
    for value in payload:
        yield decode_outcome(value)


def unpack_outcomes(payload: bytes | bytearray | memoryview) -> list[Outcome]:
    return list(iter_outcomes(payload))
