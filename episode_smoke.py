#!/usr/bin/env python3
"""Multi-turn acceptance smokes for the first non-Oracle episode runner."""

import inspect

import urza_solver as solver
import non_oracle_episode as episode_module
import non_oracle_rules_adapter as rules_module
from non_oracle_episode import run_deterministic_episode
from non_oracle_runtime import make_runtime_state


def simple_runtime(library):
    return make_runtime_state(
        solver.State(
            turn=1,
            library=tuple(library),
            hand=("Island", "Sol Ring", "Prized Statue"),
            battlefield=(),
        )
    )


def test_episode_crosses_multiple_turns_through_policy_and_typed_runtime():
    result = run_deterministic_episode(
        simple_runtime(("Island", "Welding Jar", "Island", "Tail")),
        horizon=2,
    )
    assert result.terminal_reason == "horizon"
    assert result.runtime.true_state.turn == 3
    assert len(result.steps) > 4
    assert any(step.action_kind == "main_play_land" for step in result.steps)
    assert any(step.action_kind == "main_cast_artifact" for step in result.steps)
    assert any(step.action_kind == "pass_priority" for step in result.steps)
    assert any(step.action_kind == "main_end_turn" for step in result.steps)
    assert any(p.name == "Prized Statue" for p in result.runtime.true_state.battlefield)


def test_hidden_futures_do_not_change_pre_observation_turn_one_policy_actions():
    left = run_deterministic_episode(
        simple_runtime(("SECRET_ALPHA", "Island", "Tail")),
        horizon=1,
    )
    right = run_deterministic_episode(
        simple_runtime(("SECRET_BETA", "Island", "Tail")),
        horizon=1,
    )
    lturn1 = tuple(
        step.action_strategic_key for step in left.steps if step.turn_before == 1
    )
    rturn1 = tuple(
        step.action_strategic_key for step in right.steps if step.turn_before == 1
    )
    assert lturn1 == rturn1
    # The hidden card becomes a legitimate observation only after the common
    # end-turn choice, so the resulting hands may then differ.
    assert "SECRET_ALPHA" in left.runtime.true_state.hand
    assert "SECRET_BETA" in right.runtime.true_state.hand


def test_episode_runner_never_calls_oracle_legal_actions():
    rules_source = inspect.getsource(rules_module)
    episode_source = inspect.getsource(episode_module)
    assert "solver.legal_actions(" not in rules_source
    assert "solver.legal_actions(" not in episode_source
    assert "oracle_game(" not in rules_source
    assert "oracle_game(" not in episode_source


def test_episode_stops_at_mandatory_unimplemented_window_instead_of_skipping():
    runtime = make_runtime_state(
        solver.State(
            turn=1,
            library=("R1", "R2", "Natural"),
            hand=(),
            battlefield=(solver.Perm("Mystic Remora"),),
        )
    )
    result = run_deterministic_episode(runtime, horizon=3)
    assert result.terminal_reason == "unsupported_remora_upkeep"
    assert result.runtime.true_state.turn == 2
    assert result.runtime.true_state.remora_upkeep_pending
    assert result.runtime.true_state.hand == ("R1", "R2")
    assert result.runtime.true_state.library == ("Natural",)


def test_already_winning_public_state_records_exact_turn():
    state = solver.State(
        turn=3,
        library=(),
        hand=(),
        battlefield=(
            solver.Perm(solver.COMMANDER, sick=False),
            solver.Perm("Basalt Monolith"),
            solver.Perm("Power Artifact"),
        ),
        urza=True,
        commander_in_command_zone=False,
        pa_target="Basalt Monolith",
    )
    result = run_deterministic_episode(make_runtime_state(state), horizon=6)
    assert result.terminal_reason == "win"
    assert result.win_turn == 3
    assert result.won_by_horizon
    assert result.steps == ()


def test_episode_is_repeatable_for_same_concrete_world():
    one = run_deterministic_episode(
        simple_runtime(("Island", "Welding Jar", "Tail")),
        horizon=2,
    )
    two = run_deterministic_episode(
        simple_runtime(("Island", "Welding Jar", "Tail")),
        horizon=2,
    )
    assert tuple(step.action_strategic_key for step in one.steps) == tuple(
        step.action_strategic_key for step in two.steps
    )
    assert one.terminal_reason == two.terminal_reason
    assert one.runtime.value_key() == two.runtime.value_key()


def main():
    tests = (
        test_episode_crosses_multiple_turns_through_policy_and_typed_runtime,
        test_hidden_futures_do_not_change_pre_observation_turn_one_policy_actions,
        test_episode_runner_never_calls_oracle_legal_actions,
        test_episode_stops_at_mandatory_unimplemented_window_instead_of_skipping,
        test_already_winning_public_state_records_exact_turn,
        test_episode_is_repeatable_for_same_concrete_world,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("NON-ORACLE MULTI-TURN EPISODE SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
