#!/usr/bin/env python3
"""Phase-2 non-Oracle rules adapter: public actions + typed runtime.

This is intentionally NOT a wrapper around ``urza_solver.legal_actions``. The
Oracle action generator contains already-resolved hidden-information branches and
search pruning whose candidate set can depend on the concrete hidden future.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, Iterable, Tuple

import urza_solver as solver

# Install card-specific runtime dispatch before the other Phase-2 adapters import
# symbols from non_oracle_runtime. This keeps Cam target choice in the typed runtime
# rather than falling back to the Oracle's already-resolved successor branches.
from non_oracle_cam_runtime import install_cam_runtime_extension
install_cam_runtime_extension()

from decision_observation import ActionIntent, DECISION_COMMIT, DecisionRequest, PolicyDecisionContext
from non_oracle_commander_adapter import (
    MAIN_CAST_COMMANDER,
    apply_commander_stack_action,
    begin_commander_cast,
    commander_cast_intents,
    handles_commander_stack_top,
)
from non_oracle_proactive_spell_adapter import (
    MAIN_CAST_PROACTIVE_NONARTIFACT,
    apply_proactive_stack_action,
    begin_proactive_nonartifact_cast,
    handles_proactive_stack_top,
    proactive_nonartifact_intents,
)
from non_oracle_simple_tutor_runtime import (
    MAIN_USE_SIMPLE_TUTOR,
    apply_simple_tutor_pending,
    apply_simple_tutor_stack_action,
    begin_simple_tutor,
    handles_simple_tutor_pending,
    handles_simple_tutor_stack_top,
    simple_tutor_pending_request,
    simple_tutor_runtime_intents,
)
from non_oracle_x_artifact_tutor_runtime import (
    MAIN_USE_X_ARTIFACT_TUTOR,
    apply_x_artifact_pending,
    apply_x_artifact_stack_action,
    begin_x_artifact_tutor,
    handles_x_artifact_pending,
    handles_x_artifact_stack_top,
    x_artifact_pending_request,
    x_artifact_runtime_intents,
)
from non_oracle_transmute_runtime import (
    MAIN_USE_TRANSMUTE_ARTIFACT,
    apply_transmute_pending,
    apply_transmute_stack_action,
    begin_transmute,
    handles_transmute_pending,
    handles_transmute_stack_top,
    transmute_pending_request,
    transmute_runtime_intents,
)
from non_oracle_remaining_search_runtime import (
    MAIN_ACTIVATE_BAY,
    MAIN_ACTIVATE_TEZZ_MINUS3,
    MAIN_CAST_SCOUR,
    apply_remaining_main_action,
    apply_remaining_pending,
    apply_remaining_stack_action,
    handles_remaining_pending,
    handles_remaining_stack_top,
    remaining_pending_request,
    remaining_search_main_intents,
)
from non_oracle_runtime import (
    NonOracleRuntimeState,
    apply_runtime_action,
    begin_committed_artifact_cast,
    record_artifact_entry,
    runtime_decision_request,
)
from non_oracle_runtime_value_key import (
    RuntimeDecisionWindow,
    WINDOW_MAIN_EMPTY,
    WINDOW_PRIORITY,
    WINDOW_UPKEEP,
)
from non_oracle_turn_engine import (
    advance_after_end_turn,
    can_commit_end_turn,
    resolve_remora_upkeep,
)
from non_oracle_chrome_dome_runtime import (
    apply_chrome_pending,
    apply_chrome_stack_action,
    begin_chrome_aware_end_turn,
    can_begin_chrome_end_turn,
    chrome_pending_request,
    handles_chrome_pending,
    handles_chrome_stack_top,
)
from non_oracle_chrome_priority_runtime import (
    PRIORITY_ACTIVATE_CHROME,
    apply_chrome_priority_action,
)
from non_oracle_utility_artifact_runtime import (
    MAIN_ACTIVATE_KEY,
    MAIN_ACTIVATE_TOP,
    MAIN_CAST_UTILITY_ARTIFACT,
    apply_utility_pending,
    apply_utility_stack_action,
    begin_utility_main_action,
    handles_utility_pending,
    handles_utility_stack_top,
    utility_main_intents,
    utility_pending_request,
)
from non_oracle_draw_engine_runtime import (
    MAIN_CAST_PROBE,
    MAIN_DRAW_ACTIVATION,
    apply_draw_stack_action,
    begin_draw_engine_main_action,
    draw_engine_main_intents,
    handles_draw_stack_top,
)
from non_oracle_top_draw_runtime import (
    MAIN_ACTIVATE_TOP_DRAW,
    PRIORITY_ACTIVATE_KEY,
    PRIORITY_ACTIVATE_TOP_DRAW,
    apply_top_priority_action,
    apply_top_stack_action,
    begin_top_draw_main_action,
    handles_top_stack_top,
    top_draw_main_intents,
)
from non_oracle_urza_runtime import (
    MAIN_ACTIVATE_URZA_SPIN,
    MAIN_USE_URZA_PERMISSION,
    apply_urza_stack_action,
    begin_urza_main_action,
    begin_urza_priority_action,
    handles_urza_stack_top,
    urza_main_intents,
)
from non_oracle_engine_activation_runtime import (
    MAIN_ACTIVATE_CHIP_RECONFIGURE,
    MAIN_ACTIVATE_UTHROS_STATION,
    apply_engine_stack_action,
    begin_engine_activation,
    engine_activation_main_intents,
    handles_engine_stack_top,
)
from non_oracle_mill_runtime import (
    MAIN_ACTIVATE_CODEX_MILL,
    MAIN_ACTIVATE_STATION_MILL,
    PRIORITY_ACTIVATE_CODEX_MILL,
    PRIORITY_ACTIVATE_STATION_MILL,
    apply_mill_priority_action,
    apply_mill_stack_action,
    begin_mill_main_action,
    extended_priority_actions,
    extended_priority_request,
    handles_mill_stack_top,
    mill_main_intents,
)
from non_oracle_top_access_runtime import (
    begin_top_access_main_action,
    begin_top_access_priority_action,
    is_top_access_action,
    is_top_access_priority_action,
    top_access_main_intents,
)

MAIN_PLAY_LAND = "main_play_land"
MAIN_MANA_ACTION = "main_mana_action"
MAIN_CAST_ARTIFACT = "main_cast_artifact"
MAIN_END_TURN = "main_end_turn"
UPKEEP_PAY_REMORA = "upkeep_pay_remora"
UPKEEP_DECLINE_REMORA = "upkeep_decline_remora"
SPECIAL_ARTIFACT_CASTS = frozenset({"Mox Diamond", "Everflowing Chalice"})


@dataclass(frozen=True)
class _MechanicalSuccessor:
    action: ActionIntent
    state: solver.State


def _public_perm_key(perm) -> Tuple[object, ...]:
    return (
        str(perm.name), bool(perm.tapped), bool(perm.sick), int(perm.counters),
        str(perm.mode), bool(perm.knack_granted), bool(perm.producer_urza_ready),
    )


def _state_resource_delta(before: solver.State, after: solver.State) -> Tuple[object, ...]:
    return (
        int(after.blue - before.blue), int(after.colorless - before.colorless),
        tuple(sorted(after.hand)),
        tuple(sorted(_public_perm_key(p) for p in after.battlefield)),
        tuple(sorted(after.graveyard)), tuple(sorted(after.exile)),
        bool(after.land_played),
    )


def _safe_successor_actions(
    state: solver.State,
    successors: Iterable[solver.State],
    *,
    family: str,
) -> Tuple[_MechanicalSuccessor, ...]:
    unique: Dict[Tuple[object, ...], solver.State] = {}
    for successor in successors:
        signature = _state_resource_delta(state, successor)
        unique.setdefault(signature, successor)

    rows = []
    for index, (signature, successor) in enumerate(sorted(unique.items(), key=lambda kv: repr(kv[0]))):
        label = successor.trace[-1].splitlines()[0] if successor.trace else family
        action = ActionIntent(
            action_id=f"{family}.{index:03d}",
            kind=family,
            parameters=(
                ("blue_delta", int(successor.blue - state.blue)),
                ("colorless_delta", int(successor.colorless - state.colorless)),
                ("mechanical_index", index),
            ),
            equivalence_key=(family, signature),
            label=label,
            decision_stage=DECISION_COMMIT,
            source=family,
        )
        rows.append(_MechanicalSuccessor(action, successor))
    return tuple(rows)


def _land_rows(runtime: NonOracleRuntimeState) -> Tuple[_MechanicalSuccessor, ...]:
    state = runtime.true_state
    rows = []
    for card in sorted(set(state.hand)):
        if card not in solver.ALL_LANDS:
            continue
        physical = solver._play_land_physical(state, card)
        if physical is None:
            continue
        next_state, message = physical
        next_state = solver.add_trace(next_state, message)
        signature = (card, _state_resource_delta(state, next_state))
        rows.append(_MechanicalSuccessor(
            ActionIntent(
                action_id=f"main.land.{card}", kind=MAIN_PLAY_LAND,
                parameters=(("card", card),),
                equivalence_key=(MAIN_PLAY_LAND, signature),
                label=f"Play land {card}", decision_stage=DECISION_COMMIT, source=card,
            ),
            next_state,
        ))
    return tuple(rows)


def _mana_rows(runtime: NonOracleRuntimeState) -> Tuple[_MechanicalSuccessor, ...]:
    state = runtime.true_state
    successors = tuple(solver.intrinsic_mana_actions(state)) + tuple(solver.tap_artifact_for_urza_actions(state))
    return _safe_successor_actions(state, successors, family=MAIN_MANA_ACTION)


def _ordinary_artifact_cast_intents(runtime: NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    state = runtime.true_state
    rows = []
    for card in sorted(set(state.hand)):
        if card not in solver.ARTIFACTS or card in solver.ALL_LANDS or card in SPECIAL_ARTIFACT_CASTS:
            continue
        generic, blue_req = solver.spell_cost(state, card)
        mana_spent = int(generic + blue_req)
        if not solver.can_pay(state, generic, blue_req):
            continue
        rows.append(ActionIntent(
            action_id=f"main.cast.artifact.{card}",
            kind=MAIN_CAST_ARTIFACT,
            parameters=(
                ("blue_required", int(blue_req)), ("card", card),
                ("generic_cost", int(generic)), ("mana_spent", mana_spent),
            ),
            equivalence_key=(MAIN_CAST_ARTIFACT, card, int(generic), int(blue_req)),
            label=f"Cast {card}", decision_stage=DECISION_COMMIT, source=card,
        ))
    return tuple(rows)


def _end_turn_intent(runtime: NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    if not can_commit_end_turn(runtime) and not can_begin_chrome_end_turn(runtime):
        return ()
    return (ActionIntent(
        action_id="main.end_turn", kind=MAIN_END_TURN,
        parameters=(("ending_turn", int(runtime.true_state.turn)),),
        equivalence_key=(MAIN_END_TURN, int(runtime.true_state.turn)),
        label=f"End turn {runtime.true_state.turn}",
        decision_stage=DECISION_COMMIT, source="turn structure",
    ),)


def _remora_upkeep_intents(runtime: NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    state = runtime.true_state
    if not state.remora_upkeep_pending or not solver.has(state, "Mystic Remora"):
        return ()
    cost = int(state.remora_age) + 1
    rows = [row.action for row in _mana_rows(runtime)]
    rows.append(ActionIntent(
        action_id="upkeep.remora.decline",
        kind=UPKEEP_DECLINE_REMORA,
        parameters=(("cost", cost),),
        equivalence_key=(UPKEEP_DECLINE_REMORA, cost),
        label=f"Decline Mystic Remora cumulative upkeep {{{cost}}}",
        decision_stage=DECISION_COMMIT,
        source="Mystic Remora",
    ))
    if solver.can_pay(state, cost, 0):
        rows.append(ActionIntent(
            action_id="upkeep.remora.pay",
            kind=UPKEEP_PAY_REMORA,
            parameters=(("cost", cost),),
            equivalence_key=(UPKEEP_PAY_REMORA, cost),
            label=f"Pay Mystic Remora cumulative upkeep {{{cost}}}",
            decision_stage=DECISION_COMMIT,
            source="Mystic Remora",
        ))
    return tuple(sorted(rows, key=lambda action: action.action_id))


def _normalize_empty_stack_main_window(runtime: NonOracleRuntimeState) -> NonOracleRuntimeState:
    if (
        runtime.pending is None
        and not runtime.stack.objects
        and runtime.window.kind == WINDOW_PRIORITY
    ):
        return replace(runtime, window=RuntimeDecisionWindow(WINDOW_MAIN_EMPTY))
    return runtime


def main_phase_intents(runtime: NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    state = runtime.true_state
    if runtime.pending is not None or runtime.stack.objects:
        return ()
    if runtime.window.kind != WINDOW_MAIN_EMPTY:
        return ()
    if state.remora_upkeep_pending or state.saga3_pending:
        return ()
    rows = [row.action for row in _land_rows(runtime)]
    rows.extend(row.action for row in _mana_rows(runtime))
    rows.extend(_ordinary_artifact_cast_intents(runtime))
    rows.extend(utility_main_intents(runtime))
    rows.extend(top_draw_main_intents(runtime))
    rows.extend(draw_engine_main_intents(runtime))
    rows.extend(proactive_nonartifact_intents(runtime))
    rows.extend(simple_tutor_runtime_intents(runtime))
    rows.extend(x_artifact_runtime_intents(runtime))
    rows.extend(transmute_runtime_intents(runtime))
    rows.extend(remaining_search_main_intents(runtime))
    rows.extend(commander_cast_intents(runtime))
    rows.extend(urza_main_intents(runtime))
    rows.extend(engine_activation_main_intents(runtime))
    rows.extend(mill_main_intents(runtime))
    rows.extend(top_access_main_intents(runtime))
    rows.extend(_end_turn_intent(runtime))
    return tuple(sorted(rows, key=lambda action: action.action_id))


def rules_decision_request(
    runtime: NonOracleRuntimeState,
    *,
    horizon: int,
    objective: str = "win_by_horizon",
    policy_id: str = "urza-deterministic-base-v1",
    caverns_live=None,
) -> DecisionRequest:
    if handles_utility_pending(runtime):
        return utility_pending_request(
            runtime, horizon=horizon, objective=objective,
            policy_id=policy_id, caverns_live=caverns_live,
        )
    if handles_simple_tutor_pending(runtime):
        return simple_tutor_pending_request(
            runtime, horizon=horizon, objective=objective,
            policy_id=policy_id, caverns_live=caverns_live,
        )
    if handles_x_artifact_pending(runtime):
        return x_artifact_pending_request(
            runtime, horizon=horizon, objective=objective,
            policy_id=policy_id, caverns_live=caverns_live,
        )
    if handles_transmute_pending(runtime):
        return transmute_pending_request(
            runtime, horizon=horizon, objective=objective,
            policy_id=policy_id, caverns_live=caverns_live,
        )
    if handles_remaining_pending(runtime):
        return remaining_pending_request(
            runtime, horizon=horizon, objective=objective,
            policy_id=policy_id, caverns_live=caverns_live,
        )
    if handles_chrome_pending(runtime):
        return chrome_pending_request(
            runtime, horizon=horizon, objective=objective,
            policy_id=policy_id, caverns_live=caverns_live,
        )
    if runtime.pending is not None:
        return runtime_decision_request(
            runtime, horizon=horizon, objective=objective,
            policy_id=policy_id, caverns_live=caverns_live,
        )
    if runtime.stack.objects:
        if extended_priority_actions(runtime):
            return extended_priority_request(
                runtime, horizon=horizon, objective=objective,
                policy_id=policy_id, caverns_live=caverns_live,
            )
        return runtime_decision_request(
            runtime, horizon=horizon, objective=objective,
            policy_id=policy_id, caverns_live=caverns_live,
        )
    if runtime.true_state.remora_upkeep_pending:
        return DecisionRequest(
            observation=runtime.policy_view(caverns_live=caverns_live),
            actions=_remora_upkeep_intents(runtime),
            context=PolicyDecisionContext(
                horizon=horizon, objective=objective, policy_id=policy_id,
                decision_id=f"upkeep.remora.turn.{runtime.true_state.turn}",
                decision_stage=DECISION_COMMIT,
            ),
        )
    runtime = _normalize_empty_stack_main_window(runtime)
    return DecisionRequest(
        observation=runtime.policy_view(caverns_live=caverns_live),
        actions=main_phase_intents(runtime),
        context=PolicyDecisionContext(
            horizon=horizon, objective=objective, policy_id=policy_id,
            decision_id=f"main.turn.{runtime.true_state.turn}",
            decision_stage=DECISION_COMMIT,
        ),
    )


def _find_mechanical_successor(runtime: NonOracleRuntimeState, action: ActionIntent) -> solver.State:
    if action.kind == MAIN_PLAY_LAND:
        rows = _land_rows(runtime)
    elif action.kind == MAIN_MANA_ACTION:
        rows = _mana_rows(runtime)
    else:
        raise ValueError(f"{action.kind!r} is not a mechanical main action")
    legal = {row.action.canonical_key(): row.state for row in rows}
    try:
        return legal[action.canonical_key()]
    except KeyError as exc:
        raise ValueError("mechanical action is no longer legal in current state") from exc


def apply_main_action(runtime: NonOracleRuntimeState, action: ActionIntent) -> NonOracleRuntimeState:
    if runtime.pending is not None or runtime.stack.objects:
        if action.kind in {PRIORITY_ACTIVATE_TOP_DRAW, PRIORITY_ACTIVATE_KEY}:
            return apply_top_priority_action(runtime, action)
        if action.kind in {PRIORITY_ACTIVATE_STATION_MILL, PRIORITY_ACTIVATE_CODEX_MILL}:
            return apply_mill_priority_action(runtime, action)
        if action.kind == PRIORITY_ACTIVATE_CHROME:
            return apply_chrome_priority_action(runtime, action)
        if action.kind in {MAIN_ACTIVATE_URZA_SPIN, MAIN_USE_URZA_PERMISSION}:
            return begin_urza_priority_action(runtime, action)
        if is_top_access_priority_action(action):
            return begin_top_access_priority_action(runtime, action)
        if handles_utility_pending(runtime):
            resolved = apply_utility_pending(runtime, action)
        elif handles_simple_tutor_pending(runtime):
            resolved = apply_simple_tutor_pending(runtime, action)
        elif handles_x_artifact_pending(runtime):
            resolved = apply_x_artifact_pending(runtime, action)
        elif handles_transmute_pending(runtime):
            resolved = apply_transmute_pending(runtime, action)
        elif handles_remaining_pending(runtime):
            resolved = apply_remaining_pending(runtime, action)
        elif handles_chrome_pending(runtime):
            resolved = apply_chrome_pending(runtime, action)
        elif handles_top_stack_top(runtime):
            resolved = apply_top_stack_action(runtime, action)
        elif handles_draw_stack_top(runtime):
            resolved = apply_draw_stack_action(runtime, action)
        elif handles_utility_stack_top(runtime):
            resolved = apply_utility_stack_action(runtime, action)
        elif handles_urza_stack_top(runtime):
            resolved = apply_urza_stack_action(runtime, action)
        elif handles_engine_stack_top(runtime):
            resolved = apply_engine_stack_action(runtime, action)
        elif handles_mill_stack_top(runtime):
            resolved = apply_mill_stack_action(runtime, action)
        elif handles_chrome_stack_top(runtime):
            resolved = apply_chrome_stack_action(runtime, action)
        elif handles_commander_stack_top(runtime):
            resolved = apply_commander_stack_action(runtime, action)
        elif handles_proactive_stack_top(runtime):
            resolved = apply_proactive_stack_action(runtime, action)
        elif handles_simple_tutor_stack_top(runtime):
            resolved = apply_simple_tutor_stack_action(runtime, action)
        elif handles_x_artifact_stack_top(runtime):
            resolved = apply_x_artifact_stack_action(runtime, action)
        elif handles_transmute_stack_top(runtime):
            resolved = apply_transmute_stack_action(runtime, action)
        elif handles_remaining_stack_top(runtime):
            resolved = apply_remaining_stack_action(runtime, action)
        else:
            resolved = apply_runtime_action(runtime, action)
        return _normalize_empty_stack_main_window(resolved)

    if runtime.true_state.remora_upkeep_pending:
        legal = {candidate.canonical_key(): candidate for candidate in _remora_upkeep_intents(runtime)}
        if action.canonical_key() not in legal:
            raise ValueError("action is not legal in the current Remora upkeep request")
        if action.kind == MAIN_MANA_ACTION:
            next_state = _find_mechanical_successor(runtime, action)
            return replace(
                runtime,
                true_state=solver._ensure_oracle_instance_tags(next_state),
                window=RuntimeDecisionWindow(WINDOW_UPKEEP),
            )
        if action.kind == UPKEEP_PAY_REMORA:
            return resolve_remora_upkeep(runtime, pay_upkeep=True)
        if action.kind == UPKEEP_DECLINE_REMORA:
            return resolve_remora_upkeep(runtime, pay_upkeep=False)
        raise AssertionError(f"unhandled upkeep action kind {action.kind!r}")

    runtime = _normalize_empty_stack_main_window(runtime)
    legal = {candidate.canonical_key(): candidate for candidate in main_phase_intents(runtime)}
    if action.canonical_key() not in legal:
        raise ValueError("action is not legal in the current main-phase request")

    if is_top_access_action(action):
        return begin_top_access_main_action(runtime, action)

    if action.kind in {MAIN_PLAY_LAND, MAIN_MANA_ACTION}:
        next_state = _find_mechanical_successor(runtime, action)
        out = replace(runtime, true_state=solver._ensure_oracle_instance_tags(next_state))
        if action.kind == MAIN_PLAY_LAND and dict(action.parameters)["card"] == "Seat of the Synod":
            out = record_artifact_entry(out, ("Seat of the Synod",), source="play Seat of the Synod")
        return out

    if action.kind == MAIN_CAST_ARTIFACT:
        params = dict(action.parameters)
        card = str(params["card"])
        generic = int(params["generic_cost"])
        blue_req = int(params["blue_required"])
        paid = solver.pay(runtime.true_state, generic, blue_req)
        if paid is None:
            raise ValueError("committed artifact cast can no longer pay its cost")
        return begin_committed_artifact_cast(
            replace(runtime, true_state=paid), card,
            mana_spent=int(params["mana_spent"]), from_zone="hand",
        )

    if action.kind in {MAIN_CAST_UTILITY_ARTIFACT, MAIN_ACTIVATE_TOP, MAIN_ACTIVATE_KEY}:
        return begin_utility_main_action(runtime, action)
    if action.kind == MAIN_ACTIVATE_TOP_DRAW:
        return begin_top_draw_main_action(runtime, action)
    if action.kind in {MAIN_CAST_PROBE, MAIN_DRAW_ACTIVATION}:
        return begin_draw_engine_main_action(runtime, action)
    if action.kind == MAIN_CAST_PROACTIVE_NONARTIFACT:
        return begin_proactive_nonartifact_cast(runtime, action)
    if action.kind == MAIN_USE_SIMPLE_TUTOR:
        return begin_simple_tutor(runtime, action)
    if action.kind == MAIN_USE_X_ARTIFACT_TUTOR:
        return begin_x_artifact_tutor(runtime, action)
    if action.kind == MAIN_USE_TRANSMUTE_ARTIFACT:
        return begin_transmute(runtime, action)
    if action.kind in {MAIN_ACTIVATE_BAY, MAIN_CAST_SCOUR, MAIN_ACTIVATE_TEZZ_MINUS3}:
        return apply_remaining_main_action(runtime, action)
    if action.kind == MAIN_CAST_COMMANDER:
        return begin_commander_cast(runtime, action)
    if action.kind in {MAIN_ACTIVATE_URZA_SPIN, MAIN_USE_URZA_PERMISSION}:
        return begin_urza_main_action(runtime, action)
    if action.kind in {MAIN_ACTIVATE_CHIP_RECONFIGURE, MAIN_ACTIVATE_UTHROS_STATION}:
        return begin_engine_activation(runtime, action)
    if action.kind in {MAIN_ACTIVATE_STATION_MILL, MAIN_ACTIVATE_CODEX_MILL}:
        return begin_mill_main_action(runtime, action)
    if action.kind == MAIN_END_TURN:
        if can_begin_chrome_end_turn(runtime):
            return begin_chrome_aware_end_turn(runtime)
        return advance_after_end_turn(runtime)

    raise AssertionError(f"unhandled main action kind {action.kind!r}")
