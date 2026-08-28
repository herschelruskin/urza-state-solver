#!/usr/bin/env python3
"""Compact deterministic identities for Phase-5 hot runtime state.

The readable rules engine remains string/dataclass based. This module is only the
memoization/cycle-detection projection used in inner Monte Carlo loops.

Known deck cards receive one-byte IDs. Scalar fields are streamed directly into a
SHA-256 digest so hot paths do not retain or repeatedly nest large tagged Python
tuples containing full card names and library state.
"""

from __future__ import annotations

from collections import Counter

from dataclasses import fields, is_dataclass
import hashlib
from pathlib import Path
import struct

from non_oracle_runtime_value_key import _pending_strategic_key

COMPACT_RUNTIME_ENCODING_VERSION = b"urza-phase5-compact-runtime-v1"

_EXCLUDED_MARKOV_FIELDS = frozenset({"trace", "interaction_seen", "urza_cast_turn"})
_SORTED_CARD_ZONES = frozenset({"hand", "graveyard", "exile"})


def _load_card_names():
    path=Path(__file__).with_name("decklist.txt")
    names=set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line=raw.strip()
        if not line:
            continue
        _,name=line.split(" ",1)
        names.add(name)
    ordered=tuple(sorted(names))
    if len(ordered)>=255:
        raise RuntimeError("compact card registry requires fewer than 255 names")
    return ordered


CARD_NAMES=_load_card_names()
CARD_TO_ID={name:index+1 for index,name in enumerate(CARD_NAMES)}
CARD_REGISTRY_DIGEST=hashlib.sha256("\n".join(CARD_NAMES).encode("utf-8")).digest()


