#!/usr/bin/env python3
"""Focused Oracle/non-Oracle line-recognition and public-action parity smoke."""

from __future__ import annotations

import urza_solver as solver
from non_oracle_episode import run_deterministic_episode
from non_oracle_ftt_runtime import MAIN_LEVEL_FTT
from non_oracle_rules_adapter_v2 import apply_main_action, rules_decision_request
from non_oracle_runtime import make_runtime_state
from non_oracle_public_parity_runtime import (
    MAIN_ACTIVATE_FETCH,
    MAIN_ACTIVATE_KNACK_BOUNCE,
)
from non_oracle_urza_runtime import MAIN_USE_URZA_PERMISSION
from non_oracle_urza_search_permission_runtime import USE_CAST_SIMPLE_TUTOR
from non_oracle_urza_x_permission_runtime import USE_CAST_RESHAPE, USE_CAST_WHIR
from solver_architecture import InformationState, canonical_markov_state_key
from urza_permission_adapter import UrzaPermissionState


def _action(runtime, *, kind=None, label_contains=None, parameter=None):
    request = rules_decision_request(runtime, horizon=6, policy_id="line-parity-smoke")
    rows = list(request.actions)
    if kind is not None:
        rows = [row for row in rows if row.kind == kind]
    if label_contains is not None:
        rows = [row for row in rows if label_contains in row.label]
    if parameter is not None:
        key, value = parameter
        rows = [row for row in rows if dict(row.parameters).get(key) == value]
    if not rows:
        raise AssertionError(
            f"no matching action kind={kind!r} label={label_contains!r} parameter={parameter!r}"
        )
    return sorted(rows, key=lambda row: row.action_id)[0]


def _resolve_until_main(runtime, max_steps=32):
    for _ in range(max_steps):
        if runtime.pending is None and not runtime.stack.objects:
            return runtime
        request = rules_decision_request(runtime, horizon=6, policy_id="line-parity-smoke")
        actions = list(request.actions)
        untap = [a for a in actions if "untap" in a.label.lower() and "decline" not in a.label.lower()]
        passes = [a for a in actions if a.kind == "pass_priority"]
        chosen = untap[0] if untap else (passes[0] if passes else actions[0])
        runtime = apply_main_action(runtime, chosen)
    raise AssertionError("runtime did not return to an empty-stack main window")


