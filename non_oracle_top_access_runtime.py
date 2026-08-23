#!/usr/bin/env python3
"""Phase-2 known-top land/artifact play bridge for Reality Chip / FTT.

This slice intentionally uses InformationState -- never the concrete hidden library --
to decide which top-card actions are visible to the policy.  It models the compact
main-phase surface shared by an attached Reality Chip and an active level-2+
Fortune Teller's Talent permission:

* play a known top land when the land drop is available;
* cast a known top artifact for its normal cost;
* preserve Mox Diamond's as-it-enters land-discard decision;
* preserve Everflowing Chalice's committed multikicker count.

Fortune Teller's Talent class-level actions are delegated through the same main-phase
extension point because they are the public resource commitments that make FTT top
access reachable.  The leveling rules themselves live in ``non_oracle_ftt_runtime``.

The rules layer validates that the advertised known card is still the physical top.
Casting removes it from the library before post-cast observations are applied, so a
continuous Chip/FTT look can expose the new top before simultaneous cast triggers are
ordered.  Grafdigger's Cage blocks artifact spell casts from the library but does not
block playing a land.

Nonartifact top casting and priority-time top casting are deliberately left to the
next timing slice rather than approximated here.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Tuple

import urza_solver as solver
import non_oracle_runtime as core
from decision_observation import (
    ActionIntent,
    DECISION_COMMIT,
    MoveKnownCardObservation,
    ObservationBatch,
    apply_observation_batch,
)
from non_oracle_ftt_runtime import (
    MAIN_LEVEL_FTT,
    apply_ftt_level_action,
    ftt_level_main_intents,
)
from non_oracle_turn_engine import _refresh_continuous_top
from non_oracle_utility_artifact_runtime import (
    CHALICE,
    MOX_DIAMOND,
    UTILITY_ARTIFACT_SPELL,
)
from trigger_order_adapter import post_cast_observations

MAIN_PLAY_LAND = "main_play_land"
MAIN_CAST_ARTIFACT = "main_cast_artifact"
TOP_ZONE = "library_top"


def _access_source(state: solver.State) -> str:
    chip = bool(state.chip_attached)
    ftt = bool(state.ftt_level >= 2 and state.spell_cast_this_turn)
    if chip and ftt:
        return "Reality Chip + Fortune Teller's Talent"
    if chip:
        return "Reality Chip"
    if ftt:
        return "Fortune Teller's Talent"
    return ""


def _known_top(runtime: core.NonOracleRuntimeState) -> str:
    if not runtime.information.known_top:
        return ""
    return str(runtime.information.known_top[0])


def _land_intent(card: str, source: str) -> ActionIntent:
    return ActionIntent(
        action_id=f"main.top.land.{card}",
        kind=MAIN_PLAY_LAND,
        parameters=(
            ("card", card),
            ("from_zone", TOP_ZONE),
            ("top_access_source", source),
        ),
        equivalence_key=(MAIN_PLAY_LAND, TOP_ZONE, card),
        label=f"{source}: play {card} from top",
        decision_stage=DECISION_COMMIT,
        source=source,
    )


def _artifact_intent(
    card: str,
    source: str,
    *,
    generic: int,
    blue: int,
    kicks: int = 0,
    special: str = "",
) -> ActionIntent:
    mana_spent = int(generic + blue)
    suffix = f" kicked {kicks} time(s)" if card == CHALICE else ""
    return ActionIntent(
        action_id=(
            f"main.top.artifact.{card}.k{kicks}"
            if card == CHALICE
            else f"main.top.artifact.{card}"
        ),
        kind=MAIN_CAST_ARTIFACT,
        parameters=(
            ("blue_required", int(blue)),
            ("card", card),
            ("from_zone", TOP_ZONE),
            ("generic_cost", int(generic)),
            ("kicks", int(kicks)),
            ("mana_spent", mana_spent),
            ("special", special),
            ("top_access_source", source),
        ),
        equivalence_key=(
            MAIN_CAST_ARTIFACT,
            TOP_ZONE,
            card,
            int(generic),
            int(blue),
            int(kicks),
            special,
        ),
        label=f"{source}: cast {card} from top{suffix}",
        decision_stage=DECISION_COMMIT,
        source=source,
    )


def top_access_main_intents(runtime: core.NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    # FTT leveling is intentionally collected here so the central Phase-2 rules
    # adapter keeps one compact extension point for the whole top-access engine.
    rows = list(ftt_level_main_intents(runtime))
    state = runtime.true_state
    source = _access_source(state)
    card = _known_top(runtime)
    if not source or not card:
        return tuple(sorted(rows, key=lambda action: action.action_id))

    if card in solver.ALL_LANDS and not state.land_played:
        rows.append(_land_intent(card, source))

    # In this batch MDFCs receive only their land face. Their nonartifact spell
    # face belongs to the following generic top-spell timing slice.
    if card not in solver.ARTIFACTS or card in solver.ALL_LANDS:
        return tuple(sorted(rows, key=lambda action: action.action_id))
    if solver.cage_blocks_library_cast(state, card):
        return tuple(sorted(rows, key=lambda action: action.action_id))

    if card == CHALICE:
        max_k = min(8, max(0, (int(state.blue) + int(state.colorless)) // 2))
        for kicks in range(max_k + 1):
            cost = 2 * kicks
            if solver.can_pay(state, cost, 0):
                rows.append(_artifact_intent(
                    card,
                    source,
                    generic=cost,
                    blue=0,
                    kicks=kicks,
                    special="chalice",
                ))
    elif card == MOX_DIAMOND:
        rows.append(_artifact_intent(
            card,
            source,
            generic=0,
            blue=0,
            special="mox_diamond",
        ))
    else:
        generic, blue = solver.spell_cost(state, card, outside=True)
        if solver.can_pay(state, generic, blue):
            rows.append(_artifact_intent(
                card,
                source,
                generic=int(generic),
                blue=int(blue),
            ))

    return tuple(sorted(rows, key=lambda action: action.action_id))


def is_top_access_action(action: ActionIntent) -> bool:
    if action.kind == MAIN_LEVEL_FTT:
        return True
    return bool(
        action.kind in {MAIN_PLAY_LAND, MAIN_CAST_ARTIFACT}
        and dict(action.parameters).get("from_zone") == TOP_ZONE
    )


def _validate_top(runtime: core.NonOracleRuntimeState, card: str) -> None:
    if not runtime.true_state.library or str(runtime.true_state.library[0]) != card:
        raise ValueError("known top-access card no longer matches the physical library top")
    if not runtime.information.known_top or str(runtime.information.known_top[0]) != card:
        raise ValueError("top-access action is no longer supported by legal information")


def _play_top_land(
    runtime: core.NonOracleRuntimeState,
    card: str,
    source: str,
) -> core.NonOracleRuntimeState:
    _validate_top(runtime, card)
    if card not in solver.ALL_LANDS or runtime.true_state.land_played:
        raise ValueError("top land play is no longer legal")

    state = replace(
        runtime.true_state,
        library=tuple(runtime.true_state.library[1:]),
        hand=runtime.true_state.hand + (card,),
    )
    physical = solver._play_land_physical(state, card)
    if physical is None:
        raise ValueError("top land play failed physical legality")
    state, message = physical
    state = solver.add_trace(state, f"Phase2 {source}: {message} from library top")

    info = apply_observation_batch(
        runtime.information,
        ObservationBatch((
            MoveKnownCardObservation(
                card,
                from_zone="library",
                to_zone="battlefield",
                position="top",
                source=f"{source} top land play",
            ),
        )),
    )
    info = _refresh_continuous_top(
        state,
        info,
        source=f"post-{source} top land play continuous look",
    )
    runtime = replace(
        runtime,
        true_state=solver._ensure_oracle_instance_tags(state),
        information=info,
    )
    if card == "Seat of the Synod":
        runtime = core.record_artifact_entry(
            runtime,
            ("Seat of the Synod",),
            source="play Seat of the Synod from top",
        )
    return runtime


def _begin_special_top_artifact(
    runtime: core.NonOracleRuntimeState,
    *,
    card: str,
    kicks: int,
    mana_spent: int,
    source: str,
) -> core.NonOracleRuntimeState:
    _validate_top(runtime, card)
    paid = solver.pay(runtime.true_state, int(mana_spent), 0)
    if paid is None:
        raise ValueError(f"cannot pay committed top-cast cost for {card}")
    state = replace(
        paid,
        library=tuple(paid.library[1:]),
        spell_cast_this_turn=True,
    )
    state = solver.add_trace(
        state,
        f"Phase2 {source}: cast {card} from library top; mana spent={mana_spent}",
    )
    runtime = replace(runtime, true_state=state)

    spell, stack = runtime.stack.allocate(
        object_type=core.STACK_SPELL,
        kind=UTILITY_ARTIFACT_SPELL,
        source=TOP_ZONE,
        card=card,
        payload=(("kicks", int(kicks)), ("mana_spent", int(mana_spent))),
        public_payload=(("kicks", int(kicks)), ("mana_spent", int(mana_spent))),
        strategic_payload=(("kicks", int(kicks)), ("mana_spent", int(mana_spent))),
    )
    runtime = replace(runtime, stack=stack.push_existing((spell,)))
    info = apply_observation_batch(
        runtime.information,
        post_cast_observations(state, card, cast_from_library_top=True),
    )
    runtime = replace(runtime, information=info)
    triggers, allocated = core._cast_trigger_objects(
        runtime,
        card,
        int(mana_spent),
        spell.object_id,
    )
    runtime = replace(runtime, stack=allocated)
    return core._queue_simultaneous_objects(
        runtime,
        triggers,
        source=f"cast {card} from top",
    )


def _cast_top_artifact(
    runtime: core.NonOracleRuntimeState,
    action: ActionIntent,
) -> core.NonOracleRuntimeState:
    params = dict(action.parameters)
    card = str(params["card"])
    source = str(params.get("top_access_source", "top access"))
    _validate_top(runtime, card)
    if card not in solver.ARTIFACTS or card in solver.ALL_LANDS:
        raise ValueError("top artifact action no longer names an artifact spell")
    if solver.cage_blocks_library_cast(runtime.true_state, card):
        raise ValueError("Grafdigger's Cage blocks this library cast")

    special = str(params.get("special", ""))
    if special:
        if card == CHALICE and special == "chalice":
            kicks = int(params.get("kicks", 0))
            mana_spent = int(params.get("mana_spent", 0))
            if kicks < 0 or mana_spent != 2 * kicks:
                raise ValueError("top Chalice multikicker commitment is malformed")
            return _begin_special_top_artifact(
                runtime,
                card=card,
                kicks=kicks,
                mana_spent=mana_spent,
                source=source,
            )
        if card == MOX_DIAMOND and special == "mox_diamond":
            if int(params.get("mana_spent", 0)) != 0:
                raise ValueError("top Mox Diamond commitment is malformed")
            return _begin_special_top_artifact(
                runtime,
                card=card,
                kicks=0,
                mana_spent=0,
                source=source,
            )
        raise ValueError("unknown special top-artifact commitment")

    generic = int(params.get("generic_cost", 0))
    blue = int(params.get("blue_required", 0))
    mana_spent = int(params.get("mana_spent", generic + blue))
    if mana_spent != generic + blue:
        raise ValueError("top artifact mana commitment is malformed")
    paid = solver.pay(runtime.true_state, generic, blue)
    if paid is None:
        raise ValueError("top artifact cast can no longer pay its committed cost")
    return core.begin_committed_artifact_cast(
        replace(runtime, true_state=paid),
        card,
        mana_spent=mana_spent,
        from_zone=TOP_ZONE,
        cast_from_library_top=True,
    )


def begin_top_access_main_action(
    runtime: core.NonOracleRuntimeState,
    action: ActionIntent,
) -> core.NonOracleRuntimeState:
    legal = {candidate.canonical_key() for candidate in top_access_main_intents(runtime)}
    if action.canonical_key() not in legal:
        raise ValueError("top-access action is no longer legal")
    if action.kind == MAIN_LEVEL_FTT:
        return apply_ftt_level_action(runtime, action)
    params = dict(action.parameters)
    card = str(params["card"])
    source = str(params.get("top_access_source", "top access"))
    if action.kind == MAIN_PLAY_LAND:
        return _play_top_land(runtime, card, source)
    if action.kind == MAIN_CAST_ARTIFACT:
        return _cast_top_artifact(runtime, action)
    raise ValueError(f"unsupported top-access main action {action.kind!r}")
