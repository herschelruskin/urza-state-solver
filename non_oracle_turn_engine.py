#!/usr/bin/env python3
"""Typed end-turn / next-turn transition for the Phase-2 non-Oracle runtime.

Ending the turn is a policy commitment made BEFORE future hidden draws are known.
Only after that commitment may this rules layer inspect the concrete library and
emit typed observations.  This is the same anti-clairvoyance boundary used by Top,
scry, and tutors.

The first version intentionally blocks Chrome-Dome end-step copy automation.  That
is a real optional decision and must later be exposed to the policy rather than
silently taking the Oracle heuristic.  Ordinary turns, environmental draw engines,
Urza permission expiry, natural draw, Saga lore advancement, and Mana Drain bank
release are handled here.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable, Tuple

import urza_solver as solver
from decision_observation import (
    DrawObservation,
    ObservationBatch,
    RevealTopObservation,
    apply_observation_batch,
)
from information_state_propagation import _top_visible
from non_oracle_runtime import NonOracleRuntimeState
from non_oracle_runtime_value_key import RuntimeDecisionWindow, WINDOW_MAIN_EMPTY


class UnsupportedTurnBoundary(RuntimeError):
    """A real decision exists at the boundary but its Phase-2 adapter is not built."""


def _draw_one(
    state: solver.State,
    information,
    *,
    source: str,
):
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


def can_commit_end_turn(runtime: NonOracleRuntimeState) -> bool:
    state = runtime.true_state
    if runtime.pending is not None or runtime.stack.objects:
        return False
    if state.remora_upkeep_pending or state.saga3_pending:
        return False
    # Chrome Dome activation in the opponent end step is optional and therefore
    # must become a real policy decision before we support it here.
    if solver.has(state, "Chrome Dome"):
        return False
    # Existing delayed Chrome copies are sacrificed at our end step and can have
    # LTB consequences. Route those through the typed sacrifice engine later.
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

    # Environmental draw assumptions occur during the opponent cycle.  These are
    # chance observations after the end-turn decision, never action-generation
    # inputs. No policy decisions are currently modeled between these abstract
    # opponent events, so refresh continuous top visibility after the batch.
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

    # End-of-turn floating resources disappear, then untap/cleanup occurs for the
    # next turn.  Mana Vault / Monoliths preserve the validated Oracle assumption
    # of remaining tapped. Temporary Knack/VFC/producer credits expire.
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
        remora_age=(state.remora_age if solver.has(state, "Mystic Remora") else 0),
        remora_upkeep_pending=remora_pending,
        spell_cast_this_turn=False,
        vfc_pumps=0,
    )
    state = solver.add_trace(state, f"--- Turn {next_turn} --- [Phase2]")
    for card in environment_cards:
        state = solver.append_trace_detail(state, f"Phase2 opponent-cycle draw observed: {card}")

    permissions = runtime.permissions.expire_end_of_turn(ending_turn)

    # Remora cumulative upkeep is a mandatory decision before natural draw/main.
    # Leave the runtime at that public blocked window; its Phase-2 adapter is the
    # next mandatory-window slice.
    if remora_pending:
        state = solver.add_trace(
            state,
            "Phase2 Mystic Remora cumulative-upkeep decision pending",
        )
        return replace(
            runtime,
            true_state=state,
            information=information,
            permissions=permissions,
            window=RuntimeDecisionWindow(WINDOW_MAIN_EMPTY),
            pending=None,
        )

    # Natural draw happens before Saga's turn-based lore counter is added.
    state, information, drawn = _draw_one(
        state,
        information,
        source=f"natural draw turn {next_turn}",
    )
    if drawn:
        state = solver.append_trace_detail(
            state,
            f"Phase2 normal draw for turn {next_turn}: {drawn[0]}",
        )

    # First precombat main: Saga lore advances and Mana Drain bank is released.
    battlefield = []
    saga3_pending = state.saga3_pending
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
                saga3_pending = True
        battlefield.append(next_perm)
    state = replace(
        state,
        battlefield=tuple(battlefield),
        saga3_pending=saga3_pending,
        blue=0,
        colorless=state.drain_bank,
        drain_bank=0,
    )
    information = _refresh_continuous_top(
        state,
        information,
        source="post-natural-draw continuous look",
    )

    return replace(
        runtime,
        true_state=solver._ensure_oracle_instance_tags(state),
        information=information,
        permissions=permissions,
        window=RuntimeDecisionWindow(WINDOW_MAIN_EMPTY),
        pending=None,
    )
