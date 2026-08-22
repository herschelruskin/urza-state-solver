#!/usr/bin/env python3
"""Phase-1 non-Oracle Sensei's Divining Top decision adapter.

This module is the first production-shaped action -> observation -> contingent
choice split.  It deliberately lives beside the Oracle search: Oracle top_actions
remains unchanged and clairvoyant, while the non-Oracle path commits to activating
Top before the rules layer reveals the top cards.

Policy boundary:
    current PolicyView
        -> commit intent: activate Top
        -> rules pay {1}
        -> RevealTopObservation(top N)
        -> updated InformationState / PolicyView
        -> post-observation reorder intents
        -> rules apply chosen order

Only rules-layer functions in this module receive the concrete solver State.
Policy-facing DecisionRequest objects contain PolicyView and ActionIntent only.
"""

from __future__ import annotations

from dataclasses import replace
import itertools
from typing import Optional, Tuple

import urza_solver as solver
from solver_architecture import InformationState, make_policy_view
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

TOP_ACTIVATE_ACTION_ID = "top.activate.look"
TOP_REORDER_DECISION_KIND = "top_reorder"
TOP_REORDER_DECISION_ID = "top.reorder.after-look"
TOP_SOURCE = "Sensei's Divining Top"


def _top_in_play(state) -> bool:
    return any(getattr(p, "name", "") == TOP_SOURCE for p in state.battlefield)


def top_activation_intents(state) -> Tuple[ActionIntent, ...]:
    """Return the policy-facing Top activation intent without inspecting cards.

    The rules adapter may inspect concrete state to determine legality, but action
    identity/parameters are independent of the unknown top-card permutation.
    This intentionally mirrors the current Oracle legality gate (pay {1}, at
    least two cards in library) so Phase 1 does not silently change rules.
    """
    if not _top_in_play(state):
        return ()
    if not solver.can_pay(state, 1, 0):
        return ()
    if len(state.library) < 2:
        return ()
    return (
        ActionIntent(
            action_id=TOP_ACTIVATE_ACTION_ID,
            kind="activate_ability",
            parameters=(("ability", "look_reorder_top3"),),
            equivalence_key=("top", "look_reorder_top3"),
            label="Activate Sensei's Divining Top",
            decision_stage=DECISION_COMMIT,
            source=TOP_SOURCE,
        ),
    )


def top_activation_request(
    state,
    information: InformationState,
    *,
    horizon: int,
    objective: str = "win_by_horizon",
    policy_id: str = "base",
    caverns_live: Optional[bool] = None,
) -> DecisionRequest:
    """Build the pre-observation Top activation request."""
    return DecisionRequest(
        observation=make_policy_view(state, information, caverns_live=caverns_live),
        actions=top_activation_intents(state),
        context=PolicyDecisionContext(
            horizon=horizon,
            objective=objective,
            policy_id=policy_id,
            decision_id="top.activation",
            decision_stage=DECISION_COMMIT,
        ),
    )


def resolve_top_activation(state, action: ActionIntent) -> TransitionEnvelope:
    """Commit to Top activation, pay cost, then reveal the actual top cards.

    The concrete top cards are consulted only after the policy has selected the
    commit action.  They are emitted as a typed observation and are not encoded in
    the root ActionIntent.
    """
    if action.action_id != TOP_ACTIVATE_ACTION_ID:
        raise ValueError(f"not a Top activation intent: {action.action_id!r}")
    legal = {intent.action_id for intent in top_activation_intents(state)}
    if action.action_id not in legal:
        raise ValueError("Top activation is not legal in this concrete state")

    paid = solver.pay(state, 1, 0)
    n = min(3, len(paid.library))
    revealed = tuple(paid.library[:n])
    paid = solver.add_trace(paid, f"Top activate -> look at {n}")
    return TransitionEnvelope(
        true_state=paid,
        observations=ObservationBatch(
            (RevealTopObservation(revealed, source=TOP_SOURCE),)
        ),
        pending_decision=PendingDecisionSpec(
            decision_id=TOP_REORDER_DECISION_ID,
            kind=TOP_REORDER_DECISION_KIND,
            source=TOP_SOURCE,
            decision_stage=DECISION_POST_OBSERVATION,
            contingent_on=action.action_id,
        ),
        trace_note=f"Top revealed {n} card(s)",
    )


