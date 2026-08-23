#!/usr/bin/env python3
"""Focused Phase-2 smokes for Urza-exiled tutor/search spells."""

import urza_solver as solver
import non_oracle_rules_adapter as rules
from non_oracle_runtime import ACTION_PASS_PRIORITY, make_runtime_state
from non_oracle_urza_runtime import MAIN_USE_URZA_PERMISSION
from non_oracle_urza_search_permission_runtime import (
    USE_CAST_SCOUR,
    USE_CAST_SIMPLE_TUTOR,
    USE_CAST_TRANSMUTE_ARTIFACT,
)
from urza_permission_adapter import UrzaPermissionState


def _request(runtime):
    return rules.rules_decision_request(runtime, horizon=6)


def _pass(runtime):
    return next(a for a in _request(runtime).actions if a.action_id == ACTION_PASS_PRIORITY)


def _permission_runtime(
    card,
    *,
    library=("TAIL",),
    hand=(),
    battlefield=(),
    graveyard=(),
    blue=0,
    colorless=0,
):
    permissions = UrzaPermissionState().grant(card, 2)
    return make_runtime_state(
        solver.State(
            turn=2,
            library=tuple(library),
            hand=tuple(hand),
            battlefield=tuple(battlefield),
            graveyard=tuple(graveyard),
            exile=(card,),
            blue=blue,
            colorless=colorless,
        ),
        permissions=permissions,
    )


def _permission_actions(runtime, *, use=None, card=None):
    rows = [a for a in _request(runtime).actions if a.kind == MAIN_USE_URZA_PERMISSION]
    if use is not None:
        rows = [a for a in rows if dict(a.parameters).get("use") == use]
    if card is not None:
        rows = [a for a in rows if dict(a.parameters).get("card") == card]
    return rows


def _target(runtime, target, kind=None):
    rows = _request(runtime).actions
    if kind is not None:
        rows = [a for a in rows if a.kind == kind]
    return next(a for a in rows if dict(a.parameters).get("target") == target)


def test_mystical_permission_hides_library_until_spell_resolves():
    def build(library):
        return _permission_runtime("Mystical Tutor", library=library)

    left = build(("Dramatic Reversal", "Island", "Sol Ring"))
    right = build(("Sol Ring", "Island", "Dramatic Reversal"))
    la = _permission_actions(left, use=USE_CAST_SIMPLE_TUTOR, card="Mystical Tutor")
    ra = _permission_actions(right, use=USE_CAST_SIMPLE_TUTOR, card="Mystical Tutor")
    assert tuple(a.strategic_key() for a in la) == tuple(a.strategic_key() for a in ra)
    assert len(la) == 1
    assert "Dramatic Reversal" not in repr(la)
    assert "Sol Ring" not in repr(la)

    left = rules.apply_main_action(left, la[0])
    assert "Mystical Tutor" not in left.true_state.exile
    assert not left.permissions.permissions
    assert left.stack.top().kind == "simple_tutor_spell"
    assert "Dramatic Reversal" not in repr(_request(left).actions)

    left = rules.apply_main_action(left, _pass(left))
    request = _request(left)
    assert request.actions and all(a.kind == "choose_tutor_target" for a in request.actions)
    assert "Dramatic Reversal" in {dict(a.parameters).get("target") for a in request.actions}
    left = rules.apply_main_action(left, _target(left, "Dramatic Reversal", "choose_tutor_target"))
    assert left.information.known_top[:1] == ("Dramatic Reversal",)
    assert left.true_state.library[0] == "Dramatic Reversal"


def test_merchant_priority_requires_floodcaller():
    def stacked(with_floodcaller):
        battlefield = (solver.Perm("Valley Floodcaller"),) if with_floodcaller else ()
        runtime = _permission_runtime(
            "Merchant Scroll",
            library=("Dramatic Reversal", "Island"),
            hand=("Sol Ring",),
            battlefield=battlefield,
            colorless=1,
        )
        cast = next(
            a for a in _request(runtime).actions
            if a.kind == "main_cast_artifact" and dict(a.parameters).get("card") == "Sol Ring"
        )
        return rules.apply_main_action(runtime, cast)

    plain = stacked(False)
    assert not _permission_actions(plain, use=USE_CAST_SIMPLE_TUTOR, card="Merchant Scroll")

    flashed = stacked(True)
    actions = _permission_actions(flashed, use=USE_CAST_SIMPLE_TUTOR, card="Merchant Scroll")
    assert actions and all(bool(dict(a.parameters).get("priority")) for a in actions)
    flashed = rules.apply_main_action(flashed, actions[0])
    assert "Merchant Scroll" not in flashed.true_state.exile
    assert not flashed.permissions.permissions
    assert any(obj.card == "Merchant Scroll" for obj in flashed.stack.objects)


