#!/usr/bin/env python3
"""Focused Oracle regressions for persistent Urza {5} exile permissions."""

from dataclasses import replace

import urza_solver as solver
from solver_architecture import canonical_markov_state_key


def choose(actions, prefix):
    return next(a for a in actions if a.trace and a.trace[-1].startswith(prefix))


def test_spin_grants_permission_without_immediate_use():
    state = solver.State(
        turn=3,
        library=("Mana Vault",),
        hand=(),
        battlefield=(solver.Perm(solver.COMMANDER),),
        urza=True,
        colorless=5,
        rng_root_seed=20260822,
    )
    spun = choose(solver.special_actions(state), "Urza spin -> exile Mana Vault")
    assert spun.library == ()
    assert spun.exile == ("Mana Vault",)
    assert spun.urza_exile_permissions == ("Mana Vault",)
    assert not any(p.name == "Mana Vault" for p in spun.battlefield)
    assert "Mana Vault" not in spun.hand


def test_permission_survives_unrelated_action_and_can_be_used_later():
    state = solver.State(
        turn=3,
        library=("Tail",),
        hand=(),
        battlefield=(solver.Perm(solver.COMMANDER), solver.Perm("Sol Ring")),
        exile=("Mana Vault",),
        urza_exile_permissions=("Mana Vault",),
        urza=True,
    )
    tapped = choose(solver.intrinsic_mana_actions(state), "tap Sol Ring")
    assert tapped.urza_exile_permissions == ("Mana Vault",)
    assert tapped.exile == ("Mana Vault",)

    used = choose(
        solver.urza_exile_permission_actions(tapped),
        "Urza permission -> cast Mana Vault free",
    )
    assert used.urza_exile_permissions == ()
    assert used.exile == ()
    assert any(p.name == "Mana Vault" for p in used.battlefield)


def test_multiple_spins_accumulate_permissions_before_use():
    state = solver.State(
        turn=3,
        library=("Mana Vault", "Island"),
        hand=(),
        battlefield=(solver.Perm(solver.COMMANDER),),
        urza=True,
        colorless=10,
        rng_root_seed=20260822,
    )
    first = next(
        a for a in solver.special_actions(state)
        if a.trace and a.trace[-1].startswith("Urza spin -> exile ")
    )
    assert len(first.urza_exile_permissions) == 1
    second = next(
        a for a in solver.special_actions(first)
        if a.trace and a.trace[-1].startswith("Urza spin -> exile ")
    )
    assert len(second.urza_exile_permissions) == 2
    assert len(second.exile) == 2
    assert second.colorless == 0


def test_mdfc_permission_offers_land_and_spell_faces():
    state = solver.State(
        turn=3,
        library=("Tail",),
        hand=(),
        battlefield=(),
        exile=("Hydroelectric Specimen",),
        urza_exile_permissions=("Hydroelectric Specimen",),
        land_played=False,
    )
    actions = solver.urza_exile_permission_actions(state)
    assert any(
        a.trace and a.trace[-1].startswith("Urza permission -> play Hydroelectric Specimen")
        for a in actions
    )
    assert any(
        a.trace and a.trace[-1].startswith("Urza permission -> cast Hydroelectric Specimen free")
        for a in actions
    )


def test_unused_permission_expires_but_card_stays_exiled():
    state = solver.State(
        turn=3,
        library=("Tail",),
        hand=(),
        battlefield=(),
        exile=("Mana Vault",),
        urza_exile_permissions=("Mana Vault",),
    )
    nxt = solver.end_turn(state)
    assert nxt.turn == 4
    assert nxt.urza_exile_permissions == ()
    assert "Mana Vault" in nxt.exile


def test_exact_and_dominance_identity_distinguish_live_permission():
    base = solver.State(
        turn=3,
        library=("Tail",),
        hand=(),
        battlefield=(),
        exile=("Mana Vault",),
    )
    live = replace(base, urza_exile_permissions=("Mana Vault",))
    assert base.key() != live.key()
    assert solver.dominance_signature(base) != solver.dominance_signature(live)
    assert canonical_markov_state_key(base) != canonical_markov_state_key(live)


def test_free_spell_is_still_countered_by_own_vexing_bauble():
    state = solver.State(
        turn=3,
        library=("Tail",),
        hand=(),
        battlefield=(solver.Perm("Vexing Bauble"),),
        exile=("Mana Vault",),
        urza_exile_permissions=("Mana Vault",),
    )
    used = choose(
        solver.urza_exile_permission_actions(state),
        "Urza permission -> cast Mana Vault free",
    )
    assert used.urza_exile_permissions == ()
    assert used.exile == ()
    assert "Mana Vault" in used.graveyard
    assert not any(p.name == "Mana Vault" for p in used.battlefield)


def main():
    tests = (
        test_spin_grants_permission_without_immediate_use,
        test_permission_survives_unrelated_action_and_can_be_used_later,
        test_multiple_spins_accumulate_permissions_before_use,
        test_mdfc_permission_offers_land_and_spell_faces,
        test_unused_permission_expires_but_card_stays_exiled,
        test_exact_and_dominance_identity_distinguish_live_permission,
        test_free_spell_is_still_countered_by_own_vexing_bauble,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("ORACLE URZA PERMISSION SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
