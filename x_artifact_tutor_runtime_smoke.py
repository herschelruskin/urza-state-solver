#!/usr/bin/env python3
"""Focused Phase-2 smokes for Reshape/Whir runtime integration."""

import urza_solver as solver
from non_oracle_base_policy import DeterministicBasePolicy
from non_oracle_cam_runtime import DECISION_CAM_TARGET
from non_oracle_rules_adapter import apply_main_action, rules_decision_request
from non_oracle_runtime import ACTION_PASS_PRIORITY, make_runtime_state
from non_oracle_x_artifact_tutor_runtime import MAIN_USE_X_ARTIFACT_TUTOR


def x_actions(runtime, source=None, x=None):
    rows = [
        action for action in rules_decision_request(runtime, horizon=6).actions
        if action.kind == MAIN_USE_X_ARTIFACT_TUTOR
    ]
    if source is not None:
        rows = [a for a in rows if dict(a.parameters).get("source") == source]
    if x is not None:
        rows = [a for a in rows if int(dict(a.parameters).get("x", -1)) == int(x)]
    return rows


def pass_action(runtime):
    return next(
        action for action in rules_decision_request(runtime, horizon=6).actions
        if action.action_id == ACTION_PASS_PRIORITY
    )


def commit_reshape(runtime, x, sacrifice_name=None):
    """Commit X, then the additional-cost sacrifice, without an observation gap."""
    roots=x_actions(runtime,"Reshape",x)
    assert len(roots)==1, (x,len(roots))
    runtime=apply_main_action(runtime,roots[0])
    assert runtime.pending is not None
    assert runtime.pending.kind=="runtime_reshape_sacrifice"
    request=rules_decision_request(runtime,horizon=6)
    assert request.actions
    assert all(action.kind=="reshape_choose_sacrifice" for action in request.actions)
    if sacrifice_name is None:
        chosen=request.actions[0]
    else:
        chosen=next(
            action for action in request.actions
            if dict(action.parameters).get("sacrifice_name")==sacrifice_name
        )
    return apply_main_action(runtime,chosen)


def finish_whir_payment(runtime, *, maximize_improvise=False):
    """Advance only the pre-search Whir payment DAG until the spell is on stack."""
    while runtime.pending is not None and runtime.pending.kind == "runtime_whir_payment":
        request = rules_decision_request(runtime, horizon=6)
        add = tuple(
            action for action in request.actions
            if action.kind == "whir_payment_add_improvise"
        )
        finish = tuple(
            action for action in request.actions
            if action.kind == "whir_payment_finish"
        )
        if maximize_improvise and add:
            chosen = add[0]
        elif finish:
            chosen = finish[0]
        elif add:
            chosen = add[0]
        else:
            raise AssertionError("Whir payment DAG has no continuation")
        runtime = apply_main_action(runtime, chosen)
    return runtime


def test_cast_commit_actions_are_hidden_future_invariant():
    left = make_runtime_state(solver.State(
        turn=3,
        library=("Basalt Monolith", "Sensei's Divining Top", "Island"),
        hand=("Reshape", "Whir of Invention"),
        battlefield=(solver.Perm("Prized Statue"), solver.Perm("Sol Ring")),
        blue=5,
        colorless=3,
    ))
    right = make_runtime_state(solver.State(
        turn=3,
        library=("Island", "Sensei's Divining Top", "Basalt Monolith"),
        hand=("Reshape", "Whir of Invention"),
        battlefield=(solver.Perm("Prized Statue"), solver.Perm("Sol Ring")),
        blue=5,
        colorless=3,
    ))
    la = x_actions(left)
    ra = x_actions(right)
    assert tuple(a.strategic_key() for a in la) == tuple(a.strategic_key() for a in ra)
    text = repr(la)
    assert "Basalt Monolith" not in text
    assert "Sensei's Divining Top" not in text


def test_runtime_reshape_sacrifice_survives_payment_annotation_change():
    runtime = make_runtime_state(solver.State(
        turn=3,
        library=("Mana Vault", "Island"),
        hand=("Reshape",),
        battlefield=(
            solver.Perm(
                "Grinding Station", tapped=True, producer_urza_ready=True
            ),
        ),
        blue=2,
        colorless=0,
    ))
    runtime = commit_reshape(runtime,0,"Grinding Station")
    assert not any(p.name == "Grinding Station" for p in runtime.true_state.battlefield)
    assert runtime.stack.top().kind == "x_artifact_reshape_spell"


