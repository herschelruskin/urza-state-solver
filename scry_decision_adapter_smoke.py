#!/usr/bin/env python3
"""Focused Phase-1 regressions for staged non-Oracle scry decisions."""

from dataclasses import replace

import urza_solver as solver
from solver_architecture import InformationState, canonical_markov_state_key
from decision_observation import DECISION_COMMIT, DECISION_POST_OBSERVATION, RevealTopObservation
from information_state_propagation import validate_information_against_state
from scry_decision_adapter import (
    SCRY_CHOICE_KIND,
    ScrySourceSpec,
    information_after_scry_choice,
    information_after_scry_reveal,
    resolve_scry_choice,
    resolve_scry_commit,
    scry_choice_intents,
    scry_choice_request,
    scry_commit_request,
)


def base_state(library):
    return solver.State(
        turn=2,
        library=tuple(library),
        hand=("Island",),
        battlefield=(),
        blue=1,
        rng_root_seed=20260822,
    )


def spec(count=2):
    return ScrySourceSpec("Witching Well", count, "witching-well-etb-1")


def test_scry_commit_hidden_future_invariance():
    a = base_state(("Grinding Station", "Blank", "Tail A", "Tail B"))
    b = base_state(("Island", "Tail B", "Blank", "Grinding Station"))
    info = InformationState()

    req_a = scry_commit_request(a, info, spec(), horizon=6, policy_id="test")
    req_b = scry_commit_request(b, info, spec(), horizon=6, policy_id="test")

    assert req_a.observation == req_b.observation
    assert req_a.context.decision_stage == DECISION_COMMIT
    assert tuple(x.canonical_key() for x in req_a.actions) == tuple(
        x.canonical_key() for x in req_b.actions
    )
    assert len(req_a.actions) == 1
    action = req_a.actions[0]
    assert "Grinding Station" not in repr(action.parameters)
    assert "Blank" not in repr(action.parameters)


def test_scry_choices_do_not_exist_without_revealed_cards():
    assert scry_choice_intents(InformationState(), spec(), revealed_count=2) == ()


def test_scry_commit_emits_typed_reveal_and_contingent_choice():
    state = base_state(("Grinding Station", "Blank", "Tail A", "Tail B"))
    prior = InformationState()
    commit = scry_commit_request(state, prior, spec(), horizon=6).actions[0]
    envelope = resolve_scry_commit(state, spec(), commit)

    assert envelope.pending_decision is not None
    assert envelope.pending_decision.kind == SCRY_CHOICE_KIND
    assert envelope.pending_decision.decision_stage == DECISION_POST_OBSERVATION
    assert len(envelope.observations.events) == 1
    event = envelope.observations.events[0]
    assert isinstance(event, RevealTopObservation)
    assert event.cards == ("Grinding Station", "Blank")

    info = information_after_scry_reveal(prior, envelope)
    assert info.known_top == ("Grinding Station", "Blank")
    request = scry_choice_request(
        envelope.true_state,
        info,
        spec(),
        revealed_count=2,
        horizon=6,
    )
    assert request.context.decision_stage == DECISION_POST_OBSERVATION
    # Two distinct cards: (N+1) * N! = 6 unique top/bottom/order results.
    assert len(request.actions) == 6


def test_post_observation_scry_choice_can_depend_on_revealed_cards():
    state_a = base_state(("Grinding Station", "Blank", "Tail", "Island"))
    state_b = base_state(("Island", "Blank", "Tail", "Grinding Station"))
    prior = InformationState()

    commit_a = scry_commit_request(state_a, prior, spec(), horizon=6).actions[0]
    commit_b = scry_commit_request(state_b, prior, spec(), horizon=6).actions[0]
    assert commit_a.canonical_key() == commit_b.canonical_key()

    env_a = resolve_scry_commit(state_a, spec(), commit_a)
    env_b = resolve_scry_commit(state_b, spec(), commit_b)
    info_a = information_after_scry_reveal(prior, env_a)
    info_b = information_after_scry_reveal(prior, env_b)

    choices_a = {
        (dict(action.parameters)["top"], dict(action.parameters)["bottom"])
        for action in scry_choice_intents(info_a, spec(), revealed_count=2)
    }
    choices_b = {
        (dict(action.parameters)["top"], dict(action.parameters)["bottom"])
        for action in scry_choice_intents(info_b, spec(), revealed_count=2)
    }
    assert choices_a != choices_b
    assert any("Grinding Station" in top + bottom for top, bottom in choices_a)
    assert all("Grinding Station" not in top + bottom for top, bottom in choices_b)


