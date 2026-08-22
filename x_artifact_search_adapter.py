#!/usr/bin/env python3
"""Phase-1 staged non-Oracle adapters for Reshape and Whir of Invention.

The critical anti-clairvoyance invariant for both spells is that X is chosen while
casting, before a library search reveals eligible artifact targets. Reshape also
sacrifices an artifact as an additional casting cost. Whir may use improvise as
part of paying the generic portion of its cast cost.

This module intentionally lives beside the Oracle macros. It reuses validated
mana/permanent helpers but does not alter Oracle search behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import combinations
from typing import Dict, Optional, Tuple

import urza_solver as solver
from solver_architecture import InformationState, make_policy_view
from decision_observation import (
    ActionIntent,
    DECISION_COMMIT,
    DECISION_MECHANICAL,
    DECISION_POST_OBSERVATION,
    DecisionRequest,
    ObservationBatch,
    PendingDecisionSpec,
    PolicyDecisionContext,
    SearchZoneObservation,
    ShuffleObservation,
    TransitionEnvelope,
    apply_observation_batch,
)

RESHAPE = "Reshape"
WHIR = "Whir of Invention"
SEARCH_KIND = "x_artifact_search_target"
ETB_KIND = "resolve_entered_artifact_triggers"


@dataclass(frozen=True)
class SearchContext:
    source: str
    x: int
    search_decision_id: str
    cast_action_id: str


@dataclass(frozen=True, order=True)
class PermanentSlot:
    """Publicly addressable battlefield object without runtime instance tags."""

    name: str
    mode: str
    tapped: bool
    sick: bool
    counters: int
    knack_granted: bool
    producer_urza_ready: bool
    occurrence: int

    def key(self) -> Tuple[object, ...]:
        return (
            self.name,
            self.mode,
            self.tapped,
            self.sick,
            self.counters,
            self.knack_granted,
            self.producer_urza_ready,
            self.occurrence,
        )


def _source_prefix(source: str) -> str:
    return source.lower().replace(" ", ".").replace("'", "")


def _slot_base(perm) -> Tuple[object, ...]:
    return (
        str(getattr(perm, "name", "")),
        str(getattr(perm, "mode", "")),
        bool(getattr(perm, "tapped", False)),
        bool(getattr(perm, "sick", False)),
        int(getattr(perm, "counters", 0)),
        bool(getattr(perm, "knack_granted", False)),
        bool(getattr(perm, "producer_urza_ready", False)),
    )


def _public_slots(state, predicate) -> Tuple[PermanentSlot, ...]:
    grouped: Dict[Tuple[object, ...], int] = {}
    rows = []
    ordered = sorted(
        ((i, p) for i, p in enumerate(state.battlefield) if predicate(p)),
        key=lambda row: (_slot_base(row[1]), row[0]),
    )
    for _, perm in ordered:
        base = _slot_base(perm)
        occurrence = grouped.get(base, 0)
        grouped[base] = occurrence + 1
        rows.append(PermanentSlot(*base, occurrence))
    return tuple(rows)


def _slot_index(state, wanted: PermanentSlot) -> int:
    occurrence = 0
    wanted_base = tuple(wanted.key()[:-1])
    for index, perm in sorted(
        enumerate(state.battlefield), key=lambda row: (_slot_base(row[1]), row[0])
    ):
        if _slot_base(perm) != wanted_base:
            continue
        if occurrence == wanted.occurrence:
            return index
        occurrence += 1
    raise ValueError(f"battlefield slot no longer exists: {wanted!r}")


def _artifact_slots(state, *, untapped_only: bool = False) -> Tuple[PermanentSlot, ...]:
    return _public_slots(
        state,
        lambda p: solver.is_artifact_perm(p) and (not untapped_only or not p.tapped),
    )


def _slot_from_parameter(raw) -> PermanentSlot:
    if not isinstance(raw, tuple) or len(raw) != 8:
        raise ValueError("invalid permanent slot parameter")
    return PermanentSlot(
        str(raw[0]),
        str(raw[1]),
        bool(raw[2]),
        bool(raw[3]),
        int(raw[4]),
        bool(raw[5]),
        bool(raw[6]),
        int(raw[7]),
    )


def _artifact_search_event(state, source: str, x: int) -> SearchZoneObservation:
    legal = tuple(
        sorted(
            {
                card
                for card in state.library
                if card in solver.ARTIFACTS and solver.mana_value(card) <= int(x)
            }
        )
    )
    return SearchZoneObservation(
        zone="library",
        legal_cards=legal,
        context=f"{source} X={int(x)}",
        may_fail_to_find=True,
    )


def _target_intents(
    context: SearchContext, search: SearchZoneObservation
) -> Tuple[ActionIntent, ...]:
    prefix = _source_prefix(context.source)
    rows = [
        ActionIntent(
            action_id=f"{prefix}.target.fail",
            kind=SEARCH_KIND,
            parameters=(("target", ""), ("x", context.x)),
            equivalence_key=(context.source, "fail", context.x),
            label="Find no card",
            decision_stage=DECISION_POST_OBSERVATION,
            source=context.source,
            contingent_on=context.cast_action_id,
        )
    ]
    for index, card in enumerate(search.legal_cards):
        rows.append(
            ActionIntent(
                action_id=f"{prefix}.target.{index:02d}",
                kind=SEARCH_KIND,
                parameters=(("target", card), ("x", context.x)),
                equivalence_key=(context.source, "target", card, context.x),
                label=f"Find {card}",
                decision_stage=DECISION_POST_OBSERVATION,
                source=context.source,
                contingent_on=context.cast_action_id,
            )
        )
    return tuple(rows)


def _target_request(
    state,
    information: InformationState,
    context: SearchContext,
    search: SearchZoneObservation,
    *,
    horizon: int,
    objective: str,
    policy_id: str,
    caverns_live: Optional[bool],
) -> DecisionRequest:
    return DecisionRequest(
        observation=make_policy_view(state, information, caverns_live=caverns_live),
        actions=_target_intents(context, search),
        context=PolicyDecisionContext(
            horizon=horizon,
            objective=objective,
            policy_id=policy_id,
            decision_id=context.search_decision_id,
            decision_stage=DECISION_POST_OBSERVATION,
        ),
    )


def _target_from_action(
    action: ActionIntent, context: SearchContext, search: SearchZoneObservation
) -> str:
    if action.kind != SEARCH_KIND or action.decision_stage != DECISION_POST_OBSERVATION:
        raise ValueError("not an X-artifact search target action")
    params = dict(action.parameters)
    if int(params.get("x", -1)) != context.x:
        raise ValueError("target action X does not match committed X")
    target = str(params.get("target", ""))
    if target and target not in search.legal_cards:
        raise ValueError("chosen target was not legally revealed by search")
    return target


def _finish_search(state, context: SearchContext, target: str) -> TransitionEnvelope:
    if not target:
        salt = f"{_source_prefix(context.source)}:no-target:x{context.x}"
        shuffled = replace(state, library=solver.shuffled_library(state, salt))
        shuffled = solver.add_trace(
            shuffled, f"{context.source} X={context.x}: find no card; shuffle"
        )
        return TransitionEnvelope(
            true_state=shuffled,
            observations=ObservationBatch((ShuffleObservation(context.source),)),
            pending_decision=None,
            trace_note="Qualified search failed to find",
        )

    lib = list(state.library)
    if target not in lib:
        raise ValueError("chosen target is no longer in library")
    lib.remove(target)
    without = replace(state, library=tuple(lib))
    entered = solver.add_perm(without, target, sick=target in solver.CREATURES)
    salt = ("reshape:" + target) if context.source == RESHAPE else ("whir:" + target)
    shuffled = replace(entered, library=solver.shuffled_library(entered, salt))
    shuffled = solver.add_trace(
        shuffled, f"{context.source} X={context.x} -> {target}; shuffle"
    )
    return TransitionEnvelope(
        true_state=shuffled,
        observations=ObservationBatch((ShuffleObservation(context.source),)),
        pending_decision=PendingDecisionSpec(
            decision_id=f"{_source_prefix(context.source)}.etb",
            kind=ETB_KIND,
            source=target,
            decision_stage=DECISION_MECHANICAL,
            contingent_on=context.search_decision_id,
        ),
        trace_note="Artifact entered; ETB trigger bundle intentionally deferred",
    )


# ---------------------------------------------------------------------------
# Reshape
# ---------------------------------------------------------------------------


def reshape_cast_intents(state) -> Tuple[ActionIntent, ...]:
    if RESHAPE not in state.hand or state.blue < 2:
        return ()
    sacrifices = _artifact_slots(state)
    if not sacrifices:
        return ()
    reduction = solver.medallion_reduction(state, RESHAPE)
    generic_capacity = state.colorless + max(0, state.blue - 2)
    max_x = generic_capacity + reduction
    rows = []
    serial = 0
    for x in range(max_x + 1):
        generic = max(0, x - reduction)
        if not solver.can_pay(state, generic, 2):
            continue
        for slot in sacrifices:
            rows.append(
                ActionIntent(
                    action_id=f"reshape.cast.{serial:03d}",
                    kind="cast_reshape",
                    parameters=(
                        ("x", x),
                        ("generic_paid", generic),
                        ("sacrifice", slot.key()),
                    ),
                    equivalence_key=("reshape", x, slot.key()),
                    label=f"Cast Reshape X={x}; sacrifice {slot.name or slot.mode}",
                    decision_stage=DECISION_COMMIT,
                    source=RESHAPE,
                )
            )
            serial += 1
    return tuple(rows)


def reshape_cast_request(
    state,
    information: InformationState,
    *,
    horizon: int,
    objective: str = "win_by_horizon",
    policy_id: str = "base",
    caverns_live: Optional[bool] = None,
) -> DecisionRequest:
    return DecisionRequest(
        observation=make_policy_view(state, information, caverns_live=caverns_live),
        actions=reshape_cast_intents(state),
        context=PolicyDecisionContext(
            horizon=horizon,
            objective=objective,
            policy_id=policy_id,
            decision_id="reshape.cast",
            decision_stage=DECISION_COMMIT,
        ),
    )


def resolve_reshape_cast(
    state, action: ActionIntent
) -> Tuple[TransitionEnvelope, SearchContext, SearchZoneObservation]:
    legal = {
        candidate.canonical_key(): candidate for candidate in reshape_cast_intents(state)
    }
    if action.canonical_key() not in legal:
        raise ValueError("Reshape cast action is not legal in current state")
    params = dict(action.parameters)
    x = int(params["x"])
    generic = int(params["generic_paid"])
    slot = _slot_from_parameter(tuple(params["sacrifice"]))

    paid = solver.pay(state, generic, 2)
    if paid is None:
        raise ValueError("Reshape mana cost could not be paid")
    paid = replace(
        paid,
        hand=solver.remove_one(paid.hand, RESHAPE),
        graveyard=paid.graveyard + (RESHAPE,),
        spell_cast_this_turn=True,
    )
    index = _slot_index(paid, slot)
    paid = solver.remove_perm(paid, index)
    paid = solver.vfc_noncreature_cast_trigger(paid, RESHAPE)
    paid = solver.add_trace(
        paid, f"cast Reshape X={x}; artifact sacrificed as additional cost"
    )

    search = _artifact_search_event(paid, RESHAPE, x)
    context = SearchContext(RESHAPE, x, "reshape.search.target", action.action_id)
    envelope = TransitionEnvelope(
        true_state=paid,
        observations=ObservationBatch((search,)),
        pending_decision=PendingDecisionSpec(
            decision_id=context.search_decision_id,
            kind=SEARCH_KIND,
            source=RESHAPE,
            decision_stage=DECISION_POST_OBSERVATION,
            contingent_on=action.action_id,
        ),
        trace_note=f"Reshape search opened at committed X={x}",
    )
    return envelope, context, search


def reshape_target_request(
    state_after_cast,
    information: InformationState,
    context: SearchContext,
    search: SearchZoneObservation,
    *,
    horizon: int,
    objective: str = "win_by_horizon",
    policy_id: str = "base",
    caverns_live: Optional[bool] = None,
) -> DecisionRequest:
    return _target_request(
        state_after_cast,
        information,
        context,
        search,
        horizon=horizon,
        objective=objective,
        policy_id=policy_id,
        caverns_live=caverns_live,
    )


def resolve_reshape_target(
    state_after_cast,
    context: SearchContext,
    search: SearchZoneObservation,
    action: ActionIntent,
) -> TransitionEnvelope:
    target = _target_from_action(action, context, search)
    return _finish_search(state_after_cast, context, target)


# ---------------------------------------------------------------------------
# Whir of Invention
# ---------------------------------------------------------------------------


def _whir_payment_plans(
    state, x: int
) -> Tuple[Tuple[Tuple[PermanentSlot, ...], int], ...]:
    """Return legal (improvise slots, floating generic paid) plans for fixed X."""
    if state.blue < 3:
        return ()
    reduction = solver.medallion_reduction(state, WHIR)
    need = max(0, int(x) - reduction)
    after_blue = solver.pay(state, 0, 3)
    if after_blue is None:
        return ()
    slots = _artifact_slots(after_blue, untapped_only=True)
    rows = []
    for k in range(0, min(need, len(slots)) + 1):
        floating = need - k
        if not solver.can_pay(after_blue, floating, 0):
            continue
        for combo in combinations(slots, k):
            rows.append((tuple(combo), floating))
    rows.sort(key=lambda row: (tuple(slot.key() for slot in row[0]), row[1]))
    return tuple(rows)


def whir_cast_intents(state) -> Tuple[ActionIntent, ...]:
    if WHIR not in state.hand or state.blue < 3:
        return ()
    reduction = solver.medallion_reduction(state, WHIR)
    after_blue = solver.pay(state, 0, 3)
    if after_blue is None:
        return ()
    max_x = (
        reduction
        + after_blue.blue
        + after_blue.colorless
        + len(_artifact_slots(after_blue, untapped_only=True))
    )
    rows = []
    serial = 0
    for x in range(max_x + 1):
        for slots, floating in _whir_payment_plans(state, x):
            rows.append(
                ActionIntent(
                    action_id=f"whir.cast.{serial:03d}",
                    kind="cast_whir",
                    parameters=(
                        ("x", x),
                        ("improvise", tuple(slot.key() for slot in slots)),
                        ("floating_generic", floating),
                    ),
                    equivalence_key=(
                        "whir",
                        x,
                        tuple(slot.key() for slot in slots),
                        floating,
                    ),
                    label=(
                        f"Cast Whir X={x}"
                        + (
                            "; improvise "
                            + ", ".join(slot.name or slot.mode for slot in slots)
                            if slots
                            else ""
                        )
                    ),
                    decision_stage=DECISION_COMMIT,
                    source=WHIR,
                )
            )
            serial += 1
    return tuple(rows)


def whir_cast_request(
    state,
    information: InformationState,
    *,
    horizon: int,
    objective: str = "win_by_horizon",
    policy_id: str = "base",
    caverns_live: Optional[bool] = None,
) -> DecisionRequest:
    return DecisionRequest(
        observation=make_policy_view(state, information, caverns_live=caverns_live),
        actions=whir_cast_intents(state),
        context=PolicyDecisionContext(
            horizon=horizon,
            objective=objective,
            policy_id=policy_id,
            decision_id="whir.cast",
            decision_stage=DECISION_COMMIT,
        ),
    )


def resolve_whir_cast(
    state, action: ActionIntent
) -> Tuple[TransitionEnvelope, SearchContext, SearchZoneObservation]:
    legal = {
        candidate.canonical_key(): candidate for candidate in whir_cast_intents(state)
    }
    if action.canonical_key() not in legal:
        raise ValueError("Whir cast action is not legal in current state")
    params = dict(action.parameters)
    x = int(params["x"])
    floating = int(params["floating_generic"])
    raw_slots = tuple(params["improvise"])
    slots = tuple(_slot_from_parameter(tuple(raw)) for raw in raw_slots)

    paid = solver.pay(state, 0, 3)
    if paid is None:
        raise ValueError("Whir colored cost could not be paid")
    for slot in slots:
        index = _slot_index(paid, slot)
        if paid.battlefield[index].tapped or not solver.is_artifact_perm(
            paid.battlefield[index]
        ):
            raise ValueError("committed improvise object is no longer legal")
        paid = solver.update_perm(paid, index, tapped=True)
    paid = solver.pay(paid, floating, 0)
    if paid is None:
        raise ValueError("Whir generic remainder could not be paid")
    paid = replace(
        paid,
        hand=solver.remove_one(paid.hand, WHIR),
        graveyard=paid.graveyard + (WHIR,),
        spell_cast_this_turn=True,
    )
    paid = solver.vfc_noncreature_cast_trigger(paid, WHIR)
    paid = solver.add_trace(
        paid, f"cast Whir X={x}; payment plan committed before search"
    )

    search = _artifact_search_event(paid, WHIR, x)
    context = SearchContext(WHIR, x, "whir.search.target", action.action_id)
    envelope = TransitionEnvelope(
        true_state=paid,
        observations=ObservationBatch((search,)),
        pending_decision=PendingDecisionSpec(
            decision_id=context.search_decision_id,
            kind=SEARCH_KIND,
            source=WHIR,
            decision_stage=DECISION_POST_OBSERVATION,
            contingent_on=action.action_id,
        ),
        trace_note=f"Whir search opened at committed X={x}",
    )
    return envelope, context, search


def whir_target_request(
    state_after_cast,
    information: InformationState,
    context: SearchContext,
    search: SearchZoneObservation,
    *,
    horizon: int,
    objective: str = "win_by_horizon",
    policy_id: str = "base",
    caverns_live: Optional[bool] = None,
) -> DecisionRequest:
    return _target_request(
        state_after_cast,
        information,
        context,
        search,
        horizon=horizon,
        objective=objective,
        policy_id=policy_id,
        caverns_live=caverns_live,
    )


def resolve_whir_target(
    state_after_cast,
    context: SearchContext,
    search: SearchZoneObservation,
    action: ActionIntent,
) -> TransitionEnvelope:
    target = _target_from_action(action, context, search)
    return _finish_search(state_after_cast, context, target)


def information_after_x_search_transition(
    prior: InformationState, envelope: TransitionEnvelope
) -> InformationState:
    return apply_observation_batch(prior, envelope.observations)
