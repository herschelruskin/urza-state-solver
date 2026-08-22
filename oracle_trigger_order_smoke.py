#!/usr/bin/env python3
"""Focused regressions for Oracle controlled artifact-cast trigger ordering."""

from solver_architecture import canonical_markov_state_key
import urza_solver as solver


def _base_order_state(*, hand=(), extra_battlefield=(), urza=False):
    return solver.State(
        turn=3,
        library=("Island", "Junk", "Tail"),
        hand=tuple(hand),
        battlefield=(
            solver.Perm("Artificer's Assistant"),
            solver.Perm("Uthros Research Craft"),
        ) + tuple(extra_battlefield),
        uthros_counters=3,
        urza=urza,
    )


def _library_set(states):
    return {state.library for state in states}


def _final(states):
    return [state for state in states if not getattr(state, "oracle_stack", ())]


def test_assistant_and_uthros_both_legal_orders_survive():
    state = _base_order_state()
    variants = solver.artifact_cast_trigger_variants(state, "Welding Jar")
    assert len(variants) == 2
    assert _library_set(variants) == {
        ("Junk", "Tail"),      # Assistant keeps Island, then Uthros draws it.
        ("Tail", "Junk"),      # Uthros draws Island, then Assistant bottoms Junk.
    }
    assert all(v.hand == ("Island",) for v in variants)
    assert all(v.uthros_counters == 4 for v in variants)


def test_legacy_fixed_helper_is_still_one_of_the_oracle_variants():
    state = _base_order_state()
    legacy = solver.artifact_cast_triggers(state, "Welding Jar")
    variant_keys = {canonical_markov_state_key(v) for v in solver.artifact_cast_trigger_variants(state, "Welding Jar")}
    assert canonical_markov_state_key(legacy) in variant_keys


def test_duplicate_or_commuting_orders_are_collapsed_after_resolution():
    state = solver.State(
        turn=3,
        library=("Tail",),
        hand=(),
        battlefield=(
            solver.Perm("Valley Floodcaller"),
            solver.Perm("Forensic Gadgeteer"),
            solver.Perm("Grinding Station", tapped=True),
        ),
        urza=True,
    )
    variants = solver.artifact_cast_trigger_variants(state, "Welding Jar")
    assert len(variants) == 1
    only = variants[0]
    assert only.vfc_pumps == 1
    assert sum(p.mode == "clue" for p in only.battlefield) == 1
    assert only.blue == 1


def test_bauble_counter_keeps_all_value_trigger_orders():
    state = _base_order_state(
        hand=("Welding Jar",),
        extra_battlefield=(solver.Perm("Vexing Bauble"),),
    )
    variants = _final(solver.cast_from_hand_variants(state, "Welding Jar", free=True))
    assert _library_set(variants) == {("Junk", "Tail"), ("Tail", "Junk")}
    assert len(variants) >= 2
    for v in variants:
        assert "Welding Jar" in v.graveyard
        assert not any(p.name == "Welding Jar" for p in v.battlefield)
        assert v.hand == ("Island",)
        assert v.uthros_counters == 4


def test_ordinary_legal_actions_use_trigger_order_variants():
    state = _base_order_state(hand=("Welding Jar",))
    casts = [
        action for action in _final(solver.legal_actions(state))
        if action.trace and action.trace[-1] == "cast Welding Jar"
    ]
    assert len(casts) == 2
    assert _library_set(casts) == {("Junk", "Tail"), ("Tail", "Junk")}
    assert all(any(p.name == "Welding Jar" for p in v.battlefield) for v in casts)


def test_chip_top_cast_uses_trigger_order_variants():
    state = solver.State(
        turn=3,
        library=("Welding Jar", "Island", "Junk", "Tail"),
        hand=(),
        battlefield=(
            solver.Perm("The Reality Chip", mode="chip_attached"),
            solver.Perm("Artificer's Assistant"),
            solver.Perm("Uthros Research Craft"),
        ),
        chip_attached=True,
        chip_target="Artificer's Assistant",
        uthros_counters=3,
    )
    casts = _final(solver.chip_ftt_top_casts(state))
    assert len(casts) == 2
    assert _library_set(casts) == {("Junk", "Tail"), ("Tail", "Junk")}


def test_urza_permission_free_cast_uses_trigger_order_variants():
    state = solver.State(
        turn=3,
        library=("Island", "Junk", "Tail"),
        hand=(),
        battlefield=(
            solver.Perm("Artificer's Assistant"),
            solver.Perm("Uthros Research Craft"),
        ),
        exile=("Welding Jar",),
        urza_exile_permissions=("Welding Jar",),
        uthros_counters=3,
    )
    casts = _final(solver.urza_exile_permission_actions(state))
    assert len(casts) == 2
    assert _library_set(casts) == {("Junk", "Tail"), ("Tail", "Junk")}
    assert all(v.urza_exile_permissions == () for v in casts)
    assert all(v.exile == () for v in casts)


def test_special_zero_mana_artifact_casts_branch_trigger_order():
    chalice = _base_order_state(hand=("Everflowing Chalice",))
    chalice_casts = [
        v for v in _final(solver.chalice_cast_variants(chalice))
        if v.trace and v.trace[-1].startswith("cast Everflowing Chalice kicked 0x")
    ]
    assert len(chalice_casts) == 2
    assert _library_set(chalice_casts) == {("Junk", "Tail"), ("Tail", "Junk")}

    chrome = _base_order_state(hand=("Chrome Mox",))
    chrome_casts = [
        v for v in _final(solver.mox_cast_actions(chrome))
        if v.trace and v.trace[-1] == "cast Chrome Mox, no imprint"
    ]
    assert len(chrome_casts) == 2
    assert _library_set(chrome_casts) == {("Junk", "Tail"), ("Tail", "Junk")}

    diamond = _base_order_state(hand=("Mox Diamond",))
    diamond_no_discard = [
        v for v in _final(solver.mox_cast_actions(diamond))
        if v.trace and v.trace[-1] == "cast Mox Diamond, decline/cannot discard land -> graveyard"
    ]
    assert len(diamond_no_discard) == 2
    assert _library_set(diamond_no_discard) == {("Junk", "Tail"), ("Tail", "Junk")}


def test_unique_multiset_order_count_is_exact():
    orders = solver._unique_multiset_orders(("vfc", "assistant", "uthros", "gadgeteer"))
    assert len(orders) == 24
    dup = solver._unique_multiset_orders(("assistant", "assistant", "uthros"))
    assert len(dup) == 3


def main():
    tests = (
        test_assistant_and_uthros_both_legal_orders_survive,
        test_legacy_fixed_helper_is_still_one_of_the_oracle_variants,
        test_duplicate_or_commuting_orders_are_collapsed_after_resolution,
        test_bauble_counter_keeps_all_value_trigger_orders,
        test_ordinary_legal_actions_use_trigger_order_variants,
        test_chip_top_cast_uses_trigger_order_variants,
        test_urza_permission_free_cast_uses_trigger_order_variants,
        test_special_zero_mana_artifact_casts_branch_trigger_order,
        test_unique_multiset_order_count_is_exact,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("ORACLE CONTROLLED TRIGGER ORDER SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
