#!/usr/bin/env python3
"""Phase-2 information-faithful runtime kernel.

This module is the production bridge between the validated Magic mechanics and a
knowledge-constrained policy.  It deliberately does NOT call Oracle search to pick
future actions.  Only this rules layer may inspect the concrete hidden library;
policies receive RuntimePolicyView + ActionIntent objects only.

The first Phase-2 slice focuses on the sequencing that most easily causes strategy
fusion or rules leakage:

    committed artifact cast
      -> simultaneous controlled cast triggers
      -> explicit top-first runtime stack
      -> priority between resolutions
      -> artifact spell resolves
      -> simultaneous artifact-entry triggers
      -> priority between resolutions
      -> nested artifact creation / LTB triggers

Prized Statue is intentionally modeled both on entry and on dying.  Its Treasure
enters in a later event and therefore creates a NEW Station/Golem trigger wave.
Offer-style two-Treasure creation is represented as one simultaneous two-artifact
entry event, so each Station/Golem triggers twice from that event.

The module is intentionally not yet the complete 99-card action generator.  It is
the shared runtime substrate that Phase-1 Top/scry/tutor adapters and the upcoming
deterministic base policy plug into.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, replace
import itertools
from typing import Iterable, Optional, Tuple

import urza_solver as solver
from decision_observation import (
    ActionIntent,
    DECISION_MECHANICAL,
    DECISION_POST_OBSERVATION,
    DecisionRequest,
    PendingDecisionSpec,
    PolicyDecisionContext,
    apply_observation_batch,
)
from non_oracle_runtime_value_key import (
    RuntimeDecisionWindow,
    WINDOW_POST_OBSERVATION,
    WINDOW_PRIORITY,
    canonical_non_oracle_runtime_value_key,
)
from non_oracle_runtime_view import RuntimePolicyView, make_runtime_policy_view
from scry_decision_adapter import (
    ScrySourceSpec,
    information_after_scry_choice,
    information_after_scry_reveal,
    resolve_scry_choice,
    resolve_scry_commit,
    scry_choice_intents,
    scry_commit_intent,
)
from solver_architecture import InformationState, canonical_markov_state_key, stable_key
from trigger_order_adapter import collect_controlled_cast_triggers, post_cast_observations
from urza_permission_adapter import UrzaPermissionState

RUNTIME_STACK_VERSION = "urza-runtime-stack-v1"
RUNTIME_STATE_VERSION = "urza-non-oracle-runtime-v1"

STACK_TRIGGER = "trigger"
STACK_SPELL = "spell"

DECISION_STACK_ORDER = "runtime_stack_order"
DECISION_PRODUCER_UNTAP = "runtime_producer_untap"
DECISION_SCRY = "runtime_scry_choice"
DECISION_CHROME_IMPRINT = "runtime_chrome_imprint"

ACTION_PASS_PRIORITY = "runtime.pass_priority"


@dataclass(frozen=True, order=True)
class RuntimeStackObject:
    """One exact stack object plus its policy-safe/strategic projection."""

    object_id: str
    object_type: str
    kind: str
    source: str
    card: str = ""
    payload: Tuple[Tuple[str, object], ...] = ()
    public_payload: Tuple[Tuple[str, object], ...] = ()
    strategic_payload: Tuple[Tuple[str, object], ...] = ()

    def __post_init__(self) -> None:
        if self.object_type not in {STACK_TRIGGER, STACK_SPELL}:
            raise ValueError(f"invalid stack object type {self.object_type!r}")
        if not self.object_id or not self.kind:
            raise ValueError("runtime stack objects require object_id and kind")

    def key(self) -> Tuple[object, ...]:
        return stable_key(
            (
                self.object_id,
                self.object_type,
                self.kind,
                self.source,
                self.card,
                tuple(self.payload),
            ),
            version=RUNTIME_STACK_VERSION,
        )

    def strategic_key(self) -> Tuple[object, ...]:
        projected = self.strategic_payload or self.public_payload or self.payload
        return (
            self.object_type,
            self.kind,
            self.source,
            self.card,
            tuple(projected),
        )


@dataclass(frozen=True)
class RuntimeStack:
    """Top-first exact runtime stack.

    ``next_sequence`` is execution provenance and is excluded from strategic_key.
    """

    objects: Tuple[RuntimeStackObject, ...] = ()
    next_sequence: int = 0

    def key(self) -> Tuple[object, ...]:
        return (
            RUNTIME_STACK_VERSION,
            tuple(obj.key() for obj in self.objects),
            int(self.next_sequence),
        )

    def strategic_key(self) -> Tuple[object, ...]:
        return (
            "runtime-stack-strategic-v1",
            tuple(obj.strategic_key() for obj in self.objects),
        )

    def top(self) -> Optional[RuntimeStackObject]:
        return self.objects[0] if self.objects else None

    def pop_top(self) -> Tuple[Optional[RuntimeStackObject], "RuntimeStack"]:
        if not self.objects:
            return None, self
        return self.objects[0], RuntimeStack(self.objects[1:], self.next_sequence)

    def push_existing(self, objects: Iterable[RuntimeStackObject]) -> "RuntimeStack":
        rows = tuple(objects)
        return RuntimeStack(rows + self.objects, self.next_sequence)

    def allocate(
        self,
        *,
        object_type: str,
        kind: str,
        source: str,
        card: str = "",
        payload: Tuple[Tuple[str, object], ...] = (),
        public_payload: Tuple[Tuple[str, object], ...] = (),
        strategic_payload: Tuple[Tuple[str, object], ...] = (),
    ) -> Tuple[RuntimeStackObject, "RuntimeStack"]:
        seq = int(self.next_sequence)
        obj = RuntimeStackObject(
            object_id=f"runtime-stack:{seq}",
            object_type=object_type,
            kind=kind,
            source=source,
            card=card,
            payload=tuple(payload),
            public_payload=tuple(public_payload),
            strategic_payload=tuple(strategic_payload),
        )
        return obj, RuntimeStack(self.objects, seq + 1)


@dataclass(frozen=True)
class RuntimePendingDecision:
    spec: PendingDecisionSpec
    kind: str
    payload: Tuple[Tuple[str, object], ...] = ()


@dataclass(frozen=True)
class NonOracleRuntimeState:
    true_state: solver.State
    information: InformationState = InformationState()
    permissions: UrzaPermissionState = UrzaPermissionState()
    stack: RuntimeStack = RuntimeStack()
    window: RuntimeDecisionWindow = RuntimeDecisionWindow()
    pending: Optional[RuntimePendingDecision] = None

    def __post_init__(self) -> None:
        # Oracle's compact stack/permission fields must not silently coexist with
        # the Phase-2 typed runtime sidecars.  Keeping one authority prevents both
        # double resolution and accidental policy exposure of Oracle-only state.
        if getattr(self.true_state, "oracle_stack", ()):
            raise ValueError("Phase-2 runtime requires true_state.oracle_stack == ()")
        if getattr(self.true_state, "urza_exile_permissions", ()):
            raise ValueError(
                "Phase-2 runtime keeps Urza permissions in UrzaPermissionState, "
                "not true_state.urza_exile_permissions"
            )

    def policy_view(self, *, caverns_live=None) -> RuntimePolicyView:
        return make_runtime_policy_view(
            self.true_state,
            self.information,
            permissions=self.permissions,
            runtime_stack=self.stack,
            window=self.window,
            caverns_live=caverns_live,
        )

    def value_key(self, *, objective_memory=None) -> Tuple[object, ...]:
        return canonical_non_oracle_runtime_value_key(
            self.true_state,
            self.information,
            permissions=self.permissions,
            runtime_stack=self.stack,
            window=self.window,
            objective_memory=objective_memory,
        )


def make_runtime_state(
    true_state: solver.State,
    information: InformationState | None = None,
    *,
    permissions: UrzaPermissionState | None = None,
) -> NonOracleRuntimeState:
    """Create a clean Phase-2 runtime root and assign runtime-only permanent tags."""
    if true_state.oracle_stack:
        raise ValueError("cannot import an Oracle state with a live Oracle stack")
    if true_state.urza_exile_permissions:
        raise ValueError("migrate live Oracle permissions explicitly before Phase 2")
    tagged = solver._ensure_oracle_instance_tags(true_state)
    return NonOracleRuntimeState(
        true_state=tagged,
        information=information or InformationState(),
        permissions=permissions or UrzaPermissionState(),
    )


def _perm_public_signature(perm) -> Tuple[object, ...]:
    return (
        str(perm.name),
        bool(perm.tapped),
        bool(perm.sick),
        int(perm.counters),
        str(perm.mode),
        bool(perm.knack_granted),
        bool(perm.producer_urza_ready),
    )


def _perm_for_tag(state: solver.State, tag: int):
    return next((p for p in state.battlefield if int(p.instance_tag) == int(tag)), None)


def _perm_index_for_tag(state: solver.State, tag: int) -> Optional[int]:
    return next(
        (i for i, p in enumerate(state.battlefield) if int(p.instance_tag) == int(tag)),
        None,
    )


def _alloc_trigger(
    stack: RuntimeStack,
    *,
    kind: str,
    source: str,
    card: str = "",
    source_perm=None,
    payload: Tuple[Tuple[str, object], ...] = (),
    public_payload: Tuple[Tuple[str, object], ...] = (),
) -> Tuple[RuntimeStackObject, RuntimeStack]:
    exact = list(payload)
    public = list(public_payload)
    strategic = list(public_payload)
    if source_perm is not None:
        exact.append(("source_tag", int(source_perm.instance_tag)))
        signature = _perm_public_signature(source_perm)
        public.append(("source_state", signature))
        strategic.append(("source_state", signature))
    return stack.allocate(
        object_type=STACK_TRIGGER,
        kind=kind,
        source=source,
        card=card,
        payload=tuple(exact),
        public_payload=tuple(public),
        strategic_payload=tuple(strategic),
    )


def _unique_object_orders(
    objects: Tuple[RuntimeStackObject, ...],
) -> Tuple[Tuple[RuntimeStackObject, ...], ...]:
    if len(objects) <= 1:
        return (objects,)
    signatures = tuple(obj.strategic_key() for obj in objects)
    signature_orders = sorted(set(itertools.permutations(signatures)), key=repr)
    by_signature = defaultdict(list)
    for obj in objects:
        by_signature[obj.strategic_key()].append(obj)
    for group in by_signature.values():
        group.sort(key=lambda obj: obj.object_id)
    rows = []
    for order in signature_orders:
        offsets = Counter()
        concrete = []
        for signature in order:
            concrete.append(by_signature[signature][offsets[signature]])
            offsets[signature] += 1
        rows.append(tuple(concrete))
    return tuple(rows)


def _stack_order_intents(
    objects: Tuple[RuntimeStackObject, ...],
    *,
    source: str,
) -> Tuple[ActionIntent, ...]:
    rows = []
    for index, order in enumerate(_unique_object_orders(objects)):
        rows.append(
            ActionIntent(
                action_id=f"runtime.stack.order.{index:03d}",
                kind=DECISION_STACK_ORDER,
                parameters=(("object_ids", tuple(obj.object_id for obj in order)),),
                equivalence_key=(
                    DECISION_STACK_ORDER,
                    tuple(obj.strategic_key() for obj in order),
                ),
                label="Resolve: " + " -> ".join(obj.kind for obj in order),
                decision_stage=DECISION_POST_OBSERVATION,
                source=source,
            )
        )
    return tuple(rows)


def _queue_simultaneous_objects(
    runtime: NonOracleRuntimeState,
    objects: Tuple[RuntimeStackObject, ...],
    *,
    source: str,
) -> NonOracleRuntimeState:
    if not objects:
        return replace(runtime, window=RuntimeDecisionWindow(WINDOW_PRIORITY))
    if len(objects) == 1:
        return replace(
            runtime,
            stack=runtime.stack.push_existing(objects),
            window=RuntimeDecisionWindow(WINDOW_PRIORITY),
            pending=None,
        )
    spec = PendingDecisionSpec(
        decision_id=f"runtime.stack.order.after.{source}",
        kind=DECISION_STACK_ORDER,
        source=source,
        decision_stage=DECISION_POST_OBSERVATION,
        contingent_on=source,
    )
    return replace(
        runtime,
        pending=RuntimePendingDecision(
            spec=spec,
            kind=DECISION_STACK_ORDER,
            payload=(("objects", objects),),
        ),
        window=RuntimeDecisionWindow(WINDOW_POST_OBSERVATION),
    )


def _artifact_entry_trigger_objects(
    runtime: NonOracleRuntimeState,
    entered_cards: Tuple[str, ...],
) -> Tuple[Tuple[RuntimeStackObject, ...], RuntimeStack]:
    """Collect controlled triggers from ONE simultaneous artifact-entry event."""
    state = solver._ensure_oracle_instance_tags(runtime.true_state)
    stack = runtime.stack
    objects = []

    # Each producer/Tezzeret triggers once for each artifact in the event.
    for perm in state.battlefield:
        if perm.name == "Tezzeret, Cruel Captain":
            for _ in entered_cards:
                obj, stack = _alloc_trigger(
                    stack,
                    kind="etb_tezz",
                    source=perm.name,
                    card=" + ".join(entered_cards),
                    source_perm=perm,
                )
                objects.append(obj)
    for perm in state.battlefield:
        if perm.name in {"Grinding Station", "Battered Golem"}:
            for _ in entered_cards:
                obj, stack = _alloc_trigger(
                    stack,
                    kind="etb_producer",
                    source=perm.name,
                    card=" + ".join(entered_cards),
                    source_perm=perm,
                )
                objects.append(obj)

    # Abilities of the newly-entered artifact(s).
    for card in entered_cards:
        if card in {"Witching Well", "Giant's Boulder"}:
            obj, stack = _alloc_trigger(
                stack,
                kind="etb_scry_2",
                source=card,
                card=card,
                public_payload=(("count", 2),),
            )
            objects.append(obj)
        elif card == "Prized Statue":
            obj, stack = _alloc_trigger(
                stack,
                kind="prized_entry_treasure",
                source=card,
                card=card,
            )
            objects.append(obj)
        elif card == "Chrome Mox":
            chrome = next(
                (p for p in reversed(state.battlefield)
                 if p.name == "Chrome Mox" and p.mode != "imprinted"),
                None,
            )
            obj, stack = _alloc_trigger(
                stack,
                kind="chrome_imprint",
                source=card,
                card=card,
                source_perm=chrome,
            )
            objects.append(obj)
        elif card == "Sewer-veillance Cam":
            # Cam targets when the trigger is put on the stack.  That target-choice
            # boundary is the next Phase-2 adapter slice; do not silently move the
            # choice to resolution.
            raise NotImplementedError(
                "Phase-2 Cam ETB target selection must be staged before stack ordering"
            )

    return tuple(objects), stack


def record_artifact_entry(
    runtime: NonOracleRuntimeState,
    entered_cards: Iterable[str],
    *,
    source: str = "artifact entry",
) -> NonOracleRuntimeState:
    """Record one simultaneous artifact-entry event and expose legal trigger order."""
    cards = tuple(str(card) for card in entered_cards)
    if not cards:
        return runtime
    tagged = solver._ensure_oracle_instance_tags(runtime.true_state)
    runtime = replace(runtime, true_state=tagged)
    objects, allocated_stack = _artifact_entry_trigger_objects(runtime, cards)
    runtime = replace(runtime, stack=allocated_stack)
    return _queue_simultaneous_objects(runtime, objects, source=source)


def add_artifact_tokens(
    runtime: NonOracleRuntimeState,
    cards: Iterable[str],
    *,
    modes: Optional[Iterable[str]] = None,
    source: str,
) -> NonOracleRuntimeState:
    """Add artifact tokens, then record their ONE simultaneous entry event."""
    cards = tuple(str(card) for card in cards)
    mode_rows = tuple(modes) if modes is not None else tuple(card.lower() for card in cards)
    if len(mode_rows) != len(cards):
        raise ValueError("token cards/modes length mismatch")
    state = runtime.true_state
    for card, mode in zip(cards, mode_rows):
        state = solver.add_perm(state, card, mode=str(mode))
    runtime = replace(runtime, true_state=solver._ensure_oracle_instance_tags(state))
    return record_artifact_entry(runtime, cards, source=source)


def _cast_trigger_objects(
    runtime: NonOracleRuntimeState,
    card: str,
    mana_spent: int,
    spell_object_id: str,
) -> Tuple[Tuple[RuntimeStackObject, ...], RuntimeStack]:
    batch = collect_controlled_cast_triggers(
        runtime.true_state,
        card,
        mana_spent=int(mana_spent),
    )
    stack = runtime.stack
    objects = []
    for trigger in batch.triggers:
        payload = tuple(trigger.payload)
        public_payload = tuple(trigger.payload)
        if trigger.kind == "vexing_bauble_counter":
            payload = payload + (("spell_object_id", spell_object_id),)
            public_payload = public_payload + (("target_spell", card),)
        obj, stack = _alloc_trigger(
            stack,
            kind=trigger.kind,
            source=trigger.source,
            card=card,
            payload=payload,
            public_payload=public_payload,
        )
        objects.append(obj)
    return tuple(objects), stack


def begin_committed_artifact_cast(
    runtime: NonOracleRuntimeState,
    card: str,
    *,
    mana_spent: int,
    from_zone: str = "hand",
    cast_from_library_top: bool = False,
) -> NonOracleRuntimeState:
    """Move a PRE-COMMITTED ordinary artifact spell to the runtime stack.

    Cost/payment choice belongs to the caller.  This function intentionally starts
    after that commitment so hidden information cannot influence whether/how the
    cast was paid.  Special replacement/cast cases (Mox Diamond, Chalice) remain
    separate adapters.
    """
    if card in {"Mox Diamond", "Everflowing Chalice"}:
        raise NotImplementedError(f"{card} requires its dedicated Phase-2 cast adapter")

    state = runtime.true_state
    if from_zone == "hand":
        if card not in state.hand:
            raise ValueError(f"{card!r} is not in hand")
        state = replace(state, hand=solver.remove_one(state.hand, card))
    elif from_zone == "library_top":
        if not state.library or state.library[0] != card:
            raise ValueError(f"{card!r} is not the concrete library top")
        state = replace(state, library=tuple(state.library[1:]))
        cast_from_library_top = True
    elif from_zone == "exile":
        if card not in state.exile:
            raise ValueError(f"{card!r} is not in exile")
        exile = list(state.exile); exile.remove(card)
        state = replace(state, exile=tuple(exile))
    else:
        raise ValueError(f"unsupported cast source zone {from_zone!r}")

    state = replace(state, spell_cast_this_turn=True)
    runtime = replace(runtime, true_state=state)

    # The spell is above the older stack. Its simultaneous cast triggers will be
    # ordered above the spell after post-cast observations are applied.
    spell, stack = runtime.stack.allocate(
        object_type=STACK_SPELL,
        kind="artifact_spell",
        source=from_zone,
        card=card,
        payload=(("mana_spent", int(mana_spent)),),
        public_payload=(("mana_spent", int(mana_spent)),),
        strategic_payload=(("mana_spent", int(mana_spent)),),
    )
    stack = stack.push_existing((spell,))
    runtime = replace(runtime, stack=stack)

    info = apply_observation_batch(
        runtime.information,
        post_cast_observations(
            state,
            card,
            cast_from_library_top=cast_from_library_top,
        ),
    )
    runtime = replace(runtime, information=info)

    triggers, allocated = _cast_trigger_objects(
        runtime,
        card,
        int(mana_spent),
        spell.object_id,
    )
    runtime = replace(runtime, stack=allocated)
    return _queue_simultaneous_objects(runtime, triggers, source=f"cast {card}")


def _producer_choice_actions(obj: RuntimeStackObject, can_untap: bool) -> Tuple[ActionIntent, ...]:
    rows = [
        ActionIntent(
            action_id=f"{obj.object_id}.producer.decline",
            kind=DECISION_PRODUCER_UNTAP,
            parameters=(("choice", "decline"), ("stack_object_id", obj.object_id)),
            equivalence_key=(DECISION_PRODUCER_UNTAP, "decline", obj.strategic_key()),
            label=f"Decline {obj.source} untap",
            decision_stage=DECISION_MECHANICAL,
            source=obj.source,
        )
    ]
    if can_untap:
        rows.append(
            ActionIntent(
                action_id=f"{obj.object_id}.producer.untap",
                kind=DECISION_PRODUCER_UNTAP,
                parameters=(("choice", "untap"), ("stack_object_id", obj.object_id)),
                equivalence_key=(DECISION_PRODUCER_UNTAP, "untap", obj.strategic_key()),
                label=f"Untap {obj.source}",
                decision_stage=DECISION_MECHANICAL,
                source=obj.source,
            )
        )
    return tuple(rows)


def _chrome_imprint_actions(runtime: NonOracleRuntimeState, obj: RuntimeStackObject) -> Tuple[ActionIntent, ...]:
    rows = [
        ActionIntent(
            action_id=f"{obj.object_id}.chrome.no_imprint",
            kind=DECISION_CHROME_IMPRINT,
            parameters=(("card", ""), ("stack_object_id", obj.object_id)),
            equivalence_key=(DECISION_CHROME_IMPRINT, ""),
            label="Chrome Mox: no imprint",
            decision_stage=DECISION_MECHANICAL,
            source="Chrome Mox",
        )
    ]
    for card in sorted(set(runtime.true_state.hand)):
        if card not in solver.BLUE_NONARTIFACT_FRONT:
            continue
        rows.append(
            ActionIntent(
                action_id=f"{obj.object_id}.chrome.imprint.{card}",
                kind=DECISION_CHROME_IMPRINT,
                parameters=(("card", card), ("stack_object_id", obj.object_id)),
                equivalence_key=(DECISION_CHROME_IMPRINT, card),
                label=f"Chrome Mox: imprint {card}",
                decision_stage=DECISION_MECHANICAL,
                source="Chrome Mox",
            )
        )
    return tuple(rows)


def runtime_decision_request(
    runtime: NonOracleRuntimeState,
    *,
    horizon: int,
    objective: str = "win_by_horizon",
    policy_id: str = "base-v1",
    caverns_live=None,
) -> DecisionRequest:
    """Return the current policy-safe request.  No raw State is included."""
    view = runtime.policy_view(caverns_live=caverns_live)

    if runtime.pending is not None:
        pending = runtime.pending
        data = dict(pending.payload)
        if pending.kind == DECISION_STACK_ORDER:
            actions = _stack_order_intents(
                tuple(data["objects"]),
                source=pending.spec.source,
            )
        elif pending.kind == DECISION_PRODUCER_UNTAP:
            obj = data["object"]
            actions = _producer_choice_actions(obj, bool(data["can_untap"]))
        elif pending.kind == DECISION_SCRY:
            spec = data["scry_spec"]
            actions = scry_choice_intents(
                runtime.information,
                spec,
                revealed_count=int(data["revealed_count"]),
            )
        elif pending.kind == DECISION_CHROME_IMPRINT:
            actions = _chrome_imprint_actions(runtime, data["object"])
        else:
            raise AssertionError(f"unknown runtime pending decision {pending.kind!r}")
        return DecisionRequest(
            observation=view,
            actions=tuple(actions),
            context=PolicyDecisionContext(
                horizon=horizon,
                objective=objective,
                policy_id=policy_id,
                decision_id=pending.spec.decision_id,
                decision_stage=pending.spec.decision_stage,
            ),
        )

    actions = ()
    if runtime.stack.objects and runtime.window.kind == WINDOW_PRIORITY:
        actions = (
            ActionIntent(
                action_id=ACTION_PASS_PRIORITY,
                kind="pass_priority",
                equivalence_key=("pass_priority", runtime.stack.objects[0].strategic_key()),
                label="Pass priority / resolve top stack object",
                decision_stage=DECISION_MECHANICAL,
                source="runtime stack",
            ),
        )
    return DecisionRequest(
        observation=view,
        actions=actions,
        context=PolicyDecisionContext(
            horizon=horizon,
            objective=objective,
            policy_id=policy_id,
            decision_id="runtime.priority" if actions else "runtime.no_choice",
            decision_stage=DECISION_MECHANICAL,
        ),
    )


def _resolve_scry_trigger(
    runtime: NonOracleRuntimeState,
    obj: RuntimeStackObject,
    count: int,
) -> NonOracleRuntimeState:
    spec = ScrySourceSpec(
        source=obj.source,
        count=int(count),
        commitment_id=obj.object_id.replace(":", "."),
    )
    envelope = resolve_scry_commit(
        runtime.true_state,
        spec,
        scry_commit_intent(spec),
    )
    info = information_after_scry_reveal(runtime.information, envelope)
    runtime = replace(runtime, true_state=envelope.true_state, information=info)
    if envelope.pending_decision is None:
        return replace(runtime, window=RuntimeDecisionWindow(WINDOW_PRIORITY))
    revealed_count = min(count, len(runtime.true_state.library))
    return replace(
        runtime,
        pending=RuntimePendingDecision(
            spec=envelope.pending_decision,
            kind=DECISION_SCRY,
            payload=(("scry_spec", spec), ("revealed_count", revealed_count)),
        ),
        window=RuntimeDecisionWindow(WINDOW_POST_OBSERVATION),
    )


def _resolve_runtime_stack_top(runtime: NonOracleRuntimeState) -> NonOracleRuntimeState:
    obj, remaining = runtime.stack.pop_top()
    if obj is None:
        return replace(runtime, window=RuntimeDecisionWindow(WINDOW_PRIORITY))
    runtime = replace(runtime, stack=remaining)
    state = runtime.true_state
    params = dict(obj.payload)

    if obj.object_type == STACK_SPELL:
        if obj.kind != "artifact_spell":
            raise NotImplementedError(f"unsupported runtime spell kind {obj.kind!r}")
        card = obj.card
        state = solver.add_perm(state, card, sick=card in solver.CREATURES)
        if card == "Uthros Research Craft":
            state = replace(state, uthros_counters=0)
        if card == "The One Ring":
            state = replace(state, ring_counters=0)
        state = solver.add_trace(state, f"Phase2 resolve artifact spell {card}")
        runtime = replace(runtime, true_state=solver._ensure_oracle_instance_tags(state))
        return record_artifact_entry(runtime, (card,), source=f"resolve {card}")

    if obj.kind in {"assistant_scry_1"}:
        return _resolve_scry_trigger(runtime, obj, 1)
    if obj.kind == "etb_scry_2":
        return _resolve_scry_trigger(runtime, obj, 2)

    if obj.kind == "vfc_noncreature_cast":
        state = solver._resolve_vfc_trigger_already_on_stack(state)
        return replace(
            runtime,
            true_state=state,
            window=RuntimeDecisionWindow(WINDOW_PRIORITY),
        )

    if obj.kind == "uthros_draw_and_counter":
        if state.library:
            state, drawn = solver.draw_from_library(state, 1)
            if solver.has(state, "Uthros Research Craft"):
                state = replace(state, uthros_counters=state.uthros_counters + 1)
            from decision_observation import DrawObservation, ObservationBatch
            info = apply_observation_batch(
                runtime.information,
                ObservationBatch((DrawObservation(str(drawn[0]), source="Uthros"),)),
            )
            state = solver.add_trace(state, f"Phase2 Uthros draws {drawn[0]}")
            runtime = replace(runtime, true_state=state, information=info)
        return replace(runtime, window=RuntimeDecisionWindow(WINDOW_PRIORITY))

    if obj.kind == "gadgeteer_investigate":
        runtime = add_artifact_tokens(
            runtime,
            ("Clue",),
            modes=("clue",),
            source="Gadgeteer investigate",
        )
        return runtime

    if obj.kind == "vexing_bauble_counter":
        target_id = str(params.get("spell_object_id", ""))
        target = next((x for x in runtime.stack.objects if x.object_id == target_id), None)
        if target is None:
            return replace(runtime, window=RuntimeDecisionWindow(WINDOW_PRIORITY))
        objects = tuple(x for x in runtime.stack.objects if x.object_id != target_id)
        state = replace(state, graveyard=state.graveyard + (target.card,))
        state = solver.add_trace(state, f"Phase2 Vexing Bauble counters {target.card}")
        return replace(
            runtime,
            true_state=state,
            stack=RuntimeStack(objects, runtime.stack.next_sequence),
            window=RuntimeDecisionWindow(WINDOW_PRIORITY),
        )

    if obj.kind == "etb_tezz":
        tag = int(params["source_tag"])
        idx = _perm_index_for_tag(state, tag)
        if idx is not None and state.battlefield[idx].name == "Tezzeret, Cruel Captain":
            state = solver.update_perm(
                state,
                idx,
                counters=state.battlefield[idx].counters + 1,
            )
        return replace(runtime, true_state=state, window=RuntimeDecisionWindow(WINDOW_PRIORITY))

    if obj.kind == "etb_producer":
        tag = int(params["source_tag"])
        perm = _perm_for_tag(state, tag)
        if perm is None or perm.name not in {"Grinding Station", "Battered Golem"}:
            return replace(runtime, window=RuntimeDecisionWindow(WINDOW_PRIORITY))
        if not perm.tapped:
            # Untapping an already-untapped permanent is physically a no-op, so
            # declining and choosing to untap are strategically equivalent here.
            return replace(runtime, window=RuntimeDecisionWindow(WINDOW_PRIORITY))
        pending = PendingDecisionSpec(
            decision_id=f"{obj.object_id}.producer_untap",
            kind=DECISION_PRODUCER_UNTAP,
            source=perm.name,
            decision_stage=DECISION_MECHANICAL,
            contingent_on=obj.object_id,
        )
        return replace(
            runtime,
            pending=RuntimePendingDecision(
                pending,
                DECISION_PRODUCER_UNTAP,
                (("object", obj), ("can_untap", True)),
            ),
            window=RuntimeDecisionWindow(WINDOW_POST_OBSERVATION),
        )

    if obj.kind in {"prized_entry_treasure", "prized_dies_treasure"}:
        return add_artifact_tokens(
            runtime,
            ("Treasure",),
            modes=("treasure",),
            source=obj.kind,
        )

    if obj.kind == "chrome_imprint":
        pending = PendingDecisionSpec(
            decision_id=f"{obj.object_id}.chrome_imprint",
            kind=DECISION_CHROME_IMPRINT,
            source="Chrome Mox",
            decision_stage=DECISION_MECHANICAL,
            contingent_on=obj.object_id,
        )
        return replace(
            runtime,
            pending=RuntimePendingDecision(
                pending,
                DECISION_CHROME_IMPRINT,
                (("object", obj),),
            ),
            window=RuntimeDecisionWindow(WINDOW_POST_OBSERVATION),
        )

    raise NotImplementedError(f"unsupported Phase-2 stack trigger {obj.kind!r}")


def _apply_pending_action(
    runtime: NonOracleRuntimeState,
    action: ActionIntent,
) -> NonOracleRuntimeState:
    pending = runtime.pending
    if pending is None:
        raise ValueError("no pending runtime decision")
    request = runtime_decision_request(runtime, horizon=max(1, int(runtime.true_state.turn)))
    legal = {candidate.canonical_key(): candidate for candidate in request.actions}
    if action.canonical_key() not in legal:
        raise ValueError("action is not legal for the current runtime decision")
    data = dict(pending.payload)

    if pending.kind == DECISION_STACK_ORDER:
        objects = tuple(data["objects"])
        by_id = {obj.object_id: obj for obj in objects}
        wanted = tuple(dict(action.parameters)["object_ids"])
        if len(wanted) != len(objects) or set(wanted) != set(by_id):
            raise ValueError("stack ordering action does not contain the exact batch")
        ordered = tuple(by_id[object_id] for object_id in wanted)
        return replace(
            runtime,
            stack=runtime.stack.push_existing(ordered),
            pending=None,
            window=RuntimeDecisionWindow(WINDOW_PRIORITY),
        )

    if pending.kind == DECISION_PRODUCER_UNTAP:
        obj = data["object"]
        choice = str(dict(action.parameters)["choice"])
        state = runtime.true_state
        if choice == "untap":
            tag = int(dict(obj.payload)["source_tag"])
            idx = _perm_index_for_tag(state, tag)
            if idx is not None:
                state = solver.update_perm(state, idx, tapped=False, producer_urza_ready=False)
                state = solver.add_trace(state, f"Phase2 {obj.source} ETB untaps")
        elif choice != "decline":
            raise ValueError(f"unknown producer choice {choice!r}")
        return replace(
            runtime,
            true_state=state,
            pending=None,
            window=RuntimeDecisionWindow(WINDOW_PRIORITY),
        )

    if pending.kind == DECISION_SCRY:
        spec = data["scry_spec"]
        envelope = resolve_scry_choice(
            runtime.true_state,
            runtime.information,
            spec,
            action,
        )
        info = information_after_scry_choice(runtime.information, envelope)
        return replace(
            runtime,
            true_state=envelope.true_state,
            information=info,
            pending=None,
            window=RuntimeDecisionWindow(WINDOW_PRIORITY),
        )

    if pending.kind == DECISION_CHROME_IMPRINT:
        obj = data["object"]
        chosen = str(dict(action.parameters)["card"])
        state = runtime.true_state
        if chosen:
            if chosen not in state.hand or chosen not in solver.BLUE_NONARTIFACT_FRONT:
                raise ValueError("illegal Chrome Mox imprint choice")
            state = replace(
                state,
                hand=solver.remove_one(state.hand, chosen),
                exile=state.exile + (chosen,),
            )
            tag = int(dict(obj.payload).get("source_tag", 0))
            idx = _perm_index_for_tag(state, tag)
            if idx is None:
                raise ValueError("Chrome Mox source disappeared before imprint resolution")
            state = solver.update_perm(state, idx, mode="imprinted")
            state = solver.add_trace(state, f"Phase2 Chrome Mox imprints {chosen}")
        else:
            state = solver.add_trace(state, "Phase2 Chrome Mox no imprint")
        return replace(
            runtime,
            true_state=state,
            pending=None,
            window=RuntimeDecisionWindow(WINDOW_PRIORITY),
        )

    raise AssertionError(f"unknown pending decision {pending.kind!r}")


def apply_runtime_action(
    runtime: NonOracleRuntimeState,
    action: ActionIntent,
) -> NonOracleRuntimeState:
    """Apply one policy-selected runtime action without ever passing raw State to policy."""
    if runtime.pending is not None:
        return _apply_pending_action(runtime, action)
    if action.action_id != ACTION_PASS_PRIORITY or action.kind != "pass_priority":
        raise ValueError("only pass/resolve is currently legal in this priority slice")
    if not runtime.stack.objects:
        raise ValueError("cannot pass to resolve an empty runtime stack")
    return _resolve_runtime_stack_top(runtime)


def sacrifice_permanent(
    runtime: NonOracleRuntimeState,
    *,
    instance_tag: int,
    source: str,
    to_graveyard: bool = True,
) -> NonOracleRuntimeState:
    """Phase-2 mechanical sacrifice/move with LTB triggers staged separately.

    Bay/Reshape/Transmute should call this shared helper rather than Oracle
    ``remove_perm()``, because Oracle's legacy helper may resolve LTB consequences
    immediately.  Here Prized Statue dying creates a REAL pending trigger; its
    Treasure does not exist until that trigger resolves, and the Treasure's entry
    then creates a fresh producer-trigger wave.
    """
    state = runtime.true_state
    idx = _perm_index_for_tag(state, int(instance_tag))
    if idx is None:
        raise ValueError(f"no permanent with runtime tag {instance_tag}")
    perm = state.battlefield[idx]
    battlefield = state.battlefield[:idx] + state.battlefield[idx + 1 :]
    graveyard = state.graveyard
    is_token = perm.mode in {"clue", "construct", "treasure"}
    if to_graveyard and not is_token:
        graveyard = graveyard + (perm.name,)
    state = replace(state, battlefield=battlefield, graveyard=graveyard)
    state = solver.add_trace(state, f"Phase2 {source} sacrifices {perm.name or perm.mode}")
    runtime = replace(runtime, true_state=state)

    triggers = []
    stack = runtime.stack
    if perm.name == "Prized Statue" and to_graveyard:
        obj, stack = _alloc_trigger(
            stack,
            kind="prized_dies_treasure",
            source="Prized Statue",
            card="Prized Statue",
        )
        triggers.append(obj)
    if perm.name == "Sewer-veillance Cam":
        raise NotImplementedError(
            "Phase-2 Cam LTB target selection must be staged before stack ordering"
        )
    runtime = replace(runtime, stack=stack)
    return _queue_simultaneous_objects(runtime, tuple(triggers), source=f"{source} LTB")
