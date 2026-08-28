#!/usr/bin/env python3
"""Lossless reversible binary codec for Urza solver state.

This codec is intentionally separate from strategic/Markov projections:
- exact objects round-trip with every field preserved;
- known deck card strings use one byte;
- arbitrary strings/integers remain lossless;
- dataclass schemas use compact numeric class IDs;
- a registry/schema fingerprint prevents silent cross-version misdecode.

The format is designed for local simulation storage/checkpointing and compact
in-memory state when exact reconstruction is required.
"""

from __future__ import annotations

from dataclasses import fields, is_dataclass
import hashlib
import struct
from typing import Any

import urza_solver as solver
from solver_architecture import (
    EpisodeOutcome,
    InformationState,
    PolicyView,
    PublicPermanent,
)
from decision_observation import (
    ActionIntent,
    PolicyDecisionContext,
    DecisionRequest,
    DrawObservation,
    RevealTopObservation,
    SearchZoneObservation,
    ShuffleObservation,
    MoveKnownCardObservation,
    LibraryPositionsObservation,
    PublicZoneChangeObservation,
    EnvironmentObservation,
    ObservationBatch,
    PendingDecisionSpec,
    TransitionEnvelope,
)
from non_oracle_runtime import (
    RuntimeStackObject,
    RuntimeStack,
    RuntimePendingDecision,
    NonOracleRuntimeState,
)
from non_oracle_runtime_view import (
    PublicPlayPermissionView,
    PublicPendingTriggerView,
    PublicRuntimeStackObjectView,
    RuntimePolicyView,
)
from non_oracle_runtime_value_key import RuntimeDecisionWindow
from urza_permission_adapter import (
    UrzaPlayPermission,
    UrzaPermissionState,
)
from phase3_value_engine import WinDistributionValue
from phase5_compact_runtime_encoding import CARD_NAMES, CARD_TO_ID, CARD_REGISTRY_DIGEST


PACKED_STATE_MAGIC=b"UZPK"
PACKED_STATE_VERSION=1

# Explicit stable numeric IDs. Never renumber an existing entry.
_CLASS_ROWS=(
    (1, solver.Perm),
    (2, solver.State),
    (3, InformationState),
    (4, PublicPermanent),
    (5, PolicyView),
    (6, ActionIntent),
    (7, PolicyDecisionContext),
    (8, DecisionRequest),
    (9, DrawObservation),
    (10, RevealTopObservation),
    (11, SearchZoneObservation),
    (12, ShuffleObservation),
    (13, MoveKnownCardObservation),
    (14, LibraryPositionsObservation),
    (15, PublicZoneChangeObservation),
    (16, EnvironmentObservation),
    (17, ObservationBatch),
    (18, PendingDecisionSpec),
    (19, TransitionEnvelope),
    (20, RuntimeStackObject),
    (21, RuntimeStack),
    (22, RuntimePendingDecision),
    (23, NonOracleRuntimeState),
    (24, PublicPlayPermissionView),
    (25, PublicPendingTriggerView),
    (26, PublicRuntimeStackObjectView),
    (27, RuntimePolicyView),
    (28, RuntimeDecisionWindow),
    (29, UrzaPlayPermission),
    (30, UrzaPermissionState),
    (31, EpisodeOutcome),
    (32, WinDistributionValue),
)
_CLASS_TO_ID={cls:class_id for class_id,cls in _CLASS_ROWS}
_ID_TO_CLASS={class_id:cls for class_id,cls in _CLASS_ROWS}

_SCHEMA_TEXT="\n".join(
    f"{class_id}:{cls.__module__}.{cls.__qualname__}:"
    + ",".join(field.name for field in fields(cls))
    for class_id,cls in _CLASS_ROWS
)
PACKED_SCHEMA_DIGEST=hashlib.sha256(_SCHEMA_TEXT.encode("utf-8")).digest()

