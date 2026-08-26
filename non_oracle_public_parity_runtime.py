#!/usr/bin/env python3
"""Public mechanical actions required for Oracle/non-Oracle line parity.

This module adds two reproduced Phase-5 runtime gaps without delegating policy
choices to the Oracle search:

* fetchland activation: the action is public/legal independent of hidden order;
  the rules layer may inspect the concrete library to resolve whether an Island
  is actually found, then InformationState is updated across the shuffle;
* Banishing Knack / Retraction Helix granted bounce activation: source and target
  are selected from public permanent signatures.  The hidden library is never
  consulted by action generation.

The shared Oracle terminal recognizer remains authoritative after each transition.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Dict, Tuple

import urza_solver as solver
import non_oracle_runtime as core
from decision_observation import ActionIntent, DECISION_COMMIT, DECISION_MECHANICAL
from information_state_propagation import propagate_information
from non_oracle_runtime_value_key import RuntimeDecisionWindow, WINDOW_MAIN_EMPTY, WINDOW_PRIORITY

MAIN_ACTIVATE_FETCH = "main_activate_fetch"
PRIORITY_ACTIVATE_FETCH = "priority_activate_fetch"
MAIN_ACTIVATE_KNACK_BOUNCE = "main_activate_knack_bounce"
PRIORITY_ACTIVATE_KNACK_BOUNCE = "priority_activate_knack_bounce"

PUBLIC_PARITY_KINDS = frozenset({
    MAIN_ACTIVATE_FETCH,
    PRIORITY_ACTIVATE_FETCH,
    MAIN_ACTIVATE_KNACK_BOUNCE,
    PRIORITY_ACTIVATE_KNACK_BOUNCE,
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


def _representative(state, signature, predicate):
    rows = [
        perm for perm in state.battlefield
        if _signature(perm) == tuple(signature) and predicate(perm)
    ]
    if not rows:
        return None
    return min(rows, key=lambda p: int(p.instance_tag))


def _source_ready_for_knack(state, perm) -> bool:
    if not solver.is_knack_target_perm(state, perm) or perm.sick:
        return False
    if not perm.tapped:
        return True
    return bool(
        perm.name in {"Grinding Station", "Battered Golem"}
        and perm.producer_urza_ready
        and state.blue >= 1
    )


def _knack_target_allowed(perm) -> bool:
    if solver.is_land_perm(perm) or solver.is_pruned_own_bounce_target(perm):
        return False
    # Cam's LTB trigger has an explicit typed target/effect decision boundary in
    # non_oracle_cam_runtime.  The shared terminal recognizer already declares
    # Cam + a ready Knack grant a win, so a Cam self-bounce is not required to
    # reach that win family.  Keep it out of this narrow parity slice rather than
    # reintroducing the Oracle's automatic Cam-target shortcut.
    if perm.name == "Sewer-veillance Cam":
        return False
    return True


def fetch_actions(runtime: core.NonOracleRuntimeState, *, priority: bool) -> Tuple[ActionIntent, ...]:
    if runtime.pending is not None:
        return ()
    if priority:
        if not runtime.stack.objects or runtime.window.kind != WINDOW_PRIORITY:
            return ()
        kind = PRIORITY_ACTIVATE_FETCH
        stage = DECISION_MECHANICAL
        prefix = "priority"
    else:
        if runtime.stack.objects or runtime.window.kind != WINDOW_MAIN_EMPTY:
            return ()
        kind = MAIN_ACTIVATE_FETCH
        stage = DECISION_COMMIT
        prefix = "main"

    groups = _groups(runtime.true_state, lambda p: p.name in solver.FETCHES)
    rows = []
    for index, signature in enumerate(sorted(groups, key=repr)):
        source = groups[signature][0]
        rows.append(ActionIntent(
            action_id=f"{prefix}.fetch.{index:03d}",
            kind=kind,
            parameters=(("source_name", str(source.name)), ("source_signature", signature)),
            equivalence_key=(kind, signature),
            label=f"{source.name}: fetch Island and shuffle",
            decision_stage=stage,
            source=str(source.name),
        ))
    return tuple(rows)


def knack_bounce_actions(runtime: core.NonOracleRuntimeState, *, priority: bool) -> Tuple[ActionIntent, ...]:
    if runtime.pending is not None:
        return ()
    if priority:
        if not runtime.stack.objects or runtime.window.kind != WINDOW_PRIORITY:
            return ()
        kind = PRIORITY_ACTIVATE_KNACK_BOUNCE
        stage = DECISION_MECHANICAL
        prefix = "priority"
    else:
        if runtime.stack.objects or runtime.window.kind != WINDOW_MAIN_EMPTY:
            return ()
        kind = MAIN_ACTIVATE_KNACK_BOUNCE
        stage = DECISION_COMMIT
        prefix = "main"

    state = runtime.true_state
    sources = _groups(state, lambda p: _source_ready_for_knack(state, p))
    targets = _groups(state, _knack_target_allowed)
    rows = []
    serial = 0
    for source_signature in sorted(sources, key=repr):
        source = sources[source_signature][0]
        refundable = bool(source.tapped and source.producer_urza_ready)
        for target_signature in sorted(targets, key=repr):
            target = targets[target_signature][0]
            rows.append(ActionIntent(
                action_id=f"{prefix}.knack_bounce.{serial:03d}",
                kind=kind,
                parameters=(
                    ("refund_urza_blue", refundable),
                    ("source_name", str(source.name or source.mode)),
                    ("source_signature", source_signature),
                    ("target_name", str(target.name or target.mode)),
                    ("target_signature", target_signature),
                ),
                equivalence_key=(kind, source_signature, target_signature, refundable),
                label=(
                    f"Knack/Helix: tap {source.name or source.mode}; "
                    f"bounce {target.name or target.mode}"
                ),
                decision_stage=stage,
                source="Banishing Knack / Retraction Helix",
            ))
            serial += 1
    return tuple(rows)


def public_parity_main_intents(runtime: core.NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    rows = list(fetch_actions(runtime, priority=False))
    rows.extend(knack_bounce_actions(runtime, priority=False))
    return tuple(sorted(rows, key=lambda action: action.action_id))


def public_parity_priority_actions(runtime: core.NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    rows = list(fetch_actions(runtime, priority=True))
    rows.extend(knack_bounce_actions(runtime, priority=True))
    return tuple(sorted(rows, key=lambda action: action.action_id))


def _apply_fetch(runtime: core.NonOracleRuntimeState, action: ActionIntent) -> core.NonOracleRuntimeState:
    params = dict(action.parameters)
    signature = tuple(params["source_signature"])
    state = runtime.true_state
    source = _representative(state, signature, lambda p: p.name in solver.FETCHES)
    if source is None:
        raise ValueError("fetch source is no longer present")
    idx = core._perm_index_for_tag(state, int(source.instance_tag))
    if idx is None:
        raise ValueError("fetch source runtime tag disappeared")

    before = state
    state = solver.remove_perm(state, idx)
    library = list(state.library)
    found = "Island" in library
    if found:
        library.remove("Island")
        state = replace(state, library=tuple(library))
        state = solver.add_perm(state, "Island")
    state = replace(state, library=solver.shuffled_library(state, f"fetch:{source.name}"))
    state = solver.add_trace(
        state,
        f"{source.name} fetches {'Island' if found else 'no Island'} and shuffles",
    )
    state = solver.check_win(state)
    info = propagate_information(before, state, runtime.information)
    return replace(
        runtime,
        true_state=solver._ensure_oracle_instance_tags(state),
        information=info,
        window=runtime.window,
    )


def _apply_knack_bounce(runtime: core.NonOracleRuntimeState, action: ActionIntent) -> core.NonOracleRuntimeState:
    params = dict(action.parameters)
    source_signature = tuple(params["source_signature"])
    target_signature = tuple(params["target_signature"])
    state = runtime.true_state

    source = _representative(state, source_signature, lambda p: _source_ready_for_knack(state, p))
    target = _representative(state, target_signature, _knack_target_allowed)
    if source is None or target is None:
        raise ValueError("Knack/Helix source or target is no longer legal")

    before = state
    source_idx = core._perm_index_for_tag(state, int(source.instance_tag))
    if source_idx is None:
        raise ValueError("Knack/Helix source runtime tag disappeared")
    if source.tapped:
        state = solver._refund_producer_urza_tap(state, source_idx)
        if state is None:
            raise ValueError("Knack/Helix source cannot refund its deferred Urza tap")
        source_idx = core._perm_index_for_tag(state, int(source.instance_tag))
        if source_idx is None:
            raise ValueError("Knack/Helix source disappeared after refund")

    state = solver.update_perm(state, source_idx, tapped=True)
    target_idx = core._perm_index_for_tag(state, int(target.instance_tag))
    if target_idx is None:
        raise ValueError("Knack/Helix target disappeared before bounce")
    state = solver.bounce_own_perm(state, target_idx)
    state = solver.add_trace(
        state,
        f"Knack/Helix target {source.name or source.mode} bounces our {target.name or target.mode}",
    )
    state = solver.check_win(state)
    info = propagate_information(before, state, runtime.information)
    return replace(
        runtime,
        true_state=solver._ensure_oracle_instance_tags(state),
        information=info,
        window=runtime.window,
    )


def apply_public_parity_action(
    runtime: core.NonOracleRuntimeState,
    action: ActionIntent,
) -> core.NonOracleRuntimeState:
    priority = action.kind in {PRIORITY_ACTIVATE_FETCH, PRIORITY_ACTIVATE_KNACK_BOUNCE}
    legal = {
        candidate.canonical_key(): candidate
        for candidate in (
            public_parity_priority_actions(runtime)
            if priority else public_parity_main_intents(runtime)
        )
    }
    if action.canonical_key() not in legal:
        raise ValueError("public parity action is no longer legal")
    if action.kind in {MAIN_ACTIVATE_FETCH, PRIORITY_ACTIVATE_FETCH}:
        return _apply_fetch(runtime, action)
    if action.kind in {MAIN_ACTIVATE_KNACK_BOUNCE, PRIORITY_ACTIVATE_KNACK_BOUNCE}:
        return _apply_knack_bounce(runtime, action)
    raise AssertionError(f"unhandled public parity action kind {action.kind!r}")
