#!/usr/bin/env python3
"""Focused Phase-1 regressions for staged Reshape / Whir X searches."""

from dataclasses import replace

import urza_solver as solver
from solver_architecture import InformationState, canonical_markov_state_key
from decision_observation import SearchZoneObservation, ShuffleObservation
from x_artifact_search_adapter import (
    RESHAPE,
    WHIR,
    information_after_x_search_transition,
    reshape_cast_request,
    reshape_target_request,
    resolve_reshape_cast,
    resolve_reshape_target,
    resolve_whir_cast,
    resolve_whir_target,
    whir_cast_request,
    whir_target_request,
)


def clue():
    return solver.Perm("Clue", mode="clue")


def choose_reshape_cast(request, x, sacrifice_name="Clue"):
    for action in request.actions:
        params = dict(action.parameters)
        sac = tuple(params["sacrifice"])
        if int(params["x"]) == x and sac[0] == sacrifice_name:
            return action
    raise AssertionError(f"no Reshape X={x} sacrifice={sacrifice_name} action")


def choose_whir_cast(request, x, *, improvise_names=(), floating_generic=None):
    wanted = tuple(sorted(improvise_names))
    for action in request.actions:
        params = dict(action.parameters)
        slots = tuple(tuple(raw) for raw in params["improvise"])
        names = tuple(sorted(slot[0] for slot in slots))
        if int(params["x"]) != x or names != wanted:
            continue
        if floating_generic is not None and int(params["floating_generic"]) != floating_generic:
            continue
        return action
    raise AssertionError(
        f"no Whir X={x} improvise={wanted} floating={floating_generic} action"
    )


def choose_target(request, target):
    return next(
        action
        for action in request.actions
        if dict(action.parameters).get("target") == target
    )


def public_physical_key(state):
    """Compare physical non-library state while ignoring trace and hidden shuffle tape."""
    return canonical_markov_state_key(replace(state, library=(), trace=()))


def test_reshape_commit_is_hidden_future_invariant():
    cards = ("Mana Vault", "Basalt Monolith", "Sensei's Divining Top", "Tail")
    a = solver.State(
        turn=2,
        library=cards,
        hand=(RESHAPE,),
        battlefield=(clue(),),
        blue=2,
        colorless=2,
        rng_root_seed=20260822,
    )
    b = replace(a, library=tuple(reversed(cards)))
    info = InformationState()
    req_a = reshape_cast_request(a, info, horizon=6, policy_id="smoke")
    req_b = reshape_cast_request(b, info, horizon=6, policy_id="smoke")
    assert req_a.observation == req_b.observation
    assert tuple(x.canonical_key() for x in req_a.actions) == tuple(
        x.canonical_key() for x in req_b.actions
    )
    assert req_a.actions
    assert all("Mana Vault" not in repr(action.parameters) for action in req_a.actions)
    assert all("Basalt Monolith" not in repr(action.parameters) for action in req_a.actions)


def test_reshape_x_and_sacrifice_are_committed_before_search():
    state = solver.State(
        turn=2,
        library=("Mana Vault", "Basalt Monolith", "Tail"),
        hand=(RESHAPE,),
        battlefield=(clue(),),
        blue=2,
        colorless=1,
        rng_root_seed=20260822,
    )
    info = InformationState()
    cast = choose_reshape_cast(
        reshape_cast_request(state, info, horizon=6), 1, "Clue"
    )
    envelope, context, search = resolve_reshape_cast(state, cast)
    assert context.x == 1
    assert isinstance(search, SearchZoneObservation)
    assert search.legal_cards == ("Mana Vault",)
    assert "Basalt Monolith" not in search.legal_cards
    assert not any(p.mode == "clue" for p in envelope.true_state.battlefield)
    assert RESHAPE in envelope.true_state.graveyard
    assert envelope.pending_decision is not None
    assert envelope.pending_decision.kind == "x_artifact_search_target"


