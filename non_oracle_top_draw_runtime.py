#!/usr/bin/env python3
"""Phase-2 Sensei's Divining Top draw / priority-time Key runtime.

Top's second ability and Voltaic/Manifold Key are timing-sensitive enough that a
main-phase successor shortcut would be wrong.  This module keeps the real stack:

    activate Top A1 (tap as cost)
      -> priority: Key may untap Top
      -> resolve Key
      -> priority: Top may activate A2
      -> resolve A2: draw underlying card, put Top on library
      -> resolve A1: draw that known Top; no battlefield Top remains to move

The same priority adapter exposes Key untaps of other public tapped artifacts while
a stack is live.  Every action is based only on public permanent signatures; exact
instance tags remain in stack payloads/rules state.

The runtime core currently transports activated abilities using its generic
``STACK_TRIGGER`` object class.  Distinct ``activated_*`` kinds preserve semantics;
this module never treats them as triggered abilities for ordering purposes.
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
from non_oracle_runtime_value_key import RuntimeDecisionWindow, WINDOW_PRIORITY
from non_oracle_turn_engine import _draw_one, _refresh_continuous_top

TOP = "Sensei's Divining Top"
KEYS = frozenset({"Voltaic Key", "Manifold Key"})

MAIN_ACTIVATE_TOP_DRAW = "main_activate_top_draw"
PRIORITY_ACTIVATE_TOP_DRAW = "priority_activate_top_draw"
PRIORITY_ACTIVATE_KEY = "priority_activate_key"

ACT_TOP_DRAW = "activated_top_draw"
ACT_KEY_UNTAP = "activated_key_untap"
TOP_STACK_KINDS = frozenset({ACT_TOP_DRAW, ACT_KEY_UNTAP})


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


def _top_draw_stack_count(runtime: core.NonOracleRuntimeState) -> int:
    return sum(1 for obj in runtime.stack.objects if obj.kind == ACT_TOP_DRAW)


def _top_draw_action(runtime, *, priority: bool, index: int = 0) -> Tuple[ActionIntent, ...]:
    state = runtime.true_state
    tops = _groups(state, lambda p: p.name == TOP and not p.tapped)
    if not tops or not state.library:
        return ()
    stack_count = _top_draw_stack_count(runtime)
    kind = PRIORITY_ACTIVATE_TOP_DRAW if priority else MAIN_ACTIVATE_TOP_DRAW
    stage = DECISION_MECHANICAL if priority else DECISION_COMMIT
    rows = []
    for offset, signature in enumerate(sorted(tops, key=repr)):
        rows.append(ActionIntent(
            action_id=(
                f"priority.top.draw.{index+offset:03d}"
                if priority else f"main.top.draw.{offset:03d}"
            ),
            kind=kind,
            parameters=(
                ("source_signature", signature),
                ("top_draws_on_stack", stack_count),
                ("ready_key_count", sum(
                    1 for p in state.battlefield
                    if p.name in KEYS and not p.tapped
                )),
            ),
            equivalence_key=(kind, signature, stack_count),
            label="Sensei's Divining Top: draw a card, then put Top on library",
            decision_stage=stage,
            source=TOP,
        ))
    return tuple(rows)


def top_draw_main_intents(runtime: core.NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    return _top_draw_action(runtime, priority=False)


def _priority_key_actions(runtime: core.NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    state = runtime.true_state
    # If a Key ability is already on top, resolve it before stacking redundant
    # copies against the same current board.  Once it resolves, priority returns
    # and the now-untapped target can create the intended follow-up choice.
    top_obj = runtime.stack.top()
    if top_obj is not None and top_obj.kind == ACT_KEY_UNTAP:
        return ()
    if not solver.can_pay(state, 1, 0):
        return ()
    keys = _groups(state, lambda p: p.name in KEYS and not p.tapped)
    targets = _groups(state, lambda p: solver.is_artifact_perm(p) and p.tapped)
    stack_count = _top_draw_stack_count(runtime)
    rows = []
    index = 0
    for key_signature in sorted(keys, key=repr):
        key_name = str(key_signature[0])
        for target_signature in sorted(targets, key=repr):
            if key_signature == target_signature:
                continue
            target_name = str(target_signature[0])
            rows.append(ActionIntent(
                action_id=f"priority.key.{index:03d}",
                kind=PRIORITY_ACTIVATE_KEY,
                parameters=(
                    ("key_name", key_name),
                    ("key_signature", key_signature),
                    ("target_name", target_name),
                    ("target_signature", target_signature),
                    ("top_draws_on_stack", stack_count),
                ),
                equivalence_key=(PRIORITY_ACTIVATE_KEY, key_signature, target_signature, stack_count),
                label=f"{key_name}: untap {target_name} at priority",
                decision_stage=DECISION_MECHANICAL,
                source=key_name,
            ))
            index += 1
    return tuple(rows)


def top_priority_actions(runtime: core.NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    if runtime.pending is not None or not runtime.stack.objects or runtime.window.kind != WINDOW_PRIORITY:
        return ()
    rows = []
    rows.extend(_priority_key_actions(runtime))
    rows.extend(_top_draw_action(runtime, priority=True, index=len(rows)))
    return tuple(sorted(rows, key=lambda action: action.action_id))


def top_priority_request(
    runtime: core.NonOracleRuntimeState,
    *,
    horizon: int,
    objective: str,
    policy_id: str,
    caverns_live=None,
) -> DecisionRequest:
    actions = list(top_priority_actions(runtime))
    top_obj = runtime.stack.top()
    if top_obj is None:
        raise ValueError("priority request requires a live stack")
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
            decision_id="runtime.priority.with_top_key",
            decision_stage=DECISION_MECHANICAL,
        ),
    )


def _perm_from_signature(state, signature, predicate):
    candidates = [
        p for p in state.battlefield
        if _signature(p) == tuple(signature) and predicate(p)
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda p: int(p.instance_tag))


def _push_top_draw(runtime: core.NonOracleRuntimeState, source) -> core.NonOracleRuntimeState:
    idx = core._perm_index_for_tag(runtime.true_state, int(source.instance_tag))
    if idx is None or runtime.true_state.battlefield[idx].name != TOP or runtime.true_state.battlefield[idx].tapped:
        raise ValueError("Sensei's Divining Top is no longer an untapped legal source")
    if not runtime.true_state.library:
        raise ValueError("Top draw ability requires a card to draw in this model")
    state = solver.update_perm(runtime.true_state, idx, tapped=True)
    exact = (("source_tag", int(source.instance_tag)),)
    public = (("source_state", _signature(source)),)
    obj, stack = runtime.stack.allocate(
        object_type=core.STACK_TRIGGER,
        kind=ACT_TOP_DRAW,
        source=TOP,
        card=TOP,
        payload=exact,
        public_payload=public,
        strategic_payload=public,
    )
    state = solver.add_trace(state, "Phase2 activate Sensei's Divining Top draw ability")
    return replace(
        runtime,
        true_state=state,
        stack=stack.push_existing((obj,)),
        window=RuntimeDecisionWindow(WINDOW_PRIORITY),
    )


def begin_top_draw_main_action(
    runtime: core.NonOracleRuntimeState,
    action: ActionIntent,
) -> core.NonOracleRuntimeState:
    legal = {candidate.canonical_key() for candidate in top_draw_main_intents(runtime)}
    if action.canonical_key() not in legal:
        raise ValueError("Top draw action is no longer legal")
    signature = tuple(dict(action.parameters)["source_signature"])
    source = _perm_from_signature(
        runtime.true_state,
        signature,
        lambda p: p.name == TOP and not p.tapped,
    )
    if source is None:
        raise ValueError("Top draw source disappeared")
    return _push_top_draw(runtime, source)


def apply_top_priority_action(
    runtime: core.NonOracleRuntimeState,
    action: ActionIntent,
) -> core.NonOracleRuntimeState:
    legal = {candidate.canonical_key() for candidate in top_priority_actions(runtime)}
    if action.canonical_key() not in legal:
        raise ValueError("Top/Key priority action is no longer legal")
    params = dict(action.parameters)

    if action.kind == PRIORITY_ACTIVATE_TOP_DRAW:
        signature = tuple(params["source_signature"])
        source = _perm_from_signature(
            runtime.true_state,
            signature,
            lambda p: p.name == TOP and not p.tapped,
        )
        if source is None:
            raise ValueError("Top priority source disappeared")
        return _push_top_draw(runtime, source)

    if action.kind == PRIORITY_ACTIVATE_KEY:
        key_signature = tuple(params["key_signature"])
        target_signature = tuple(params["target_signature"])
        key = _perm_from_signature(
            runtime.true_state,
            key_signature,
            lambda p: p.name in KEYS and not p.tapped,
        )
        target = _perm_from_signature(
            runtime.true_state,
            target_signature,
            lambda p: solver.is_artifact_perm(p) and p.tapped,
        )
        if key is None or target is None or int(key.instance_tag) == int(target.instance_tag):
            raise ValueError("priority Key source/target is no longer legal")
        state = solver.pay(runtime.true_state, 1, 0)
        if state is None:
            raise ValueError("priority Key cost is no longer payable")
        key_idx = core._perm_index_for_tag(state, int(key.instance_tag))
        if key_idx is None:
            raise ValueError("priority Key source left battlefield")
        state = solver.update_perm(state, key_idx, tapped=True)
        exact = (
            ("source_tag", int(key.instance_tag)),
            ("target_tag", int(target.instance_tag)),
        )
        public = (
            ("source_state", _signature(key)),
            ("target_state", _signature(target)),
        )
        obj, stack = runtime.stack.allocate(
            object_type=core.STACK_TRIGGER,
            kind=ACT_KEY_UNTAP,
            source=key.name,
            card=key.name,
            payload=exact,
            public_payload=public,
            strategic_payload=public,
        )
        state = solver.add_trace(state, f"Phase2 {key.name} activates targeting {target.name or target.mode}")
        return replace(
            runtime,
            true_state=state,
            stack=stack.push_existing((obj,)),
            window=RuntimeDecisionWindow(WINDOW_PRIORITY),
        )

    raise ValueError(f"unknown Top/Key priority action {action.kind!r}")


def handles_top_stack_top(runtime: core.NonOracleRuntimeState) -> bool:
    if runtime.pending is not None:
        return False
    top = runtime.stack.top()
    return bool(top and top.kind in TOP_STACK_KINDS)


def _resolve_top_draw(runtime: core.NonOracleRuntimeState, obj) -> core.NonOracleRuntimeState:
    runtime_state = runtime.true_state
    info = runtime.information
    runtime_state, info, drawn = _draw_one(runtime_state, info, source="Sensei's Divining Top draw")
    tag = int(dict(obj.payload).get("source_tag", 0))
    idx = core._perm_index_for_tag(runtime_state, tag)
    if idx is not None and runtime_state.battlefield[idx].name == TOP:
        runtime_state = solver.remove_perm(runtime_state, idx, to_grave=False)
        runtime_state = replace(runtime_state, library=(TOP,) + tuple(runtime_state.library))
        info = apply_observation_batch(
            info,
            ObservationBatch((
                MoveKnownCardObservation(
                    TOP,
                    from_zone="battlefield",
                    to_zone="library",
                    position="top",
                    source="Sensei's Divining Top draw",
                ),
            )),
        )
        runtime_state = solver.add_trace(
            runtime_state,
            f"Phase2 Top draw resolves: drew {drawn[0] if drawn else '(empty)'}; Top to library top",
        )
    else:
        runtime_state = solver.add_trace(
            runtime_state,
            f"Phase2 Top draw resolves: drew {drawn[0] if drawn else '(empty)'}; source no longer on battlefield",
        )
    info = _refresh_continuous_top(runtime_state, info, source="post-Top-draw continuous look")
    return replace(
        runtime,
        true_state=runtime_state,
        information=info,
        window=RuntimeDecisionWindow(WINDOW_PRIORITY),
    )


def apply_top_stack_action(
    runtime: core.NonOracleRuntimeState,
    action: ActionIntent,
) -> core.NonOracleRuntimeState:
    if action.action_id != core.ACTION_PASS_PRIORITY or action.kind != "pass_priority":
        raise ValueError("Top/Key stack object resolves only after passing priority")
    obj, remaining = runtime.stack.pop_top()
    if obj is None or obj.kind not in TOP_STACK_KINDS:
        raise ValueError("top object is not a Top/Key activated ability")
    runtime = replace(runtime, stack=remaining)

    if obj.kind == ACT_TOP_DRAW:
        return _resolve_top_draw(runtime, obj)

    target_tag = int(dict(obj.payload).get("target_tag", 0))
    idx = core._perm_index_for_tag(runtime.true_state, target_tag)
    state = runtime.true_state
    if idx is not None and solver.is_artifact_perm(state.battlefield[idx]):
        target_name = state.battlefield[idx].name or state.battlefield[idx].mode
        state = solver.update_perm(state, idx, tapped=False)
        state = solver.add_trace(state, f"Phase2 {obj.source} resolves: untap {target_name}")
    else:
        state = solver.add_trace(state, f"Phase2 {obj.source} resolves with target absent")
    return replace(
        runtime,
        true_state=state,
        window=RuntimeDecisionWindow(WINDOW_PRIORITY),
    )