def test_shared_terminal_recognition():
    cases = (
        (
            "Power Artifact + Grim",
            solver.State(
                turn=3, library=(), hand=(), urza=True, commander_in_command_zone=False,
                pa_target="Grim Monolith",
                battlefield=(
                    solver.Perm(solver.COMMANDER, sick=False),
                    solver.Perm("Grim Monolith"),
                    solver.Perm("Power Artifact"),
                ),
            ),
        ),
        (
            "Power Artifact + Basalt",
            solver.State(
                turn=3, library=(), hand=(), urza=True, commander_in_command_zone=False,
                pa_target="Basalt Monolith",
                battlefield=(
                    solver.Perm(solver.COMMANDER, sick=False),
                    solver.Perm("Basalt Monolith"),
                    solver.Perm("Power Artifact"),
                ),
            ),
        ),
        (
            "Basalt + Gadgeteer",
            solver.State(
                turn=3, library=(), hand=(), urza=True, commander_in_command_zone=False,
                battlefield=(
                    solver.Perm(solver.COMMANDER, sick=False),
                    solver.Perm("Basalt Monolith"),
                    solver.Perm("Forensic Gadgeteer", sick=False),
                ),
            ),
        ),
        (
            "Top + Reality Chip",
            solver.State(
                turn=3, library=("Island",), hand=(), urza=True,
                commander_in_command_zone=False, chip_attached=True,
                chip_target=solver.COMMANDER,
                battlefield=(
                    solver.Perm(solver.COMMANDER, sick=False),
                    solver.Perm("Sensei's Divining Top"),
                    solver.Perm("The Reality Chip", mode="chip_attached"),
                    solver.Perm("Grinding Station"),
                ),
            ),
        ),
        (
            "Top + FTT L3",
            solver.State(
                turn=3, library=("Island",), hand=(), urza=True,
                commander_in_command_zone=False, ftt_level=3, spell_cast_this_turn=True,
                battlefield=(
                    solver.Perm(solver.COMMANDER, sick=False),
                    solver.Perm("Sensei's Divining Top"),
                    solver.Perm("Fortune Teller's Talent"),
                ),
            ),
        ),
        (
            "Top + FTT L2 + producer",
            solver.State(
                turn=3, library=("Island",), hand=(), urza=True,
                commander_in_command_zone=False, ftt_level=2, spell_cast_this_turn=True,
                battlefield=(
                    solver.Perm(solver.COMMANDER, sick=False),
                    solver.Perm("Sensei's Divining Top"),
                    solver.Perm("Fortune Teller's Talent"),
                    solver.Perm("Grinding Station"),
                ),
            ),
        ),
        (
            "Top + Gadgeteer + producer",
            solver.State(
                turn=3, library=("Island",), hand=(), urza=True,
                commander_in_command_zone=False,
                battlefield=(
                    solver.Perm(solver.COMMANDER, sick=False),
                    solver.Perm("Sensei's Divining Top"),
                    solver.Perm("Forensic Gadgeteer", sick=False),
                    solver.Perm("Grinding Station"),
                ),
            ),
        ),
        (
            "Knack/Helix + Cam",
            solver.State(
                turn=3, library=(), hand=(), urza=True, commander_in_command_zone=False,
                battlefield=(
                    solver.Perm(solver.COMMANDER, sick=False),
                    solver.Perm("Sewer-veillance Cam"),
                    solver.Perm("Battered Golem", sick=False, knack_granted=True),
                ),
            ),
        ),
        (
            "Chrome Dome",
            solver.State(
                turn=3, library=(), hand=(), urza=True, commander_in_command_zone=False,
                colorless=5,
                battlefield=(
                    solver.Perm(solver.COMMANDER, sick=False),
                    solver.Perm("Chrome Dome"),
                    solver.Perm("Grinding Station"),
                ),
            ),
        ),
    )
    for family, state in cases:
        oracle = solver.check_win(state)
        assert oracle.won and oracle.win_family == family, family
        result = run_deterministic_episode(make_runtime_state(state), horizon=6)
        assert result.win_turn == state.turn and result.win_family == family, family
    print("shared terminal recognizer parity (all families): PASS")


def test_fetch_parity_and_information_reset():
    state = solver.State(
        turn=2,
        library=("Mystic Remora", "Island", "Sol Ring"),
        hand=(),
        battlefield=(solver.Perm("Polluted Delta"),),
        rng_root_seed=20260826,
    )
    info = InformationState(
        known_top=("Mystic Remora",),
        known_bottom=("Sol Ring",),
    )
    runtime = make_runtime_state(state, info)
    action = _action(runtime, kind=MAIN_ACTIVATE_FETCH)
    after = apply_main_action(runtime, action)

    oracle_rows = solver.fetch_actions(runtime.true_state)
    assert len(oracle_rows) == 1
    oracle = oracle_rows[0]
    assert canonical_markov_state_key(after.true_state) == canonical_markov_state_key(oracle)
    assert any(p.name == "Island" for p in after.true_state.battlefield)
    assert not any(p.name == "Polluted Delta" for p in after.true_state.battlefield)
    assert after.information.known_top == ()
    assert after.information.known_bottom == ()
    print("fetch activation + shuffle information parity: PASS")


def test_ftt_level_surface():
    state = solver.State(
        turn=3,
        library=("Sensei's Divining Top", "Island"),
        hand=(),
        battlefield=(solver.Perm("Fortune Teller's Talent"),),
        ftt_level=1,
        blue=2,
        colorless=5,
    )
    runtime = make_runtime_state(state)
    first = _action(runtime, kind=MAIN_LEVEL_FTT, label_contains="level 1 -> 2")
    runtime = apply_main_action(runtime, first)
    assert runtime.true_state.ftt_level == 2
    second = _action(runtime, kind=MAIN_LEVEL_FTT, label_contains="level 2 -> 3")
    runtime = apply_main_action(runtime, second)
    assert runtime.true_state.ftt_level == 3
    assert runtime.information.known_top == ("Sensei's Divining Top",)
    print("Fortune Teller's Talent level 1 -> 2 -> 3 action surface: PASS")


