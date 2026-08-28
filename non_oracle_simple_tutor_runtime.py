#!/usr/bin/env python3
"""Typed Phase-2 runtime bridge for the simple tutor family.

The Phase-1 tutor adapter already established the correct information boundary:
commit first, inspect only the legal search set after resolution, then choose a
target.  This module places those commitments on the actual Phase-2 stack so cast
triggers and priority remain legal rather than resolving tutors atomically.

Supported:
- Dizzy Spell / Muddle the Mixture transmute abilities;
- Merchant Scroll / Mystical Tutor spells;
- Spellseeker spell -> ETB trigger -> search.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Tuple

import urza_solver as solver
from decision_observation import (
    ActionIntent,
    DECISION_COMMIT,
    DECISION_MECHANICAL,
    DECISION_POST_OBSERVATION,
    DecisionRequest,
    ObservationBatch,
    PendingDecisionSpec,
    PolicyDecisionContext,
    SearchZoneObservation,
    TransitionEnvelope,
    apply_observation_batch,
)
from non_oracle_runtime import (
    ACTION_PASS_PRIORITY,
    STACK_SPELL,
    STACK_TRIGGER,
    NonOracleRuntimeState,
    RuntimeDecisionWindow,
    RuntimePendingDecision,
    _cast_trigger_objects,
    _queue_simultaneous_objects,
)
from non_oracle_runtime_value_key import WINDOW_POST_OBSERVATION, WINDOW_PRIORITY
from trigger_order_adapter import post_cast_observations
from tutor_decision_adapter import (
    TUTOR_TARGET_DECISION_KIND,
    information_after_tutor_target,
    resolve_tutor_target,
    tutor_target_intents,
)

MAIN_USE_SIMPLE_TUTOR = "main_use_simple_tutor"
SPELL_SIMPLE_TUTOR = "simple_tutor_spell"
ABILITY_TRANSMUTE = "simple_tutor_transmute"
SPELLSEEKER_SPELL = "simple_tutor_spellseeker_spell"
SPELLSEEKER_ETB = "simple_tutor_spellseeker_etb"
RUNTIME_TUTOR_TARGET = "runtime_simple_tutor_target"

TUTOR_CONFIG = {
    "Dizzy Spell": ("dizzy", 1, 2, "transmute", "hand"),
    "Muddle the Mixture": ("muddle", 1, 2, "transmute", "hand"),
    "Merchant Scroll": ("merchant", 1, 1, "spell", "hand"),
    "Mystical Tutor": ("mystical", 0, 1, "spell", "top"),
    "Spellseeker": ("spellseeker", 2, 1, "spellseeker", "hand"),
}


def simple_tutor_runtime_intents(runtime: NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    state = runtime.true_state
    rows = []
    for source in sorted(set(state.hand) & set(TUTOR_CONFIG)):
        search_kind, generic, blue, mode, result_zone = TUTOR_CONFIG[source]
        # Use spell-cost reduction for actual spells/Spellseeker; transmute has an
        # activated-ability cost and is not reduced by Sapphire Medallion.
        if mode in {"spell", "spellseeker"}:
            generic, blue = solver.spell_cost(state, source)
        if not solver.can_pay(state, generic, blue):
            continue
        rows.append(
            ActionIntent(
                action_id=f"main.simple_tutor.{source}",
                kind=MAIN_USE_SIMPLE_TUTOR,
                parameters=(
                    ("blue_required", int(blue)),
                    ("generic_cost", int(generic)),
                    ("mode", mode),
                    ("result_zone", result_zone),
                    ("search_kind", search_kind),
                    ("source", source),
                ),
                equivalence_key=(
                    MAIN_USE_SIMPLE_TUTOR,
                    source,
                    search_kind,
                    mode,
                    int(generic),
                    int(blue),
                ),
                label=f"Use {source}",
                decision_stage=DECISION_COMMIT,
                source=source,
            )
        )
    return tuple(rows)


def _queue_spell(runtime, *, source, search_kind, result_zone, spell_kind, mana_spent):
    spell, stack = runtime.stack.allocate(
        object_type=STACK_SPELL,
        kind=spell_kind,
        source="hand",
        card=source,
        payload=(
            ("search_kind", search_kind),
            ("result_zone", result_zone),
            ("mana_spent", int(mana_spent)),
        ),
        public_payload=(("search_kind", search_kind), ("result_zone", result_zone)),
        strategic_payload=(("search_kind", search_kind), ("result_zone", result_zone)),
    )
    runtime = replace(runtime, stack=stack.push_existing((spell,)))
    info = apply_observation_batch(
        runtime.information,
        post_cast_observations(runtime.true_state, source, cast_from_library_top=False),
    )
    runtime = replace(runtime, information=info)
    triggers, allocated = _cast_trigger_objects(
        runtime,
        source,
        int(mana_spent),
        spell.object_id,
    )
    runtime = replace(runtime, stack=allocated)
    return _queue_simultaneous_objects(runtime, triggers, source=f"cast {source}")


def begin_simple_tutor(runtime: NonOracleRuntimeState, action: ActionIntent) -> NonOracleRuntimeState:
    legal = {candidate.canonical_key(): candidate for candidate in simple_tutor_runtime_intents(runtime)}
    if action.canonical_key() not in legal:
        raise ValueError("simple tutor commitment is not currently legal")
    params = dict(action.parameters)
    source = str(params["source"])
    generic = int(params["generic_cost"])
    blue = int(params["blue_required"])
    mode = str(params["mode"])
    search_kind = str(params["search_kind"])
    result_zone = str(params["result_zone"])

    paid = solver.pay(runtime.true_state, generic, blue)
    if paid is None or source not in paid.hand:
        raise ValueError("simple tutor can no longer pay/commit")
    paid = replace(paid, hand=solver.remove_one(paid.hand, source))

    if mode == "transmute":
        # Discarding the card is part of the transmute activation cost.
        paid = replace(paid, graveyard=paid.graveyard + (source,))
        paid = solver.add_trace(paid, f"Phase2 activate transmute {source}")
        ability, stack = runtime.stack.allocate(
            object_type=STACK_TRIGGER,
            kind=ABILITY_TRANSMUTE,
            source=source,
            card=source,
            payload=(("search_kind", search_kind), ("result_zone", result_zone)),
            public_payload=(("search_kind", search_kind), ("result_zone", result_zone)),
            strategic_payload=(("search_kind", search_kind), ("result_zone", result_zone)),
        )
        return replace(
            runtime,
            true_state=paid,
            stack=stack.push_existing((ability,)),
            window=RuntimeDecisionWindow(WINDOW_PRIORITY),
        )

    paid = replace(paid, spell_cast_this_turn=True)
    paid = solver.add_trace(paid, f"Phase2 cast {source}")
    runtime = replace(runtime, true_state=paid)
    spell_kind = SPELLSEEKER_SPELL if mode == "spellseeker" else SPELL_SIMPLE_TUTOR
    return _queue_spell(
        runtime,
        source=source,
        search_kind=search_kind,
        result_zone=result_zone,
        spell_kind=spell_kind,
        mana_spent=generic + blue,
    )


def _search_pending(runtime, *, source, search_kind, result_zone, contingent_on):
    legal_targets = tuple(solver.tutor_targets(runtime.true_state, search_kind))
    observation = SearchZoneObservation(
        zone="library",
        legal_cards=legal_targets,
        context=source,
        may_fail_to_find=True,
    )
    info = apply_observation_batch(
        runtime.information,
        ObservationBatch((observation,)),
    )

    # A search of a hidden zone may legally fail to find.  When the modeled
    # eligible set is actually empty there is no player choice to expose:
    # resolve the no-find branch mechanically, shuffle the concrete library,
    # and return to priority.  This prevents an empty pending decision from
    # becoming an artificial rollout hard blocker.
    if not legal_targets:
        state = replace(
            runtime.true_state,
            library=solver.shuffled_library(
                runtime.true_state,
                f"simple-tutor-no-find:{source}:{search_kind}",
            ),
        )
        state = solver.add_trace(
            state,
            f"{source}: search finds no legal target; shuffle",
        )
        return replace(
            runtime,
            true_state=solver._ensure_oracle_instance_tags(state),
            information=info,
            pending=None,
            window=RuntimeDecisionWindow(WINDOW_PRIORITY),
        )

    spec = PendingDecisionSpec(
        decision_id=f"runtime.simple_tutor.{source}.target",
        kind=TUTOR_TARGET_DECISION_KIND,
        source=source,
        decision_stage=DECISION_POST_OBSERVATION,
        contingent_on=str(contingent_on),
    )
    return replace(
        runtime,
        information=info,
        pending=RuntimePendingDecision(
            spec=spec,
            kind=RUNTIME_TUTOR_TARGET,
            payload=(
                ("legal_targets", legal_targets),
                ("result_zone", result_zone),
                ("search_kind", search_kind),
                ("source", source),
            ),
        ),
        window=RuntimeDecisionWindow(WINDOW_POST_OBSERVATION),
    )


def _resolve_tutor_stack_top(runtime: NonOracleRuntimeState) -> NonOracleRuntimeState:
    obj, remaining = runtime.stack.pop_top()
    if obj is None:
        raise ValueError("empty tutor stack")
    runtime = replace(runtime, stack=remaining)
    params = dict(obj.payload)

    if obj.kind == ABILITY_TRANSMUTE:
        return _search_pending(
            runtime,
            source=obj.source,
            search_kind=str(params["search_kind"]),
            result_zone=str(params["result_zone"]),
            contingent_on=obj.object_id,
        )

    if obj.kind == SPELL_SIMPLE_TUTOR:
        state = replace(runtime.true_state, graveyard=runtime.true_state.graveyard + (obj.card,))
        state = solver.add_trace(state, f"Phase2 resolve {obj.card}")
        runtime = replace(runtime, true_state=state)
        return _search_pending(
            runtime,
            source=obj.card,
            search_kind=str(params["search_kind"]),
            result_zone=str(params["result_zone"]),
            contingent_on=obj.object_id,
        )

    if obj.kind == SPELLSEEKER_SPELL:
        state = solver.add_perm(runtime.true_state, "Spellseeker", sick=True)
        state = solver.add_trace(state, "Phase2 Spellseeker resolves")
        runtime = replace(runtime, true_state=solver._ensure_oracle_instance_tags(state))
        trigger, stack = runtime.stack.allocate(
            object_type=STACK_TRIGGER,
            kind=SPELLSEEKER_ETB,
            source="Spellseeker",
            card="Spellseeker",
            payload=(("search_kind", "spellseeker"), ("result_zone", "hand")),
            public_payload=(("search_kind", "spellseeker"),),
            strategic_payload=(("search_kind", "spellseeker"),),
        )
        return replace(
            runtime,
            stack=stack.push_existing((trigger,)),
            window=RuntimeDecisionWindow(WINDOW_PRIORITY),
        )

    if obj.kind == SPELLSEEKER_ETB:
        return _search_pending(
            runtime,
            source="Spellseeker",
            search_kind="spellseeker",
            result_zone="hand",
            contingent_on=obj.object_id,
        )

    raise ValueError(f"not a simple tutor stack object {obj.kind!r}")


def handles_simple_tutor_stack_top(runtime: NonOracleRuntimeState) -> bool:
    if runtime.pending is not None:
        return False
    top = runtime.stack.top()
    return bool(top and top.kind in {
        ABILITY_TRANSMUTE, SPELL_SIMPLE_TUTOR, SPELLSEEKER_SPELL, SPELLSEEKER_ETB,
    })


def handles_simple_tutor_pending(runtime: NonOracleRuntimeState) -> bool:
    return bool(runtime.pending and runtime.pending.kind == RUNTIME_TUTOR_TARGET)


def _pending_envelope(runtime: NonOracleRuntimeState) -> TransitionEnvelope:
    pending = runtime.pending
    if pending is None or pending.kind != RUNTIME_TUTOR_TARGET:
        raise ValueError("not a pending simple tutor target")
    data = dict(pending.payload)
    observation = SearchZoneObservation(
        zone="library",
        legal_cards=tuple(data["legal_targets"]),
        context=str(data["source"]),
        may_fail_to_find=True,
    )
    return TransitionEnvelope(
        true_state=runtime.true_state,
        observations=ObservationBatch((observation,)),
        pending_decision=pending.spec,
    )


def simple_tutor_pending_request(
    runtime: NonOracleRuntimeState,
    *,
    horizon: int,
    objective: str,
    policy_id: str,
    caverns_live=None,
) -> DecisionRequest:
    envelope = _pending_envelope(runtime)
    return DecisionRequest(
        observation=runtime.policy_view(caverns_live=caverns_live),
        actions=tutor_target_intents(envelope),
        context=PolicyDecisionContext(
            horizon=horizon,
            objective=objective,
            policy_id=policy_id,
            decision_id=runtime.pending.spec.decision_id,
            decision_stage=DECISION_POST_OBSERVATION,
        ),
    )


def apply_simple_tutor_pending(runtime: NonOracleRuntimeState, action: ActionIntent) -> NonOracleRuntimeState:
    envelope = _pending_envelope(runtime)
    resolved = resolve_tutor_target(runtime.true_state, envelope, action)
    info = information_after_tutor_target(runtime.information, resolved)
    state = solver.check_win(resolved.true_state)
    return replace(
        runtime,
        true_state=solver._ensure_oracle_instance_tags(state),
        information=info,
        pending=None,
        window=RuntimeDecisionWindow(WINDOW_PRIORITY),
    )


def apply_simple_tutor_stack_action(runtime: NonOracleRuntimeState, action: ActionIntent) -> NonOracleRuntimeState:
    if action.action_id != ACTION_PASS_PRIORITY or action.kind != "pass_priority":
        raise ValueError("simple tutor stack resolves only after passing priority")
    return _resolve_tutor_stack_top(runtime)
