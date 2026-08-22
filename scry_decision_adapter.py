#!/usr/bin/env python3
"""Phase-1 non-Oracle scry decision adapter.

This module stages scry as:

    commit to the scry source/effect
        -> RevealTopObservation(top N)
        -> post-observation choose top/bottom ordering
        -> apply the chosen physical library arrangement
        -> refresh continuous top-card look permission after scry completes

The adapter is intentionally effect-scoped.  It does not duplicate spell casting,
ETB, or trigger mechanics.  Phase 2's non-Oracle rules adapter will invoke this
staged scry effect after the actual source commitment is made through shared rules.
For Phase 1, the important invariant is that the commit action contains no hidden
card identities and that all top/bottom choices are generated only from legally
revealed InformationState.

Important rules boundary: cards being looked at for scry remain the top cards of
the library for rules purposes.  A Reality Chip / Fortune Teller's Talent look
permission does not reveal card N+1 while scry N is in progress.  If the scry
changes the physical top card, the continuous look permission refreshes only after
the scry placement is complete, before the next policy/priority decision.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
import itertools
from typing import Optional, Tuple

import urza_solver as solver
from solver_architecture import InformationState, make_policy_view
from information_state_propagation import _top_visible
from decision_observation import (
    ActionIntent,
    DECISION_COMMIT,
    DECISION_POST_OBSERVATION,
    DecisionRequest,
    LibraryPositionsObservation,
    ObservationBatch,
    PendingDecisionSpec,
    PolicyDecisionContext,
    RevealTopObservation,
    TransitionEnvelope,
    apply_observation_batch,
)

SCRY_CHOICE_KIND = "scry_choose_positions"


@dataclass(frozen=True)
class ScrySourceSpec:
    """Public description of one committed scry effect.

    ``commitment_id`` identifies the source commitment that created this scry
    window.  It is deliberately independent of the concrete hidden top cards.
    """

    source: str
    count: int
    commitment_id: str

    def __post_init__(self) -> None:
        if not self.source:
            raise ValueError("scry source must be non-empty")
        if self.count < 1:
            raise ValueError("scry count must be >= 1")
        if not self.commitment_id:
            raise ValueError("scry commitment_id must be non-empty")

    @property
    def commit_action_id(self) -> str:
        return f"scry.commit.{self.commitment_id}"

    @property
    def choice_decision_id(self) -> str:
        return f"scry.choose.{self.commitment_id}"


def scry_commit_intent(spec: ScrySourceSpec) -> ActionIntent:
    """Return a source/effect commitment that contains no hidden card identities."""
    return ActionIntent(
        action_id=spec.commit_action_id,
        kind="commit_scry_source",
        parameters=(("count", spec.count), ("source", spec.source)),
        equivalence_key=("scry_source", spec.source, spec.count),
        label=f"Commit {spec.source} scry {spec.count}",
        decision_stage=DECISION_COMMIT,
        source=spec.source,
    )


def scry_commit_request(
    state,
    information: InformationState,
    spec: ScrySourceSpec,
    *,
    horizon: int,
    objective: str = "win_by_horizon",
    policy_id: str = "base",
    caverns_live: Optional[bool] = None,
) -> DecisionRequest:
    """Build the pre-observation scry commitment request.

    Source-specific legality/cost is intentionally owned by the caller/rules
    adapter.  This request models only the information boundary of the scry effect.
    """
    return DecisionRequest(
        observation=make_policy_view(state, information, caverns_live=caverns_live),
        actions=(scry_commit_intent(spec),),
        context=PolicyDecisionContext(
            horizon=horizon,
            objective=objective,
            policy_id=policy_id,
            decision_id=f"scry.commit.{spec.commitment_id}",
            decision_stage=DECISION_COMMIT,
        ),
    )


def resolve_scry_commit(
    state,
    spec: ScrySourceSpec,
    action: ActionIntent,
) -> TransitionEnvelope:
    """After commitment, reveal exactly the concrete cards the scry may inspect."""
    expected = scry_commit_intent(spec)
    if action.canonical_key() != expected.canonical_key():
        raise ValueError("action is not the expected scry commitment")

    n = min(spec.count, len(state.library))
    revealed = tuple(state.library[:n])
    next_state = solver.add_trace(state, f"{spec.source}: commit scry {spec.count} -> look {n}")
    pending = None
    if n > 0:
        pending = PendingDecisionSpec(
            decision_id=spec.choice_decision_id,
            kind=SCRY_CHOICE_KIND,
            source=spec.source,
            decision_stage=DECISION_POST_OBSERVATION,
            contingent_on=spec.commit_action_id,
        )
    return TransitionEnvelope(
        true_state=next_state,
        observations=ObservationBatch(
            (RevealTopObservation(revealed, source=spec.source),) if n else ()
        ),
        pending_decision=pending,
        trace_note=f"{spec.source} revealed {n} scry card(s)",
    )


def information_after_scry_reveal(
    prior: InformationState,
    envelope: TransitionEnvelope,
) -> InformationState:
    return apply_observation_batch(prior, envelope.observations)


def _unique_scry_choices(cards: Tuple[str, ...]) -> Tuple[Tuple[Tuple[str, ...], Tuple[str, ...]], ...]:
    """Enumerate every unique legal (top_order, bottom_order) result.

    Any number of the looked-at cards may be put on the bottom.  Both groups may
    be ordered.  A permutation plus split point spans the complete legal set.
    """
    if not cards:
        return ()
    choices = set()
    for permutation in set(itertools.permutations(cards)):
        for split in range(len(cards) + 1):
            choices.add((tuple(permutation[:split]), tuple(permutation[split:])))
    return tuple(sorted(choices, key=repr))


def scry_choice_intents(
    information: InformationState,
    spec: ScrySourceSpec,
    *,
    revealed_count: Optional[int] = None,
) -> Tuple[ActionIntent, ...]:
    """Generate legal scry choices using only the revealed InformationState prefix."""
    n = spec.count if revealed_count is None else int(revealed_count)
    n = max(0, min(n, len(information.known_top)))
    cards = tuple(information.known_top[:n])
    out = []
    for index, (top_order, bottom_order) in enumerate(_unique_scry_choices(cards)):
        out.append(
            ActionIntent(
                action_id=f"{spec.choice_decision_id}.{index:02d}",
                kind=SCRY_CHOICE_KIND,
                parameters=(
                    ("bottom", tuple(bottom_order)),
                    ("revealed_count", n),
                    ("top", tuple(top_order)),
                ),
                equivalence_key=(SCRY_CHOICE_KIND, tuple(top_order), tuple(bottom_order)),
                label=(
                    "Scry top: " + (" | ".join(top_order) if top_order else "<none>")
                    + "; bottom: "
                    + (" | ".join(bottom_order) if bottom_order else "<none>")
                ),
                decision_stage=DECISION_POST_OBSERVATION,
                source=spec.source,
                contingent_on=spec.commit_action_id,
            )
        )
    return tuple(out)


def scry_choice_request(
    state_after_reveal,
    information_after_reveal: InformationState,
    spec: ScrySourceSpec,
    *,
    revealed_count: int,
    horizon: int,
    objective: str = "win_by_horizon",
    policy_id: str = "base",
    caverns_live: Optional[bool] = None,
) -> DecisionRequest:
    return DecisionRequest(
        observation=make_policy_view(
            state_after_reveal,
            information_after_reveal,
            caverns_live=caverns_live,
        ),
        actions=scry_choice_intents(
            information_after_reveal,
            spec,
            revealed_count=revealed_count,
        ),
        context=PolicyDecisionContext(
            horizon=horizon,
            objective=objective,
            policy_id=policy_id,
            decision_id=spec.choice_decision_id,
            decision_stage=DECISION_POST_OBSERVATION,
        ),
    )


def _choice_parameters(action: ActionIntent) -> Tuple[Tuple[str, ...], Tuple[str, ...], int]:
    params = dict(action.parameters)
    top = params.get("top")
    bottom = params.get("bottom")
    n = params.get("revealed_count")
    if not isinstance(top, tuple) or not isinstance(bottom, tuple) or not isinstance(n, int):
        raise ValueError("malformed scry choice parameters")
    return tuple(str(card) for card in top), tuple(str(card) for card in bottom), int(n)


def resolve_scry_choice(
    state_after_reveal,
    information_after_reveal: InformationState,
    spec: ScrySourceSpec,
    action: ActionIntent,
) -> TransitionEnvelope:
    """Apply the selected post-reveal scry arrangement to the concrete library."""
    if action.kind != SCRY_CHOICE_KIND or action.decision_stage != DECISION_POST_OBSERVATION:
        raise ValueError("scry choice must be a post-observation scry action")
    if action.contingent_on != spec.commit_action_id:
        raise ValueError("scry choice is not contingent on this scry commitment")

    top_order, bottom_order, n = _choice_parameters(action)
    legal = {
        candidate.canonical_key()
        for candidate in scry_choice_intents(
            information_after_reveal,
            spec,
            revealed_count=n,
        )
    }
    if action.canonical_key() not in legal:
        raise ValueError("scry choice was not generated from current legal information")

    concrete_revealed = tuple(state_after_reveal.library[:n])
    known_revealed = tuple(information_after_reveal.known_top[:n])
    if concrete_revealed != known_revealed:
        raise ValueError("InformationState known_top contradicts concrete scry reveal")
    if len(top_order) + len(bottom_order) != n:
        raise ValueError("scry choice does not account for every revealed card")
    if Counter(top_order + bottom_order) != Counter(concrete_revealed):
        raise ValueError("scry choice is not a rearrangement of the revealed cards")

    rest = tuple(state_after_reveal.library[n:])
    next_state = replace(
        state_after_reveal,
        library=tuple(top_order) + rest + tuple(bottom_order),
    )
    next_state = solver.add_trace(
        next_state,
        f"{spec.source}: scry choice top=[{', '.join(top_order)}] bottom=[{', '.join(bottom_order)}]",
    )

    # Any deeper prefix that was already legally known remains known immediately
    # below the cards kept on top.  Newly bottomed cards go below an older known
    # London/scry suffix, so bottom_mode='append'.
    deeper_known = tuple(information_after_reveal.known_top[n:])
    resulting_top = tuple(top_order) + deeper_known
    events = [
        LibraryPositionsObservation(
            known_top=resulting_top,
            known_bottom=tuple(bottom_order),
            top_mode="replace",
            bottom_mode="append",
            source=spec.source,
        )
    ]

    # Continuous look effects do not reveal the card underneath while the scry is
    # in progress.  Once the placement is complete, however, the physical top may
    # have changed (notably when all looked-at cards were bottomed).  Refresh that
    # now-known top before returning to the next policy/priority decision.
    if next_state.library and _top_visible(next_state):
        events.append(
            RevealTopObservation(
                (str(next_state.library[0]),),
                source=f"{spec.source} post-scry continuous look",
                preserve_known_deeper=True,
            )
        )

    return TransitionEnvelope(
        true_state=next_state,
        observations=ObservationBatch(tuple(events)),
        pending_decision=None,
        trace_note=f"{spec.source} scry positions committed",
    )


def information_after_scry_choice(
    prior: InformationState,
    envelope: TransitionEnvelope,
) -> InformationState:
    return apply_observation_batch(prior, envelope.observations)
