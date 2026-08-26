#!/usr/bin/env python3
"""Phase-3 distribution-valued Bellman / memoization engine.

This module is rules-neutral.  It consumes a transition model supplied by the
non-Oracle runtime layer and returns a full exact-win-turn distribution through
the configured horizon.  Hidden-world Monte Carlo can later implement the same
transition/value surface without changing comparison or cache semantics.

Important invariants:
- V/Q identity is supplied by the strategic runtime value key, never exact hidden
  library order or the actual-game RNG seed;
- Q identity uses strategic action identity;
- terminal outcomes preserve exact win turn through T1..T6;
- value comparison is deterministic and versioned;
- the store namespace includes horizon, objective and policy id;
- this module never executes Magic rules itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isclose
from typing import Any, Generic, Iterable, Optional, Protocol, Sequence, Tuple, TypeVar

from solver_architecture import EpisodeOutcome, MemoizationStore


PHASE3_VALUE_VERSION = "urza-win-distribution-v1"
PHASE3_OBJECTIVE_ID = "win_by_horizon_then_earlier-v1"

TState = TypeVar("TState")
TAction = TypeVar("TAction")


@dataclass(frozen=True)
class WinDistributionValue:
    """Probability distribution over exact win turn plus no-win mass.

    ``exact_win`` stores T1..Thorizon probability mass.  The remaining mass is
    explicit in ``no_win`` rather than inferred so malformed values fail loudly.
    Optional family probabilities are unconditional terminal masses and therefore
    sum to at most the total win probability.
    """

    horizon: int
    exact_win: Tuple[float, ...]
    no_win: float
    win_families: Tuple[Tuple[str, float], ...] = ()
    version: str = PHASE3_VALUE_VERSION

    def __post_init__(self) -> None:
        if self.horizon < 1:
            raise ValueError("value horizon must be >= 1")
        if len(self.exact_win) != self.horizon:
            raise ValueError("exact_win must contain one probability for every turn")
        masses = tuple(self.exact_win) + (self.no_win,)
        if any(p < -1e-12 or p > 1.0 + 1e-12 for p in masses):
            raise ValueError("probability mass outside [0, 1]")
        if not isclose(sum(masses), 1.0, rel_tol=0.0, abs_tol=1e-10):
            raise ValueError(f"probability mass sums to {sum(masses)!r}, not 1")
        if any(p < -1e-12 for _, p in self.win_families):
            raise ValueError("negative win-family mass")
        if sum(p for _, p in self.win_families) > self.win_probability + 1e-10:
            raise ValueError("win-family mass exceeds total win probability")
        names = [name for name, _ in self.win_families]
        if names != sorted(names) or len(names) != len(set(names)):
            raise ValueError("win_families must be unique and lexicographically sorted")

    @property
    def win_probability(self) -> float:
        return sum(self.exact_win)

    def win_by(self, turn: int) -> float:
        if turn <= 0:
            return 0.0
        return sum(self.exact_win[: min(turn, self.horizon)])

    def cumulative_curve(self) -> Tuple[Tuple[int, float], ...]:
        return tuple((turn, self.win_by(turn)) for turn in range(1, self.horizon + 1))

    def comparison_key(self, *, digits: int = 15) -> Tuple[float, ...]:
        """Versioned deterministic objective: win by horizon, then earlier wins.

        The primary coordinate is P(win by horizon).  When effectively identical,
        cumulative probabilities at T1, T2, ... T(h-1) prefer distributions that
        move probability mass earlier.  Rounded coordinates avoid platform-level
        last-bit noise from changing deterministic action ordering.
        """

        cumulative = tuple(self.win_by(turn) for turn in range(1, self.horizon))
        return tuple(round(x, digits) for x in (self.win_probability,) + cumulative)

    @classmethod
    def zero(cls, horizon: int) -> "WinDistributionValue":
        return cls(horizon=horizon, exact_win=(0.0,) * horizon, no_win=1.0)

    @classmethod
    def from_outcome(cls, outcome: EpisodeOutcome) -> "WinDistributionValue":
        exact = [0.0] * outcome.horizon
        families = ()
        if outcome.won:
            assert outcome.win_turn is not None
            exact[outcome.win_turn - 1] = 1.0
            families = ((outcome.win_family, 1.0),) if outcome.win_family else ()
            return cls(outcome.horizon, tuple(exact), 0.0, families)
        return cls(outcome.horizon, tuple(exact), 1.0)

    @classmethod
    def mixture(
        cls,
        weighted_values: Iterable[Tuple[float, "WinDistributionValue"]],
        *,
        horizon: int,
    ) -> "WinDistributionValue":
        rows = tuple(weighted_values)
        if not rows:
            raise ValueError("cannot mix an empty value set")
        total_weight = sum(float(weight) for weight, _ in rows)
        if total_weight <= 0.0:
            raise ValueError("mixture weights must have positive total")
        if not isclose(total_weight, 1.0, rel_tol=0.0, abs_tol=1e-10):
            raise ValueError(f"mixture weights sum to {total_weight!r}, not 1")

        exact = [0.0] * horizon
        no_win = 0.0
        families: dict[str, float] = {}
        for raw_weight, value in rows:
            weight = float(raw_weight)
            if weight < 0.0:
                raise ValueError("negative mixture weight")
            if value.horizon != horizon:
                raise ValueError("cannot mix values from different horizons")
            for index, probability in enumerate(value.exact_win):
                exact[index] += weight * probability
            no_win += weight * value.no_win
            for family, probability in value.win_families:
                families[family] = families.get(family, 0.0) + weight * probability

        return cls(
            horizon=horizon,
            exact_win=tuple(exact),
            no_win=no_win,
            win_families=tuple(sorted(families.items())),
        )


@dataclass(frozen=True)
class WeightedSuccessor(Generic[TState]):
    probability: float
    state: TState


class BellmanTransitionModel(Protocol[TState, TAction]):
    """Rules/runtime-owned surface required by the Phase-3 evaluator."""

    def state_key(self, state: TState) -> Tuple[Any, ...]: ...

    def actions(self, state: TState) -> Sequence[TAction]: ...

    def action_key(self, action: TAction) -> Tuple[Any, ...]: ...

    def successors(self, state: TState, action: TAction) -> Sequence[WeightedSuccessor[TState]]: ...

    def terminal_outcome(self, state: TState, *, horizon: int) -> Optional[EpisodeOutcome]: ...


@dataclass(frozen=True)
class BellmanResult(Generic[TAction]):
    value: WinDistributionValue
    action: Optional[TAction]


class DistributionBellmanEvaluator(Generic[TState, TAction]):
    """Exact memoized V/Q evaluator for controlled finite transition models.

    This intentionally contains no hidden-world sampler.  Phase 4 can estimate the
    same Q values with Monte Carlo while retaining this value/comparison contract.
    """

    def __init__(
        self,
        model: BellmanTransitionModel[TState, TAction],
        *,
        horizon: int = 6,
        objective: str = PHASE3_OBJECTIVE_ID,
        policy_id: str = "optimal-visible-v1",
        store: MemoizationStore[WinDistributionValue] | None = None,
    ) -> None:
        if horizon < 1:
            raise ValueError("horizon must be >= 1")
        self.model = model
        self.horizon = int(horizon)
        self.objective = str(objective)
        self.policy_id = str(policy_id)
        self.store = store or MemoizationStore()
        self._active_v: set[Tuple[Any, ...]] = set()
        # Keep only strategic action identity.  A cached concrete ActionIntent may
        # carry runtime execution IDs that are invalid in an equivalent state.
        self._best_action_keys: dict[Tuple[Any, ...], Tuple[Any, ...]] = {}

    def _v_cache_key(self, state: TState) -> Tuple[Any, ...]:
        return self.store.value_key(
            self.model.state_key(state),
            horizon=self.horizon,
            objective=self.objective,
            policy_id=self.policy_id,
        )

    def _q_cache_key(self, state: TState, action: TAction) -> Tuple[Any, ...]:
        return self.store.q_key(
            self.model.state_key(state),
            self.model.action_key(action),
            horizon=self.horizon,
            objective=self.objective,
            policy_id=self.policy_id,
        )

    def q(self, state: TState, action: TAction) -> WinDistributionValue:
        key = self._q_cache_key(state, action)
        cached = self.store.get_q(key)
        if cached is not None:
            return cached

        successors = tuple(self.model.successors(state, action))
        if not successors:
            raise ValueError("nonterminal action produced no successors")
        total = sum(float(row.probability) for row in successors)
        if not isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-10):
            raise ValueError(f"successor probabilities sum to {total!r}, not 1")
        value = WinDistributionValue.mixture(
            ((row.probability, self.value(row.state)) for row in successors),
            horizon=self.horizon,
        )
        self.store.set_q(key, value)
        return value

    def value(self, state: TState) -> WinDistributionValue:
        """Return V(state) without requiring a concrete best action object."""

        terminal = self.model.terminal_outcome(state, horizon=self.horizon)
        if terminal is not None:
            return WinDistributionValue.from_outcome(terminal)

        key = self._v_cache_key(state)
        cached = self.store.get_v(key)
        if cached is not None:
            return cached
        if key in self._active_v:
            raise RuntimeError("cycle detected in exact Bellman evaluator; transition model must collapse or bound cycles")

        actions = tuple(self.model.actions(state))
        if not actions:
            raise ValueError("nonterminal state has no actions")

        self._active_v.add(key)
        try:
            ranked = []
            for action in actions:
                value = self.q(state, action)
                action_key = self.model.action_key(action)
                ranked.append((value.comparison_key(), repr(action_key), action_key, value))
            _, _, best_action_key, best_value = max(ranked, key=lambda row: (row[0], row[1]))
            self.store.set_v(key, best_value)
            self._best_action_keys[key] = best_action_key
            return best_value
        finally:
            self._active_v.remove(key)

    def _resolve_best_action(self, state: TState, value: WinDistributionValue) -> Optional[TAction]:
        actions = tuple(self.model.actions(state))
        if not actions:
            return None
        key = self._v_cache_key(state)
        best_action_key = self._best_action_keys.get(key)
        if best_action_key is not None:
            matches = [action for action in actions if self.model.action_key(action) == best_action_key]
            if matches:
                return min(matches, key=lambda action: repr(self.model.action_key(action)))

        # A shared/pre-populated V store may not carry this evaluator's local best
        # action key.  Recover it from Q using current-state legal action objects;
        # cached Q values make this cheap and avoid reusing stale execution IDs.
        ranked = []
        for action in actions:
            action_value = self.q(state, action)
            ranked.append((action_value.comparison_key(), repr(self.model.action_key(action)), action, action_value))
        _, _, best_action, recovered_value = max(ranked, key=lambda row: (row[0], row[1]))
        if recovered_value.comparison_key() != value.comparison_key():
            raise AssertionError("cached V disagrees with current legal Q values")
        self._best_action_keys[key] = self.model.action_key(best_action)
        return best_action

    def v(self, state: TState) -> BellmanResult[TAction]:
        terminal = self.model.terminal_outcome(state, horizon=self.horizon)
        if terminal is not None:
            return BellmanResult(WinDistributionValue.from_outcome(terminal), None)
        value = self.value(state)
        return BellmanResult(value, self._resolve_best_action(state, value))

    def rank_actions(self, state: TState) -> Tuple[Tuple[TAction, WinDistributionValue], ...]:
        rows = [(action, self.q(state, action)) for action in self.model.actions(state)]
        return tuple(
            sorted(
                rows,
                key=lambda row: (row[1].comparison_key(), repr(self.model.action_key(row[0]))),
                reverse=True,
            )
        )
