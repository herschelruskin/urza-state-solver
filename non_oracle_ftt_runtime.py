#!/usr/bin/env python3
"""Phase-2 Fortune Teller's Talent class-level actions.

FTT's class level abilities are public, sorcery-speed resource commitments.  They
make no hidden-information choice and do not cast a spell.  The runtime therefore
models them as immediate main-phase actions:

* level 1 -> 2: pay {3}{U};
* level 2 -> 3: pay {2}{U}.

Level 2's top-play permission is still conditioned on having cast a spell this turn;
level 3 is consumed by the existing ``spell_cost(..., outside=True)`` reduction.
Continuous top look is refreshed after leveling so the information state remains
consistent even when this is the first transition after FTT entered.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Tuple

import urza_solver as solver
import non_oracle_runtime as core
from decision_observation import ActionIntent, DECISION_COMMIT
from non_oracle_turn_engine import _refresh_continuous_top

MAIN_LEVEL_FTT = "main_level_fortune_tellers_talent"
FTT = "Fortune Teller's Talent"


def _level_cost(level: int) -> Tuple[int, int]:
    if int(level) == 1:
        return 3, 1
    if int(level) == 2:
        return 2, 1
    raise ValueError(f"FTT has no modeled next level from {level}")


def ftt_level_main_intents(runtime: core.NonOracleRuntimeState) -> Tuple[ActionIntent, ...]:
    state = runtime.true_state
    if not solver.has(state, FTT) or int(state.ftt_level) not in {1, 2}:
        return ()
    current = int(state.ftt_level)
    generic, blue = _level_cost(current)
    if not solver.can_pay(state, generic, blue):
        return ()
    target = current + 1
    access_live_after = bool(target >= 2 and state.spell_cast_this_turn)
    return (ActionIntent(
        action_id=f"main.ftt.level.{current}.to.{target}",
        kind=MAIN_LEVEL_FTT,
        parameters=(
            ("access_live_after", access_live_after),
            ("blue_required", int(blue)),
            ("from_level", current),
            ("generic_cost", int(generic)),
            ("to_level", target),
        ),
        equivalence_key=(MAIN_LEVEL_FTT, current, target, int(generic), int(blue)),
        label=f"Fortune Teller's Talent: level {current} -> {target}",
        decision_stage=DECISION_COMMIT,
        source=FTT,
    ),)


def apply_ftt_level_action(
    runtime: core.NonOracleRuntimeState,
    action: ActionIntent,
) -> core.NonOracleRuntimeState:
    legal = {candidate.canonical_key() for candidate in ftt_level_main_intents(runtime)}
    if action.canonical_key() not in legal:
        raise ValueError("FTT level action is no longer legal")
    params = dict(action.parameters)
    current = int(params["from_level"])
    target = int(params["to_level"])
    if int(runtime.true_state.ftt_level) != current or target != current + 1:
        raise ValueError("FTT level commitment no longer matches current level")
    generic, blue = _level_cost(current)
    if generic != int(params["generic_cost"]) or blue != int(params["blue_required"]):
        raise ValueError("FTT level cost commitment is malformed")
    state = solver.pay(runtime.true_state, generic, blue)
    if state is None:
        raise ValueError("FTT level cost can no longer be paid")
    state = replace(state, ftt_level=target)
    state = solver.add_trace(state, f"Phase2 Fortune Teller's Talent -> level {target}")
    info = _refresh_continuous_top(
        state,
        runtime.information,
        source=f"Fortune Teller's Talent level {target} continuous look",
    )
    return replace(runtime, true_state=state, information=info)
