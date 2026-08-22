#!/usr/bin/env python3
"""Focused legal-information propagation regressions."""

from solver_architecture import InformationState
from information_state_propagation import (
    initial_information,
    propagate_information,
    validate_information_against_state,
)
import urza_solver as solver


def traced(actions, prefix):
    return next(
        action for action in actions
        if action.trace and action.trace[-1].splitlines()[0].startswith(prefix)
    )


def test_initial_state_does_not_leak_hidden_top():
    state = solver.State(
        turn=1,
        library=("Island", "Sol Ring", "Force of Will"),
        hand=(),
        battlefield=(),
    )
    info = initial_information(state)
    assert info.known_top == ()
    assert info.known_bottom == ()


def test_continuous_chip_and_ftt_reveal_only_current_top():
    chip = solver.State(
        turn=2,
        library=("Sol Ring", "Island"),
        hand=(),
        battlefield=(),
        chip_attached=True,
    )
    assert initial_information(chip).known_top == ("Sol Ring",)

    ftt = solver.State(
        turn=2,
        library=("Mana Vault", "Island"),
        hand=(),
        battlefield=(),
        ftt_level=2,
        spell_cast_this_turn=True,
    )
    assert initial_information(ftt).known_top == ("Mana Vault",)


def test_known_prefix_is_consumed_by_draw():
    before = solver.State(
        turn=2,
        library=("Island", "Sol Ring", "Force of Will"),
        hand=(),
        battlefield=(),
    )
    prior = InformationState(known_top=("Island", "Sol Ring"))
    after, drawn = solver.draw_from_library(before, 1)
    assert drawn == ("Island",)
    info = propagate_information(before, after, prior)
    assert info.known_top == ("Sol Ring",)


def test_continuous_visibility_refreshes_after_draw():
    before = solver.State(
        turn=2,
        library=("Island", "Sol Ring", "Force of Will"),
        hand=(),
        battlefield=(),
        chip_attached=True,
    )
    prior = initial_information(before)
    after, drawn = solver.draw_from_library(before, 1)
    assert drawn == ("Island",)
    info = propagate_information(before, after, prior)
    assert info.known_top == ("Sol Ring",)


def test_scry_records_kept_top_and_bottom():
    before = solver.State(
        turn=2,
        library=("Island", "Chrome Dome", "Force of Will", "Tail"),
        hand=(),
        battlefield=(),
    )
    after = solver.apply_scry(before, 3, "test")
    info = propagate_information(before, after, InformationState())
    assert info.known_top == ("Chrome Dome", "Island")
    assert info.known_bottom == ("Force of Will",)
    validate_information_against_state(info, after)


def test_scry_parser_handles_comma_in_card_name():
    before = solver.State(
        turn=2,
        library=("Minamo, School at Water's Edge", "Force of Will", "Tail"),
        hand=(),
        battlefield=(),
    )
    after = solver.apply_scry(before, 2, "comma-card")
    info = propagate_information(before, after, InformationState())
    assert info.known_top == ("Minamo, School at Water's Edge",)
    assert info.known_bottom == ("Force of Will",)


def test_top_reorder_knows_chosen_top_three():
    before = solver.State(
        turn=2,
        library=("Island", "Sol Ring", "Force of Will", "Tail"),
        hand=(),
        battlefield=(solver.Perm("Sensei's Divining Top"),),
        colorless=1,
    )
    after = traced(solver.top_actions(before), "Top reorder")
    info = propagate_information(before, after, InformationState())
    assert info.known_top == after.library[:3]


def test_top_draw_places_known_top_and_preserves_deeper_memory():
    before = solver.State(
        turn=2,
        library=("Island", "Sol Ring", "Force of Will"),
        hand=(),
        battlefield=(solver.Perm("Sensei's Divining Top"),),
    )
    prior = InformationState(known_top=("Island", "Sol Ring"))
    after = traced(solver.top_actions(before), "Sensei's Divining Top -> draw:")
    info = propagate_information(before, after, prior)
    assert info.known_top == ("Sensei's Divining Top", "Sol Ring")


