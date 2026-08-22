#!/usr/bin/env python3
"""Seed-independent strategic value-state projection for non-Oracle DP/MC.

This module is deliberately decision-neutral. It does not alter Oracle State,
legal actions, pruning, beam search, shuffles, or winners. It provides a separate
identity for expected-value memoization and instrumentation.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional, Tuple

from solver_architecture import (
    InformationState,
    PublicPermanent,
    canonical_markov_state_key,
    stable_key,
)

STRATEGIC_VALUE_KEY_VERSION = "urza-strategic-value-v1"
INFORMATION_VALUE_KEY_VERSION = "urza-information-value-v1"


def _sorted_cards(values: Iterable[str]) -> Tuple[str, ...]:
    return tuple(sorted(str(v) for v in values))


def _canonical_permanent(perm: Any) -> PublicPermanent:
    return PublicPermanent(
        name=str(getattr(perm, "name")),
        tapped=bool(getattr(perm, "tapped", False)),
        sick=bool(getattr(perm, "sick", False)),
        counters=int(getattr(perm, "counters", 0)),
        mode=str(getattr(perm, "mode", "")),
        knack_granted=bool(getattr(perm, "knack_granted", False)),
        producer_urza_ready=bool(getattr(perm, "producer_urza_ready", False)),
    )


def _canonical_battlefield(permanents: Iterable[Any]) -> Tuple[PublicPermanent, ...]:
    return tuple(sorted(_canonical_permanent(p) for p in permanents))


def _normalize_known_counts(values: Iterable[Tuple[str, int]]) -> Tuple[Tuple[str, int], ...]:
    out = []
    for card, count in values:
        count = int(count)
        if count < 0:
            raise ValueError(f"negative known library count for {card!r}: {count}")
        out.append((str(card), count))
    return tuple(sorted(out))


def _normalize_objective_memory(
    memory: Optional[Mapping[str, Any] | Iterable[Tuple[str, Any]]],
) -> Tuple[Tuple[str, Any], ...]:
    if memory is None:
        return ()
    items = memory.items() if isinstance(memory, Mapping) else memory
    return tuple(sorted(((str(k), v) for k, v in items), key=lambda kv: kv[0]))


def canonical_information_value_key(information: InformationState) -> Tuple[Any, ...]:
    """Value-relevant legal knowledge, deliberately excluding shuffle_epoch.

    ``shuffle_epoch`` is useful for replay/invalidation bookkeeping but is not
    observable strategic information once current top/bottom/count knowledge is
    identical. It therefore must not inflate concrete+information denominators.
    """
    payload = (
        tuple(str(card) for card in information.known_top),
        tuple(str(card) for card in information.known_bottom),
        _normalize_known_counts(information.known_library_counts),
    )
    return stable_key(payload, version=INFORMATION_VALUE_KEY_VERSION)


@dataclass(frozen=True)
class LibraryBeliefKey:
    """Information-safe identity for the current hidden library."""

    remaining_counts: Tuple[Tuple[str, int], ...]
    known_top: Tuple[str, ...] = ()
    known_bottom: Tuple[str, ...] = ()
    known_library_counts: Tuple[Tuple[str, int], ...] = ()

    @classmethod
    def from_state(cls, state: Any, information: InformationState) -> "LibraryBeliefKey":
        counts = Counter(str(card) for card in getattr(state, "library", ()))
        return cls(
            remaining_counts=tuple(sorted(counts.items())),
            known_top=tuple(str(c) for c in information.known_top),
            known_bottom=tuple(str(c) for c in information.known_bottom),
            known_library_counts=_normalize_known_counts(information.known_library_counts),
        )


@dataclass(frozen=True)
class StrategicValueState:
    """Base state for V_win_by_horizon under a legal-information policy."""

    turn: int
    library_belief: LibraryBeliefKey
    hand: Tuple[str, ...]
    battlefield: Tuple[PublicPermanent, ...]
    graveyard: Tuple[str, ...]
    exile: Tuple[str, ...]
    blue: int
    colorless: int
    land_played: bool
    drain_bank: int
    bauble_draws: int
    remora_age: int
    remora_upkeep_pending: bool
    saga3_pending: bool
    ring_counters: int
    ftt_level: int
    uthros_counters: int
    urza: bool
    chip_attached: bool
    chip_target: str
    spell_cast_this_turn: bool
    pa_target: str
    vfc_pumps: int
    commander_in_command_zone: bool
    commander_casts_from_zone: int
    won: bool
    urza_exile_permissions: Tuple[str, ...] = ()
    objective_memory: Tuple[Tuple[str, Any], ...] = ()


def project_strategic_value_state(
    state: Any,
    information: InformationState,
    *,
    objective_memory: Optional[Mapping[str, Any] | Iterable[Tuple[str, Any]]] = None,
) -> StrategicValueState:
    return StrategicValueState(
        turn=int(getattr(state, "turn")),
        library_belief=LibraryBeliefKey.from_state(state, information),
        hand=_sorted_cards(getattr(state, "hand", ())),
        battlefield=_canonical_battlefield(getattr(state, "battlefield", ())),
        graveyard=_sorted_cards(getattr(state, "graveyard", ())),
        exile=_sorted_cards(getattr(state, "exile", ())),
        blue=int(getattr(state, "blue", 0)),
        colorless=int(getattr(state, "colorless", 0)),
        land_played=bool(getattr(state, "land_played", False)),
        drain_bank=int(getattr(state, "drain_bank", 0)),
        bauble_draws=int(getattr(state, "bauble_draws", 0)),
        remora_age=int(getattr(state, "remora_age", 0)),
        remora_upkeep_pending=bool(getattr(state, "remora_upkeep_pending", False)),
        saga3_pending=bool(getattr(state, "saga3_pending", False)),
        ring_counters=int(getattr(state, "ring_counters", 0)),
        ftt_level=int(getattr(state, "ftt_level", 1)),
        uthros_counters=int(getattr(state, "uthros_counters", 0)),
        urza=bool(getattr(state, "urza", False)),
        chip_attached=bool(getattr(state, "chip_attached", False)),
        chip_target=str(getattr(state, "chip_target", "")),
        spell_cast_this_turn=bool(getattr(state, "spell_cast_this_turn", False)),
        pa_target=str(getattr(state, "pa_target", "")),
        vfc_pumps=int(getattr(state, "vfc_pumps", 0)),
        commander_in_command_zone=bool(getattr(state, "commander_in_command_zone", True)),
        commander_casts_from_zone=int(getattr(state, "commander_casts_from_zone", 0)),
        won=bool(getattr(state, "won", False)),
        urza_exile_permissions=_sorted_cards(getattr(state, "urza_exile_permissions", ())),
        objective_memory=_normalize_objective_memory(objective_memory),
    )


def canonical_strategic_state_key(
    state: Any,
    information: InformationState,
    *,
    objective_memory: Optional[Mapping[str, Any] | Iterable[Tuple[str, Any]]] = None,
) -> Tuple[Any, ...]:
    projection = project_strategic_value_state(
        state,
        information,
        objective_memory=objective_memory,
    )
    return stable_key(projection, version=STRATEGIC_VALUE_KEY_VERSION)


class StrategicKeyProfiler:
    """Decision-neutral concrete/information -> strategic collapse measurement."""

    def __init__(self) -> None:
        self.observations = 0
        self._concrete = set()
        self._concrete_information = set()
        self._strategic = set()
        self._by_turn: MutableMapping[int, Dict[str, Any]] = defaultdict(
            lambda: {
                "observations": 0,
                "concrete": set(),
                "concrete_information": set(),
                "strategic": set(),
            }
        )
        self._by_turn_depth: MutableMapping[Tuple[int, int], Dict[str, Any]] = defaultdict(
            lambda: {
                "observations": 0,
                "concrete": set(),
                "concrete_information": set(),
                "strategic": set(),
            }
        )

    def observe(
        self,
        state: Any,
        information: InformationState,
        *,
        objective_memory: Optional[Mapping[str, Any] | Iterable[Tuple[str, Any]]] = None,
        depth: Optional[int] = None,
    ) -> None:
        concrete = canonical_markov_state_key(state)
        concrete_information = (concrete, canonical_information_value_key(information))
        strategic = canonical_strategic_state_key(
            state,
            information,
            objective_memory=objective_memory,
        )
        turn = int(getattr(state, "turn", 0))
        self.observations += 1
        self._concrete.add(concrete)
        self._concrete_information.add(concrete_information)
        self._strategic.add(strategic)
        bucket = self._by_turn[turn]
        bucket["observations"] += 1
        bucket["concrete"].add(concrete)
        bucket["concrete_information"].add(concrete_information)
        bucket["strategic"].add(strategic)
        if depth is not None:
            td = self._by_turn_depth[(turn, int(depth))]
            td["observations"] += 1
            td["concrete"].add(concrete)
            td["concrete_information"].add(concrete_information)
            td["strategic"].add(strategic)

    @staticmethod
    def _metrics(
        observations: int,
        concrete: int,
        concrete_information: int,
        strategic: int,
    ) -> Dict[str, float | int]:
        legacy_collapse = 0.0 if concrete == 0 else 1.0 - (strategic / concrete)
        information_collapse = (
            0.0 if concrete_information == 0
            else 1.0 - (strategic / concrete_information)
        )
        estimated_hit = 0.0 if observations == 0 else 1.0 - (strategic / observations)
        return {
            "observations": observations,
            "concrete_unique": concrete,
            "concrete_information_unique": concrete_information,
            "strategic_unique": strategic,
            "concrete_to_strategic_collapse_fraction": legacy_collapse,
            "concrete_information_to_strategic_collapse_fraction": information_collapse,
            "estimated_strategic_cache_hit_fraction": estimated_hit,
        }

    def summary(self) -> Dict[str, Any]:
        by_turn: Dict[int, Dict[str, float | int]] = {}
        for turn in sorted(self._by_turn):
            bucket = self._by_turn[turn]
            by_turn[turn] = self._metrics(
                int(bucket["observations"]),
                len(bucket["concrete"]),
                len(bucket["concrete_information"]),
                len(bucket["strategic"]),
            )
        by_turn_depth: Dict[str, Dict[str, float | int]] = {}
        for (turn, depth) in sorted(self._by_turn_depth):
            bucket = self._by_turn_depth[(turn, depth)]
            by_turn_depth[f"T{turn}D{depth}"] = self._metrics(
                int(bucket["observations"]),
                len(bucket["concrete"]),
                len(bucket["concrete_information"]),
                len(bucket["strategic"]),
            )
        return {
            **self._metrics(
                self.observations,
                len(self._concrete),
                len(self._concrete_information),
                len(self._strategic),
            ),
            "by_turn": by_turn,
            "by_turn_depth": by_turn_depth,
        }
