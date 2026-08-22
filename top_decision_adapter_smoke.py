#!/usr/bin/env python3
"""Focused Phase-1 tests for non-Oracle Sensei's Divining Top staging."""

import urza_solver as solver
from solver_architecture import InformationState, canonical_markov_state_key
from decision_observation import (
    DECISION_COMMIT,
    DECISION_POST_OBSERVATION,
    DecisionRequest,
    RevealTopObservation,
)
from top_decision_adapter import (
    TOP_ACTIVATE_ACTION_ID,
    information_after_top_activation,
    information_after_top_reorder,
    resolve_top_activation,
    resolve_top_reorder,
    top_activation_request,
    top_reorder_intents,
    top_reorder_request,
)


def base_state(library):
    return solver.State(
        turn=2,
        library=tuple(library),
        hand=("Island",),
        battlefield=(solver.Perm("Sensei's Divining Top"),),
        colorless=1,
        rng_root_seed=20260822,
    )


def choose_winner_first(request: DecisionRequest):
    """Tiny policy used only to prove post-observation sensitivity."""
    assert request.context.decision_stage == DECISION_POST_OBSERVATION
    def rank(action):
        order = dict(action.parameters)["order"]
        return (0 if order and order[0] == "Winner" else 1, tuple(order), action.action_id)
    return sorted(request.actions, key=rank)[0]


def test_top_commit_hidden_future_invariance():
    a = base_state(("Winner", "Blank", "Island", "Tail"))
    b = base_state(("Island", "Tail", "Blank", "Winner"))
    info = InformationState()

    req_a = top_activation_request(a, info, horizon=6, policy_id="test")
    req_b = top_activation_request(b, info, horizon=6, policy_id="test")

    assert req_a.observation == req_b.observation, "PolicyView changed with hidden library"
    assert tuple(x.canonical_key() for x in req_a.actions) == tuple(
        x.canonical_key() for x in req_b.actions
    ), "pre-look Top actions depended on unknown top cards"
    assert len(req_a.actions) == 1
    action = req_a.actions[0]
    assert action.action_id == TOP_ACTIVATE_ACTION_ID
    assert action.decision_stage == DECISION_COMMIT
    assert "Winner" not in repr(action.parameters)
    assert "Blank" not in repr(action.parameters)


def test_top_reorder_is_unavailable_before_reveal():
    assert top_reorder_intents(InformationState()) == ()


def test_top_activation_emits_typed_reveal_then_contingent_decision():
    state = base_state(("Winner", "Blank", "Island", "Tail"))
    prior = InformationState()
    commit = top_activation_request(state, prior, horizon=6).actions[0]
    envelope = resolve_top_activation(state, commit)

    assert envelope.pending_decision is not None
    assert envelope.pending_decision.kind == "top_reorder"
    assert envelope.pending_decision.decision_stage == DECISION_POST_OBSERVATION
    assert len(envelope.observations.events) == 1
    event = envelope.observations.events[0]
    assert isinstance(event, RevealTopObservation)
    assert event.cards == ("Winner", "Blank", "Island")

    info = information_after_top_activation(prior, envelope)
    assert info.known_top == ("Winner", "Blank", "Island")
    request = top_reorder_request(envelope.true_state, info, horizon=6)
    assert request.context.decision_stage == DECISION_POST_OBSERVATION
    assert len(request.actions) == 6
    assert all(dict(action.parameters)["order"] for action in request.actions)


