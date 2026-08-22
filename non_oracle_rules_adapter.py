#!/usr/bin/env python3
"""Phase-2 non-Oracle rules adapter: public main-phase actions + typed runtime.

This is intentionally NOT a wrapper around ``urza_solver.legal_actions``.  The
Oracle action generator contains already-resolved hidden-information branches and
search pruning whose candidate set can depend on the concrete hidden future.

The adapter admits only audited safe families: land plays, public mana abilities,
Urza artifact taps, ordinary artifact casts through the typed stack, and end-turn
commitment followed by typed chance observations. Hidden-information families are
added through their Phase-1 staged adapters, never by importing Oracle successors.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, Iterable, Tuple

import urza_solver as solver
from decision_observation import ActionIntent, DECISION_COMMIT, DecisionRequest, PolicyDecisionContext
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
)
from non_oracle_turn_engine import advance_after_end_turn, can_commit_end_turn

MAIN_PLAY_LAND = "main_play_land"
MAIN_MANA_ACTION = "main_mana_action"
MAIN_CAST_ARTIFACT = "main_cast_artifact"
MAIN_END_TURN = "main_end_turn"
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
    if not can_commit_end_turn(runtime):
        return ()
    return (ActionIntent(
        action_id="main.end_turn", kind=MAIN_END_TURN,
        parameters=(("ending_turn", int(runtime.true_state.turn)),),
        equivalence_key=(MAIN_END_TURN, int(runtime.true_state.turn)),
        label=f"End turn {runtime.true_state.turn}",
        decision_stage=DECISION_COMMIT, source="turn structure",
    ),)


def _normalize_empty_stack_main_window(runtime: NonOracleRuntimeState) -> NonOracleRuntimeState:
    """Empty stack + our main-phase priority is the main_empty decision window."""
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
    if runtime.pending is not None or runtime.stack.objects:
        return runtime_decision_request(
            runtime, horizon=horizon, objective=objective,
            policy_id=policy_id, caverns_live=caverns_live,
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
        raise ValueError("main action is no longer legal in current state") from exc


def apply_main_action(runtime: NonOracleRuntimeState, action: ActionIntent) -> NonOracleRuntimeState:
    if runtime.pending is not None or runtime.stack.objects:
        return _normalize_empty_stack_main_window(apply_runtime_action(runtime, action))
    runtime = _normalize_empty_stack_main_window(runtime)
    legal = {candidate.canonical_key(): candidate for candidate in main_phase_intents(runtime)}
    if action.canonical_key() not in legal:
        raise ValueError("action is not legal in the current main-phase request")

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

    if action.kind == MAIN_END_TURN:
        return advance_after_end_turn(runtime)

    raise AssertionError(f"unhandled main action kind {action.kind!r}")
