#!/usr/bin/env python3
"""Phase-1 non-Oracle decision / observation contracts.

This module is deliberately rules-neutral.  It creates the hard API boundary the
knowledge-constrained solver will use before any Monte-Carlo or Bellman evaluation
is allowed to make production decisions.

Key invariants:
- a policy decision object contains PolicyView, not Oracle State/TrueState;
- policy-facing context contains no root game seed;
- ActionIntent identity is deterministic and distinct from explicit strategic
  equivalence identity;
- observations are typed data rather than trace-string semantics;
- InformationState updates are pure reducers over typed observations;
- a rules-layer transition may carry concrete state internally, but the policy
  never receives that transition envelope directly.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any, Generic, Iterable, Optional, Sequence, Tuple, TypeAlias, TypeVar

from solver_architecture import InformationState, PolicyAction, PolicyView, stable_key


DECISION_OBSERVATION_VERSION = "urza-decision-observation-v1"
ACTION_INTENT_VERSION = "urza-action-intent-v1"
OBSERVATION_EVENT_VERSION = "urza-observation-event-v1"

DECISION_COMMIT = "commit"
DECISION_POST_OBSERVATION = "post_observation"
DECISION_MECHANICAL = "mechanical"
VALID_DECISION_STAGES = frozenset(
    {DECISION_COMMIT, DECISION_POST_OBSERVATION, DECISION_MECHANICAL}
)

TState = TypeVar("TState")


def _normalize_parameters(
    values: Iterable[Tuple[str, Any]],
) -> Tuple[Tuple[str, Any], ...]:
    return tuple(sorted(((str(key), value) for key, value in values), key=lambda kv: kv[0]))


@dataclass(frozen=True)
class ActionIntent:
    """Policy-facing commitment before rules resolution.

    ``decision_stage`` is explicit so an activation/cast decision can be distinct
    from a later contingent choice made after an observation.  ``contingent_on``
    links the later decision to the commitment/observation that created it without
    exposing the concrete hidden world.
    """

    action_id: str
    kind: str
    parameters: Tuple[Tuple[str, Any], ...] = ()
    equivalence_key: Tuple[Any, ...] = ()
    label: str = ""
    decision_stage: str = DECISION_COMMIT
    source: str = ""
    contingent_on: str = ""

    def __post_init__(self) -> None:
        if not self.action_id:
            raise ValueError("ActionIntent.action_id must be non-empty")
        if not self.kind:
            raise ValueError("ActionIntent.kind must be non-empty")
        if self.decision_stage not in VALID_DECISION_STAGES:
            raise ValueError(f"unknown decision stage {self.decision_stage!r}")
        names = [str(key) for key, _ in self.parameters]
        if len(names) != len(set(names)):
            raise ValueError("ActionIntent parameters must have unique names")

    def canonical_key(self) -> Tuple[Any, ...]:
        return stable_key(
            (
                self.kind,
                _normalize_parameters(self.parameters),
                self.action_id,
                self.decision_stage,
                self.source,
                self.contingent_on,
            ),
            version=ACTION_INTENT_VERSION,
        )

    def strategic_key(self) -> Tuple[Any, ...]:
        if self.equivalence_key:
            return stable_key(
                (self.decision_stage, self.kind, self.equivalence_key),
                version=ACTION_INTENT_VERSION,
            )
        return self.canonical_key()

    def as_policy_action(self) -> PolicyAction:
        """Compatibility bridge for architecture code that still uses PolicyAction."""
        return PolicyAction(
            action_id=self.action_id,
            kind=self.kind,
            parameters=_normalize_parameters(self.parameters),
            equivalence_key=self.equivalence_key,
            label=self.label,
        )


@dataclass(frozen=True)
class PolicyDecisionContext:
    """Policy-safe decision metadata.

    Deliberately excludes the root game seed.  A policy that needs stochastic
    sampling receives an isolated policy/tie RNG from its caller; it must never be
    able to reconstruct the actual game randomness tape from context.
    """

    horizon: int
    objective: str = "win_by_horizon"
    policy_id: str = "base"
    decision_id: str = ""
    decision_stage: str = DECISION_COMMIT

    def __post_init__(self) -> None:
        if self.horizon < 1:
            raise ValueError("horizon must be >= 1")
        if self.decision_stage not in VALID_DECISION_STAGES:
            raise ValueError(f"unknown decision stage {self.decision_stage!r}")


@dataclass(frozen=True)
class DecisionRequest:
    """Complete object a policy may inspect at one choice point."""

    observation: PolicyView
    actions: Tuple[ActionIntent, ...]
    context: PolicyDecisionContext

    def __post_init__(self) -> None:
        ids = [action.action_id for action in self.actions]
        if len(ids) != len(set(ids)):
            raise ValueError("DecisionRequest action ids must be unique")
        for action in self.actions:
            if action.decision_stage != self.context.decision_stage:
                raise ValueError(
                    "action decision stage does not match DecisionRequest context"
                )

    def canonical_key(self) -> Tuple[Any, ...]:
        return stable_key(
            (
                self.observation.key(),
                tuple(action.canonical_key() for action in self.actions),
                self.context,
            ),
            version=DECISION_OBSERVATION_VERSION,
        )


# ---------------------------------------------------------------------------
# Typed observation events
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DrawObservation:
    card: str
    source: str = "draw"


@dataclass(frozen=True)
class RevealTopObservation:
    cards: Tuple[str, ...]
    source: str = ""
    preserve_known_deeper: bool = True


@dataclass(frozen=True)
class SearchZoneObservation:
    """Ephemeral legal search information used to form a contingent decision.

    ``legal_cards`` is intentionally the legal choice set produced by the rules
    layer, not the raw hidden library permutation.  This event does not persist the
    whole searched library in InformationState after the search decision closes.
    """

    zone: str
    legal_cards: Tuple[str, ...]
    context: str
    may_fail_to_find: bool = False


@dataclass(frozen=True)
class ShuffleObservation:
    source: str = ""


@dataclass(frozen=True)
class MoveKnownCardObservation:
    card: str
    from_zone: str
    to_zone: str
    position: str = ""
    source: str = ""


@dataclass(frozen=True)
class LibraryPositionsObservation:
    """Commit the legally chosen known prefix/suffix after an ordering decision.

    ``bottom_mode='append'`` is used for scry bottoming when an older known-bottom
    suffix (for example London bottoms) remains below the newly moved cards.
    """

    known_top: Tuple[str, ...] = ()
    known_bottom: Tuple[str, ...] = ()
    top_mode: str = "replace"
    bottom_mode: str = "replace"
    source: str = ""

    def __post_init__(self) -> None:
        if self.top_mode not in {"replace", "preserve"}:
            raise ValueError(f"invalid top_mode {self.top_mode!r}")
        if self.bottom_mode not in {"replace", "append", "preserve"}:
            raise ValueError(f"invalid bottom_mode {self.bottom_mode!r}")


@dataclass(frozen=True)
class PublicZoneChangeObservation:
    card: str
    from_zone: str
    to_zone: str
    source: str = ""


@dataclass(frozen=True)
class EnvironmentObservation:
    event_kind: str
    parameters: Tuple[Tuple[str, Any], ...] = ()


ObservationEvent: TypeAlias = (
    DrawObservation
    | RevealTopObservation
    | SearchZoneObservation
    | ShuffleObservation
    | MoveKnownCardObservation
    | LibraryPositionsObservation
    | PublicZoneChangeObservation
    | EnvironmentObservation
)


def observation_event_key(event: ObservationEvent) -> Tuple[Any, ...]:
    return stable_key(event, version=OBSERVATION_EVENT_VERSION)


@dataclass(frozen=True)
class ObservationBatch:
    events: Tuple[ObservationEvent, ...] = ()

    def canonical_key(self) -> Tuple[Any, ...]:
        return stable_key(
            tuple(observation_event_key(event) for event in self.events),
            version=OBSERVATION_EVENT_VERSION,
        )


@dataclass(frozen=True)
class PendingDecisionSpec:
    """Rules-layer notice that a new policy choice is now legal."""

    decision_id: str
    kind: str
    source: str
    decision_stage: str = DECISION_POST_OBSERVATION
    contingent_on: str = ""

    def __post_init__(self) -> None:
        if not self.decision_id or not self.kind:
            raise ValueError("pending decision requires decision_id and kind")
        if self.decision_stage not in VALID_DECISION_STAGES:
            raise ValueError(f"unknown decision stage {self.decision_stage!r}")


@dataclass(frozen=True)
class TransitionEnvelope(Generic[TState]):
    """Internal rules-layer result; policies must not receive this object."""

    true_state: TState
    observations: ObservationBatch = ObservationBatch()
    pending_decision: Optional[PendingDecisionSpec] = None
    trace_note: str = ""


# ---------------------------------------------------------------------------
# Pure InformationState reducer
# ---------------------------------------------------------------------------


def _consume_known_top(info: InformationState, card: str) -> InformationState:
    if not info.known_top:
        return info
    if info.known_top[0] != card:
        raise ValueError(
            f"draw/move observed {card!r} but known top was {info.known_top[0]!r}"
        )
    return InformationState(
        known_top=tuple(info.known_top[1:]),
        known_bottom=info.known_bottom,
        known_library_counts=info.known_library_counts,
        shuffle_epoch=info.shuffle_epoch,
    )


def apply_observation_event(
    information: InformationState,
    event: ObservationEvent,
) -> InformationState:
    """Update persistent legal knowledge from one typed observation."""

    if isinstance(event, ShuffleObservation):
        return information.after_shuffle()

    if isinstance(event, DrawObservation):
        return _consume_known_top(information, event.card)

    if isinstance(event, RevealTopObservation):
        deeper: Tuple[str, ...] = ()
        if event.preserve_known_deeper and len(information.known_top) > len(event.cards):
            deeper = tuple(information.known_top[len(event.cards) :])
        return InformationState(
            known_top=tuple(event.cards) + deeper,
            known_bottom=information.known_bottom,
            known_library_counts=information.known_library_counts,
            shuffle_epoch=information.shuffle_epoch,
        )

    if isinstance(event, LibraryPositionsObservation):
        if event.top_mode == "replace":
            known_top = tuple(event.known_top)
        else:
            known_top = information.known_top

        if event.bottom_mode == "replace":
            known_bottom = tuple(event.known_bottom)
        elif event.bottom_mode == "append":
            known_bottom = tuple(information.known_bottom) + tuple(event.known_bottom)
        else:
            known_bottom = information.known_bottom

        return InformationState(
            known_top=known_top,
            known_bottom=known_bottom,
            known_library_counts=information.known_library_counts,
            shuffle_epoch=information.shuffle_epoch,
        )

    if isinstance(event, MoveKnownCardObservation):
        out = information
        if event.from_zone == "library" and event.position == "top":
            out = _consume_known_top(out, event.card)
        elif event.from_zone == "library" and event.position == "bottom":
            if out.known_bottom:
                if out.known_bottom[-1] != event.card:
                    raise ValueError(
                        f"bottom move observed {event.card!r} but known physical bottom was "
                        f"{out.known_bottom[-1]!r}"
                    )
                out = InformationState(
                    known_top=out.known_top,
                    known_bottom=tuple(out.known_bottom[:-1]),
                    known_library_counts=out.known_library_counts,
                    shuffle_epoch=out.shuffle_epoch,
                )

        if event.to_zone == "library" and event.position == "top":
            out = InformationState(
                known_top=(event.card,) + tuple(out.known_top),
                known_bottom=out.known_bottom,
                known_library_counts=out.known_library_counts,
                shuffle_epoch=out.shuffle_epoch,
            )
        elif event.to_zone == "library" and event.position == "bottom":
            out = InformationState(
                known_top=out.known_top,
                known_bottom=tuple(out.known_bottom) + (event.card,),
                known_library_counts=out.known_library_counts,
                shuffle_epoch=out.shuffle_epoch,
            )
        return out

    if isinstance(
        event,
        (SearchZoneObservation, PublicZoneChangeObservation, EnvironmentObservation),
    ):
        # These observations are either ephemeral decision information or public
        # facts already represented by PolicyView/true public zones.  They do not
        # by themselves create persistent hidden-position knowledge.
        return information

    raise TypeError(f"unsupported observation event {type(event)!r}")


def apply_observation_batch(
    information: InformationState,
    batch: ObservationBatch | Sequence[ObservationEvent],
) -> InformationState:
    events = batch.events if isinstance(batch, ObservationBatch) else tuple(batch)
    out = information
    for event in events:
        out = apply_observation_event(out, event)
    return out


def policy_surface_field_names() -> Tuple[str, ...]:
    """Audit helper for the Phase-1 hidden-information acceptance tests."""
    names = set()
    for cls in (ActionIntent, PolicyDecisionContext, DecisionRequest):
        names.update(field.name for field in fields(cls))
    return tuple(sorted(names))