def test_reshape_prized_statue_dies_trigger_is_above_spell():
    runtime = make_runtime_state(solver.State(
        turn=3,
        library=("Basalt Monolith", "Island"),
        hand=("Reshape",),
        battlefield=(solver.Perm("Prized Statue"),),
        blue=2,
        colorless=3,
    ))
    runtime = commit_reshape(runtime,3,"Prized Statue")
    assert "Reshape" not in runtime.true_state.hand
    assert not any(p.name == "Prized Statue" for p in runtime.true_state.battlefield)
    assert "Reshape" not in runtime.true_state.graveyard
    assert [obj.kind for obj in runtime.stack.objects] == [
        "prized_dies_treasure", "x_artifact_reshape_spell"
    ]

    runtime = apply_main_action(runtime, pass_action(runtime))
    assert any(p.mode == "treasure" for p in runtime.true_state.battlefield)
    assert runtime.stack.top().kind == "x_artifact_reshape_spell"


def test_reshape_cast_and_statue_death_trigger_are_orderable_with_other_cast_trigger():
    runtime = make_runtime_state(solver.State(
        turn=3,
        library=("Basalt Monolith", "Island"),
        hand=("Reshape",),
        battlefield=(solver.Perm("Prized Statue"), solver.Perm("Valley Floodcaller")),
        blue=2,
        colorless=3,
    ))
    runtime = commit_reshape(runtime,3,"Prized Statue")
    request = rules_decision_request(runtime, horizon=6)
    assert request.actions and all(a.kind == "runtime_stack_order" for a in request.actions)
    labels = "\n".join(a.label for a in request.actions)
    assert "vfc_noncreature_cast" in labels
    assert "prized_dies_treasure" in labels
    assert runtime.stack.top().kind == "x_artifact_reshape_spell"


def test_reshape_cam_additional_cost_stages_target_before_trigger_order():
    runtime = make_runtime_state(solver.State(
        turn=3,
        library=("Sol Ring", "Island"),
        hand=("Reshape",),
        battlefield=(
            solver.Perm("Sewer-veillance Cam"),
            solver.Perm("Valley Floodcaller"),
            solver.Perm("Faerie Mastermind"),
        ),
        blue=2,
        colorless=2,
    ))
    runtime = commit_reshape(runtime,0,"Sewer-veillance Cam")
    assert not any(p.name == "Sewer-veillance Cam" for p in runtime.true_state.battlefield)
    assert runtime.stack.objects and runtime.stack.objects[-1].kind == "x_artifact_reshape_spell"
    assert runtime.pending is not None and runtime.pending.kind == DECISION_CAM_TARGET
    request = rules_decision_request(runtime, horizon=6)
    assert request.actions and all(a.kind == DECISION_CAM_TARGET for a in request.actions)
    target = next(
        a for a in request.actions
        if tuple(dict(a.parameters)["target_signature"])[0] == "Faerie Mastermind"
    )
    runtime = apply_main_action(runtime, target)
    # Floodcaller cast trigger and the now-targeted Cam LTB must be ordered only
    # after the Cam target has been committed.
    request = rules_decision_request(runtime, horizon=6)
    assert request.actions and all(a.kind == "runtime_stack_order" for a in request.actions)
    labels = "\n".join(a.label for a in request.actions)
    assert "vfc_noncreature_cast" in labels
    assert "ltb_cam" in labels


def test_reshape_search_targets_appear_only_when_spell_resolves():
    runtime = make_runtime_state(solver.State(
        turn=3,
        library=("Basalt Monolith", "Sensei's Divining Top", "Island"),
        hand=("Reshape",),
        battlefield=(solver.Perm("Sol Ring"),),
        blue=2,
        colorless=3,
        rng_root_seed=99,
    ))
    runtime = apply_main_action(runtime,x_actions(runtime,"Reshape",3)[0])
    assert runtime.pending is not None
    assert runtime.pending.kind=="runtime_reshape_sacrifice"
    assert "Basalt Monolith" not in repr(rules_decision_request(runtime,horizon=6).actions)
    runtime = apply_main_action(
        runtime,
        rules_decision_request(runtime,horizon=6).actions[0],
    )
    assert runtime.pending is None
    assert "Basalt Monolith" not in repr(rules_decision_request(runtime, horizon=6).actions)

    runtime = apply_main_action(runtime, pass_action(runtime))
    request = rules_decision_request(runtime, horizon=6)
    assert request.actions and all(a.kind == "x_artifact_search_target" for a in request.actions)
    targets = {dict(a.parameters).get("target") for a in request.actions}
    assert "Basalt Monolith" in targets
    assert "Sensei's Divining Top" in targets
    assert "Island" not in targets

    target = next(a for a in request.actions if dict(a.parameters).get("target") == "Basalt Monolith")
    runtime = apply_main_action(runtime, target)
    assert any(p.name == "Basalt Monolith" for p in runtime.true_state.battlefield)
    assert "Reshape" in runtime.true_state.graveyard
    assert "Basalt Monolith" not in runtime.true_state.library
    assert runtime.information.known_top == ()


