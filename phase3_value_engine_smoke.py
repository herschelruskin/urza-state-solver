#!/usr/bin/env python3
"""Controlled exact-validation smoke for Phase-3 distribution V/Q semantics."""

from __future__ import annotations

from dataclasses import dataclass

from phase3_value_engine import DistributionBellmanEvaluator, WeightedSuccessor, WinDistributionValue
from solver_architecture import EpisodeOutcome


@dataclass(frozen=True)
class ToyState:
    name: str


class ToyModel:
    def __init__(self) -> None:
        self.transitions = {
            ("root", "safe"): ((0.5, "t3"), (0.5, "fail")),
            ("root", "fast"): ((0.4, "t2"), (0.6, "t4")),
            ("copy", "fast"): ((0.4, "t2"), (0.6, "t4")),
        }

    def state_key(self, state: ToyState):
        logical = "root-equivalent" if state.name in {"root", "copy"} else state.name
        return ("toy-state", logical)

    def actions(self, state: ToyState):
        if state.name in {"root", "copy"}:
            return ("safe", "fast") if state.name == "root" else ("fast",)
        return ()

    def action_key(self, action: str):
        return ("toy-action", action)

    def successors(self, state: ToyState, action: str):
        return tuple(WeightedSuccessor(p, ToyState(name)) for p, name in self.transitions[(state.name, action)])

    def terminal_outcome(self, state: ToyState, *, horizon: int):
        terminal = {
            "t2": EpisodeOutcome(True, 2, 2, horizon, "fast", "win"),
            "t3": EpisodeOutcome(True, 3, 3, horizon, "safe", "win"),
            "t4": EpisodeOutcome(True, 4, 4, horizon, "fast", "win"),
            "fail": EpisodeOutcome(False, None, horizon, horizon, "", "horizon"),
        }
        return terminal.get(state.name)


def main():
    model = ToyModel()
    evaluator = DistributionBellmanEvaluator(model, horizon=6)

    fast = evaluator.q(ToyState("root"), "fast")
    assert fast.exact_win == (0.0, 0.4, 0.0, 0.6, 0.0, 0.0)
    assert fast.no_win == 0.0
    assert dict(fast.win_families) == {"fast": 1.0}

    safe = evaluator.q(ToyState("root"), "safe")
    assert safe.exact_win == (0.0, 0.0, 0.5, 0.0, 0.0, 0.0)
    assert safe.no_win == 0.5

    best = evaluator.v(ToyState("root"))
    assert best.action == "fast"
    assert best.value == fast

    before_hits = evaluator.store.stats.v_hits
    copy = evaluator.v(ToyState("copy"))
    assert copy.value == fast
    assert evaluator.store.stats.v_hits == before_hits + 1

    earlier = WinDistributionValue(6, (0.0, 1.0, 0.0, 0.0, 0.0, 0.0), 0.0)
    later = WinDistributionValue(6, (0.0, 0.0, 0.0, 1.0, 0.0, 0.0), 0.0)
    assert earlier.comparison_key() > later.comparison_key()

    print("PASS distribution-rich exact T1-T6 value semantics")
    print("PASS deterministic value comparison")
    print("PASS real V/Q memoization on strategic keys")
    print("PHASE 3 VALUE ENGINE SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
