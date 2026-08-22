#!/usr/bin/env python3
"""Phase-2 draw/cantrip runtime bridge.

This module connects compact card-flow actions that were previously visible only to
the Oracle.  Costs are committed before any draw is observed; draws update the
information state only when the spell/ability resolves.

Modeled here:
- Gitaxian Probe (Phyrexian/free line, or pay U through our own Vexing Bauble);
- The One Ring tap/draw activation;
- Clue, Aether Spellbomb, Vexing Bauble, Witching Well draw activations;
- Mishra's/Urza's Bauble delayed-draw activations;
- Sewer-veillance Cam 3U sacrifice/draw-two, with its LTB target staged through
  the existing information-faithful Cam adapter above the pending draw ability.

The runtime core currently has generic resolvable stack objects classified as
``trigger`` or ``spell``.  Activated abilities use the generic trigger transport
class here but retain distinct ``activated_*`` kinds; no trigger-order semantics
are inferred from that transport label.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Dict, Iterable, Tuple

import urza_solver as solver
import non_oracle_runtime as core
from decision_observation import ActionIntent, DECISION_COMMIT, apply_observation_batch
from non_oracle_cam_runtime import queue_cam_ltb
from non_oracle_runtime_value_key import RuntimeDecisionWindow, WINDOW_PRIORITY
from non_oracle_turn_engine import _draw_one, _refresh_continuous_top
from trigger_order_adapter import post_cast_observations

MAIN_CAST_PROBE = "main_cast_gitaxian_probe"
MAIN_DRAW_ACTIVATION = "main_draw_activation"

SPELL_PROBE = "draw_gitaxian_probe_spell"
ACT_RING = "activated_one_ring_draw"
ACT_CLUE = "activated_clue_draw"
ACT_AETHER = "activated_aether_spellbomb_draw"
ACT_VEXING = "activated_vexing_bauble_draw"
ACT_BAUBLE_DELAYED = "activated_bauble_delayed_draw"
ACT_WELL = "activated_witching_well_draw"
ACT_CAM = "activated_cam_draw_two"

PROBE = "Gitaxian Probe"
CAM = "Sewer-veillance Cam"
RING = "The One Ring"
WELL = "Witching Well"
AETHER = "Aether Spellbomb"
VEXING = "Vexing Bauble"
DELAYED_BAUBLES = frozenset({"Mishra's Bauble", "Urza's Bauble"})
DRAW_STACK_KINDS = frozenset({
    SPELL_PROBE,
    ACT_RING,
    ACT_CLUE,
    ACT_AETHER,
    ACT_VEXING,
    ACT_BAUBLE_DELAYED,
    ACT_WELL,
    ACT_CAM,
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


def _has_public_bauble(state: solver.State) -> bool:
    return solver.has(state, VEXING)


def _probe_intents(state: solver.State) -> Tuple[ActionIntent, ...]:
    if PROBE not in state.hand:
        return ()
    # Match the Oracle's useful payment compression: through our own Vexing
    # Bauble, pay U when it is already floating so Probe survives; otherwise the
    # Phyrexian/no-mana line is the available commitment.
    pay_blue = bool(_has_public_bauble(state) and state.blue >= 1)
    blue_required = 1 if pay_blue else 0
    mana_spent = blue_required
    countered = bool(_has_public_bauble(state) and mana_spent == 0)
    return (ActionIntent(
        action_id="main.cast.gitaxian_probe",
        kind=MAIN_CAST_PROBE,
        parameters=(
            ("blue_required", blue_required),
            ("mana_spent", mana_spent),
            ("will_be_countered_by_own_bauble", countered),
        ),
        equivalence_key=(MAIN_CAST_PROBE, blue_required, countered),
        label=(
            "Cast Gitaxian Probe for U"
            if pay_blue
            else "Cast Gitaxian Probe with no mana spent"
        ),
        decision_stage=DECISION_COMMIT,
        source=PROBE,
    ),)


def _activation_action(
    *,
    index: int,
    source_name: str,
    source_signature: Tuple[object, ...],
    ability_kind: str,
    generic: int = 0,
    blue: int = 0,
    draw_count: int = 0,
    sacrifice: bool = False,
    delayed: bool = False,
) -> ActionIntent:
    return ActionIntent(
        action_id=f"main.draw.{ability_kind}.{index:03d}",
        kind=MAIN_DRAW_ACTIVATION,
        parameters=(
            ("ability_kind", ability_kind),
            ("blue_required", int(blue)),
            ("draw_count", int(draw_count)),
            ("generic_cost", int(generic)),
            ("sacrifice", bool(sacrifice)),
            ("source_name", source_name),
            ("source_signature", source_signature),
            ("delayed", bool(delayed)),
        ),
        equivalence_key=(
            MAIN_DRAW_ACTIVATION,
            ability_kind,
            source_signature,
            int(generic),
            int(blue),
            int(draw_count),
            bool(sacrifice),
            bool(delayed),
        ),
        label=(
            f"{source_name}: schedule delayed draw"
            if delayed
            else f"{source_name}: draw {draw_count}"
        ),
        decision_stage=DECISION_COMMIT,
        source=source_name,
    )


def draw_engine_main_intents(runtime: core.NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    state = runtime.true_state
    rows = list(_probe_intents(state))
    index = 0

    def add_groups(predicate, *, ability_kind, generic=0, blue=0, draw_count=0, sacrifice=False, delayed=False):
        nonlocal index
        for signature in sorted(_groups(state, predicate), key=repr):
            source_name = str(signature[0]) if signature else "artifact"
            if not solver.can_pay(state, int(generic), int(blue)):
                continue
            rows.append(_activation_action(
                index=index,
                source_name=source_name,
                source_signature=signature,
                ability_kind=ability_kind,
                generic=generic,
                blue=blue,
                draw_count=draw_count,
                sacrifice=sacrifice,
                delayed=delayed,
            ))
            index += 1

    add_groups(
        lambda p: p.name == RING and not p.tapped,
        ability_kind=ACT_RING,
        draw_count=max(1, int(state.ring_counters) + 1),
    )

    clue_cost = max(1, 2 - (1 if solver.has(state, "Forensic Gadgeteer") else 0))
    add_groups(
        lambda p: p.mode == "clue",
        ability_kind=ACT_CLUE,
        generic=clue_cost,
        draw_count=1,
        sacrifice=True,
    )
    add_groups(
        lambda p: p.name == AETHER,
        ability_kind=ACT_AETHER,
        generic=1,
        draw_count=1,
        sacrifice=True,
    )
    add_groups(
        lambda p: p.name == VEXING and not p.tapped,
        ability_kind=ACT_VEXING,
        generic=1,
        draw_count=1,
        sacrifice=True,
    )
    add_groups(
        lambda p: p.name in DELAYED_BAUBLES and not p.tapped,
        ability_kind=ACT_BAUBLE_DELAYED,
        sacrifice=True,
        delayed=True,
    )
    add_groups(
        lambda p: p.name == WELL,
        ability_kind=ACT_WELL,
        generic=3,
        blue=1,
        draw_count=2,
        sacrifice=True,
    )
    add_groups(
        lambda p: p.name == CAM,
        ability_kind=ACT_CAM,
        generic=3,
        blue=1,
        draw_count=2,
        sacrifice=True,
    )
    return tuple(sorted(rows, key=lambda action: action.action_id))


def _source_from_signature(state, signature: Tuple[object, ...]):
    candidates = [
        perm for perm in state.battlefield
        if _signature(perm) == tuple(signature)
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda perm: int(perm.instance_tag))


def _remove_cam_without_oracle_ltb(state: solver.State, source_tag: int) -> solver.State:
    """Pay Cam's sacrifice cost without invoking Oracle target selection.

    ``solver.remove_perm`` intentionally resolves Cam's LTB with ``cam_untap_best``.
    Phase 2 must instead create a typed target decision, so reproduce only the
    physical zone-change/SBA bookkeeping here and let ``queue_cam_ltb`` own the
    trigger.
    """
    idx = core._perm_index_for_tag(state, int(source_tag))
    if idx is None or state.battlefield[idx].name != CAM:
        raise ValueError("Cam source is no longer on the battlefield")
    perm = state.battlefield[idx]
    battlefield = list(state.battlefield)
    battlefield.pop(idx)
    state = replace(
        state,
        battlefield=tuple(battlefield),
        graveyard=state.graveyard + (CAM,),
    )

    if state.chip_attached and state.chip_target == perm.name:
        state = replace(state, chip_attached=False, chip_target="")
        for ci, candidate in enumerate(state.battlefield):
            if candidate.name == "The Reality Chip":
                state = solver.update_perm(state, ci, mode="")
                break

    if state.pa_target == perm.name:
        board = list(state.battlefield)
        for pi in range(len(board) - 1, -1, -1):
            if board[pi].name == "Power Artifact":
                board.pop(pi)
                state = replace(
                    state,
                    battlefield=tuple(board),
                    graveyard=state.graveyard + ("Power Artifact",),
                    pa_target="",
                )
                break
    return state


def _allocate_activation(
    runtime: core.NonOracleRuntimeState,
    *,
    ability_kind: str,
    source_perm,
    draw_count: int,
    delayed: bool,
) -> core.NonOracleRuntimeState:
    exact = (("source_tag", int(source_perm.instance_tag)), ("draw_count", int(draw_count)), ("delayed", bool(delayed)))
    public = (("source_state", _signature(source_perm)), ("draw_count", int(draw_count)), ("delayed", bool(delayed)))
    obj, stack = runtime.stack.allocate(
        object_type=core.STACK_TRIGGER,
        kind=ability_kind,
        source=source_perm.name or source_perm.mode,
        card=source_perm.name,
        payload=exact,
        public_payload=public,
        strategic_payload=public,
    )
    return replace(
        runtime,
        stack=stack.push_existing((obj,)),
        window=RuntimeDecisionWindow(WINDOW_PRIORITY),
    )


def _begin_probe(runtime: core.NonOracleRuntimeState, action: ActionIntent) -> core.NonOracleRuntimeState:
    params = dict(action.parameters)
    blue = int(params.get("blue_required", 0))
    mana_spent = int(params.get("mana_spent", 0))
    if PROBE not in runtime.true_state.hand:
        raise ValueError("Gitaxian Probe is no longer in hand")
    paid = solver.pay(runtime.true_state, 0, blue)
    if paid is None:
        raise ValueError("committed Gitaxian Probe payment is no longer legal")
    state = replace(
        paid,
        hand=solver.remove_one(paid.hand, PROBE),
        spell_cast_this_turn=True,
    )
    state = solver.add_trace(state, f"Phase2 cast Gitaxian Probe; mana spent={mana_spent}")
    runtime = replace(runtime, true_state=state)

    spell, stack = runtime.stack.allocate(
        object_type=core.STACK_SPELL,
        kind=SPELL_PROBE,
        source="hand",
        card=PROBE,
        payload=(("mana_spent", mana_spent),),
        public_payload=(("mana_spent", mana_spent),),
        strategic_payload=(("mana_spent", mana_spent),),
    )
    runtime = replace(runtime, stack=stack.push_existing((spell,)))
    info = apply_observation_batch(
        runtime.information,
        post_cast_observations(state, PROBE, cast_from_library_top=False),
    )
    runtime = replace(runtime, information=info)
    triggers, stack = core._cast_trigger_objects(runtime, PROBE, mana_spent, spell.object_id)
    runtime = replace(runtime, stack=stack)
    return core._queue_simultaneous_objects(runtime, triggers, source="cast Gitaxian Probe")


def begin_draw_engine_main_action(
    runtime: core.NonOracleRuntimeState,
    action: ActionIntent,
) -> core.NonOracleRuntimeState:
    legal = {candidate.canonical_key() for candidate in draw_engine_main_intents(runtime)}
    if action.canonical_key() not in legal:
        raise ValueError("draw-engine action is no longer legal")
    if action.kind == MAIN_CAST_PROBE:
        return _begin_probe(runtime, action)
    if action.kind != MAIN_DRAW_ACTIVATION:
        raise ValueError(f"unsupported draw-engine main action {action.kind!r}")

    params = dict(action.parameters)
    ability_kind = str(params["ability_kind"])
    signature = tuple(params["source_signature"])
    source = _source_from_signature(runtime.true_state, signature)
    if source is None:
        raise ValueError("draw-engine source is no longer present")

    generic = int(params.get("generic_cost", 0))
    blue = int(params.get("blue_required", 0))
    paid = solver.pay(runtime.true_state, generic, blue)
    if paid is None:
        raise ValueError("draw-engine activation cost is no longer payable")
    runtime = replace(runtime, true_state=paid)

    # Tap cost is relevant only for Ring.  Vexing/Bauble sources are sacrificed
    # as part of the same activation cost, so their eventual tapped status is moot.
    if ability_kind == ACT_RING:
        idx = core._perm_index_for_tag(runtime.true_state, int(source.instance_tag))
        if idx is None or runtime.true_state.battlefield[idx].tapped:
            raise ValueError("The One Ring is no longer an untapped legal source")
        state = solver.update_perm(runtime.true_state, idx, tapped=True)
        runtime = replace(runtime, true_state=state)

    runtime = _allocate_activation(
        runtime,
        ability_kind=ability_kind,
        source_perm=source,
        draw_count=int(params.get("draw_count", 0)),
        delayed=bool(params.get("delayed", False)),
    )

    if bool(params.get("sacrifice", False)):
        if ability_kind == ACT_CAM:
            state = _remove_cam_without_oracle_ltb(runtime.true_state, int(source.instance_tag))
        else:
            idx = core._perm_index_for_tag(runtime.true_state, int(source.instance_tag))
            if idx is None:
                raise ValueError("draw-engine sacrifice source is no longer present")
            state = solver.remove_perm(runtime.true_state, idx, to_grave=True)
        state = solver.add_trace(
            state,
            f"Phase2 activate {source.name or source.mode}: pay costs / sacrifice",
        )
        runtime = replace(runtime, true_state=solver._ensure_oracle_instance_tags(state))
        if ability_kind == ACT_CAM:
            return queue_cam_ltb(
                runtime,
                count=1,
                source="Cam draw activation sacrifice cost LTB",
            )
    return runtime


def handles_draw_stack_top(runtime: core.NonOracleRuntimeState) -> bool:
    if runtime.pending is not None:
        return False
    top = runtime.stack.top()
    return bool(top and top.kind in DRAW_STACK_KINDS)


def _draw_cards(runtime: core.NonOracleRuntimeState, count: int, *, source: str) -> core.NonOracleRuntimeState:
    state = runtime.true_state
    info = runtime.information
    drawn = []
    for _ in range(max(0, int(count))):
        state, info, row = _draw_one(state, info, source=source)
        drawn.extend(row)
    info = _refresh_continuous_top(state, info, source=f"post-{source} continuous look")
    if drawn:
        state = solver.add_trace(state, f"Phase2 {source} draws: {', '.join(drawn)}")
    return replace(runtime, true_state=state, information=info)


def apply_draw_stack_action(
    runtime: core.NonOracleRuntimeState,
    action: ActionIntent,
) -> core.NonOracleRuntimeState:
    if action.action_id != core.ACTION_PASS_PRIORITY or action.kind != "pass_priority":
        raise ValueError("draw spell/ability resolves only after passing priority")
    obj, remaining = runtime.stack.pop_top()
    if obj is None or obj.kind not in DRAW_STACK_KINDS:
        raise ValueError("top object is not handled by draw-engine runtime")
    runtime = replace(runtime, stack=remaining)

    if obj.kind == SPELL_PROBE:
        state = replace(runtime.true_state, graveyard=runtime.true_state.graveyard + (PROBE,))
        runtime = replace(runtime, true_state=state)
        runtime = _draw_cards(runtime, 1, source="Gitaxian Probe")
    elif obj.kind == ACT_RING:
        tag = int(dict(obj.payload).get("source_tag", 0))
        idx = core._perm_index_for_tag(runtime.true_state, tag)
        if idx is None or runtime.true_state.battlefield[idx].name != RING:
            state = solver.add_trace(runtime.true_state, "Phase2 One Ring ability resolves with source absent")
            runtime = replace(runtime, true_state=state)
        else:
            next_count = int(runtime.true_state.ring_counters) + 1
            state = replace(runtime.true_state, ring_counters=next_count)
            runtime = replace(runtime, true_state=state)
            runtime = _draw_cards(runtime, next_count, source="The One Ring")
    elif obj.kind == ACT_BAUBLE_DELAYED:
        state = replace(runtime.true_state, bauble_draws=int(runtime.true_state.bauble_draws) + 1)
        state = solver.add_trace(state, f"Phase2 {obj.source} schedules next-opponent-cycle draw")
        runtime = replace(runtime, true_state=state)
    else:
        count = int(dict(obj.payload).get("draw_count", 0))
        runtime = _draw_cards(runtime, count, source=obj.source or obj.kind)

    return replace(runtime, window=RuntimeDecisionWindow(WINDOW_PRIORITY))
