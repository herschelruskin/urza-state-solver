#!/usr/bin/env python3
"""Focused regressions for Oracle artifact-entry trigger stack semantics."""

from dataclasses import replace

import urza_solver as solver


def _kinds(state):
    return tuple(
        entry[2]
        for entry in state.oracle_stack
        if len(entry)>=5 and entry[0]=="trigger"
    )


def _count_kind(state,kind):
    return sum(
        1 for entry in state.oracle_stack
        if len(entry)>=5 and entry[0]=="trigger" and entry[2]==kind
    )


def _has_kind(state,kind):
    return _count_kind(state,kind)>0


def _finals(states):
    return [state for state in states if not state.oracle_stack]


def test_offer_two_treasures_are_one_simultaneous_entry_event():
    state=solver.State(
        turn=3,
        library=("Tail",),
        hand=("An Offer You Can't Refuse",),
        battlefield=(
            solver.Perm("Grinding Station"),
            solver.Perm("Battered Golem",sick=False),
            solver.Perm("Tezzeret, Cruel Captain",counters=4),
        ),
        blue=1,
        oracle_stack=(("spell","1","Welding Jar","ordinary",""),),
    )
    actions=solver.offer_pending_stack_actions(state)
    assert actions
    assert all(sum(p.mode=="treasure" for p in s.battlefield)==2 for s in actions)
    # Two Treasures enter simultaneously: each producer triggers twice and
    # Tezzeret triggers twice. There is never an intermediate one-Treasure state.
    assert all(_count_kind(s,"etb_producer")==4 for s in actions)
    assert all(_count_kind(s,"etb_tezz")==2 for s in actions)
    assert all(not any(p.mode=="treasure" for p in state.battlefield) for _ in (0,))


def test_prized_statue_then_treasure_are_two_nested_entry_events():
    state=solver.State(
        turn=3,
        library=("Tail",),
        hand=(),
        battlefield=(
            solver.Perm("Grinding Station"),
            solver.Perm("Battered Golem",sick=False),
        ),
    )
    entered=solver.add_perm(state,"Prized Statue")
    starts=solver._push_artifact_etb_stack_variants(entered,("Prized Statue",))
    prized_first=next(s for s in starts if _kinds(s) and _kinds(s)[0]=="etb_prized_treasure")
    assert _count_kind(prized_first,"etb_producer")==2
    assert _count_kind(prized_first,"etb_prized_treasure")==1

    after=solver._resolve_oracle_stack_top(prized_first)
    nested=next(s for s in after if sum(p.mode=="treasure" for p in s.battlefield)==1)
    # Treasure is a SECOND artifact-entry event. Its two fresh producer triggers
    # are pushed above the two still-unresolved producer triggers from Statue.
    assert _count_kind(nested,"etb_producer")==4
    assert _count_kind(nested,"etb_prized_treasure")==0


def test_witching_well_producer_trigger_can_resolve_before_scry_then_take_priority():
    state=solver.State(
        turn=3,
        library=("A","B","C","Tail"),
        hand=(),
        battlefield=(
            solver.Perm("Grinding Station",tapped=True),
            solver.Perm("Grafdigger's Cage"),
        ),
    )
    entered=solver.add_perm(state,"Witching Well")
    starts=solver._push_artifact_etb_stack_variants(entered,("Witching Well",))
    ordered=next(
        s for s in starts
        if _kinds(s)[:2]==("etb_producer","etb_scry2")
    )
    after_producer=next(
        s for s in solver._resolve_oracle_stack_top(ordered)
        if _has_kind(s,"etb_scry2")
        and any(p.name=="Grinding Station" and not p.tapped for p in s.battlefield)
    )
    actions=solver.legal_actions(after_producer)
    assert any(
        a.trace and a.trace[-1].splitlines()[0].startswith("Grinding Station sacs ")
        for a in actions
    ), "priority between producer untap and Well scry must expose Station activation"


def test_exact_scry_two_enumerates_all_six_distinct_outcomes():
    state=solver.State(
        turn=3,library=("A","B","Tail"),hand=(),battlefield=()
    )
    variants=solver.oracle_scry_variants(state,2,"test")
    libraries={v.library for v in variants}
    assert libraries=={
        ("A","B","Tail"),
        ("B","A","Tail"),
        ("A","Tail","B"),
        ("B","Tail","A"),
        ("Tail","A","B"),
        ("Tail","B","A"),
    }


def test_assistant_stack_scry_one_has_keep_and_bottom_branches():
    state=solver.State(
        turn=3,
        library=("A","B","Tail"),
        hand=(),
        battlefield=(),
        oracle_stack=(("trigger","1","assistant","Welding Jar",""),),
    )
    variants=solver._resolve_oracle_stack_top(state)
    assert {v.library for v in variants}=={
        ("A","B","Tail"),
        ("B","Tail","A"),
    }


