#!/usr/bin/env python3
"""Focused Phase-1 regressions for Bay/Saga/Tezzeret/Scour search timing."""

from dataclasses import replace

import urza_solver as solver
from solver_architecture import InformationState
from decision_observation import SearchZoneObservation, ShuffleObservation
from remaining_search_adapters import (
    BAY,
    SCOUR,
    SAGA,
    TEZZ,
    bay_activation_request,
    bay_target_request,
    begin_saga3_search,
    information_after_remaining_search,
    resolve_bay_activation,
    resolve_bay_target,
    resolve_saga3_target,
    resolve_scour_cast,
    resolve_scour_target,
    resolve_tezzeret_minus3,
    resolve_tezzeret_target,
    saga3_target_request,
    scour_cast_request,
    scour_target_request,
    tezzeret_minus3_request,
    tezzeret_target_request,
)


def clue():
    return solver.Perm("Clue", mode="clue")


def choose_action(request, predicate):
    return next(action for action in request.actions if predicate(dict(action.parameters)))


def choose_target(request, target):
    return choose_action(request, lambda p: p.get("target") == target)


def test_bay_commit_is_hidden_future_invariant_and_sacrifice_precedes_search():
    cards = ("Sensei's Divining Top", "Mana Vault", "Basalt Monolith", "Tail")
    base = solver.State(
        turn=2,
        library=cards,
        hand=(),
        battlefield=(solver.Perm(BAY), clue()),
        colorless=2,
        rng_root_seed=20260822,
    )
    other = replace(base, library=tuple(reversed(cards)))
    info = InformationState()
    req_a = bay_activation_request(base, info, horizon=6)
    req_b = bay_activation_request(other, info, horizon=6)
    assert req_a.observation == req_b.observation
    assert tuple(a.canonical_key() for a in req_a.actions) == tuple(
        a.canonical_key() for a in req_b.actions
    )
    action = req_a.actions[0]
    assert "Sensei's Divining Top" not in repr(action.parameters)
    env, ctx, search = resolve_bay_activation(base, action)
    assert ctx.target_mv == 1
    assert not any(p.mode == "clue" for p in env.true_state.battlefield)
    assert any(p.name == BAY and p.tapped for p in env.true_state.battlefield)
    assert isinstance(search, SearchZoneObservation)
    assert set(search.legal_cards) == {"Sensei's Divining Top", "Mana Vault"}
    assert "Basalt Monolith" not in search.legal_cards


def test_bay_target_only_appears_after_search_and_shuffle_resets_information():
    state = solver.State(
        turn=2,
        library=("Mana Vault", "Tail"),
        hand=(),
        battlefield=(solver.Perm(BAY), clue()),
        colorless=2,
        rng_root_seed=20260822,
    )
    prior = InformationState(
        known_top=("Mana Vault",), known_bottom=("Tail",), shuffle_epoch=2
    )
    root = bay_activation_request(state, prior, horizon=6).actions[0]
    env, ctx, search = resolve_bay_activation(state, root)
    request = bay_target_request(env.true_state, prior, ctx, search, horizon=6)
    target = choose_target(request, "Mana Vault")
    final = resolve_bay_target(env.true_state, ctx, search, target)
    assert any(p.name == "Mana Vault" for p in final.true_state.battlefield)
    assert any(isinstance(e, ShuffleObservation) for e in final.observations.events)
    updated = information_after_remaining_search(prior, final)
    assert updated.known_top == ()
    assert updated.known_bottom == ()
    assert updated.shuffle_epoch == 3


def test_tezzeret_minus3_commit_is_hidden_future_invariant_and_loyalty_paid_first():
    cards = ("Mana Vault", "Sensei's Divining Top", "Basalt Monolith", "Tail")
    base = solver.State(
        turn=2,
        library=cards,
        hand=(),
        battlefield=(solver.Perm(TEZZ, counters=4),),
        rng_root_seed=20260822,
    )
    other = replace(base, library=tuple(reversed(cards)))
    info = InformationState()
    req_a = tezzeret_minus3_request(base, info, horizon=6)
    req_b = tezzeret_minus3_request(other, info, horizon=6)
    assert req_a.observation == req_b.observation
    assert tuple(a.canonical_key() for a in req_a.actions) == tuple(
        a.canonical_key() for a in req_b.actions
    )
    action = req_a.actions[0]
    assert "Mana Vault" not in repr(action.parameters)
    env, ctx, search = resolve_tezzeret_minus3(base, action)
    tez = next(p for p in env.true_state.battlefield if p.name == TEZZ)
    assert tez.counters == 1 and tez.mode == "tez_used"
    assert set(search.legal_cards) == {"Mana Vault", "Sensei's Divining Top"}
    assert "Basalt Monolith" not in search.legal_cards


def test_tezzeret_target_to_hand_occurs_only_after_search():
    state = solver.State(
        turn=2,
        library=("Mana Vault", "Tail"),
        hand=(),
        battlefield=(solver.Perm(TEZZ, counters=4),),
        rng_root_seed=20260822,
    )
    info = InformationState()
    root = tezzeret_minus3_request(state, info, horizon=6).actions[0]
    env, ctx, search = resolve_tezzeret_minus3(state, root)
    req = tezzeret_target_request(env.true_state, info, ctx, search, horizon=6)
    final = resolve_tezzeret_target(
        env.true_state, ctx, search, choose_target(req, "Mana Vault")
    )
    assert "Mana Vault" in final.true_state.hand
    assert "Mana Vault" not in final.true_state.library


