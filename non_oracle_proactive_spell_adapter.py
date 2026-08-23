#!/usr/bin/env python3
"""Typed Phase-2 casting for proactive nonartifact spells.

This slice intentionally covers only effects whose complete goldfish semantics can
be resolved without hidden-information shortcuts.  Search/tutor spells remain on
their Phase-1 staged adapters and Spellseeker remains excluded until its ETB search
is connected.

Supported now:
- engine permanents: Assistant, Mastermind, Gadgeteer, Floodcaller, Remora,
  Rhystic Study, Fortune Teller's Talent, Tezzeret;
- Power Artifact with its artifact target committed at cast time;
- Banishing Knack / Retraction Helix with creature target committed at cast time;
- Dramatic Reversal.

All casts use the shared typed cast-trigger stack, so Valley Floodcaller,
Artificer's Assistant, and Vexing Bauble ordering remains consistent with artifact
and commander casts.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable, Optional, Tuple

import urza_solver as solver
from decision_observation import ActionIntent, DECISION_COMMIT, apply_observation_batch
from non_oracle_runtime import (
    ACTION_PASS_PRIORITY,
    STACK_SPELL,
    NonOracleRuntimeState,
    RuntimeDecisionWindow,
    _cast_trigger_objects,
    _queue_simultaneous_objects,
    _perm_public_signature,
)
from non_oracle_runtime_value_key import WINDOW_PRIORITY
from non_oracle_turn_engine import _refresh_continuous_top
from trigger_order_adapter import post_cast_observations

MAIN_CAST_PROACTIVE_NONARTIFACT = "main_cast_proactive_nonartifact"

SPELL_ENGINE_PERMANENT = "proactive_engine_permanent_spell"
SPELL_POWER_ARTIFACT = "proactive_power_artifact_spell"
SPELL_KNACK = "proactive_knack_spell"
SPELL_DRAMATIC_REVERSAL = "proactive_dramatic_reversal_spell"

ENGINE_PERMANENTS = frozenset({
    "Artificer's Assistant",
    "Faerie Mastermind",
    "Forensic Gadgeteer",
    "Valley Floodcaller",
    "Mystic Remora",
    "Rhystic Study",
    "Fortune Teller's Talent",
    "Tezzeret, Cruel Captain",
})
KNUCK_SPELLS = frozenset({"Banishing Knack", "Retraction Helix"})
SUPPORTED_PROACTIVE = ENGINE_PERMANENTS | KNUCK_SPELLS | frozenset({
    "Power Artifact", "Dramatic Reversal",
})


def _unique_target_perms(state, predicate) -> Tuple[object, ...]:
    """One deterministic representative per strategically identical public target."""
    by_signature = {}
    for perm in state.battlefield:
        if not predicate(perm):
            continue
        signature = _perm_public_signature(perm)
        current = by_signature.get(signature)
        if current is None or int(perm.instance_tag) < int(current.instance_tag):
            by_signature[signature] = perm
    return tuple(by_signature[key] for key in sorted(by_signature, key=repr))


def _power_artifact_targets(state) -> Tuple[object, ...]:
    return _unique_target_perms(
        state,
        lambda perm: (
            solver.is_artifact_perm(perm)
            and perm.mode not in {"chrome_copy", "chrome_copy_preturn"}
        ),
    )


def _knack_targets(state) -> Tuple[object, ...]:
    return _unique_target_perms(state, solver.is_creature_perm)


def proactive_nonartifact_intents(runtime: NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    state = runtime.true_state
    rows = []
    for card in sorted(set(state.hand) & SUPPORTED_PROACTIVE):
        generic, blue = solver.spell_cost(state, card)
        if not solver.can_pay(state, generic, blue):
            continue
        mana_spent = int(generic + blue)

        if card == "Power Artifact":
            targets = _power_artifact_targets(state)
        elif card in KNUCK_SPELLS:
            targets = _knack_targets(state)
        else:
            targets = (None,)

        for index, target in enumerate(targets):
            target_signature = () if target is None else _perm_public_signature(target)
            target_label = "" if target is None else f" -> {target.name or target.mode}"
            rows.append(
                ActionIntent(
                    action_id=f"main.cast.proactive.{card}.{index:02d}",
                    kind=MAIN_CAST_PROACTIVE_NONARTIFACT,
                    parameters=(
                        ("blue_required", int(blue)),
                        ("card", card),
                        ("generic_cost", int(generic)),
                        ("mana_spent", mana_spent),
                        ("target_signature", target_signature),
                    ),
                    equivalence_key=(
                        MAIN_CAST_PROACTIVE_NONARTIFACT,
                        card,
                        int(generic),
                        int(blue),
                        target_signature,
                    ),
                    label=f"Cast {card}{target_label}",
                    decision_stage=DECISION_COMMIT,
                    source=card,
                )
            )
    return tuple(rows)


def _target_from_signature(state, signature: Tuple[object, ...]):
    if not signature:
        return None
    candidates = [
        perm for perm in state.battlefield
        if _perm_public_signature(perm) == tuple(signature)
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda perm: int(perm.instance_tag))


def _spell_kind(card: str) -> str:
    if card in ENGINE_PERMANENTS:
        return SPELL_ENGINE_PERMANENT
    if card == "Power Artifact":
        return SPELL_POWER_ARTIFACT
    if card in KNUCK_SPELLS:
        return SPELL_KNACK
    if card == "Dramatic Reversal":
        return SPELL_DRAMATIC_REVERSAL
    raise ValueError(f"unsupported proactive spell {card!r}")


def begin_proactive_nonartifact_cast(
    runtime: NonOracleRuntimeState,
    action: ActionIntent,
) -> NonOracleRuntimeState:
    legal = {
        candidate.canonical_key(): candidate
        for candidate in proactive_nonartifact_intents(runtime)
    }
    if action.canonical_key() not in legal:
        raise ValueError("proactive nonartifact cast is not currently legal")

    params = dict(action.parameters)
    card = str(params["card"])
    generic = int(params["generic_cost"])
    blue = int(params["blue_required"])
    target_signature = tuple(params.get("target_signature", ()))
    target = _target_from_signature(runtime.true_state, target_signature)
    if target_signature and target is None:
        raise ValueError("committed proactive spell target is no longer present")

    paid = solver.pay(runtime.true_state, generic, blue)
    if paid is None:
        raise ValueError("proactive spell can no longer pay committed cost")
    if card not in paid.hand:
        raise ValueError("proactive spell is no longer in hand")
    paid = replace(
        paid,
        hand=solver.remove_one(paid.hand, card),
        spell_cast_this_turn=True,
    )
    paid = solver.add_trace(paid, f"Phase2 cast {card}")
    runtime = replace(runtime, true_state=paid)

    exact_payload = (("mana_spent", int(params["mana_spent"])),)
    public_payload = (("mana_spent", int(params["mana_spent"])),)
    strategic_payload = list(public_payload)
    if target is not None:
        exact_payload += (("target_tag", int(target.instance_tag)),)
        public_payload += (("target_state", target_signature),)
        strategic_payload.append(("target_state", target_signature))

    spell, stack = runtime.stack.allocate(
        object_type=STACK_SPELL,
        kind=_spell_kind(card),
        source="hand",
        card=card,
        payload=exact_payload,
        public_payload=public_payload,
        strategic_payload=tuple(strategic_payload),
    )
    runtime = replace(runtime, stack=stack.push_existing((spell,)))

    info = apply_observation_batch(
        runtime.information,
        post_cast_observations(paid, card, cast_from_library_top=False),
    )
    runtime = replace(runtime, information=info)
    triggers, allocated = _cast_trigger_objects(
        runtime,
        card,
        int(params["mana_spent"]),
        spell.object_id,
    )
    runtime = replace(runtime, stack=allocated)
    return _queue_simultaneous_objects(runtime, triggers, source=f"cast {card}")


def _remove_top_spell(runtime: NonOracleRuntimeState):
    obj, remaining = runtime.stack.pop_top()
    if obj is None or obj.object_type != STACK_SPELL:
        raise ValueError("top runtime object is not a proactive spell")
    return obj, replace(runtime, stack=remaining)


def _resolve_engine_permanent(runtime: NonOracleRuntimeState, obj) -> NonOracleRuntimeState:
    state = runtime.true_state
    card = obj.card
    if card == "Tezzeret, Cruel Captain":
        state = solver.add_perm(state, card, counters=4, mode="tez_ready")
    else:
        state = solver.add_perm(state, card, sick=card in solver.CREATURES)
    if card == "Fortune Teller's Talent":
        state = replace(state, ftt_level=1)
    state = solver.check_win(solver.add_trace(state, f"Phase2 resolve {card}"))
    info = runtime.information
    if card == "Fortune Teller's Talent":
        info = _refresh_continuous_top(
            state,
            info,
            source="Fortune Teller's Talent enters: continuous top look",
        )
    return replace(
        runtime,
        true_state=solver._ensure_oracle_instance_tags(state),
        information=info,
        window=RuntimeDecisionWindow(WINDOW_PRIORITY),
    )


def _resolve_power_artifact(runtime: NonOracleRuntimeState, obj) -> NonOracleRuntimeState:
    state = runtime.true_state
    target_tag = int(dict(obj.payload).get("target_tag", 0))
    index = next(
        (i for i, perm in enumerate(state.battlefield) if int(perm.instance_tag) == target_tag),
        None,
    )
    if index is None or not solver.is_artifact_perm(state.battlefield[index]):
        state = replace(state, graveyard=state.graveyard + (obj.card,))
        state = solver.add_trace(state, "Phase2 Power Artifact fizzles: target absent")
    else:
        target = state.battlefield[index]
        state = solver.add_perm(state, "Power Artifact")
        state = replace(state, pa_target=target.name)
        state = solver.add_trace(state, f"Phase2 Power Artifact enchants {target.name or target.mode}")
    state = solver.check_win(state)
    return replace(
        runtime,
        true_state=solver._ensure_oracle_instance_tags(state),
        window=RuntimeDecisionWindow(WINDOW_PRIORITY),
    )


def _resolve_knack(runtime: NonOracleRuntimeState, obj) -> NonOracleRuntimeState:
    state = runtime.true_state
    target_tag = int(dict(obj.payload).get("target_tag", 0))
    state = replace(state, graveyard=state.graveyard + (obj.card,))
    index = next(
        (i for i, perm in enumerate(state.battlefield) if int(perm.instance_tag) == target_tag),
        None,
    )
    if index is not None and solver.is_creature_perm(state.battlefield[index]):
        state = solver.update_perm(
            state,
            index,
            knack_granted=True,
            knack_source=obj.card,
        )
        state = solver.add_trace(
            state,
            f"Phase2 {obj.card} grants bounce ability to {state.battlefield[index].name or state.battlefield[index].mode}",
        )
    else:
        state = solver.add_trace(state, f"Phase2 {obj.card} fizzles: target absent")
    state = solver.check_win(state)
    return replace(runtime, true_state=state, window=RuntimeDecisionWindow(WINDOW_PRIORITY))


def _resolve_dramatic_reversal(runtime: NonOracleRuntimeState, obj) -> NonOracleRuntimeState:
    state = replace(runtime.true_state, graveyard=runtime.true_state.graveyard + (obj.card,))
    battlefield = tuple(
        perm if solver.is_land_perm(perm)
        else replace(perm, tapped=False, producer_urza_ready=False)
        for perm in state.battlefield
    )
    state = solver.check_win(
        solver.add_trace(replace(state, battlefield=battlefield), "Phase2 Dramatic Reversal untaps all nonlands")
    )
    return replace(runtime, true_state=state, window=RuntimeDecisionWindow(WINDOW_PRIORITY))


def handles_proactive_stack_top(runtime: NonOracleRuntimeState) -> bool:
    if runtime.pending is not None:
        return False
    top = runtime.stack.top()
    return bool(top and top.kind in {
        SPELL_ENGINE_PERMANENT,
        SPELL_POWER_ARTIFACT,
        SPELL_KNACK,
        SPELL_DRAMATIC_REVERSAL,
    })


def apply_proactive_stack_action(
    runtime: NonOracleRuntimeState,
    action: ActionIntent,
) -> NonOracleRuntimeState:
    if action.action_id != ACTION_PASS_PRIORITY or action.kind != "pass_priority":
        raise ValueError("proactive spell resolves only after passing priority")
    obj, runtime = _remove_top_spell(runtime)
    if obj.kind == SPELL_ENGINE_PERMANENT:
        return _resolve_engine_permanent(runtime, obj)
    if obj.kind == SPELL_POWER_ARTIFACT:
        return _resolve_power_artifact(runtime, obj)
    if obj.kind == SPELL_KNACK:
        return _resolve_knack(runtime, obj)
    if obj.kind == SPELL_DRAMATIC_REVERSAL:
        return _resolve_dramatic_reversal(runtime, obj)
    raise ValueError("top stack object is not handled by proactive spell adapter")
