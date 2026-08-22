#!/usr/bin/env python3
"""Phase-1 staged adapters for remaining library-search macros.

Covered effects:
- Repurposing Bay: activation costs (mana/tap/sacrifice) commit before search.
- Urza's Saga chapter III: pending trigger proceeds directly to search observation.
- Tezzeret, Cruel Captain -3: loyalty activation commits before search.
- Scour for Scrap: modes and graveyard target commit on cast; library card is
  chosen later during the search portion of resolution.

Oracle macros remain unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional, Tuple

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
from x_artifact_search_adapter import (
    ETB_KIND,
    PermanentSlot,
    _artifact_slots,
    _slot_from_parameter,
    _slot_index,
)

BAY = "Repurposing Bay"
TEZZ = "Tezzeret, Cruel Captain"
SCOUR = "Scour for Scrap"
SAGA = "Urza's Saga"
TARGET_KIND = "remaining_search_target"


@dataclass(frozen=True)
class RemainingSearchContext:
    source: str
    decision_id: str
    contingent_on: str
    target_mv: int = -1
    graveyard_target: str = ""
    mode: str = ""


def _search_event(cards, *, source: str, context: str, may_fail: bool = True):
    return SearchZoneObservation(
        zone="library",
        legal_cards=tuple(sorted(set(cards))),
        context=context,
        may_fail_to_find=may_fail,
    )


def _target_intents(ctx: RemainingSearchContext, search: SearchZoneObservation):
    prefix = ctx.source.lower().replace(" ", ".").replace("'", "")
    rows = [
        ActionIntent(
            action_id=f"{prefix}.target.fail",
            kind=TARGET_KIND,
            parameters=(("target", ""),),
            equivalence_key=(ctx.source, "fail", ctx.target_mv, ctx.mode, ctx.graveyard_target),
            label="Find no card",
            decision_stage=DECISION_POST_OBSERVATION,
            source=ctx.source,
            contingent_on=ctx.contingent_on,
        )
    ]
    for index, card in enumerate(search.legal_cards):
        rows.append(
            ActionIntent(
                action_id=f"{prefix}.target.{index:02d}",
                kind=TARGET_KIND,
                parameters=(("target", card),),
                equivalence_key=(ctx.source, "target", card, ctx.target_mv, ctx.mode, ctx.graveyard_target),
                label=f"Find {card}",
                decision_stage=DECISION_POST_OBSERVATION,
                source=ctx.source,
                contingent_on=ctx.contingent_on,
            )
        )
    return tuple(rows)


def _target_request(state, information, ctx, search, *, horizon, objective, policy_id, caverns_live):
    return DecisionRequest(
        observation=make_policy_view(state, information, caverns_live=caverns_live),
        actions=_target_intents(ctx, search),
        context=PolicyDecisionContext(
            horizon=horizon,
            objective=objective,
            policy_id=policy_id,
            decision_id=ctx.decision_id,
            decision_stage=DECISION_POST_OBSERVATION,
        ),
    )


def _chosen_target(action: ActionIntent, search: SearchZoneObservation) -> str:
    if action.kind != TARGET_KIND or action.decision_stage != DECISION_POST_OBSERVATION:
        raise ValueError("not a remaining-search target action")
    target = str(dict(action.parameters).get("target", ""))
    if target and target not in search.legal_cards:
        raise ValueError("search target was not in the revealed legal set")
    return target


def _shuffle_event(source: str):
    return ObservationBatch((ShuffleObservation(source),))


def _deferred_etb(state, source: str, target: str, contingent_on: str):
    return TransitionEnvelope(
        true_state=state,
        observations=_shuffle_event(source),
        pending_decision=PendingDecisionSpec(
            decision_id=f"{source.lower().replace(' ', '.')}.etb",
            kind=ETB_KIND,
            source=target,
            decision_stage=DECISION_MECHANICAL,
            contingent_on=contingent_on,
        ),
        trace_note="Artifact entered; ETB trigger bundle intentionally deferred",
    )


# ---------------------------------------------------------------------------
# Repurposing Bay
# ---------------------------------------------------------------------------


def _bay_cost(state) -> int:
    generic = 2
    if solver.has(state, "Forensic Gadgeteer"):
        generic = max(1, generic - 1)
    if state.pa_target == BAY:
        generic = max(1, generic - 2)
    return generic


def bay_activation_intents(state) -> Tuple[ActionIntent, ...]:
    bay_slots = tuple(
        slot for slot in _artifact_slots(state)
        if slot.name == BAY and not slot.tapped
    )
    if not bay_slots:
        return ()
    cost = _bay_cost(state)
    if not solver.can_pay(state, cost, 0):
        return ()
    bay_slot = bay_slots[0]
    rows = []
    serial = 0
    for slot in _artifact_slots(state):
        if slot == bay_slot:
            continue
        # Cannot sacrifice the Bay itself; all other modeled artifact permanents are legal.
        perm_index = _slot_index(state, slot)
        perm = state.battlefield[perm_index]
        sac_mv = 0 if perm.mode in {"clue", "construct", "treasure"} else solver.mana_value(perm.name)
        rows.append(
            ActionIntent(
                action_id=f"bay.activate.{serial:03d}",
                kind="activate_repurposing_bay",
                parameters=(
                    ("bay", bay_slot.key()),
                    ("sacrifice", slot.key()),
                    ("cost", cost),
                    ("target_mv", sac_mv + 1),
                ),
                equivalence_key=("bay", slot.key(), sac_mv + 1, cost),
                label=f"Activate Bay; sacrifice {slot.name or slot.mode}",
                decision_stage=DECISION_COMMIT,
                source=BAY,
            )
        )
        serial += 1
    return tuple(rows)


def bay_activation_request(state, information: InformationState, *, horizon: int, objective="win_by_horizon", policy_id="base", caverns_live=None):
    return DecisionRequest(
        observation=make_policy_view(state, information, caverns_live=caverns_live),
        actions=bay_activation_intents(state),
        context=PolicyDecisionContext(
            horizon=horizon,
            objective=objective,
            policy_id=policy_id,
            decision_id="bay.activation",
            decision_stage=DECISION_COMMIT,
        ),
    )


def resolve_bay_activation(state, action: ActionIntent):
    legal = {candidate.canonical_key(): candidate for candidate in bay_activation_intents(state)}
    if action.canonical_key() not in legal:
        raise ValueError("Repurposing Bay activation is not legal")
    params = dict(action.parameters)
    bay_slot = _slot_from_parameter(tuple(params["bay"]))
    sac_slot = _slot_from_parameter(tuple(params["sacrifice"]))
    cost = int(params["cost"])
    target_mv = int(params["target_mv"])

    paid = solver.pay(state, cost, 0)
    bay_index = _slot_index(paid, bay_slot)
    paid = solver.update_perm(paid, bay_index, tapped=True)
    sac_index = _slot_index(paid, sac_slot)
    paid = solver.remove_perm(paid, sac_index)
    paid = solver.add_trace(paid, f"Repurposing Bay activation costs paid; required target MV {target_mv}")

    legal_cards = (
        card for card in paid.library
        if card in solver.ARTIFACTS
        and solver.mana_value(card) == target_mv
        and not solver.cage_blocks_library_battlefield_entry(paid, card)
    )
    search = _search_event(
        legal_cards,
        source=BAY,
        context=f"Repurposing Bay exact MV {target_mv}",
    )
    ctx = RemainingSearchContext(
        source=BAY,
        decision_id="bay.search.target",
        contingent_on=action.action_id,
        target_mv=target_mv,
    )
    env = TransitionEnvelope(
        true_state=paid,
        observations=ObservationBatch((search,)),
        pending_decision=PendingDecisionSpec(
            decision_id=ctx.decision_id,
            kind=TARGET_KIND,
            source=BAY,
            decision_stage=DECISION_POST_OBSERVATION,
            contingent_on=action.action_id,
        ),
    )
    return env, ctx, search


def bay_target_request(state, information, ctx, search, *, horizon, objective="win_by_horizon", policy_id="base", caverns_live=None):
    return _target_request(
        state, information, ctx, search,
        horizon=horizon, objective=objective, policy_id=policy_id, caverns_live=caverns_live,
    )


def resolve_bay_target(state, ctx, search, action):
    target = _chosen_target(action, search)
    if not target:
        shuffled = replace(state, library=solver.shuffled_library(state, "bay:no-target:staged"))
        shuffled = solver.add_trace(shuffled, "Repurposing Bay finds no card; shuffle")
        return TransitionEnvelope(shuffled, _shuffle_event(BAY))
    lib = list(state.library)
    lib.remove(target)
    searched = replace(state, library=tuple(lib))
    shuffled = replace(searched, library=solver.shuffled_library(searched, "bay:" + target))
    entered = solver.add_perm(shuffled, target, sick=target in solver.CREATURES)
    entered = solver.add_trace(entered, f"Repurposing Bay -> {target}; shuffle")
    return _deferred_etb(entered, BAY, target, ctx.decision_id)


# ---------------------------------------------------------------------------
# Tezzeret -3
# ---------------------------------------------------------------------------


def tezzeret_minus3_intents(state) -> Tuple[ActionIntent, ...]:
    rows = []
    for index, perm in enumerate(state.battlefield):
        if perm.name == TEZZ and perm.mode != "tez_used" and perm.counters >= 3:
            rows.append(
                ActionIntent(
                    action_id=f"tezzeret.minus3.{index}",
                    kind="activate_tezzeret_minus3",
                    parameters=(("battlefield_index", index),),
                    equivalence_key=("tezzeret_minus3",),
                    label="Tezzeret -3",
                    decision_stage=DECISION_COMMIT,
                    source=TEZZ,
                )
            )
    return tuple(rows)


def tezzeret_minus3_request(state, information, *, horizon, objective="win_by_horizon", policy_id="base", caverns_live=None):
    return DecisionRequest(
        observation=make_policy_view(state, information, caverns_live=caverns_live),
        actions=tezzeret_minus3_intents(state),
        context=PolicyDecisionContext(horizon=horizon, objective=objective, policy_id=policy_id, decision_id="tezzeret.minus3", decision_stage=DECISION_COMMIT),
    )


def resolve_tezzeret_minus3(state, action):
    legal = {candidate.canonical_key(): candidate for candidate in tezzeret_minus3_intents(state)}
    if action.canonical_key() not in legal:
        raise ValueError("Tezzeret -3 is not legal")
    index = int(dict(action.parameters)["battlefield_index"])
    perm = state.battlefield[index]
    activated = solver.update_perm(state, index, counters=perm.counters - 3, mode="tez_used")
    search = _search_event(
        (card for card in activated.library if card in solver.ARTIFACTS and solver.mana_value(card) <= 1),
        source=TEZZ,
        context="Tezzeret -3 artifact MV <= 1",
    )
    ctx = RemainingSearchContext(TEZZ, "tezzeret.search.target", action.action_id, target_mv=1)
    env = TransitionEnvelope(
        true_state=activated,
        observations=ObservationBatch((search,)),
        pending_decision=PendingDecisionSpec(ctx.decision_id, TARGET_KIND, TEZZ, contingent_on=action.action_id),
    )
    return env, ctx, search


def tezzeret_target_request(state, information, ctx, search, *, horizon, objective="win_by_horizon", policy_id="base", caverns_live=None):
    return _target_request(state, information, ctx, search, horizon=horizon, objective=objective, policy_id=policy_id, caverns_live=caverns_live)


def resolve_tezzeret_target(state, ctx, search, action):
    target = _chosen_target(action, search)
    if target:
        moved = solver.move_library_to_hand(state, target)
        shuffled = replace(moved, library=solver.shuffled_library(moved, "tezz:" + target))
        shuffled = solver.add_trace(shuffled, f"Tezzeret -3 -> {target}")
    else:
        shuffled = replace(state, library=solver.shuffled_library(state, "tezz:no-target"))
        shuffled = solver.add_trace(shuffled, "Tezzeret -3 finds no card; shuffle")
    return TransitionEnvelope(shuffled, _shuffle_event(TEZZ))


# ---------------------------------------------------------------------------
# Saga III
# ---------------------------------------------------------------------------


def begin_saga3_search(state):
    if not state.saga3_pending:
        raise ValueError("Saga III is not pending")
    base = replace(state, saga3_pending=False)
    search = _search_event(
        (card for card in base.library if card in solver.SAGA_TARGETS),
        source=SAGA,
        context="Urza's Saga chapter III",
    )
    ctx = RemainingSearchContext(SAGA, "saga3.search.target", "saga3.trigger")
    env = TransitionEnvelope(
        true_state=base,
        observations=ObservationBatch((search,)),
        pending_decision=PendingDecisionSpec(ctx.decision_id, TARGET_KIND, SAGA, contingent_on="saga3.trigger"),
    )
    return env, ctx, search


def saga3_target_request(state, information, ctx, search, *, horizon, objective="win_by_horizon", policy_id="base", caverns_live=None):
    return _target_request(state, information, ctx, search, horizon=horizon, objective=objective, policy_id=policy_id, caverns_live=caverns_live)


def resolve_saga3_target(state, ctx, search, action):
    target = _chosen_target(action, search)
    if target:
        lib = list(state.library)
        lib.remove(target)
        searched = replace(state, library=tuple(lib))
        shuffled = replace(searched, library=solver.shuffled_library(searched, "saga:" + target))
        entered = solver.add_perm(shuffled, target, sick=target in solver.CREATURES)
        entered = solver._sacrifice_final_saga_if_present(entered)
        entered = solver.add_trace(entered, f"Saga III puts {target} onto battlefield; shuffle")
        return _deferred_etb(entered, SAGA, target, ctx.decision_id)
    shuffled = replace(state, library=solver.shuffled_library(state, "saga:no-target"))
    shuffled = solver._sacrifice_final_saga_if_present(shuffled)
    shuffled = solver.add_trace(shuffled, "Saga III search finds no card; shuffle; final chapter resolves")
    return TransitionEnvelope(shuffled, _shuffle_event(SAGA))


# ---------------------------------------------------------------------------
# Scour for Scrap
# ---------------------------------------------------------------------------


def scour_cast_intents(state) -> Tuple[ActionIntent, ...]:
    if SCOUR not in state.hand:
        return ()
    generic, blue = solver.spell_cost(state, SCOUR)
    if not solver.can_pay(state, generic, blue):
        return ()
    gy_artifacts = tuple(sorted(set(state.graveyard) & solver.ARTIFACTS))
    rows = [
        ActionIntent(
            action_id="scour.cast.library",
            kind="cast_scour",
            parameters=(("mode", "library"), ("graveyard_target", ""), ("generic", generic), ("blue", blue)),
            equivalence_key=("scour", "library"),
            label="Cast Scour: library mode",
            decision_stage=DECISION_COMMIT,
            source=SCOUR,
        )
    ]
    for index, card in enumerate(gy_artifacts):
        for mode in ("graveyard", "both"):
            rows.append(
                ActionIntent(
                    action_id=f"scour.cast.{mode}.{index:02d}",
                    kind="cast_scour",
                    parameters=(("mode", mode), ("graveyard_target", card), ("generic", generic), ("blue", blue)),
                    equivalence_key=("scour", mode, card),
                    label=f"Cast Scour: {mode}; target {card}",
                    decision_stage=DECISION_COMMIT,
                    source=SCOUR,
                )
            )
    return tuple(rows)


def scour_cast_request(state, information, *, horizon, objective="win_by_horizon", policy_id="base", caverns_live=None):
    return DecisionRequest(
        observation=make_policy_view(state, information, caverns_live=caverns_live),
        actions=scour_cast_intents(state),
        context=PolicyDecisionContext(horizon=horizon, objective=objective, policy_id=policy_id, decision_id="scour.cast", decision_stage=DECISION_COMMIT),
    )


def resolve_scour_cast(state, action):
    legal = {candidate.canonical_key(): candidate for candidate in scour_cast_intents(state)}
    if action.canonical_key() not in legal:
        raise ValueError("Scour cast action is not legal")
    params = dict(action.parameters)
    mode = str(params["mode"])
    gy_target = str(params["graveyard_target"])
    generic = int(params["generic"])
    blue = int(params["blue"])
    paid = solver.pay(state, generic, blue)
    paid = replace(
        paid,
        hand=solver.remove_one(paid.hand, SCOUR),
        graveyard=paid.graveyard + (SCOUR,),
        spell_cast_this_turn=True,
    )
    paid = solver.vfc_noncreature_cast_trigger(paid, SCOUR)
    paid = solver.add_trace(paid, f"cast Scour for Scrap; mode={mode}" + (f"; grave target={gy_target}" if gy_target else ""))

    if mode == "graveyard":
        if gy_target not in state.graveyard:
            raise ValueError("Scour graveyard target was not legal when cast")
        gy = list(paid.graveyard)
        gy.remove(gy_target)
        resolved = replace(paid, graveyard=tuple(gy), hand=paid.hand + (gy_target,))
        resolved = solver.add_trace(resolved, f"Scour returns {gy_target} from graveyard")
        return TransitionEnvelope(resolved), None, None

    search = _search_event(
        (card for card in paid.library if card in solver.ARTIFACTS),
        source=SCOUR,
        context=f"Scour for Scrap mode={mode}",
    )
    ctx = RemainingSearchContext(
        SCOUR,
        "scour.search.target",
        action.action_id,
        graveyard_target=gy_target,
        mode=mode,
    )
    env = TransitionEnvelope(
        true_state=paid,
        observations=ObservationBatch((search,)),
        pending_decision=PendingDecisionSpec(ctx.decision_id, TARGET_KIND, SCOUR, contingent_on=action.action_id),
    )
    return env, ctx, search


def scour_target_request(state, information, ctx, search, *, horizon, objective="win_by_horizon", policy_id="base", caverns_live=None):
    return _target_request(state, information, ctx, search, horizon=horizon, objective=objective, policy_id=policy_id, caverns_live=caverns_live)


def resolve_scour_target(state, ctx, search, action):
    target = _chosen_target(action, search)
    resolved = state
    if target:
        resolved = solver.move_library_to_hand(resolved, target)
        salt = "scourboth:" + target + ctx.graveyard_target if ctx.mode == "both" else "scour:" + target
        resolved = replace(resolved, library=solver.shuffled_library(resolved, salt))
    else:
        resolved = replace(resolved, library=solver.shuffled_library(resolved, "scour:no-target:" + ctx.mode))
    if ctx.mode == "both":
        if ctx.graveyard_target not in resolved.graveyard:
            raise ValueError("Scour graveyard target became unavailable")
        gy = list(resolved.graveyard)
        gy.remove(ctx.graveyard_target)
        resolved = replace(resolved, graveyard=tuple(gy), hand=resolved.hand + (ctx.graveyard_target,))
    label = "Scour " + (f"tutors {target}" if target else "finds no library card")
    if ctx.mode == "both":
        label += f" + returns {ctx.graveyard_target}"
    resolved = solver.add_trace(resolved, label)
    return TransitionEnvelope(resolved, _shuffle_event(SCOUR))


def information_after_remaining_search(prior: InformationState, envelope: TransitionEnvelope) -> InformationState:
    return apply_observation_batch(prior, envelope.observations)