# Scalar/container tags.
_T_NONE=0
_T_FALSE=1
_T_TRUE=2
_T_INT=3
_T_FLOAT=4
_T_CARD=5
_T_TEXT=6
_T_BYTES=7
_T_TUPLE=8
_T_LIST=9
_T_DICT=10
_T_SET=11
_T_FROZENSET=12
_T_DATACLASS=13


class PackedStateError(ValueError):
    pass


def _write_uvarint(out:bytearray,value:int)->None:
    value=int(value)
    if value<0:
        raise PackedStateError("uvarint cannot encode negative value")
    while value>=0x80:
        out.append((value&0x7F)|0x80)
        value >>= 7
    out.append(value)


def _read_uvarint(data:memoryview,offset:int)->tuple[int,int]:
    value=0
    shift=0
    while True:
        if offset>=len(data):
            raise PackedStateError("truncated uvarint")
        byte=int(data[offset]); offset+=1
        value |= (byte&0x7F)<<shift
        if not (byte&0x80):
            return value,offset
        shift += 7
        if shift>4096:
            raise PackedStateError("uvarint is unreasonably large")


def _write_int(out:bytearray,value:int)->None:
    n=int(value)
    zigzag=2*n if n>=0 else -2*n-1
    _write_uvarint(out,zigzag)


def _read_int(data:memoryview,offset:int)->tuple[int,int]:
    zigzag,offset=_read_uvarint(data,offset)
    value=zigzag//2 if zigzag%2==0 else -(zigzag//2)-1
    return value,offset


def _write_blob(out:bytearray,payload:bytes)->None:
    _write_uvarint(out,len(payload))
    out.extend(payload)


def _read_blob(data:memoryview,offset:int)->tuple[bytes,int]:
    size,offset=_read_uvarint(data,offset)
    end=offset+size
    if end>len(data):
        raise PackedStateError("truncated byte payload")
    return bytes(data[offset:end]),end


def _encode_value(out:bytearray,value:Any)->None:
    if value is None:
        out.append(_T_NONE); return
    if value is False:
        out.append(_T_FALSE); return
    if value is True:
        out.append(_T_TRUE); return
    if isinstance(value,int):
        out.append(_T_INT); _write_int(out,value); return
    if isinstance(value,float):
        out.append(_T_FLOAT)
        out.extend(struct.pack(">d",float(value)))
        return
    if isinstance(value,str):
        card_id=CARD_TO_ID.get(value)
        if card_id is not None:
            out.append(_T_CARD); out.append(card_id); return
        out.append(_T_TEXT); _write_blob(out,value.encode("utf-8")); return
    if isinstance(value,(bytes,bytearray,memoryview)):
        out.append(_T_BYTES); _write_blob(out,bytes(value)); return
    if isinstance(value,tuple):
        out.append(_T_TUPLE); _write_uvarint(out,len(value))
        for item in value: _encode_value(out,item)
        return
    if isinstance(value,list):
        out.append(_T_LIST); _write_uvarint(out,len(value))
        for item in value: _encode_value(out,item)
        return
    if isinstance(value,dict):
        out.append(_T_DICT); _write_uvarint(out,len(value))
        # Preserve insertion order for exact round-trip.
        for key,item in value.items():
            _encode_value(out,key); _encode_value(out,item)
        return
    if isinstance(value,set):
        out.append(_T_SET)
        rows=tuple(sorted(value,key=repr))
        _write_uvarint(out,len(rows))
        for item in rows: _encode_value(out,item)
        return
    if isinstance(value,frozenset):
        out.append(_T_FROZENSET)
        rows=tuple(sorted(value,key=repr))
        _write_uvarint(out,len(rows))
        for item in rows: _encode_value(out,item)
        return
    if is_dataclass(value):
        cls=type(value)
        class_id=_CLASS_TO_ID.get(cls)
        if class_id is None:
            raise PackedStateError(
                f"unregistered dataclass {cls.__module__}.{cls.__qualname__}"
            )
        out.append(_T_DATACLASS)
        _write_uvarint(out,class_id)
        for field in fields(cls):
            _encode_value(out,getattr(value,field.name))
        return
    raise PackedStateError(f"unsupported packed value type {type(value)!r}")