def test_mystical_tutor_clears_old_knowledge_then_sets_target_top():
    before = solver.State(
        turn=2,
        library=("Whir of Invention", "Island", "Power Artifact", "Force of Will"),
        hand=("Mystical Tutor",),
        battlefield=(),
        blue=1,
    )
    prior = InformationState(
        known_top=("Whir of Invention",),
        known_bottom=("Force of Will",),
        shuffle_epoch=4,
    )
    after = next(
        action for action in solver.simple_tutor_actions(before)
        if action.library and action.library[0] == "Whir of Invention"
    )
    info = propagate_information(before, after, prior)
    assert info.known_top == ("Whir of Invention",)
    assert info.known_bottom == ()
    assert info.shuffle_epoch == 5


def test_fetch_shuffle_invalidates_top_and_bottom():
    before = solver.State(
        turn=2,
        library=("Island", "Sol Ring", "Force of Will"),
        hand=(),
        battlefield=(solver.Perm("Flooded Strand"),),
    )
    prior = InformationState(
        known_top=("Island",),
        known_bottom=("Force of Will",),
        shuffle_epoch=2,
    )
    after = solver.fetch_actions(before)[0]
    info = propagate_information(before, after, prior)
    assert info.known_top == ()
    assert info.known_bottom == ()
    assert info.shuffle_epoch == 3


def test_bay_shuffle_then_etb_scry_retains_postshuffle_observation():
    before = solver.State(
        turn=3,
        library=(
            "Witching Well", "Power Artifact", "Sol Ring", "Island", "Force of Will"
        ),
        hand=(),
        battlefield=(
            solver.Perm("Repurposing Bay"),
            solver.Perm("Treasure", mode="treasure"),
        ),
        colorless=2,
        rng_root_seed=20260821,
    )
    actions = solver.repurposing_bay_actions(before)
    after = next(
        action for action in actions
        if action.trace[-1].splitlines()[0].endswith(" -> Witching Well")
    )
    info = propagate_information(before, after, InformationState())
    assert info.shuffle_epoch == 1
    assert info.known_top or info.known_bottom
    validate_information_against_state(info, after)


def test_urza_spin_shuffle_does_not_leave_random_top_known():
    before = solver.State(
        turn=3,
        library=("Island", "Sol Ring", "Force of Will", "Mana Vault"),
        hand=(),
        battlefield=(solver.Perm(solver.COMMANDER, sick=False),),
        colorless=5,
        urza=True,
        commander_in_command_zone=False,
        rng_root_seed=123,
    )
    prior = InformationState(
        known_top=("Island",),
        known_bottom=("Mana Vault",),
    )
    spins = [
        action for action in solver.special_actions(before)
        if action.trace and action.trace[-1].splitlines()[0].startswith("Urza spin -> ")
    ]
    assert spins
    after = spins[0]
    info = propagate_information(before, after, prior)
    assert info.shuffle_epoch == 1
    assert info.known_bottom == ()
    assert info.known_top == ()


def test_ordinary_action_does_not_reveal_hidden_library():
    before = solver.State(
        turn=2,
        library=("Force of Will", "Island"),
        hand=(),
        battlefield=(solver.Perm("Island"),),
    )
    after = solver.intrinsic_mana_actions(before)[0]
    info = propagate_information(before, after, InformationState())
    assert info.known_top == ()
    assert info.known_bottom == ()


def main():
    tests = [
        test_initial_state_does_not_leak_hidden_top,
        test_continuous_chip_and_ftt_reveal_only_current_top,
        test_known_prefix_is_consumed_by_draw,
        test_continuous_visibility_refreshes_after_draw,
        test_scry_records_kept_top_and_bottom,
        test_scry_parser_handles_comma_in_card_name,
        test_top_reorder_knows_chosen_top_three,
        test_top_draw_places_known_top_and_preserves_deeper_memory,
        test_mystical_tutor_clears_old_knowledge_then_sets_target_top,
        test_fetch_shuffle_invalidates_top_and_bottom,
        test_bay_shuffle_then_etb_scry_retains_postshuffle_observation,
        test_urza_spin_shuffle_does_not_leave_random_top_known,
        test_ordinary_action_does_not_reveal_hidden_library,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("INFORMATION STATE PROPAGATION SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