def test_saga_pending_trigger_goes_directly_to_search_observation():
    cards = ("Sensei's Divining Top", "Mana Vault", "Basalt Monolith", "Tail")
    state = solver.State(
        turn=3,
        library=cards,
        hand=(),
        battlefield=(solver.Perm(SAGA, counters=3, mode="landface"),),
        saga3_pending=True,
        rng_root_seed=20260822,
    )
    env, ctx, search = begin_saga3_search(state)
    assert env.true_state.saga3_pending is False
    assert isinstance(search, SearchZoneObservation)
    assert search.legal_cards == tuple(sorted(set(cards) & solver.SAGA_TARGETS))
    assert env.pending_decision is not None
    assert env.pending_decision.kind == "remaining_search_target"
    assert ctx.contingent_on == "saga3.trigger"


def test_saga_target_choice_occurs_after_observation_and_final_chapter_sacrifices_saga():
    state = solver.State(
        turn=3,
        library=("Sensei's Divining Top", "Tail"),
        hand=(),
        battlefield=(solver.Perm(SAGA, counters=3, mode="landface"),),
        saga3_pending=True,
        rng_root_seed=20260822,
    )
    info = InformationState()
    env, ctx, search = begin_saga3_search(state)
    req = saga3_target_request(env.true_state, info, ctx, search, horizon=6)
    target = choose_target(req, "Sensei's Divining Top")
    final = resolve_saga3_target(env.true_state, ctx, search, target)
    assert any(p.name == "Sensei's Divining Top" for p in final.true_state.battlefield)
    assert not any(p.name == SAGA for p in final.true_state.battlefield)
    assert SAGA in final.true_state.graveyard


def test_scour_modes_and_graveyard_target_are_committed_before_library_search():
    cards = ("Mana Vault", "Basalt Monolith", "Tail")
    base = solver.State(
        turn=3,
        library=cards,
        hand=(SCOUR,),
        battlefield=(),
        graveyard=("Sensei's Divining Top",),
        blue=1,
        colorless=3,
        rng_root_seed=20260822,
    )
    other = replace(base, library=tuple(reversed(cards)))
    info = InformationState()
    req_a = scour_cast_request(base, info, horizon=6)
    req_b = scour_cast_request(other, info, horizon=6)
    assert req_a.observation == req_b.observation
    assert tuple(a.canonical_key() for a in req_a.actions) == tuple(
        a.canonical_key() for a in req_b.actions
    )
    modes = {(dict(a.parameters)["mode"], dict(a.parameters)["graveyard_target"]) for a in req_a.actions}
    assert ("library", "") in modes
    assert ("graveyard", "Sensei's Divining Top") in modes
    assert ("both", "Sensei's Divining Top") in modes
    assert all("Mana Vault" not in repr(a.parameters) for a in req_a.actions)


def test_scour_both_searches_then_returns_precommitted_graveyard_target():
    state = solver.State(
        turn=3,
        library=("Mana Vault", "Tail"),
        hand=(SCOUR,),
        battlefield=(),
        graveyard=("Sensei's Divining Top",),
        blue=1,
        colorless=3,
        rng_root_seed=20260822,
    )
    info = InformationState()
    root_req = scour_cast_request(state, info, horizon=6)
    both = choose_action(
        root_req,
        lambda p: p["mode"] == "both" and p["graveyard_target"] == "Sensei's Divining Top",
    )
    env, ctx, search = resolve_scour_cast(state, both)
    assert isinstance(search, SearchZoneObservation)
    assert search.legal_cards == ("Mana Vault",)
    req = scour_target_request(env.true_state, info, ctx, search, horizon=6)
    final = resolve_scour_target(
        env.true_state, ctx, search, choose_target(req, "Mana Vault")
    )
    assert "Mana Vault" in final.true_state.hand
    assert "Sensei's Divining Top" in final.true_state.hand
    assert "Sensei's Divining Top" not in final.true_state.graveyard
    assert any(isinstance(e, ShuffleObservation) for e in final.observations.events)


def test_scour_graveyard_only_has_no_hidden_library_decision():
    state = solver.State(
        turn=3,
        library=("Basalt Monolith", "Tail"),
        hand=(SCOUR,),
        battlefield=(),
        graveyard=("Mana Vault",),
        blue=1,
        colorless=3,
        rng_root_seed=20260822,
    )
    info = InformationState()
    req = scour_cast_request(state, info, horizon=6)
    action = choose_action(
        req, lambda p: p["mode"] == "graveyard" and p["graveyard_target"] == "Mana Vault"
    )
    final, ctx, search = resolve_scour_cast(state, action)
    assert ctx is None and search is None
    assert final.pending_decision is None
    assert "Mana Vault" in final.true_state.hand
    assert "Basalt Monolith" not in final.true_state.hand


def main():
    tests = [
        test_bay_commit_is_hidden_future_invariant_and_sacrifice_precedes_search,
        test_bay_target_only_appears_after_search_and_shuffle_resets_information,
        test_tezzeret_minus3_commit_is_hidden_future_invariant_and_loyalty_paid_first,
        test_tezzeret_target_to_hand_occurs_only_after_search,
        test_saga_pending_trigger_goes_directly_to_search_observation,
        test_saga_target_choice_occurs_after_observation_and_final_chapter_sacrifices_saga,
        test_scour_modes_and_graveyard_target_are_committed_before_library_search,
        test_scour_both_searches_then_returns_precommitted_graveyard_target,
        test_scour_graveyard_only_has_no_hidden_library_decision,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("REMAINING SEARCH ADAPTERS SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
