#!/usr/bin/env python3
"""Typed Phase-2 runtime bridge for Transmute Artifact.

Transmute differs from Reshape: the artifact is sacrificed during resolution, not
as a casting cost. Therefore any leaves/dies trigger caused by that sacrifice waits
until the whole Transmute spell has finished resolving. If the searched artifact
also creates ETB triggers during that resolution, all of those waiting controlled
triggers are put on the stack together afterward and may be ordered by the policy.

For Sewer-veillance Cam, the LTB trigger is remembered during resolution but its
target is not chosen until Transmute has completely finished. That is important:
the searched permanent may have entered by then and is part of the legal target set.
Only after the target is committed do we order Cam's trigger with any waiting ETB
triggers from the searched artifact.

Sequence:
    cast/pay UU -> real cast-trigger stack -> resolve Transmute
      -> choose sacrifice -> search observation -> choose target
      -> optional difference-payment decision (mana abilities legal here)
      -> target enters or goes to graveyard -> shuffle -> spell finishes
      -> choose any Cam LTB target on the final battlefield
      -> queue/order all waiting death/LTB/artifact-entry triggers
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
    _artifact_entry_trigger_objects,
    _cast_trigger_objects,
    _queue_simultaneous_objects,
)
from non_oracle_runtime_value_key import WINDOW_POST_OBSERVATION, WINDOW_PRIORITY
from non_oracle_x_artifact_tutor_runtime import _remove_artifact_for_reshape_cost
from trigger_order_adapter import post_cast_observations
from transmute_artifact_adapter import (
    CARD,
    _artifact_mv_for_sacrifice,
    _resolve_selector,
    transmute_difference_payment_options,
    transmute_payment_intents,
    transmute_sacrifice_intents,
    transmute_target_intents,
)

MAIN_USE_TRANSMUTE_ARTIFACT = "main_use_transmute_artifact"
SPELL_TRANSMUTE = "transmute_artifact_spell"
RUNTIME_TRANSMUTE_SACRIFICE = "runtime_transmute_sacrifice"
RUNTIME_TRANSMUTE_TARGET = "runtime_transmute_target"
RUNTIME_TRANSMUTE_PAYMENT = "runtime_transmute_payment"


def transmute_runtime_intents(runtime: NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    state = runtime.true_state
    if CARD not in state.hand or not solver.can_pay(state, 0, 2):
        return ()
    # A cast with no artifact to sacrifice is legal but cannot advance the goldfish
    # objective. Omit that dominated dead action from the deterministic rollout.
    if not any(solver.is_artifact_perm(p) for p in state.battlefield):
        return ()
    return (
        ActionIntent(
            action_id="main.transmute_artifact.cast",
            kind=MAIN_USE_TRANSMUTE_ARTIFACT,
            parameters=(("blue_required", 2), ("source", CARD)),
            equivalence_key=(MAIN_USE_TRANSMUTE_ARTIFACT, CARD, 2),
            label="Cast Transmute Artifact",
            decision_stage=DECISION_COMMIT,
            source=CARD,
        ),
    )


def begin_transmute(runtime: NonOracleRuntimeState, action: ActionIntent) -> NonOracleRuntimeState:
    legal = {candidate.canonical_key() for candidate in transmute_runtime_intents(runtime)}
    if action.canonical_key() not in legal:
        raise ValueError("Transmute Artifact cast is not currently legal")
    state = solver.pay(runtime.true_state, 0, 2)
    if state is None or CARD not in state.hand:
        raise ValueError("Transmute Artifact can no longer pay/commit")
    state = replace(
        state,
        hand=solver.remove_one(state.hand, CARD),
        spell_cast_this_turn=True,
    )
    state = solver.add_trace(state, "Phase2 cast Transmute Artifact")
    runtime = replace(runtime, true_state=state)

    spell, stack = runtime.stack.allocate(
        object_type=STACK_SPELL,
        kind=SPELL_TRANSMUTE,
        source="hand",
        card=CARD,
        payload=(("mana_spent", 2),),
        public_payload=(("mana_spent", 2),),
        strategic_payload=(("mana_spent", 2),),
    )
    runtime = replace(runtime, stack=stack.push_existing((spell,)))
    info = apply_observation_batch(
        runtime.information,
        post_cast_observations(state, CARD, cast_from_library_top=False),
    )
    runtime = replace(runtime, information=info)
    triggers, allocated = _cast_trigger_objects(runtime, CARD, 2, spell.object_id)
    runtime = replace(runtime, stack=allocated)
    return _queue_simultaneous_objects(runtime, triggers, source=f"cast {CARD}")


def handles_transmute_stack_top(runtime: NonOracleRuntimeState) -> bool:
    if runtime.pending is not None:
        return False
    top = runtime.stack.top()
    return bool(top and top.kind == SPELL_TRANSMUTE)


def handles_transmute_pending(runtime: NonOracleRuntimeState) -> bool:
    return bool(runtime.pending and runtime.pending.kind in {
        RUNTIME_TRANSMUTE_SACRIFICE,
        RUNTIME_TRANSMUTE_TARGET,
        RUNTIME_TRANSMUTE_PAYMENT,
    })


def _begin_sacrifice_decision(runtime: NonOracleRuntimeState, spell_id: str) -> NonOracleRuntimeState:
    actions = transmute_sacrifice_intents(runtime.true_state)
    if not actions:
        state = replace(runtime.true_state, graveyard=runtime.true_state.graveyard + (CARD,))
        state = solver.add_trace(state, "Phase2 Transmute resolves with no artifact to sacrifice")
        return replace(
            runtime,
            true_state=state,
            window=RuntimeDecisionWindow(WINDOW_PRIORITY),
        )
    spec = PendingDecisionSpec(
        decision_id="runtime.transmute.sacrifice",
        kind="transmute_choose_sacrifice",
        source=CARD,
        decision_stage=DECISION_COMMIT,
        contingent_on=spell_id,
    )
    return replace(
        runtime,
        pending=RuntimePendingDecision(
            spec=spec,
            kind=RUNTIME_TRANSMUTE_SACRIFICE,
            payload=(),
        ),
        window=RuntimeDecisionWindow(WINDOW_POST_OBSERVATION),
    )


def apply_transmute_stack_action(runtime: NonOracleRuntimeState, action: ActionIntent) -> NonOracleRuntimeState:
    if action.action_id != ACTION_PASS_PRIORITY or action.kind != "pass_priority":
        raise ValueError("Transmute Artifact resolves only after passing priority")
    obj, remaining = runtime.stack.pop_top()
    if obj is None or obj.kind != SPELL_TRANSMUTE:
        raise ValueError("top stack object is not Transmute Artifact")
    return _begin_sacrifice_decision(replace(runtime, stack=remaining), obj.object_id)


def _search_observation(state) -> SearchZoneObservation:
    return SearchZoneObservation(
        zone="library",
        legal_cards=tuple(sorted(set(state.library) & solver.ARTIFACTS)),
        context=CARD,
        may_fail_to_find=True,
    )


def _sacrifice_request(runtime, *, horizon, objective, policy_id, caverns_live):
    return DecisionRequest(
        observation=runtime.policy_view(caverns_live=caverns_live),
        actions=transmute_sacrifice_intents(runtime.true_state),
        context=PolicyDecisionContext(
            horizon=horizon,
            objective=objective,
            policy_id=policy_id,
            decision_id=runtime.pending.spec.decision_id,
            decision_stage=DECISION_COMMIT,
        ),
    )


def _target_request(runtime, *, horizon, objective, policy_id, caverns_live):
    data = dict(runtime.pending.payload)
    search = SearchZoneObservation(
        zone="library",
        legal_cards=tuple(data["legal_targets"]),
        context=CARD,
        may_fail_to_find=True,
    )
    return DecisionRequest(
        observation=runtime.policy_view(caverns_live=caverns_live),
        actions=transmute_target_intents(search),
        context=PolicyDecisionContext(
            horizon=horizon,
            objective=objective,
            policy_id=policy_id,
            decision_id=runtime.pending.spec.decision_id,
            decision_stage=DECISION_POST_OBSERVATION,
        ),
    )


def _payment_request(runtime, *, horizon, objective, policy_id, caverns_live):
    data = dict(runtime.pending.payload)
    difference = int(data["difference"])
    options = transmute_difference_payment_options(runtime.true_state, difference)
    return DecisionRequest(
        observation=runtime.policy_view(caverns_live=caverns_live),
        actions=transmute_payment_intents(options, difference),
        context=PolicyDecisionContext(
            horizon=horizon,
            objective=objective,
            policy_id=policy_id,
            decision_id=runtime.pending.spec.decision_id,
            decision_stage=DECISION_POST_OBSERVATION,
        ),
    )


def transmute_pending_request(
    runtime: NonOracleRuntimeState,
    *,
    horizon: int,
    objective: str,
    policy_id: str,
    caverns_live=None,
) -> DecisionRequest:
    if runtime.pending is None:
        raise ValueError("no pending Transmute decision")
    if runtime.pending.kind == RUNTIME_TRANSMUTE_SACRIFICE:
        return _sacrifice_request(
            runtime, horizon=horizon, objective=objective, policy_id=policy_id, caverns_live=caverns_live
        )
    if runtime.pending.kind == RUNTIME_TRANSMUTE_TARGET:
        return _target_request(
            runtime, horizon=horizon, objective=objective, policy_id=policy_id, caverns_live=caverns_live
        )
    if runtime.pending.kind == RUNTIME_TRANSMUTE_PAYMENT:
        return _payment_request(
            runtime, horizon=horizon, objective=objective, policy_id=policy_id, caverns_live=caverns_live
        )
    raise ValueError("not a Transmute pending decision")


def _queue_waiting_after_resolution(
    runtime: NonOracleRuntimeState,
    *,
    entered_target: str,
    prized_died: bool,
    cam_died: bool,
) -> NonOracleRuntimeState:
    objects = []
    stack = runtime.stack
    if entered_target:
        runtime = replace(runtime, stack=stack)
        entry_objects, stack = _artifact_entry_trigger_objects(runtime, (entered_target,))
        objects.extend(entry_objects)
    if prized_died:
        death, stack = stack.allocate(
            object_type=STACK_TRIGGER,
            kind="prized_dies_treasure",
            source="Prized Statue",
            card="Prized Statue",
        )
        objects.append(death)
    runtime = replace(runtime, stack=stack)
    if cam_died:
        return queue_cam_ltb(
            runtime,
            extra_objects=tuple(objects),
            count=1,
            source="Transmute resolution Cam LTB",
        )
    return _queue_simultaneous_objects(runtime, tuple(objects), source="resolve Transmute Artifact")


def _finish_transmute(
    runtime: NonOracleRuntimeState,
    *,
    target: str,
    prized_died: bool,
    cam_died: bool,
    target_to_graveyard: bool = False,
    shuffle_salt: str,
) -> NonOracleRuntimeState:
    state = runtime.true_state
    entered = ""
    if target:
        if target_to_graveyard:
            state = replace(state, graveyard=state.graveyard + (target,))
        else:
            state = solver.add_perm(state, target, sick=target in solver.CREATURES)
            entered = target
    state = replace(state, library=solver.shuffled_library(state, shuffle_salt))
    state = replace(state, graveyard=state.graveyard + (CARD,))
    state = solver.check_win(solver.add_trace(state, "Phase2 Transmute Artifact finishes; shuffle"))
    info = apply_observation_batch(
        runtime.information,
        ObservationBatch((ShuffleObservation(CARD),)),
    )
    runtime = replace(
        runtime,
        true_state=solver._ensure_oracle_instance_tags(state),
        information=info,
        pending=None,
        window=RuntimeDecisionWindow(WINDOW_PRIORITY),
    )
    return _queue_waiting_after_resolution(
        runtime,
        entered_target=entered,
        prized_died=prized_died,
        cam_died=cam_died,
    )


def _apply_sacrifice(runtime: NonOracleRuntimeState, action: ActionIntent) -> NonOracleRuntimeState:
    request = _sacrifice_request(
        runtime, horizon=max(1, runtime.true_state.turn), objective="win_by_horizon", policy_id="runtime", caverns_live=None
    )
    legal = {candidate.canonical_key() for candidate in request.actions}
    if action.canonical_key() not in legal:
        raise ValueError("Transmute sacrifice is no longer legal")
    params = dict(action.parameters)
    signature = tuple(params["signature"])
    ordinal = int(params["ordinal"])
    index = _resolve_selector(runtime.true_state, signature, ordinal)
    perm = runtime.true_state.battlefield[index]
    mv = _artifact_mv_for_sacrifice(perm)
    state, sacrificed = _remove_artifact_for_reshape_cost(runtime.true_state, index)
    state = solver.add_trace(state, f"Phase2 Transmute sacrifices {sacrificed.name or sacrificed.mode}")
    search = _search_observation(state)
    info = apply_observation_batch(runtime.information, ObservationBatch((search,)))
    spec = PendingDecisionSpec(
        decision_id="runtime.transmute.target",
        kind="transmute_choose_target",
        source=CARD,
        decision_stage=DECISION_POST_OBSERVATION,
        contingent_on=runtime.pending.spec.decision_id,
    )
    return replace(
        runtime,
        true_state=solver._ensure_oracle_instance_tags(state),
        information=info,
        pending=RuntimePendingDecision(
            spec=spec,
            kind=RUNTIME_TRANSMUTE_TARGET,
            payload=(
                ("cam_died", sacrificed.name == "Sewer-veillance Cam"),
                ("legal_targets", tuple(search.legal_cards)),
                ("prized_died", sacrificed.name == "Prized Statue"),
                ("sacrificed_mv", int(mv)),
                ("sacrificed_name", sacrificed.name),
            ),
        ),
        window=RuntimeDecisionWindow(WINDOW_POST_OBSERVATION),
    )


def _apply_target(runtime: NonOracleRuntimeState, action: ActionIntent) -> NonOracleRuntimeState:
    request = _target_request(
        runtime, horizon=max(1, runtime.true_state.turn), objective="win_by_horizon", policy_id="runtime", caverns_live=None
    )
    legal = {candidate.canonical_key() for candidate in request.actions}
    if action.canonical_key() not in legal:
        raise ValueError("Transmute target is not legal for the observed search")
    data = dict(runtime.pending.payload)
    target = str(dict(action.parameters).get("target", ""))
    prized_died = bool(data["prized_died"])
    cam_died = bool(data["cam_died"])
    sacrificed_name = str(data["sacrificed_name"])
    if not target:
        return _finish_transmute(
            runtime,
            target="",
            prized_died=prized_died,
            cam_died=cam_died,
            shuffle_salt=f"transmute:no-target:{sacrificed_name}",
        )
    if target not in tuple(data["legal_targets"]) or target not in runtime.true_state.library:
        raise ValueError("chosen Transmute target is absent or was not revealed")

    library = list(runtime.true_state.library)
    library.remove(target)
    state = replace(runtime.true_state, library=tuple(library))
    difference = max(0, solver.mana_value(target) - int(data["sacrificed_mv"]))
    runtime = replace(runtime, true_state=state)
    if difference <= 0:
        return _finish_transmute(
            runtime,
            target=target,
            prized_died=prized_died,
            cam_died=cam_died,
            shuffle_salt=f"transmute-paid:{sacrificed_name}:{target}",
        )

    spec = PendingDecisionSpec(
        decision_id="runtime.transmute.payment",
        kind="transmute_pay_difference",
        source=CARD,
        decision_stage=DECISION_POST_OBSERVATION,
        contingent_on=runtime.pending.spec.decision_id,
    )
    return replace(
        runtime,
        pending=RuntimePendingDecision(
            spec=spec,
            kind=RUNTIME_TRANSMUTE_PAYMENT,
            payload=(
                ("cam_died", cam_died),
                ("difference", int(difference)),
                ("prized_died", prized_died),
                ("sacrificed_name", sacrificed_name),
                ("target", target),
            ),
        ),
        window=RuntimeDecisionWindow(WINDOW_POST_OBSERVATION),
    )


def _apply_payment(runtime: NonOracleRuntimeState, action: ActionIntent) -> NonOracleRuntimeState:
    request = _payment_request(
        runtime, horizon=max(1, runtime.true_state.turn), objective="win_by_horizon", policy_id="runtime", caverns_live=None
    )
    legal = {candidate.canonical_key() for candidate in request.actions}
    if action.canonical_key() not in legal:
        raise ValueError("Transmute difference payment is not legal")
    data = dict(runtime.pending.payload)
    difference = int(data["difference"])
    target = str(data["target"])
    prized_died = bool(data["prized_died"])
    cam_died = bool(data["cam_died"])
    sacrificed_name = str(data["sacrificed_name"])
    choice = str(dict(action.parameters).get("choice", ""))

    if choice == "decline":
        return _finish_transmute(
            runtime,
            target=target,
            prized_died=prized_died,
            cam_died=cam_died,
            target_to_graveyard=True,
            shuffle_salt=f"transmute:{sacrificed_name}:{target}",
        )
    if choice != "pay":
        raise ValueError("unknown Transmute payment choice")
    options = {
        candidate.canonical_key(): paid_state
        for candidate, paid_state in transmute_difference_payment_options(runtime.true_state, difference)
    }
    paid_state = options.get(action.canonical_key())
    if paid_state is None:
        raise ValueError("Transmute payment plan is no longer legal")
    runtime = replace(runtime, true_state=paid_state)
    return _finish_transmute(
        runtime,
        target=target,
        prized_died=prized_died,
        cam_died=cam_died,
        shuffle_salt=f"transmute-paid:{sacrificed_name}:{target}",
    )


def apply_transmute_pending(runtime: NonOracleRuntimeState, action: ActionIntent) -> NonOracleRuntimeState:
    if runtime.pending is None:
        raise ValueError("no pending Transmute decision")
    if runtime.pending.kind == RUNTIME_TRANSMUTE_SACRIFICE:
        return _apply_sacrifice(runtime, action)
    if runtime.pending.kind == RUNTIME_TRANSMUTE_TARGET:
        return _apply_target(runtime, action)
    if runtime.pending.kind == RUNTIME_TRANSMUTE_PAYMENT:
        return _apply_payment(runtime, action)
    raise ValueError("not a Transmute pending decision")
