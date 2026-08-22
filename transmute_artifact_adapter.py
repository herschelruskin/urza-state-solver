#!/usr/bin/env python3
"""Phase-1 information-faithful Transmute Artifact adapter.

Transmute Artifact is intentionally separated from the simpler tutor adapter because
its important choices occur at different points during spell resolution:

    cast/pay UU
      -> choose an artifact to sacrifice
      -> sacrifice
      -> search observation
      -> choose a target (or fail to find)
      -> if target MV is greater: pay the difference or decline
      -> enter battlefield / graveyard
      -> shuffle

The searched target is not available to help pay its own difference.  Conversely,
the difference does *not* have to be floating before resolution: when the effect
asks for a mana payment, legal mana abilities may be activated at that point.

This module does not modify Oracle search.  It reuses the validated rules helpers
for spell payment, VFC triggers, permanent sacrifice, mana abilities, shuffling,
and battlefield entry.  Artifact ETB trigger bundles are deliberately left as a
pending mechanical continuation after placement; Phase 2 will route those through
the same staged scry/observation machinery instead of calling an Oracle macro that
could resolve a hidden-information scry immediately.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, Iterable, Optional, Sequence, Tuple

import urza_solver as solver
from solver_architecture import (
    InformationState,
    canonical_markov_state_key,
    make_policy_view,
)
from decision_observation import (
    ActionIntent,
    DECISION_COMMIT,
    DECISION_MECHANICAL,
    DECISION_POST_OBSERVATION,
    DecisionRequest,
    ObservationBatch,
    PendingDecisionSpec,
    PolicyDecisionContext,
    PublicZoneChangeObservation,
    SearchZoneObservation,
    ShuffleObservation,
    TransitionEnvelope,
    apply_observation_batch,
)

CARD = "Transmute Artifact"
CAST_ACTION_ID = "transmute.cast"
SACRIFICE_DECISION_ID = "transmute.choose-sacrifice"
SEARCH_DECISION_ID = "transmute.choose-target"
PAYMENT_DECISION_ID = "transmute.pay-difference"
ETB_CONTINUATION_ID = "transmute.resolve-entered-artifact-triggers"


@dataclass(frozen=True)
class TransmuteResolutionContext:
    """Rules-side continuation metadata; never passed directly to a policy."""

    sacrificed_name: str = ""
    sacrificed_mode: str = ""
    sacrificed_mv: int = -1
    target: str = ""
    difference: int = 0


def _artifact_mv_for_sacrifice(perm) -> int:
    # Preserve the current Oracle Transmute representation for now.  The broader
    # Phase-1 macro audit will separately review copy-token mana-value semantics.
    if getattr(perm, "mode", "") in {
        "clue",
        "construct",
        "treasure",
        "chrome_copy",
        "chrome_copy_preturn",
    }:
        return 0
    return int(solver.mana_value(getattr(perm, "name", "")))


def _public_perm_signature(perm) -> Tuple[object, ...]:
    return (
        str(getattr(perm, "name", "")),
        bool(getattr(perm, "tapped", False)),
        bool(getattr(perm, "sick", False)),
        int(getattr(perm, "counters", 0)),
        str(getattr(perm, "mode", "")),
        bool(getattr(perm, "knack_granted", False)),
        bool(getattr(perm, "producer_urza_ready", False)),
    )


def _artifact_selectors(state) -> Tuple[Tuple[int, Tuple[object, ...], int], ...]:
    """Return deterministic public selectors for sacrificial artifacts.

    The third item is the ordinal among identical public signatures.  This avoids
    exposing unstable battlefield insertion indexes in policy identity while still
    allowing the rules layer to resolve one concrete permanent.
    """
    seen: Dict[Tuple[object, ...], int] = {}
    rows = []
    for index, perm in enumerate(state.battlefield):
        if not solver.is_artifact_perm(perm):
            continue
        sig = _public_perm_signature(perm)
        ordinal = seen.get(sig, 0)
        seen[sig] = ordinal + 1
        rows.append((index, sig, ordinal))
    rows.sort(key=lambda row: (row[1], row[2]))
    return tuple(rows)


def _resolve_selector(state, signature: Sequence[object], ordinal: int) -> int:
    wanted = tuple(signature)
    found = 0
    for index, perm in enumerate(state.battlefield):
        if _public_perm_signature(perm) != wanted:
            continue
        if found == int(ordinal):
            return index
        found += 1
    raise ValueError("selected Transmute sacrifice permanent is no longer present")


def transmute_cast_intents(state) -> Tuple[ActionIntent, ...]:
    """Casting commitment depends only on current legal/public resources."""
    if CARD not in state.hand or not solver.can_pay(state, 0, 2):
        return ()
    return (
        ActionIntent(
            action_id=CAST_ACTION_ID,
            kind="cast_spell",
            parameters=(("card", CARD),),
            equivalence_key=("cast", CARD),
            label="Cast Transmute Artifact",
            decision_stage=DECISION_COMMIT,
            source=CARD,
        ),
    )


def transmute_cast_request(
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
        actions=transmute_cast_intents(state),
        context=PolicyDecisionContext(
            horizon=horizon,
            objective=objective,
            policy_id=policy_id,
            decision_id="transmute.cast",
            decision_stage=DECISION_COMMIT,
        ),
    )


def resolve_transmute_cast(state, action: ActionIntent) -> TransitionEnvelope:
    """Pay UU and put the spell in its resolving state; do not sacrifice yet."""
    if action.action_id != CAST_ACTION_ID:
        raise ValueError("not a Transmute Artifact cast intent")
    if not transmute_cast_intents(state):
        raise ValueError("Transmute Artifact cast is not legal")

    paid = solver.pay(state, 0, 2)
    next_state = replace(
        paid,
        hand=solver.remove_one(paid.hand, CARD),
        graveyard=paid.graveyard + (CARD,),
        spell_cast_this_turn=True,
    )
    next_state = solver.vfc_noncreature_cast_trigger(next_state, CARD)
    next_state = solver.add_trace(next_state, "cast Transmute Artifact; resolution pending")
    return TransitionEnvelope(
        true_state=next_state,
        observations=ObservationBatch(),
        pending_decision=PendingDecisionSpec(
            decision_id=SACRIFICE_DECISION_ID,
            kind="transmute_choose_sacrifice",
            source=CARD,
            decision_stage=DECISION_COMMIT,
            contingent_on=action.action_id,
        ),
        trace_note="Transmute cast paid; sacrifice choice occurs on resolution",
    )


def transmute_sacrifice_intents(state_after_cast) -> Tuple[ActionIntent, ...]:
    out = []
    for _, signature, ordinal in _artifact_selectors(state_after_cast):
        name, tapped, sick, counters, mode, knack, refund = signature
        mv = _artifact_mv_for_sacrifice(
            next(
                p
                for p in state_after_cast.battlefield
                if _public_perm_signature(p) == signature
            )
        )
        out.append(
            ActionIntent(
                action_id=f"transmute.sac.{len(out):02d}",
                kind="transmute_choose_sacrifice",
                parameters=(
                    ("signature", tuple(signature)),
                    ("ordinal", int(ordinal)),
                    ("mana_value", int(mv)),
                ),
                equivalence_key=("transmute_sacrifice", tuple(signature), int(ordinal)),
                label=f"Sacrifice {name or mode} (MV {mv})",
                decision_stage=DECISION_COMMIT,
                source=CARD,
                contingent_on=CAST_ACTION_ID,
            )
        )
    return tuple(out)


def transmute_sacrifice_request(
    state_after_cast,
    information: InformationState,
    *,
    horizon: int,
    objective: str = "win_by_horizon",
    policy_id: str = "base",
    caverns_live: Optional[bool] = None,
) -> DecisionRequest:
    return DecisionRequest(
        observation=make_policy_view(
            state_after_cast, information, caverns_live=caverns_live
        ),
        actions=transmute_sacrifice_intents(state_after_cast),
        context=PolicyDecisionContext(
            horizon=horizon,
            objective=objective,
            policy_id=policy_id,
            decision_id=SACRIFICE_DECISION_ID,
            decision_stage=DECISION_COMMIT,
        ),
    )


def resolve_transmute_sacrifice(
    state_after_cast,
    action: ActionIntent,
) -> Tuple[TransitionEnvelope, TransmuteResolutionContext, SearchZoneObservation]:
    if action.kind != "transmute_choose_sacrifice":
        raise ValueError("not a Transmute sacrifice intent")
    params = dict(action.parameters)
    signature = tuple(params["signature"])
    ordinal = int(params["ordinal"])
    index = _resolve_selector(state_after_cast, signature, ordinal)
    perm = state_after_cast.battlefield[index]
    mv = _artifact_mv_for_sacrifice(perm)
    name = str(getattr(perm, "name", ""))
    mode = str(getattr(perm, "mode", ""))

    sacrificed = solver.remove_perm(state_after_cast, index, to_grave=True)
    sacrificed = solver.add_trace(
        sacrificed, f"Transmute resolution sacrifices {name or mode}"
    )
    legal_cards = tuple(sorted(set(sacrificed.library) & solver.ARTIFACTS))
    search = SearchZoneObservation(
        zone="library",
        legal_cards=legal_cards,
        context=CARD,
        may_fail_to_find=True,
    )
    context = TransmuteResolutionContext(
        sacrificed_name=name,
        sacrificed_mode=mode,
        sacrificed_mv=mv,
    )
    return (
        TransitionEnvelope(
            true_state=sacrificed,
            observations=ObservationBatch((search,)),
            pending_decision=PendingDecisionSpec(
                decision_id=SEARCH_DECISION_ID,
                kind="transmute_choose_target",
                source=CARD,
                decision_stage=DECISION_POST_OBSERVATION,
                contingent_on=action.action_id,
            ),
            trace_note="Transmute search information is now legal",
        ),
        context,
        search,
    )


def transmute_target_intents(search: SearchZoneObservation) -> Tuple[ActionIntent, ...]:
    if search.context != CARD:
        raise ValueError("search observation is not from Transmute Artifact")
    out = [
        ActionIntent(
            action_id="transmute.target.no-find",
            kind="transmute_choose_target",
            parameters=(("target", ""),),
            equivalence_key=("transmute_target", "no_find"),
            label="Fail to find",
            decision_stage=DECISION_POST_OBSERVATION,
            source=CARD,
            contingent_on=SACRIFICE_DECISION_ID,
        )
    ]
    for target in tuple(sorted(set(search.legal_cards))):
        out.append(
            ActionIntent(
                action_id=f"transmute.target.{len(out):02d}",
                kind="transmute_choose_target",
                parameters=(("target", target),),
                equivalence_key=("transmute_target", target),
                label=f"Find {target}",
                decision_stage=DECISION_POST_OBSERVATION,
                source=CARD,
                contingent_on=SACRIFICE_DECISION_ID,
            )
        )
    return tuple(out)


def transmute_target_request(
    state_after_sacrifice,
    information_after_search: InformationState,
    search: SearchZoneObservation,
    *,
    horizon: int,
    objective: str = "win_by_horizon",
    policy_id: str = "base",
    caverns_live: Optional[bool] = None,
) -> DecisionRequest:
    return DecisionRequest(
        observation=make_policy_view(
            state_after_sacrifice,
            information_after_search,
            caverns_live=caverns_live,
        ),
        actions=transmute_target_intents(search),
        context=PolicyDecisionContext(
            horizon=horizon,
            objective=objective,
            policy_id=policy_id,
            decision_id=SEARCH_DECISION_ID,
            decision_stage=DECISION_POST_OBSERVATION,
        ),
    )


def _trace_delta(before, after) -> Tuple[str, ...]:
    start = len(before.trace)
    rows = []
    for entry in after.trace[start:]:
        rows.extend(str(entry).splitlines())
    return tuple(rows)


def _resolution_mana_successors(state) -> Tuple[Tuple[object, str], ...]:
    """Mana abilities currently modeled as legal during a resolution payment.

    We deliberately use only existing rules helpers whose actions are mana
    abilities: intrinsic sources and Urza's artifact-tap mana ability.  The Phase-1
    macro audit will enumerate any remaining card-specific mana abilities before
    declaring the whole phase complete.
    """
    rows = []
    for successor in solver.intrinsic_mana_actions(state):
        delta = _trace_delta(state, successor)
        label = " | ".join(delta) if delta else "intrinsic mana ability"
        rows.append((successor, label))
    for successor in solver.tap_artifact_for_urza_actions(state):
        delta = _trace_delta(state, successor)
        label = " | ".join(delta) if delta else "Urza mana ability"
        rows.append((successor, label))
    rows.sort(key=lambda row: row[1])
    return tuple(rows)


def transmute_difference_payment_options(
    state_with_target_removed,
    difference: int,
    *,
    max_steps: int = 12,
) -> Tuple[Tuple[ActionIntent, object], ...]:
    """Enumerate minimal legal ways to pay X during Transmute resolution.

    Search stops expanding a path once it can pay, so these are minimal activation
    plans rather than arbitrary extra mana floating.  Distinct public mana-source
    plans remain distinct because tapped/sacrificed resources can affect future
    value.  Hidden library order is never placed in the policy action identity.
    """
    difference = int(difference)
    if difference <= 0:
        paid = solver.pay(state_with_target_removed, 0, 0)
        action = ActionIntent(
            action_id="transmute.pay.zero",
            kind="transmute_pay_difference",
            parameters=(("choice", "pay"), ("difference", 0), ("mana_steps", ())),
            equivalence_key=("transmute_pay", 0, ()),
            label="No difference payment required",
            decision_stage=DECISION_POST_OBSERVATION,
            source=CARD,
            contingent_on=SEARCH_DECISION_ID,
        )
        return ((action, paid),)

    root_trace_len = len(state_with_target_removed.trace)
    queue = [(state_with_target_removed, tuple())]
    seen = {canonical_markov_state_key(state_with_target_removed)}
    payable: Dict[Tuple[str, ...], object] = {}

    while queue:
        current, plan = queue.pop(0)
        if solver.can_pay(current, difference, 0):
            paid = solver.pay(current, difference, 0)
            payable.setdefault(plan, paid)
            continue
        if len(plan) >= max_steps:
            continue
        for successor, label in _resolution_mana_successors(current):
            key = canonical_markov_state_key(successor)
            if key in seen:
                continue
            seen.add(key)
            queue.append((successor, plan + (label,)))

    rows = []
    for index, (plan, paid_state) in enumerate(sorted(payable.items(), key=lambda kv: kv[0])):
        action = ActionIntent(
            action_id=f"transmute.pay.{index:02d}",
            kind="transmute_pay_difference",
            parameters=(
                ("choice", "pay"),
                ("difference", difference),
                ("mana_steps", tuple(plan)),
            ),
            equivalence_key=("transmute_pay", difference, tuple(plan)),
            label=(
                f"Pay {difference}"
                + (" via " + " ; ".join(plan) if plan else " from floating mana")
            ),
            decision_stage=DECISION_POST_OBSERVATION,
            source=CARD,
            contingent_on=SEARCH_DECISION_ID,
        )
        rows.append((action, paid_state))
    return tuple(rows)


def _shuffle_events(source: str) -> ObservationBatch:
    return ObservationBatch((ShuffleObservation(source),))


def _enter_target_then_shuffle(
    state_without_target,
    target: str,
    *,
    salt: str,
) -> TransitionEnvelope:
    entered = solver.add_perm(
        state_without_target,
        target,
        sick=target in solver.CREATURES,
    )
    shuffled = replace(entered, library=solver.shuffled_library(entered, salt))
    shuffled = solver.add_trace(shuffled, f"Transmute puts {target} onto battlefield; shuffle")
    return TransitionEnvelope(
        true_state=shuffled,
        observations=_shuffle_events(CARD),
        pending_decision=PendingDecisionSpec(
            decision_id=ETB_CONTINUATION_ID,
            kind="resolve_entered_artifact_triggers",
            source=target,
            decision_stage=DECISION_MECHANICAL,
            contingent_on=PAYMENT_DECISION_ID,
        ),
        trace_note="Artifact entered; ETB trigger bundle intentionally deferred",
    )


def resolve_transmute_target(
    state_after_sacrifice,
    context: TransmuteResolutionContext,
    search: SearchZoneObservation,
    action: ActionIntent,
) -> Tuple[TransitionEnvelope, TransmuteResolutionContext, Tuple[Tuple[ActionIntent, object], ...]]:
    """Resolve target selection up to the optional difference-payment decision."""
    legal = {intent.canonical_key() for intent in transmute_target_intents(search)}
    if action.canonical_key() not in legal:
        raise ValueError("Transmute target action is not legal for this search")
    target = str(dict(action.parameters).get("target", ""))

    if not target:
        shuffled = replace(
            state_after_sacrifice,
            library=solver.shuffled_library(
                state_after_sacrifice,
                f"transmute:no-target:{context.sacrificed_name}",
            ),
        )
        shuffled = solver.add_trace(shuffled, "Transmute finds no card; shuffle")
        return (
            TransitionEnvelope(
                true_state=shuffled,
                observations=_shuffle_events(CARD),
                pending_decision=None,
                trace_note="Transmute search failed to find",
            ),
            context,
            (),
        )

    if target not in search.legal_cards or target not in state_after_sacrifice.library:
        raise ValueError("chosen Transmute target is not present/legal")

    lib = list(state_after_sacrifice.library)
    lib.remove(target)
    without_target = replace(state_after_sacrifice, library=tuple(lib))
    target_mv = int(solver.mana_value(target))
    difference = max(0, target_mv - int(context.sacrificed_mv))
    next_context = replace(context, target=target, difference=difference)

    if difference == 0:
        envelope = _enter_target_then_shuffle(
            without_target,
            target,
            salt=f"transmute-paid:{context.sacrificed_name}:{target}",
        )
        return envelope, next_context, ()

    payment_options = transmute_difference_payment_options(without_target, difference)
    pending = PendingDecisionSpec(
        decision_id=PAYMENT_DECISION_ID,
        kind="transmute_pay_difference",
        source=CARD,
        decision_stage=DECISION_POST_OBSERVATION,
        contingent_on=action.action_id,
    )
    return (
        TransitionEnvelope(
            true_state=without_target,
            observations=ObservationBatch(),
            pending_decision=pending,
            trace_note=f"Transmute target chosen; optional difference payment {difference}",
        ),
        next_context,
        payment_options,
    )


def transmute_payment_intents(
    payment_options: Iterable[Tuple[ActionIntent, object]],
    difference: int,
) -> Tuple[ActionIntent, ...]:
    out = [
        ActionIntent(
            action_id="transmute.pay.decline",
            kind="transmute_pay_difference",
            parameters=(("choice", "decline"), ("difference", int(difference))),
            equivalence_key=("transmute_pay", int(difference), "decline"),
            label=f"Decline {int(difference)}; target to graveyard",
            decision_stage=DECISION_POST_OBSERVATION,
            source=CARD,
            contingent_on=SEARCH_DECISION_ID,
        )
    ]
    out.extend(action for action, _ in payment_options)
    return tuple(out)


def resolve_transmute_payment(
    state_with_target_removed,
    context: TransmuteResolutionContext,
    action: ActionIntent,
) -> TransitionEnvelope:
    if not context.target or context.difference <= 0:
        raise ValueError("Transmute payment decision requires a higher-MV target")
    choice = str(dict(action.parameters).get("choice", ""))

    if choice == "decline":
        searched = replace(
            state_with_target_removed,
            graveyard=state_with_target_removed.graveyard + (context.target,),
        )
        # Match the current Oracle decline shuffle coordinate: the shuffle is
        # derived from the searched state before the target is moved to graveyard.
        base_for_shuffle = state_with_target_removed
        shuffled_library = solver.shuffled_library(
            base_for_shuffle,
            f"transmute:{context.sacrificed_name}:{context.target}",
        )
        searched = replace(searched, library=tuple(shuffled_library))
        searched = solver.add_trace(
            searched,
            f"Transmute {context.sacrificed_name}->{context.target}; "
            f"decline {context.difference}, target to graveyard",
        )
        return TransitionEnvelope(
            true_state=searched,
            observations=_shuffle_events(CARD),
            pending_decision=None,
            trace_note="Transmute difference declined",
        )

    if choice != "pay":
        raise ValueError("unknown Transmute difference-payment choice")

    options = {
        candidate.canonical_key(): paid_state
        for candidate, paid_state in transmute_difference_payment_options(
            state_with_target_removed, context.difference
        )
    }
    paid_state = options.get(action.canonical_key())
    if paid_state is None:
        raise ValueError("Transmute payment plan is not legal from current state")
    return _enter_target_then_shuffle(
        paid_state,
        context.target,
        salt=f"transmute-paid:{context.sacrificed_name}:{context.target}",
    )


def information_after_transmute_transition(
    prior: InformationState,
    envelope: TransitionEnvelope,
) -> InformationState:
    return apply_observation_batch(prior, envelope.observations)
