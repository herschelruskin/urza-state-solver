#!/usr/bin/env python3
"""Compact Phase-2 engine activations: Reality Chip reconfigure + Uthros Station.

Both abilities are sorcery-speed, public-board commitments and therefore fit one
small runtime slice without touching hidden library order:

* The Reality Chip -- pay its current reconfigure cost, then attach/move it to a
  committed controlled creature or unattach it.  The source/target remain unchanged
  until the activated ability resolves.
* Uthros Research Craft -- tap another controlled creature as the Station cost,
  then put charge counters equal to that creature's committed public power on Uthros
  when the ability resolves.

Uthros's existing >=3 artifact-cast trigger is already implemented by the shared
runtime stack.  Reconfigure intentionally does NOT implement casting/playing from
library top; that information-sensitive surface is a separate later batch.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Dict, Tuple

import urza_solver as solver
import non_oracle_runtime as core
from decision_observation import ActionIntent, DECISION_COMMIT
from non_oracle_runtime_value_key import RuntimeDecisionWindow, WINDOW_PRIORITY

MAIN_ACTIVATE_CHIP_RECONFIGURE = "main_activate_chip_reconfigure"
MAIN_ACTIVATE_UTHROS_STATION = "main_activate_uthros_station"

ACT_CHIP_RECONFIGURE = "activated_chip_reconfigure"
ACT_UTHROS_STATION = "activated_uthros_station"

CHIP = "The Reality Chip"
UTHROS = "Uthros Research Craft"


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


def _chip_cost(state: solver.State) -> Tuple[int, int]:
    generic, blue = 2, 1
    if solver.has(state, "Forensic Gadgeteer"):
        generic = max(0, generic - 1)
    if state.pa_target == CHIP:
        generic = max(0, generic - 2)
    return generic, blue


def _chip_source(state: solver.State):
    return next((perm for perm in state.battlefield if perm.name == CHIP), None)


def _uthros_source(state: solver.State):
    return next((perm for perm in state.battlefield if perm.name == UTHROS), None)


def _chip_intents(runtime: core.NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    state = runtime.true_state
    source = _chip_source(state)
    if source is None:
        return ()
    generic, blue = _chip_cost(state)
    if not solver.can_pay(state, generic, blue):
        return ()

    rows = []
    index = 0
    # Reconfigure may attach/move the Equipment to a controlled creature.  Exclude
    # the Chip itself and temporary Chrome copies, matching the retained Oracle
    # state-space contract.  Strategically identical public targets collapse.
    targets = _groups(
        state,
        lambda perm: (
            solver.is_creature_perm(perm)
            and perm.name != CHIP
            and perm.mode not in {"chrome_copy", "chrome_copy_preturn"}
        ),
    )
    for signature in sorted(targets, key=repr):
        target = targets[signature][0]
        rows.append(ActionIntent(
            action_id=f"main.chip.reconfigure.attach.{index:03d}",
            kind=MAIN_ACTIVATE_CHIP_RECONFIGURE,
            parameters=(
                ("blue_required", int(blue)),
                ("choice", "attach"),
                ("generic_cost", int(generic)),
                ("target_name", str(target.name or target.mode)),
                ("target_signature", signature),
            ),
            equivalence_key=(
                MAIN_ACTIVATE_CHIP_RECONFIGURE,
                "attach",
                int(generic),
                int(blue),
                signature,
            ),
            label=f"Reality Chip: reconfigure onto {target.name or target.mode}",
            decision_stage=DECISION_COMMIT,
            source=CHIP,
        ))
        index += 1

    if state.chip_attached:
        rows.append(ActionIntent(
            action_id="main.chip.reconfigure.unattach",
            kind=MAIN_ACTIVATE_CHIP_RECONFIGURE,
            parameters=(
                ("blue_required", int(blue)),
                ("choice", "unattach"),
                ("generic_cost", int(generic)),
                ("target_name", ""),
                ("target_signature", ()),
            ),
            equivalence_key=(
                MAIN_ACTIVATE_CHIP_RECONFIGURE,
                "unattach",
                int(generic),
                int(blue),
            ),
            label="Reality Chip: reconfigure / unattach",
            decision_stage=DECISION_COMMIT,
            source=CHIP,
        ))
    return tuple(rows)


def _uthros_intents(runtime: core.NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    state = runtime.true_state
    source = _uthros_source(state)
    if source is None:
        return ()
    targets = _groups(
        state,
        lambda perm: (
            perm.name != UTHROS
            and solver.is_creature_perm(perm)
            and not perm.tapped
        ),
    )
    rows = []
    for index, signature in enumerate(sorted(targets, key=repr)):
        target = targets[signature][0]
        power = int(solver.creature_power(state, target))
        if power <= 0:
            continue
        result = int(state.uthros_counters) + power
        rows.append(ActionIntent(
            action_id=f"main.uthros.station.{index:03d}",
            kind=MAIN_ACTIVATE_UTHROS_STATION,
            parameters=(
                ("current_counters", int(state.uthros_counters)),
                ("power", power),
                ("result_counters", result),
                ("target_name", str(target.name or target.mode)),
                ("target_signature", signature),
            ),
            equivalence_key=(
                MAIN_ACTIVATE_UTHROS_STATION,
                int(state.uthros_counters),
                power,
                signature,
            ),
            label=(
                f"Uthros Station: tap {target.name or target.mode} "
                f"for {power} counter(s)"
            ),
            decision_stage=DECISION_COMMIT,
            source=UTHROS,
        ))
    return tuple(rows)


def engine_activation_main_intents(
    runtime: core.NonOracleRuntimeState,
) -> Tuple[ActionIntent, ...]:
    rows = list(_chip_intents(runtime))
    rows.extend(_uthros_intents(runtime))
    return tuple(sorted(rows, key=lambda action: action.action_id))


def _representative(state, signature, predicate):
    groups = _groups(state, predicate)
    rows = groups.get(tuple(signature), ())
    return rows[0] if rows else None


def _begin_chip(
    runtime: core.NonOracleRuntimeState,
    action: ActionIntent,
) -> core.NonOracleRuntimeState:
    params = dict(action.parameters)
    state = runtime.true_state
    source = _chip_source(state)
    if source is None:
        raise ValueError("Reality Chip source is no longer present")
    generic = int(params["generic_cost"])
    blue = int(params["blue_required"])
    if (generic, blue) != _chip_cost(state):
        raise ValueError("Reality Chip reconfigure cost changed before commitment")
    paid = solver.pay(state, generic, blue)
    if paid is None:
        raise ValueError("Reality Chip reconfigure cost can no longer be paid")

    choice = str(params["choice"])
    target_signature = tuple(params.get("target_signature", ()))
    target = None
    if choice == "attach":
        target = _representative(
            paid,
            target_signature,
            lambda perm: (
                solver.is_creature_perm(perm)
                and perm.name != CHIP
                and perm.mode not in {"chrome_copy", "chrome_copy_preturn"}
            ),
        )
        if target is None:
            raise ValueError("committed Reality Chip target is no longer legal")
    elif choice != "unattach":
        raise ValueError(f"unknown Reality Chip reconfigure choice {choice!r}")

    exact = [
        ("choice", choice),
        ("source_tag", int(source.instance_tag)),
    ]
    public = [("choice", choice)]
    strategic = [("choice", choice)]
    if target is not None:
        exact.append(("target_tag", int(target.instance_tag)))
        public.extend((
            ("target_name", str(target.name or target.mode)),
            ("target_state", target_signature),
        ))
        strategic.extend(public[1:])

    obj, stack = runtime.stack.allocate(
        object_type=core.STACK_TRIGGER,
        kind=ACT_CHIP_RECONFIGURE,
        source=CHIP,
        card=CHIP,
        payload=tuple(exact),
        public_payload=tuple(public),
        strategic_payload=tuple(strategic),
    )
    paid = solver.add_trace(
        paid,
        f"Phase2 activate Reality Chip reconfigure ({choice}); pay {{{generic}}}{{U}}",
    )
    return replace(
        runtime,
        true_state=paid,
        stack=stack.push_existing((obj,)),
        window=RuntimeDecisionWindow(WINDOW_PRIORITY),
    )


def _begin_uthros(
    runtime: core.NonOracleRuntimeState,
    action: ActionIntent,
) -> core.NonOracleRuntimeState:
    params = dict(action.parameters)
    state = runtime.true_state
    source = _uthros_source(state)
    if source is None:
        raise ValueError("Uthros source is no longer present")
    target_signature = tuple(params["target_signature"])
    target = _representative(
        state,
        target_signature,
        lambda perm: (
            perm.name != UTHROS
            and solver.is_creature_perm(perm)
            and not perm.tapped
        ),
    )
    if target is None:
        raise ValueError("Uthros Station creature is no longer legal")
    power = int(solver.creature_power(state, target))
    if power != int(params["power"]) or power <= 0:
        raise ValueError("Uthros Station committed power no longer matches public state")

    target_idx = core._perm_index_for_tag(state, int(target.instance_tag))
    if target_idx is None:
        raise ValueError("Uthros Station creature disappeared before cost payment")
    # "Tap another creature you control" is the activation cost.  It is not the
    # tap symbol, so summoning sickness does not prevent paying this cost.
    state = solver.update_perm(state, target_idx, tapped=True)
    state = solver.add_trace(
        state,
        f"Phase2 Uthros Station cost: tap {target.name or target.mode} (power {power})",
    )
    obj, stack = runtime.stack.allocate(
        object_type=core.STACK_TRIGGER,
        kind=ACT_UTHROS_STATION,
        source=UTHROS,
        card=UTHROS,
        payload=(
            ("power", power),
            ("source_tag", int(source.instance_tag)),
            ("target_tag", int(target.instance_tag)),
        ),
        public_payload=(
            ("power", power),
            ("target_name", str(target.name or target.mode)),
            ("target_state", target_signature),
        ),
        strategic_payload=(
            ("power", power),
            ("target_state", target_signature),
        ),
    )
    return replace(
        runtime,
        true_state=state,
        stack=stack.push_existing((obj,)),
        window=RuntimeDecisionWindow(WINDOW_PRIORITY),
    )


def begin_engine_activation(
    runtime: core.NonOracleRuntimeState,
    action: ActionIntent,
) -> core.NonOracleRuntimeState:
    legal = {
        candidate.canonical_key()
        for candidate in engine_activation_main_intents(runtime)
    }
    if action.canonical_key() not in legal:
        raise ValueError("engine activation is no longer legal")
    if action.kind == MAIN_ACTIVATE_CHIP_RECONFIGURE:
        return _begin_chip(runtime, action)
    if action.kind == MAIN_ACTIVATE_UTHROS_STATION:
        return _begin_uthros(runtime, action)
    raise ValueError(f"unsupported engine activation {action.kind!r}")


def handles_engine_stack_top(runtime: core.NonOracleRuntimeState) -> bool:
    if runtime.pending is not None:
        return False
    top = runtime.stack.top()
    return bool(top and top.kind in {ACT_CHIP_RECONFIGURE, ACT_UTHROS_STATION})


def _resolve_chip(runtime: core.NonOracleRuntimeState, obj) -> core.NonOracleRuntimeState:
    state = runtime.true_state
    params = dict(obj.payload)
    source_idx = core._perm_index_for_tag(state, int(params.get("source_tag", 0)))
    if source_idx is None or state.battlefield[source_idx].name != CHIP:
        state = solver.add_trace(state, "Phase2 Reality Chip reconfigure: source absent")
        return replace(runtime, true_state=state, window=RuntimeDecisionWindow(WINDOW_PRIORITY))

    choice = str(params["choice"])
    if choice == "unattach":
        state = solver.update_perm(state, source_idx, mode="")
        state = replace(state, chip_attached=False, chip_target="")
        state = solver.add_trace(state, "Phase2 Reality Chip reconfigure resolves: unattach")
    else:
        target_idx = core._perm_index_for_tag(state, int(params.get("target_tag", 0)))
        if target_idx is None or not solver.is_creature_perm(state.battlefield[target_idx]):
            state = solver.add_trace(state, "Phase2 Reality Chip reconfigure fizzles: target absent")
            return replace(runtime, true_state=state, window=RuntimeDecisionWindow(WINDOW_PRIORITY))
        target = state.battlefield[target_idx]
        source_idx = core._perm_index_for_tag(state, int(params["source_tag"]))
        state = solver.update_perm(state, source_idx, mode="chip_attached")
        state = replace(
            state,
            chip_attached=True,
            chip_target=str(target.name or target.mode),
        )
        state = solver.add_trace(
            state,
            f"Phase2 Reality Chip reconfigure resolves -> {target.name or target.mode}",
        )
    state = solver.check_win(state)
    return replace(runtime, true_state=state, window=RuntimeDecisionWindow(WINDOW_PRIORITY))


def _resolve_uthros(runtime: core.NonOracleRuntimeState, obj) -> core.NonOracleRuntimeState:
    state = runtime.true_state
    params = dict(obj.payload)
    source_idx = core._perm_index_for_tag(state, int(params.get("source_tag", 0)))
    power = int(params.get("power", 0))
    if source_idx is None or state.battlefield[source_idx].name != UTHROS:
        state = solver.add_trace(state, "Phase2 Uthros Station resolves: source absent")
        return replace(runtime, true_state=state, window=RuntimeDecisionWindow(WINDOW_PRIORITY))
    state = replace(state, uthros_counters=int(state.uthros_counters) + power)
    state = solver.add_trace(
        state,
        f"Phase2 Uthros Station resolves: +{power} -> {state.uthros_counters} counter(s)",
    )
    return replace(runtime, true_state=state, window=RuntimeDecisionWindow(WINDOW_PRIORITY))


def apply_engine_stack_action(
    runtime: core.NonOracleRuntimeState,
    action: ActionIntent,
) -> core.NonOracleRuntimeState:
    if action.action_id != core.ACTION_PASS_PRIORITY or action.kind != "pass_priority":
        raise ValueError("engine activation resolves only after passing priority")
    obj, remaining = runtime.stack.pop_top()
    if obj is None or obj.kind not in {ACT_CHIP_RECONFIGURE, ACT_UTHROS_STATION}:
        raise ValueError("top runtime object is not a supported engine activation")
    runtime = replace(runtime, stack=remaining)
    if obj.kind == ACT_CHIP_RECONFIGURE:
        return _resolve_chip(runtime, obj)
    return _resolve_uthros(runtime, obj)
