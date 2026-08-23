#!/usr/bin/env python3
"""Phase-2 runtime bridge for Bay, Saga III, Scour, and Tezzeret -3.

All four effects already have information-faithful Phase-1 search adapters. This
module connects them to the typed Phase-2 stack so their pre-search commitments,
priority windows, observations, and triggered abilities occur at the correct time.

Timing highlights:
- Repurposing Bay pays/taps/sacrifices as activation costs. Prized Statue or Cam
  triggers therefore go above the Bay ability and resolve before Bay searches; a
  Cam target is committed after the activation is complete and before priority.
- Saga III is a mandatory triggered ability. The turn engine creates its stack
  object; resolving it exposes the search, with no fake "use Saga?" decision.
- Scour commits modes and its graveyard target when cast. Its library target is not
  visible until the spell resolves.
- Tezzeret -3 pays loyalty before its search ability is put on the stack.
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
    _perm_public_signature,
    _queue_simultaneous_objects,
    record_artifact_entry,
)
from non_oracle_runtime_value_key import WINDOW_POST_OBSERVATION, WINDOW_PRIORITY
from non_oracle_x_artifact_tutor_runtime import _remove_artifact_for_reshape_cost
from remaining_search_adapters import (
    BAY,
    SCOUR,
    SAGA,
    TEZZ,
    TARGET_KIND,
    _bay_cost,
    _slot_from_parameter,
    _slot_index,
    bay_activation_intents,
    scour_cast_intents,
    tezzeret_minus3_intents,
)
from trigger_order_adapter import post_cast_observations

MAIN_ACTIVATE_BAY = "main_activate_repurposing_bay"
MAIN_CAST_SCOUR = "main_cast_scour_for_scrap"
MAIN_ACTIVATE_TEZZ_MINUS3 = "main_activate_tezzeret_minus3"

ABILITY_BAY = "repurposing_bay_search_ability"
TRIGGER_SAGA3 = "saga3_search_trigger"
SPELL_SCOUR = "scour_for_scrap_spell"
ABILITY_TEZZ_MINUS3 = "tezzeret_minus3_search_ability"

RUNTIME_BAY_TARGET = "runtime_bay_target"
RUNTIME_SAGA_TARGET = "runtime_saga3_target"
RUNTIME_SCOUR_TARGET = "runtime_scour_target"
RUNTIME_TEZZ_TARGET = "runtime_tezzeret_target"


def _wrap_bay_intents(runtime: NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    rows = []
    for candidate in bay_activation_intents(runtime.true_state):
        params = dict(candidate.parameters)
        sacrifice = tuple(params["sacrifice"])
        sacrifice_name = str(sacrifice[0]) if sacrifice else ""
        rows.append(ActionIntent(
            action_id=f"main.bay.{candidate.action_id}",
            kind=MAIN_ACTIVATE_BAY,
            parameters=(
                ("activation_parameters", tuple(candidate.parameters)),
                ("sacrifice_name", sacrifice_name),
                ("source", BAY),
                ("target_mv", int(params["target_mv"])),
            ),
            equivalence_key=(MAIN_ACTIVATE_BAY, candidate.strategic_key()),
            label=candidate.label,
            decision_stage=DECISION_COMMIT,
            source=BAY,
        ))
    return tuple(rows)


def _wrap_scour_intents(runtime: NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    rows = []
    for candidate in scour_cast_intents(runtime.true_state):
        params = dict(candidate.parameters)
        rows.append(ActionIntent(
            action_id=f"main.scour.{candidate.action_id}",
            kind=MAIN_CAST_SCOUR,
            parameters=(
                ("blue", int(params["blue"])),
                ("generic", int(params["generic"])),
                ("graveyard_target", str(params["graveyard_target"])),
                ("mode", str(params["mode"])),
                ("source", SCOUR),
            ),
            equivalence_key=(MAIN_CAST_SCOUR, candidate.strategic_key()),
            label=candidate.label,
            decision_stage=DECISION_COMMIT,
            source=SCOUR,
        ))
    return tuple(rows)


def _wrap_tezz_intents(runtime: NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    rows = []
    for candidate in tezzeret_minus3_intents(runtime.true_state):
        index = int(dict(candidate.parameters)["battlefield_index"])
        perm = runtime.true_state.battlefield[index]
        rows.append(ActionIntent(
            action_id=f"main.tezz.{candidate.action_id}",
            kind=MAIN_ACTIVATE_TEZZ_MINUS3,
            parameters=(
                ("source_state", _perm_public_signature(perm)),
                ("source_tag", int(perm.instance_tag)),
            ),
            equivalence_key=(MAIN_ACTIVATE_TEZZ_MINUS3, _perm_public_signature(perm)),
            label="Tezzeret -3",
            decision_stage=DECISION_COMMIT,
            source=TEZZ,
        ))
    return tuple(rows)


def remaining_search_main_intents(runtime: NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    return tuple(
        sorted(
            _wrap_bay_intents(runtime) + _wrap_scour_intents(runtime) + _wrap_tezz_intents(runtime),
            key=lambda action: action.action_id,
        )
    )


def _allocate_ability(runtime, *, kind, source, payload=(), public_payload=()):
    obj, stack = runtime.stack.allocate(
        object_type=STACK_TRIGGER,
        kind=kind,
        source=source,
        card=source,
        payload=tuple(payload),
        public_payload=tuple(public_payload),
        strategic_payload=tuple(public_payload),
    )
    return obj, replace(runtime, stack=stack.push_existing((obj,)))


def _underlying_bay(runtime, action):
    wanted = tuple(dict(action.parameters)["activation_parameters"])
    matches = [c for c in bay_activation_intents(runtime.true_state) if tuple(c.parameters) == wanted]
    if len(matches) != 1:
        raise ValueError("Bay activation is no longer legal")
    return matches[0]


def begin_bay_activation(runtime: NonOracleRuntimeState, action: ActionIntent) -> NonOracleRuntimeState:
    legal = {a.canonical_key() for a in _wrap_bay_intents(runtime)}
    if action.canonical_key() not in legal:
        raise ValueError("Repurposing Bay activation is not currently legal")
    underlying = _underlying_bay(runtime, action)
    params = dict(underlying.parameters)
    state = solver.pay(runtime.true_state, int(params["cost"]), 0)
    if state is None:
        raise ValueError("Bay activation cost can no longer be paid")
    bay_slot = _slot_from_parameter(tuple(params["bay"]))
    bay_index = _slot_index(state, bay_slot)
    state = solver.update_perm(state, bay_index, tapped=True)
    sac_slot = _slot_from_parameter(tuple(params["sacrifice"]))
    sac_index = _slot_index(state, sac_slot)
    if not solver.is_artifact_perm(state.battlefield[sac_index]):
        raise ValueError("Bay sacrifice is no longer an artifact")
    state, sacrificed = _remove_artifact_for_reshape_cost(state, sac_index)
    state = solver.add_trace(
        state,
        f"Phase2 activate Repurposing Bay; sacrifice {sacrificed.name or sacrificed.mode}; target MV {int(params['target_mv'])}",
    )
    runtime = replace(runtime, true_state=solver._ensure_oracle_instance_tags(state))
    _, runtime = _allocate_ability(
        runtime,
        kind=ABILITY_BAY,
        source=BAY,
        payload=(("target_mv", int(params["target_mv"])),),
        public_payload=(("target_mv", int(params["target_mv"])),),
    )
    if sacrificed.name == "Sewer-veillance Cam":
        return queue_cam_ltb(
            runtime,
            count=1,
            source="Repurposing Bay activation-cost Cam LTB",
        )
    if sacrificed.name == "Prized Statue":
        death, allocated = runtime.stack.allocate(
            object_type=STACK_TRIGGER,
            kind="prized_dies_treasure",
            source="Prized Statue",
            card="Prized Statue",
        )
        return replace(
            runtime,
            stack=allocated.push_existing((death,)),
            window=RuntimeDecisionWindow(WINDOW_PRIORITY),
        )
    return replace(runtime, window=RuntimeDecisionWindow(WINDOW_PRIORITY))


def begin_scour_cast(runtime: NonOracleRuntimeState, action: ActionIntent) -> NonOracleRuntimeState:
    legal = {a.canonical_key() for a in _wrap_scour_intents(runtime)}
    if action.canonical_key() not in legal:
        raise ValueError("Scour for Scrap cast is not currently legal")
    params = dict(action.parameters)
    state = solver.pay(runtime.true_state, int(params["generic"]), int(params["blue"]))
    if state is None or SCOUR not in state.hand:
        raise ValueError("Scour can no longer pay/commit")
    state = replace(
        state,
        hand=solver.remove_one(state.hand, SCOUR),
        spell_cast_this_turn=True,
    )
    state = solver.add_trace(state, f"Phase2 cast Scour for Scrap mode={params['mode']}")
    runtime = replace(runtime, true_state=state)
    spell, stack = runtime.stack.allocate(
        object_type=STACK_SPELL,
        kind=SPELL_SCOUR,
        source="hand",
        card=SCOUR,
        payload=(
            ("graveyard_target", str(params["graveyard_target"])),
            ("mana_spent", int(params["generic"]) + int(params["blue"])),
            ("mode", str(params["mode"])),
        ),
        public_payload=(
            ("graveyard_target", str(params["graveyard_target"])),
            ("mode", str(params["mode"])),
        ),
        strategic_payload=(
            ("graveyard_target", str(params["graveyard_target"])),
            ("mode", str(params["mode"])),
        ),
    )
    runtime = replace(runtime, stack=stack.push_existing((spell,)))
    info = apply_observation_batch(
        runtime.information,
        post_cast_observations(state, SCOUR, cast_from_library_top=False),
    )
    runtime = replace(runtime, information=info)
    triggers, allocated = _cast_trigger_objects(
        runtime,
        SCOUR,
        int(params["generic"]) + int(params["blue"]),
        spell.object_id,
    )
    runtime = replace(runtime, stack=allocated)
    return _queue_simultaneous_objects(runtime, triggers, source=f"cast {SCOUR}")


def begin_tezz_minus3(runtime: NonOracleRuntimeState, action: ActionIntent) -> NonOracleRuntimeState:
    legal = {a.canonical_key() for a in _wrap_tezz_intents(runtime)}
    if action.canonical_key() not in legal:
        raise ValueError("Tezzeret -3 is not currently legal")
    tag = int(dict(action.parameters)["source_tag"])
    index = next(
        (i for i, p in enumerate(runtime.true_state.battlefield) if int(p.instance_tag) == tag),
        None,
    )
    if index is None:
        raise ValueError("Tezzeret source is no longer present")
    perm = runtime.true_state.battlefield[index]
    if perm.name != TEZZ or perm.mode == "tez_used" or perm.counters < 3:
        raise ValueError("Tezzeret -3 is no longer legal")
    state = solver.update_perm(
        runtime.true_state,
        index,
        counters=perm.counters - 3,
        mode="tez_used",
    )
    state = solver.add_trace(state, "Phase2 activate Tezzeret -3")
    runtime = replace(runtime, true_state=state)
    _, runtime = _allocate_ability(runtime, kind=ABILITY_TEZZ_MINUS3, source=TEZZ)
    return replace(runtime, window=RuntimeDecisionWindow(WINDOW_PRIORITY))


def apply_remaining_main_action(runtime: NonOracleRuntimeState, action: ActionIntent) -> NonOracleRuntimeState:
    if action.kind == MAIN_ACTIVATE_BAY:
        return begin_bay_activation(runtime, action)
    if action.kind == MAIN_CAST_SCOUR:
        return begin_scour_cast(runtime, action)
    if action.kind == MAIN_ACTIVATE_TEZZ_MINUS3:
        return begin_tezz_minus3(runtime, action)
    raise ValueError("not a remaining-search main action")


def _open_search(runtime, *, source, legal_targets, pending_kind, payload, contingent_on):
    search = SearchZoneObservation(
        zone="library",
        legal_cards=tuple(sorted(set(legal_targets))),
        context=source,
        may_fail_to_find=True,
    )
    info = apply_observation_batch(runtime.information, ObservationBatch((search,)))
    spec = PendingDecisionSpec(
        decision_id=f"runtime.{pending_kind}.target",
        kind=TARGET_KIND,
        source=source,
        decision_stage=DECISION_POST_OBSERVATION,
        contingent_on=contingent_on,
    )
    return replace(
        runtime,
        information=info,
        pending=RuntimePendingDecision(
            spec=spec,
            kind=pending_kind,
            payload=(
                ("legal_targets", tuple(search.legal_cards)),
                ("source", source),
            ) + tuple(payload),
        ),
        window=RuntimeDecisionWindow(WINDOW_POST_OBSERVATION),
    )


def _finish_scour_graveyard_only(runtime, obj):
    params = dict(obj.payload)
    target = str(params["graveyard_target"])
    state = runtime.true_state
    if target and target in state.graveyard:
        gy = list(state.graveyard)
        gy.remove(target)
        state = replace(state, graveyard=tuple(gy), hand=state.hand + (target,))
    state = replace(state, graveyard=state.graveyard + (SCOUR,))
    state = solver.check_win(solver.add_trace(state, f"Phase2 Scour returns {target or 'no target'}"))
    return replace(runtime, true_state=state, window=RuntimeDecisionWindow(WINDOW_PRIORITY))


def handles_remaining_stack_top(runtime: NonOracleRuntimeState) -> bool:
    if runtime.pending is not None:
        return False
    top = runtime.stack.top()
    return bool(top and top.kind in {ABILITY_BAY, TRIGGER_SAGA3, SPELL_SCOUR, ABILITY_TEZZ_MINUS3})


def apply_remaining_stack_action(runtime: NonOracleRuntimeState, action: ActionIntent) -> NonOracleRuntimeState:
    if action.action_id != ACTION_PASS_PRIORITY or action.kind != "pass_priority":
        raise ValueError("remaining search object resolves only after passing priority")
    obj, remaining = runtime.stack.pop_top()
    if obj is None:
        raise ValueError("empty remaining-search stack")
    runtime = replace(runtime, stack=remaining)
    params = dict(obj.payload)

    if obj.kind == ABILITY_BAY:
        target_mv = int(params["target_mv"])
        legal = (
            card for card in runtime.true_state.library
            if card in solver.ARTIFACTS
            and solver.mana_value(card) == target_mv
            and not solver.cage_blocks_library_battlefield_entry(runtime.true_state, card)
        )
        return _open_search(
            runtime,
            source=BAY,
            legal_targets=legal,
            pending_kind=RUNTIME_BAY_TARGET,
            payload=(("target_mv", target_mv),),
            contingent_on=obj.object_id,
        )

    if obj.kind == TRIGGER_SAGA3:
        return _open_search(
            runtime,
            source=SAGA,
            legal_targets=(card for card in runtime.true_state.library if card in solver.SAGA_TARGETS),
            pending_kind=RUNTIME_SAGA_TARGET,
            payload=(),
            contingent_on=obj.object_id,
        )

    if obj.kind == ABILITY_TEZZ_MINUS3:
        return _open_search(
            runtime,
            source=TEZZ,
            legal_targets=(
                card for card in runtime.true_state.library
                if card in solver.ARTIFACTS and solver.mana_value(card) <= 1
            ),
            pending_kind=RUNTIME_TEZZ_TARGET,
            payload=(),
            contingent_on=obj.object_id,
        )

    if obj.kind == SPELL_SCOUR:
        mode = str(params["mode"])
        gy_target = str(params["graveyard_target"])
        if mode == "graveyard":
            return _finish_scour_graveyard_only(runtime, obj)
        return _open_search(
            runtime,
            source=SCOUR,
            legal_targets=(card for card in runtime.true_state.library if card in solver.ARTIFACTS),
            pending_kind=RUNTIME_SCOUR_TARGET,
            payload=(("graveyard_target", gy_target), ("mode", mode)),
            contingent_on=obj.object_id,
        )

    raise ValueError(f"unsupported remaining-search stack object {obj.kind!r}")


def handles_remaining_pending(runtime: NonOracleRuntimeState) -> bool:
    return bool(runtime.pending and runtime.pending.kind in {
        RUNTIME_BAY_TARGET,
        RUNTIME_SAGA_TARGET,
        RUNTIME_SCOUR_TARGET,
        RUNTIME_TEZZ_TARGET,
    })


def _target_actions(runtime: NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    data = dict(runtime.pending.payload)
    source = str(data["source"])
    rows = [ActionIntent(
        action_id=f"runtime.{runtime.pending.kind}.fail",
        kind=TARGET_KIND,
        parameters=(("target", ""),),
        equivalence_key=(runtime.pending.kind, "fail"),
        label="Find no card",
        decision_stage=DECISION_POST_OBSERVATION,
        source=source,
        contingent_on=runtime.pending.spec.contingent_on,
    )]
    for index, target in enumerate(tuple(data["legal_targets"])):
        rows.append(ActionIntent(
            action_id=f"runtime.{runtime.pending.kind}.{index:02d}",
            kind=TARGET_KIND,
            parameters=(("target", str(target)),),
            equivalence_key=(runtime.pending.kind, "target", str(target)),
            label=f"Find {target}",
            decision_stage=DECISION_POST_OBSERVATION,
            source=source,
            contingent_on=runtime.pending.spec.contingent_on,
        ))
    return tuple(rows)


def remaining_pending_request(
    runtime: NonOracleRuntimeState,
    *,
    horizon: int,
    objective: str,
    policy_id: str,
    caverns_live=None,
) -> DecisionRequest:
    if not handles_remaining_pending(runtime):
        raise ValueError("not a pending remaining-search target")
    return DecisionRequest(
        observation=runtime.policy_view(caverns_live=caverns_live),
        actions=_target_actions(runtime),
        context=PolicyDecisionContext(
            horizon=horizon,
            objective=objective,
            policy_id=policy_id,
            decision_id=runtime.pending.spec.decision_id,
            decision_stage=DECISION_POST_OBSERVATION,
        ),
    )


def _shuffle_information(runtime, source):
    return apply_observation_batch(
        runtime.information,
        ObservationBatch((ShuffleObservation(source),)),
    )


def _sacrifice_final_saga(state):
    return solver._sacrifice_final_saga_if_present(state)


def _apply_bay_target(runtime, target):
    state = runtime.true_state
    if target:
        if target not in state.library:
            raise ValueError("Bay target is no longer in library")
        library = list(state.library)
        library.remove(target)
        state = replace(state, library=tuple(library))
        state = solver.add_perm(state, target, sick=target in solver.CREATURES)
    salt = "bay:" + target if target else "bay:no-target:staged"
    state = replace(state, library=solver.shuffled_library(state, salt))
    state = solver.check_win(solver.add_trace(state, f"Phase2 Bay -> {target or 'no card'}; shuffle"))
    runtime = replace(
        runtime,
        true_state=solver._ensure_oracle_instance_tags(state),
        information=_shuffle_information(runtime, BAY),
        pending=None,
        window=RuntimeDecisionWindow(WINDOW_PRIORITY),
    )
    return record_artifact_entry(runtime, (target,), source=f"resolve Bay -> {target}") if target else runtime


def _apply_saga_target(runtime, target):
    state = runtime.true_state
    if target:
        if target not in state.library:
            raise ValueError("Saga target is no longer in library")
        library = list(state.library)
        library.remove(target)
        state = replace(state, library=tuple(library))
        state = solver.add_perm(state, target, sick=target in solver.CREATURES)
    salt = "saga:" + target if target else "saga:no-target"
    state = replace(state, library=solver.shuffled_library(state, salt))
    state = _sacrifice_final_saga(state)
    state = solver.check_win(solver.add_trace(state, f"Phase2 Saga III -> {target or 'no card'}; shuffle"))
    runtime = replace(
        runtime,
        true_state=solver._ensure_oracle_instance_tags(state),
        information=_shuffle_information(runtime, SAGA),
        pending=None,
        window=RuntimeDecisionWindow(WINDOW_PRIORITY),
    )
    return record_artifact_entry(runtime, (target,), source=f"resolve Saga III -> {target}") if target else runtime


def _apply_tezz_target(runtime, target):
    state = runtime.true_state
    if target:
        if target not in state.library:
            raise ValueError("Tezzeret target is no longer in library")
        state = solver.move_library_to_hand(state, target)
    salt = "tezz:" + target if target else "tezz:no-target"
    state = replace(state, library=solver.shuffled_library(state, salt))
    state = solver.check_win(solver.add_trace(state, f"Phase2 Tezzeret -3 -> {target or 'no card'}"))
    return replace(
        runtime,
        true_state=state,
        information=_shuffle_information(runtime, TEZZ),
        pending=None,
        window=RuntimeDecisionWindow(WINDOW_PRIORITY),
    )


def _apply_scour_target(runtime, target):
    data = dict(runtime.pending.payload)
    mode = str(data["mode"])
    gy_target = str(data["graveyard_target"])
    state = runtime.true_state
    if target:
        if target not in state.library:
            raise ValueError("Scour target is no longer in library")
        state = solver.move_library_to_hand(state, target)
    salt = (
        "scourboth:" + target + gy_target if target and mode == "both"
        else "scour:" + target if target
        else "scour:no-target:" + mode
    )
    state = replace(state, library=solver.shuffled_library(state, salt))
    if mode == "both" and gy_target and gy_target in state.graveyard:
        gy = list(state.graveyard)
        gy.remove(gy_target)
        state = replace(state, graveyard=tuple(gy), hand=state.hand + (gy_target,))
    state = replace(state, graveyard=state.graveyard + (SCOUR,))
    state = solver.check_win(solver.add_trace(
        state,
        f"Phase2 Scour -> {target or 'no library card'}"
        + (f" + returns {gy_target}" if mode == "both" and gy_target in state.hand else ""),
    ))
    return replace(
        runtime,
        true_state=state,
        information=_shuffle_information(runtime, SCOUR),
        pending=None,
        window=RuntimeDecisionWindow(WINDOW_PRIORITY),
    )


def apply_remaining_pending(runtime: NonOracleRuntimeState, action: ActionIntent) -> NonOracleRuntimeState:
    if not handles_remaining_pending(runtime):
        raise ValueError("no remaining-search target pending")
    legal = {candidate.canonical_key() for candidate in _target_actions(runtime)}
    if action.canonical_key() not in legal:
        raise ValueError("remaining-search target is not legal for the observed search")
    target = str(dict(action.parameters).get("target", ""))
    data = dict(runtime.pending.payload)
    if target and target not in tuple(data["legal_targets"]):
        raise ValueError("target was not in the observed legal search set")
    kind = runtime.pending.kind
    if kind == RUNTIME_BAY_TARGET:
        return _apply_bay_target(runtime, target)
    if kind == RUNTIME_SAGA_TARGET:
        return _apply_saga_target(runtime, target)
    if kind == RUNTIME_SCOUR_TARGET:
        return _apply_scour_target(runtime, target)
    if kind == RUNTIME_TEZZ_TARGET:
        return _apply_tezz_target(runtime, target)
    raise ValueError("unknown remaining-search pending kind")
