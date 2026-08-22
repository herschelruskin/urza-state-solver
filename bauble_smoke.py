#!/usr/bin/env python3
"""Focused Vexing Bauble correctness smoke tests.

Run after applying ``tools/apply_vexing_bauble_patch.py``:

    py -3 bauble_smoke.py
"""

from urza_solver import (
    Perm,
    State,
    cast_from_hand,
    chalice_cast_variants,
    chip_ftt_top_casts,
    offer_actions,
    special_actions,
)


def names(state):
    return tuple(p.name for p in state.battlefield)


def trace_has(state, needle):
    return any(needle in line for line in state.trace)


def test_zero_mana_artifact_is_countered():
    s = State(
        turn=2,
        library=("Tail",),
        hand=("Tormod's Crypt",),
        battlefield=(Perm("Vexing Bauble"),),
    )
    r = cast_from_hand(s, "Tormod's Crypt")
    assert r is not None
    assert "Tormod's Crypt" not in names(r)
    assert "Tormod's Crypt" in r.graveyard
    assert trace_has(r, "Vexing Bauble counters Tormod's Crypt")


def test_paid_spell_survives_bauble():
    s = State(
        turn=2,
        library=("Tail",),
        hand=("Sol Ring",),
        battlefield=(Perm("Vexing Bauble"),),
        colorless=1,
    )
    r = cast_from_hand(s, "Sol Ring")
    assert r is not None
    assert "Sol Ring" in names(r)
    assert "Sol Ring" not in r.graveyard
    assert r.colorless == 0


def test_probe_can_pay_blue_but_free_probe_is_countered():
    paid = State(
        turn=2,
        library=("Drawn", "Tail"),
        hand=("Gitaxian Probe",),
        battlefield=(Perm("Vexing Bauble"),),
        blue=1,
    )
    r = cast_from_hand(paid, "Gitaxian Probe")
    assert r is not None
    assert r.blue == 0
    assert "Drawn" in r.hand
    assert not trace_has(r, "Vexing Bauble counters")

    free = State(
        turn=2,
        library=("ShouldStay", "Tail"),
        hand=("Gitaxian Probe",),
        battlefield=(Perm("Vexing Bauble"),),
        blue=1,
    )
    r2 = cast_from_hand(free, "Gitaxian Probe", free=True)
    assert r2 is not None
    assert r2.blue == 1, "Urza/free alternate cost must not secretly pay U"
    assert r2.library == free.library
    assert "Gitaxian Probe" in r2.graveyard
    assert trace_has(r2, "Vexing Bauble counters")


def test_nonartifact_cast_trigger_happens_before_bauble_counter():
    s = State(
        turn=3,
        library=("Tail",),
        hand=("Tezzeret, Cruel Captain",),
        battlefield=(
            Perm("Vexing Bauble"),
            Perm("Valley Floodcaller", tapped=True),
        ),
    )
    r = cast_from_hand(s, "Tezzeret, Cruel Captain", free=True)
    assert r is not None
    assert "Tezzeret, Cruel Captain" not in names(r)
    assert "Tezzeret, Cruel Captain" in r.graveyard
    vfc = next(p for p in r.battlefield if p.name == "Valley Floodcaller")
    assert not vfc.tapped, "VFC cast trigger must resolve before Bauble counter"
    assert r.vfc_pumps == 1


def test_urza_spin_free_nonartifact_is_countered():
    s = State(
        turn=3,
        library=("Rhystic Study",),
        hand=(),
        battlefield=(Perm("Vexing Bauble"),),
        colorless=5,
        urza=True,
        construct=True,
    )
    spins = [x for x in special_actions(s) if trace_has(x, "Urza spin")]
    assert spins, "expected Urza spin action"
    r = spins[0]
    assert "Rhystic Study" not in names(r)
    assert "Rhystic Study" in r.graveyard
    assert trace_has(r, "Vexing Bauble counters Rhystic Study")


def test_chalice_uses_actual_mana_spent():
    s = State(
        turn=2,
        library=("Tail",),
        hand=("Everflowing Chalice",),
        battlefield=(Perm("Vexing Bauble"),),
        colorless=2,
    )
    variants = chalice_cast_variants(s)
    zero = next(x for x in variants if trace_has(x, "kicked 0x"))
    one = next(x for x in variants if trace_has(x, "kicked 1x ->"))

    assert "Everflowing Chalice" in zero.graveyard
    assert not any(p.name == "Everflowing Chalice" for p in zero.battlefield)

    chalice = next(p for p in one.battlefield if p.name == "Everflowing Chalice")
    assert chalice.counters == 1
    assert "Everflowing Chalice" not in one.graveyard


def test_ftt_zero_cost_cast_is_countered():
    s = State(
        turn=3,
        library=("Sol Ring", "Tail"),
        hand=(),
        battlefield=(Perm("Vexing Bauble"), Perm("Fortune Teller's Talent")),
        ftt_level=3,
        spell_cast_this_turn=True,
    )
    actions = chip_ftt_top_casts(s)
    assert actions
    r = actions[0]
    assert "Sol Ring" not in names(r)
    assert "Sol Ring" in r.graveyard
    assert trace_has(r, "Vexing Bauble counters Sol Ring")


def test_offer_can_respond_to_bauble_trigger():
    s = State(
        turn=2,
        library=("Tail",),
        hand=("An Offer You Can't Refuse", "Tormod's Crypt"),
        battlefield=(Perm("Vexing Bauble"),),
        blue=1,
    )
    actions = [x for x in offer_actions(s) if trace_has(x, "Offer counters our Tormod's Crypt")]
    assert actions, "self-Offer response to Bauble trigger should remain legal"
    r = actions[0]
    assert sum(p.mode == "treasure" for p in r.battlefield) == 2
    assert "Tormod's Crypt" in r.graveyard
    assert "An Offer You Can't Refuse" in r.graveyard


def main():
    tests = [
        test_zero_mana_artifact_is_countered,
        test_paid_spell_survives_bauble,
        test_probe_can_pay_blue_but_free_probe_is_countered,
        test_nonartifact_cast_trigger_happens_before_bauble_counter,
        test_urza_spin_free_nonartifact_is_countered,
        test_chalice_uses_actual_mana_spent,
        test_ftt_zero_cost_cast_is_countered,
        test_offer_can_respond_to_bauble_trigger,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("VEXING BAUBLE SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