def test_cam_etb_branches_real_target_and_tap_untap_choice():
    state=solver.State(
        turn=3,
        library=("Tail",),
        hand=(),
        battlefield=(
            solver.Perm("Battered Golem",tapped=True,sick=False),
            solver.Perm("Artificer's Assistant",tapped=False,sick=False),
        ),
    )
    entered=solver.add_perm(state,"Sewer-veillance Cam")
    variants=solver._artifact_entry_state_variants(entered,("Sewer-veillance Cam",))
    finals=_finals(variants)
    assert finals
    assert any(
        any(p.name=="Battered Golem" and not p.tapped for p in s.battlefield)
        for s in finals
    )
    assert any(
        any(p.name=="Artificer's Assistant" and p.tapped for p in s.battlefield)
        for s in finals
    )


def test_chrome_mox_imprint_orders_with_other_entry_triggers():
    state=solver.State(
        turn=3,
        library=("Tail",),
        hand=("Mystical Tutor",),
        battlefield=(solver.Perm("Grinding Station",tapped=True),),
    )
    entered=solver.add_perm(state,"Chrome Mox")
    starts=solver._push_artifact_etb_stack_variants(entered,("Chrome Mox",))
    orders={_kinds(s) for s in starts}
    assert ("etb_chrome_imprint","etb_producer") in orders
    assert ("etb_producer","etb_chrome_imprint") in orders


def test_bay_direct_entry_exposes_pending_etb_and_resolved_final():
    state=solver.State(
        turn=3,
        library=("Witching Well","Tail A","Tail B"),
        hand=(),
        battlefield=(
            solver.Perm("Repurposing Bay"),
            solver.Perm("Treasure",mode="treasure"),
        ),
        colorless=2,
        rng_root_seed=20260822,
    )
    actions=solver.repurposing_bay_actions(state)
    target_actions=[
        a for a in actions
        if a.trace and a.trace[-1].splitlines()[0].endswith(" -> Witching Well")
    ]
    assert target_actions
    assert any(_has_kind(a,"etb_scry2") for a in target_actions)
    assert any(not a.oracle_stack for a in target_actions)


def test_seat_of_synod_uses_real_artifact_entry_stack():
    state=solver.State(
        turn=3,
        library=("Tail",),
        hand=("Seat of the Synod",),
        battlefield=(solver.Perm("Grinding Station",tapped=True),),
    )
    variants=solver.play_land_variants(state,"Seat of the Synod")
    assert variants
    assert any(_has_kind(v,"etb_producer") for v in variants)
    assert any(not v.oracle_stack for v in variants)


def test_two_treasure_event_gives_each_producer_two_resolution_opportunities():
    state=solver.State(
        turn=3,
        library=("Tail",),
        hand=(),
        battlefield=(
            solver.Perm(solver.COMMANDER,sick=False),
            solver.Perm("Grinding Station"),
            solver.Perm("Battered Golem",sick=False),
        ),
        urza=True,
        commander_in_command_zone=False,
    )
    state=solver.add_perm(state,"Treasure",mode="treasure")
    state=solver.add_perm(state,"Treasure",mode="treasure")
    starts=solver._push_artifact_etb_stack_variants(state,("Treasure","Treasure"))
    assert starts
    assert all(_count_kind(s,"etb_producer")==4 for s in starts)
    finals=[]
    for start in starts:
        finals.extend(solver._oracle_stack_pause_frontier(start))
    finals=[s for s in finals if not s.oracle_stack]
    # The legacy-fast legal representative may take both Urza taps around each
    # untap trigger, so the two-entry event can realize substantial producer mana.
    assert max((s.blue for s in finals),default=0)>=4


def main():
    tests=(
        test_offer_two_treasures_are_one_simultaneous_entry_event,
        test_prized_statue_then_treasure_are_two_nested_entry_events,
        test_witching_well_producer_trigger_can_resolve_before_scry_then_take_priority,
        test_exact_scry_two_enumerates_all_six_distinct_outcomes,
        test_assistant_stack_scry_one_has_keep_and_bottom_branches,
        test_cam_etb_branches_real_target_and_tap_untap_choice,
        test_chrome_mox_imprint_orders_with_other_entry_triggers,
        test_bay_direct_entry_exposes_pending_etb_and_resolved_final,
        test_seat_of_synod_uses_real_artifact_entry_stack,
        test_two_treasure_event_gives_each_producer_two_resolution_opportunities,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("ORACLE ARTIFACT ETB STACK SMOKE: ALL PASS")


if __name__=="__main__":
    main()
