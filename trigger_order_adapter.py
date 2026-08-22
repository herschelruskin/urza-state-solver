#!/usr/bin/env python3
"""Phase-1 controlled-trigger ordering boundary.

A cast can create several simultaneous triggers we control.  In policy mode their
order may depend on information legally available *after casting is complete*.
That is especially important when Reality Chip or Fortune Teller's Talent lets us
look at the newly exposed library top after casting a card from the top.

The resulting trigger stack is a value-relevant public rules sidecar.  Phase 2
must resolve it one trigger at a time and return priority between resolutions;
new triggers created while resolving one trigger are stacked above the remaining
older triggers according to normal rules.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import itertools
from typing import Dict, Optional, Tuple

import urza_solver as solver
from solver_architecture import InformationState, make_policy_view
from decision_observation import (
    ActionIntent,
    DECISION_POST_OBSERVATION,
    DecisionRequest,
    MoveKnownCardObservation,
    ObservationBatch,
    PolicyDecisionContext,
    RevealTopObservation,
    apply_observation_batch,
)

TRIGGER_ORDER_KIND = "order_controlled_cast_triggers"


@dataclass(frozen=True, order=True)
class PendingTrigger:
    trigger_id: str
    kind: str
    source: str
    ordinal: int = 0
    payload: Tuple[Tuple[str, object], ...] = ()

    def key(self) -> Tuple[object, ...]:
        return (
            self.trigger_id,
            self.kind,
            self.source,
            self.ordinal,
            tuple(self.payload),
        )

    def strategic_key(self) -> Tuple[object, ...]:
        return (self.kind, self.source, tuple(self.payload))


@dataclass(frozen=True)
class TriggerBatch:
    triggers: Tuple[PendingTrigger, ...] = ()
    caused_by: str = ""

    def key(self) -> Tuple[object, ...]:
        return (
            "trigger-batch-v1",
            self.caused_by,
            tuple(trigger.key() for trigger in self.triggers),
        )


@dataclass(frozen=True)
class PendingTriggerStack:
    """Top-first resolution order for controlled triggers already on the stack."""

    triggers: Tuple[PendingTrigger, ...] = ()

    def key(self) -> Tuple[object, ...]:
        return (
            "pending-trigger-stack-v1",
            tuple(trigger.key() for trigger in self.triggers),
        )

    def strategic_key(self) -> Tuple[object, ...]:
        return (
            "pending-trigger-stack-strategic-v1",
            tuple(trigger.strategic_key() for trigger in self.triggers),
        )

    def next_trigger(self) -> Optional[PendingTrigger]:
        return self.triggers[0] if self.triggers else None

    def pop_next(self) -> Tuple[Optional[PendingTrigger], "PendingTriggerStack"]:
        if not self.triggers:
            return None, self
        return self.triggers[0], PendingTriggerStack(self.triggers[1:])

    def push_above(self, new_triggers: Tuple[PendingTrigger, ...]) -> "PendingTriggerStack":
        """Place newly stacked triggers above older unresolved ones."""
        return PendingTriggerStack(tuple(new_triggers) + self.triggers)


@dataclass(frozen=True)
class TriggerOrderResolution:
    stack: PendingTriggerStack
    chosen_action: Optional[ActionIntent] = None


def _has(state, name: str) -> bool:
    return any(getattr(perm, "name", "") == name for perm in state.battlefield)


def _is_creature_spell(card: str) -> bool:
    return card == solver.COMMANDER or card in solver.CREATURES


def _is_historic_spell(card: str) -> bool:
    return bool(
        card in solver.ARTIFACTS
        or card in solver.LEGENDARY_CREATURES
        or card in solver.PLANESWALKERS
        or card == "Urza's Saga"
    )


def _top_look_sources(state) -> Tuple[str, ...]:
    names = {str(getattr(perm, "name", "")) for perm in state.battlefield}
    return tuple(
        source
        for source in ("The Reality Chip", "Fortune Teller's Talent")
        if source in names
    )


def post_cast_observations(
    state_after_cast,
    cast_card: str,
    *,
    cast_from_library_top: bool = False,
) -> ObservationBatch:
    """Observations available after casting finishes, before trigger ordering.

    If the spell was cast from the top, consume that remembered top position first.
    Chip/FTT may then expose the *new* top before simultaneous triggers are stacked.
    """
    events = []
    if cast_from_library_top:
        events.append(
            MoveKnownCardObservation(
                str(cast_card),
                from_zone="library",
                to_zone="stack",
                position="top",
                source="cast from top",
            )
        )

    look_sources = _top_look_sources(state_after_cast)
    if look_sources and state_after_cast.library:
        events.append(
            RevealTopObservation(
                (str(state_after_cast.library[0]),),
                source=" + ".join(look_sources),
                preserve_known_deeper=True,
            )
        )
    return ObservationBatch(tuple(events))


def information_before_trigger_order(
    prior: InformationState,
    state_after_cast,
    cast_card: str,
    *,
    cast_from_library_top: bool = False,
) -> InformationState:
    return apply_observation_batch(
        prior,
        post_cast_observations(
            state_after_cast,
            cast_card,
            cast_from_library_top=cast_from_library_top,
        ),
    )


def collect_controlled_cast_triggers(
    state_after_cast,
    cast_card: str,
    *,
    mana_spent: int,
) -> TriggerBatch:
    """Collect current modeled triggers that fired from one completed cast."""
    rows = []
    serial = 0

    def add(kind: str, source: str, ordinal: int = 0, **payload):
        nonlocal serial
        rows.append(
            PendingTrigger(
                trigger_id=f"cast:{cast_card}:{serial}:{kind}:{ordinal}",
                kind=kind,
                source=source,
                ordinal=int(ordinal),
                payload=tuple(sorted(payload.items())),
            )
        )
        serial += 1

    if _has(state_after_cast, "Valley Floodcaller") and not _is_creature_spell(cast_card):
        add("vfc_noncreature_cast", "Valley Floodcaller")

    if _is_historic_spell(cast_card):
        assistants = sum(
            1
            for perm in state_after_cast.battlefield
            if getattr(perm, "name", "") == "Artificer's Assistant"
        )
        for ordinal in range(assistants):
            add("assistant_scry_1", "Artificer's Assistant", ordinal + 1)

    if cast_card in solver.ARTIFACTS:
        if _has(state_after_cast, "Uthros Research Craft") and state_after_cast.uthros_counters >= 3:
            add("uthros_draw_and_counter", "Uthros Research Craft")

        gadgets = sum(
            1
            for perm in state_after_cast.battlefield
            if getattr(perm, "name", "") == "Forensic Gadgeteer"
        )
        for ordinal in range(gadgets):
            add("gadgeteer_investigate", "Forensic Gadgeteer", ordinal + 1)

    if _has(state_after_cast, "Vexing Bauble") and int(mana_spent) == 0:
        add("vexing_bauble_counter", "Vexing Bauble")

    return TriggerBatch(tuple(rows), caused_by=str(cast_card))


def _unique_resolution_orders(batch: TriggerBatch) -> Tuple[Tuple[PendingTrigger, ...], ...]:
    """Enumerate unique strategic resolution orders while collapsing duplicates."""
    if len(batch.triggers) <= 1:
        return (batch.triggers,)

    # Permute strategic signatures so identical copies do not factorially explode.
    signatures = tuple(trigger.strategic_key() for trigger in batch.triggers)
    unique_signatures = sorted(set(itertools.permutations(signatures)), key=repr)

    by_signature: Dict[Tuple[object, ...], list[PendingTrigger]] = defaultdict(list)
    for trigger in batch.triggers:
        by_signature[trigger.strategic_key()].append(trigger)
    for group in by_signature.values():
        group.sort(key=lambda trigger: trigger.trigger_id)

    rows = []
    for signature_order in unique_signatures:
        offsets = Counter()
        concrete = []
        for signature in signature_order:
            index = offsets[signature]
            concrete.append(by_signature[signature][index])
            offsets[signature] += 1
        rows.append(tuple(concrete))
    return tuple(rows)


def trigger_order_intents(batch: TriggerBatch) -> Tuple[ActionIntent, ...]:
    if len(batch.triggers) <= 1:
        return ()
    rows = []
    for index, resolution_order in enumerate(_unique_resolution_orders(batch)):
        trigger_ids = tuple(trigger.trigger_id for trigger in resolution_order)
        strategic_order = tuple(trigger.strategic_key() for trigger in resolution_order)
        rows.append(
            ActionIntent(
                action_id=f"trigger.order.{index:03d}",
                kind=TRIGGER_ORDER_KIND,
                parameters=(("resolution_order", trigger_ids),),
                equivalence_key=(TRIGGER_ORDER_KIND, strategic_order),
                label="Resolve: " + " -> ".join(trigger.kind for trigger in resolution_order),
                decision_stage=DECISION_POST_OBSERVATION,
                source=batch.caused_by,
            )
        )
    return tuple(rows)


def trigger_order_request(
    state_after_cast,
    information: InformationState,
    batch: TriggerBatch,
    *,
    horizon: int,
    objective: str = "win_by_horizon",
    policy_id: str = "base",
    caverns_live=None,
) -> DecisionRequest:
    return DecisionRequest(
        observation=make_policy_view(
            state_after_cast, information, caverns_live=caverns_live
        ),
        actions=trigger_order_intents(batch),
        context=PolicyDecisionContext(
            horizon=horizon,
            objective=objective,
            policy_id=policy_id,
            decision_id=f"trigger.order.after.{batch.caused_by}",
            decision_stage=DECISION_POST_OBSERVATION,
        ),
    )


def resolve_trigger_order(
    batch: TriggerBatch,
    action: Optional[ActionIntent] = None,
) -> TriggerOrderResolution:
    if not batch.triggers:
        return TriggerOrderResolution(PendingTriggerStack(()), action)
    if len(batch.triggers) == 1:
        if action is not None:
            raise ValueError("single trigger requires no ordering decision")
        return TriggerOrderResolution(PendingTriggerStack(batch.triggers), None)

    if action is None:
        raise ValueError("multiple simultaneous triggers require an ordering action")
    legal = {candidate.canonical_key(): candidate for candidate in trigger_order_intents(batch)}
    if action.canonical_key() not in legal:
        raise ValueError("trigger ordering action is not legal for this batch")

    wanted = tuple(dict(action.parameters)["resolution_order"])
    by_id = {trigger.trigger_id: trigger for trigger in batch.triggers}
    if set(wanted) != set(by_id) or len(wanted) != len(batch.triggers):
        raise ValueError("trigger ordering action does not contain the exact batch")
    # The action stores top-first resolution order directly.
    stack = PendingTriggerStack(tuple(by_id[trigger_id] for trigger_id in wanted))
    return TriggerOrderResolution(stack, action)