def test_reshape_sacrifice_identity_survives_payment_annotation_change():
    state = solver.State(
        turn=2,
        library=("Mana Vault", "Tail"),
        hand=(RESHAPE,),
        battlefield=(
            solver.Perm(
                "Grinding Station", tapped=True, producer_urza_ready=True
            ),
        ),
        blue=2,
        colorless=0,
        rng_root_seed=20260822,
    )
    info = InformationState()
    cast = choose_reshape_cast(
        reshape_cast_request(state, info, horizon=6), 0, "Grinding Station"
    )
    envelope, _, _ = resolve_reshape_cast(state, cast)
    assert not any(p.name == "Grinding Station" for p in envelope.true_state.battlefield)
    print("Reshape sacrifice survives payment-side annotation change: PASS")


def test_reshape_search_cannot_retroactively_raise_x_for_hidden_target():
    state = solver.State(
        turn=2,
        library=("Basalt Monolith", "Tail"),
        hand=(RESHAPE,),
        battlefield=(clue(),),
        blue=2,
        colorless=3,
        rng_root_seed=20260822,
    )
    info = InformationState()
    cast = choose_reshape_cast(reshape_cast_request(state, info, horizon=6), 1)
    envelope, context, search = resolve_reshape_cast(state, cast)
    request = reshape_target_request(
        envelope.true_state, info, context, search, horizon=6
    )
    targets = tuple(dict(action.parameters)["target"] for action in request.actions)
    assert targets == ("",), targets
    assert context.x == 1


def test_whir_commit_is_hidden_future_invariant():
    cards = ("Mana Vault", "Basalt Monolith", "Sensei's Divining Top", "Tail")
    a = solver.State(
        turn=2,
        library=cards,
        hand=(WHIR,),
        battlefield=(solver.Perm("Sol Ring"),),
        blue=3,
        colorless=1,
        rng_root_seed=20260822,
    )
    b = replace(a, library=(cards[3], cards[1], cards[0], cards[2]))
    info = InformationState()
    req_a = whir_cast_request(a, info, horizon=6, policy_id="smoke")
    req_b = whir_cast_request(b, info, horizon=6, policy_id="smoke")
    assert req_a.observation == req_b.observation
    assert tuple(x.canonical_key() for x in req_a.actions) == tuple(
        x.canonical_key() for x in req_b.actions
    )
    assert req_a.actions
    assert all("Mana Vault" not in repr(action.parameters) for action in req_a.actions)
    assert all("Basalt Monolith" not in repr(action.parameters) for action in req_a.actions)


def test_whir_improvise_plan_is_committed_before_search():
    state = solver.State(
        turn=2,
        library=("Mana Vault", "Basalt Monolith", "Tail"),
        hand=(WHIR,),
        battlefield=(
            solver.Perm("Sol Ring"),
            solver.Perm("Sensei's Divining Top"),
        ),
        blue=3,
        colorless=0,
        rng_root_seed=20260822,
    )
    info = InformationState()
    request = whir_cast_request(state, info, horizon=6)
    cast = choose_whir_cast(
        request,
        2,
        improvise_names=("Sol Ring", "Sensei's Divining Top"),
        floating_generic=0,
    )
    envelope, context, search = resolve_whir_cast(state, cast)
    assert context.x == 2
    assert all(p.tapped for p in envelope.true_state.battlefield)
    assert isinstance(search, SearchZoneObservation)
    assert "Mana Vault" in search.legal_cards
    assert "Basalt Monolith" not in search.legal_cards


def test_whir_duplicate_improvise_slots_survive_first_tap():
    state = solver.State(
        turn=2,
        library=("Grim Monolith", "Tail"),
        hand=(WHIR,),
        battlefield=(clue(), clue()),
        blue=3,
        colorless=0,
        rng_root_seed=20260822,
    )
    request = whir_cast_request(state, InformationState(), horizon=6)
    cast = choose_whir_cast(
        request, 2, improvise_names=("Clue", "Clue"), floating_generic=0
    )
    envelope, _, _ = resolve_whir_cast(state, cast)
    assert len(envelope.true_state.battlefield) == 2
    assert all(p.tapped for p in envelope.true_state.battlefield)
    print("Whir duplicate improvise slots remain addressable: PASS")


