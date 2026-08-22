#!/usr/bin/env python3
"""Phase-1 staged adapters for random/reveal decisions outside tutors.

Covered:
- Urza, Lord High Artificer {5}: commit activation, shuffle, exile observed top,
  then choose whether/how to play the now-known exiled card.
- Cephalid Coliseum threshold: commit activation/costs, draw observed cards,
  then choose discards from the resulting known hand.

The Urza adapter intentionally does not invoke the old bundled Oracle cast macro
for a revealed spell.  It hands that known-card cast to a later shared rules
adapter so artifact/Assistant scry triggers cannot bypass the Phase-1 boundary.
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
    DECISION_MECHANICAL,
    DECISION_POST_OBSERVATION,
    DecisionRequest,
    DrawObservation,
    ObservationBatch,
    PendingDecisionSpec,
    PolicyDecisionContext,
    PublicZoneChangeObservation,
    ShuffleObservation,
    TransitionEnvelope,
    apply_observation_batch,
)

URZA = solver.COMMANDER
COLISEUM = "Cephalid Coliseum"
URZA_SPIN_ACTION_ID = "urza.spin.activate"
URZA_PLAY_DECISION_ID = "urza.spin.play-exiled"
COLISEUM_ACTION_ID = "coliseum.threshold.activate"
COLISEUM_DISCARD_DECISION_ID = "coliseum.threshold.discard"


def urza_spin_intents(state) -> Tuple[ActionIntent, ...]:
    if not state.urza or not solver.can_pay(state, 5, 0) or not state.library:
        return ()
    return (
        ActionIntent(
            action_id=URZA_SPIN_ACTION_ID,
            kind="activate_urza_spin",
            parameters=(("generic_cost", 5),),
            equivalence_key=("urza_spin",),
            label="Activate Urza for 5",
            decision_stage=DECISION_COMMIT,
            source=URZA,
        ),
    )


def urza_spin_request(state, information: InformationState, *, horizon: int, objective="win_by_horizon", policy_id="base", caverns_live=None):
    return DecisionRequest(
        observation=make_policy_view(state, information, caverns_live=caverns_live),
        actions=urza_spin_intents(state),
        context=PolicyDecisionContext(
            horizon=horizon,
            objective=objective,
            policy_id=policy_id,
            decision_id="urza.spin.activation",
            decision_stage=DECISION_COMMIT,
        ),
    )


def resolve_urza_spin(state, action: ActionIntent) -> TransitionEnvelope:
    legal = {candidate.canonical_key(): candidate for candidate in urza_spin_intents(state)}
    if action.canonical_key() not in legal:
        raise ValueError("Urza spin activation is not legal")
    paid = solver.pay(state, 5, 0)
    shuffled = replace(paid, library=solver.shuffled_library(paid, "urza-spin"))
    card = shuffled.library[0]
    observed = replace(
        shuffled,
        library=shuffled.library[1:],
        exile=shuffled.exile + (card,),
    )
    observed = solver.add_trace(observed, f"Urza spin -> exile {card}")
    return TransitionEnvelope(
        true_state=observed,
        observations=ObservationBatch(
            (
                ShuffleObservation("Urza spin"),
                PublicZoneChangeObservation(
                    card,
                    from_zone="library",
                    to_zone="exile",
                    source="Urza spin",
                ),
            )
        ),
        pending_decision=PendingDecisionSpec(
            decision_id=URZA_PLAY_DECISION_ID,
            kind="urza_play_exiled",
            source=URZA,
            decision_stage=DECISION_POST_OBSERVATION,
            contingent_on=action.action_id,
        ),
        trace_note=f"Urza spin observed exiled card {card}",
    )


def information_after_urza_spin(prior: InformationState, envelope: TransitionEnvelope) -> InformationState:
    return apply_observation_batch(prior, envelope.observations)


def _latest_urza_exiled_card(state) -> str:
    if not state.exile:
        raise ValueError("Urza spin has no exiled card")
    return str(state.exile[-1])


def urza_post_spin_intents(state) -> Tuple[ActionIntent, ...]:
    card = _latest_urza_exiled_card(state)
    rows = [
        ActionIntent(
            action_id="urza.spin.decline",
            kind="urza_play_exiled",
            parameters=(("choice", "decline"), ("card", card)),
            equivalence_key=("urza_spin", "decline", card),
            label=f"Leave {card} in exile",
            decision_stage=DECISION_POST_OBSERVATION,
            source=URZA,
            contingent_on=URZA_SPIN_ACTION_ID,
        )
    ]

    if card in solver.ALL_LANDS and not state.land_played:
        rows.append(
            ActionIntent(
                action_id="urza.spin.play-land",
                kind="urza_play_exiled",
                parameters=(("choice", "play_land"), ("card", card)),
                equivalence_key=("urza_spin", "play_land", card),
                label=f"Play {card}",
                decision_stage=DECISION_POST_OBSERVATION,
                source=URZA,
                contingent_on=URZA_SPIN_ACTION_ID,
            )
        )

    can_cast_front = card not in solver.ALL_LANDS or card in solver.MDFC_BLUE_LANDS
    if can_cast_front and card not in {"Chrome Mox", "Mox Diamond"}:
        if card == "Everflowing Chalice":
            reduction = 2 if state.ftt_level >= 3 else 0
            pool = state.blue + state.colorless
            max_k = min(8, max(0, (pool + reduction) // 2))
            for k in range(max_k + 1):
                rows.append(
                    ActionIntent(
                        action_id=f"urza.spin.cast-chalice.{k}",
                        kind="urza_play_exiled",
                        parameters=(("choice", "cast_spell"), ("card", card), ("multikicker", k)),
                        equivalence_key=("urza_spin", "cast", card, k),
                        label=f"Cast {card} free; multikicker {k}",
                        decision_stage=DECISION_POST_OBSERVATION,
                        source=URZA,
                        contingent_on=URZA_SPIN_ACTION_ID,
                    )
                )
        else:
            rows.append(
                ActionIntent(
                    action_id="urza.spin.cast-spell",
                    kind="urza_play_exiled",
                    parameters=(("choice", "cast_spell"), ("card", card)),
                    equivalence_key=("urza_spin", "cast", card),
                    label=f"Cast {card} without paying mana cost",
                    decision_stage=DECISION_POST_OBSERVATION,
                    source=URZA,
                    contingent_on=URZA_SPIN_ACTION_ID,
                )
            )
    return tuple(rows)


def urza_post_spin_request(state, information: InformationState, *, horizon: int, objective="win_by_horizon", policy_id="base", caverns_live=None):
    return DecisionRequest(
        observation=make_policy_view(state, information, caverns_live=caverns_live),
        actions=urza_post_spin_intents(state),
        context=PolicyDecisionContext(
            horizon=horizon,
            objective=objective,
            policy_id=policy_id,
            decision_id=URZA_PLAY_DECISION_ID,
            decision_stage=DECISION_POST_OBSERVATION,
        ),
    )


def resolve_urza_post_spin_choice(state, action: ActionIntent) -> TransitionEnvelope:
    legal = {candidate.canonical_key(): candidate for candidate in urza_post_spin_intents(state)}
    if action.canonical_key() not in legal:
        raise ValueError("Urza post-spin action is not legal")
    params = dict(action.parameters)
    choice = str(params["choice"])
    card = str(params["card"])
    if state.exile[-1] != card:
        raise ValueError("post-spin action does not match observed exiled card")

    if choice == "decline":
        return TransitionEnvelope(
            true_state=solver.add_trace(state, f"Urza spin -> leave {card} exiled")
        )

    # Move the known permission card out of exile only after the policy has made
    # its post-observation choice.
    exile = list(state.exile)
    exile.pop()
    staged = replace(state, exile=tuple(exile), hand=state.hand + (card,))

    if choice == "play_land":
        played = solver.play_land(staged, card)
        if played is None:
            raise ValueError("observed Urza land could not be played")
        return TransitionEnvelope(true_state=solver.add_trace(played, f"Urza spin -> play {card}"))

    if choice == "cast_spell":
        # Do not call cast_from_hand here. That legacy macro can bundle Assistant
        # scry / artifact triggers and would bypass the observation boundary.
        return TransitionEnvelope(
            true_state=staged,
            pending_decision=PendingDecisionSpec(
                decision_id="urza.spin.cast-known-card",
                kind="cast_known_card_free",
                source=card,
                decision_stage=DECISION_MECHANICAL,
                contingent_on=URZA_PLAY_DECISION_ID,
            ),
            trace_note=(
                f"Known Urza-exiled spell {card} selected for free cast"
                + (
                    f" with multikicker {int(params.get('multikicker', 0))}"
                    if card == "Everflowing Chalice"
                    else ""
                )
            ),
        )
    raise ValueError(f"unknown Urza post-spin choice {choice!r}")


# ---------------------------------------------------------------------------
# Cephalid Coliseum
# ---------------------------------------------------------------------------


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


def coliseum_threshold_request(state, information: InformationState, *, horizon: int, objective="win_by_horizon", policy_id="base", caverns_live=None):
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
    legal = {candidate.canonical_key(): candidate for candidate in coliseum_threshold_intents(state)}
    if action.canonical_key() not in legal:
        raise ValueError("Cephalid Coliseum threshold activation is not legal")
    index = _coliseum_index(state)
    paid = solver.pay(state, 0, 1)
    paid = solver.remove_perm(paid, index, to_grave=True)
    before_hand = len(paid.hand)
    drawn_state, drawn = solver.draw_from_library(paid, 3)
    drawn_state = solver.add_trace(
        drawn_state,
        f"Cephalid Coliseum threshold -> draw {len(drawn)}: {solver.drawn_cards_text(drawn)}",
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
        trace_note=f"Coliseum drew {len(drawn)} after commitment; hand grew from {before_hand}",
    )


def information_after_coliseum_draw(prior: InformationState, envelope: TransitionEnvelope) -> InformationState:
    return apply_observation_batch(prior, envelope.observations)


def coliseum_discard_intents(state) -> Tuple[ActionIntent, ...]:
    hand = tuple(sorted(state.hand))
    discard_n = min(3, len(hand))
    if discard_n == 0:
        return ()
    unique = sorted({tuple(sorted(hand[i] for i in inds)) for inds in combinations(range(len(hand)), discard_n)})
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


def coliseum_discard_request(state, information: InformationState, *, horizon: int, objective="win_by_horizon", policy_id="base", caverns_live=None):
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
    legal = {candidate.canonical_key(): candidate for candidate in coliseum_discard_intents(state)}
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
    resolved = solver.add_trace(resolved, "Cephalid Coliseum discard: " + ", ".join(cards))
    return TransitionEnvelope(true_state=resolved)
