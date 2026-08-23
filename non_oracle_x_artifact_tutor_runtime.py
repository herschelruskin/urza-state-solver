#!/usr/bin/env python3
"""Typed Phase-2 runtime bridge for Reshape and Whir of Invention.

The Phase-1 X-artifact adapter established the anti-clairvoyance boundary: X,
payment, and (for Reshape) the sacrifice are committed before the library is
searched. This bridge preserves that boundary while placing the actual spell and
all cast-time triggers on the Phase-2 stack.

Important timing:
- Reshape sacrifices as an additional casting cost. Prized Statue and Cam triggers
  therefore wait until casting finishes; Cam chooses its target before those
  simultaneous controlled triggers are ordered above Reshape.
- Whir commits X and its exact improvise/payment plan before any search target is
  visible.
- Search targets become policy-visible only when the spell resolves. The selected
  artifact enters during resolution, the library is shuffled, the spell finishes,
  and only then are artifact-entry triggers put on the runtime stack.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Tuple

import urza_solver as solver
from decision_observation import (
    ActionIntent,
    DECISION_COMMIT,
    DECISION_POST_OBSERVATION,
    DecisionRequest,
    ObservationBatch,
    PendingDecisionSpec,
    PolicyDecisionContext,
    SearchZoneObservation,
    ShuffleObservation,
    apply_observation_batch,
)
from non_oracle_cam_runtime import queue_cam_ltb
from non_oracle_runtime import (
    ACTION_PASS_PRIORITY,
    STACK_SPELL,
    STACK_TRIGGER,
    NonOracleRuntimeState,
    RuntimeDecisionWindow,
    RuntimePendingDecision,
    _cast_trigger_objects,
    _queue_simultaneous_objects,
    record_artifact_entry,
)
from non_oracle_runtime_value_key import WINDOW_POST_OBSERVATION, WINDOW_PRIORITY
from trigger_order_adapter import post_cast_observations
from x_artifact_search_adapter import (
    RESHAPE,
    WHIR,
    SEARCH_KIND,
    SearchContext,
    _slot_from_parameter,
    _slot_index,
    _target_intents,
    reshape_cast_intents,
    whir_cast_intents,
)

MAIN_USE_X_ARTIFACT_TUTOR = "main_use_x_artifact_tutor"
SPELL_RESHAPE = "x_artifact_reshape_spell"
SPELL_WHIR = "x_artifact_whir_spell"
RUNTIME_X_TARGET = "runtime_x_artifact_target"


def _underlying_cast_intents(runtime: NonOracleRuntimeState, source: str):
    if source == RESHAPE:
        return reshape_cast_intents(runtime.true_state)
    if source == WHIR:
        return whir_cast_intents(runtime.true_state)
    raise ValueError(f"unsupported X artifact tutor {source!r}")


def x_artifact_runtime_intents(runtime: NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    """Expose only pre-search public commitments; never target identities."""
    rows = []
    for source in (RESHAPE, WHIR):
        for candidate in _underlying_cast_intents(runtime, source):
            params = dict(candidate.parameters)
            sacrifice_name = ""
            if source == RESHAPE:
                sacrifice = tuple(params.get("sacrifice", ()))
                sacrifice_name = str(sacrifice[0]) if sacrifice else ""
            rows.append(
                ActionIntent(
                    action_id=f"main.x_artifact.{candidate.action_id}",
                    kind=MAIN_USE_X_ARTIFACT_TUTOR,
                    parameters=(
                        ("cast_parameters", tuple(candidate.parameters)),
                        ("sacrifice_name", sacrifice_name),
                        ("source", source),
                        ("x", int(params["x"])),
                    ),
                    equivalence_key=(
                        MAIN_USE_X_ARTIFACT_TUTOR,
                        source,
                        candidate.strategic_key(),
                    ),
                    label=candidate.label,
                    decision_stage=DECISION_COMMIT,
                    source=source,
                )
            )
    return tuple(rows)


def _find_underlying(runtime: NonOracleRuntimeState, action: ActionIntent):
    params = dict(action.parameters)
    source = str(params["source"])
    cast_parameters = tuple(params["cast_parameters"])
    matches = [
        candidate
        for candidate in _underlying_cast_intents(runtime, source)
        if tuple(candidate.parameters) == cast_parameters
    ]
    if len(matches) != 1:
        raise ValueError("X-artifact tutor commitment is no longer legal")
    return source, matches[0]


def _remove_artifact_for_reshape_cost(state, index: int):
    """Remove one artifact without resolving triggered abilities atomically."""
    battlefield = list(state.battlefield)
    perm = battlefield.pop(index)
    graveyard = state.graveyard
    if (
        perm.name not in {"Clue", "Treasure", "Construct"}
        and perm.mode not in {"clue", "treasure", "construct", "chrome_copy", "chrome_copy_preturn"}
    ):
        graveyard = graveyard + (perm.name,)
    state = replace(state, battlefield=tuple(battlefield), graveyard=graveyard)

    if perm.name == "Uthros Research Craft":
        state = replace(state, uthros_counters=0)
    if perm.name == "The One Ring":
        state = replace(state, ring_counters=0)
    if perm.name == "The Reality Chip":
        state = replace(state, chip_attached=False, chip_target="")
    if state.chip_attached and state.chip_target and perm.name == state.chip_target:
        state = replace(state, chip_attached=False, chip_target="")
        for i, chip in enumerate(state.battlefield):
            if chip.name == "The Reality Chip":
                state = solver.update_perm(state, i, mode="")
                break
    if state.pa_target and perm.name == state.pa_target:
        bf = list(state.battlefield)
        for i in range(len(bf) - 1, -1, -1):
            if bf[i].name == "Power Artifact":
                bf.pop(i)
                state = replace(
                    state,
                    battlefield=tuple(bf),
                    graveyard=state.graveyard + ("Power Artifact",),
                    pa_target="",
                )
                break
    return state, perm


def _allocate_spell(runtime, *, kind: str, source: str, x: int, mana_spent: int):
    spell, stack = runtime.stack.allocate(
        object_type=STACK_SPELL,
        kind=kind,
        source="hand",
        card=source,
        payload=(("x", int(x)), ("mana_spent", int(mana_spent))),
        public_payload=(("x", int(x)), ("mana_spent", int(mana_spent))),
        strategic_payload=(("x", int(x)), ("mana_spent", int(mana_spent))),
    )
    return spell, replace(runtime, stack=stack.push_existing((spell,)))


def _finish_cast_triggers(
    runtime,
    *,
    source: str,
    spell,
    mana_spent: int,
    prized_died: bool,
    cam_died: bool = False,
):
    info = apply_observation_batch(
        runtime.information,
        post_cast_observations(runtime.true_state, source, cast_from_library_top=False),
    )
    runtime = replace(runtime, information=info)
    triggers, allocated = _cast_trigger_objects(
        runtime, source, int(mana_spent), spell.object_id
    )
    extra = []
    if prized_died:
        death, allocated = allocated.allocate(
            object_type=STACK_TRIGGER,
            kind="prized_dies_treasure",
            source="Prized Statue",
            card="Prized Statue",
        )
        extra.append(death)
    runtime = replace(runtime, stack=allocated)
    simultaneous = tuple(triggers) + tuple(extra)
    if cam_died:
        return queue_cam_ltb(
            runtime,
            extra_objects=simultaneous,
            count=1,
            source="Reshape additional-cost Cam LTB",
        )
    return _queue_simultaneous_objects(
        runtime,
        simultaneous,
        source=f"cast {source}",
    )


def begin_x_artifact_tutor(runtime: NonOracleRuntimeState, action: ActionIntent) -> NonOracleRuntimeState:
    legal = {candidate.canonical_key() for candidate in x_artifact_runtime_intents(runtime)}
    if action.canonical_key() not in legal:
        raise ValueError("X-artifact tutor commitment is not currently legal")
    source, underlying = _find_underlying(runtime, action)
    params = dict(underlying.parameters)
    state = runtime.true_state
    x = int(params["x"])
    prized_died = False
    cam_died = False

    if source == RESHAPE:
        generic = int(params["generic_paid"])
        paid = solver.pay(state, generic, 2)
        if paid is None or source not in paid.hand:
            raise ValueError("Reshape can no longer pay its committed cost")
        paid = replace(
            paid,
            hand=solver.remove_one(paid.hand, source),
            spell_cast_this_turn=True,
        )
        slot = _slot_from_parameter(tuple(params["sacrifice"]))
        index = _slot_index(paid, slot)
        if not solver.is_artifact_perm(paid.battlefield[index]):
            raise ValueError("Reshape sacrifice is no longer an artifact")
        paid, sacrificed = _remove_artifact_for_reshape_cost(paid, index)
        prized_died = sacrificed.name == "Prized Statue"
        cam_died = sacrificed.name == "Sewer-veillance Cam"
        mana_spent = int(generic + 2)
        paid = solver.add_trace(
            paid,
            f"Phase2 cast Reshape X={x}; sacrifice {sacrificed.name or sacrificed.mode} as additional cost",
        )
        runtime = replace(runtime, true_state=solver._ensure_oracle_instance_tags(paid))
        spell, runtime = _allocate_spell(
            runtime, kind=SPELL_RESHAPE, source=source, x=x, mana_spent=mana_spent
        )
        return _finish_cast_triggers(
            runtime,
            source=source,
            spell=spell,
            mana_spent=mana_spent,
            prized_died=prized_died,
            cam_died=cam_died,
        )

    if source == WHIR:
        paid = solver.pay(state, 0, 3)
        if paid is None or source not in paid.hand:
            raise ValueError("Whir can no longer pay its colored cost")
        for raw in tuple(params["improvise"]):
            slot = _slot_from_parameter(tuple(raw))
            index = _slot_index(paid, slot)
            if paid.battlefield[index].tapped or not solver.is_artifact_perm(paid.battlefield[index]):
                raise ValueError("committed Whir improvise permanent is no longer legal")
            paid = solver.update_perm(paid, index, tapped=True)
        floating = int(params["floating_generic"])
        paid = solver.pay(paid, floating, 0)
        if paid is None:
            raise ValueError("Whir generic remainder can no longer be paid")
        paid = replace(
            paid,
            hand=solver.remove_one(paid.hand, source),
            spell_cast_this_turn=True,
        )
        mana_spent = int(3 + floating)
        paid = solver.add_trace(paid, f"Phase2 cast Whir X={x}; payment plan committed")
        runtime = replace(runtime, true_state=solver._ensure_oracle_instance_tags(paid))
        spell, runtime = _allocate_spell(
            runtime, kind=SPELL_WHIR, source=source, x=x, mana_spent=mana_spent
        )
        return _finish_cast_triggers(
            runtime,
            source=source,
            spell=spell,
            mana_spent=mana_spent,
            prized_died=False,
            cam_died=False,
        )

    raise AssertionError("unhandled X-artifact tutor source")


def _search_pending(runtime: NonOracleRuntimeState, obj) -> NonOracleRuntimeState:
    x = int(dict(obj.payload)["x"])
    legal_targets = tuple(
        sorted({
            card for card in runtime.true_state.library
            if card in solver.ARTIFACTS
            and solver.mana_value(card) <= x
            and not solver.cage_blocks_library_battlefield_entry(runtime.true_state, card)
        })
    )
    search = SearchZoneObservation(
        zone="library",
        legal_cards=legal_targets,
        context=f"{obj.card} X={x}",
        may_fail_to_find=True,
    )
    info = apply_observation_batch(runtime.information, ObservationBatch((search,)))
    spec = PendingDecisionSpec(
        decision_id=f"runtime.x_artifact.{obj.card}.target",
        kind=SEARCH_KIND,
        source=obj.card,
        decision_stage=DECISION_POST_OBSERVATION,
        contingent_on=obj.object_id,
    )
    return replace(
        runtime,
        information=info,
        pending=RuntimePendingDecision(
            spec=spec,
            kind=RUNTIME_X_TARGET,
            payload=(("legal_targets", legal_targets), ("source", obj.card), ("x", x)),
        ),
        window=RuntimeDecisionWindow(WINDOW_POST_OBSERVATION),
    )


def handles_x_artifact_stack_top(runtime: NonOracleRuntimeState) -> bool:
    if runtime.pending is not None:
        return False
    top = runtime.stack.top()
    return bool(top and top.kind in {SPELL_RESHAPE, SPELL_WHIR})


def handles_x_artifact_pending(runtime: NonOracleRuntimeState) -> bool:
    return bool(runtime.pending and runtime.pending.kind == RUNTIME_X_TARGET)


def x_artifact_pending_request(
    runtime: NonOracleRuntimeState,
    *,
    horizon: int,
    objective: str,
    policy_id: str,
    caverns_live=None,
) -> DecisionRequest:
    pending = runtime.pending
    if pending is None or pending.kind != RUNTIME_X_TARGET:
        raise ValueError("not a pending X-artifact target decision")
    data = dict(pending.payload)
    source = str(data["source"])
    x = int(data["x"])
    search = SearchZoneObservation(
        zone="library",
        legal_cards=tuple(data["legal_targets"]),
        context=f"{source} X={x}",
        may_fail_to_find=True,
    )
    context = SearchContext(source, x, pending.spec.decision_id, pending.spec.contingent_on)
    return DecisionRequest(
        observation=runtime.policy_view(caverns_live=caverns_live),
        actions=_target_intents(context, search),
        context=PolicyDecisionContext(
            horizon=horizon,
            objective=objective,
            policy_id=policy_id,
            decision_id=pending.spec.decision_id,
            decision_stage=DECISION_POST_OBSERVATION,
        ),
    )


def apply_x_artifact_pending(runtime: NonOracleRuntimeState, action: ActionIntent) -> NonOracleRuntimeState:
    pending = runtime.pending
    if pending is None or pending.kind != RUNTIME_X_TARGET:
        raise ValueError("not a pending X-artifact target decision")
    request = x_artifact_pending_request(
        runtime, horizon=max(1, int(runtime.true_state.turn)), objective="win_by_horizon", policy_id="runtime"
    )
    legal = {candidate.canonical_key() for candidate in request.actions}
    if action.canonical_key() not in legal:
        raise ValueError("X-artifact target is not legal for the observed search")
    data = dict(pending.payload)
    source = str(data["source"])
    x = int(data["x"])
    target = str(dict(action.parameters).get("target", ""))
    state = runtime.true_state

    if target:
        if target not in tuple(data["legal_targets"]) or target not in state.library:
            raise ValueError("chosen X-artifact target is absent or was not revealed")
        library = list(state.library)
        library.remove(target)
        state = replace(state, library=tuple(library))
        state = solver.add_perm(state, target, sick=target in solver.CREATURES)

    salt = (
        f"reshape:{target}" if source == RESHAPE and target
        else f"whir:{target}" if source == WHIR and target
        else f"{source.lower().replace(' ', '.')}:no-target:x{x}"
    )
    state = replace(state, library=solver.shuffled_library(state, salt))
    state = replace(state, graveyard=state.graveyard + (source,))
    state = solver.check_win(
        solver.add_trace(state, f"Phase2 {source} X={x} -> {target or 'no card'}; shuffle")
    )
    info = apply_observation_batch(
        runtime.information,
        ObservationBatch((ShuffleObservation(source),)),
    )
    runtime = replace(
        runtime,
        true_state=solver._ensure_oracle_instance_tags(state),
        information=info,
        pending=None,
        window=RuntimeDecisionWindow(WINDOW_PRIORITY),
    )
    if target:
        return record_artifact_entry(runtime, (target,), source=f"resolve {source} -> {target}")
    return runtime
