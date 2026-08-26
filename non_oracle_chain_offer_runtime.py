#!/usr/bin/env python3
"""Typed non-Oracle runtime for Chain of Vapor and self-Offer goldfish lines.

Both cards are present in held-out human-kept trajectories and are real Oracle
action families, but were absent from the production non-Oracle action surface.
This module keeps every policy choice public/typed rather than importing Oracle
successor macros.

Modeled Chain surface:
- cast Chain targeting one controlled nonland permanent;
- resolve the bounce;
- explicitly decline OR sacrifice a controlled land and choose the next controlled
  nonland target for a copy;
- repeat for later copies.

Cam is deliberately excluded as a Chain bounce target in this slice because Cam's
LTB trigger has a separate typed target/effect boundary.  The ordinary Knack/Cam
terminal line is already covered.  If a benchmark trajectory proves Chain->Cam
material, it should be added through that boundary, not Oracle's automatic helper.

Modeled Offer surface:
- while one of our noncreature spell objects is on the typed stack, cast
  An Offer You Can't Refuse targeting that exact public stack object;
- the target spell's cast triggers remain on the stack;
- Offer resolves, counters/removes only the target spell, then creates two Treasure
  tokens as ONE simultaneous artifact-entry event using the shared runtime.
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
    PendingDecisionSpec,
    PolicyDecisionContext,
    apply_observation_batch,
)
from non_oracle_runtime_value_key import RuntimeDecisionWindow, WINDOW_POST_OBSERVATION, WINDOW_PRIORITY
from trigger_order_adapter import post_cast_observations

CHAIN = "Chain of Vapor"
OFFER = "An Offer You Can't Refuse"

MAIN_CAST_CHAIN = "main_cast_chain_of_vapor"
PRIORITY_CAST_CHAIN = "priority_cast_chain_of_vapor"
PRIORITY_CAST_OFFER_SELF = "priority_cast_offer_self_counter"
CHAIN_COPY_CHOICE = "chain_copy_choice"
CHAIN_COPY_DECLINE = "chain_copy_decline"
CHAIN_COPY_COMMIT = "chain_copy_commit"

SPELL_CHAIN = "chain_of_vapor_spell"
SPELL_CHAIN_COPY = "chain_of_vapor_copy"
SPELL_OFFER = "offer_self_counter_spell"

CHAIN_OFFER_ACTION_KINDS = frozenset({
    MAIN_CAST_CHAIN,
    PRIORITY_CAST_CHAIN,
    PRIORITY_CAST_OFFER_SELF,
    CHAIN_COPY_DECLINE,
    CHAIN_COPY_COMMIT,
})


def _signature(perm) -> Tuple[object, ...]:
    return core._perm_public_signature(perm)


def _groups(state, predicate) -> Dict[Tuple[object, ...], Tuple[object, ...]]:
    grouped = {}
    for perm in state.battlefield:
        if predicate(perm):
            grouped.setdefault(_signature(perm), []).append(perm)
    return {
        signature: tuple(sorted(perms, key=lambda p: int(p.instance_tag)))
        for signature, perms in grouped.items()
    }


def _representative(state, signature, predicate):
    rows = [
        perm for perm in state.battlefield
        if _signature(perm) == tuple(signature) and predicate(perm)
    ]
    return min(rows, key=lambda p: int(p.instance_tag)) if rows else None


def _chain_target_allowed(perm) -> bool:
    return bool(
        not solver.is_land_perm(perm)
        and not solver.is_pruned_own_bounce_target(perm)
        and perm.name != "Sewer-veillance Cam"
    )


def _land_allowed(perm) -> bool:
    return bool(solver.is_land_perm(perm))


def _noncreature_spell_object(obj) -> bool:
    return bool(
        obj.object_type == core.STACK_SPELL
        and obj.card
        and obj.card != OFFER
        and obj.card not in solver.CREATURES
    )


def _stage(priority: bool) -> str:
    return DECISION_MECHANICAL if priority else DECISION_COMMIT


def chain_cast_intents(runtime: core.NonOracleRuntimeState, *, priority: bool) -> Tuple[ActionIntent, ...]:
    state = runtime.true_state
    if CHAIN not in state.hand or not solver.can_pay(state, 0, 1):
        return ()
    if runtime.pending is not None:
        return ()
    if priority:
        if not runtime.stack.objects or runtime.window.kind != WINDOW_PRIORITY:
            return ()
        kind = PRIORITY_CAST_CHAIN
        prefix = "priority"
    else:
        if runtime.stack.objects:
            return ()
        kind = MAIN_CAST_CHAIN
        prefix = "main"

    targets = _groups(state, _chain_target_allowed)
    rows = []
    for index, signature in enumerate(sorted(targets, key=repr)):
        target = targets[signature][0]
        rows.append(ActionIntent(
            action_id=f"{prefix}.chain.{index:03d}",
            kind=kind,
            parameters=(
                ("target_name", str(target.name or target.mode)),
                ("target_signature", signature),
            ),
            equivalence_key=(kind, signature),
            label=f"Cast Chain of Vapor -> {target.name or target.mode}",
            decision_stage=_stage(priority),
            source=CHAIN,
        ))
    return tuple(rows)


def offer_priority_intents(runtime: core.NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    state = runtime.true_state
    if (
        OFFER not in state.hand
        or not solver.can_pay(state, 0, 1)
        or runtime.pending is not None
        or not runtime.stack.objects
        or runtime.window.kind != WINDOW_PRIORITY
    ):
        return ()
    rows = []
    targets = [obj for obj in runtime.stack.objects if _noncreature_spell_object(obj)]
    for index, obj in enumerate(targets):
        rows.append(ActionIntent(
            action_id=f"priority.offer.self.{index:03d}",
            kind=PRIORITY_CAST_OFFER_SELF,
            parameters=(
                ("target_card", str(obj.card)),
                ("target_kind", str(obj.kind)),
                ("target_object_id", str(obj.object_id)),
            ),
            equivalence_key=(PRIORITY_CAST_OFFER_SELF, obj.strategic_key()),
            label=f"Cast Offer targeting our {obj.card}",
            decision_stage=DECISION_MECHANICAL,
            source=OFFER,
        ))
    return tuple(rows)


def chain_offer_main_intents(runtime: core.NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    return chain_cast_intents(runtime, priority=False)


def chain_offer_priority_intents(runtime: core.NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    rows = list(chain_cast_intents(runtime, priority=True))
    rows.extend(offer_priority_intents(runtime))
    return tuple(sorted(rows, key=lambda action: action.action_id))


def _queue_cast_triggers(runtime, *, card: str, mana_spent: int, spell_object_id: str):
    info = apply_observation_batch(
        runtime.information,
        post_cast_observations(runtime.true_state, card, cast_from_library_top=False),
    )
    runtime = replace(runtime, information=info)
    triggers, stack = core._cast_trigger_objects(runtime, card, mana_spent, spell_object_id)
    runtime = replace(runtime, stack=stack)
    return core._queue_simultaneous_objects(runtime, triggers, source=f"cast {card}")


def _begin_chain(runtime: core.NonOracleRuntimeState, action: ActionIntent) -> core.NonOracleRuntimeState:
    params = dict(action.parameters)
    signature = tuple(params["target_signature"])
    target = _representative(runtime.true_state, signature, _chain_target_allowed)
    if target is None:
        raise ValueError("Chain target is no longer legal")
    paid = solver.pay(runtime.true_state, 0, 1)
    if paid is None or CHAIN not in paid.hand:
        raise ValueError("Chain can no longer be paid/cast")
    paid = replace(
        paid,
        hand=solver.remove_one(paid.hand, CHAIN),
        spell_cast_this_turn=True,
    )
    paid = solver.add_trace(paid, f"Phase5 cast Chain of Vapor -> {target.name or target.mode}")
    runtime = replace(runtime, true_state=paid)
    spell, stack = runtime.stack.allocate(
        object_type=core.STACK_SPELL,
        kind=SPELL_CHAIN,
        source="hand",
        card=CHAIN,
        payload=(("target_tag", int(target.instance_tag)),),
        public_payload=(("target_state", signature),),
        strategic_payload=(("target_state", signature),),
    )
    runtime = replace(runtime, stack=stack.push_existing((spell,)))
    return _queue_cast_triggers(runtime, card=CHAIN, mana_spent=1, spell_object_id=spell.object_id)


def _begin_offer(runtime: core.NonOracleRuntimeState, action: ActionIntent) -> core.NonOracleRuntimeState:
    params = dict(action.parameters)
    target_id = str(params["target_object_id"])
    target = next((obj for obj in runtime.stack.objects if obj.object_id == target_id), None)
    if target is None or not _noncreature_spell_object(target):
        raise ValueError("Offer target is no longer a legal noncreature spell")
    paid = solver.pay(runtime.true_state, 0, 1)
    if paid is None or OFFER not in paid.hand:
        raise ValueError("Offer can no longer be paid/cast")
    paid = replace(
        paid,
        hand=solver.remove_one(paid.hand, OFFER),
        spell_cast_this_turn=True,
    )
    paid = solver.add_trace(paid, f"Phase5 cast Offer targeting our {target.card}")
    runtime = replace(runtime, true_state=paid)
    spell, stack = runtime.stack.allocate(
        object_type=core.STACK_SPELL,
        kind=SPELL_OFFER,
        source="hand",
        card=OFFER,
        payload=(("target_object_id", target_id),),
        public_payload=(("target_card", str(target.card)), ("target_kind", str(target.kind))),
        strategic_payload=(("target_card", str(target.card)), ("target_kind", str(target.kind))),
    )
    runtime = replace(runtime, stack=stack.push_existing((spell,)))
    return _queue_cast_triggers(runtime, card=OFFER, mana_spent=1, spell_object_id=spell.object_id)


def begin_chain_offer_action(runtime, action):
    priority = action.kind != MAIN_CAST_CHAIN
    legal = {
        candidate.canonical_key()
        for candidate in (
            chain_offer_priority_intents(runtime) if priority else chain_offer_main_intents(runtime)
        )
    }
    if action.canonical_key() not in legal:
        raise ValueError("Chain/Offer action is no longer legal")
    if action.kind in {MAIN_CAST_CHAIN, PRIORITY_CAST_CHAIN}:
        return _begin_chain(runtime, action)
    if action.kind == PRIORITY_CAST_OFFER_SELF:
        return _begin_offer(runtime, action)
    raise ValueError(f"unsupported Chain/Offer cast action {action.kind!r}")


def handles_chain_offer_stack_top(runtime) -> bool:
    if runtime.pending is not None:
        return False
    top = runtime.stack.top()
    return bool(top and top.kind in {SPELL_CHAIN, SPELL_CHAIN_COPY, SPELL_OFFER})


def _stage_chain_copy_choice(runtime, *, source_object_id: str):
    state = runtime.true_state
    lands = _groups(state, _land_allowed)
    targets = _groups(state, _chain_target_allowed)
    if not lands or not targets:
        return replace(runtime, window=RuntimeDecisionWindow(WINDOW_PRIORITY))
    spec = PendingDecisionSpec(
        decision_id=f"{source_object_id}.chain.copy",
        kind=CHAIN_COPY_CHOICE,
        source=CHAIN,
        decision_stage=DECISION_MECHANICAL,
        contingent_on=source_object_id,
    )
    return replace(
        runtime,
        pending=core.RuntimePendingDecision(
            spec=spec,
            kind=CHAIN_COPY_CHOICE,
            payload=(),
        ),
        window=RuntimeDecisionWindow(WINDOW_POST_OBSERVATION),
    )


def chain_pending_request(runtime, *, horizon: int, objective: str, policy_id: str, caverns_live=None):
    if runtime.pending is None or runtime.pending.kind != CHAIN_COPY_CHOICE:
        raise ValueError("runtime is not at a Chain copy decision")
    state = runtime.true_state
    lands = _groups(state, _land_allowed)
    targets = _groups(state, _chain_target_allowed)
    rows = [ActionIntent(
        action_id="chain.copy.decline",
        kind=CHAIN_COPY_DECLINE,
        parameters=(("choice", "decline"),),
        equivalence_key=(CHAIN_COPY_DECLINE,),
        label="Chain of Vapor: decline land sacrifice / copy",
        decision_stage=DECISION_MECHANICAL,
        source=CHAIN,
    )]
    serial = 0
    for land_signature in sorted(lands, key=repr):
        land = lands[land_signature][0]
        for target_signature in sorted(targets, key=repr):
            target = targets[target_signature][0]
            rows.append(ActionIntent(
                action_id=f"chain.copy.{serial:04d}",
                kind=CHAIN_COPY_COMMIT,
                parameters=(
                    ("choice", "copy"),
                    ("land_name", str(land.name)),
                    ("land_signature", land_signature),
                    ("target_name", str(target.name or target.mode)),
                    ("target_signature", target_signature),
                ),
                equivalence_key=(CHAIN_COPY_COMMIT, land_signature, target_signature),
                label=f"Chain copy: sacrifice {land.name}; bounce {target.name or target.mode}",
                decision_stage=DECISION_MECHANICAL,
                source=CHAIN,
            ))
            serial += 1
    return DecisionRequest(
        observation=runtime.policy_view(caverns_live=caverns_live),
        actions=tuple(rows),
        context=PolicyDecisionContext(
            horizon=horizon,
            objective=objective,
            policy_id=policy_id,
            decision_id=runtime.pending.spec.decision_id,
            decision_stage=DECISION_MECHANICAL,
        ),
    )


def apply_chain_pending(runtime, action):
    if runtime.pending is None or runtime.pending.kind != CHAIN_COPY_CHOICE:
        raise ValueError("no Chain copy decision is pending")
    request = chain_pending_request(
        runtime,
        horizon=max(1, int(runtime.true_state.turn)),
        objective="win_by_horizon",
        policy_id="runtime",
    )
    legal = {candidate.canonical_key() for candidate in request.actions}
    if action.canonical_key() not in legal:
        raise ValueError("Chain copy choice is no longer legal")
    if action.kind == CHAIN_COPY_DECLINE:
        return replace(
            runtime,
            pending=None,
            window=RuntimeDecisionWindow(WINDOW_PRIORITY),
        )
    params = dict(action.parameters)
    land = _representative(runtime.true_state, tuple(params["land_signature"]), _land_allowed)
    target = _representative(runtime.true_state, tuple(params["target_signature"]), _chain_target_allowed)
    if land is None or target is None:
        raise ValueError("Chain copy land or target is no longer legal")
    state = runtime.true_state
    land_idx = core._perm_index_for_tag(state, int(land.instance_tag))
    if land_idx is None:
        raise ValueError("Chain copy land disappeared")
    state = solver.remove_perm(state, land_idx, to_grave=True)
    state = solver.add_trace(
        state,
        f"Phase5 Chain copy: sacrifice {land.name}; target {target.name or target.mode}",
    )
    runtime = replace(runtime, true_state=state, pending=None)
    target = _representative(runtime.true_state, tuple(params["target_signature"]), _chain_target_allowed)
    if target is None:
        raise ValueError("Chain copy target disappeared after land sacrifice")
    copy, stack = runtime.stack.allocate(
        object_type=core.STACK_SPELL,
        kind=SPELL_CHAIN_COPY,
        source="Chain copy",
        card=CHAIN,
        payload=(("target_tag", int(target.instance_tag)),),
        public_payload=(("target_state", tuple(params["target_signature"])),),
        strategic_payload=(("target_state", tuple(params["target_signature"])),),
    )
    return replace(
        runtime,
        stack=stack.push_existing((copy,)),
        window=RuntimeDecisionWindow(WINDOW_PRIORITY),
    )


def _resolve_chain(runtime, obj):
    state = runtime.true_state
    tag = int(dict(obj.payload).get("target_tag", 0))
    index = core._perm_index_for_tag(state, tag)
    if obj.kind == SPELL_CHAIN:
        state = replace(state, graveyard=state.graveyard + (CHAIN,))
    if index is None or not _chain_target_allowed(state.battlefield[index]):
        state = solver.add_trace(state, f"Phase5 {obj.kind}: target absent / illegal")
        return replace(runtime, true_state=state, window=RuntimeDecisionWindow(WINDOW_PRIORITY))
    target_name = state.battlefield[index].name or state.battlefield[index].mode
    state = solver.bounce_own_perm(state, index)
    state = solver.check_win(solver.add_trace(state, f"Phase5 {obj.kind}: bounce {target_name}"))
    runtime = replace(runtime, true_state=solver._ensure_oracle_instance_tags(state))
    return _stage_chain_copy_choice(runtime, source_object_id=obj.object_id)


def _resolve_offer(runtime, obj):
    state = replace(runtime.true_state, graveyard=runtime.true_state.graveyard + (OFFER,))
    target_id = str(dict(obj.payload).get("target_object_id", ""))
    target = next((row for row in runtime.stack.objects if row.object_id == target_id), None)
    objects = tuple(row for row in runtime.stack.objects if row.object_id != target_id)
    runtime = replace(runtime, true_state=state, stack=core.RuntimeStack(objects, runtime.stack.next_sequence))
    if target is None or target.object_type != core.STACK_SPELL:
        state = solver.add_trace(state, "Phase5 Offer resolves: target absent")
        return replace(runtime, true_state=state, window=RuntimeDecisionWindow(WINDOW_PRIORITY))
    state = replace(state, graveyard=state.graveyard + ((target.card,) if False else ()))
    # The expression above intentionally does not mutate yet; spell destination is
    # assigned once below so the trace and runtime state change remain adjacent.
    state = replace(runtime.true_state, graveyard=runtime.true_state.graveyard + (target.card,))
    state = solver.add_trace(state, f"Phase5 Offer counters our {target.card} -> two Treasures")
    runtime = replace(runtime, true_state=state)
    runtime = core.add_artifact_tokens(
        runtime,
        ("Treasure", "Treasure"),
        modes=("treasure", "treasure"),
        source="Offer creates two Treasures",
    )
    return replace(runtime, true_state=solver.check_win(runtime.true_state))


def apply_chain_offer_stack_action(runtime, action):
    if action.action_id != core.ACTION_PASS_PRIORITY or action.kind != "pass_priority":
        raise ValueError("Chain/Offer spell resolves only after passing priority")
    obj, remaining = runtime.stack.pop_top()
    if obj is None or obj.kind not in {SPELL_CHAIN, SPELL_CHAIN_COPY, SPELL_OFFER}:
        raise ValueError("top stack object is not Chain/Offer")
    runtime = replace(runtime, stack=remaining)
    if obj.kind in {SPELL_CHAIN, SPELL_CHAIN_COPY}:
        return _resolve_chain(runtime, obj)
    return _resolve_offer(runtime, obj)
