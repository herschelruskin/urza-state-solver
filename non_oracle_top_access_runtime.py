#!/usr/bin/env python3
"""Information-faithful Reality Chip / Fortune Teller's Talent top access.

Only cards that are legally known through ``InformationState`` are exposed.  The
rules layer then validates that the advertised card is still the physical top before
moving it.  Casting removes the top card before post-cast observations are applied,
so continuous Chip/FTT look can reveal the newly exposed top before simultaneous cast
triggers are ordered.

Modeled here:
- main-phase top land plays;
- artifact casts from top, including Chalice and Mox Diamond special commitments;
- already-typed proactive nonartifact spells from top;
- Gitaxian Probe from top;
- the same spell casts in a real priority window only when normal timing permits
  (instant/native flash, or Valley Floodcaller granting flash to noncreature spells).

Search/tutor families and remaining special spell faces are intentionally separate
follow-up slices rather than being approximated with Oracle successor states.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Tuple

import urza_solver as solver
import non_oracle_runtime as core
from decision_observation import (
    ActionIntent,
    DECISION_COMMIT,
    DECISION_MECHANICAL,
    MoveKnownCardObservation,
    ObservationBatch,
    apply_observation_batch,
)
from non_oracle_chrome_dome_runtime import (
    MAIN_ACTIVATE_CHROME,
    begin_chrome_main_activation,
    chrome_main_intents,
)
from non_oracle_draw_engine_runtime import MAIN_CAST_PROBE, PROBE, SPELL_PROBE
from non_oracle_ftt_runtime import (
    MAIN_LEVEL_FTT,
    apply_ftt_level_action,
    ftt_level_main_intents,
)
from non_oracle_proactive_spell_adapter import (
    MAIN_CAST_PROACTIVE_NONARTIFACT,
    KNUCK_SPELLS,
    SUPPORTED_PROACTIVE,
    _knack_targets,
    _power_artifact_targets,
    _spell_kind,
    _target_from_signature,
)
from non_oracle_runtime_value_key import WINDOW_PRIORITY
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


def _decision_stage(priority: bool) -> str:
    return DECISION_MECHANICAL if priority else DECISION_COMMIT


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
    priority: bool = False,
) -> ActionIntent:
    mana_spent = int(generic + blue)
    suffix = f" kicked {kicks} time(s)" if card == CHALICE else ""
    prefix = "priority" if priority else "main"
    return ActionIntent(
        action_id=(
            f"{prefix}.top.artifact.{card}.k{kicks}"
            if card == CHALICE
            else f"{prefix}.top.artifact.{card}"
        ),
        kind=MAIN_CAST_ARTIFACT,
        parameters=(
            ("blue_required", int(blue)),
            ("card", card),
            ("from_zone", TOP_ZONE),
            ("generic_cost", int(generic)),
            ("kicks", int(kicks)),
            ("mana_spent", mana_spent),
            ("priority", bool(priority)),
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
            bool(priority),
        ),
        label=f"{source}: cast {card} from top{suffix}",
        decision_stage=_decision_stage(priority),
        source=card,
    )


def _proactive_intents(
    state: solver.State,
    card: str,
    source: str,
    *,
    priority: bool,
) -> Tuple[ActionIntent, ...]:
    if card not in SUPPORTED_PROACTIVE:
        return ()
    if priority and not solver._can_cast_card_at_priority(state, card):
        return ()
    generic, blue = solver.spell_cost(state, card, outside=True)
    if not solver.can_pay(state, generic, blue):
        return ()

    if card == "Power Artifact":
        targets = _power_artifact_targets(state)
    elif card in KNUCK_SPELLS:
        targets = _knack_targets(state)
    else:
        targets = (None,)

    prefix = "priority" if priority else "main"
    rows = []
    for index, target in enumerate(targets):
        signature = () if target is None else core._perm_public_signature(target)
        target_label = "" if target is None else f" -> {target.name or target.mode}"
        rows.append(ActionIntent(
            action_id=f"{prefix}.top.proactive.{card}.{index:02d}",
            kind=MAIN_CAST_PROACTIVE_NONARTIFACT,
            parameters=(
                ("blue_required", int(blue)),
                ("card", card),
                ("from_zone", TOP_ZONE),
                ("generic_cost", int(generic)),
                ("mana_spent", int(generic + blue)),
                ("priority", bool(priority)),
                ("target_signature", signature),
                ("top_access_source", source),
            ),
            equivalence_key=(
                MAIN_CAST_PROACTIVE_NONARTIFACT,
                TOP_ZONE,
                card,
                int(generic),
                int(blue),
                signature,
                bool(priority),
            ),
            label=f"{source}: cast {card} from top{target_label}",
            decision_stage=_decision_stage(priority),
            source=card,
        ))
    return tuple(rows)


def _probe_intent(
    state: solver.State,
    source: str,
    *,
    priority: bool,
) -> Tuple[ActionIntent, ...]:
    if priority and not solver._can_cast_card_at_priority(state, PROBE):
        return ()
    pay_blue = bool(solver.has(state, "Vexing Bauble") and state.blue >= 1)
    blue = 1 if pay_blue else 0
    countered = bool(solver.has(state, "Vexing Bauble") and blue == 0)
    prefix = "priority" if priority else "main"
    return (ActionIntent(
        action_id=f"{prefix}.top.gitaxian_probe",
        kind=MAIN_CAST_PROBE,
        parameters=(
            ("blue_required", blue),
            ("card", PROBE),
            ("from_zone", TOP_ZONE),
            ("mana_spent", blue),
            ("priority", bool(priority)),
            ("top_access_source", source),
            ("will_be_countered_by_own_bauble", countered),
        ),
        equivalence_key=(MAIN_CAST_PROBE, TOP_ZONE, blue, countered, bool(priority)),
        label=(
            f"{source}: cast Gitaxian Probe from top for U"
            if pay_blue
            else f"{source}: cast Gitaxian Probe from top with no mana spent"
        ),
        decision_stage=_decision_stage(priority),
        source=PROBE,
    ),)


def _known_top_spell_intents(
    runtime: core.NonOracleRuntimeState,
    *,
    priority: bool,
) -> Tuple[ActionIntent, ...]:
    state = runtime.true_state
    source = _access_source(state)
    card = _known_top(runtime)
    if not source or not card:
        return ()

    rows = []
    if not priority and card in solver.ALL_LANDS and not state.land_played:
        rows.append(_land_intent(card, source))

    if solver.cage_blocks_library_cast(state, card):
        return tuple(rows)

    if card in solver.ARTIFACTS and card not in solver.ALL_LANDS:
        if priority and not solver._can_cast_card_at_priority(state, card):
            return tuple(rows)
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
                        priority=priority,
                    ))
        elif card == MOX_DIAMOND:
            rows.append(_artifact_intent(
                card,
                source,
                generic=0,
                blue=0,
                special="mox_diamond",
                priority=priority,
            ))
        else:
            generic, blue = solver.spell_cost(state, card, outside=True)
            if solver.can_pay(state, generic, blue):
                rows.append(_artifact_intent(
                    card,
                    source,
                    generic=int(generic),
                    blue=int(blue),
                    priority=priority,
                ))
        return tuple(rows)

    rows.extend(_proactive_intents(state, card, source, priority=priority))
    if card == PROBE:
        rows.extend(_probe_intent(state, source, priority=priority))
    return tuple(rows)


def top_access_main_intents(runtime: core.NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    rows = list(ftt_level_main_intents(runtime))
    rows.extend(chrome_main_intents(runtime))
    rows.extend(_known_top_spell_intents(runtime, priority=False))
    return tuple(sorted(rows, key=lambda action: action.action_id))


def top_access_priority_intents(runtime: core.NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    if runtime.pending is not None or not runtime.stack.objects or runtime.window.kind != WINDOW_PRIORITY:
        return ()
    return tuple(sorted(
        _known_top_spell_intents(runtime, priority=True),
        key=lambda action: action.action_id,
    ))


def is_top_access_action(action: ActionIntent) -> bool:
    if action.kind in {MAIN_LEVEL_FTT, MAIN_ACTIVATE_CHROME}:
        return True
    return bool(
        action.kind in {
            MAIN_PLAY_LAND,
            MAIN_CAST_ARTIFACT,
            MAIN_CAST_PROACTIVE_NONARTIFACT,
            MAIN_CAST_PROBE,
        }
        and dict(action.parameters).get("from_zone") == TOP_ZONE
    )


def is_top_access_priority_action(action: ActionIntent) -> bool:
    return bool(is_top_access_action(action) and dict(action.parameters).get("priority", False))


def _validate_top(runtime: core.NonOracleRuntimeState, card: str) -> None:
    if not runtime.true_state.library or str(runtime.true_state.library[0]) != card:
        raise ValueError("known top-access card no longer matches the physical library top")
    if not runtime.information.known_top or str(runtime.information.known_top[0]) != card:
        raise ValueError("top-access action is no longer supported by legal information")


def _play_top_land(runtime: core.NonOracleRuntimeState, card: str, source: str) -> core.NonOracleRuntimeState:
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
        ObservationBatch((MoveKnownCardObservation(
            card,
            from_zone="library",
            to_zone="battlefield",
            position="top",
            source=f"{source} top land play",
        ),)),
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
    return core._queue_simultaneous_objects(runtime, triggers, source=f"cast {card} from top")


def _cast_top_artifact(runtime: core.NonOracleRuntimeState, action: ActionIntent) -> core.NonOracleRuntimeState:
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


def _cast_top_proactive(runtime: core.NonOracleRuntimeState, action: ActionIntent) -> core.NonOracleRuntimeState:
    params = dict(action.parameters)
    card = str(params["card"])
    source = str(params.get("top_access_source", "top access"))
    _validate_top(runtime, card)
    if card not in SUPPORTED_PROACTIVE:
        raise ValueError("top proactive action names an unsupported spell")
    if solver.cage_blocks_library_cast(runtime.true_state, card):
        raise ValueError("Grafdigger's Cage blocks this library cast")
    generic = int(params["generic_cost"])
    blue = int(params["blue_required"])
    paid = solver.pay(runtime.true_state, generic, blue)
    if paid is None:
        raise ValueError("top proactive spell can no longer pay committed cost")

    target_signature = tuple(params.get("target_signature", ()))
    target = _target_from_signature(runtime.true_state, target_signature)
    if target_signature and target is None:
        raise ValueError("committed top proactive target is no longer present")

    state = replace(
        paid,
        library=tuple(paid.library[1:]),
        spell_cast_this_turn=True,
    )
    state = solver.add_trace(state, f"Phase2 {source}: cast {card} from library top")
    runtime = replace(runtime, true_state=state)

    exact_payload = (("mana_spent", int(params["mana_spent"])),)
    public_payload = (("mana_spent", int(params["mana_spent"])),)
    strategic_payload = list(public_payload)
    if target is not None:
        exact_payload += (("target_tag", int(target.instance_tag)),)
        public_payload += (("target_state", target_signature),)
        strategic_payload.append(("target_state", target_signature))

    spell, stack = runtime.stack.allocate(
        object_type=core.STACK_SPELL,
        kind=_spell_kind(card),
        source=TOP_ZONE,
        card=card,
        payload=exact_payload,
        public_payload=public_payload,
        strategic_payload=tuple(strategic_payload),
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
        int(params["mana_spent"]),
        spell.object_id,
    )
    runtime = replace(runtime, stack=allocated)
    return core._queue_simultaneous_objects(runtime, triggers, source=f"cast {card} from top")


def _cast_top_probe(runtime: core.NonOracleRuntimeState, action: ActionIntent) -> core.NonOracleRuntimeState:
    params = dict(action.parameters)
    _validate_top(runtime, PROBE)
    if solver.cage_blocks_library_cast(runtime.true_state, PROBE):
        raise ValueError("Grafdigger's Cage blocks Gitaxian Probe from the library")
    blue = int(params.get("blue_required", 0))
    mana_spent = int(params.get("mana_spent", blue))
    paid = solver.pay(runtime.true_state, 0, blue)
    if paid is None:
        raise ValueError("top Gitaxian Probe payment is no longer legal")
    state = replace(
        paid,
        library=tuple(paid.library[1:]),
        spell_cast_this_turn=True,
    )
    state = solver.add_trace(state, f"Phase2 cast Gitaxian Probe from library top; mana spent={mana_spent}")
    runtime = replace(runtime, true_state=state)
    spell, stack = runtime.stack.allocate(
        object_type=core.STACK_SPELL,
        kind=SPELL_PROBE,
        source=TOP_ZONE,
        card=PROBE,
        payload=(("mana_spent", mana_spent),),
        public_payload=(("mana_spent", mana_spent),),
        strategic_payload=(("mana_spent", mana_spent),),
    )
    runtime = replace(runtime, stack=stack.push_existing((spell,)))
    info = apply_observation_batch(
        runtime.information,
        post_cast_observations(state, PROBE, cast_from_library_top=True),
    )
    runtime = replace(runtime, information=info)
    triggers, stack = core._cast_trigger_objects(runtime, PROBE, mana_spent, spell.object_id)
    runtime = replace(runtime, stack=stack)
    return core._queue_simultaneous_objects(runtime, triggers, source="cast Gitaxian Probe from top")


def _begin_top_cast(runtime: core.NonOracleRuntimeState, action: ActionIntent) -> core.NonOracleRuntimeState:
    params = dict(action.parameters)
    card = str(params.get("card", ""))
    source = str(params.get("top_access_source", "top access"))
    if action.kind == MAIN_PLAY_LAND:
        return _play_top_land(runtime, card, source)
    if action.kind == MAIN_CAST_ARTIFACT:
        return _cast_top_artifact(runtime, action)
    if action.kind == MAIN_CAST_PROACTIVE_NONARTIFACT:
        return _cast_top_proactive(runtime, action)
    if action.kind == MAIN_CAST_PROBE:
        return _cast_top_probe(runtime, action)
    raise ValueError(f"unsupported top-access cast action {action.kind!r}")


def begin_top_access_main_action(
    runtime: core.NonOracleRuntimeState,
    action: ActionIntent,
) -> core.NonOracleRuntimeState:
    legal = {candidate.canonical_key() for candidate in top_access_main_intents(runtime)}
    if action.canonical_key() not in legal:
        raise ValueError("top-access/engine action is no longer legal")
    if action.kind == MAIN_LEVEL_FTT:
        return apply_ftt_level_action(runtime, action)
    if action.kind == MAIN_ACTIVATE_CHROME:
        return begin_chrome_main_activation(runtime, action)
    return _begin_top_cast(runtime, action)


def begin_top_access_priority_action(
    runtime: core.NonOracleRuntimeState,
    action: ActionIntent,
) -> core.NonOracleRuntimeState:
    legal = {candidate.canonical_key() for candidate in top_access_priority_intents(runtime)}
    if action.canonical_key() not in legal:
        raise ValueError("top-access priority action is no longer legal")
    return _begin_top_cast(runtime, action)
