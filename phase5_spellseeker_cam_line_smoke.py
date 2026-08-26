#!/usr/bin/env python3
"""End-to-end production-path smoke for Spellseeker's Cam conversion route.

This is deliberately a *line execution* test, not a presence-terminal shortcut.
Under sufficient visible resources and with a separate ready creature:

  Spellseeker -> Knack/Helix
  cast Knack/Helix on ready creature
  tap that creature -> bounce Spellseeker
  replay Spellseeker -> Transmute Artifact
  Transmute a visible MV1 artifact -> Sewer-veillance Cam
  Cam ETB -> untap the Knack/Helix creature
  shared terminal recognizer -> Knack/Helix + Cam

Spellseeker remains free to tutor for other cards whenever this expensive route is
not the best/available continuation.
"""

import urza_solver as solver

from non_oracle_cam_runtime import DECISION_CAM_EFFECT, DECISION_CAM_TARGET
from non_oracle_rules_adapter_v2 import apply_main_action, rules_decision_request
from non_oracle_runtime import make_runtime_state


def request(runtime):
    return rules_decision_request(
        runtime,horizon=6,policy_id="spellseeker-cam-line-smoke"
    )


def action(runtime,*,kind,label_contains="",target=""):
    rows=[a for a in request(runtime).actions if a.kind==kind]
    if label_contains:
        rows=[a for a in rows if label_contains in a.label]
    if target:
        rows=[
            a for a in rows
            if dict(a.parameters).get("target")==target
        ]
    if not rows:
        raise AssertionError(
            f"no action kind={kind!r} label={label_contains!r} target={target!r}; "
            f"available={[a.label for a in request(runtime).actions]!r}"
        )
    return sorted(rows,key=lambda a:a.action_id)[0]


def pass_priority(runtime):
    return apply_main_action(runtime,action(runtime,kind="pass_priority"))


def spellseeker_for(runtime,target):
    runtime=apply_main_action(
        runtime,
        action(runtime,kind="main_use_simple_tutor",label_contains="Spellseeker"),
    )
    runtime=pass_priority(runtime)  # Spellseeker spell resolves; ETB queued.
    runtime=pass_priority(runtime)  # ETB resolves; search target becomes visible.
    runtime=apply_main_action(
        runtime,
        action(runtime,kind="choose_tutor_target",target=target),
    )
    return runtime


def run_line(knack):
    runtime=make_runtime_state(solver.State(
        turn=4,
        library=(knack,"Transmute Artifact","Sewer-veillance Cam","Island"),
        hand=("Spellseeker",),
        battlefield=(
            solver.Perm(solver.COMMANDER,sick=False),
            solver.Perm("Sol Ring"),
        ),
        blue=20,
        urza=True,
        commander_in_command_zone=False,
        rng_root_seed=20260826,
    ))

    # First Spellseeker finds the one-mana bounce-grant spell.
    runtime=spellseeker_for(runtime,knack)
    assert knack in runtime.true_state.hand

    # Use a different, already-ready creature as the Knack/Helix source.
    runtime=apply_main_action(
        runtime,
        action(
            runtime,
            kind="main_cast_proactive_nonartifact",
            label_contains=f"{knack} -> {solver.COMMANDER}",
        ),
    )
    runtime=pass_priority(runtime)
    urza=next(
        p for p in runtime.true_state.battlefield if p.name==solver.COMMANDER
    )
    assert urza.knack_granted and not urza.tapped and not urza.sick

    # The persistent grant source bounces Spellseeker; Spellseeker itself is not
    # used as the source because it would lose the granted ability on zone change.
    runtime=apply_main_action(
        runtime,
        action(
            runtime,
            kind="main_activate_knack_bounce",
            label_contains="bounce Spellseeker",
        ),
    )
    urza=next(
        p for p in runtime.true_state.battlefield if p.name==solver.COMMANDER
    )
    assert urza.tapped and urza.knack_granted
    assert "Spellseeker" in runtime.true_state.hand

    # Replay Spellseeker, this time finding Transmute Artifact.
    runtime=spellseeker_for(runtime,"Transmute Artifact")
    assert "Transmute Artifact" in runtime.true_state.hand

    # Transmute the visible MV1 Sol Ring into MV1 Cam; no difference payment.
    runtime=apply_main_action(
        runtime,
        action(runtime,kind="main_use_transmute_artifact"),
    )
    runtime=pass_priority(runtime)
    runtime=apply_main_action(
        runtime,
        action(
            runtime,
            kind="transmute_choose_sacrifice",
            label_contains="Sol Ring",
        ),
    )
    runtime=apply_main_action(
        runtime,
        action(
            runtime,
            kind="transmute_choose_target",
            target="Sewer-veillance Cam",
        ),
    )
    assert any(
        p.name=="Sewer-veillance Cam" for p in runtime.true_state.battlefield
    )
    assert runtime.pending is not None
    assert runtime.pending.kind==DECISION_CAM_TARGET

    # Cam sees the tapped persistent Knack/Helix source and untaps it.
    runtime=apply_main_action(
        runtime,
        action(
            runtime,
            kind=DECISION_CAM_TARGET,
            label_contains=solver.COMMANDER,
        ),
    )
    runtime=pass_priority(runtime)
    assert runtime.pending is not None
    assert runtime.pending.kind==DECISION_CAM_EFFECT
    runtime=apply_main_action(
        runtime,
        action(
            runtime,
            kind=DECISION_CAM_EFFECT,
            label_contains=f"untap {solver.COMMANDER}",
        ),
    )

    assert runtime.true_state.won
    assert runtime.true_state.win_family=="Knack/Helix + Cam"
    return runtime


def main():
    for knack in ("Banishing Knack","Retraction Helix"):
        run_line(knack)
        print(f"Spellseeker -> {knack} -> Transmute -> Cam: PASS")
    print("PHASE5 SPELLSEEKER CAM LINE SMOKE: ALL PASS")


if __name__=="__main__":
    main()
