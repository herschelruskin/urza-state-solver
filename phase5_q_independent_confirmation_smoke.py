#!/usr/bin/env python3
"""Focused regressions for independent Q screening/confirmation worlds."""

import urza_solver as solver

from non_oracle_runtime import make_runtime_state
from phase4_hidden_world import HiddenWorldSampler
from strategic_value_state import LibraryBeliefKey
from information_state_propagation import initial_information
from phase5_rollout_policy_v6 import DeterministicRolloutPolicyV6
from phase5_selective_tutor_q import SelectiveTutorQController


def test_controller_uses_disjoint_namespaces():
    controller=SelectiveTutorQController(
        continuation_policy=DeterministicRolloutPolicyV6(),
        horizon=2,
        mc_root_seed=20260827,
        screen_rollouts=1,
        confirm_rollouts=2,
        shortlist_size=3,
    )
    assert controller.screen.sample_namespace=="screen"
    assert controller.confirm.sample_namespace=="confirm"
    assert controller.screen.sample_namespace!=controller.confirm.sample_namespace
    print("Q controller screen/confirm sample namespaces are disjoint: PASS")


def test_namespaces_change_hidden_world_coordinate_not_belief():
    state=solver.State(
        turn=1,
        library=(
            "Power Artifact","Defense Grid","Island","Sol Ring",
            "Mana Vault","Sensei's Divining Top","Swan Song",
        ),
        hand=("Muddle the Mixture",),
        battlefield=(),
    )
    info=initial_information(state)
    belief=LibraryBeliefKey.from_state(state,info)
    sampler=HiddenWorldSampler(20260827)
    screen=sampler.sample(
        belief,
        sample_id=("phase5-q","screen",0),
    )
    confirm=sampler.sample(
        belief,
        sample_id=("phase5-q","confirm",0),
    )
    assert screen.belief_digest==confirm.belief_digest
    assert screen.rng_root_seed!=confirm.rng_root_seed
    assert sorted(screen.library)==sorted(confirm.library)
    print("screen/confirm share belief but use different MC coordinates: PASS")


def main():
    test_controller_uses_disjoint_namespaces()
    test_namespaces_change_hidden_world_coordinate_not_belief()
    print("PHASE5 Q INDEPENDENT CONFIRMATION SMOKE: ALL PASS")


if __name__=="__main__":
    main()