def _decode_value(data:memoryview,offset:int)->tuple[Any,int]:
    if offset>=len(data):
        raise PackedStateError("truncated value")
    tag=int(data[offset]); offset+=1
    if tag==_T_NONE: return None,offset
    if tag==_T_FALSE: return False,offset
    if tag==_T_TRUE: return True,offset
    if tag==_T_INT: return _read_int(data,offset)
    if tag==_T_FLOAT:
        end=offset+8
        if end>len(data): raise PackedStateError("truncated float")
        return struct.unpack(">d",data[offset:end])[0],end
    if tag==_T_CARD:
        if offset>=len(data): raise PackedStateError("truncated card id")
        card_id=int(data[offset]); offset+=1
        if not 1<=card_id<=len(CARD_NAMES):
            raise PackedStateError(f"unknown card id {card_id}")
        return CARD_NAMES[card_id-1],offset
    if tag==_T_TEXT:
        payload,offset=_read_blob(data,offset)
        return payload.decode("utf-8"),offset
    if tag==_T_BYTES:
        return _read_blob(data,offset)
    if tag in (_T_TUPLE,_T_LIST,_T_SET,_T_FROZENSET):
        count,offset=_read_uvarint(data,offset)
        rows=[]
        for _ in range(count):
            item,offset=_decode_value(data,offset)
            rows.append(item)
        if tag==_T_TUPLE: return tuple(rows),offset
        if tag==_T_LIST: return rows,offset
        if tag==_T_SET: return set(rows),offset
        return frozenset(rows),offset
    if tag==_T_DICT:
        count,offset=_read_uvarint(data,offset)
        out={}
        for _ in range(count):
            key,offset=_decode_value(data,offset)
            item,offset=_decode_value(data,offset)
            out[key]=item
        return out,offset
    if tag==_T_DATACLASS:
        class_id,offset=_read_uvarint(data,offset)
        cls=_ID_TO_CLASS.get(class_id)
        if cls is None:
            raise PackedStateError(f"unknown packed class id {class_id}")
        values=[]
        for _field in fields(cls):
            item,offset=_decode_value(data,offset)
            values.append(item)
        return cls(*values),offset
    raise PackedStateError(f"unknown packed tag {tag}")


def pack_lossless(value:Any)->bytes:
    body=bytearray()
    _encode_value(body,value)
    header=bytearray(PACKED_STATE_MAGIC)
    header.append(PACKED_STATE_VERSION)
    header.extend(CARD_REGISTRY_DIGEST)
    header.extend(PACKED_SCHEMA_DIGEST)
    header.extend(body)
    return bytes(header)


def unpack_lossless(payload:bytes)->Any:
    data=memoryview(payload)
    header_size=4+1+32+32
    if len(data)<header_size:
        raise PackedStateError("packed state is shorter than header")
    if bytes(data[:4])!=PACKED_STATE_MAGIC:
        raise PackedStateError("invalid packed-state magic")
    version=int(data[4])
    if version!=PACKED_STATE_VERSION:
        raise PackedStateError(
            f"unsupported packed-state version {version}; expected {PACKED_STATE_VERSION}"
        )
    if bytes(data[5:37])!=CARD_REGISTRY_DIGEST:
        raise PackedStateError("card registry mismatch")
    if bytes(data[37:69])!=PACKED_SCHEMA_DIGEST:
        raise PackedStateError("packed dataclass schema mismatch")
    value,offset=_decode_value(data,header_size)
    if offset!=len(data):
        raise PackedStateError(f"trailing bytes after packed state: {len(data)-offset}")
    return value


def packed_fingerprint(payload:bytes)->bytes:
    """Optional short lookup fingerprint; packed bytes remain authoritative."""
    return hashlib.sha256(payload).digest()


def lossless_roundtrip(value:Any)->Any:
    return unpack_lossless(pack_lossless(value))
