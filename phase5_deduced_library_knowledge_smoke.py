#!/usr/bin/env python3
"""Regressions for logically deduced remaining-library membership.

The player may know exactly WHICH cards remain from decklist + known zones while
still not knowing WHERE those cards are in the library.
"""

from collections import Counter

import urza_solver as solver
from information_state_propagation import (
    deduced_library_counts,
    initial_information,
    propagate_information,
)
from solver_architecture import make_policy_view


def count_map(info):
    return dict(info.known_library_counts)


def test_initial_membership_known_but_order_hidden():
    a=solver.State(
        turn=1,
        library=("Power Artifact","Island","Sol Ring","Island"),
        hand=("Mana Vault",),
        battlefield=(),
    )
    b=solver.State(
        turn=1,
        library=("Island","Sol Ring","Island","Power Artifact"),
        hand=("Mana Vault",),
        battlefield=(),
    )
    ia=initial_information(a)
    ib=initial_information(b)
    assert ia.known_top==()
    assert ib.known_top==()
    assert ia.known_bottom==()
    assert ib.known_bottom==()
    assert ia.known_library_counts==ib.known_library_counts
    assert count_map(ia)=={
        "Island":2,
        "Power Artifact":1,
        "Sol Ring":1,
    }
    print("same multiset / different hidden order gives same player knowledge: PASS")


def test_policy_view_receives_deduced_membership_not_order():
    state=solver.State(
        turn=1,
        library=("Power Artifact","Island","Grim Monolith"),
        hand=("Muddle the Mixture",),
        battlefield=(),
    )
    info=initial_information(state)
    view=make_policy_view(state,info)
    assert dict(view.known_library_counts)=={
        "Grim Monolith":1,
        "Island":1,
        "Power Artifact":1,
    }
    assert view.known_top==()
    print("policy view exposes deduced membership while hiding order: PASS")


def test_draw_updates_exact_remaining_multiset():
    before=solver.State(
        turn=2,
        library=("Island","Power Artifact","Island"),
        hand=(),
        battlefield=(),
    )
    prior=initial_information(before)
    after,drawn=solver.draw_from_library(before,1)
    assert drawn==("Island",)
    info=propagate_information(before,after,prior)
    assert count_map(info)=={"Island":1,"Power Artifact":1}
    assert info.known_top==()
    print("observed draw decrements deduced library membership: PASS")


def test_card_moving_into_library_is_added_to_deduced_multiset():
    before=solver.State(
        turn=2,
        library=("Island","Sol Ring"),
        hand=(),
        battlefield=(solver.Perm("Sensei's Divining Top"),),
    )
    prior=initial_information(before)
    after=next(
        row for row in solver.top_actions(before)
        if row.trace and row.trace[-1].startswith("Sensei's Divining Top -> draw:")
    )
    info=propagate_information(before,after,prior)
    assert count_map(info)==dict(Counter(after.library))
    assert count_map(info)["Sensei's Divining Top"]==1
    assert info.known_top[0]=="Sensei's Divining Top"
    print("known card moved into library is added to membership deduction: PASS")


def test_search_removes_known_target_from_remaining_multiset():
    before=solver.State(
        turn=3,
        library=("Power Artifact","Defense Grid","Island"),
        hand=("Muddle the Mixture",),
        battlefield=(),
        blue=2,
    )
    prior=initial_information(before)
    after=next(
        row for row in solver.simple_tutor_actions(before)
        if "Power Artifact" in row.hand
    )
    info=propagate_information(before,after,prior)
    assert "Power Artifact" not in count_map(info)
    assert count_map(info)==dict(Counter(after.library))
    assert info.known_top==()
    assert info.known_bottom==()
    print("known tutor result leaving library updates exact membership: PASS")


def test_shuffle_erases_order_knowledge_but_keeps_exact_membership():
    before=solver.State(
        turn=2,
        library=("Island","Power Artifact","Sol Ring","Force of Will"),
        hand=(),
        battlefield=(solver.Perm("Flooded Strand"),),
        rng_root_seed=91,
    )
    prior=initial_information(before)
    # Give the player legitimate positional knowledge before the fetch.
    from dataclasses import replace
    prior=replace(
        prior,
        known_top=("Island",),
        known_bottom=("Force of Will",),
    )
    after=solver.fetch_actions(before)[0]
    info=propagate_information(before,after,prior)
    assert info.known_top==()
    assert info.known_bottom==()
    assert count_map(info)==dict(Counter(after.library))
    print("shuffle destroys position knowledge, not membership deduction: PASS")


def test_deduction_helper_never_depends_on_order():
    a=solver.State(turn=1,library=("A","B","A","C"),hand=(),battlefield=())
    b=solver.State(turn=1,library=("C","A","B","A"),hand=(),battlefield=())
    assert deduced_library_counts(a)==deduced_library_counts(b)
    print("deduced library counts are order-invariant by construction: PASS")


def main():
    tests=(
        test_initial_membership_known_but_order_hidden,
        test_policy_view_receives_deduced_membership_not_order,
        test_draw_updates_exact_remaining_multiset,
        test_card_moving_into_library_is_added_to_deduced_multiset,
        test_search_removes_known_target_from_remaining_multiset,
        test_shuffle_erases_order_knowledge_but_keeps_exact_membership,
        test_deduction_helper_never_depends_on_order,
    )
    for test in tests:
        test()
    print("DEDUCED LIBRARY KNOWLEDGE SMOKE: ALL PASS")


if __name__=="__main__":
    main()