def test_cage_filters_creature_targets_from_reshape_and_whir():
    reshape = make_runtime_state(solver.State(
        turn=3,
        library=("Hope of Ghirapur", "Sol Ring", "Island"),
        hand=("Reshape",),
        battlefield=(solver.Perm("Grafdigger's Cage"), solver.Perm("Tormod's Crypt")),
        blue=2,
        colorless=1,
    ))
    reshape = commit_reshape(reshape,1,"Tormod's Crypt")
    reshape = apply_main_action(reshape, pass_action(reshape))
    targets = {
        dict(a.parameters).get("target")
        for a in rules_decision_request(reshape, horizon=6).actions
    }
    assert "Sol Ring" in targets
    assert "Hope of Ghirapur" not in targets

    whir = make_runtime_state(solver.State(
        turn=3,
        library=("Hope of Ghirapur", "Sol Ring", "Island"),
        hand=("Whir of Invention",),
        battlefield=(solver.Perm("Grafdigger's Cage", tapped=True),),
        blue=3,
        colorless=1,
    ))
    action = x_actions(whir, "Whir of Invention", 1)[0]
    whir = apply_main_action(whir, action)
    whir = finish_whir_payment(whir)
    whir = apply_main_action(whir, pass_action(whir))
    targets = {
        dict(a.parameters).get("target")
        for a in rules_decision_request(whir, horizon=6).actions
    }
    assert "Sol Ring" in targets
    assert "Hope of Ghirapur" not in targets


def test_whir_commits_x_and_improvise_before_search():
    runtime = make_runtime_state(solver.State(
        turn=3,
        library=("Basalt Monolith", "Grim Monolith", "Sensei's Divining Top", "Island"),
        hand=("Whir of Invention",),
        battlefield=(solver.Perm("Sol Ring"), solver.Perm("Mana Vault")),
        blue=3,
        colorless=0,
    ))
    candidates = x_actions(runtime, "Whir of Invention", 2)
    assert len(candidates) == 1
    runtime = apply_main_action(runtime, candidates[0])
    assert runtime.pending is not None
    assert runtime.pending.kind == "runtime_whir_payment"
    # No search target is visible while payment is still being committed.
    assert "Grim Monolith" not in repr(rules_decision_request(runtime, horizon=6).actions)
    runtime = finish_whir_payment(runtime, maximize_improvise=True)
    assert all(p.tapped for p in runtime.true_state.battlefield)
    assert runtime.stack.top().kind == "x_artifact_whir_spell"
    assert runtime.pending is None

    runtime = apply_main_action(runtime, pass_action(runtime))
    request = rules_decision_request(runtime, horizon=6)
    targets = {dict(a.parameters).get("target") for a in request.actions}
    assert "Grim Monolith" in targets
    assert "Sensei's Divining Top" in targets
    assert "Basalt Monolith" not in targets


def test_runtime_whir_duplicate_improvise_slots_survive_first_tap():
    runtime = make_runtime_state(solver.State(
        turn=3,
        library=("Grim Monolith", "Island"),
        hand=("Whir of Invention",),
        battlefield=(
            solver.Perm("Clue", mode="clue"),
            solver.Perm("Clue", mode="clue"),
        ),
        blue=3,
        colorless=0,
    ))
    actions = x_actions(runtime, "Whir of Invention", 2)
    assert len(actions) == 1
    runtime = apply_main_action(runtime, actions[0])
    runtime = finish_whir_payment(runtime, maximize_improvise=True)
    assert len(runtime.true_state.battlefield) == 2
    assert all(p.tapped for p in runtime.true_state.battlefield)
    assert runtime.stack.top().kind == "x_artifact_whir_spell"


def test_base_policy_chooses_revealed_artifact_not_fail_to_find():
    runtime = make_runtime_state(solver.State(
        turn=3,
        library=("Basalt Monolith", "Sensei's Divining Top", "Island"),
        hand=("Reshape",),
        battlefield=(solver.Perm("Sol Ring"),),
        blue=2,
        colorless=3,
    ))
    runtime = commit_reshape(runtime,3)
    runtime = apply_main_action(runtime, pass_action(runtime))
    request = rules_decision_request(runtime, horizon=6)
    chosen = DeterministicBasePolicy().choose_request(request)
    assert dict(chosen.parameters).get("target") in {"Basalt Monolith", "Sensei's Divining Top"}


def main():
    tests = (
        test_cast_commit_actions_are_hidden_future_invariant,
        test_runtime_reshape_sacrifice_survives_payment_annotation_change,
        test_reshape_prized_statue_dies_trigger_is_above_spell,
        test_reshape_cast_and_statue_death_trigger_are_orderable_with_other_cast_trigger,
        test_reshape_cam_additional_cost_stages_target_before_trigger_order,
        test_reshape_search_targets_appear_only_when_spell_resolves,
        test_cage_filters_creature_targets_from_reshape_and_whir,
        test_whir_commits_x_and_improvise_before_search,
        test_runtime_whir_duplicate_improvise_slots_survive_first_tap,
        test_base_policy_chooses_revealed_artifact_not_fail_to_find,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("X ARTIFACT TUTOR RUNTIME SMOKE: ALL PASS")


if __name__ == "__main__":
    main()