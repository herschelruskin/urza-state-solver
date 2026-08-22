#!/usr/bin/env python3
"""Typed end-turn / next-turn transition for the Phase-2 non-Oracle runtime.

Ending the turn is a policy commitment made BEFORE future hidden draws are known.
Only after that commitment may this rules layer inspect the concrete library and
emit typed observations. This module also owns the cumulative-upkeep bridge so a
Remora choice is completed before the natural draw becomes policy-visible.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Tuple

import urza_solver as solver
from decision_observation import (
    DrawObservation,
    ObservationBatch,
    RevealTopObservation,
    apply_observation_batch,
)
from information_state_propagation import _top_visible
from non_oracle_runtime import NonOracleRuntimeState, STACK_TRIGGER
from non_oracle_runtime_value_key import (
    RuntimeDecisionWindow,
    WINDOW_MAIN_EMPTY,
    WINDOW_PRIORITY,
    WINDOW_UPKEEP,
)


class UnsupportedTurnBoundary(RuntimeError):
    """A real decision exists at the boundary but its Phase-2 adapter is not built."""


def _draw_one(state: solver.State, information, *, source: str):
    if not state.library:
        return state, information, ()
    state, drawn = solver.draw_from_library(state, 1)
    if not drawn:
        return state, information, ()
    card = str(drawn[0])
    batch = ObservationBatch((DrawObservation(card, source=source),))
    information = apply_observation_batch(information, batch)
    return state, information, (card,)


def _refresh_continuous_top(state: solver.State, information, *, source: str):
    if not state.library or not _top_visible(state):
        return information
    return apply_observation_batch(
        information,
        ObservationBatch((
            RevealTopObservation(
                (str(state.library[0]),),
                source=source,
                preserve_known_deeper=True,
            ),
        )),
    )


def _environment_draw_plan(state: solver.State) -> Tuple[str, ...]:
    names = solver.bf_name_set(state)
    rows = list(solver.pending_bauble_draw_sources(state))
    if "Mystic Remora" in names:
        rows.extend(("Mystic Remora", "Mystic Remora"))
    if "Rhystic Study" in names:
        rows.extend(("Rhystic Study", "Rhystic Study"))
    if "Faerie Mastermind" in names:
        rows.append("Faerie Mastermind")
    return tuple(rows)


def _enter_precombat_main(runtime: NonOracleRuntimeState) -> NonOracleRuntimeState:
    """Resolve the natural draw and first-main turn resources after upkeep."""
    state = runtime.true_state
    information = runtime.information
    if state.remora_upkeep_pending:
        raise ValueError("cannot enter main phase while Remora upkeep is pending")

    state, information, drawn = _draw_one(
        state,
        information,
        source=f"natural draw turn {state.turn}",
    )
    if drawn:
        state = solver.append_trace_detail(
            state,
            f"Phase2 normal draw for turn {state.turn}: {drawn[0]}",
        )

    battlefield = []
    saga3_count = 0
    for perm in state.battlefield:
        next_perm = perm
        if next_perm.name == "Urza's Saga":
            counters = next_perm.counters + 1
            next_perm = replace(
                next_perm,
                counters=counters,
                mode="saga3" if counters >= 3 else next_perm.mode,
            )
            if counters >= 3:
                saga3_count += 1
        battlefield.append(next_perm)

    state = replace(
        state,
        battlefield=tuple(battlefield),
        saga3_pending=False,
        blue=0,
        colorless=state.drain_bank,
        drain_bank=0,
    )
    information = _refresh_continuous_top(
        state,
        information,
        source="post-natural-draw continuous look",
    )
    runtime = replace(
        runtime,
        true_state=solver._ensure_oracle_instance_tags(state),
        information=information,
        window=RuntimeDecisionWindow(WINDOW_MAIN_EMPTY),
        pending=None,
    )

    if saga3_count:
        stack = runtime.stack
        triggers = []
        for _ in range(saga3_count):
            trigger, stack = stack.allocate(
                object_type=STACK_TRIGGER,
                kind="saga3_search_trigger",
                source="Urza's Saga",
                card="Urza's Saga",
            )
            triggers.append(trigger)
        runtime = replace(
            runtime,
            stack=stack.push_existing(tuple(triggers)),
            window=RuntimeDecisionWindow(WINDOW_PRIORITY),
        )
    return runtime


def resolve_remora_upkeep(
    runtime: NonOracleRuntimeState,
    *,
    pay_upkeep: bool,
) -> NonOracleRuntimeState:
    """Resolve the pending cumulative upkeep, then expose the natural draw."""
    state = runtime.true_state
    if not state.remora_upkeep_pending or not solver.has(state, "Mystic Remora"):
        raise ValueError("no live Mystic Remora cumulative upkeep to resolve")

    cost = int(state.remora_age) + 1
    if pay_upkeep:
        paid = solver.pay(state, cost, 0)
        if paid is None:
            raise ValueError("Mystic Remora cumulative upkeep cannot currently be paid")
        state = replace(paid, remora_age=cost, remora_upkeep_pending=False)
        state = solver.add_trace(state, f"Phase2 Mystic Remora cumulative upkeep {{{cost}}}: pay")
    else:
        index = next(i for i, perm in enumerate(state.battlefield) if perm.name == "Mystic Remora")
        state = solver.remove_perm(state, index, to_grave=True)
        state = solver.add_trace(
            state,
            f"Phase2 Mystic Remora cumulative upkeep {{{cost}}}: decline; sacrifice Mystic Remora",
        )

    # Mana floated to resolve cumulative upkeep empties before the precombat main.
    state = replace(state, blue=0, colorless=0)
    return _enter_precombat_main(
        replace(
            runtime,
            true_state=solver._ensure_oracle_instance_tags(state),
            window=RuntimeDecisionWindow(WINDOW_MAIN_EMPTY),
            pending=None,
        )
    )


def can_commit_end_turn(runtime: NonOracleRuntimeState) -> bool:
    state = runtime.true_state
    if runtime.pending is not None or runtime.stack.objects:
        return False
    if state.remora_upkeep_pending or state.saga3_pending:
        return False
    if solver.has(state, "Chrome Dome"):
        return False
    if any(p.mode in {"chrome_copy", "chrome_copy_preturn"} for p in state.battlefield):
        return False
    return True


def advance_after_end_turn(runtime: NonOracleRuntimeState) -> NonOracleRuntimeState:
    """Resolve one committed end turn through the next policy-visible window."""
    if not can_commit_end_turn(runtime):
        raise UnsupportedTurnBoundary(
            "end-turn boundary has unresolved mandatory/Chrome runtime decisions"
        )

    state = runtime.true_state
    information = runtime.information
    ending_turn = int(state.turn)

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

    next_turn = ending_turn + 1
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
    for card in environment_cards:
        state = solver.append_trace_detail(state, f"Phase2 opponent-cycle draw observed: {card}")

    permissions = runtime.permissions.expire_end_of_turn(ending_turn)
    runtime = replace(
        runtime,
        true_state=solver._ensure_oracle_instance_tags(state),
        information=information,
        permissions=permissions,
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
