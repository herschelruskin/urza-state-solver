#!/usr/bin/env python3
"""Focused Phase-1 regressions for staged simple tutor/search decisions."""

from dataclasses import replace

import urza_solver as solver
from solver_architecture import InformationState, canonical_markov_state_key
from decision_observation import (
    DECISION_COMMIT,
    DECISION_POST_OBSERVATION,
    SearchZoneObservation,
    ShuffleObservation,
    MoveKnownCardObservation,
)
from tutor_decision_adapter import (
    information_after_tutor_search,
    information_after_tutor_target,
    resolve_simple_tutor_commit,
    resolve_tutor_target,
    simple_tutor_commit_request,
    tutor_target_intents,
    tutor_target_request,
)


def state_with_hand(source, library, *, blue=4, colorless=4):
    return solver.State(
        turn=2,
        library=tuple(library),
        hand=(source, "Island"),
        battlefield=(),
        blue=blue,
        colorless=colorless,
        rng_root_seed=20260822,
    )


def choose_source(request, source):
    return next(action for action in request.actions if action.source == source)


def choose_target(request, target):
    return next(
        action for action in request.actions
        if dict(action.parameters).get("target") == target
    )


def oracle_simple_match(state, source, target):
    candidates = solver.simple_tutor_actions(state)
    if source == "Mystical Tutor":
        marker = f"Mystical -> shuffle, then top {target}"
    elif source == "Spellseeker":
        marker = f"Spellseeker ETB -> {target}"
    else:
        marker = f"{source} -> {target}"
    matches = [candidate for candidate in candidates if candidate.trace and candidate.trace[-1] == marker]
    assert matches, f"Oracle simple tutor transition missing {marker!r}"
    return matches[0]


def test_tutor_use_hidden_permutation_invariance():
    cards_a = (
        "Dramatic Reversal",
        "Merchant Scroll",
        "Mystical Tutor",
        "Sensei's Divining Top",
        "Island",
    )
    cards_b = tuple(reversed(cards_a))
    a = state_with_hand("Mystical Tutor", cards_a)
    b = state_with_hand("Mystical Tutor", cards_b)
    info = InformationState()

    req_a = simple_tutor_commit_request(a, info, horizon=6, policy_id="phase1")
    req_b = simple_tutor_commit_request(b, info, horizon=6, policy_id="phase1")

    assert req_a.observation == req_b.observation
    assert tuple(action.canonical_key() for action in req_a.actions) == tuple(
        action.canonical_key() for action in req_b.actions
    )
    mystical = choose_source(req_a, "Mystical Tutor")
    assert mystical.decision_stage == DECISION_COMMIT
    assert "Dramatic Reversal" not in repr(mystical.parameters)
    assert "Merchant Scroll" not in repr(mystical.parameters)


def test_target_choices_do_not_exist_until_search_observation():
    assert tutor_target_intents(
        type("NoSearch", (), {"pending_decision": None, "observations": type("B", (), {"events": ()})()})()
    ) == ()


def test_commit_emits_search_observation_then_target_request():
    state = state_with_hand(
        "Mystical Tutor",
        ("Dramatic Reversal", "Merchant Scroll", "Island", "Sensei's Divining Top"),
    )
    prior = InformationState(known_top=("Dramatic Reversal",), known_bottom=("Island",))
    request = simple_tutor_commit_request(state, prior, horizon=6)
    commit = choose_source(request, "Mystical Tutor")
    envelope = resolve_simple_tutor_commit(state, commit)

    assert envelope.pending_decision is not None
    assert envelope.pending_decision.decision_stage == DECISION_POST_OBSERVATION
    events = envelope.observations.events
    assert len(events) == 1
    assert isinstance(events[0], SearchZoneObservation)
    assert events[0].context == "Mystical Tutor"
    assert "Dramatic Reversal" in events[0].legal_cards

    info = information_after_tutor_search(prior, envelope)
    assert info == prior, "search target list should be ephemeral hidden-zone information"
    target_request = tutor_target_request(envelope.true_state, info, envelope, horizon=6)
    assert target_request.context.decision_stage == DECISION_POST_OBSERVATION
    assert any(dict(action.parameters).get("target") == "Dramatic Reversal" for action in target_request.actions)


