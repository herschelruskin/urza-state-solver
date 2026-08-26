#!/usr/bin/env python3
"""Focused regression tests for exact-world recurrent-state action suppression."""

from dataclasses import replace

import urza_solver as solver
from non_oracle_episode import episode_cycle_key, run_deterministic_episode
from non_oracle_runtime import make_runtime_state
from phase5_rollout_policy_v5 import DeterministicRolloutPolicyV5
from solver_architecture import InformationState


def test_cycle_key_keeps_hidden_world_but_ignores_trace_and_stack_ids():
    base = solver.State(
        turn=3,
        library=("Sol Ring", "Island"),
        hand=("Mox Opal",),
        battlefield=(solver.Perm("Battered Golem", sick=False, knack_granted=True),),
        rng_root_seed=17,
    )
    left = make_runtime_state(base, InformationState())
    right = make_runtime_state(replace(base, trace=("irrelevant provenance",)), InformationState())
    assert episode_cycle_key(left) == episode_cycle_key(right)

    changed_library = make_runtime_state(replace(base, library=("Island", "Sol Ring")), InformationState())
    changed_seed = make_runtime_state(replace(base, rng_root_seed=18), InformationState())
    assert episode_cycle_key(left) != episode_cycle_key(changed_library)
    assert episode_cycle_key(left) != episode_cycle_key(changed_seed)
    print("episode cycle key exact-world/provenance boundary: PASS")


def test_knack_zero_cost_loop_tries_alternative_action():
    # Reproduce the recurrent shape from held-out hand 20 without depending on its
    # entire opening sequence.  V5 strongly prefers bouncing/recasting Mox Opal.
    # Once that exact state/action pair has been tried, the episode runner must not
    # choose it forever; it should eventually take another legal continuation.
    state = solver.State(
        turn=5,
        library=("Island", "Sol Ring", "Power Artifact"),
        hand=("Mox Opal", "Scour for Scrap", "Reshape"),
        battlefield=(
            solver.Perm("Island"),
            solver.Perm("Grinding Station"),
            solver.Perm("The Reality Chip"),
            solver.Perm("Battered Golem", sick=False, knack_granted=True),
            solver.Perm(solver.COMMANDER, sick=False),
            solver.Perm("Construct", mode="construct"),
            solver.Perm("Spellseeker", sick=False),
        ),
        urza=True,
        commander_in_command_zone=False,
        construct=True,
        blue=2,
        colorless=2,
        rng_root_seed=20260826,
    )
    result = run_deterministic_episode(
        make_runtime_state(state),
        horizon=5,
        max_steps=160,
        policy=DeterministicRolloutPolicyV5(),
    )
    bounce_steps = [step for step in result.steps if step.action_kind in {
        "main_activate_knack_bounce", "priority_activate_knack_bounce"
    }]
    # The old runner hit max_steps while repeating bounce/recast.  A finite number
    # of bounces is fine; reaching the cap through that recurrence is not.
    assert result.terminal_reason != "step_limit"
    assert len(bounce_steps) < 20
    assert any(step.action_kind not in {
        "main_activate_knack_bounce", "priority_activate_knack_bounce",
        "main_cast_artifact", "runtime_producer_untap", "pass_priority",
    } for step in result.steps)
    print("exact recurrent Knack/Mox loop suppression: PASS")


def main():
    test_cycle_key_keeps_hidden_world_but_ignores_trace_and_stack_ids()
    test_knack_zero_cost_loop_tries_alternative_action()
    print("PHASE5 EPISODE CYCLE SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
