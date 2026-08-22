#!/usr/bin/env python3
"""Focused smoke tests for solver_architecture.py.

Run with:
    py -3 architecture_smoke.py
or:
    python architecture_smoke.py
"""

from dataclasses import dataclass, replace

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


@dataclass(frozen=True)
class DummyPerm:
    name: str
    tapped: bool = False
    sick: bool = False
    counters: int = 0
    mode: str = ""


@dataclass(frozen=True)
class DummyState:
    turn: int = 1
    library: tuple = ("A", "B", "C")
    hand: tuple = ("Island", "Sol Ring")
    battlefield: tuple = ()
    graveyard: tuple = ()
    exile: tuple = ()
    blue: int = 0
    colorless: int = 0
    land_played: bool = False
    drain_bank: int = 0
    bauble_draws: int = 0
    remora_age: int = 0
    ring_counters: int = 0
    ftt_level: int = 1
    uthros_counters: int = 0
    urza: bool = False
    construct: bool = False
    top_access: bool = False
    chip_attached: bool = False
    chip_target: str = ""
    spell_cast_this_turn: bool = False
    knack_target: str = ""
    pa_target: str = ""
    vfc_pumps: int = 0
    urza_cast_turn: int = 0
    commander_in_command_zone: bool = True
    commander_casts_from_zone: int = 0
    interaction_seen: tuple = ()
    won: bool = False
    win_family: str = ""
    trace: tuple = ()


def test_true_vs_observation_boundary():
    state = DummyState()
    info = InformationState(known_top=("A",), known_library_counts=(("A", 1),))
    view = make_policy_view(state, info, caverns_live=True)
    assert not hasattr(view, "library")
    assert view.known_top == ("A",)
    assert view.hand == tuple(sorted(state.hand))


def test_canonical_true_key_is_complete_and_deterministic():
    base = DummyState()
    assert canonical_true_state_key(base) == canonical_true_state_key(base)
    assert canonical_true_state_key(base) != canonical_true_state_key(
        replace(base, graveyard=("A",))
    )
    assert canonical_true_state_key(base) != canonical_true_state_key(
        replace(base, exile=("A",))
    )
    assert canonical_true_state_key(base) != canonical_true_state_key(
        replace(base, remora_age=1)
    )
    assert canonical_true_state_key(base) != canonical_true_state_key(
        replace(base, trace=("history matters in legacy shuffle",))
    )
    assert canonical_true_state_key(base) == canonical_true_state_key(
        replace(base, hand=tuple(reversed(base.hand)))
    )


def test_rng_namespaces_are_reproducible_and_independent():
    streams = RandomStreams(20260822)
    a = [streams.game_rng("opening").random() for _ in range(3)]
    b = [RandomStreams(20260822).game_rng("opening").random() for _ in range(3)]
    assert a == b
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
    state_key = canonical_true_state_key(DummyState())
    action = PolicyAction("play-island", "play_land")
    vkey = store.value_key(
        state_key, horizon=6, objective="win_by_horizon", policy_id="base"
    )
    qkey = store.q_key(
        state_key,
        action.strategic_key(),
        horizon=6,
        objective="win_by_horizon",
        policy_id="base",
    )
    assert store.get_v(vkey) is None
    store.set_v(vkey, 0.42)
    store.set_q(qkey, 0.51)
    assert store.get_v(vkey) == 0.42
    assert store.get_q(qkey) == 0.51
    assert store.stats.v_hits == 1 and store.stats.q_hits == 1


def test_trajectory_roundtrip():
    before = stable_digest(canonical_true_state_key(DummyState()))
    after = stable_digest(canonical_true_state_key(replace(DummyState(), turn=2)))
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
        test_canonical_true_key_is_complete_and_deterministic,
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
