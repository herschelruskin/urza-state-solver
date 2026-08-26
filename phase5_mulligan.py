#!/usr/bin/env python3
"""Sequential London mulligan DP on top of Phase-4 Monte Carlo.

Stages follow the user's convention:
0=initial 7, 1=free second 7, 2=keep 6, 3=keep 5, 4=keep 4,
5=keep 3, 6=keep 2. Stage 6 is the current forced-keep floor.

For visible fresh seven h at stage s, K_s(h) is the best value after exhaustive
London bottom selection. Because a rejected seven is shuffled back before the next
fresh seven, the value of mulliganing again depends only on stage:

    V_6 = E_h[K_6(h)]
    V_s = E_h[max(K_s(h), V_{s+1})]

Monte Carlo supplies the expectations; the stage recursion and bottom enumeration
are exact. Human labels remain held-out calibration data, not policy weights.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import itertools
import json
import random
from typing import Callable, Iterable, Sequence, Tuple

import urza_solver as solver
from information_state_propagation import validate_information_against_state
from non_oracle_base_policy import DeterministicBasePolicy
from non_oracle_episode import run_deterministic_episode
from non_oracle_runtime import make_runtime_state
from phase3_value_engine import WinDistributionValue
from phase4_hidden_world import SampledHiddenWorld, materialize_hidden_world
from phase4_monte_carlo import _episode_outcome, _value_from_outcomes, _wilson_interval
from phase5_monte_carlo import MODELED_TERMINALS
from solver_architecture import InformationState

PHASE5_MULLIGAN_VERSION = "urza-mulligan-dp-v1"
MULLIGAN_KEEP_SIZES = {0: 7, 1: 7, 2: 6, 3: 5, 4: 4, 5: 3, 6: 2}
FREE_MULLIGAN_STAGE = 1
MULLIGAN_FLOOR_STAGE = 6
MULLIGAN_KEEP_FLOOR = 2


class MulliganEvaluationError(RuntimeError):
    pass


def keep_size_for_stage(stage: int) -> int:
    try:
        return MULLIGAN_KEEP_SIZES[int(stage)]
    except KeyError as exc:
        raise ValueError(f"unsupported mulligan stage {stage!r}") from exc


def bottom_count_for_stage(stage: int) -> int:
    return 7 - keep_size_for_stage(stage)


def value_at_least(left: WinDistributionValue, right: WinDistributionValue) -> bool:
    if left.horizon != right.horizon:
        raise ValueError("cannot compare mulligan values with different horizons")
    return left.comparison_key() >= right.comparison_key()


def _counter_tuple(cards: Iterable[str]) -> Tuple[Tuple[str, int], ...]:
    return tuple(sorted(Counter(str(card) for card in cards).items()))


def unique_bottom_subsets(seven: Sequence[str], stage: int) -> Tuple[Tuple[str, ...], ...]:
    """All distinct card-multiset bottoms; suffix ordering is canonicalized."""
    cards = tuple(str(card) for card in seven)
    if len(cards) != 7:
        raise ValueError("mulligan evaluation requires a fresh seven-card hand")
    count = bottom_count_for_stage(stage)
    if count == 0:
        return ((),)
    unique = {
        tuple(sorted(cards[index] for index in combo))
        for combo in itertools.combinations(range(7), count)
    }
    return tuple(sorted(unique))


def _remove_multiset(cards: Sequence[str], remove: Sequence[str]) -> Tuple[str, ...]:
    remaining = list(str(card) for card in cards)
    for card in remove:
        try:
            remaining.remove(str(card))
        except ValueError as exc:
            raise MulliganEvaluationError(f"cannot remove bottom card {card!r} from seven") from exc
    return tuple(remaining)


def _deck_without_seven(deck: Sequence[str], seven: Sequence[str]) -> Tuple[str, ...]:
    remaining = list(str(card) for card in deck)
    for card in seven:
        try:
            remaining.remove(str(card))
        except ValueError as exc:
            raise MulliganEvaluationError(
                f"visible seven contains card {card!r} beyond supplied deck multiplicity"
            ) from exc
    return tuple(remaining)


def opening_runtime(deck: Sequence[str], seven: Sequence[str], bottom: Sequence[str], *, rollout_game_seed: int = 0):
    seven = tuple(str(card) for card in seven)
    bottom = tuple(sorted(str(card) for card in bottom))
    keep = _remove_multiset(seven, bottom)
    unknown = tuple(sorted(_deck_without_seven(deck, seven)))
    state = solver.State(
        turn=1,
        library=unknown + bottom,
        hand=keep,
        battlefield=(),
        rng_root_seed=int(rollout_game_seed),
        trace=("--- Turn 1 ---",),
    )
    information = InformationState(known_bottom=bottom)
    validate_information_against_state(information, state)
    return make_runtime_state(state, information)


def _opening_world(*, deck: Sequence[str], seven: Sequence[str], bottom: Sequence[str], mc_root_seed: int, sample_id: int) -> SampledHiddenWorld:
    """Sample one common unknown prefix for every bottom choice of this seven."""
    unknown = list(_deck_without_seven(deck, seven))
    coordinate = (
        PHASE5_MULLIGAN_VERSION,
        "opening-unknown-prefix",
        _counter_tuple(deck),
        tuple(sorted(str(card) for card in seven)),
        int(sample_id),
    )
    seed_material = json.dumps(
        [int(mc_root_seed), coordinate], sort_keys=True, separators=(",", ":"), default=repr
    ).encode("utf-8")
    digest = hashlib.sha256(seed_material).hexdigest()
    seed = int.from_bytes(hashlib.sha256(seed_material).digest()[:8], "big")
    rng = random.Random(seed)
    rng.shuffle(unknown)
    bottom = tuple(sorted(str(card) for card in bottom))
    game_seed_material = json.dumps(
        [int(mc_root_seed), "opening-rollout-game", int(sample_id)], separators=(",", ":")
    ).encode("utf-8")
    rollout_game_seed = int.from_bytes(hashlib.sha256(game_seed_material).digest()[:8], "big")
    return SampledHiddenWorld(
        sample_id=str(sample_id),
        library=tuple(unknown) + bottom,
        rng_root_seed=rollout_game_seed,
        belief_digest=digest,
    )


@dataclass(frozen=True)
class OpeningKeepEstimate:
    stage: int
    keep_size: int
    bottom: Tuple[str, ...]
    kept_hand: Tuple[str, ...]
    value: WinDistributionValue
    rollouts: int
    win_probability_wilson95: Tuple[float, float]
    terminal_reason_counts: Tuple[Tuple[str, int], ...]


@dataclass(frozen=True)
class OpeningKeepEvaluation:
    stage: int
    seven: Tuple[str, ...]
    best: OpeningKeepEstimate
    estimates: Tuple[OpeningKeepEstimate, ...]
    rollout_count_per_bottom: int
    mc_root_seed: int
    horizon: int
    version: str = PHASE5_MULLIGAN_VERSION


class OpeningKeepEvaluator:
    def __init__(self, deck: Sequence[str], *, rollout_count: int = 32, mc_root_seed: int = 0,
                 horizon: int = 6, continuation_policy: DeterministicBasePolicy | None = None,
                 max_episode_steps: int = 512, strict_terminal_reasons: bool = True,
                 episode_runner: Callable | None = None) -> None:
        if rollout_count < 1:
            raise ValueError("rollout_count must be >= 1")
        self.deck = tuple(str(card) for card in deck)
        self.rollout_count = int(rollout_count)
        self.mc_root_seed = int(mc_root_seed)
        self.horizon = int(horizon)
        self.continuation_policy = continuation_policy or DeterministicBasePolicy()
        self.max_episode_steps = int(max_episode_steps)
        self.strict_terminal_reasons = bool(strict_terminal_reasons)
        self.episode_runner = episode_runner or run_deterministic_episode

    def evaluate(
        self,
        seven: Sequence[str],
        *,
        stage: int,
        candidate_bottoms: Sequence[Sequence[str]] | None = None,
        sample_start: int = 0,
    ) -> OpeningKeepEvaluation:
        seven = tuple(str(card) for card in seven)
        keep_size = keep_size_for_stage(stage)
        legal_bottoms = unique_bottom_subsets(seven, stage)
        if candidate_bottoms is None:
            bottoms = legal_bottoms
        else:
            legal = set(legal_bottoms)
            normalized = {
                tuple(sorted(str(card) for card in bottom))
                for bottom in candidate_bottoms
            }
            invalid = sorted(normalized - legal)
            if invalid:
                raise ValueError(
                    f"candidate bottoms are not legal for stage {stage}: {invalid!r}"
                )
            if not normalized:
                raise ValueError("candidate_bottoms must not be empty")
            bottoms = tuple(sorted(normalized))
        if int(sample_start) < 0:
            raise ValueError("sample_start must be >= 0")
        outcomes_by_bottom = {bottom: [] for bottom in bottoms}
        reasons_by_bottom = {bottom: Counter() for bottom in bottoms}

        for sample_id in range(
            int(sample_start), int(sample_start) + self.rollout_count
        ):
            for bottom in bottoms:
                root = opening_runtime(self.deck, seven, bottom)
                world = _opening_world(
                    deck=self.deck, seven=seven, bottom=bottom,
                    mc_root_seed=self.mc_root_seed, sample_id=sample_id,
                )
                sampled = materialize_hidden_world(root, world)
                validate_information_against_state(sampled.information, sampled.true_state)
                result = self.episode_runner(
                    sampled, horizon=self.horizon, policy=self.continuation_policy,
                    max_steps=self.max_episode_steps,
                )
                reason = str(result.terminal_reason)
                reasons_by_bottom[bottom][reason] += 1
                if self.strict_terminal_reasons and reason not in MODELED_TERMINALS:
                    raise MulliganEvaluationError(
                        f"opening rollout terminated with unmodeled reason {reason!r}"
                    )
                outcomes_by_bottom[bottom].append(_episode_outcome(result, horizon=self.horizon))

        estimates = []
        for bottom in bottoms:
            outcomes = tuple(outcomes_by_bottom[bottom])
            value = _value_from_outcomes(outcomes, horizon=self.horizon)
            wins = sum(outcome.won for outcome in outcomes)
            estimates.append(OpeningKeepEstimate(
                stage=int(stage), keep_size=keep_size, bottom=bottom,
                kept_hand=_remove_multiset(seven, bottom), value=value,
                rollouts=len(outcomes), win_probability_wilson95=_wilson_interval(wins, len(outcomes)),
                terminal_reason_counts=tuple(sorted(reasons_by_bottom[bottom].items())),
            ))
        ranked = tuple(sorted(
            estimates,
            key=lambda estimate: (estimate.value.comparison_key(), repr(estimate.bottom)),
            reverse=True,
        ))
        return OpeningKeepEvaluation(
            stage=int(stage), seven=seven, best=ranked[0], estimates=ranked,
            rollout_count_per_bottom=self.rollout_count,
            mc_root_seed=self.mc_root_seed, horizon=self.horizon,
        )


def _mix_values(values: Sequence[WinDistributionValue]) -> WinDistributionValue:
    if not values:
        raise ValueError("cannot average zero values")
    horizon = values[0].horizon
    weight = 1.0 / len(values)
    return WinDistributionValue.mixture(
        tuple((weight, value) for value in values), horizon=horizon
    )


def _sample_fresh_seven(deck: Sequence[str], *, root_seed: int, stage: int, sample_id: int) -> Tuple[str, ...]:
    coordinate = (PHASE5_MULLIGAN_VERSION, "fresh-seven", int(stage), int(sample_id))
    material = json.dumps([int(root_seed), coordinate], separators=(",", ":")).encode("utf-8")
    seed = int.from_bytes(hashlib.sha256(material).digest()[:8], "big")
    cards = list(str(card) for card in deck)
    random.Random(seed).shuffle(cards)
    return tuple(cards[:7])


@dataclass(frozen=True)
class MulliganStageEstimate:
    stage: int
    keep_size: int
    value: WinDistributionValue
    sampled_hands: int
    kept_count: int
    mulligan_count: int

    @property
    def keep_rate(self) -> float:
        return self.kept_count / self.sampled_hands if self.sampled_hands else 0.0


@dataclass(frozen=True)
class MulliganDecision:
    stage: int
    keep_size: int
    decision: str
    keep: OpeningKeepEstimate
    mulligan_value: WinDistributionValue | None
    forced_floor: bool


@dataclass(frozen=True)
class MulliganStageModel:
    stages: Tuple[MulliganStageEstimate, ...]
    hand_samples_per_stage: int
    rollout_count_per_bottom: int
    mc_root_seed: int
    horizon: int
    version: str = PHASE5_MULLIGAN_VERSION

    def stage_estimate(self, stage: int) -> MulliganStageEstimate:
        for estimate in self.stages:
            if estimate.stage == int(stage):
                return estimate
        raise KeyError(stage)

    def continuation_value(self, current_stage: int) -> WinDistributionValue | None:
        next_stage = int(current_stage) + 1
        return None if next_stage > MULLIGAN_FLOOR_STAGE else self.stage_estimate(next_stage).value

    def decide(self, seven: Sequence[str], *, stage: int, evaluator: OpeningKeepEvaluator) -> MulliganDecision:
        keep_eval = evaluator.evaluate(seven, stage=stage)
        if int(stage) == MULLIGAN_FLOOR_STAGE:
            return MulliganDecision(int(stage), keep_size_for_stage(stage), "Keep", keep_eval.best, None, True)
        mulligan_value = self.continuation_value(stage)
        assert mulligan_value is not None
        decision = "Keep" if value_at_least(keep_eval.best.value, mulligan_value) else "Mulligan"
        return MulliganDecision(int(stage), keep_size_for_stage(stage), decision, keep_eval.best, mulligan_value, False)


class MulliganStageTrainer:
    def __init__(self, deck: Sequence[str], *, hand_samples_per_stage: int = 16,
                 rollout_count_per_bottom: int = 16, mc_root_seed: int = 0,
                 horizon: int = 6, continuation_policy: DeterministicBasePolicy | None = None,
                 strict_terminal_reasons: bool = True,
                 episode_runner: Callable | None = None) -> None:
        if hand_samples_per_stage < 1:
            raise ValueError("hand_samples_per_stage must be >= 1")
        self.deck = tuple(str(card) for card in deck)
        self.hand_samples_per_stage = int(hand_samples_per_stage)
        self.rollout_count_per_bottom = int(rollout_count_per_bottom)
        self.mc_root_seed = int(mc_root_seed)
        self.horizon = int(horizon)
        self.continuation_policy = continuation_policy or DeterministicBasePolicy()
        self.strict_terminal_reasons = bool(strict_terminal_reasons)
        self.episode_runner = episode_runner or run_deterministic_episode

    def train(self) -> MulliganStageModel:
        fitted: dict[int, MulliganStageEstimate] = {}
        for stage in range(MULLIGAN_FLOOR_STAGE, -1, -1):
            evaluator = OpeningKeepEvaluator(
                self.deck, rollout_count=self.rollout_count_per_bottom,
                mc_root_seed=self.mc_root_seed, horizon=self.horizon,
                continuation_policy=self.continuation_policy,
                strict_terminal_reasons=self.strict_terminal_reasons,
                episode_runner=self.episode_runner,
            )
            chosen_values = []
            kept = mulled = 0
            continuation = fitted.get(stage + 1)
            for sample_id in range(self.hand_samples_per_stage):
                seven = _sample_fresh_seven(self.deck, root_seed=self.mc_root_seed, stage=stage, sample_id=sample_id)
                keep = evaluator.evaluate(seven, stage=stage).best.value
                if continuation is None or value_at_least(keep, continuation.value):
                    chosen_values.append(keep); kept += 1
                else:
                    chosen_values.append(continuation.value); mulled += 1
            fitted[stage] = MulliganStageEstimate(
                stage, keep_size_for_stage(stage), _mix_values(chosen_values),
                self.hand_samples_per_stage, kept, mulled,
            )
        return MulliganStageModel(
            stages=tuple(fitted[s] for s in range(MULLIGAN_FLOOR_STAGE + 1)),
            hand_samples_per_stage=self.hand_samples_per_stage,
            rollout_count_per_bottom=self.rollout_count_per_bottom,
            mc_root_seed=self.mc_root_seed,
            horizon=self.horizon,
        )
