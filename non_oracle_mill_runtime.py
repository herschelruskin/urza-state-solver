#!/usr/bin/env python3
"""Phase-2 self-mill runtime for Grinding Station and Codex Shredder.

Grinding Station is modeled as a real activated ability at both empty-main and
priority windows:

    tap Station + sacrifice an artifact as costs
      -> any Cam/Prized death/LTB trigger is put above the ability
      -> intervening trigger/priority sequencing resolves normally
      -> Station mills the top three cards on resolution

The sacrificed artifact may be tapped and may be Grinding Station itself. Physical
removal reuses the Phase-2 artifact-cost helper that avoids Oracle trigger shortcuts.
Cam target selection is staged by the typed Cam runtime; Prized Statue creates its
normal death trigger above the pending mill ability.

The Oracle's producer fast-line may leave Station tapped with a still-unspent
``producer_urza_ready`` +U credit. Such a state also represents the legal branch
where the final Urza tap was not taken, so this adapter refunds that exact credit
before paying Station's tap cost instead of incorrectly suppressing the activation.

Codex Shredder's tap-to-mill-one ability is included as the compact companion surface.
Both abilities update InformationState only when the milled cards become public, then
refresh continuous Chip/FTT top visibility.

This module also owns the combined priority request aggregator. It collects Top/Key,
self-mill, and Chrome Dome priority actions into one policy-safe request while each
card-specific adapter remains responsible for applying its own action.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Dict, Tuple

import urza_solver as solver
import non_oracle_runtime as core
from decision_observation import (
    ActionIntent,
    DECISION_COMMIT,
    DECISION_MECHANICAL,
    DecisionRequest,
    MoveKnownCardObservation,
    ObservationBatch,
    PolicyDecisionContext,
    apply_observation_batch,
)
from non_oracle_cam_runtime import queue_cam_ltb
from non_oracle_chrome_priority_runtime import chrome_priority_actions
from non_oracle_runtime_value_key import RuntimeDecisionWindow, WINDOW_PRIORITY
from non_oracle_turn_engine import _refresh_continuous_top
from non_oracle_x_artifact_tutor_runtime import _remove_artifact_for_reshape_cost
from non_oracle_top_draw_runtime import top_priority_actions

STATION = "Grinding Station"
CODEX = "Codex Shredder"

MAIN_ACTIVATE_STATION_MILL = "main_activate_station_mill"
MAIN_ACTIVATE_CODEX_MILL = "main_activate_codex_mill"
PRIORITY_ACTIVATE_STATION_MILL = "priority_activate_station_mill"
PRIORITY_ACTIVATE_CODEX_MILL = "priority_activate_codex_mill"

ACT_STATION_MILL = "activated_station_self_mill"
ACT_CODEX_MILL = "activated_codex_self_mill"
MILL_STACK_KINDS = frozenset({ACT_STATION_MILL, ACT_CODEX_MILL})
MILL_PRIORITY_KINDS = frozenset({
    PRIORITY_ACTIVATE_STATION_MILL,
    PRIORITY_ACTIVATE_CODEX_MILL,
})


def _signature(perm) -> Tuple[object, ...]:
    return core._perm_public_signature(perm)


def _groups(state, predicate) -> Dict[Tuple[object, ...], Tuple[object, ...]]:
    rows = {}
    for perm in state.battlefield:
        if not predicate(perm):
            continue
        rows.setdefault(_signature(perm), []).append(perm)
    return {
        signature: tuple(sorted(perms, key=lambda p: int(p.instance_tag)))
        for signature, perms in rows.items()
    }


def _station_source_available(state: solver.State, perm) -> bool:
    if perm.name != STATION:
        return False
    if not perm.tapped:
        return True
    return bool(perm.producer_urza_ready and state.blue >= 1)


def _station_live_flags(state: solver.State) -> Tuple[bool, bool, bool]:
    top_access = bool(state.chip_attached or state.ftt_level >= 2)
    cage = bool(solver.has(state, "Grafdigger's Cage"))
    graveyard_live = bool("Scour for Scrap" in state.hand or solver.has(state, CODEX))
    return top_access, cage, graveyard_live


def _station_is_strategically_live(state: solver.State) -> bool:
    return any(_station_live_flags(state))


def _station_actions(
    runtime: core.NonOracleRuntimeState,
    *,
    priority: bool,
) -> Tuple[ActionIntent, ...]:
    state = runtime.true_state
    if not state.library or not _station_is_strategically_live(state):
        return ()
    stations = _groups(state, lambda p: _station_source_available(state, p))
    artifacts = _groups(state, solver.is_artifact_perm)
    if not stations or not artifacts:
        return ()
    top_access, cage, graveyard_live = _station_live_flags(state)
    kind = PRIORITY_ACTIVATE_STATION_MILL if priority else MAIN_ACTIVATE_STATION_MILL
    stage = DECISION_MECHANICAL if priority else DECISION_COMMIT
    rows = []
    index = 0
    for source_signature in sorted(stations, key=repr):
        source = stations[source_signature][0]
        refundable = bool(source.tapped and source.producer_urza_ready)
        for sacrifice_signature in sorted(artifacts, key=repr):
            candidates = artifacts[sacrifice_signature]
            sacrifice = candidates[0]
            if sacrifice_signature == source_signature:
                sacrifice = source
            rows.append(ActionIntent(
                action_id=(
                    f"priority.station.mill.{index:03d}"
                    if priority else f"main.station.mill.{index:03d}"
                ),
                kind=kind,
                parameters=(
                    ("cage_live", cage),
                    ("graveyard_live", graveyard_live),
                    ("mill_count", min(3, len(state.library))),
                    ("refund_urza_blue", refundable),
                    ("sacrifice_name", str(sacrifice.name or sacrifice.mode)),
                    ("sacrifice_signature", sacrifice_signature),
                    ("source_signature", source_signature),
                    ("top_access_live", top_access),
                ),
                equivalence_key=(
                    kind,
                    source_signature,
                    sacrifice_signature,
                    refundable,
                    top_access,
                    cage,
                    graveyard_live,
                ),
                label=f"Grinding Station: sacrifice {sacrifice.name or sacrifice.mode}; mill 3",
                decision_stage=stage,
                source=STATION,
            ))
            index += 1
    return tuple(rows)


def _codex_actions(
    runtime: core.NonOracleRuntimeState,
    *,
    priority: bool,
) -> Tuple[ActionIntent, ...]:
    state = runtime.true_state
    if not state.library or not (state.chip_attached or state.ftt_level >= 2):
        return ()
    codices = _groups(state, lambda p: p.name == CODEX and not p.tapped)
    kind = PRIORITY_ACTIVATE_CODEX_MILL if priority else MAIN_ACTIVATE_CODEX_MILL
    stage = DECISION_MECHANICAL if priority else DECISION_COMMIT
    rows = []
    for index, signature in enumerate(sorted(codices, key=repr)):
        rows.append(ActionIntent(
            action_id=(
                f"priority.codex.mill.{index:03d}"
                if priority else f"main.codex.mill.{index:03d}"
            ),
            kind=kind,
            parameters=(
                ("mill_count", 1),
                ("source_signature", signature),
                ("top_access_live", True),
            ),
            equivalence_key=(kind, signature),
            label="Codex Shredder: mill our top card",
            decision_stage=stage,
            source=CODEX,
        ))
    return tuple(rows)


def mill_main_intents(runtime: core.NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    rows = list(_station_actions(runtime, priority=False))
    rows.extend(_codex_actions(runtime, priority=False))
    return tuple(sorted(rows, key=lambda action: action.action_id))


def mill_priority_actions(runtime: core.NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    if runtime.pending is not None or not runtime.stack.objects or runtime.window.kind != WINDOW_PRIORITY:
        return ()
    rows = list(_station_actions(runtime, priority=True))
    rows.extend(_codex_actions(runtime, priority=True))
    return tuple(sorted(rows, key=lambda action: action.action_id))


def extended_priority_actions(runtime: core.NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    rows = list(top_priority_actions(runtime))
    rows.extend(mill_priority_actions(runtime))
    rows.extend(chrome_priority_actions(runtime))
    return tuple(sorted(rows, key=lambda action: action.action_id))


def extended_priority_request(
    runtime: core.NonOracleRuntimeState,
    *,
    horizon: int,
    objective: str,
    policy_id: str,
    caverns_live=None,
) -> DecisionRequest:
    actions = list(extended_priority_actions(runtime))
    top_obj = runtime.stack.top()
    if top_obj is None:
        raise ValueError("extended priority request requires a live stack")
    actions.append(ActionIntent(
        action_id=core.ACTION_PASS_PRIORITY,
        kind="pass_priority",
        equivalence_key=("pass_priority", top_obj.strategic_key()),
        label="Pass priority / resolve top stack object",
        decision_stage=DECISION_MECHANICAL,
        source="runtime stack",
    ))
    return DecisionRequest(
        observation=runtime.policy_view(caverns_live=caverns_live),
        actions=tuple(sorted(actions, key=lambda action: action.action_id)),
        context=PolicyDecisionContext(
            horizon=horizon,
            objective=objective,
            policy_id=policy_id,
            decision_id="runtime.priority.with_top_key_mill_chrome",
            decision_stage=DECISION_MECHANICAL,
        ),
    )


def _representative(state, signature, predicate):
    rows = [
        perm for perm in state.battlefield
        if _signature(perm) == tuple(signature) and predicate(perm)
    ]
    if not rows:
        return None
    return min(rows, key=lambda p: int(p.instance_tag))


def _allocate_mill(runtime, *, kind: str, source_perm, mill_count: int):
    public = (
        ("mill_count", int(mill_count)),
        ("source_state", _signature(source_perm)),
    )
    obj, stack = runtime.stack.allocate(
        object_type=core.STACK_TRIGGER,
        kind=kind,
        source=source_perm.name or source_perm.mode,
        card=source_perm.name,
        payload=(
            ("mill_count", int(mill_count)),
            ("source_tag", int(source_perm.instance_tag)),
        ),
        public_payload=public,
        strategic_payload=public,
    )
    return obj, replace(runtime, stack=stack.push_existing((obj,)))


def _begin_station(runtime: core.NonOracleRuntimeState, action: ActionIntent) -> core.NonOracleRuntimeState:
    params = dict(action.parameters)
    state = runtime.true_state
    source = _representative(
        state,
        tuple(params["source_signature"]),
        lambda p: _station_source_available(state, p),
    )
    if source is None:
        raise ValueError("Grinding Station is no longer a legal source")

    sacrifice_signature = tuple(params["sacrifice_signature"])
    candidates = [
        perm for perm in state.battlefield
        if _signature(perm) == sacrifice_signature and solver.is_artifact_perm(perm)
    ]
    if not candidates:
        raise ValueError("Grinding Station sacrifice artifact is no longer present")
    candidates.sort(key=lambda p: int(p.instance_tag))
    sacrifice = source if sacrifice_signature == _signature(source) else candidates[0]

    source_idx = core._perm_index_for_tag(state, int(source.instance_tag))
    if source.tapped:
        refunded = solver._refund_producer_urza_tap(state, source_idx)
        if refunded is None:
            raise ValueError("Grinding Station refundable Urza tap is no longer available")
        state = refunded
        source_idx = core._perm_index_for_tag(state, int(source.instance_tag))
    state = solver.update_perm(state, source_idx, tapped=True)
    runtime = replace(runtime, true_state=state)
    _, runtime = _allocate_mill(
        runtime,
        kind=ACT_STATION_MILL,
        source_perm=source,
        mill_count=min(3, len(state.library)),
    )

    sacrifice_idx = core._perm_index_for_tag(runtime.true_state, int(sacrifice.instance_tag))
    if sacrifice_idx is None or not solver.is_artifact_perm(runtime.true_state.battlefield[sacrifice_idx]):
        raise ValueError("Grinding Station sacrifice artifact disappeared during cost payment")
    state, removed = _remove_artifact_for_reshape_cost(runtime.true_state, sacrifice_idx)
    state = solver.add_trace(
        state,
        f"Phase2 Grinding Station cost: tap Station; sacrifice {removed.name or removed.mode}",
    )
    runtime = replace(runtime, true_state=solver._ensure_oracle_instance_tags(state))

    if removed.name == "Sewer-veillance Cam":
        return queue_cam_ltb(
            runtime,
            count=1,
            source="Grinding Station sacrifice cost Cam LTB",
        )
    if removed.name == "Prized Statue":
        death, stack = runtime.stack.allocate(
            object_type=core.STACK_TRIGGER,
            kind="prized_dies_treasure",
            source="Prized Statue",
            card="Prized Statue",
        )
        return replace(
            runtime,
            stack=stack.push_existing((death,)),
            window=RuntimeDecisionWindow(WINDOW_PRIORITY),
        )
    return replace(runtime, window=RuntimeDecisionWindow(WINDOW_PRIORITY))


def _begin_codex(runtime: core.NonOracleRuntimeState, action: ActionIntent) -> core.NonOracleRuntimeState:
    params = dict(action.parameters)
    source = _representative(
        runtime.true_state,
        tuple(params["source_signature"]),
        lambda p: p.name == CODEX and not p.tapped,
    )
    if source is None:
        raise ValueError("Codex Shredder is no longer an untapped legal source")
    idx = core._perm_index_for_tag(runtime.true_state, int(source.instance_tag))
    state = solver.update_perm(runtime.true_state, idx, tapped=True)
    state = solver.add_trace(state, "Phase2 Codex Shredder cost: tap; self-mill 1 pending")
    runtime = replace(runtime, true_state=state)
    _, runtime = _allocate_mill(
        runtime,
        kind=ACT_CODEX_MILL,
        source_perm=source,
        mill_count=1,
    )
    return replace(runtime, window=RuntimeDecisionWindow(WINDOW_PRIORITY))


def _legal_main_keys(runtime):
    return {candidate.canonical_key() for candidate in mill_main_intents(runtime)}


def _legal_priority_keys(runtime):
    return {candidate.canonical_key() for candidate in mill_priority_actions(runtime)}


def begin_mill_main_action(
    runtime: core.NonOracleRuntimeState,
    action: ActionIntent,
) -> core.NonOracleRuntimeState:
    if action.canonical_key() not in _legal_main_keys(runtime):
        raise ValueError("mill main action is no longer legal")
    if action.kind == MAIN_ACTIVATE_STATION_MILL:
        return _begin_station(runtime, action)
    if action.kind == MAIN_ACTIVATE_CODEX_MILL:
        return _begin_codex(runtime, action)
    raise ValueError(f"unsupported mill main action {action.kind!r}")


def apply_mill_priority_action(
    runtime: core.NonOracleRuntimeState,
    action: ActionIntent,
) -> core.NonOracleRuntimeState:
    if action.canonical_key() not in _legal_priority_keys(runtime):
        raise ValueError("mill priority action is no longer legal")
    if action.kind == PRIORITY_ACTIVATE_STATION_MILL:
        return _begin_station(runtime, action)
    if action.kind == PRIORITY_ACTIVATE_CODEX_MILL:
        return _begin_codex(runtime, action)
    raise ValueError(f"unsupported mill priority action {action.kind!r}")


def handles_mill_stack_top(runtime: core.NonOracleRuntimeState) -> bool:
    if runtime.pending is not None:
        return False
    top = runtime.stack.top()
    return bool(top and top.kind in MILL_STACK_KINDS)


def _resolve_mill(runtime: core.NonOracleRuntimeState, obj) -> core.NonOracleRuntimeState:
    state = runtime.true_state
    count = min(int(dict(obj.payload).get("mill_count", 0)), len(state.library))
    milled = tuple(str(card) for card in state.library[:count])
    if milled:
        state = replace(
            state,
            library=tuple(state.library[count:]),
            graveyard=tuple(state.graveyard) + milled,
        )
        info = apply_observation_batch(
            runtime.information,
            ObservationBatch(tuple(
                MoveKnownCardObservation(
                    card,
                    from_zone="library",
                    to_zone="graveyard",
                    position="top",
                    source=obj.source or obj.kind,
                )
                for card in milled
            )),
        )
        info = _refresh_continuous_top(
            state,
            info,
            source=f"post-{obj.source or obj.kind} mill continuous look",
        )
        state = solver.add_trace(
            state,
            f"Phase2 {obj.source or obj.kind} self-mills {len(milled)}: {', '.join(milled)}",
        )
        runtime = replace(runtime, true_state=state, information=info)
    return replace(runtime, window=RuntimeDecisionWindow(WINDOW_PRIORITY))


def apply_mill_stack_action(
    runtime: core.NonOracleRuntimeState,
    action: ActionIntent,
) -> core.NonOracleRuntimeState:
    if action.action_id != core.ACTION_PASS_PRIORITY or action.kind != "pass_priority":
        raise ValueError("mill ability resolves only after passing priority")
    obj, remaining = runtime.stack.pop_top()
    if obj is None or obj.kind not in MILL_STACK_KINDS:
        raise ValueError("top runtime object is not a supported mill ability")
    runtime = replace(runtime, stack=remaining)
    return _resolve_mill(runtime, obj)
