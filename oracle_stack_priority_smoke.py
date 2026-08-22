#!/usr/bin/env python3
"""Focused regressions for Oracle artifact stack / inter-trigger priority windows."""

from dataclasses import replace

import urza_solver as solver
from solver_architecture import canonical_markov_state_key


def _is_trigger(state,kind):
    return bool(
        state.oracle_stack
        and len(state.oracle_stack[0])>=5
        and state.oracle_stack[0][0]=="trigger"
        and state.oracle_stack[0][2]==kind
    )


def _has_pending_spell(state,card):
    return any(
        len(entry)>=5 and entry[0]=="spell" and entry[2]==card
        for entry in state.oracle_stack
    )


def _finals(states):
    return [s for s in states if not s.oracle_stack]


def _pending(states):
    return [s for s in states if s.oracle_stack]


def test_cast_exposes_real_pending_stack_and_pass_only_final():
    state=solver.State(
        turn=3,
        library=("A","B","Tail"),
        hand=("Welding Jar",),
        battlefield=(
            solver.Perm("Artificer's Assistant"),
            solver.Perm("Uthros Research Craft"),
        ),
        uthros_counters=3,
    )
    variants=solver.cast_from_hand_variants(state,"Welding Jar")
    assert _pending(variants), "cast must expose at least one priority pause"
    assert _finals(variants), "cast must also retain a pure-pass resolved branch"
    assert all("Welding Jar" not in p.hand for p in variants)
    assert any(_has_pending_spell(p,"Welding Jar") for p in _pending(variants))
    finals=_finals(variants)
    assert all(any(p.name=="Welding Jar" for p in f.battlefield) for f in finals)


def test_gadgeteer_clue_crack_between_cast_triggers_changes_uthros_draw():
    state=solver.State(
        turn=3,
        library=("A","B","C","Tail"),
        hand=("Welding Jar",),
        battlefield=(
            solver.Perm("Forensic Gadgeteer"),
            solver.Perm("Uthros Research Craft"),
        ),
        uthros_counters=3,
        colorless=1,
    )
    cast_states=solver.cast_from_hand_variants(state,"Welding Jar")
    pause=next(
        s for s in cast_states
        if _is_trigger(s,"uthros")
        and any(p.mode=="clue" for p in s.battlefield)
        and _has_pending_spell(s,"Welding Jar")
    )
    assert pause.hand==()
    assert pause.library==( "A","B","C","Tail")

    successors=solver.legal_actions(pause)
    final=next(
        s for s in successors
        if not s.oracle_stack
        and s.hand[:2]==("A","B")
        and any(p.name=="Welding Jar" for p in s.battlefield)
    )
    assert final.library==( "C","Tail")
    assert final.uthros_counters==4
    assert not any(p.mode=="clue" for p in final.battlefield)


def test_top_reorder_can_happen_between_gadgeteer_and_uthros():
    state=solver.State(
        turn=3,
        library=("A","B","C","Tail"),
        hand=("Welding Jar",),
        battlefield=(
            solver.Perm("Forensic Gadgeteer"),
            solver.Perm("Uthros Research Craft"),
            solver.Perm("Sensei's Divining Top"),
        ),
        uthros_counters=3,
        colorless=1,
    )
    cast_states=solver.cast_from_hand_variants(state,"Welding Jar")
    pause=next(
        s for s in cast_states
        if _is_trigger(s,"uthros")
        and any(p.mode=="clue" for p in s.battlefield)
        and _has_pending_spell(s,"Welding Jar")
    )
    successors=solver.legal_actions(pause)
    final=next(
        s for s in successors
        if not s.oracle_stack
        and s.hand==("C",)
        and s.library[:2]==("B","A")
        and any(p.name=="Welding Jar" for p in s.battlefield)
    )
    assert final.uthros_counters==4


