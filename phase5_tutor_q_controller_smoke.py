#!/usr/bin/env python3
"""Focused smoke for the selective tutor-Q controller."""

import urza_solver as solver
from non_oracle_rules_adapter_v2 import apply_main_action, rules_decision_request
from non_oracle_runtime import make_runtime_state
from phase5_rollout_policy_v6 import DeterministicRolloutPolicyV6
from phase5_tutor_q_controller import Phase5TutorQController


def request(runtime, policy):
    return rules_decision_request(runtime, horizon=6, policy_id=policy.policy_id)


def action(runtime, policy, kind, contains=""):
    rows=[a for a in request(runtime, policy).actions if a.kind==kind]
    if contains:
        rows=[a for a in rows if contains in a.label]
    assert rows,(kind,contains)
    return sorted(rows,key=lambda a:a.action_id)[0]


def test_q_selects_immediate_terminal_transmute_target():
    policy=DeterministicRolloutPolicyV6()
    controller=Phase5TutorQController(
        screen_rollouts=1,
        confirm_rollouts=2,
        shortlist=5,
        mc_root_seed=20260826,
        continuation_policy=policy,
    )
    state=solver.State(
        turn=4,
        library=("Sensei's Divining Top","Tormod's Crypt","Island"),
        hand=("Transmute Artifact",),
        battlefield=(
            solver.Perm(solver.COMMANDER,sick=False),
            solver.Perm("The Reality Chip",mode="chip_attached"),
            solver.Perm("Grinding Station"),
            solver.Perm("Sapphire Medallion"),
        ),
        blue=3,
        urza=True,
        commander_in_command_zone=False,
        chip_attached=True,
        chip_target=solver.COMMANDER,
    )
    runtime=make_runtime_state(state)
    runtime=apply_main_action(
        runtime,action(runtime,policy,"main_use_transmute_artifact")
    )
    runtime=apply_main_action(
        runtime,action(runtime,policy,"pass_priority")
    )
    runtime=apply_main_action(
        runtime,action(
            runtime,policy,"transmute_choose_sacrifice","Sapphire Medallion"
        )
    )
    req=request(runtime,policy)
    labels=[a.label for a in req.actions]
    assert any("Sensei's Divining Top" in x for x in labels)
    assert any("Tormod's Crypt" in x for x in labels)

    chosen=controller.choose(runtime,req,req.actions)
    assert chosen.kind=="transmute_choose_target"
    assert "Sensei's Divining Top" in chosen.label,chosen.label

    runtime=apply_main_action(runtime,chosen)
    runtime_state=solver.check_win(runtime.true_state)
    assert runtime_state.won
    assert runtime_state.win_family=="Top + Reality Chip"
    print("tutor-Q chooses immediate terminal Transmute target: PASS")


def test_payable_transmute_decline_is_not_a_controller_candidate():
    policy=DeterministicRolloutPolicyV6()
    controller=Phase5TutorQController(
        screen_rollouts=1,
        confirm_rollouts=2,
        shortlist=5,
        mc_root_seed=20260826,
        continuation_policy=policy,
    )
    state=solver.State(
        turn=3,
        library=("The One Ring","Island"),
        hand=("Transmute Artifact",),
        battlefield=(solver.Perm("Sapphire Medallion"),),
        blue=6,
    )
    runtime=make_runtime_state(state)
    runtime=apply_main_action(runtime,action(runtime,policy,"main_use_transmute_artifact"))
    runtime=apply_main_action(runtime,action(runtime,policy,"pass_priority"))
    runtime=apply_main_action(
        runtime,action(runtime,policy,"transmute_choose_sacrifice","Sapphire Medallion")
    )
    runtime=apply_main_action(
        runtime,action(runtime,policy,"transmute_choose_target","The One Ring")
    )
    req=request(runtime,policy)
    assert any("Decline" in a.label for a in req.actions)
    assert any(a.label.startswith("Pay ") for a in req.actions)
    chosen=controller.choose(runtime,req,req.actions)
    assert chosen.label.startswith("Pay "),chosen.label
    print("tutor-Q preserves payable Transmute discipline: PASS")


def main():
    test_q_selects_immediate_terminal_transmute_target()
    test_payable_transmute_decline_is_not_a_controller_candidate()
    print("PHASE5 TUTOR Q CONTROLLER SMOKE: ALL PASS")


if __name__=="__main__":
    main()