def test_post_observation_top_order_can_depend_on_revealed_cards():
    # The root commitment is identical. Only after each actual reveal may the
    # contingent policy make a different ordering decision.
    state_a = base_state(("Winner", "Blank", "Island", "Tail"))
    state_b = base_state(("Blank", "Island", "Tail", "Winner"))
    prior = InformationState()

    commit_a = top_activation_request(state_a, prior, horizon=6).actions[0]
    commit_b = top_activation_request(state_b, prior, horizon=6).actions[0]
    assert commit_a.canonical_key() == commit_b.canonical_key()

    env_a = resolve_top_activation(state_a, commit_a)
    env_b = resolve_top_activation(state_b, commit_b)
    info_a = information_after_top_activation(prior, env_a)
    info_b = information_after_top_activation(prior, env_b)
    req_a = top_reorder_request(env_a.true_state, info_a, horizon=6)
    req_b = top_reorder_request(env_b.true_state, info_b, horizon=6)

    chosen_a = choose_winner_first(req_a)
    chosen_b = choose_winner_first(req_b)
    order_a = dict(chosen_a.parameters)["order"]
    order_b = dict(chosen_b.parameters)["order"]

    assert order_a[0] == "Winner"
    assert "Winner" not in order_b, "second reveal unexpectedly exposed hidden fourth card"
    assert order_a != order_b


def test_top_reorder_matches_oracle_physical_transition():
    state = base_state(("Winner", "Blank", "Island", "Tail"))
    prior = InformationState()
    commit = top_activation_request(state, prior, horizon=6).actions[0]
    activated = resolve_top_activation(state, commit)
    info = information_after_top_activation(prior, activated)
    request = top_reorder_request(activated.true_state, info, horizon=6)

    target_order = ("Island", "Winner", "Blank")
    chosen = next(
        action for action in request.actions
        if dict(action.parameters)["order"] == target_order
    )
    resolved = resolve_top_reorder(activated.true_state, info, chosen)
    final_info = information_after_top_reorder(info, resolved)
    assert resolved.true_state.library[:3] == target_order
    assert final_info.known_top == target_order

    oracle_successors = solver.top_actions(state)
    matching = [
        candidate for candidate in oracle_successors
        if tuple(candidate.library[:3]) == target_order
        and len(candidate.library) == len(state.library)
    ]
    assert matching, "Oracle Top reorder did not contain the chosen legal order"
    assert canonical_markov_state_key(resolved.true_state) == canonical_markov_state_key(
        matching[0]
    ), "non-Oracle staged Top transition changed physical rules semantics"


def test_top_reorder_preserves_previously_known_deeper_card():
    state = base_state(("Winner", "Blank", "Island", "Known Fourth", "Tail"))
    prior = InformationState(
        known_top=("Winner", "Blank", "Island", "Known Fourth")
    )
    commit = top_activation_request(state, prior, horizon=6).actions[0]
    activated = resolve_top_activation(state, commit)
    info = information_after_top_activation(prior, activated)
    assert info.known_top == ("Winner", "Blank", "Island", "Known Fourth")

    request = top_reorder_request(activated.true_state, info, horizon=6)
    target_order = ("Island", "Winner", "Blank")
    chosen = next(
        action for action in request.actions
        if dict(action.parameters)["order"] == target_order
    )
    resolved = resolve_top_reorder(activated.true_state, info, chosen)
    final_info = information_after_top_reorder(info, resolved)
    assert resolved.true_state.library[:4] == target_order + ("Known Fourth",)
    assert final_info.known_top == target_order + ("Known Fourth",)


def test_duplicate_top_cards_have_deterministic_unique_orders():
    info = InformationState(known_top=("Island", "Island", "Winner"))
    actions = top_reorder_intents(info)
    orders = tuple(dict(action.parameters)["order"] for action in actions)
    assert orders == tuple(sorted(set(orders)))
    assert len(orders) == 3


def main():
    tests = [
        test_top_commit_hidden_future_invariance,
        test_top_reorder_is_unavailable_before_reveal,
        test_top_activation_emits_typed_reveal_then_contingent_decision,
        test_post_observation_top_order_can_depend_on_revealed_cards,
        test_top_reorder_matches_oracle_physical_transition,
        test_top_reorder_preserves_previously_known_deeper_card,
        test_duplicate_top_cards_have_deterministic_unique_orders,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("TOP DECISION ADAPTER SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
