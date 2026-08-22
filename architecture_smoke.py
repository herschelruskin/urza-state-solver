#!/usr/bin/env python3
"""Focused architecture compatibility tests against the finalized Oracle classes.

Run:
    py -3 architecture_smoke.py
"""

from dataclasses import replace

from urza_solver import Perm, State
from solver_architecture import (
    EpisodeOutcome,
    InformationState,
    MemoizationStore,
    PolicyAction,
    RandomStreams,
    Trajectory,
    TrajectoryEvent,
    canonical_true_state_key,
    collapse_action_equivalence,
    cumulative_win_curve,
    make_policy_view,
    stable_digest,
)


def base_state() -> State:
    return State(
        turn=1,
        library=("A", "B", "C"),
        hand=("Island", "Sol Ring"),
        battlefield=(Perm("Grinding Station"),),
    )


def test_true_vs_observation_boundary():
    state = base_state()
    info = InformationState(
        known_top=("A",),
        known_library_counts=(("A", 1), ("B", 1), ("C", 1)),
    )
    view = make_policy_view(state, info, caverns_live=True)
    assert not hasattr(view, "library"), "PolicyView leaked exact hidden library"
    assert view.known_top == ("A",)
    assert view.hand == tuple(sorted(state.hand))
    assert view.caverns_live is True


def test_exact_key_tracks_final_oracle_state_fields():
    state = base_state()
    key = canonical_true_state_key(state)

    assert key != canonical_true_state_key(replace(state, graveyard=("A",)))
    assert key != canonical_true_state_key(replace(state, exile=("A",)))
    assert key != canonical_true_state_key(replace(state, remora_age=1))
    assert key != canonical_true_state_key(replace(state, remora_upkeep_pending=True))
    assert key != canonical_true_state_key(replace(state, saga3_pending=True))
    assert key != canonical_true_state_key(
        replace(state, trace=("history-sensitive legacy shuffle",))
    )

    granted = replace(
        state,
        battlefield=(replace(state.battlefield[0], knack_granted=True),),
    )
    refundable = replace(
        state,
        battlefield=(replace(state.battlefield[0], producer_urza_ready=True),),
    )
    assert key != canonical_true_state_key(granted), "Knack grant collapsed"
    assert key != canonical_true_state_key(refundable), "producer refund credit collapsed"

    runtime_only = replace(
        state,
        battlefield=(
            replace(
                state.battlefield[0],
                instance_tag=99,
                knack_source="Banishing Knack",
            ),
        ),
    )
    assert key == canonical_true_state_key(runtime_only), (
        "ephemeral provenance polluted strategic permanent identity"
    )

    assert key == canonical_true_state_key(
        replace(state, hand=tuple(reversed(state.hand)))
    )


def test_policy_view_tracks_future_legality_without_hidden_future():
    p = Perm(
        "Battered Golem",
        tapped=True,
        knack_granted=True,
        producer_urza_ready=True,
    )
    state = replace(
        base_state(),
        battlefield=(p,),
        remora_age=2,
        remora_upkeep_pending=True,
        saga3_pending=True,
    )
    view = make_policy_view(state, InformationState())
    assert view.remora_age == 2
    assert view.remora_upkeep_pending is True
    assert view.saga3_pending is True
    assert view.battlefield[0].knack_granted is True
    assert view.battlefield[0].producer_urza_ready is True
    assert not hasattr(view.battlefield[0], "instance_tag")
    assert not hasattr(view.battlefield[0], "knack_source")


def test_information_state_shuffle_reset():
    info = InformationState(
        known_top=("A", "B"),
        known_bottom=("C",),
        known_library_counts=(("A", 1), ("B", 1), ("C", 1)),
        shuffle_epoch=4,
    )
    shuffled = info.after_shuffle()
    assert shuffled.known_top == ()
    assert shuffled.known_bottom == ()
    assert shuffled.known_library_counts == info.known_library_counts
    assert shuffled.shuffle_epoch == 5


def test_rng_namespaces_are_reproducible_and_independent():
    streams = RandomStreams(20260822)
    assert streams.seed_for("game", "opening") == RandomStreams(20260822).seed_for(
        "game", "opening"
    )
    assert streams.seed_for("game", "shuffle-1") != streams.seed_for(
        "policy", "shuffle-1"
    )
    game_seed = streams.seed_for("game", "shuffle-2")
    for rollout in range(100):
        streams.policy_rng(("decision-4", rollout)).random()
    assert game_seed == streams.seed_for("game", "shuffle-2")


def test_action_equivalence_collapsing():
    actions = (
        PolicyAction("b", "tap", equivalence_key=("same-result",)),
        PolicyAction("a", "tap", equivalence_key=("same-result",)),
        PolicyAction("c", "tutor", equivalence_key=("target", "Top")),
        PolicyAction("d", "tutor", equivalence_key=("target", "Cam")),
    )
    kept = collapse_action_equivalence(actions)
    assert tuple(a.action_id for a in kept) == ("a", "c", "d")


def test_v_q_memoization_namespaces():
    store = MemoizationStore[float]()
    state_key = canonical_true_state_key(base_state())
    action = PolicyAction("play-island", "play_land")
    info_key = InformationState(known_top=("A",)).key()

    vkey = store.value_key(
        state_key,
        horizon=6,
        objective="win_by_horizon",
        policy_id="base",
        information_key=info_key,
    )
    qkey = store.q_key(
        state_key,
        action.strategic_key(),
        horizon=6,
        objective="win_by_horizon",
        policy_id="base",
        information_key=info_key,
    )
    assert store.get_v(vkey) is None
    store.set_v(vkey, 0.42)
    store.set_q(qkey, 0.51)
    assert store.get_v(vkey) == 0.42
    assert store.get_q(qkey) == 0.51


def test_trajectory_roundtrip():
    before = stable_digest(canonical_true_state_key(base_state()))
    after = stable_digest(
        canonical_true_state_key(replace(base_state(), turn=2))
    )
    trajectory = Trajectory(root_seed=7, horizon=6).append(
        TrajectoryEvent(
            index=0,
            turn=1,
            action_id="pass-turn",
            state_before=before,
            state_after=after,
            rng_namespace="game",
            rng_event="turn-1",
        )
    )
    restored = Trajectory.from_jsonl(trajectory.to_jsonl())
    assert restored == trajectory
    assert restored.digest() == trajectory.digest()


def test_win_turn_and_horizon_recording():
    outcomes = (
        EpisodeOutcome(True, 2, 2, 6, "A", "win"),
        EpisodeOutcome(True, 4, 4, 6, "B", "win"),
        EpisodeOutcome(False, None, 6, 6, "", "horizon"),
    )
    curve = dict(cumulative_win_curve(outcomes, 6))
    assert curve[1] == 0.0
    assert curve[2] == 1 / 3
    assert curve[4] == 2 / 3
    assert curve[6] == 2 / 3


def main():
    tests = [
        test_true_vs_observation_boundary,
        test_exact_key_tracks_final_oracle_state_fields,
        test_policy_view_tracks_future_legality_without_hidden_future,
        test_information_state_shuffle_reset,
        test_rng_namespaces_are_reproducible_and_independent,
        test_action_equivalence_collapsing,
        test_v_q_memoization_namespaces,
        test_trajectory_roundtrip,
        test_win_turn_and_horizon_recording,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("ARCHITECTURE SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