class _DigestWriter:
    __slots__=("h",)

    def __init__(self,domain:bytes):
        self.h=hashlib.sha256()
        self.h.update(COMPACT_RUNTIME_ENCODING_VERSION)
        self.h.update(CARD_REGISTRY_DIGEST)
        self.raw(domain)

    def raw(self,data:bytes):
        self.h.update(struct.pack(">I",len(data)))
        self.h.update(data)

    def boolean(self,value:bool):
        self.h.update(b"B")
        self.h.update(b"\x01" if value else b"\x00")

    def integer(self,value:int):
        self.h.update(b"I")
        number=int(value)
        self.h.update(b"-" if number<0 else b"+")
        magnitude=abs(number)
        data=magnitude.to_bytes(max(1,(magnitude.bit_length()+7)//8),"big")
        self.raw(data)

    def floating(self,value:float):
        self.h.update(b"F")
        self.h.update(struct.pack(">d",float(value)))

    def text(self,value:str):
        data=str(value).encode("utf-8")
        self.h.update(b"T")
        self.raw(data)

    def card(self,value:str):
        name=str(value)
        card_id=CARD_TO_ID.get(name)
        self.h.update(b"C")
        if card_id is not None:
            self.h.update(bytes((card_id,)))
            return
        # Robust fallback for future generated/non-deck labels without retaining
        # the original string in hot keys.
        self.h.update(b"\x00")
        self.h.update(hashlib.sha256(name.encode("utf-8")).digest())

    def generic(self,value):
        if value is None:
            self.h.update(b"N")
            return
        if isinstance(value,bool):
            self.boolean(value)
            return
        if isinstance(value,int):
            self.integer(value)
            return
        if isinstance(value,float):
            self.floating(value)
            return
        if isinstance(value,str):
            if value in CARD_TO_ID:
                self.card(value)
            else:
                self.text(value)
            return
        if isinstance(value,tuple):
            self.h.update(b"(")
            self.integer(len(value))
            for item in value:
                self.generic(item)
            return
        if isinstance(value,list):
            self.h.update(b"[")
            self.integer(len(value))
            for item in value:
                self.generic(item)
            return
        if isinstance(value,(set,frozenset)):
            self.h.update(b"{")
            rows=tuple(sorted(value,key=repr))
            self.integer(len(rows))
            for item in rows:
                self.generic(item)
            return
        if isinstance(value,dict):
            self.h.update(b"D")
            rows=tuple(sorted(value.items(),key=lambda row:repr(row[0])))
            self.integer(len(rows))
            for key,item in rows:
                self.generic(key)
                self.generic(item)
            return
        if is_dataclass(value):
            self.h.update(b"d")
            self.text(value.__class__.__qualname__)
            for field in fields(value):
                self.text(field.name)
                self.generic(getattr(value,field.name))
            return
        method=getattr(value,"strategic_key",None)
        if method is not None:
            self.h.update(b"S")
            self.generic(tuple(method()))
            return
        raise TypeError(f"cannot compactly encode {type(value)!r}")

    def digest(self)->bytes:
        return self.h.digest()


def _permanent_signature(perm):
    """Match solver_architecture.PublicPermanent strategic/Markov semantics."""
    return (
        str(perm.name),
        bool(perm.tapped),
        bool(perm.sick),
        int(perm.counters),
        str(perm.mode),
        bool(perm.knack_granted),
        bool(perm.producer_urza_ready),
    )


def _write_permanent(writer:_DigestWriter,perm):
    writer.card(str(perm.name))
    writer.boolean(bool(perm.tapped))
    writer.boolean(bool(perm.sick))
    writer.integer(int(perm.counters))
    writer.text(str(perm.mode))
    writer.boolean(bool(perm.knack_granted))
    writer.boolean(bool(perm.producer_urza_ready))


def _write_card_sequence(writer:_DigestWriter,cards,*,sort_cards:bool=False):
    rows=tuple(str(card) for card in cards)
    if sort_cards:
        rows=tuple(sorted(rows))
    writer.integer(len(rows))
    for card in rows:
        writer.card(card)


def _write_true_markov_state(writer:_DigestWriter,state):
    if not is_dataclass(state):
        raise TypeError("compact Markov projection requires dataclass state")
    writer.text(state.__class__.__qualname__)
    for field in fields(state):
        name=field.name
        if name in _EXCLUDED_MARKOV_FIELDS:
            continue
        writer.text(name)
        value=getattr(state,name)
        if name in _SORTED_CARD_ZONES:
            writer.raw(b"sorted-card-zone")
            _write_card_sequence(writer,value,sort_cards=True)
        elif name=="library":
            writer.raw(b"ordered-library")
            _write_card_sequence(writer,value,sort_cards=False)
        elif name=="battlefield":
            writer.raw(b"canonical-battlefield")
            rows=tuple(sorted(value,key=_permanent_signature))
            writer.integer(len(rows))
            for perm in rows:
                _write_permanent(writer,perm)
        elif name=="urza_exile_permissions":
            writer.raw(b"ordered-card-zone")
            _write_card_sequence(writer,value,sort_cards=False)
        else:
            writer.generic(value)


def compact_markov_state_digest(state)->bytes:
    writer=_DigestWriter(b"markov-state")
    _write_true_markov_state(writer,state)
    return writer.digest()


def compact_runtime_cycle_digest(runtime)->bytes:
    """Exact sampled-world + semantic sidecar identity for episode cycles.

    This mirrors the equivalence relation of:
      canonical_markov_state_key(true_state) + runtime.value_key()
    while avoiding retention of those deeply nested tuples.
    """
    writer=_DigestWriter(b"episode-cycle")
    _write_true_markov_state(writer,runtime.true_state)

    info=runtime.information
    writer.raw(b"information")
    _write_card_sequence(writer,info.known_top,sort_cards=False)
    _write_card_sequence(writer,info.known_bottom,sort_cards=False)
    writer.integer(len(info.known_library_counts))
    for card,count in sorted(info.known_library_counts):
        writer.card(str(card))
        writer.integer(int(count))
    # shuffle_epoch is intentionally absent: the legacy strategic runtime value
    # key excludes shuffle provenance and retains only observable knowledge.

    writer.raw(b"permissions")
    permission_rows=tuple(sorted(
        (
            str(permission.card),
            int(permission.expires_turn),
            bool(permission.without_paying_mana_cost),
            str(permission.source),
        )
        for permission in runtime.permissions.permissions
    ))
    writer.integer(len(permission_rows))
    for card,expires,free,source in permission_rows:
        writer.card(card)
        writer.integer(expires)
        writer.boolean(free)
        writer.text(source)

    writer.raw(b"runtime-stack")
    writer.generic(tuple(runtime.stack.strategic_key()))

    writer.raw(b"window")
    writer.text(str(runtime.window.kind))

    writer.raw(b"pending")
    writer.generic(tuple(_pending_strategic_key(runtime.pending)))

    return writer.digest()


def compact_observation_digest(observation)->bytes:
    """Fixed-size identity for policy-visible observations.

    RuntimePolicyView/PolicyView are dataclasses containing only public state.
    Generic compact encoding therefore preserves their equality relation without
    constructing the recursively tagged stable_key() tuple.
    """
    writer=_DigestWriter(b"policy-observation")
    writer.generic(observation)
    return writer.digest()


def compact_action_strategic_digest(action)->bytes:
    """Fixed-size identity matching ActionIntent.strategic_key() semantics."""
    writer=_DigestWriter(b"strategic-action")
    equivalence_key=tuple(getattr(action,"equivalence_key",()) or ())
    if equivalence_key:
        writer.text(str(action.decision_stage))
        writer.text(str(action.kind))
        writer.generic(equivalence_key)
    else:
        writer.text(str(action.kind))
        params=tuple(sorted(
            ((str(key),value) for key,value in action.parameters),
            key=lambda row:row[0],
        ))
        writer.generic(params)
        writer.text(str(action.action_id))
        writer.text(str(action.decision_stage))
        writer.text(str(action.source))
        writer.text(str(action.contingent_on))
    return writer.digest()


def _write_strategic_value_state(writer:_DigestWriter,runtime):
    """Direct numeric equivalent of canonical_runtime_object_value_key(runtime).

    Exact hidden library order and RNG provenance are deliberately absent.
    """
    state=runtime.true_state
    info=runtime.information

    writer.raw(b"strategic-state")
    writer.integer(int(state.turn))

    # LibraryBeliefKey: order-free remaining multiset + legally known positions.
    counts=Counter(str(card) for card in state.library)
    writer.integer(len(counts))
    for card,count in sorted(counts.items()):
        writer.card(card)
        writer.integer(int(count))
    _write_card_sequence(writer,info.known_top,sort_cards=False)
    _write_card_sequence(writer,info.known_bottom,sort_cards=False)
    known_counts=tuple(sorted((str(card),int(count)) for card,count in info.known_library_counts))
    writer.integer(len(known_counts))
    for card,count in known_counts:
        if count<0:
            raise ValueError(f"negative known library count for {card!r}: {count}")
        writer.card(card)
        writer.integer(count)

    _write_card_sequence(writer,state.hand,sort_cards=True)

    rows=tuple(sorted(state.battlefield,key=_permanent_signature))
    writer.integer(len(rows))
    for perm in rows:
        _write_permanent(writer,perm)

    _write_card_sequence(writer,state.graveyard,sort_cards=True)
    _write_card_sequence(writer,state.exile,sort_cards=True)

    for name in (
        "blue","colorless","drain_bank","bauble_draws","remora_age",
        "ring_counters","ftt_level","uthros_counters","vfc_pumps",
        "commander_casts_from_zone",
    ):
        writer.text(name)
        writer.integer(int(getattr(state,name,0)))

    for name in (
        "land_played","remora_upkeep_pending","saga3_pending","urza",
        "chip_attached","spell_cast_this_turn","commander_in_command_zone","won",
    ):
        writer.text(name)
        writer.boolean(bool(getattr(state,name,False)))

    writer.text("chip_target")
    writer.text(str(getattr(state,"chip_target","")))
    writer.text("pa_target")
    writer.text(str(getattr(state,"pa_target","")))

    writer.text("urza_exile_permissions")
    _write_card_sequence(
        writer,
        getattr(state,"urza_exile_permissions",()),
        sort_cards=True,
    )

    writer.text("oracle_stack")
    writer.generic(tuple(
        tuple(str(item) for item in entry)
        for entry in getattr(state,"oracle_stack",())
    ))

    # objective_memory is empty for the production Phase-5 MC cache path.
    writer.text("objective_memory")
    writer.generic(())

    writer.raw(b"permissions")
    permission_rows=tuple(sorted(
        (
            str(permission.card),
            int(permission.expires_turn),
            bool(permission.without_paying_mana_cost),
            str(permission.source),
        )
        for permission in runtime.permissions.permissions
    ))
    writer.integer(len(permission_rows))
    for card,expires,free,source in permission_rows:
        writer.card(card)
        writer.integer(expires)
        writer.boolean(free)
        writer.text(source)

    writer.raw(b"runtime-stack")
    writer.generic(tuple(runtime.stack.strategic_key()))

    writer.raw(b"window")
    writer.text(str(runtime.window.kind))

    writer.raw(b"pending")
    writer.generic(tuple(_pending_strategic_key(runtime.pending)))


def compact_runtime_value_digest(runtime)->bytes:
    """Fixed 32-byte strategic Q identity, excluding exact hidden order/RNG."""
    writer=_DigestWriter(b"runtime-value")
    _write_strategic_value_state(writer,runtime)
    return writer.digest()
