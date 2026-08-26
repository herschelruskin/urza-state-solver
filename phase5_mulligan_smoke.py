#!/usr/bin/env python3
"""Acceptance smoke for sequential London mulligan DP."""

from pathlib import Path

from phase3_value_engine import WinDistributionValue
from phase5_mulligan import (
    MULLIGAN_KEEP_FLOOR,
    MULLIGAN_FLOOR_STAGE,
    MulliganDecision,
    MulliganStageEstimate,
    MulliganStageModel,
    OpeningKeepEstimate,
    OpeningKeepEvaluation,
    OpeningKeepEvaluator,
    _opening_world,
    keep_size_for_stage,
    opening_runtime,
    unique_bottom_subsets,
    value_at_least,
)


def load_deck():
    cards = []
    for raw in Path("decklist.txt").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        count, name = line.split(" ", 1)
        if name == "Urza, Lord High Artificer":
            continue
        cards.extend([name] * int(count))
    assert len(cards) == 99
    return tuple(cards)


def value(win_t3=0.0, win_t4=0.0, horizon=6):
    exact = [0.0] * horizon
    exact[2] = win_t3
    exact[3] = win_t4
    return WinDistributionValue(horizon, tuple(exact), 1.0 - win_t3 - win_t4)


def test_stage_and_bottom_counts():
    assert [keep_size_for_stage(s) for s in range(7)] == [7, 7, 6, 5, 4, 3, 2]
    assert MULLIGAN_FLOOR_STAGE == 6
    assert MULLIGAN_KEEP_FLOOR == 2
    seven = ("A", "B", "C", "D", "E", "F", "G")
    assert [len(unique_bottom_subsets(seven, s)) for s in range(7)] == [1, 1, 7, 21, 35, 35, 21]
    duplicate = ("Island", "Island", "A", "B", "C", "D", "E")
    assert len(unique_bottom_subsets(duplicate, 2)) == 6


def test_opening_runtime_preserves_known_bottom_and_keep_size():
    deck = load_deck()
    seven = ("Island", "Island", "Sol Ring", "Mana Vault", "Welding Jar", "Swan Song", "The One Ring")
    bottom = ("Island", "Welding Jar")
    runtime = opening_runtime(deck, seven, bottom)
    assert len(runtime.true_state.hand) == 5
    assert runtime.information.known_bottom == tuple(sorted(bottom))
    assert runtime.true_state.library[-2:] == tuple(sorted(bottom))
    assert len(runtime.true_state.library) == 94


def test_bottom_contenders_share_unknown_world_prefix():
    deck = load_deck()
    seven = ("Island", "Sol Ring", "Mana Vault", "Welding Jar", "Swan Song", "The One Ring", "Mox Opal")
    left = _opening_world(deck=deck, seven=seven, bottom=("Island",), mc_root_seed=20260826, sample_id=3)
    right = _opening_world(deck=deck, seven=seven, bottom=("Welding Jar",), mc_root_seed=20260826, sample_id=3)
    assert left.library[:-1] == right.library[:-1]
    assert left.rng_root_seed == right.rng_root_seed
    assert left.library[-1] == "Island"
    assert right.library[-1] == "Welding Jar"


def test_value_comparison_uses_phase3_semantics():
    later = value(win_t4=0.6)
    earlier = value(win_t3=0.6)
    more_wins = value(win_t4=0.7)
    assert value_at_least(earlier, later)
    assert not value_at_least(later, earlier)
    assert value_at_least(more_wins, earlier)


def test_floor_forces_keep_and_nonfloor_compares_continuation():
    weak = value(win_t4=0.2)
    strong = value(win_t3=0.8)
    weak_est = OpeningKeepEstimate(6, 2, ("A", "B", "C", "D", "E"), ("F", "G"), weak, 1, (0.0, 1.0), ())
    strong_est = OpeningKeepEstimate(0, 7, (), ("A", "B", "C", "D", "E", "F", "G"), strong, 1, (0.0, 1.0), ())

    class FakeEvaluator:
        def __init__(self, estimate): self.estimate = estimate
        def evaluate(self, seven, *, stage):
            est = self.estimate
            return OpeningKeepEvaluation(stage, tuple(seven), est, (est,), 1, 0, 6)

    stages = tuple(
        MulliganStageEstimate(s, keep_size_for_stage(s), value(win_t4=0.5), 1, 1, 0)
        for s in range(7)
    )
    model = MulliganStageModel(stages, 1, 1, 0, 6)
    floor = model.decide(("A", "B", "C", "D", "E", "F", "G"), stage=6, evaluator=FakeEvaluator(weak_est))
    assert floor.decision == "Keep" and floor.forced_floor
    top = model.decide(("A", "B", "C", "D", "E", "F", "G"), stage=0, evaluator=FakeEvaluator(strong_est))
    assert top.decision == "Keep" and not top.forced_floor


def test_real_opening_evaluator_runs_one_common_world():
    deck = load_deck()
    seven = ("Island", "Sol Ring", "Mana Vault", "Welding Jar", "Swan Song", "The One Ring", "Mox Opal")
    evaluator = OpeningKeepEvaluator(
        deck, rollout_count=1, mc_root_seed=17, horizon=1,
        strict_terminal_reasons=False, max_episode_steps=128,
    )
    result = evaluator.evaluate(seven, stage=2)
    assert len(result.estimates) == 7
    assert all(estimate.keep_size == 6 for estimate in result.estimates)
    assert all(estimate.rollouts == 1 for estimate in result.estimates)
    assert all(len(estimate.bottom) == 1 for estimate in result.estimates)


def main():
    tests = (
        test_stage_and_bottom_counts,
        test_opening_runtime_preserves_known_bottom_and_keep_size,
        test_bottom_contenders_share_unknown_world_prefix,
        test_value_comparison_uses_phase3_semantics,
        test_floor_forces_keep_and_nonfloor_compares_continuation,
        test_real_opening_evaluator_runs_one_common_world,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("PHASE 5 MULLIGAN DP SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