def test_scry_choice_matches_current_oracle_apply_scry_physical_result():
    state = base_state(("Grinding Station", "Blank", "Tail A", "Tail B"))
    prior = InformationState()
    commit = scry_commit_request(state, prior, spec(), horizon=6).actions[0]
    revealed = resolve_scry_commit(state, spec(), commit)
    info = information_after_scry_reveal(prior, revealed)
    actions = scry_choice_intents(info, spec(), revealed_count=2)

    # Current Oracle policy keeps Grinding Station (priority >=45) and bottoms Blank.
    chosen = next(
        action for action in actions
        if dict(action.parameters)["top"] == ("Grinding Station",)
        and dict(action.parameters)["bottom"] == ("Blank",)
    )
    resolved = resolve_scry_choice(revealed.true_state, info, spec(), chosen)
    final_info = information_after_scry_choice(info, resolved)
    validate_information_against_state(final_info, resolved.true_state)

    oracle = solver.apply_scry(state, 2, "Witching Well")
    assert canonical_markov_state_key(resolved.true_state) == canonical_markov_state_key(oracle)


def test_scry_preserves_deeper_known_top_and_appends_below_london_bottom():
    state = base_state((
        "Grinding Station",
        "Blank",
        "Known Deep",
        "Tail",
        "London A",
        "London B",
    ))
    prior = InformationState(
        known_top=("Grinding Station", "Blank", "Known Deep"),
        known_bottom=("London A", "London B"),
    )
    validate_information_against_state(prior, state)

    commit = scry_commit_request(state, prior, spec(), horizon=6).actions[0]
    reveal = resolve_scry_commit(state, spec(), commit)
    info = information_after_scry_reveal(prior, reveal)
    chosen = next(
        action for action in scry_choice_intents(info, spec(), revealed_count=2)
        if dict(action.parameters)["top"] == ("Grinding Station",)
        and dict(action.parameters)["bottom"] == ("Blank",)
    )
    resolved = resolve_scry_choice(reveal.true_state, info, spec(), chosen)
    final_info = information_after_scry_choice(info, resolved)

    assert resolved.true_state.library == (
        "Grinding Station",
        "Known Deep",
        "Tail",
        "London A",
        "London B",
        "Blank",
    )
    assert final_info.known_top == ("Grinding Station", "Known Deep")
    assert final_info.known_bottom == ("London A", "London B", "Blank")
    validate_information_against_state(final_info, resolved.true_state)


def test_scry_one_has_exact_keep_or_bottom_choices():
    one = ScrySourceSpec("Artificer's Assistant", 1, "assistant-trigger-1")
    info = InformationState(known_top=("Island",))
    actions = scry_choice_intents(info, one, revealed_count=1)
    results = {
        (dict(action.parameters)["top"], dict(action.parameters)["bottom"])
        for action in actions
    }
    assert results == {
        (("Island",), ()),
        ((), ("Island",)),
    }


def test_duplicate_scry_cards_have_deterministic_unique_results():
    info = InformationState(known_top=("Island", "Island"))
    actions = scry_choice_intents(info, spec(), revealed_count=2)
    keys = tuple(action.canonical_key() for action in actions)
    assert len(keys) == len(set(keys))
    # all top, split 1/1, all bottom = 3 unique results for duplicate names
    assert len(actions) == 3


def main():
    tests = [
        test_scry_commit_hidden_future_invariance,
        test_scry_choices_do_not_exist_without_revealed_cards,
        test_scry_commit_emits_typed_reveal_and_contingent_choice,
        test_post_observation_scry_choice_can_depend_on_revealed_cards,
        test_scry_choice_matches_current_oracle_apply_scry_physical_result,
        test_scry_preserves_deeper_known_top_and_appends_below_london_bottom,
        test_scry_one_has_exact_keep_or_bottom_choices,
        test_duplicate_scry_cards_have_deterministic_unique_results,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("SCRY DECISION ADAPTER SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