def test_bauble_is_real_stack_trigger_and_offer_can_use_mana_from_prior_gadgeteer():
    # No blue initially.  If Gadgeteer resolves above Bauble, its Clue ETB lets
    # an already-tapped Station generate U through Urza.  Priority then returns
    # before Bauble, allowing Offer to counter the still-pending Welding Jar.
    state=solver.State(
        turn=3,
        library=("Tail",),
        hand=("Welding Jar","An Offer You Can't Refuse"),
        battlefield=(
            solver.Perm("Vexing Bauble"),
            solver.Perm("Forensic Gadgeteer"),
            solver.Perm("Grinding Station",tapped=True),
        ),
        urza=True,
        blue=0,
    )
    casts=solver.cast_from_hand_variants(state,"Welding Jar")
    pause=next(
        s for s in casts
        if _is_trigger(s,"bauble")
        and any(p.mode=="clue" for p in s.battlefield)
        and s.blue>=1
        and _has_pending_spell(s,"Welding Jar")
    )
    assert pause.blue>=1
    successors=solver.legal_actions(pause)
    offered=next(
        s for s in successors
        if not s.oracle_stack
        and "Welding Jar" in s.graveyard
        and "An Offer You Can't Refuse" in s.graveyard
        and sum(p.mode=="treasure" for p in s.battlefield)>=2
    )
    assert not any(p.name=="Welding Jar" for p in offered.battlefield)


def test_mox_diamond_can_discard_land_drawn_by_uthros_before_resolution():
    state=solver.State(
        turn=3,
        library=("Island","Tail"),
        hand=("Mox Diamond",),
        battlefield=(solver.Perm("Uthros Research Craft"),),
        uthros_counters=3,
    )
    variants=solver.mox_cast_actions(state)
    final=next(
        s for s in variants
        if not s.oracle_stack
        and any(p.name=="Mox Diamond" and p.mode=="diamond" for p in s.battlefield)
    )
    assert final.hand==()
    assert "Island" in final.graveyard
    assert final.library==( "Tail",)
    assert final.uthros_counters==4


def test_chrome_mox_imprint_trigger_can_use_card_drawn_before_resolution():
    state=solver.State(
        turn=3,
        library=("Mystical Tutor","Tail"),
        hand=("Chrome Mox",),
        battlefield=(solver.Perm("Uthros Research Craft"),),
        uthros_counters=3,
    )
    variants=solver.mox_cast_actions(state)
    final=next(
        s for s in variants
        if not s.oracle_stack
        and any(p.name=="Chrome Mox" and p.mode=="imprinted" for p in s.battlefield)
    )
    assert final.hand==()
    assert "Mystical Tutor" in final.exile
    assert final.library==( "Tail",)
    assert final.uthros_counters==4


def test_priority_timing_excludes_sorcery_only_station_and_bay():
    state=solver.State(
        turn=3,
        library=("Tail",),
        hand=(),
        battlefield=(
            solver.Perm("Uthros Research Craft"),
            solver.Perm("Repurposing Bay"),
            solver.Perm("Artificer's Assistant",sick=False),
        ),
        uthros_counters=3,
        blue=3,
        colorless=3,
        oracle_stack=(("trigger","1","assistant","Welding Jar",""),
                      ("spell","1","Welding Jar","ordinary","")),
    )
    actions=solver._oracle_priority_raw_actions(state)
    lines=[a.trace[-1].splitlines()[0] for a in actions if a.trace]
    assert not any(line.startswith("Uthros stations ") for line in lines)
    assert not any(line.startswith("Repurposing Bay ") for line in lines)


def test_stack_identity_and_end_turn_legality():
    base=solver.State(turn=3,library=("Tail",),hand=(),battlefield=())
    pending=replace(
        base,
        oracle_stack=(("spell","1","Welding Jar","ordinary",""),),
    )
    assert base.key()!=pending.key()
    assert solver.dominance_signature(base)!=solver.dominance_signature(pending)
    assert canonical_markov_state_key(base)!=canonical_markov_state_key(pending)
    assert solver.can_end_turn_state(base)
    assert not solver.can_end_turn_state(pending)


def main():
    tests=(
        test_cast_exposes_real_pending_stack_and_pass_only_final,
        test_gadgeteer_clue_crack_between_cast_triggers_changes_uthros_draw,
        test_top_reorder_can_happen_between_gadgeteer_and_uthros,
        test_bauble_is_real_stack_trigger_and_offer_can_use_mana_from_prior_gadgeteer,
        test_mox_diamond_can_discard_land_drawn_by_uthros_before_resolution,
        test_chrome_mox_imprint_trigger_can_use_card_drawn_before_resolution,
        test_priority_timing_excludes_sorcery_only_station_and_bay,
        test_stack_identity_and_end_turn_legality,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("ORACLE STACK / INTER-TRIGGER PRIORITY SMOKE: ALL PASS")


if __name__=="__main__":
    main()
