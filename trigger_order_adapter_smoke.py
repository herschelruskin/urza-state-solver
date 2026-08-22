#!/usr/bin/env python3
"""Focused regressions for controlled cast-trigger ordering."""

import urza_solver as solver
from solver_architecture import InformationState
from trigger_order_adapter import (
    PendingTrigger,
    PendingTriggerStack,
    collect_controlled_cast_triggers,
    information_before_trigger_order,
    resolve_trigger_order,
    trigger_order_intents,
    trigger_order_request,
)


def trigger_state(top):
    return solver.State(
        turn=3,
        library=(top, "Tail"),
        battlefield=(
            solver.Perm("Fortune Teller's Talent"),
            solver.Perm("Artificer's Assistant"),
            solver.Perm("Uthros Research Craft"),
            solver.Perm("Forensic Gadgeteer"),
            solver.Perm("Valley Floodcaller"),
            solver.Perm("Vexing Bauble"),
        ),
        ftt_level=1,
        uthros_counters=3,
        spell_cast_this_turn=True,
    )


def first_kind(batch, action):
    by_id = {trigger.trigger_id: trigger for trigger in batch.triggers}
    first_id = tuple(dict(action.parameters)["resolution_order"])[0]
    return by_id[first_id].kind


def choose_first_kind(batch, request, kind):
    return next(action for action in request.actions if first_kind(batch, action) == kind)


def test_cast_from_top_exposes_new_top_before_trigger_order_choice():
    # Before casting Mana Vault from top, the legally known prefix includes it and
    # the deeper card. Once casting completes, Mana Vault is consumed and FTT may
    # immediately look at the newly exposed Winner before triggers are ordered.
    prior = InformationState(known_top=("Mana Vault", "Winner"))
    after_cast = trigger_state("Winner")
    info = information_before_trigger_order(
        prior,
        after_cast,
        "Mana Vault",
        cast_from_library_top=True,
    )
    assert info.known_top == ("Winner",)


def test_all_current_simultaneous_artifact_cast_triggers_are_collected():
    state = trigger_state("Winner")
    batch = collect_controlled_cast_triggers(state, "Mana Vault", mana_spent=0)
    kinds = {trigger.kind for trigger in batch.triggers}
    assert kinds == {
        "vfc_noncreature_cast",
        "assistant_scry_1",
        "uthros_draw_and_counter",
        "gadgeteer_investigate",
        "vexing_bauble_counter",
    }


def test_trigger_actions_are_same_but_policy_choice_can_use_legally_known_top():
    winner_state = trigger_state("Winner")
    blank_state = trigger_state("Blank")
    winner_batch = collect_controlled_cast_triggers(winner_state, "Mana Vault", mana_spent=0)
    blank_batch = collect_controlled_cast_triggers(blank_state, "Mana Vault", mana_spent=0)
    assert tuple(trigger.strategic_key() for trigger in winner_batch.triggers) == tuple(
        trigger.strategic_key() for trigger in blank_batch.triggers
    )

    winner_info = information_before_trigger_order(
        InformationState(), winner_state, "Mana Vault"
    )
    blank_info = information_before_trigger_order(
        InformationState(), blank_state, "Mana Vault"
    )
    assert winner_info.known_top == ("Winner",)
    assert blank_info.known_top == ("Blank",)

    winner_req = trigger_order_request(winner_state, winner_info, winner_batch, horizon=6)
    blank_req = trigger_order_request(blank_state, blank_info, blank_batch, horizon=6)
    assert tuple(action.strategic_key() for action in winner_req.actions) == tuple(
        action.strategic_key() for action in blank_req.actions
    )

    # A tiny policy example: draw a known winner first; otherwise scry first.
    winner_choice = choose_first_kind(
        winner_batch, winner_req, "uthros_draw_and_counter"
    )
    blank_choice = choose_first_kind(blank_batch, blank_req, "assistant_scry_1")
    assert first_kind(winner_batch, winner_choice) != first_kind(blank_batch, blank_choice)


def test_bauble_can_be_ordered_to_resolve_after_value_triggers():
    state = trigger_state("Winner")
    batch = collect_controlled_cast_triggers(state, "Mana Vault", mana_spent=0)
    actions = trigger_order_intents(batch)
    by_id = {trigger.trigger_id: trigger for trigger in batch.triggers}
    found = False
    for action in actions:
        order = tuple(dict(action.parameters)["resolution_order"])
        kinds = tuple(by_id[trigger_id].kind for trigger_id in order)
        if kinds[-1] == "vexing_bauble_counter" and kinds[0] != "vexing_bauble_counter":
            found = True
            break
    assert found, "no ordering lets our value triggers resolve before Bauble counter"


def test_duplicate_trigger_copies_are_collapsed_by_strategic_order():
    state = solver.State(
        turn=3,
        library=("Top",),
        battlefield=(
            solver.Perm("Artificer's Assistant"),
            solver.Perm("Forensic Gadgeteer"),
            solver.Perm("Forensic Gadgeteer", mode="chrome_copy"),
        ),
    )
    batch = collect_controlled_cast_triggers(state, "Mana Vault", mana_spent=1)
    kinds = [trigger.kind for trigger in batch.triggers]
    assert kinds.count("gadgeteer_investigate") == 2
    # Three triggers with two strategically identical Gadgeteer copies have only
    # three distinct strategic resolution orders, not 3! = 6.
    assert len(trigger_order_intents(batch)) == 3


def test_pending_trigger_stack_is_order_sensitive_and_new_triggers_go_above_old_ones():
    assistant = PendingTrigger("a", "assistant_scry_1", "Artificer's Assistant")
    uthros = PendingTrigger("u", "uthros_draw_and_counter", "Uthros Research Craft")
    station = PendingTrigger("s", "station_untap", "Grinding Station")

    stack = PendingTriggerStack((assistant, uthros))
    reversed_stack = PendingTriggerStack((uthros, assistant))
    assert stack.strategic_key() != reversed_stack.strategic_key()

    expanded = stack.push_above((station,))
    assert expanded.next_trigger() == station
    popped, remaining = expanded.pop_next()
    assert popped == station
    assert remaining.triggers == (assistant, uthros)


def test_resolve_trigger_order_builds_top_first_pending_stack():
    state = trigger_state("Winner")
    batch = collect_controlled_cast_triggers(state, "Mana Vault", mana_spent=0)
    req = trigger_order_request(
        state,
        information_before_trigger_order(InformationState(), state, "Mana Vault"),
        batch,
        horizon=6,
    )
    choice = choose_first_kind(batch, req, "assistant_scry_1")
    resolved = resolve_trigger_order(batch, choice)
    assert resolved.stack.next_trigger().kind == "assistant_scry_1"


def main():
    tests = (
        test_cast_from_top_exposes_new_top_before_trigger_order_choice,
        test_all_current_simultaneous_artifact_cast_triggers_are_collected,
        test_trigger_actions_are_same_but_policy_choice_can_use_legally_known_top,
        test_bauble_can_be_ordered_to_resolve_after_value_triggers,
        test_duplicate_trigger_copies_are_collapsed_by_strategic_order,
        test_pending_trigger_stack_is_order_sensitive_and_new_triggers_go_above_old_ones,
        test_resolve_trigger_order_builds_top_first_pending_stack,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("TRIGGER ORDER ADAPTER SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
