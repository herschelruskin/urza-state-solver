#!/usr/bin/env python3
"""Phase-1 non-Oracle tutor/search decision adapter.

This module stages the current simple tutor family across the required
commit -> search observation -> target choice -> shuffle/placement boundary.
It deliberately leaves the Oracle ``simple_tutor_actions`` implementation
unchanged and uses the same validated rules helpers for payment, target
eligibility, zone movement, shuffle RNG, and permanent updates.

Supported in this first tutor layer:
- Dizzy Spell transmute;
- Muddle the Mixture transmute;
- Merchant Scroll;
- Mystical Tutor;
- Spellseeker ETB search.

Cost-coupled artifact searches (Transmute Artifact, Reshape, Whir, Bay, Saga,
Tezzeret, Scour) are intentionally handled in a subsequent layer because their
pre-search sacrifice/X/mode choices must not be retroactively determined by a
post-search target.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional, Tuple

import urza_solver as solver
from solver_architecture import InformationState, make_policy_view
from decision_observation import (
    ActionIntent,
    DECISION_COMMIT,
    DECISION_POST_OBSERVATION,
    DecisionRequest,
    MoveKnownCardObservation,
    ObservationBatch,
    PendingDecisionSpec,
    PolicyDecisionContext,
    PublicZoneChangeObservation,
    SearchZoneObservation,
    ShuffleObservation,
    TransitionEnvelope,
    apply_observation_batch,
)

TUTOR_TARGET_DECISION_KIND = "choose_tutor_target"


@dataclass(frozen=True)
class SimpleTutorSpec:
    source: str
    search_kind: str
    commit_action_id: str
    generic_cost: int = 0
    blue_cost: int = 0
    source_zone: str = "hand"
    result_zone: str = "hand"
    spell_cast: bool = False


_SIMPLE_TUTORS = (
    SimpleTutorSpec(
        source="Dizzy Spell",
        search_kind="dizzy",
        commit_action_id="tutor.dizzy.transmute",
        generic_cost=1,
        blue_cost=2,
    ),
    SimpleTutorSpec(
        source="Muddle the Mixture",
        search_kind="muddle",
        commit_action_id="tutor.muddle.transmute",
        generic_cost=1,
        blue_cost=2,
    ),
    SimpleTutorSpec(
        source="Merchant Scroll",
        search_kind="merchant",
        commit_action_id="tutor.merchant.cast",
        generic_cost=1,
        blue_cost=1,
        spell_cast=True,
    ),
    SimpleTutorSpec(
        source="Mystical Tutor",
        search_kind="mystical",
        commit_action_id="tutor.mystical.cast",
        generic_cost=0,
        blue_cost=1,
        result_zone="top",
        spell_cast=True,
    ),
    SimpleTutorSpec(
        source="Spellseeker",
        search_kind="spellseeker",
        commit_action_id="tutor.spellseeker.etb",
        source_zone="battlefield",
    ),
)

_SPEC_BY_ACTION = {spec.commit_action_id: spec for spec in _SIMPLE_TUTORS}
_SPEC_BY_SOURCE = {spec.source: spec for spec in _SIMPLE_TUTORS}


def _unused_spellseeker_index(state) -> Optional[int]:
    for index, perm in enumerate(state.battlefield):
        if perm.name == "Spellseeker" and perm.mode != "used":
            return index
    return None


def _commit_is_legal(state, spec: SimpleTutorSpec) -> bool:
    if spec.source_zone == "battlefield":
        return _unused_spellseeker_index(state) is not None
    if spec.source not in state.hand:
        return False
    return solver.can_pay(state, spec.generic_cost, spec.blue_cost)


def simple_tutor_commit_intents(state) -> Tuple[ActionIntent, ...]:
    """Generate tutor-use commitments without consulting target identities/order."""
    out = []
    for spec in _SIMPLE_TUTORS:
        if not _commit_is_legal(state, spec):
            continue
        out.append(
            ActionIntent(
                action_id=spec.commit_action_id,
                kind="commit_tutor_search",
                parameters=(("search_kind", spec.search_kind),),
                equivalence_key=("commit_tutor_search", spec.source, spec.search_kind),
                label=f"Use {spec.source}",
                decision_stage=DECISION_COMMIT,
                source=spec.source,
            )
        )
    return tuple(sorted(out, key=lambda action: action.action_id))


def simple_tutor_commit_request(
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
        actions=simple_tutor_commit_intents(state),
        context=PolicyDecisionContext(
            horizon=horizon,
            objective=objective,
            policy_id=policy_id,
            decision_id="simple-tutor.commit",
            decision_stage=DECISION_COMMIT,
        ),
    )


def _commit_simple_tutor_state(state, spec: SimpleTutorSpec):
    """Apply only costs/public commitment; do not choose or move a target yet."""
    if spec.source_zone == "battlefield":
        # Spellseeker's ETB trigger is already pending in the current Oracle model.
        # Mark it used only when the search resolves/target is selected, matching
        # ``simple_tutor_actions`` physical semantics.
        return state

    paid = solver.pay(state, spec.generic_cost, spec.blue_cost)
    if paid is None:
        raise ValueError(f"cannot pay for {spec.source}")
    committed = replace(
        paid,
        hand=solver.remove_one(paid.hand, spec.source),
        graveyard=paid.graveyard + (spec.source,),
    )
    if spec.spell_cast:
        committed = solver.vfc_noncreature_cast_trigger(committed, spec.source)
    return committed


def resolve_simple_tutor_commit(state, action: ActionIntent) -> TransitionEnvelope:
    """Commit tutor use, then expose only the legal search target set."""
    spec = _SPEC_BY_ACTION.get(action.action_id)
    if spec is None:
        raise ValueError(f"unknown simple tutor commit {action.action_id!r}")
    legal_ids = {intent.action_id for intent in simple_tutor_commit_intents(state)}
    if action.action_id not in legal_ids:
        raise ValueError(f"{spec.source} commitment is not legal")

    committed = _commit_simple_tutor_state(state, spec)
    legal_targets = tuple(solver.tutor_targets(committed, spec.search_kind))
    observation = SearchZoneObservation(
        zone="library",
        legal_cards=legal_targets,
        context=spec.source,
        may_fail_to_find=True,
    )
    committed = solver.add_trace(committed, f"{spec.source}: search committed")
    return TransitionEnvelope(
        true_state=committed,
        observations=ObservationBatch((observation,)),
        pending_decision=PendingDecisionSpec(
            decision_id=f"{spec.commit_action_id}.target",
            kind=TUTOR_TARGET_DECISION_KIND,
            source=spec.source,
            decision_stage=DECISION_POST_OBSERVATION,
            contingent_on=spec.commit_action_id,
        ),
        trace_note=f"{spec.source} search exposes {len(legal_targets)} legal target(s)",
    )


def information_after_tutor_search(
    prior: InformationState,
    envelope: TransitionEnvelope,
) -> InformationState:
    if envelope.pending_decision is None or envelope.pending_decision.kind != TUTOR_TARGET_DECISION_KIND:
        raise ValueError("transition is not a pending tutor target decision")
    return apply_observation_batch(prior, envelope.observations)


def _search_event(envelope: TransitionEnvelope) -> SearchZoneObservation:
    matches = [
        event for event in envelope.observations.events
        if isinstance(event, SearchZoneObservation)
    ]
    if len(matches) != 1:
        raise ValueError("tutor transition must contain exactly one SearchZoneObservation")
    return matches[0]


def tutor_target_intents(envelope: TransitionEnvelope) -> Tuple[ActionIntent, ...]:
    """Generate target choices only from the post-commit legal search observation."""
    if envelope.pending_decision is None or envelope.pending_decision.kind != TUTOR_TARGET_DECISION_KIND:
        return ()
    event = _search_event(envelope)
    spec = _SPEC_BY_SOURCE.get(event.context)
    if spec is None:
        raise ValueError(f"unknown tutor search context {event.context!r}")

    out = []
    for target in tuple(sorted(set(event.legal_cards))):
        out.append(
            ActionIntent(
                action_id=f"{spec.commit_action_id}.target.{target}",
                kind=TUTOR_TARGET_DECISION_KIND,
                parameters=(("target", target),),
                equivalence_key=("tutor_target", spec.source, target),
                label=f"{spec.source} -> {target}",
                decision_stage=DECISION_POST_OBSERVATION,
                source=spec.source,
                contingent_on=spec.commit_action_id,
            )
        )
    return tuple(out)


def tutor_target_request(
    state_after_commit,
    information_after_search: InformationState,
    envelope: TransitionEnvelope,
    *,
    horizon: int,
    objective: str = "win_by_horizon",
    policy_id: str = "base",
    caverns_live: Optional[bool] = None,
) -> DecisionRequest:
    pending = envelope.pending_decision
    if pending is None or pending.kind != TUTOR_TARGET_DECISION_KIND:
        raise ValueError("no pending tutor target decision")
    return DecisionRequest(
        observation=make_policy_view(
            state_after_commit,
            information_after_search,
            caverns_live=caverns_live,
        ),
        actions=tutor_target_intents(envelope),
        context=PolicyDecisionContext(
            horizon=horizon,
            objective=objective,
            policy_id=policy_id,
            decision_id=pending.decision_id,
            decision_stage=DECISION_POST_OBSERVATION,
        ),
    )


def _target_from_action(action: ActionIntent) -> str:
    target = dict(action.parameters).get("target")
    if not isinstance(target, str) or not target:
        raise ValueError("tutor target action missing string target")
    return target


def resolve_tutor_target(
    state_after_commit,
    envelope: TransitionEnvelope,
    action: ActionIntent,
) -> TransitionEnvelope:
    """Resolve a target chosen only after the legal search observation."""
    event = _search_event(envelope)
    spec = _SPEC_BY_SOURCE.get(event.context)
    if spec is None:
        raise ValueError(f"unknown tutor search context {event.context!r}")
    if action.decision_stage != DECISION_POST_OBSERVATION or action.kind != TUTOR_TARGET_DECISION_KIND:
        raise ValueError("tutor target must be a post-observation target decision")

    legal = {intent.canonical_key() for intent in tutor_target_intents(envelope)}
    if action.canonical_key() not in legal:
        raise ValueError("tutor target action was not generated by this search observation")
    target = _target_from_action(action)
    if target not in state_after_commit.library:
        raise ValueError(f"chosen target {target!r} is absent from concrete library")

    state = state_after_commit
    observations = []

    if spec.source == "Mystical Tutor":
        library = list(state.library)
        library.remove(target)
        without_target = replace(state, library=tuple(library))
        shuffled = solver.shuffled_library(without_target, "mystical:" + target)
        state = replace(without_target, library=(target,) + tuple(shuffled))
        state = solver.add_trace(state, f"Mystical -> shuffle, then top {target}")
        observations.extend(
            (
                ShuffleObservation(spec.source),
                MoveKnownCardObservation(
                    target,
                    from_zone="search",
                    to_zone="library",
                    position="top",
                    source=spec.source,
                ),
            )
        )
    elif spec.source == "Spellseeker":
        index = _unused_spellseeker_index(state)
        if index is None:
            raise ValueError("Spellseeker search source is no longer available")
        state = solver.move_library_to_hand(state, target)
        state = solver.update_perm(state, index, mode="used")
        state = replace(
            state,
            library=solver.shuffled_library(state, "spellseeker:" + target),
        )
        state = solver.add_trace(state, f"Spellseeker ETB -> {target}")
        observations.extend(
            (
                PublicZoneChangeObservation(target, "library", "hand", spec.source),
                ShuffleObservation(spec.source),
            )
        )
    else:
        state = solver.move_library_to_hand(state, target)
        state = replace(
            state,
            library=solver.shuffled_library(state, f"{spec.source}:{target}"),
        )
        state = solver.add_trace(state, f"{spec.source} -> {target}")
        observations.extend(
            (
                PublicZoneChangeObservation(target, "library", "hand", spec.source),
                ShuffleObservation(spec.source),
            )
        )

    return TransitionEnvelope(
        true_state=state,
        observations=ObservationBatch(tuple(observations)),
        pending_decision=None,
        trace_note=f"{spec.source} target {target} resolved",
    )


def information_after_tutor_target(
    prior: InformationState,
    envelope: TransitionEnvelope,
) -> InformationState:
    return apply_observation_batch(prior, envelope.observations)