def test_whir_exposes_distinct_public_payment_plans_without_hidden_target():
    state = solver.State(
        turn=2,
        library=("Mana Vault", "Tail"),
        hand=(WHIR,),
        battlefield=(solver.Perm("Sol Ring"),),
        blue=3,
        colorless=1,
        rng_root_seed=20260822,
    )
    request = whir_cast_request(state, InformationState(), horizon=6)
    no_improvise = choose_whir_cast(
        request, 1, improvise_names=(), floating_generic=1
    )
    improvise = choose_whir_cast(
        request, 1, improvise_names=("Sol Ring",), floating_generic=0
    )
    assert no_improvise.canonical_key() != improvise.canonical_key()
    assert "Mana Vault" not in repr(no_improvise.parameters)
    assert "Mana Vault" not in repr(improvise.parameters)


def test_post_search_target_choice_uses_only_revealed_eligible_set():
    state = solver.State(
        turn=2,
        library=("Mana Vault", "Basalt Monolith", "Tail"),
        hand=(WHIR,),
        battlefield=(),
        blue=3,
        colorless=1,
        rng_root_seed=20260822,
    )
    info = InformationState()
    cast = choose_whir_cast(
        whir_cast_request(state, info, horizon=6),
        1,
        improvise_names=(),
        floating_generic=1,
    )
    envelope, context, search = resolve_whir_cast(state, cast)
    target_request = whir_target_request(
        envelope.true_state, info, context, search, horizon=6
    )
    targets = tuple(dict(action.parameters)["target"] for action in target_request.actions)
    assert targets == ("", "Mana Vault"), targets
    target = choose_target(target_request, "Mana Vault")
    final = resolve_whir_target(envelope.true_state, context, search, target)
    assert any(p.name == "Mana Vault" for p in final.true_state.battlefield)
    assert any(isinstance(event, ShuffleObservation) for event in final.observations.events)


def test_search_targets_share_pre_target_shuffle_ranking():
    state = solver.State(
        turn=2,
        library=(
            "Pithing Needle",
            "Grafdigger's Cage",
            "Mana Vault",
            "Tail",
        ),
        hand=(WHIR,),
        battlefield=(),
        blue=3,
        colorless=1,
        rng_root_seed=20260828,
    )
    info = InformationState()
    cast = choose_whir_cast(
        whir_cast_request(state, info, horizon=6),
        1,
        improvise_names=(),
        floating_generic=1,
    )
    envelope, context, search = resolve_whir_cast(state, cast)
    request = whir_target_request(
        envelope.true_state, info, context, search, horizon=6
    )

    fail = resolve_whir_target(
        envelope.true_state, context, search, choose_target(request, "")
    ).true_state
    needle = resolve_whir_target(
        envelope.true_state, context, search, choose_target(request, "Pithing Needle")
    ).true_state
    cage = resolve_whir_target(
        envelope.true_state, context, search, choose_target(request, "Grafdigger's Cage")
    ).true_state

    # Exact rules identity is preserved.
    assert any(p.name == "Pithing Needle" for p in needle.battlefield)
    assert not any(p.name == "Grafdigger's Cage" for p in needle.battlefield)
    assert any(p.name == "Grafdigger's Cage" for p in cage.battlefield)
    assert "Pithing Needle" not in needle.library
    assert "Grafdigger's Cage" not in cage.library

    # All branches are projections of one common random ranking: the no-find
    # branch is the shared full permutation, while each target branch is exactly
    # that same permutation with its selected physical card deleted.
    assert tuple(x for x in fail.library if x != "Pithing Needle") == needle.library
    assert tuple(x for x in fail.library if x != "Grafdigger's Cage") == cage.library
    assert tuple(x for x in needle.library if x != "Grafdigger's Cage") == tuple(
        x for x in cage.library if x != "Pithing Needle"
    )

    # Replaying the same target from the same pre-target state is deterministic.
    needle_again = resolve_whir_target(
        envelope.true_state, context, search, choose_target(request, "Pithing Needle")
    ).true_state
    assert needle_again.library == needle.library
    print("Shared pre-target search shuffle ranking preserves exact target identity: PASS")