def test_knack_bounce_recast_loop_surface():
    state = solver.State(
        turn=3,
        library=("Island",),
        hand=(),
        battlefield=(
            solver.Perm("Battered Golem", sick=False, knack_granted=True),
            solver.Perm("Sol Ring"),
        ),
        colorless=2,
        rng_root_seed=20260826,
    )
    runtime = make_runtime_state(state)
    bounce = _action(runtime, kind=MAIN_ACTIVATE_KNACK_BOUNCE, label_contains="bounce Sol Ring")
    after_bounce = apply_main_action(runtime, bounce)

    oracle_rows = [
        row for row in solver.knack_bounce_actions(runtime.true_state)
        if row.trace and "bounces our Sol Ring" in row.trace[-1]
    ]
    assert oracle_rows
    assert canonical_markov_state_key(after_bounce.true_state) == canonical_markov_state_key(oracle_rows[0])
    assert "Sol Ring" in after_bounce.true_state.hand
    golem = next(p for p in after_bounce.true_state.battlefield if p.name == "Battered Golem")
    assert golem.tapped and golem.knack_granted

    cast = _action(after_bounce, kind="main_cast_artifact", label_contains="Sol Ring")
    runtime = apply_main_action(after_bounce, cast)
    runtime = _resolve_until_main(runtime)
    assert any(p.name == "Sol Ring" for p in runtime.true_state.battlefield)
    golem = next(p for p in runtime.true_state.battlefield if p.name == "Battered Golem")
    assert not golem.tapped and golem.knack_granted
    assert any(a.kind == MAIN_ACTIVATE_KNACK_BOUNCE for a in rules_decision_request(
        runtime, horizon=6, policy_id="line-parity-smoke"
    ).actions)
    print("Knack/Helix bounce -> recast -> producer untap loop surface: PASS")


def _permission_runtime(card, *, library, battlefield=()):
    permissions = UrzaPermissionState().grant(card, 2)
    return make_runtime_state(
        solver.State(
            turn=2,
            library=tuple(library),
            hand=(),
            battlefield=tuple(battlefield),
            exile=(card,),
        ),
        permissions=permissions,
    )


def test_urza_permission_extension_production_path():
    mystical = _permission_runtime(
        "Mystical Tutor",
        library=("Dramatic Reversal", "Island", "Sol Ring"),
    )
    mystical_action = _action(
        mystical,
        kind=MAIN_USE_URZA_PERMISSION,
        parameter=("use", USE_CAST_SIMPLE_TUTOR),
    )
    assert dict(mystical_action.parameters).get("card") == "Mystical Tutor"

    reshape = _permission_runtime(
        "Reshape",
        library=("Tormod's Crypt", "Island"),
        battlefield=(solver.Perm("Sol Ring"),),
    )
    reshape_action = _action(
        reshape,
        kind=MAIN_USE_URZA_PERMISSION,
        parameter=("use", USE_CAST_RESHAPE),
    )
    assert dict(reshape_action.parameters).get("x") == 0

    whir = _permission_runtime(
        "Whir of Invention",
        library=("Tormod's Crypt", "Island"),
    )
    whir_action = _action(
        whir,
        kind=MAIN_USE_URZA_PERMISSION,
        parameter=("use", USE_CAST_WHIR),
    )
    assert dict(whir_action.parameters).get("x") == 0
    print("Urza search + X-spell permission production-path installation: PASS")


def main():
    test_shared_terminal_recognition()
    test_fetch_parity_and_information_reset()
    test_ftt_level_surface()
    test_knack_bounce_recast_loop_surface()
    test_urza_permission_extension_production_path()
    print("PHASE5 LINE PARITY SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
