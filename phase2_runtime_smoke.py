#!/usr/bin/env python3
"""Focused acceptance smokes for the first Phase-2 runtime slice."""

from dataclasses import replace

import urza_solver as solver
from non_oracle_runtime import (
    ACTION_PASS_PRIORITY,
    NonOracleRuntimeState,
    RuntimeStack,
    RuntimeStackObject,
    add_artifact_tokens,
    apply_runtime_action,
    begin_committed_artifact_cast,
    make_runtime_state,
    record_artifact_entry,
    runtime_decision_request,
    sacrifice_permanent,
)
from solver_architecture import InformationState


def choose_label(request, text):
    return next(action for action in request.actions if text in action.label)


def pass_action(runtime):
    request = runtime_decision_request(runtime, horizon=6)
    assert len(request.actions) == 1
    assert request.actions[0].action_id == ACTION_PASS_PRIORITY
    return request.actions[0]


def count_bf(state, name):
    return sum(1 for perm in state.battlefield if perm.name == name)


def test_runtime_root_has_single_nonoracle_authority_and_safe_view():
    state = solver.State(
        turn=1,
        library=("SECRET_A", "SECRET_B"),
        hand=("Island",),
        battlefield=(solver.Perm("Grinding Station", tapped=True),),
        rng_root_seed=20260822,
    )
    runtime = make_runtime_state(state)
    assert runtime.true_state.oracle_stack == ()
    assert runtime.true_state.urza_exile_permissions == ()
    view = runtime.policy_view()
    assert not hasattr(view, "true_state")
    assert not hasattr(view.base, "library")
    assert not hasattr(view.base, "rng_root_seed")
    assert "SECRET_A" not in repr(view)
    assert "SECRET_B" not in repr(view)


def test_same_public_entry_decision_is_hidden_future_invariant():
    battlefield = (
        solver.Perm("Grinding Station", tapped=True),
        solver.Perm("Prized Statue"),
    )
    left = make_runtime_state(
        solver.State(turn=2, library=("Alpha", "Beta", "Gamma"), hand=(), battlefield=battlefield)
    )
    right = make_runtime_state(
        solver.State(turn=2, library=("Gamma", "Alpha", "Beta"), hand=(), battlefield=battlefield)
    )
    left = record_artifact_entry(left, ("Prized Statue",), source="fixture")
    right = record_artifact_entry(right, ("Prized Statue",), source="fixture")
    lreq = runtime_decision_request(left, horizon=6)
    rreq = runtime_decision_request(right, horizon=6)
    assert lreq.observation.key() == rreq.observation.key()
    assert tuple(a.strategic_key() for a in lreq.actions) == tuple(
        a.strategic_key() for a in rreq.actions
    )
    assert len(lreq.actions) == 2


def test_prized_statue_entry_then_treasure_is_two_nested_producer_waves():
    runtime = make_runtime_state(
        solver.State(
            turn=2,
            library=("Island",),
            hand=(),
            battlefield=(
                solver.Perm("Grinding Station", tapped=True),
                solver.Perm("Prized Statue"),
            ),
        )
    )
    runtime = record_artifact_entry(runtime, ("Prized Statue",), source="Statue enters")
    request = runtime_decision_request(runtime, horizon=6)
    order = choose_label(request, "prized_entry_treasure -> etb_producer")
    runtime = apply_runtime_action(runtime, order)
    assert [obj.kind for obj in runtime.stack.objects] == [
        "prized_entry_treasure",
        "etb_producer",
    ]

    # Resolve Statue's own Treasure trigger.  The Treasure is a later artifact
    # entry event, so its Station trigger goes ABOVE the older Statue-entry
    # Station trigger rather than being bundled with it.
    runtime = apply_runtime_action(runtime, pass_action(runtime))
    assert count_bf(runtime.true_state, "Treasure") == 1
    assert [obj.kind for obj in runtime.stack.objects] == [
        "etb_producer",
        "etb_producer",
    ]


def test_prized_statue_dies_from_sacrifice_then_treasure_triggers_producer():
    runtime = make_runtime_state(
        solver.State(
            turn=3,
            library=("Island",),
            hand=(),
            battlefield=(
                solver.Perm("Grinding Station", tapped=True),
                solver.Perm("Prized Statue"),
            ),
        )
    )
    statue = next(p for p in runtime.true_state.battlefield if p.name == "Prized Statue")
    runtime = sacrifice_permanent(
        runtime,
        instance_tag=statue.instance_tag,
        source="Reshape fixture",
    )
    assert "Prized Statue" in runtime.true_state.graveyard
    assert count_bf(runtime.true_state, "Prized Statue") == 0
    assert runtime.stack.top().kind == "prized_dies_treasure"

    runtime = apply_runtime_action(runtime, pass_action(runtime))
    assert count_bf(runtime.true_state, "Treasure") == 1
    assert runtime.stack.top().kind == "etb_producer"