def test_search_shuffle_clears_old_top_and_bottom_information():
    state = solver.State(
        turn=2,
        library=("Mana Vault", "Tail"),
        hand=(RESHAPE,),
        battlefield=(clue(),),
        blue=2,
        colorless=1,
        rng_root_seed=20260822,
    )
    prior = InformationState(
        known_top=("Mana Vault",),
        known_bottom=("Tail",),
        shuffle_epoch=4,
    )
    cast = choose_reshape_cast(reshape_cast_request(state, prior, horizon=6), 1)
    envelope, context, search = resolve_reshape_cast(state, cast)
    request = reshape_target_request(
        envelope.true_state, prior, context, search, horizon=6
    )
    final = resolve_reshape_target(
        envelope.true_state, context, search, choose_target(request, "Mana Vault")
    )
    updated = information_after_x_search_transition(prior, final)
    assert updated.known_top == ()
    assert updated.known_bottom == ()
    assert updated.shuffle_epoch == 5


def test_reshape_and_whir_match_oracle_nonlibrary_physical_result_for_same_line():
    reshape_state = solver.State(
        turn=2,
        library=("Mana Vault", "Basalt Monolith", "Tail"),
        hand=(RESHAPE,),
        battlefield=(clue(),),
        blue=2,
        colorless=1,
        rng_root_seed=20260822,
    )
    info = InformationState()
    rcast = choose_reshape_cast(reshape_cast_request(reshape_state, info, horizon=6), 1)
    renv, rctx, rsearch = resolve_reshape_cast(reshape_state, rcast)
    rreq = reshape_target_request(renv.true_state, info, rctx, rsearch, horizon=6)
    rfinal = resolve_reshape_target(
        renv.true_state, rctx, rsearch, choose_target(rreq, "Mana Vault")
    )
    r_oracle = next(
        st
        for st in solver.artifact_tutor_actions(reshape_state)
        if st.trace and st.trace[-1].startswith("Reshape X=1->Mana Vault")
    )
    assert public_physical_key(rfinal.true_state) == public_physical_key(r_oracle)

    whir_state = solver.State(
        turn=2,
        library=("Mana Vault", "Basalt Monolith", "Tail"),
        hand=(WHIR,),
        battlefield=(),
        blue=3,
        colorless=1,
        rng_root_seed=20260822,
    )
    wcast = choose_whir_cast(
        whir_cast_request(whir_state, info, horizon=6),
        1,
        improvise_names=(),
        floating_generic=1,
    )
    wenv, wctx, wsearch = resolve_whir_cast(whir_state, wcast)
    wreq = whir_target_request(wenv.true_state, info, wctx, wsearch, horizon=6)
    wfinal = resolve_whir_target(
        wenv.true_state, wctx, wsearch, choose_target(wreq, "Mana Vault")
    )
    w_oracle = next(
        st
        for st in solver.artifact_tutor_actions(whir_state)
        if st.trace and st.trace[-1] == "Whir X=1->Mana Vault"
    )
    assert public_physical_key(wfinal.true_state) == public_physical_key(w_oracle)


def main():
    tests = [
        test_reshape_commit_is_hidden_future_invariant,
        test_reshape_x_and_sacrifice_are_committed_before_search,
        test_reshape_sacrifice_identity_survives_payment_annotation_change,
        test_reshape_search_cannot_retroactively_raise_x_for_hidden_target,
        test_whir_commit_is_hidden_future_invariant,
        test_whir_improvise_plan_is_committed_before_search,
        test_whir_duplicate_improvise_slots_survive_first_tap,
        test_whir_exposes_distinct_public_payment_plans_without_hidden_target,
        test_post_search_target_choice_uses_only_revealed_eligible_set,
        test_search_targets_share_pre_target_shuffle_ranking,
        test_search_shuffle_clears_old_top_and_bottom_information,
        test_reshape_and_whir_match_oracle_nonlibrary_physical_result_for_same_line,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("X ARTIFACT SEARCH ADAPTER SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
