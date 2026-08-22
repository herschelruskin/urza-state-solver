#!/usr/bin/env python3
"""Chrome Dome turn-boundary adapter for the Phase-2 non-Oracle runtime.

Chrome Dome creates a genuine decision after the opponent cycle has been observed:
activate in the end step immediately before our turn, or decline, and if activating
choose a public artifact target.  A token created there survives through our next
turn because that end step has already begun; its delayed sacrifice happens at the
beginning of our following end step.

This adapter also makes those delayed sacrifices explicit before advancing the turn.
Prized Statue and Sewer-veillance Cam copy LTB triggers resolve before the opponent
cycle, and a small typed continuation object keeps the turn transition replayable.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Dict, Tuple

import urza_solver as solver
import non_oracle_runtime as core
from decision_observation import (
    ActionIntent,
    DECISION_COMMIT,
    DecisionRequest,
    PendingDecisionSpec,
    PolicyDecisionContext,
)
from non_oracle_cam_runtime import queue_cam_ltb
from non_oracle_runtime_value_key import (
    RuntimeDecisionWindow,
    WINDOW_MAIN_EMPTY,
    WINDOW_POST_OBSERVATION,
    WINDOW_PRIORITY,
    WINDOW_UPKEEP,
)
from non_oracle_turn_engine import (
    _draw_one,
    _enter_precombat_main,
    _environment_draw_plan,
    _refresh_continuous_top,
)

CHROME = "Chrome Dome"
DECISION_CHROME_ENDSTEP = "runtime_chrome_endstep_choice"
BOUNDARY_AFTER_OWN_ENDSTEP = "chrome_boundary_after_own_endstep"
BOUNDARY_FINISH_NEXT_TURN = "chrome_boundary_finish_next_turn"


def _artifact_groups(state: solver.State) -> Dict[Tuple[object, ...], Tuple[object, ...]]:
    groups = {}
    for perm in state.battlefield:
        if perm.name == CHROME or not solver.is_artifact_perm(perm):
            continue
        signature = core._perm_public_signature(perm)
        groups.setdefault(signature, []).append(perm)
    return {
        signature: tuple(sorted(perms, key=lambda p: int(p.instance_tag)))
        for signature, perms in groups.items()
    }


def can_begin_chrome_end_turn(runtime: core.NonOracleRuntimeState) -> bool:
    state = runtime.true_state
    if runtime.pending is not None or runtime.stack.objects:
        return False
    if state.remora_upkeep_pending or state.saga3_pending:
        return False
    return bool(
        solver.has(state, CHROME)
        or any(p.mode in {"chrome_copy", "chrome_copy_preturn"} for p in state.battlefield)
    )


def _finish_next_turn(runtime: core.NonOracleRuntimeState, ending_turn: int) -> core.NonOracleRuntimeState:
    state = runtime.true_state
    battlefield = []
    for perm in state.battlefield:
        if perm.name in {"Mana Vault", "Grim Monolith", "Basalt Monolith"}:
            next_perm = replace(
                perm,
                sick=False,
                knack_granted=False,
                knack_source="",
                producer_urza_ready=False,
            )
        else:
            next_perm = replace(
                perm,
                tapped=False,
                sick=False,
                knack_granted=False,
                knack_source="",
                producer_urza_ready=False,
            )
        if next_perm.name == "Battered Golem":
            next_perm = replace(next_perm, tapped=False)
        if next_perm.name == "Tezzeret, Cruel Captain":
            next_perm = replace(next_perm, mode="tez_ready")
        battlefield.append(next_perm)

    next_turn = int(ending_turn) + 1
    remora_pending = solver.has(state, "Mystic Remora")
    state = replace(
        state,
        turn=next_turn,
        battlefield=tuple(battlefield),
        blue=0,
        colorless=0,
        bauble_draws=0,
        land_played=False,
        remora_age=(state.remora_age if remora_pending else 0),
        remora_upkeep_pending=remora_pending,
        spell_cast_this_turn=False,
        vfc_pumps=0,
    )
    state = solver.add_trace(state, f"--- Turn {next_turn} --- [Phase2]")
    runtime = replace(
        runtime,
        true_state=solver._ensure_oracle_instance_tags(state),
        pending=None,
    )
    if remora_pending:
        state = solver.add_trace(
            runtime.true_state,
            "Phase2 Mystic Remora cumulative-upkeep decision pending",
        )
        return replace(
            runtime,
            true_state=state,
            window=RuntimeDecisionWindow(WINDOW_UPKEEP),
        )
    return _enter_precombat_main(
        replace(runtime, window=RuntimeDecisionWindow(WINDOW_MAIN_EMPTY))
    )


def _chrome_choice_actions(runtime: core.NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    groups = _artifact_groups(runtime.true_state)
    rows = [ActionIntent(
        action_id="runtime.chrome_endstep.decline",
        kind=DECISION_CHROME_ENDSTEP,
        parameters=(("target_name", ""), ("target_signature", ())),
        equivalence_key=(DECISION_CHROME_ENDSTEP, "decline"),
        label="Chrome Dome: decline end-step copy",
        decision_stage=DECISION_COMMIT,
        source=CHROME,
    )]
    for index, signature in enumerate(sorted(groups, key=repr)):
        name = str(signature[0]) if signature else "artifact"
        rows.append(ActionIntent(
            action_id=f"runtime.chrome_endstep.copy.{index:03d}",
            kind=DECISION_CHROME_ENDSTEP,
            parameters=(("target_name", name), ("target_signature", signature)),
            equivalence_key=(DECISION_CHROME_ENDSTEP, signature),
            label=f"Chrome Dome: copy {name} in opponent end step",
            decision_stage=DECISION_COMMIT,
            source=CHROME,
        ))
    return tuple(rows)


def _after_own_endstep(runtime: core.NonOracleRuntimeState, ending_turn: int) -> core.NonOracleRuntimeState:
    state = runtime.true_state
    information = runtime.information
    environment_cards = []
    for source in _environment_draw_plan(state):
        state, information, drawn = _draw_one(
            state,
            information,
            source=f"environment:{source}",
        )
        environment_cards.extend(drawn)
    information = _refresh_continuous_top(
        state,
        information,
        source="post-opponent-cycle continuous look",
    )
    state = replace(state, blue=0, colorless=0)
    for card in environment_cards:
        state = solver.append_trace_detail(state, f"Phase2 opponent-cycle draw observed: {card}")
    runtime = replace(
        runtime,
        true_state=solver._ensure_oracle_instance_tags(state),
        information=information,
        window=RuntimeDecisionWindow(WINDOW_POST_OBSERVATION),
    )

    groups = _artifact_groups(runtime.true_state)
    capacity = solver.opponent_endstep_mana_capacity(runtime.true_state)
    cost = solver.chrome_activation_cost(runtime.true_state) if solver.has(runtime.true_state, CHROME) else 999
    if not solver.has(runtime.true_state, CHROME) or not groups or capacity < cost:
        return _finish_next_turn(runtime, ending_turn)

    spec = PendingDecisionSpec(
        decision_id=f"runtime.chrome_endstep.turn.{ending_turn}",
        kind=DECISION_CHROME_ENDSTEP,
        source=CHROME,
        decision_stage=DECISION_COMMIT,
        contingent_on=f"end-turn:{ending_turn}",
    )
    return replace(
        runtime,
        pending=core.RuntimePendingDecision(
            spec=spec,
            kind=DECISION_CHROME_ENDSTEP,
            payload=(("ending_turn", int(ending_turn)), ("activation_cost", int(cost))),
        ),
        window=RuntimeDecisionWindow(WINDOW_POST_OBSERVATION),
    )


def begin_chrome_aware_end_turn(runtime: core.NonOracleRuntimeState) -> core.NonOracleRuntimeState:
    if not can_begin_chrome_end_turn(runtime):
        raise ValueError("Chrome-aware end turn is not legal in the current runtime")
    ending_turn = int(runtime.true_state.turn)
    state = replace(runtime.true_state, blue=0, colorless=0)

    removed = []
    battlefield = []
    for perm in state.battlefield:
        if perm.mode in {"chrome_copy", "chrome_copy_preturn"}:
            removed.append(perm)
        else:
            battlefield.append(perm)
    if removed:
        state = replace(state, battlefield=tuple(battlefield))
        state = solver.add_trace(
            state,
            "Phase2 own end step sacrifices Chrome copy token(s): "
            + ", ".join(p.name or p.mode for p in removed),
        )

    runtime = replace(
        runtime,
        true_state=solver._ensure_oracle_instance_tags(state),
        permissions=runtime.permissions.expire_end_of_turn(ending_turn),
    )

    extra = []
    stack = runtime.stack
    cam_count = 0
    for perm in removed:
        if perm.name == "Prized Statue":
            obj, stack = stack.allocate(
                object_type=core.STACK_TRIGGER,
                kind="prized_dies_treasure",
                source="Prized Statue",
                card="Prized Statue",
            )
            extra.append(obj)
        if perm.name == "Sewer-veillance Cam":
            cam_count += 1
    runtime = replace(runtime, stack=stack)

    if extra or cam_count:
        continuation, stack = runtime.stack.allocate(
            object_type=core.STACK_TRIGGER,
            kind=BOUNDARY_AFTER_OWN_ENDSTEP,
            source="turn structure",
            card=CHROME,
            payload=(("ending_turn", ending_turn),),
            public_payload=(("ending_turn", ending_turn),),
            strategic_payload=(("ending_turn", ending_turn),),
        )
        runtime = replace(runtime, stack=stack.push_existing((continuation,)))
        if cam_count:
            return queue_cam_ltb(
                runtime,
                extra_objects=tuple(extra),
                count=cam_count,
                source="Chrome copy delayed sacrifice LTB",
            )
        return core._queue_simultaneous_objects(
            runtime,
            tuple(extra),
            source="Chrome copy delayed sacrifice",
        )

    return _after_own_endstep(runtime, ending_turn)


def handles_chrome_pending(runtime: core.NonOracleRuntimeState) -> bool:
    return bool(runtime.pending and runtime.pending.kind == DECISION_CHROME_ENDSTEP)


def handles_chrome_stack_top(runtime: core.NonOracleRuntimeState) -> bool:
    if runtime.pending is not None:
        return False
    top = runtime.stack.top()
    return bool(top and top.kind in {BOUNDARY_AFTER_OWN_ENDSTEP, BOUNDARY_FINISH_NEXT_TURN})


def chrome_pending_request(
    runtime: core.NonOracleRuntimeState,
    *,
    horizon: int,
    objective: str,
    policy_id: str,
    caverns_live=None,
) -> DecisionRequest:
    if not handles_chrome_pending(runtime):
        raise ValueError("not a Chrome Dome end-step decision")
    return DecisionRequest(
        observation=runtime.policy_view(caverns_live=caverns_live),
        actions=_chrome_choice_actions(runtime),
        context=PolicyDecisionContext(
            horizon=horizon,
            objective=objective,
            policy_id=policy_id,
            decision_id=runtime.pending.spec.decision_id,
            decision_stage=runtime.pending.spec.decision_stage,
        ),
    )


def apply_chrome_pending(runtime: core.NonOracleRuntimeState, action: ActionIntent) -> core.NonOracleRuntimeState:
    request = chrome_pending_request(
        runtime,
        horizon=max(1, int(runtime.true_state.turn)),
        objective="win_by_horizon",
        policy_id="runtime",
    )
    legal = {candidate.canonical_key() for candidate in request.actions}
    if action.canonical_key() not in legal:
        raise ValueError("Chrome Dome end-step choice is no longer legal")
    ending_turn = int(dict(runtime.pending.payload)["ending_turn"])
    signature = tuple(dict(action.parameters).get("target_signature", ()))
    runtime = replace(runtime, pending=None)
    if not signature:
        state = solver.add_trace(runtime.true_state, "Phase2 Chrome Dome declines opponent-end-step copy")
        return _finish_next_turn(replace(runtime, true_state=state), ending_turn)

    groups = _artifact_groups(runtime.true_state)
    candidates = groups.get(signature, ())
    if not candidates:
        raise ValueError("Chrome Dome target is no longer a legal artifact")
    target = candidates[0]
    state = solver.add_perm(
        runtime.true_state,
        target.name,
        sick=False,
        mode="chrome_copy_preturn",
    )
    state = solver.add_trace(
        state,
        f"Phase2 opponent end step Chrome Dome copies {target.name or target.mode}; survives through next turn",
    )
    runtime = replace(runtime, true_state=solver._ensure_oracle_instance_tags(state))

    continuation, stack = runtime.stack.allocate(
        object_type=core.STACK_TRIGGER,
        kind=BOUNDARY_FINISH_NEXT_TURN,
        source="turn structure",
        card=CHROME,
        payload=(("ending_turn", ending_turn),),
        public_payload=(("ending_turn", ending_turn),),
        strategic_payload=(("ending_turn", ending_turn),),
    )
    runtime = replace(
        runtime,
        stack=stack.push_existing((continuation,)),
        window=RuntimeDecisionWindow(WINDOW_PRIORITY),
    )
    return core.record_artifact_entry(
        runtime,
        (target.name,),
        source=f"Chrome Dome copy {target.name}",
    )


def apply_chrome_stack_action(runtime: core.NonOracleRuntimeState, action: ActionIntent) -> core.NonOracleRuntimeState:
    if action.action_id != core.ACTION_PASS_PRIORITY or action.kind != "pass_priority":
        raise ValueError("Chrome turn-boundary continuation resolves only after passing priority")
    obj, remaining = runtime.stack.pop_top()
    if obj is None or obj.kind not in {BOUNDARY_AFTER_OWN_ENDSTEP, BOUNDARY_FINISH_NEXT_TURN}:
        raise ValueError("top object is not a Chrome turn-boundary continuation")
    runtime = replace(runtime, stack=remaining)
    ending_turn = int(dict(obj.payload)["ending_turn"])
    if obj.kind == BOUNDARY_AFTER_OWN_ENDSTEP:
        return _after_own_endstep(runtime, ending_turn)
    return _finish_next_turn(runtime, ending_turn)