def information_after_top_activation(
    prior: InformationState,
    envelope: TransitionEnvelope,
) -> InformationState:
    if envelope.pending_decision is None or envelope.pending_decision.kind != TOP_REORDER_DECISION_KIND:
        raise ValueError("transition is not a pending Top reorder")
    return apply_observation_batch(prior, envelope.observations)


def top_reorder_intents(information: InformationState) -> Tuple[ActionIntent, ...]:
    """Enumerate reorder choices using only legally revealed known_top cards."""
    cards = tuple(information.known_top[:3])
    if len(cards) < 2:
        return ()
    orders = tuple(sorted(set(itertools.permutations(cards))))
    out = []
    for index, order in enumerate(orders):
        out.append(
            ActionIntent(
                action_id=f"top.reorder.{index:02d}",
                kind=TOP_REORDER_DECISION_KIND,
                parameters=(("order", tuple(order)),),
                equivalence_key=(TOP_REORDER_DECISION_KIND, tuple(order)),
                label="Top reorder: " + " | ".join(order),
                decision_stage=DECISION_POST_OBSERVATION,
                source=TOP_SOURCE,
                contingent_on=TOP_ACTIVATE_ACTION_ID,
            )
        )
    return tuple(out)


def top_reorder_request(
    state_after_activation,
    information_after_reveal: InformationState,
    *,
    horizon: int,
    objective: str = "win_by_horizon",
    policy_id: str = "base",
    caverns_live: Optional[bool] = None,
) -> DecisionRequest:
    """Build the post-observation choice using the now-legitimate top knowledge."""
    return DecisionRequest(
        observation=make_policy_view(
            state_after_activation,
            information_after_reveal,
            caverns_live=caverns_live,
        ),
        actions=top_reorder_intents(information_after_reveal),
        context=PolicyDecisionContext(
            horizon=horizon,
            objective=objective,
            policy_id=policy_id,
            decision_id=TOP_REORDER_DECISION_ID,
            decision_stage=DECISION_POST_OBSERVATION,
        ),
    )


def _intent_order(action: ActionIntent) -> Tuple[str, ...]:
    params = dict(action.parameters)
    order = params.get("order")
    if not isinstance(order, tuple):
        raise ValueError("Top reorder action is missing tuple 'order' parameter")
    return tuple(str(card) for card in order)


def resolve_top_reorder(
    state_after_activation,
    information_after_reveal: InformationState,
    action: ActionIntent,
) -> TransitionEnvelope:
    """Apply a post-observation order chosen from the legally revealed cards."""
    if action.kind != TOP_REORDER_DECISION_KIND:
        raise ValueError(f"not a Top reorder intent: {action.kind!r}")
    if action.decision_stage != DECISION_POST_OBSERVATION:
        raise ValueError("Top reorder must be a post-observation decision")

    legal = {intent.canonical_key(): intent for intent in top_reorder_intents(information_after_reveal)}
    if action.canonical_key() not in legal:
        raise ValueError("Top reorder action was not generated from current legal information")

    order = _intent_order(action)
    n = len(order)
    concrete_prefix = tuple(state_after_activation.library[:n])
    known_prefix = tuple(information_after_reveal.known_top[:n])
    if concrete_prefix != known_prefix:
        raise ValueError("InformationState known_top contradicts concrete Top reveal")
    if sorted(order) != sorted(concrete_prefix):
        raise ValueError("chosen Top order is not a permutation of the revealed cards")

    next_state = replace(
        state_after_activation,
        library=tuple(order) + tuple(state_after_activation.library[n:]),
    )
    next_state = solver.add_trace(next_state, "Top reorder")
    # If deeper top cards were already legally known before this look, Top changes
    # only the viewed prefix. Preserve that remembered suffix in value identity.
    remembered_deeper = tuple(information_after_reveal.known_top[n:])
    resulting_known_top = tuple(order) + remembered_deeper
    return TransitionEnvelope(
        true_state=next_state,
        observations=ObservationBatch(
            (
                LibraryPositionsObservation(
                    known_top=resulting_known_top,
                    top_mode="replace",
                    bottom_mode="preserve",
                    source=TOP_SOURCE,
                ),
            )
        ),
        pending_decision=None,
        trace_note="Top reorder committed",
    )


def information_after_top_reorder(
    prior: InformationState,
    envelope: TransitionEnvelope,
) -> InformationState:
    return apply_observation_batch(prior, envelope.observations)
