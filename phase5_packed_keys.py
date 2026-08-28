#!/usr/bin/env python3
"""Collision-free packed byte identities for Phase-5 hot paths.

These are canonical *projection* encodings, not hashes:
- episode-cycle keys preserve exact Markov future state + runtime semantic sidecars;
- Q keys preserve only legal-information strategic value state + sidecars;
- observation/action keys preserve exactly the policy-facing equivalence relation.

The packed bytes are authoritative. Hashes may be derived for logs only.
"""

from __future__ import annotations

from dataclasses import fields
from typing import Any

from solver_architecture import InformationState, PublicPermanent
from strategic_value_state import project_strategic_value_state
from non_oracle_runtime_value_key import (
    _pending_strategic_key,
    urza_permissions_strategic_key,
)
from phase5_lossless_packed_codec import (
    PACKED_SCHEMA_DIGEST,
    pack_lossless_body,
    unpack_lossless_body,
)

PACKED_KEY_VERSION="urza-phase5-packed-keys-v1"
_EXCLUDED_MARKOV_FIELDS=frozenset({"trace","interaction_seen","urza_cast_turn"})


def _public_perm(perm)->PublicPermanent:
    return PublicPermanent(
        name=str(getattr(perm,"name")),
        tapped=bool(getattr(perm,"tapped",False)),
        sick=bool(getattr(perm,"sick",False)),
        counters=int(getattr(perm,"counters",0)),
        mode=str(getattr(perm,"mode","")),
        knack_granted=bool(getattr(perm,"knack_granted",False)),
        producer_urza_ready=bool(getattr(perm,"producer_urza_ready",False)),
    )


def _markov_state_projection(state)->tuple[Any,...]:
    """Tuple equivalent to canonical_markov_state_key(state), without tagged wrappers."""
    rows=[]
    for field in fields(state):
        name=field.name
        if name in _EXCLUDED_MARKOV_FIELDS:
            continue
        value=getattr(state,name)
        if name=="hand":
            value=tuple(sorted(value))
        elif name=="battlefield":
            value=tuple(sorted(_public_perm(perm) for perm in value))
        elif name in {"graveyard","exile"}:
            value=tuple(sorted(value))
        rows.append(value)
    return tuple(rows)


def _information_value_projection(info:InformationState)->tuple[Any,...]:
    """Match strategic information value identity; shuffle_epoch is provenance."""
    return (
        tuple(str(card) for card in info.known_top),
        tuple(str(card) for card in info.known_bottom),
        tuple(sorted((str(card),int(count)) for card,count in info.known_library_counts)),
    )


def _runtime_sidecar_projection(runtime)->tuple[Any,...]:
    return (
        tuple(urza_permissions_strategic_key(runtime.permissions)),
        tuple(runtime.stack.strategic_key()),
        str(runtime.window.kind),
        tuple(_pending_strategic_key(runtime.pending)),
    )


def packed_episode_cycle_key(runtime)->bytes:
    """Collision-free exact sampled-world cycle identity."""
    projection=(
        PACKED_KEY_VERSION,
        "episode-cycle",
        PACKED_SCHEMA_DIGEST,
        _markov_state_projection(runtime.true_state),
        _information_value_projection(runtime.information),
        _runtime_sidecar_projection(runtime),
    )
    return b"C"+pack_lossless_body(projection)


def packed_runtime_value_key(runtime)->bytes:
    """Collision-free strategic Q/V identity; exact hidden order/RNG are absent."""
    projection=(
        PACKED_KEY_VERSION,
        "runtime-value",
        PACKED_SCHEMA_DIGEST,
        project_strategic_value_state(
            runtime.true_state,
            runtime.information,
            objective_memory=None,
        ),
        _runtime_sidecar_projection(runtime),
    )
    return b"Q"+pack_lossless_body(projection)


def packed_observation_key(observation)->bytes:
    return b"O"+pack_lossless_body((
        PACKED_KEY_VERSION,
        "observation",
        PACKED_SCHEMA_DIGEST,
        observation,
    ))


def _action_projection(action)->tuple[Any,...]:
    equivalence_key=tuple(getattr(action,"equivalence_key",()) or ())
    if equivalence_key:
        return (
            str(action.decision_stage),
            str(action.kind),
            equivalence_key,
        )
    return (
        str(action.kind),
        tuple(sorted(
            ((str(key),value) for key,value in action.parameters),
            key=lambda row:row[0],
        )),
        str(action.action_id),
        str(action.decision_stage),
        str(action.source),
        str(action.contingent_on),
    )


def packed_action_strategic_key(action)->bytes:
    return b"A"+pack_lossless_body((
        PACKED_KEY_VERSION,
        "strategic-action",
        PACKED_SCHEMA_DIGEST,
        _action_projection(action),
    ))


def packed_phase5_decision_cache_key(
    *,
    runtime,
    candidate_action_keys,
    rollout_count:int,
    mc_root_seed:int,
    horizon:int,
    objective:str,
    policy_id:str,
    continuation_id:str,
    sample_namespace:str,
    max_episode_steps:int,
    strict_terminal_reasons:bool,
)->bytes:
    return b"D"+pack_lossless_body((
        PACKED_KEY_VERSION,
        "phase5-decision",
        PACKED_SCHEMA_DIGEST,
        packed_runtime_value_key(runtime),
        tuple(sorted(candidate_action_keys)),
        int(rollout_count),
        int(mc_root_seed),
        int(horizon),
        str(objective),
        str(policy_id),
        str(continuation_id),
        str(sample_namespace),
        int(max_episode_steps),
        bool(strict_terminal_reasons),
    ))


def unpack_packed_projection(key:bytes):
    """Debug helper returning the packed projection payload (prefix excluded)."""
    if not key:
        raise ValueError("empty packed key")
    return unpack_lossless_body(key[1:])