def test_offer_two_treasures_is_one_event_two_triggers_per_producer():
    runtime = make_runtime_state(
        solver.State(
            turn=3,
            library=(),
            hand=(),
            battlefield=(
                solver.Perm("Grinding Station", tapped=True),
                solver.Perm("Battered Golem", tapped=True, sick=False),
            ),
        )
    )
    runtime = add_artifact_tokens(
        runtime,
        ("Treasure", "Treasure"),
        modes=("treasure", "treasure"),
        source="Offer fixture",
    )
    pending = dict(runtime.pending.payload)["objects"]
    kinds = [obj.source for obj in pending]
    assert kinds.count("Grinding Station") == 2
    assert kinds.count("Battered Golem") == 2
    # 4 triggers with multiplicities 2+2 -> 4!/(2!*2!) = 6 strategic orders.
    request = runtime_decision_request(runtime, horizon=6)
    assert len(request.actions) == 6
    assert count_bf(runtime.true_state, "Treasure") == 2


def test_scry_trigger_reveals_only_after_priority_pass_then_choices_use_reveal():
    runtime = make_runtime_state(
        solver.State(
            turn=2,
            library=("Good", "Bad", "HIDDEN_THIRD"),
            hand=(),
            battlefield=(solver.Perm("Witching Well"),),
        ),
        InformationState(),
    )
    runtime = record_artifact_entry(runtime, ("Witching Well",), source="Well enters")
    before = runtime_decision_request(runtime, horizon=6)
    assert before.actions[0].action_id == ACTION_PASS_PRIORITY
    assert before.observation.base.known_top == ()
    assert "HIDDEN_THIRD" not in repr(before.observation)

    runtime = apply_runtime_action(runtime, before.actions[0])
    assert runtime.pending is not None
    assert runtime.information.known_top[:2] == ("Good", "Bad")
    request = runtime_decision_request(runtime, horizon=6)
    assert request.actions
    assert all("HIDDEN_THIRD" not in action.label for action in request.actions)
    keep_good = next(
        action for action in request.actions
        if dict(action.parameters)["top"] == ("Good",)
        and dict(action.parameters)["bottom"] == ("Bad",)
    )
    runtime = apply_runtime_action(runtime, keep_good)
    assert runtime.true_state.library == ("Good", "HIDDEN_THIRD", "Bad")
    assert runtime.information.known_top == ("Good",)


def test_committed_artifact_cast_uses_real_trigger_stack_and_observations():
    runtime = make_runtime_state(
        solver.State(
            turn=3,
            library=("DrawMe", "ScryMe", "Tail"),
            hand=("Welding Jar",),
            battlefield=(
                solver.Perm("Artificer's Assistant"),
                solver.Perm("Uthros Research Craft"),
            ),
            uthros_counters=3,
        )
    )
    runtime = begin_committed_artifact_cast(
        runtime,
        "Welding Jar",
        mana_spent=0,
        from_zone="hand",
    )
    request = runtime_decision_request(runtime, horizon=6)
    assert len(request.actions) == 2
    uthros_first = choose_label(request, "uthros_draw_and_counter -> assistant_scry_1")
    runtime = apply_runtime_action(runtime, uthros_first)
    assert [obj.kind for obj in runtime.stack.objects] == [
        "uthros_draw_and_counter",
        "assistant_scry_1",
        "artifact_spell",
    ]

    runtime = apply_runtime_action(runtime, pass_action(runtime))
    assert "DrawMe" in runtime.true_state.hand
    assert runtime.true_state.uthros_counters == 4
    # Assistant remains pending and therefore can make its scry choice using the
    # now-current top, rather than a clairvoyant pre-cast decision.
    assert runtime.stack.top().kind == "assistant_scry_1"
    runtime = apply_runtime_action(runtime, pass_action(runtime))
    assert runtime.pending is not None
    assert runtime.information.known_top[0] == "ScryMe"


def test_runtime_value_identity_ignores_stack_ids_but_keeps_order():
    base = make_runtime_state(
        solver.State(turn=2, library=("X",), hand=(), battlefield=())
    )
    a1 = RuntimeStackObject("a:1", "trigger", "k1", "S1")
    a2 = RuntimeStackObject("a:2", "trigger", "k2", "S2")
    b1 = RuntimeStackObject("b:91", "trigger", "k1", "S1")
    b2 = RuntimeStackObject("b:92", "trigger", "k2", "S2")
    left = replace(base, stack=RuntimeStack((a1, a2), 3))
    same = replace(base, stack=RuntimeStack((b1, b2), 99))
    reversed_state = replace(base, stack=RuntimeStack((b2, b1), 99))
    assert left.value_key() == same.value_key()
    assert left.value_key() != reversed_state.value_key()


def main():
    tests = (
        test_runtime_root_has_single_nonoracle_authority_and_safe_view,
        test_same_public_entry_decision_is_hidden_future_invariant,
        test_prized_statue_entry_then_treasure_is_two_nested_producer_waves,
        test_prized_statue_dies_from_sacrifice_then_treasure_triggers_producer,
        test_offer_two_treasures_is_one_event_two_triggers_per_producer,
        test_scry_trigger_reveals_only_after_priority_pass_then_choices_use_reveal,
        test_committed_artifact_cast_uses_real_trigger_stack_and_observations,
        test_runtime_value_identity_ignores_stack_ids_but_keeps_order,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("PHASE 2 RUNTIME KERNEL SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
