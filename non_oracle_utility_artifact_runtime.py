#!/usr/bin/env python3
"""Phase-2 utility-artifact runtime bridge.

This slice connects four high-frequency public action surfaces without delegating
choice to the clairvoyant Oracle:

* Mox Diamond -- cast first, choose its land-discard replacement only when the
  spell resolves and would enter;
* Everflowing Chalice -- commit multikicker count before paying/casting, then
  enter with exactly that many charge counters;
* Sensei's Divining Top -- commit/pay before the concrete top cards are revealed,
  then choose a reorder only from the typed RevealTop observation;
* Voltaic Key / Manifold Key -- public {1}, {T}: untap target artifact actions.

The special artifact spells reuse the shared runtime cast-trigger machinery, so
Assistant/Uthros/Floodcaller/Vexing Bauble timing remains identical to ordinary
artifact casts.  Exact permanent/object IDs stay rules-side; policy actions use
only public permanent signatures and card names.
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
    DECISION_POST_OBSERVATION,
    DecisionRequest,
    PendingDecisionSpec,
    PolicyDecisionContext,
    apply_observation_batch,
)
from non_oracle_runtime_value_key import (
    RuntimeDecisionWindow,
    WINDOW_POST_OBSERVATION,
    WINDOW_PRIORITY,
)
from top_decision_adapter import (
    TOP_ACTIVATE_ACTION_ID,
    TOP_REORDER_DECISION_KIND,
    information_after_top_activation,
    information_after_top_reorder,
    resolve_top_activation,
    resolve_top_reorder,
    top_activation_intents,
    top_reorder_intents,
)
from trigger_order_adapter import post_cast_observations

MAIN_CAST_UTILITY_ARTIFACT = "main_cast_utility_artifact"
MAIN_ACTIVATE_TOP = "main_activate_top"
MAIN_ACTIVATE_KEY = "main_activate_key"
DECISION_MOX_DIAMOND_ENTRY = "runtime_mox_diamond_entry"
UTILITY_ARTIFACT_SPELL = "utility_artifact_spell"

MOX_DIAMOND = "Mox Diamond"
CHALICE = "Everflowing Chalice"
TOP = "Sensei's Divining Top"
KEYS = frozenset({"Voltaic Key", "Manifold Key"})


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


def _top_intent(runtime: core.NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    phase1 = top_activation_intents(runtime.true_state)
    if not phase1:
        return ()
    source = phase1[0]
    return (ActionIntent(
        action_id=TOP_ACTIVATE_ACTION_ID,
        kind=MAIN_ACTIVATE_TOP,
        parameters=tuple(source.parameters),
        equivalence_key=(MAIN_ACTIVATE_TOP, "look_reorder_top3"),
        label=source.label,
        decision_stage=DECISION_COMMIT,
        source=TOP,
    ),)


def _mox_intent(state: solver.State) -> Tuple[ActionIntent, ...]:
    if MOX_DIAMOND not in state.hand:
        return ()
    return (ActionIntent(
        action_id="main.cast.utility.mox_diamond",
        kind=MAIN_CAST_UTILITY_ARTIFACT,
        parameters=(("card", MOX_DIAMOND), ("kicks", 0), ("mana_spent", 0)),
        equivalence_key=(MAIN_CAST_UTILITY_ARTIFACT, MOX_DIAMOND),
        label="Cast Mox Diamond",
        decision_stage=DECISION_COMMIT,
        source=MOX_DIAMOND,
    ),)


def _chalice_intents(state: solver.State) -> Tuple[ActionIntent, ...]:
    if CHALICE not in state.hand:
        return ()
    max_k = min(8, max(0, (int(state.blue) + int(state.colorless)) // 2))
    rows = []
    for kicks in range(max_k + 1):
        cost = 2 * kicks
        if not solver.can_pay(state, cost, 0):
            continue
        rows.append(ActionIntent(
            action_id=f"main.cast.utility.chalice.k{kicks}",
            kind=MAIN_CAST_UTILITY_ARTIFACT,
            parameters=(("card", CHALICE), ("kicks", kicks), ("mana_spent", cost)),
            equivalence_key=(MAIN_CAST_UTILITY_ARTIFACT, CHALICE, kicks),
            label=f"Cast Everflowing Chalice kicked {kicks} time(s)",
            decision_stage=DECISION_COMMIT,
            source=CHALICE,
        ))
    return tuple(rows)


def _key_intents(state: solver.State) -> Tuple[ActionIntent, ...]:
    if not solver.can_pay(state, 1, 0):
        return ()
    key_groups = _groups(
        state,
        lambda perm: perm.name in KEYS and not perm.tapped,
    )
    target_groups = _groups(
        state,
        lambda perm: solver.is_artifact_perm(perm) and perm.tapped,
    )
    rows = []
    index = 0
    for key_signature in sorted(key_groups, key=repr):
        key_name = str(key_signature[0])
        for target_signature in sorted(target_groups, key=repr):
            target_name = str(target_signature[0])
            # An untapped key and tapped target cannot be the same exact object,
            # but keep the explicit public-state guard for future signature edits.
            if key_signature == target_signature:
                continue
            rows.append(ActionIntent(
                action_id=f"main.key.{index:03d}",
                kind=MAIN_ACTIVATE_KEY,
                parameters=(
                    ("key_name", key_name),
                    ("key_signature", key_signature),
                    ("target_name", target_name),
                    ("target_signature", target_signature),
                ),
                equivalence_key=(MAIN_ACTIVATE_KEY, key_signature, target_signature),
                label=f"{key_name}: untap {target_name}",
                decision_stage=DECISION_COMMIT,
                source=key_name,
            ))
            index += 1
    return tuple(rows)


def utility_main_intents(runtime: core.NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    state = runtime.true_state
    rows = []
    rows.extend(_mox_intent(state))
    rows.extend(_chalice_intents(state))
    rows.extend(_top_intent(runtime))
    rows.extend(_key_intents(state))
    return tuple(sorted(rows, key=lambda action: action.action_id))


def _begin_special_artifact_spell(
    runtime: core.NonOracleRuntimeState,
    *,
    card: str,
    kicks: int,
    mana_spent: int,
) -> core.NonOracleRuntimeState:
    state = runtime.true_state
    if card not in state.hand:
        raise ValueError(f"{card!r} is no longer in hand")
    paid = solver.pay(state, int(mana_spent), 0)
    if paid is None:
        raise ValueError(f"cannot pay committed cost for {card}")
    state = replace(
        paid,
        hand=solver.remove_one(paid.hand, card),
        spell_cast_this_turn=True,
    )
    runtime = replace(runtime, true_state=state)

    spell, stack = runtime.stack.allocate(
        object_type=core.STACK_SPELL,
        kind=UTILITY_ARTIFACT_SPELL,
        source="hand",
        card=card,
        payload=(("kicks", int(kicks)), ("mana_spent", int(mana_spent))),
        public_payload=(("kicks", int(kicks)), ("mana_spent", int(mana_spent))),
        strategic_payload=(("kicks", int(kicks)), ("mana_spent", int(mana_spent))),
    )
    runtime = replace(runtime, stack=stack.push_existing((spell,)))
    info = apply_observation_batch(
        runtime.information,
        post_cast_observations(state, card, cast_from_library_top=False),
    )
    runtime = replace(runtime, information=info)
    triggers, allocated = core._cast_trigger_objects(
        runtime,
        card,
        int(mana_spent),
        spell.object_id,
    )
    runtime = replace(runtime, stack=allocated)
    return core._queue_simultaneous_objects(runtime, triggers, source=f"cast {card}")


def begin_utility_main_action(
    runtime: core.NonOracleRuntimeState,
    action: ActionIntent,
) -> core.NonOracleRuntimeState:
    legal = {candidate.canonical_key() for candidate in utility_main_intents(runtime)}
    if action.canonical_key() not in legal:
        raise ValueError("utility artifact action is no longer legal")
    params = dict(action.parameters)

    if action.kind == MAIN_CAST_UTILITY_ARTIFACT:
        card = str(params["card"])
        kicks = int(params.get("kicks", 0))
        mana_spent = int(params.get("mana_spent", 0))
        if card == MOX_DIAMOND:
            if kicks != 0 or mana_spent != 0:
                raise ValueError("Mox Diamond cast commitment is malformed")
        elif card == CHALICE:
            if mana_spent != 2 * kicks or kicks < 0:
                raise ValueError("Everflowing Chalice multikicker commitment is malformed")
        else:
            raise ValueError(f"unsupported utility artifact cast {card!r}")
        return _begin_special_artifact_spell(
            runtime,
            card=card,
            kicks=kicks,
            mana_spent=mana_spent,
        )

    if action.kind == MAIN_ACTIVATE_TOP:
        envelope = resolve_top_activation(runtime.true_state, action)
        info = information_after_top_activation(runtime.information, envelope)
        if envelope.pending_decision is None:
            return replace(
                runtime,
                true_state=envelope.true_state,
                information=info,
                window=RuntimeDecisionWindow(WINDOW_PRIORITY),
            )
        return replace(
            runtime,
            true_state=envelope.true_state,
            information=info,
            pending=core.RuntimePendingDecision(
                spec=envelope.pending_decision,
                kind=TOP_REORDER_DECISION_KIND,
                payload=(),
            ),
            window=RuntimeDecisionWindow(WINDOW_POST_OBSERVATION),
        )

    if action.kind == MAIN_ACTIVATE_KEY:
        key_signature = tuple(params["key_signature"])
        target_signature = tuple(params["target_signature"])
        key_groups = _groups(
            runtime.true_state,
            lambda perm: perm.name in KEYS and not perm.tapped,
        )
        target_groups = _groups(
            runtime.true_state,
            lambda perm: solver.is_artifact_perm(perm) and perm.tapped,
        )
        keys = key_groups.get(key_signature, ())
        targets = target_groups.get(target_signature, ())
        if not keys or not targets:
            raise ValueError("Key source/target is no longer legal")
        key = keys[0]
        target = next(
            (candidate for candidate in targets if int(candidate.instance_tag) != int(key.instance_tag)),
            None,
        )
        if target is None:
            raise ValueError("Key cannot target its own object")
        state = solver.pay(runtime.true_state, 1, 0)
        if state is None:
            raise ValueError("Key activation cost is no longer payable")
        key_idx = core._perm_index_for_tag(state, int(key.instance_tag))
        target_idx = core._perm_index_for_tag(state, int(target.instance_tag))
        if key_idx is None or target_idx is None:
            raise ValueError("Key source/target left the battlefield")
        state = solver.update_perm(state, key_idx, tapped=True)
        target_idx = core._perm_index_for_tag(state, int(target.instance_tag))
        state = solver.update_perm(state, target_idx, tapped=False)
        state = solver.add_trace(state, f"Phase2 {key.name} untaps {target.name or target.mode}")
        return replace(runtime, true_state=state)

    raise ValueError(f"unsupported utility main action {action.kind!r}")


def handles_utility_pending(runtime: core.NonOracleRuntimeState) -> bool:
    return bool(
        runtime.pending
        and runtime.pending.kind in {DECISION_MOX_DIAMOND_ENTRY, TOP_REORDER_DECISION_KIND}
    )


def handles_utility_stack_top(runtime: core.NonOracleRuntimeState) -> bool:
    if runtime.pending is not None:
        return False
    top = runtime.stack.top()
    return bool(top and top.object_type == core.STACK_SPELL and top.kind == UTILITY_ARTIFACT_SPELL)


def _mox_entry_actions(runtime: core.NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    rows = [ActionIntent(
        action_id="runtime.mox_diamond.entry.decline",
        kind=DECISION_MOX_DIAMOND_ENTRY,
        parameters=(("land", ""),),
        equivalence_key=(DECISION_MOX_DIAMOND_ENTRY, "decline"),
        label="Mox Diamond: decline/cannot discard a land",
        decision_stage=DECISION_MECHANICAL,
        source=MOX_DIAMOND,
    )]
    for land in sorted(set(runtime.true_state.hand) & solver.TRUE_LAND_CARDS):
        rows.append(ActionIntent(
            action_id=f"runtime.mox_diamond.entry.discard.{land}",
            kind=DECISION_MOX_DIAMOND_ENTRY,
            parameters=(("land", land),),
            equivalence_key=(DECISION_MOX_DIAMOND_ENTRY, land),
            label=f"Mox Diamond: discard {land} and enter",
            decision_stage=DECISION_MECHANICAL,
            source=MOX_DIAMOND,
        ))
    return tuple(rows)


def utility_pending_request(
    runtime: core.NonOracleRuntimeState,
    *,
    horizon: int,
    objective: str,
    policy_id: str,
    caverns_live=None,
) -> DecisionRequest:
    if not handles_utility_pending(runtime):
        raise ValueError("runtime has no utility-artifact pending decision")
    if runtime.pending.kind == DECISION_MOX_DIAMOND_ENTRY:
        actions = _mox_entry_actions(runtime)
    else:
        actions = top_reorder_intents(runtime.information)
    return DecisionRequest(
        observation=runtime.policy_view(caverns_live=caverns_live),
        actions=tuple(actions),
        context=PolicyDecisionContext(
            horizon=horizon,
            objective=objective,
            policy_id=policy_id,
            decision_id=runtime.pending.spec.decision_id,
            decision_stage=runtime.pending.spec.decision_stage,
        ),
    )


def apply_utility_pending(
    runtime: core.NonOracleRuntimeState,
    action: ActionIntent,
) -> core.NonOracleRuntimeState:
    request = utility_pending_request(
        runtime,
        horizon=max(1, int(runtime.true_state.turn)),
        objective="win_by_horizon",
        policy_id="runtime",
    )
    legal = {candidate.canonical_key() for candidate in request.actions}
    if action.canonical_key() not in legal:
        raise ValueError("utility pending choice is no longer legal")

    if runtime.pending.kind == TOP_REORDER_DECISION_KIND:
        envelope = resolve_top_reorder(runtime.true_state, runtime.information, action)
        info = information_after_top_reorder(runtime.information, envelope)
        return replace(
            runtime,
            true_state=envelope.true_state,
            information=info,
            pending=None,
            window=RuntimeDecisionWindow(WINDOW_PRIORITY),
        )

    land = str(dict(action.parameters).get("land", ""))
    state = runtime.true_state
    runtime = replace(runtime, pending=None)
    if not land:
        state = replace(state, graveyard=state.graveyard + (MOX_DIAMOND,))
        state = solver.add_trace(state, "Phase2 Mox Diamond declines land discard -> graveyard")
        return replace(
            runtime,
            true_state=state,
            window=RuntimeDecisionWindow(WINDOW_PRIORITY),
        )
    if land not in state.hand or land not in solver.TRUE_LAND_CARDS:
        raise ValueError("Mox Diamond replacement land is no longer legal")
    state = replace(
        state,
        hand=solver.remove_one(state.hand, land),
        graveyard=state.graveyard + (land,),
    )
    state = solver.add_perm(state, MOX_DIAMOND, mode="diamond")
    state = solver.add_trace(state, f"Phase2 Mox Diamond discards true land card {land}")
    runtime = replace(runtime, true_state=solver._ensure_oracle_instance_tags(state))
    return core.record_artifact_entry(runtime, (MOX_DIAMOND,), source="resolve Mox Diamond")


def apply_utility_stack_action(
    runtime: core.NonOracleRuntimeState,
    action: ActionIntent,
) -> core.NonOracleRuntimeState:
    if action.action_id != core.ACTION_PASS_PRIORITY or action.kind != "pass_priority":
        raise ValueError("utility artifact spell resolves only after passing priority")
    obj, remaining = runtime.stack.pop_top()
    if obj is None or obj.kind != UTILITY_ARTIFACT_SPELL:
        raise ValueError("top object is not a utility artifact spell")
    runtime = replace(runtime, stack=remaining)
    params = dict(obj.payload)

    if obj.card == CHALICE:
        kicks = int(params.get("kicks", 0))
        state = solver.add_perm(runtime.true_state, CHALICE, counters=kicks)
        state = solver.add_trace(state, f"Phase2 resolve Everflowing Chalice with {kicks} charge counter(s)")
        runtime = replace(runtime, true_state=solver._ensure_oracle_instance_tags(state))
        return core.record_artifact_entry(runtime, (CHALICE,), source="resolve Everflowing Chalice")

    if obj.card == MOX_DIAMOND:
        spec = PendingDecisionSpec(
            decision_id=f"{obj.object_id}.mox_diamond.entry",
            kind=DECISION_MOX_DIAMOND_ENTRY,
            source=MOX_DIAMOND,
            decision_stage=DECISION_MECHANICAL,
            contingent_on=obj.object_id,
        )
        return replace(
            runtime,
            pending=core.RuntimePendingDecision(
                spec=spec,
                kind=DECISION_MOX_DIAMOND_ENTRY,
                payload=(("spell", obj),),
            ),
            window=RuntimeDecisionWindow(WINDOW_POST_OBSERVATION),
        )

    raise ValueError(f"unknown utility artifact spell {obj.card!r}")