def test_spellseeker_permission_resolves_then_etb_searches():
    runtime = _permission_runtime(
        "Spellseeker",
        library=("Dramatic Reversal", "Island"),
    )
    action = _permission_actions(runtime, use=USE_CAST_SIMPLE_TUTOR, card="Spellseeker")[0]
    runtime = rules.apply_main_action(runtime, action)
    assert runtime.stack.top().kind == "simple_tutor_spellseeker_spell"
    runtime = rules.apply_main_action(runtime, _pass(runtime))
    assert solver.has(runtime.true_state, "Spellseeker")
    assert runtime.stack.top().kind == "simple_tutor_spellseeker_etb"
    assert "Dramatic Reversal" not in repr(_request(runtime).actions)

    runtime = rules.apply_main_action(runtime, _pass(runtime))
    request = _request(runtime)
    assert request.actions and all(a.kind == "choose_tutor_target" for a in request.actions)
    assert "Dramatic Reversal" in {dict(a.parameters).get("target") for a in request.actions}


def test_floodcaller_does_not_flash_spellseeker_permission():
    runtime = _permission_runtime(
        "Spellseeker",
        library=("Dramatic Reversal", "Island"),
        hand=("Sol Ring",),
        battlefield=(solver.Perm("Valley Floodcaller"),),
        colorless=1,
    )
    cast = next(a for a in _request(runtime).actions if a.kind == "main_cast_artifact")
    runtime = rules.apply_main_action(runtime, cast)
    assert not _permission_actions(runtime, use=USE_CAST_SIMPLE_TUTOR, card="Spellseeker")


def test_free_transmute_artifact_skips_uu_but_keeps_resolution_sacrifice_boundary():
    runtime = _permission_runtime(
        "Transmute Artifact",
        library=("Basalt Monolith", "Island"),
        battlefield=(solver.Perm("Sol Ring"),),
        blue=0,
        colorless=0,
    )
    actions = _permission_actions(runtime, use=USE_CAST_TRANSMUTE_ARTIFACT)
    assert len(actions) == 1 and int(dict(actions[0].parameters)["mana_spent"]) == 0
    runtime = rules.apply_main_action(runtime, actions[0])
    assert runtime.stack.top().kind == "transmute_artifact_spell"
    assert runtime.true_state.blue == 0 and runtime.true_state.colorless == 0
    assert solver.has(runtime.true_state, "Sol Ring")
    assert "Basalt Monolith" not in repr(_request(runtime).actions)

    runtime = rules.apply_main_action(runtime, _pass(runtime))
    request = _request(runtime)
    assert request.actions and all(a.kind == "transmute_choose_sacrifice" for a in request.actions)
    sacrifice = next(
        a for a in request.actions
        if tuple(dict(a.parameters)["signature"])[0] == "Sol Ring"
    )
    runtime = rules.apply_main_action(runtime, sacrifice)
    request = _request(runtime)
    assert request.actions and all(a.kind == "transmute_choose_target" for a in request.actions)
    assert "Basalt Monolith" in {dict(a.parameters).get("target") for a in request.actions}


def test_free_scour_commits_public_mode_before_library_search():
    runtime = _permission_runtime(
        "Scour for Scrap",
        library=("Basalt Monolith", "Island"),
        graveyard=("Sol Ring",),
    )
    actions = _permission_actions(runtime, use=USE_CAST_SCOUR)
    assert {dict(a.parameters)["mode"] for a in actions} == {"library", "graveyard", "both"}
    both = next(a for a in actions if dict(a.parameters)["mode"] == "both")
    assert dict(both.parameters)["graveyard_target"] == "Sol Ring"
    assert "Basalt Monolith" not in repr(actions)

    runtime = rules.apply_main_action(runtime, both)
    assert runtime.stack.top().kind == "scour_for_scrap_spell"
    assert "Basalt Monolith" not in repr(_request(runtime).actions)
    runtime = rules.apply_main_action(runtime, _pass(runtime))
    request = _request(runtime)
    assert request.actions and all(a.kind == "remaining_search_target" for a in request.actions)
    assert "Basalt Monolith" in {dict(a.parameters).get("target") for a in request.actions}


def test_scour_permission_is_native_priority_spell():
    runtime = _permission_runtime(
        "Scour for Scrap",
        library=("Basalt Monolith", "Island"),
        hand=("Sol Ring",),
        colorless=1,
    )
    cast = next(a for a in _request(runtime).actions if a.kind == "main_cast_artifact")
    runtime = rules.apply_main_action(runtime, cast)
    actions = _permission_actions(runtime, use=USE_CAST_SCOUR)
    assert actions and all(bool(dict(a.parameters).get("priority")) for a in actions)
    runtime = rules.apply_main_action(runtime, actions[0])
    assert any(obj.kind == "scour_for_scrap_spell" for obj in runtime.stack.objects)
    assert "Scour for Scrap" not in runtime.true_state.exile


def main():
    tests = (
        test_mystical_permission_hides_library_until_spell_resolves,
        test_merchant_priority_requires_floodcaller,
        test_spellseeker_permission_resolves_then_etb_searches,
        test_floodcaller_does_not_flash_spellseeker_permission,
        test_free_transmute_artifact_skips_uu_but_keeps_resolution_sacrifice_boundary,
        test_free_scour_commits_public_mode_before_library_search,
        test_scour_permission_is_native_priority_spell,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("URZA SEARCH PERMISSION RUNTIME SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
