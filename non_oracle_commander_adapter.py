#!/usr/bin/env python3
"""Typed non-Oracle command-zone casting for Urza.

This adapter is intentionally separate from the Oracle's atomic commander macro.
It preserves the real sequencing needed by the Phase-2 Markov runtime:

    commit/pay Urza from command zone
      -> Urza spell on stack
      -> simultaneous cast triggers above it (notably Artificer's Assistant)
      -> Urza resolves and enters
      -> Urza's Construct ETB trigger goes on the stack
      -> Construct is created only when that trigger resolves
      -> Construct artifact entry creates the normal typed ETB trigger wave

No policy-facing function receives the concrete hidden library.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Tuple

import urza_solver as solver
from decision_observation import ActionIntent, DECISION_COMMIT, apply_observation_batch
from non_oracle_runtime import (
    ACTION_PASS_PRIORITY,
    STACK_SPELL,
    NonOracleRuntimeState,
    RuntimeDecisionWindow,
    _cast_trigger_objects,
    _queue_simultaneous_objects,
    record_artifact_entry,
)
from non_oracle_runtime_value_key import WINDOW_PRIORITY
from trigger_order_adapter import post_cast_observations

MAIN_CAST_COMMANDER = "main_cast_commander"
COMMANDER_SPELL_KIND = "commander_spell"
URZA_CONSTRUCT_ETB_KIND = "urza_construct_etb"


def commander_cast_cost(state: solver.State) -> Tuple[int, int]:
    """Return current public command-zone cost after tax/reduction."""
    generic, blue = solver.spell_cost(state, solver.COMMANDER)
    generic += 2 * int(state.commander_casts_from_zone)
    return int(generic), int(blue)


def commander_cast_intents(runtime: NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    state = runtime.true_state
    if state.urza or not state.commander_in_command_zone:
        return ()
    generic, blue = commander_cast_cost(state)
    infinite_generic = bool(solver.infinite_colorless_online(state))
    if infinite_generic:
        legal = state.blue >= blue
    else:
        legal = solver.can_pay(state, generic, blue)
    if not legal:
        return ()
    return (
        ActionIntent(
            action_id="main.cast.commander.urza",
            kind=MAIN_CAST_COMMANDER,
            parameters=(
                ("blue_required", blue),
                ("generic_cost", generic),
                ("infinite_generic", infinite_generic),
                ("mana_spent", generic + blue),
            ),
            equivalence_key=(
                MAIN_CAST_COMMANDER,
                generic,
                blue,
                infinite_generic,
                int(state.commander_casts_from_zone),
            ),
            label=(
                f"Cast Urza from command zone for {{{generic}}}{{U}}{{U}}"
                + (" using infinite colorless" if infinite_generic else "")
            ),
            decision_stage=DECISION_COMMIT,
            source=solver.COMMANDER,
        ),
    )


def begin_commander_cast(
    runtime: NonOracleRuntimeState,
    action: ActionIntent,
) -> NonOracleRuntimeState:
    legal = {candidate.canonical_key(): candidate for candidate in commander_cast_intents(runtime)}
    if action.canonical_key() not in legal:
        raise ValueError("Urza command-zone cast is not currently legal")

    params = dict(action.parameters)
    generic = int(params["generic_cost"])
    blue = int(params["blue_required"])
    infinite_generic = bool(params["infinite_generic"])
    state = runtime.true_state

    if infinite_generic:
        if state.blue < blue:
            raise ValueError("Urza cast lost required blue mana")
        paid = replace(state, blue=state.blue - blue)
    else:
        paid = solver.pay(state, generic, blue)
        if paid is None:
            raise ValueError("Urza cast can no longer pay committed cost")

    # Casting, not resolution, consumes the command-zone opportunity and raises
    # future commander tax.  Urza itself is not yet on the battlefield.
    paid = replace(
        paid,
        spell_cast_this_turn=True,
        commander_in_command_zone=False,
        commander_casts_from_zone=paid.commander_casts_from_zone + 1,
        urza_cast_turn=(paid.urza_cast_turn or paid.turn),
    )
    paid = solver.add_trace(paid, "Phase2 cast Urza from command zone")
    runtime = replace(runtime, true_state=paid)

    spell, stack = runtime.stack.allocate(
        object_type=STACK_SPELL,
        kind=COMMANDER_SPELL_KIND,
        source="command_zone",
        card=solver.COMMANDER,
        payload=(("mana_spent", int(params["mana_spent"])),),
        public_payload=(("mana_spent", int(params["mana_spent"])),),
        strategic_payload=(("mana_spent", int(params["mana_spent"])),),
    )
    runtime = replace(runtime, stack=stack.push_existing((spell,)))

    # Continuous top-card look permissions refresh after the cast completes and
    # before simultaneous cast triggers are ordered.
    info = apply_observation_batch(
        runtime.information,
        post_cast_observations(paid, solver.COMMANDER, cast_from_library_top=False),
    )
    runtime = replace(runtime, information=info)

    triggers, allocated = _cast_trigger_objects(
        runtime,
        solver.COMMANDER,
        int(params["mana_spent"]),
        spell.object_id,
    )
    runtime = replace(runtime, stack=allocated)
    return _queue_simultaneous_objects(runtime, triggers, source="cast Urza")


def _resolve_commander_spell(runtime: NonOracleRuntimeState) -> NonOracleRuntimeState:
    obj, remaining = runtime.stack.pop_top()
    if obj is None or obj.object_type != STACK_SPELL or obj.kind != COMMANDER_SPELL_KIND:
        raise ValueError("top runtime object is not the Urza commander spell")

    state = runtime.true_state
    state = solver.add_perm(state, solver.COMMANDER, sick=True)
    state = replace(state, urza=True, construct=True)
    state = solver.add_trace(state, "Phase2 Urza resolves")
    runtime = replace(runtime, true_state=solver._ensure_oracle_instance_tags(state), stack=remaining)

    # Urza's Construct is created by an ETB triggered ability, not as part of the
    # spell resolving.  Put that trigger above any older unresolved object.
    trigger, stack = runtime.stack.allocate(
        object_type="trigger",
        kind=URZA_CONSTRUCT_ETB_KIND,
        source=solver.COMMANDER,
        card="Construct",
    )
    return replace(
        runtime,
        stack=stack.push_existing((trigger,)),
        window=RuntimeDecisionWindow(WINDOW_PRIORITY),
    )


def _resolve_construct_etb(runtime: NonOracleRuntimeState) -> NonOracleRuntimeState:
    obj, remaining = runtime.stack.pop_top()
    if obj is None or obj.kind != URZA_CONSTRUCT_ETB_KIND:
        raise ValueError("top runtime object is not Urza's Construct ETB")
    state = solver.add_perm(runtime.true_state, "Construct", sick=True, mode="construct")
    state = solver.add_trace(state, "Phase2 Urza ETB -> Construct")
    runtime = replace(
        runtime,
        true_state=solver._ensure_oracle_instance_tags(state),
        stack=remaining,
    )
    return record_artifact_entry(runtime, ("Construct",), source="Urza Construct enters")


def handles_commander_stack_top(runtime: NonOracleRuntimeState) -> bool:
    if runtime.pending is not None:
        return False
    top = runtime.stack.top()
    return bool(top and top.kind in {COMMANDER_SPELL_KIND, URZA_CONSTRUCT_ETB_KIND})


def apply_commander_stack_action(
    runtime: NonOracleRuntimeState,
    action: ActionIntent,
) -> NonOracleRuntimeState:
    if action.action_id != ACTION_PASS_PRIORITY or action.kind != "pass_priority":
        raise ValueError("commander stack slice currently resolves only after passing priority")
    top = runtime.stack.top()
    if top is None:
        raise ValueError("cannot resolve commander slice on empty stack")
    if top.kind == COMMANDER_SPELL_KIND:
        return _resolve_commander_spell(runtime)
    if top.kind == URZA_CONSTRUCT_ETB_KIND:
        return _resolve_construct_etb(runtime)
    raise ValueError("top stack object is not handled by commander adapter")
