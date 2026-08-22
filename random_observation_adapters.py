#!/usr/bin/env python3
"""Phase-1 staged adapter for random/reveal choices outside tutor/search effects.

Cephalid Coliseum threshold is represented as:

    commit activation / pay costs / sacrifice
        -> draw observations
        -> post-observation discard decision

Urza's {5} ability used to live in this module, but its permission is not an
immediate post-spin choice.  It is now modeled correctly as a persistent
until-end-of-turn public rules resource in ``urza_permission_adapter.py``.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from itertools import combinations
from typing import Optional, Tuple

import urza_solver as solver
from solver_architecture import InformationState, make_policy_view
from decision_observation import (
    ActionIntent,
    DECISION_COMMIT,
    DECISION_POST_OBSERVATION,
    DecisionRequest,
    DrawObservation,
    ObservationBatch,
    PendingDecisionSpec,
    PolicyDecisionContext,
    TransitionEnvelope,
    apply_observation_batch,
)

COLISEUM = "Cephalid Coliseum"
COLISEUM_ACTION_ID = "coliseum.threshold.activate"
COLISEUM_DISCARD_DECISION_ID = "coliseum.threshold.discard"


def _coliseum_index(state) -> Optional[int]:
    for index, perm in enumerate(state.battlefield):
        if perm.name == COLISEUM and not perm.tapped:
            return index
    return None


def coliseum_threshold_intents(state) -> Tuple[ActionIntent, ...]:
    index = _coliseum_index(state)
    if index is None or len(state.graveyard) < 7 or not solver.can_pay(state, 0, 1):
        return ()
    return (
        ActionIntent(
            action_id=COLISEUM_ACTION_ID,
            kind="activate_coliseum_threshold",
            parameters=(("blue_cost", 1),),
            equivalence_key=("coliseum_threshold",),
            label="Cephalid Coliseum: draw 3, discard 3",
            decision_stage=DECISION_COMMIT,
            source=COLISEUM,
        ),
    )


def coliseum_threshold_request(
    state,
    information: InformationState,
    *,
    horizon: int,
    objective: str = "win_by_horizon",
    policy_id: str = "base",
    caverns_live=None,
) -> DecisionRequest:
    return DecisionRequest(
        observation=make_policy_view(state, information, caverns_live=caverns_live),
        actions=coliseum_threshold_intents(state),
        context=PolicyDecisionContext(
            horizon=horizon,
            objective=objective,
            policy_id=policy_id,
            decision_id="coliseum.threshold.activation",
            decision_stage=DECISION_COMMIT,
        ),
    )


def resolve_coliseum_threshold(state, action: ActionIntent) -> TransitionEnvelope:
    legal = {
        candidate.canonical_key(): candidate
        for candidate in coliseum_threshold_intents(state)
    }
    if action.canonical_key() not in legal:
        raise ValueError("Cephalid Coliseum threshold activation is not legal")
    index = _coliseum_index(state)
    paid = solver.pay(state, 0, 1)
    paid = solver.remove_perm(paid, index, to_grave=True)
    before_hand = len(paid.hand)
    drawn_state, drawn = solver.draw_from_library(paid, 3)
    drawn_state = solver.add_trace(
        drawn_state,
        f"Cephalid Coliseum threshold -> draw {len(drawn)}: "
        f"{solver.drawn_cards_text(drawn)}",
    )
    return TransitionEnvelope(
        true_state=drawn_state,
        observations=ObservationBatch(
            tuple(DrawObservation(card, source=COLISEUM) for card in drawn)
        ),
        pending_decision=PendingDecisionSpec(
            decision_id=COLISEUM_DISCARD_DECISION_ID,
            kind="coliseum_discard",
            source=COLISEUM,
            decision_stage=DECISION_POST_OBSERVATION,
            contingent_on=action.action_id,
        ),
        trace_note=(
            f"Coliseum drew {len(drawn)} after commitment; "
            f"hand grew from {before_hand}"
        ),
    )


def information_after_coliseum_draw(
    prior: InformationState,
    envelope: TransitionEnvelope,
) -> InformationState:
    return apply_observation_batch(prior, envelope.observations)


def coliseum_discard_intents(state) -> Tuple[ActionIntent, ...]:
    hand = tuple(sorted(state.hand))
    discard_n = min(3, len(hand))
    if discard_n == 0:
        return ()
    unique = sorted(
        {
            tuple(sorted(hand[i] for i in inds))
            for inds in combinations(range(len(hand)), discard_n)
        }
    )
    rows = []
    for index, cards in enumerate(unique):
        rows.append(
            ActionIntent(
                action_id=f"coliseum.discard.{index:03d}",
                kind="coliseum_discard",
                parameters=(("cards", cards),),
                equivalence_key=("coliseum_discard", cards),
                label="Discard " + ", ".join(cards),
                decision_stage=DECISION_POST_OBSERVATION,
                source=COLISEUM,
                contingent_on=COLISEUM_ACTION_ID,
            )
        )
    return tuple(rows)


def coliseum_discard_request(
    state,
    information: InformationState,
    *,
    horizon: int,
    objective: str = "win_by_horizon",
    policy_id: str = "base",
    caverns_live=None,
) -> DecisionRequest:
    return DecisionRequest(
        observation=make_policy_view(state, information, caverns_live=caverns_live),
        actions=coliseum_discard_intents(state),
        context=PolicyDecisionContext(
            horizon=horizon,
            objective=objective,
            policy_id=policy_id,
            decision_id=COLISEUM_DISCARD_DECISION_ID,
            decision_stage=DECISION_POST_OBSERVATION,
        ),
    )


def resolve_coliseum_discard(state, action: ActionIntent) -> TransitionEnvelope:
    legal = {
        candidate.canonical_key(): candidate
        for candidate in coliseum_discard_intents(state)
    }
    if action.canonical_key() not in legal:
        raise ValueError("Coliseum discard action is not legal")
    cards = tuple(dict(action.parameters)["cards"])
    available = Counter(state.hand)
    requested = Counter(cards)
    if any(requested[card] > available[card] for card in requested):
        raise ValueError("discard action requests unavailable cards")
    hand = list(state.hand)
    for card in cards:
        hand.remove(card)
    resolved = replace(
        state,
        hand=tuple(hand),
        graveyard=state.graveyard + cards,
    )
    resolved = solver.add_trace(
        resolved, "Cephalid Coliseum discard: " + ", ".join(cards)
    )
    return TransitionEnvelope(true_state=resolved)