def test_same_multiset_different_order_exposes_same_target_set_after_commit():
    cards = (
        "Dramatic Reversal",
        "Merchant Scroll",
        "Gitaxian Probe",
        "Island",
    )
    a = state_with_hand("Mystical Tutor", cards)
    b = state_with_hand("Mystical Tutor", (cards[2], cards[0], cards[3], cards[1]))
    prior = InformationState()

    commit_a = choose_source(simple_tutor_commit_request(a, prior, horizon=6), "Mystical Tutor")
    commit_b = choose_source(simple_tutor_commit_request(b, prior, horizon=6), "Mystical Tutor")
    env_a = resolve_simple_tutor_commit(a, commit_a)
    env_b = resolve_simple_tutor_commit(b, commit_b)

    event_a = env_a.observations.events[0]
    event_b = env_b.observations.events[0]
    assert isinstance(event_a, SearchZoneObservation)
    assert isinstance(event_b, SearchZoneObservation)
    assert event_a.legal_cards == event_b.legal_cards
    assert tuple(action.strategic_key() for action in tutor_target_intents(env_a)) == tuple(
        action.strategic_key() for action in tutor_target_intents(env_b)
    )


def test_mystical_shuffle_then_known_top_information_semantics():
    state = state_with_hand(
        "Mystical Tutor",
        ("Dramatic Reversal", "Merchant Scroll", "Gitaxian Probe", "Island"),
    )
    prior = InformationState(
        known_top=("Dramatic Reversal",),
        known_bottom=("Island",),
        shuffle_epoch=4,
    )
    commit = choose_source(simple_tutor_commit_request(state, prior, horizon=6), "Mystical Tutor")
    search = resolve_simple_tutor_commit(state, commit)
    after_search = information_after_tutor_search(prior, search)
    request = tutor_target_request(search.true_state, after_search, search, horizon=6)
    chosen = choose_target(request, "Dramatic Reversal")
    resolved = resolve_tutor_target(search.true_state, search, chosen)

    assert isinstance(resolved.observations.events[0], ShuffleObservation)
    assert isinstance(resolved.observations.events[1], MoveKnownCardObservation)
    final_info = information_after_tutor_target(after_search, resolved)
    assert final_info.known_top == ("Dramatic Reversal",)
    assert final_info.known_bottom == ()
    assert final_info.shuffle_epoch == 5
    assert resolved.true_state.library[0] == "Dramatic Reversal"


def test_hand_tutor_shuffle_clears_positional_knowledge():
    state = state_with_hand(
        "Merchant Scroll",
        ("Mystical Tutor", "Dramatic Reversal", "Island", "Sensei's Divining Top"),
    )
    prior = InformationState(known_top=("Mystical Tutor",), known_bottom=("Sensei's Divining Top",), shuffle_epoch=2)
    commit = choose_source(simple_tutor_commit_request(state, prior, horizon=6), "Merchant Scroll")
    search = resolve_simple_tutor_commit(state, commit)
    after_search = information_after_tutor_search(prior, search)
    request = tutor_target_request(search.true_state, after_search, search, horizon=6)
    chosen = choose_target(request, "Mystical Tutor")
    resolved = resolve_tutor_target(search.true_state, search, chosen)
    final_info = information_after_tutor_target(after_search, resolved)

    assert final_info.known_top == ()
    assert final_info.known_bottom == ()
    assert final_info.shuffle_epoch == 3
    assert "Mystical Tutor" in resolved.true_state.hand


