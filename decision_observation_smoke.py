#!/usr/bin/env python3
"""Focused Phase-1 decision / observation boundary regressions."""

from dataclasses import fields

from decision_observation import (
    ACTION_INTENT_VERSION,
    ActionIntent,
    DECISION_COMMIT,
    DECISION_POST_OBSERVATION,
    DecisionRequest,
    DrawObservation,
    LibraryPositionsObservation,
    MoveKnownCardObservation,
    ObservationBatch,
    PendingDecisionSpec,
    PolicyDecisionContext,
    PublicZoneChangeObservation,
    RevealTopObservation,
    SearchZoneObservation,
    ShuffleObservation,
    TransitionEnvelope,
    apply_observation_batch,
    apply_observation_event,
    observation_event_key,
    policy_surface_field_names,
)
from solver_architecture import InformationState, make_policy_view
from urza_solver import State


def base_state(**kwargs):
    values = dict(
        turn=2,
        library=("Hidden A", "Hidden B", "Hidden C", "Bottom A"),
        hand=("Island",),
        battlefield=(),
        blue=1,
        rng_root_seed=123456,
    )
    values.update(kwargs)
    return State(**values)


def test_action_intent_identity_is_deterministic_and_stage_sensitive():
    a = ActionIntent(
        "top-activate",
        "activate",
        parameters=(("mana", 1), ("source", "Sensei's Divining Top")),
        label="Activate Top",
    )
    b = ActionIntent(
        "top-activate",
        "activate",
        parameters=(("source", "Sensei's Divining Top"), ("mana", 1)),
        label="Different display label",
    )
    assert a.canonical_key() == b.canonical_key()
    assert a.canonical_key()[0] == ACTION_INTENT_VERSION

    post = ActionIntent(
        "top-activate",
        "activate",
        parameters=a.parameters,
        decision_stage=DECISION_POST_OBSERVATION,
    )
    assert a.canonical_key() != post.canonical_key()


def test_explicit_equivalence_does_not_merge_distinct_targets():
    top_a = ActionIntent(
        "tutor-route-a-top",
        "choose_tutor_target",
        equivalence_key=("target", "Sensei's Divining Top"),
        decision_stage=DECISION_POST_OBSERVATION,
    )
    top_b = ActionIntent(
        "tutor-route-b-top",
        "choose_tutor_target",
        equivalence_key=("target", "Sensei's Divining Top"),
        decision_stage=DECISION_POST_OBSERVATION,
    )
    cam = ActionIntent(
        "tutor-route-c-cam",
        "choose_tutor_target",
        equivalence_key=("target", "The Reality Chip"),
        decision_stage=DECISION_POST_OBSERVATION,
    )
    assert top_a.strategic_key() == top_b.strategic_key()
    assert top_a.strategic_key() != cam.strategic_key()


def test_policy_decision_surface_has_no_true_state_library_or_root_seed():
    state = base_state()
    view = make_policy_view(state, InformationState(known_top=("Hidden A",)))
    request = DecisionRequest(
        observation=view,
        actions=(ActionIntent("pass", "pass"),),
        context=PolicyDecisionContext(
            horizon=6,
            policy_id="phase1-smoke",
            decision_id="T2-main-1",
        ),
    )

    assert not hasattr(request.observation, "library")
    assert not hasattr(request.context, "root_seed")
    assert "root_seed" not in policy_surface_field_names()
    assert "true_state" not in policy_surface_field_names()
    assert "library" not in policy_surface_field_names()
    assert state.rng_root_seed == 123456  # exists only on rules-side state


def test_decision_request_rejects_mixed_commit_and_post_observation_actions():
    view = make_policy_view(base_state(), InformationState())
    try:
        DecisionRequest(
            observation=view,
            actions=(
                ActionIntent("commit", "activate", decision_stage=DECISION_COMMIT),
                ActionIntent(
                    "order",
                    "choose_order",
                    decision_stage=DECISION_POST_OBSERVATION,
                ),
            ),
            context=PolicyDecisionContext(horizon=6, decision_stage=DECISION_COMMIT),
        )
    except ValueError:
        return
    raise AssertionError("mixed decision stages were accepted in one policy request")


def test_draw_consumes_only_legally_known_top_prefix():
    info = InformationState(
        known_top=("A", "B"),
        known_bottom=("Z",),
        shuffle_epoch=3,
    )
    out = apply_observation_event(info, DrawObservation("A", "normal draw"))
    assert out.known_top == ("B",)
    assert out.known_bottom == ("Z",)
    assert out.shuffle_epoch == 3


