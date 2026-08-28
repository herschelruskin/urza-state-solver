#!/usr/bin/env python3
"""Typed Phase-2 runtime bridge for Reshape and Whir of Invention.

The Phase-1 X-artifact adapter established the anti-clairvoyance boundary: X,
payment, and (for Reshape) the sacrifice are committed before the library is
searched. This bridge preserves that boundary while placing the actual spell and
all cast-time triggers on the Phase-2 stack.

Important timing:
- Reshape sacrifices as an additional casting cost. Prized Statue and Cam triggers
  therefore wait until casting finishes; Cam chooses its target before those
  simultaneous controlled triggers are ordered above Reshape.
- Whir commits X and its exact improvise/payment plan before any search target is
  visible.
- Search targets become policy-visible only when the spell resolves. The selected
  artifact enters during resolution, the library is shuffled, the spell finishes,
  and only then are artifact-entry triggers put on the runtime stack.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Tuple

import urza_solver as solver
from decision_observation import (
    ActionIntent,
    DECISION_COMMIT,
    DECISION_POST_OBSERVATION,
    DecisionRequest,
    ObservationBatch,
    PendingDecisionSpec,
    PolicyDecisionContext,
    SearchZoneObservation,
    ShuffleObservation,
    apply_observation_batch,
)
from non_oracle_cam_runtime import queue_cam_ltb
from non_oracle_runtime import (
    ACTION_PASS_PRIORITY,
    STACK_SPELL,
    STACK_TRIGGER,
    NonOracleRuntimeState,
    RuntimeDecisionWindow,
    RuntimePendingDecision,
    _cast_trigger_objects,
    _queue_simultaneous_objects,
    record_artifact_entry,
)
from non_oracle_runtime_value_key import WINDOW_POST_OBSERVATION, WINDOW_PRIORITY
from trigger_order_adapter import post_cast_observations
from symbolic_action_space import (
    add_bit,
    bit_count,
    cached_cardinality_zdd,
    highest_bit,
)
from x_artifact_search_adapter import (
    RESHAPE,
    WHIR,
    SEARCH_KIND,
    SearchContext,
    _artifact_slots,
    _slot_from_parameter,
    _slot_index,
    _target_intents,
    reshape_cast_intents,
)

MAIN_USE_X_ARTIFACT_TUTOR = "main_use_x_artifact_tutor"
SPELL_RESHAPE = "x_artifact_reshape_spell"
SPELL_WHIR = "x_artifact_whir_spell"
RUNTIME_X_TARGET = "runtime_x_artifact_target"
RUNTIME_WHIR_PAYMENT = "runtime_whir_payment"
WHIR_PAYMENT_ADD = "whir_payment_add_improvise"
WHIR_PAYMENT_FINISH = "whir_payment_finish"

# No artifact in the deck has mana value above this threshold. For Reshape/Whir,
# larger X reveals no additional legal target. Modeled cast triggers depend only
# on whether mana_spent is zero; Whir always spends >=3 and Reshape X above this
# threshold is also nonzero. Therefore X above this value is strictly resource-
# dominated and can be removed without removing a strategic outcome.
MAX_USEFUL_ARTIFACT_X = max(solver.mana_value(card) for card in solver.ARTIFACTS)
if MAX_USEFUL_ARTIFACT_X >= 99:
    raise RuntimeError("artifact mana-value metadata incomplete for staged X tutor")


def _reshape_underlying_cast_intents(runtime: NonOracleRuntimeState):
    return tuple(
        candidate
        for candidate in reshape_cast_intents(runtime.true_state)
        if int(dict(candidate.parameters)["x"]) <= MAX_USEFUL_ARTIFACT_X
    )


def _whir_generic_need(state, x: int) -> int:
    return max(0, int(x) - solver.medallion_reduction(state, WHIR))


def _whir_payment_shape(state, x: int):
    if WHIR not in state.hand or state.blue < 3:
        return None
    if not 0 <= int(x) <= MAX_USEFUL_ARTIFACT_X:
        return None
    after_blue = solver.pay(state, 0, 3)
    if after_blue is None:
        return None
    need = _whir_generic_need(state, int(x))
    slots = _artifact_slots(after_blue, untapped_only=True)
    floating_pool = int(after_blue.blue + after_blue.colorless)
    min_selected = max(0, int(need) - floating_pool)
    max_selected = min(int(need), len(slots))
    if min_selected > max_selected:
        return None
    zdd = cached_cardinality_zdd(
        len(slots), min_selected, max_selected
    )
    return after_blue, int(need), slots, min_selected, max_selected, zdd


def _whir_x_is_payable(state, x: int) -> bool:
    return _whir_payment_shape(state, int(x)) is not None


def _whir_root_intents(runtime: NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    state = runtime.true_state
    rows = []
    for x in range(MAX_USEFUL_ARTIFACT_X + 1):
        if not _whir_x_is_payable(state, x):
            continue
        need = _whir_generic_need(state, x)
        rows.append(
            ActionIntent(
                action_id=f"main.x_artifact.whir.x{x}",
                kind=MAIN_USE_X_ARTIFACT_TUTOR,
                parameters=(
                    ("generic_need", int(need)),
                    ("sacrifice_name", ""),
                    ("source", WHIR),
                    ("x", int(x)),
                ),
                equivalence_key=(
                    MAIN_USE_X_ARTIFACT_TUTOR,
                    WHIR,
                    "staged-payment",
                    int(x),
                    int(need),
                ),
                label=f"Cast Whir X={x}; choose payment",
                decision_stage=DECISION_COMMIT,
                source=WHIR,
            )
        )
    return tuple(rows)


def x_artifact_runtime_intents(runtime: NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    """Expose pre-search commitments without materializing Whir payment subsets.

    Reshape still commits X+sacrifice in one action. Whir commits X first, then
    enters a no-observation payment subdecision that selects improvise objects one
    at a time. Every historical complete payment plan remains reachable.
    """
    rows = []
    for candidate in _reshape_underlying_cast_intents(runtime):
        params = dict(candidate.parameters)
        sacrifice = tuple(params.get("sacrifice", ()))
        sacrifice_name = str(sacrifice[0]) if sacrifice else ""
        rows.append(
            ActionIntent(
                action_id=f"main.x_artifact.{candidate.action_id}",
                kind=MAIN_USE_X_ARTIFACT_TUTOR,
                parameters=(
                    ("cast_parameters", tuple(candidate.parameters)),
                    ("sacrifice_name", sacrifice_name),
                    ("source", RESHAPE),
                    ("x", int(params["x"])),
                ),
                equivalence_key=(
                    MAIN_USE_X_ARTIFACT_TUTOR,
                    RESHAPE,
                    candidate.strategic_key(),
                ),
                label=candidate.label,
                decision_stage=DECISION_COMMIT,
                source=RESHAPE,
            )
        )
    rows.extend(_whir_root_intents(runtime))
    return tuple(sorted(rows, key=lambda action: action.action_id))


def _find_reshape_underlying(runtime: NonOracleRuntimeState, action: ActionIntent):
    params = dict(action.parameters)
    if str(params["source"]) != RESHAPE:
        raise ValueError("only Reshape uses an underlying monolithic cast action")
    cast_parameters = tuple(params["cast_parameters"])
    matches = [
        candidate
        for candidate in _reshape_underlying_cast_intents(runtime)
        if tuple(candidate.parameters) == cast_parameters
    ]
    if len(matches) != 1:
        raise ValueError("Reshape commitment is no longer legal")
    return matches[0]


def _whir_payment_payload(
    *,
    x: int,
    generic_need: int,
    selected_mask: int,
    slot_keys,
    min_selected: int,
    max_selected: int,
) -> Tuple[Tuple[str, object], ...]:
    return (
        ("generic_need", int(generic_need)),
        ("max_selected", int(max_selected)),
        ("min_selected", int(min_selected)),
        ("selected_mask", int(selected_mask)),
        ("slot_keys", tuple(tuple(raw) for raw in slot_keys)),
        ("source", WHIR),
        ("x", int(x)),
    )


def _start_whir_payment(
    runtime: NonOracleRuntimeState,
    *,
    x: int,
    generic_need: int,
    contingent_on: str,
) -> NonOracleRuntimeState:
    shape = _whir_payment_shape(runtime.true_state, int(x))
    if shape is None:
        raise ValueError("Whir X commitment is no longer payable")
    after_blue, expected, slots, min_selected, max_selected, zdd = shape
    if int(generic_need) != expected:
        raise ValueError("Whir generic requirement changed after commitment")
    slot_keys = tuple(tuple(slot.key()) for slot in slots)
    if expected == 0:
        return _finish_symbolic_whir(
            runtime,
            x=int(x),
            generic_need=0,
            selected_mask=0,
            slot_keys=slot_keys,
            min_selected=0,
            max_selected=0,
            floating=0,
        )
    spec = PendingDecisionSpec(
        decision_id=f"runtime.whir.payment.x{int(x)}",
        kind=RUNTIME_WHIR_PAYMENT,
        source=WHIR,
        decision_stage=DECISION_COMMIT,
        contingent_on=str(contingent_on),
    )
    return replace(
        runtime,
        pending=RuntimePendingDecision(
            spec=spec,
            kind=RUNTIME_WHIR_PAYMENT,
            payload=_whir_payment_payload(
                x=int(x),
                generic_need=expected,
                selected_mask=0,
                slot_keys=slot_keys,
                min_selected=min_selected,
                max_selected=max_selected,
            ),
        ),
    )


def _whir_payment_state(runtime: NonOracleRuntimeState):
    pending = runtime.pending
    if pending is None or pending.kind != RUNTIME_WHIR_PAYMENT:
        raise ValueError("not a pending Whir payment decision")
    data = dict(pending.payload)
    state = runtime.true_state
    x = int(data["x"])
    need = int(data["generic_need"])
    selected_mask = int(data.get("selected_mask", 0))
    stored_slot_keys = tuple(
        tuple(raw) for raw in data.get("slot_keys", ())
    )
    min_selected = int(data["min_selected"])
    max_selected = int(data["max_selected"])

    shape = _whir_payment_shape(state, x)
    if shape is None:
        raise ValueError("pending Whir payment can no longer be paid")
    after_blue, expected_need, slots, live_min, live_max, zdd = shape
    if need != expected_need:
        raise ValueError("pending Whir generic requirement no longer matches state")
    live_slot_keys = tuple(tuple(slot.key()) for slot in slots)
    if live_slot_keys != stored_slot_keys:
        raise ValueError("pending Whir public artifact slots changed before commitment finished")
    if (min_selected, max_selected) != (live_min, live_max):
        raise ValueError("pending Whir ZDD cardinality bounds changed")
    if selected_mask >> len(slots):
        raise ValueError("pending Whir bitset references a nonexistent slot")

    chosen = bit_count(selected_mask)
    next_index = highest_bit(selected_mask) + 1
    if chosen > max_selected or not zdd.has_completion(
        start_index=next_index,
        chosen_count=chosen,
    ):
        raise ValueError("pending Whir bitset has no legal ZDD completion")
    remaining = need - chosen
    return (
        state,
        after_blue,
        x,
        need,
        selected_mask,
        remaining,
        slots,
        stored_slot_keys,
        min_selected,
        max_selected,
        zdd,
    )


def whir_payment_request(
    runtime: NonOracleRuntimeState,
    *,
    horizon: int,
    objective: str,
    policy_id: str,
    caverns_live=None,
) -> DecisionRequest:
    (
        state,
        after_blue,
        x,
        need,
        selected_mask,
        remaining,
        slots,
        slot_keys,
        min_selected,
        max_selected,
        zdd,
    ) = _whir_payment_state(runtime)

    rows = []
    chosen = bit_count(selected_mask)
    if zdd.can_finish(selected_mask):
        floating = int(need - chosen)
        if not solver.can_pay(after_blue, floating, 0):
            raise AssertionError("terminal Whir ZDD node is not mana-payable")
        rows.append(
            ActionIntent(
                action_id=f"whir.payment.x{x}.finish.mask{selected_mask:x}",
                kind=WHIR_PAYMENT_FINISH,
                parameters=(
                    ("floating_generic", floating),
                    ("selected_mask", int(selected_mask)),
                    ("x", int(x)),
                ),
                equivalence_key=(
                    WHIR_PAYMENT_FINISH,
                    int(x),
                    int(selected_mask),
                    floating,
                ),
                label=f"Finish Whir X={x}; pay {floating} generic from mana",
                decision_stage=DECISION_COMMIT,
                source=WHIR,
                contingent_on=runtime.pending.spec.contingent_on,
            )
        )

    for slot_index in zdd.next_include_indices(selected_mask):
        new_mask = add_bit(selected_mask, slot_index)
        slot = slots[slot_index]
        rows.append(
            ActionIntent(
                action_id=(
                    f"whir.payment.x{x}.add."
                    f"{slot_index:02d}.mask{new_mask:x}"
                ),
                kind=WHIR_PAYMENT_ADD,
                parameters=(
                    ("remaining_before", int(remaining)),
                    ("selected_mask_after", int(new_mask)),
                    ("selected_mask_before", int(selected_mask)),
                    ("slot_index", int(slot_index)),
                    ("x", int(x)),
                ),
                equivalence_key=(
                    WHIR_PAYMENT_ADD,
                    int(x),
                    tuple(slot.key()),
                    int(new_mask),
                ),
                label=f"Whir X={x}: improvise {slot.name or slot.mode}",
                decision_stage=DECISION_COMMIT,
                source=WHIR,
                contingent_on=runtime.pending.spec.contingent_on,
            )
        )

    if not rows:
        raise ValueError("pending Whir ZDD has no legal continuation")
    return DecisionRequest(
        observation=runtime.policy_view(caverns_live=caverns_live),
        actions=tuple(sorted(rows, key=lambda action: action.action_id)),
        context=PolicyDecisionContext(
            horizon=horizon,
            objective=objective,
            policy_id=policy_id,
            decision_id=runtime.pending.spec.decision_id,
            decision_stage=DECISION_COMMIT,
        ),
    )


def _finish_symbolic_whir(
    runtime: NonOracleRuntimeState,
    *,
    x: int,
    generic_need: int,
    selected_mask: int,
    slot_keys,
    min_selected: int,
    max_selected: int,
    floating: int,
) -> NonOracleRuntimeState:
    state = runtime.true_state
    shape = _whir_payment_shape(state, int(x))
    if shape is None:
        raise ValueError("Whir payment is no longer legal")
    after_blue, expected, slots, live_min, live_max, zdd = shape
    if int(generic_need) != expected:
        raise ValueError("Whir generic requirement changed before payment finished")
    if (int(min_selected), int(max_selected)) != (live_min, live_max):
        raise ValueError("Whir ZDD cardinality bounds changed before payment finished")
    live_slot_keys = tuple(tuple(slot.key()) for slot in slots)
    if tuple(tuple(raw) for raw in slot_keys) != live_slot_keys:
        raise ValueError("Whir slot registry changed before payment finished")
    if not zdd.contains_mask(int(selected_mask)):
        raise ValueError("Whir payment bitset is not a terminal ZDD set")

    selected_indices = tuple(
        index for index in range(len(slots))
        if int(selected_mask) & (1 << index)
    )
    if len(selected_indices) + int(floating) != expected:
        raise ValueError("Whir symbolic payment does not exactly cover generic requirement")

    paid = after_blue
    indices = tuple(
        _slot_index(paid, slots[index])
        for index in selected_indices
    )
    if len(set(indices)) != len(indices):
        raise ValueError("Whir symbolic payment resolves duplicate battlefield objects")
    for index in indices:
        if paid.battlefield[index].tapped or not solver.is_artifact_perm(paid.battlefield[index]):
            raise ValueError("committed Whir improvise permanent is no longer legal")
        paid = solver.update_perm(paid, index, tapped=True)
    paid = solver.pay(paid, int(floating), 0)
    if paid is None:
        raise ValueError("Whir floating generic remainder can no longer be paid")
    paid = replace(
        paid,
        hand=solver.remove_one(paid.hand, WHIR),
        spell_cast_this_turn=True,
    )
    mana_spent = int(3 + int(floating))
    paid = solver.add_trace(
        paid,
        f"Phase2 cast Whir X={int(x)}; ZDD payment mask={int(selected_mask):x}",
    )
    runtime = replace(
        runtime,
        true_state=solver._ensure_oracle_instance_tags(paid),
        pending=None,
    )
    spell, runtime = _allocate_spell(
        runtime,
        kind=SPELL_WHIR,
        source=WHIR,
        x=int(x),
        mana_spent=mana_spent,
    )
    return _finish_cast_triggers(
        runtime,
        source=WHIR,
        spell=spell,
        mana_spent=mana_spent,
        prized_died=False,
        cam_died=False,
    )


def apply_whir_payment_pending(
    runtime: NonOracleRuntimeState,
    action: ActionIntent,
) -> NonOracleRuntimeState:
    request = whir_payment_request(
        runtime,
        horizon=max(1, int(runtime.true_state.turn)),
        objective="win_by_horizon",
        policy_id="runtime",
    )
    legal = {candidate.canonical_key() for candidate in request.actions}
    if action.canonical_key() not in legal:
        raise ValueError("Whir payment action is not legal")
    (
        state,
        after_blue,
        x,
        need,
        selected_mask,
        remaining,
        slots,
        slot_keys,
        min_selected,
        max_selected,
        zdd,
    ) = _whir_payment_state(runtime)
    params = dict(action.parameters)

    if action.kind == WHIR_PAYMENT_FINISH:
        floating = int(params["floating_generic"])
        if int(params["selected_mask"]) != selected_mask:
            raise ValueError("Whir finish action has stale bitset")
        return _finish_symbolic_whir(
            runtime,
            x=x,
            generic_need=need,
            selected_mask=selected_mask,
            slot_keys=slot_keys,
            min_selected=min_selected,
            max_selected=max_selected,
            floating=floating,
        )

    if action.kind == WHIR_PAYMENT_ADD:
        if int(params["selected_mask_before"]) != selected_mask:
            raise ValueError("Whir improvise action has stale prior bitset")
        slot_index = int(params["slot_index"])
        if slot_index not in zdd.next_include_indices(selected_mask):
            raise ValueError("Whir ZDD transition is no longer legal")
        new_mask = add_bit(selected_mask, slot_index)
        if int(params["selected_mask_after"]) != new_mask:
            raise ValueError("Whir improvise action has stale next bitset")
        new_remaining = need - bit_count(new_mask)
        if new_remaining == 0:
            return _finish_symbolic_whir(
                runtime,
                x=x,
                generic_need=need,
                selected_mask=new_mask,
                slot_keys=slot_keys,
                min_selected=min_selected,
                max_selected=max_selected,
                floating=0,
            )
        return replace(
            runtime,
            pending=replace(
                runtime.pending,
                payload=_whir_payment_payload(
                    x=x,
                    generic_need=need,
                    selected_mask=new_mask,
                    slot_keys=slot_keys,
                    min_selected=min_selected,
                    max_selected=max_selected,
                ),
            ),
        )

    raise ValueError("unknown Whir payment action kind")


def _remove_artifact_for_reshape_cost(state, index: int):
    """Remove one artifact without resolving triggered abilities atomically."""
    battlefield = list(state.battlefield)
    perm = battlefield.pop(index)
    graveyard = state.graveyard
    if (
        perm.name not in {"Clue", "Treasure", "Construct"}
        and perm.mode not in {"clue", "treasure", "construct", "chrome_copy", "chrome_copy_preturn"}
    ):
        graveyard = graveyard + (perm.name,)
    state = replace(state, battlefield=tuple(battlefield), graveyard=graveyard)

    if perm.name == "Uthros Research Craft":
        state = replace(state, uthros_counters=0)
    if perm.name == "The One Ring":
        state = replace(state, ring_counters=0)
    if perm.name == "The Reality Chip":
        state = replace(state, chip_attached=False, chip_target="")
    if state.chip_attached and state.chip_target and perm.name == state.chip_target:
        state = replace(state, chip_attached=False, chip_target="")
        for i, chip in enumerate(state.battlefield):
            if chip.name == "The Reality Chip":
                state = solver.update_perm(state, i, mode="")
                break
    if state.pa_target and perm.name == state.pa_target:
        bf = list(state.battlefield)
        for i in range(len(bf) - 1, -1, -1):
            if bf[i].name == "Power Artifact":
                bf.pop(i)
                state = replace(
                    state,
                    battlefield=tuple(bf),
                    graveyard=state.graveyard + ("Power Artifact",),
                    pa_target="",
                )
                break
    return state, perm


def _allocate_spell(runtime, *, kind: str, source: str, x: int, mana_spent: int):
    spell, stack = runtime.stack.allocate(
        object_type=STACK_SPELL,
        kind=kind,
        source="hand",
        card=source,
        payload=(("x", int(x)), ("mana_spent", int(mana_spent))),
        public_payload=(("x", int(x)), ("mana_spent", int(mana_spent))),
        strategic_payload=(("x", int(x)), ("mana_spent", int(mana_spent))),
    )
    return spell, replace(runtime, stack=stack.push_existing((spell,)))


def _finish_cast_triggers(
    runtime,
    *,
    source: str,
    spell,
    mana_spent: int,
    prized_died: bool,
    cam_died: bool = False,
):
    info = apply_observation_batch(
        runtime.information,
        post_cast_observations(runtime.true_state, source, cast_from_library_top=False),
    )
    runtime = replace(runtime, information=info)
    triggers, allocated = _cast_trigger_objects(
        runtime, source, int(mana_spent), spell.object_id
    )
    extra = []
    if prized_died:
        death, allocated = allocated.allocate(
            object_type=STACK_TRIGGER,
            kind="prized_dies_treasure",
            source="Prized Statue",
            card="Prized Statue",
        )
        extra.append(death)
    runtime = replace(runtime, stack=allocated)
    simultaneous = tuple(triggers) + tuple(extra)
    if cam_died:
        return queue_cam_ltb(
            runtime,
            extra_objects=simultaneous,
            count=1,
            source="Reshape additional-cost Cam LTB",
        )
    return _queue_simultaneous_objects(
        runtime,
        simultaneous,
        source=f"cast {source}",
    )


def begin_x_artifact_tutor(runtime: NonOracleRuntimeState, action: ActionIntent) -> NonOracleRuntimeState:
    legal = {candidate.canonical_key() for candidate in x_artifact_runtime_intents(runtime)}
    if action.canonical_key() not in legal:
        raise ValueError("X-artifact tutor commitment is not currently legal")
    action_params = dict(action.parameters)
    source = str(action_params["source"])
    state = runtime.true_state

    if source == WHIR:
        return _start_whir_payment(
            runtime,
            x=int(action_params["x"]),
            generic_need=int(action_params["generic_need"]),
            contingent_on=action.action_id,
        )

    underlying = _find_reshape_underlying(runtime, action)
    params = dict(underlying.parameters)
    x = int(params["x"])
    prized_died = False
    cam_died = False

    if source == RESHAPE:
        generic = int(params["generic_paid"])
        paid = solver.pay(state, generic, 2)
        if paid is None or source not in paid.hand:
            raise ValueError("Reshape can no longer pay its committed cost")
        paid = replace(
            paid,
            hand=solver.remove_one(paid.hand, source),
            spell_cast_this_turn=True,
        )
        slot = _slot_from_parameter(tuple(params["sacrifice"]))
        # Recover the committed source from the pre-payment state.  pay() can
        # mutate public permanent annotations but preserves battlefield order.
        index = _slot_index(state, slot)
        if not solver.is_artifact_perm(paid.battlefield[index]):
            raise ValueError("Reshape sacrifice is no longer an artifact")
        paid, sacrificed = _remove_artifact_for_reshape_cost(paid, index)
        prized_died = sacrificed.name == "Prized Statue"
        cam_died = sacrificed.name == "Sewer-veillance Cam"
        mana_spent = int(generic + 2)
        paid = solver.add_trace(
            paid,
            f"Phase2 cast Reshape X={x}; sacrifice {sacrificed.name or sacrificed.mode} as additional cost",
        )
        runtime = replace(runtime, true_state=solver._ensure_oracle_instance_tags(paid))
        spell, runtime = _allocate_spell(
            runtime, kind=SPELL_RESHAPE, source=source, x=x, mana_spent=mana_spent
        )
        return _finish_cast_triggers(
            runtime,
            source=source,
            spell=spell,
            mana_spent=mana_spent,
            prized_died=prized_died,
            cam_died=cam_died,
        )

    raise AssertionError("unhandled X-artifact tutor source")


def _search_pending(runtime: NonOracleRuntimeState, obj) -> NonOracleRuntimeState:
    x = int(dict(obj.payload)["x"])
    legal_targets = tuple(
        sorted({
            card for card in runtime.true_state.library
            if card in solver.ARTIFACTS
            and solver.mana_value(card) <= x
            and not solver.cage_blocks_library_battlefield_entry(runtime.true_state, card)
        })
    )
    search = SearchZoneObservation(
        zone="library",
        legal_cards=legal_targets,
        context=f"{obj.card} X={x}",
        may_fail_to_find=True,
    )
    info = apply_observation_batch(runtime.information, ObservationBatch((search,)))
    spec = PendingDecisionSpec(
        decision_id=f"runtime.x_artifact.{obj.card}.target",
        kind=SEARCH_KIND,
        source=obj.card,
        decision_stage=DECISION_POST_OBSERVATION,
        contingent_on=obj.object_id,
    )
    return replace(
        runtime,
        information=info,
        pending=RuntimePendingDecision(
            spec=spec,
            kind=RUNTIME_X_TARGET,
            payload=(("legal_targets", legal_targets), ("source", obj.card), ("x", x)),
        ),
        window=RuntimeDecisionWindow(WINDOW_POST_OBSERVATION),
    )


def handles_x_artifact_stack_top(runtime: NonOracleRuntimeState) -> bool:
    if runtime.pending is not None:
        return False
    top = runtime.stack.top()
    return bool(top and top.kind in {SPELL_RESHAPE, SPELL_WHIR})


def handles_x_artifact_pending(runtime: NonOracleRuntimeState) -> bool:
    return bool(
        runtime.pending
        and runtime.pending.kind in {RUNTIME_X_TARGET, RUNTIME_WHIR_PAYMENT}
    )


def x_artifact_pending_request(
    runtime: NonOracleRuntimeState,
    *,
    horizon: int,
    objective: str,
    policy_id: str,
    caverns_live=None,
) -> DecisionRequest:
    pending = runtime.pending
    if pending is not None and pending.kind == RUNTIME_WHIR_PAYMENT:
        return whir_payment_request(
            runtime,
            horizon=horizon,
            objective=objective,
            policy_id=policy_id,
            caverns_live=caverns_live,
        )
    if pending is None or pending.kind != RUNTIME_X_TARGET:
        raise ValueError("not a pending X-artifact decision")
    data = dict(pending.payload)
    source = str(data["source"])
    x = int(data["x"])
    search = SearchZoneObservation(
        zone="library",
        legal_cards=tuple(data["legal_targets"]),
        context=f"{source} X={x}",
        may_fail_to_find=True,
    )
    context = SearchContext(source, x, pending.spec.decision_id, pending.spec.contingent_on)
    return DecisionRequest(
        observation=runtime.policy_view(caverns_live=caverns_live),
        actions=_target_intents(context, search),
        context=PolicyDecisionContext(
            horizon=horizon,
            objective=objective,
            policy_id=policy_id,
            decision_id=pending.spec.decision_id,
            decision_stage=DECISION_POST_OBSERVATION,
        ),
    )


def apply_x_artifact_pending(runtime: NonOracleRuntimeState, action: ActionIntent) -> NonOracleRuntimeState:
    pending = runtime.pending
    if pending is not None and pending.kind == RUNTIME_WHIR_PAYMENT:
        return apply_whir_payment_pending(runtime, action)
    if pending is None or pending.kind != RUNTIME_X_TARGET:
        raise ValueError("not a pending X-artifact decision")
    request = x_artifact_pending_request(
        runtime, horizon=max(1, int(runtime.true_state.turn)), objective="win_by_horizon", policy_id="runtime"
    )
    legal = {candidate.canonical_key() for candidate in request.actions}
    if action.canonical_key() not in legal:
        raise ValueError("X-artifact target is not legal for the observed search")
    data = dict(pending.payload)
    source = str(data["source"])
    x = int(data["x"])
    target = str(dict(action.parameters).get("target", ""))
    state = runtime.true_state

    if target:
        if target not in tuple(data["legal_targets"]) or target not in state.library:
            raise ValueError("chosen X-artifact target is absent or was not revealed")
        library = list(state.library)
        library.remove(target)
        state = replace(state, library=tuple(library))
        state = solver.add_perm(state, target, sick=target in solver.CREATURES)

    salt = (
        f"reshape:{target}" if source == RESHAPE and target
        else f"whir:{target}" if source == WHIR and target
        else f"{source.lower().replace(' ', '.')}:no-target:x{x}"
    )
    state = replace(state, library=solver.shuffled_library(state, salt))
    state = replace(state, graveyard=state.graveyard + (source,))
    state = solver.check_win(
        solver.add_trace(state, f"Phase2 {source} X={x} -> {target or 'no card'}; shuffle")
    )
    info = apply_observation_batch(
        runtime.information,
        ObservationBatch((ShuffleObservation(source),)),
    )
    runtime = replace(
        runtime,
        true_state=solver._ensure_oracle_instance_tags(state),
        information=info,
        pending=None,
        window=RuntimeDecisionWindow(WINDOW_PRIORITY),
    )
    if target:
        return record_artifact_entry(runtime, (target,), source=f"resolve {source} -> {target}")
    return runtime


def apply_x_artifact_stack_action(runtime: NonOracleRuntimeState, action: ActionIntent) -> NonOracleRuntimeState:
    if action.action_id != ACTION_PASS_PRIORITY or action.kind != "pass_priority":
        raise ValueError("X-artifact tutor spell resolves only after passing priority")
    obj, remaining = runtime.stack.pop_top()
    if obj is None or obj.kind not in {SPELL_RESHAPE, SPELL_WHIR}:
        raise ValueError("top stack object is not an X-artifact tutor spell")
    return _search_pending(replace(runtime, stack=remaining), obj)