def test_dizzy_target_resolution_matches_oracle_physical_state():
    state = state_with_hand(
        "Dizzy Spell",
        ("Mystical Tutor", "Sensei's Divining Top", "Dramatic Reversal", "Island"),
    )
    prior = InformationState()
    commit = choose_source(simple_tutor_commit_request(state, prior, horizon=6), "Dizzy Spell")
    search = resolve_simple_tutor_commit(state, commit)
    info = information_after_tutor_search(prior, search)
    request = tutor_target_request(search.true_state, info, search, horizon=6)
    chosen = choose_target(request, "Mystical Tutor")
    resolved = resolve_tutor_target(search.true_state, search, chosen)
    oracle = oracle_simple_match(state, "Dizzy Spell", "Mystical Tutor")
    assert canonical_markov_state_key(resolved.true_state) == canonical_markov_state_key(oracle)


def test_merchant_target_resolution_matches_oracle_physical_state():
    state = state_with_hand(
        "Merchant Scroll",
        ("Mystical Tutor", "Dramatic Reversal", "Island", "Sensei's Divining Top"),
    )
    prior = InformationState()
    commit = choose_source(simple_tutor_commit_request(state, prior, horizon=6), "Merchant Scroll")
    search = resolve_simple_tutor_commit(state, commit)
    info = information_after_tutor_search(prior, search)
    request = tutor_target_request(search.true_state, info, search, horizon=6)
    chosen = choose_target(request, "Mystical Tutor")
    resolved = resolve_tutor_target(search.true_state, search, chosen)
    oracle = oracle_simple_match(state, "Merchant Scroll", "Mystical Tutor")
    assert canonical_markov_state_key(resolved.true_state) == canonical_markov_state_key(oracle)


def test_mystical_target_resolution_matches_oracle_physical_state():
    state = state_with_hand(
        "Mystical Tutor",
        ("Dramatic Reversal", "Merchant Scroll", "Gitaxian Probe", "Island"),
    )
    prior = InformationState()
    commit = choose_source(simple_tutor_commit_request(state, prior, horizon=6), "Mystical Tutor")
    search = resolve_simple_tutor_commit(state, commit)
    info = information_after_tutor_search(prior, search)
    request = tutor_target_request(search.true_state, info, search, horizon=6)
    chosen = choose_target(request, "Dramatic Reversal")
    resolved = resolve_tutor_target(search.true_state, search, chosen)
    oracle = oracle_simple_match(state, "Mystical Tutor", "Dramatic Reversal")
    assert canonical_markov_state_key(resolved.true_state) == canonical_markov_state_key(oracle)


def test_spellseeker_target_resolution_matches_oracle_physical_state():
    state = solver.State(
        turn=2,
        library=("Dramatic Reversal", "Mystical Tutor", "Island", "Sensei's Divining Top"),
        hand=("Island",),
        battlefield=(solver.Perm("Spellseeker"),),
        blue=1,
        rng_root_seed=20260822,
    )
    prior = InformationState()
    commit = choose_source(simple_tutor_commit_request(state, prior, horizon=6), "Spellseeker")
    search = resolve_simple_tutor_commit(state, commit)
    info = information_after_tutor_search(prior, search)
    request = tutor_target_request(search.true_state, info, search, horizon=6)
    chosen = choose_target(request, "Dramatic Reversal")
    resolved = resolve_tutor_target(search.true_state, search, chosen)
    oracle = oracle_simple_match(state, "Spellseeker", "Dramatic Reversal")
    assert canonical_markov_state_key(resolved.true_state) == canonical_markov_state_key(oracle)


def main():
    tests = [
        test_tutor_use_hidden_permutation_invariance,
        test_target_choices_do_not_exist_until_search_observation,
        test_commit_emits_search_observation_then_target_request,
        test_same_multiset_different_order_exposes_same_target_set_after_commit,
        test_mystical_shuffle_then_known_top_information_semantics,
        test_hand_tutor_shuffle_clears_positional_knowledge,
        test_dizzy_target_resolution_matches_oracle_physical_state,
        test_merchant_target_resolution_matches_oracle_physical_state,
        test_mystical_target_resolution_matches_oracle_physical_state,
        test_spellseeker_target_resolution_matches_oracle_physical_state,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("TUTOR DECISION ADAPTER SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