def test_reveal_top_is_typed_and_can_preserve_deeper_memory():
    info = InformationState(known_top=("Old A", "Old B", "Known D"))
    event = RevealTopObservation(("New A", "New B"), source="Top")
    out = apply_observation_event(info, event)
    assert out.known_top == ("New A", "New B", "Known D")
    assert observation_event_key(event) == observation_event_key(event)


def test_london_bottom_plus_scry_bottom_stays_ordered():
    info = InformationState(known_bottom=("London A", "London B"))
    out = apply_observation_event(
        info,
        LibraryPositionsObservation(
            known_top=("Kept Top",),
            known_bottom=("Scry Bottom",),
            top_mode="replace",
            bottom_mode="append",
            source="scry",
        ),
    )
    assert out.known_top == ("Kept Top",)
    assert out.known_bottom == ("London A", "London B", "Scry Bottom")


def test_shuffle_is_hard_positional_reset():
    info = InformationState(
        known_top=("A", "B"),
        known_bottom=("Y", "Z"),
        known_library_counts=(("A", 1), ("Z", 1)),
        shuffle_epoch=7,
    )
    out = apply_observation_event(info, ShuffleObservation("fetch"))
    assert out.known_top == ()
    assert out.known_bottom == ()
    assert out.known_library_counts == info.known_library_counts
    assert out.shuffle_epoch == 8


def test_search_observation_is_ephemeral_and_does_not_store_hidden_order():
    info = InformationState(known_bottom=("London A",))
    event = SearchZoneObservation(
        zone="library",
        legal_cards=("A", "B", "C"),
        context="Mystical Tutor",
    )
    out = apply_observation_event(info, event)
    assert out == info
    assert not hasattr(event, "library_order")


def test_move_known_card_can_place_known_top_without_hidden_permutation():
    info = InformationState(known_bottom=("Bottom",))
    out = apply_observation_event(
        info,
        MoveKnownCardObservation(
            "Mystical Target",
            from_zone="search",
            to_zone="library",
            position="top",
            source="Mystical Tutor",
        ),
    )
    assert out.known_top == ("Mystical Target",)
    assert out.known_bottom == ("Bottom",)


def test_observation_batch_order_is_semantic():
    info = InformationState(known_top=("A",), known_bottom=("London",), shuffle_epoch=1)
    batch = ObservationBatch(
        (
            ShuffleObservation("Mystical Tutor"),
            MoveKnownCardObservation(
                "Target",
                from_zone="search",
                to_zone="library",
                position="top",
            ),
            PublicZoneChangeObservation(
                "Mystical Tutor", from_zone="stack", to_zone="graveyard"
            ),
        )
    )
    out = apply_observation_batch(info, batch)
    assert out.known_top == ("Target",)
    assert out.known_bottom == ()
    assert out.shuffle_epoch == 2


def test_transition_envelope_is_rules_side_and_marks_contingent_decision():
    state = base_state()
    transition = TransitionEnvelope(
        true_state=state,
        observations=ObservationBatch(
            (RevealTopObservation(("Hidden A", "Hidden B", "Hidden C"), source="Top"),)
        ),
        pending_decision=PendingDecisionSpec(
            decision_id="top-order-1",
            kind="choose_top_order",
            source="Sensei's Divining Top",
            contingent_on="top-activate-1",
        ),
    )
    assert transition.true_state is state
    assert transition.pending_decision is not None
    assert transition.pending_decision.decision_stage == DECISION_POST_OBSERVATION


def main():
    tests = [
        test_action_intent_identity_is_deterministic_and_stage_sensitive,
        test_explicit_equivalence_does_not_merge_distinct_targets,
        test_policy_decision_surface_has_no_true_state_library_or_root_seed,
        test_decision_request_rejects_mixed_commit_and_post_observation_actions,
        test_draw_consumes_only_legally_known_top_prefix,
        test_reveal_top_is_typed_and_can_preserve_deeper_memory,
        test_london_bottom_plus_scry_bottom_stays_ordered,
        test_shuffle_is_hard_positional_reset,
        test_search_observation_is_ephemeral_and_does_not_store_hidden_order,
        test_move_known_card_can_place_known_top_without_hidden_permutation,
        test_observation_batch_order_is_semantic,
        test_transition_envelope_is_rules_side_and_marks_contingent_decision,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("DECISION / OBSERVATION BOUNDARY SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
