#!/usr/bin/env python3
"""Phase-5 information-safe Monte Carlo evaluation for arbitrary visible decisions.

This is the parity-aware successor to the Phase-4 root evaluator.  It keeps the
same information boundary and common-random-number design but evaluates the current
Phase-5 production action surface (fetch/Knack/Chain/Offer/permission fixes included).

The evaluator is rules-side infrastructure, not a policy that receives raw State.
It derives a LibraryBeliefKey from the runtime + information state, samples hidden
worlds from that belief, verifies the policy-visible request is invariant across
worlds, applies one candidate action, and then delegates continuation to a fixed
information-constrained policy.
"""

from __future__ import annotations

from collections import Counter, OrderedDict
from dataclasses import dataclass
from math import sqrt
from typing import Iterable, Sequence, Tuple

from decision_observation import ActionIntent
from non_oracle_base_policy import DeterministicBasePolicy
from non_oracle_episode import NonOracleEpisodeResult, run_deterministic_episode
from non_oracle_rules_adapter_v2 import apply_main_action, rules_decision_request
from phase3_value_engine import PHASE3_OBJECTIVE_ID, WinDistributionValue
from phase4_hidden_world import HiddenWorldSampler, materialize_hidden_world
from solver_architecture import EpisodeOutcome
from strategic_value_state import LibraryBeliefKey
from phase5_packed_keys import (
    packed_action_strategic_key,
    packed_observation_key,
    packed_phase5_decision_cache_key,
)
from symbolic_action_space import ParetoPoint, pareto_dominates

PHASE5_MC_VERSION = "urza-phase5-decision-monte-carlo-v2-paired-outcomes"

# A deterministic continuation policy can exhaust every strategic action from an
# exact recurrent sampled state or consume its finite step budget while cycling
# through many distinct but non-converting configurations. Those are explicit
# leaf-policy failure/no-win outcomes, not evidence that Magic mechanics are
# missing. Unsupported runtime windows and no-legal-action blockers remain hard
# errors in strict mode so Q estimates cannot silently absorb missing rules coverage.
MODELED_NO_WIN_TERMINALS = frozenset({
    "horizon",
    "strategic_cycle_exhausted",
    "step_limit",
})
MODELED_TERMINALS = MODELED_NO_WIN_TERMINALS | {"win"}


class Phase5MonteCarloError(RuntimeError):
    pass


@dataclass(frozen=True)
class Phase5ActionEstimate:
    action: ActionIntent
    value: WinDistributionValue
    rollouts: int
    terminal_reason_counts: Tuple[Tuple[str, int], ...]
    win_probability_wilson95: Tuple[float, float]
    outcomes: Tuple[EpisodeOutcome, ...] = ()

    @property
    def win_probability(self) -> float:
        return self.value.win_probability


@dataclass(frozen=True)
class Phase5DecisionEvaluation:
    best_action: ActionIntent
    estimates: Tuple[Phase5ActionEstimate, ...]
    rollout_count_per_action: int
    mc_root_seed: int
    horizon: int
    continuation_policy_id: str
    candidate_count: int = 0
    branch_pruned_count: int = 0
    pareto_pruned_count: int = 0
    version: str = PHASE5_MC_VERSION


def _wilson(successes: int, trials: int, z: float = 1.959963984540054):
    if trials <= 0:
        return (0.0, 1.0)
    p = successes / trials
    z2 = z * z
    denom = 1.0 + z2 / trials
    center = (p + z2 / (2.0 * trials)) / denom
    half = z * sqrt(max(0.0, p * (1.0 - p) / trials + z2 / (4.0 * trials * trials))) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def _representatives(actions: Iterable[ActionIntent]) -> Tuple[ActionIntent, ...]:
    rows = {}
    for action in sorted(actions, key=lambda a: a.action_id):
        rows.setdefault(action.strategic_key(), action)
    return tuple(rows[key] for key in sorted(rows, key=repr))


def _partial_objective_bounds(
    rows: Sequence[EpisodeOutcome],
    *,
    total_rollouts: int,
    horizon: int,
) -> Tuple[Tuple[float, ...], Tuple[float, ...]]:
    """Exact lower/upper final comparison keys for a partial fixed sample set.

    Lower bound assumes every unevaluated world is a loss. Upper bound assumes
    every unevaluated world is a T1 win, the strongest possible outcome under
    the Phase-3 objective.
    """
    total=int(total_rollouts)
    if total<1:
        raise ValueError("total_rollouts must be >= 1")
    seen=len(rows)
    if seen>total:
        raise ValueError("partial outcome count exceeds total rollouts")
    remaining=total-seen
    exact=[0]*int(horizon)
    for outcome in rows:
        if outcome.won:
            if outcome.win_turn is None:
                raise ValueError("winning outcome is missing win_turn")
            exact[int(outcome.win_turn)-1]+=1

    wins=sum(exact)
    cumulative=[]
    running=0
    for index in range(max(0,int(horizon)-1)):
        running+=exact[index]
        cumulative.append(running)

    lower=tuple(
        round(value/total,15)
        for value in (wins,*cumulative)
    )
    upper=tuple(
        round(value/total,15)
        for value in (
            wins+remaining,
            *(value+remaining for value in cumulative),
        )
    )
    return lower,upper


def _bound_prunable_keys(
    active_keys,
    outcomes,
    *,
    total_rollouts:int,
    horizon:int,
    retain_top_n:int,
    must_retain_keys,
):
    """Return exact fixed-sample losers that cannot enter the retained top-N.

    Two admissible tests are combined:
    1. lexicographic branch bound: candidate best-case < kth-best worst-case;
    2. Pareto bound: at least N other worst-case vectors component-dominate the
       candidate best-case vector.

    Strict inequalities preserve all possible ties.
    """
    active=tuple(active_keys)
    n=max(1,min(int(retain_top_n),len(active)))
    must=frozenset(must_retain_keys)
    bounds={
        key:_partial_objective_bounds(
            tuple(outcomes[key]),
            total_rollouts=total_rollouts,
            horizon=horizon,
        )
        for key in active
    }
    ranked_lower=sorted(
        (lower,key)
        for key,(lower,_upper) in bounds.items()
    )
    kth_lower=ranked_lower[-n][0]

    pruned=set()
    pareto_pruned=set()
    for key in active:
        if key in must:
            continue
        lower,upper=bounds[key]
        lexicographic=upper<kth_lower

        candidate_upper=ParetoPoint(key,tuple(upper))
        dominators=0
        for other,(other_lower,_other_upper) in bounds.items():
            if other==key:
                continue
            if pareto_dominates(
                ParetoPoint(other,tuple(other_lower)),
                candidate_upper,
            ):
                dominators+=1
                if dominators>=n:
                    break
        pareto=dominators>=n
        if lexicographic or pareto:
            pruned.add(key)
            if pareto:
                pareto_pruned.add(key)
    return frozenset(pruned),frozenset(pareto_pruned)


def _episode_outcome(result: NonOracleEpisodeResult, *, horizon: int) -> EpisodeOutcome:
    won = bool(result.won_by_horizon)
    return EpisodeOutcome(
        won=won,
        win_turn=int(result.win_turn) if won and result.win_turn is not None else None,
        terminal_turn=min(max(0, int(result.runtime.true_state.turn)), int(horizon)),
        horizon=int(horizon),
        win_family=str(result.win_family) if won else "",
        terminal_reason=str(result.terminal_reason),
    )


def _value(outcomes: Sequence[EpisodeOutcome], *, horizon: int) -> WinDistributionValue:
    if not outcomes:
        raise ValueError("at least one rollout outcome is required")
    exact = [0] * horizon
    families: Counter[str] = Counter()
    wins = 0
    for outcome in outcomes:
        if not outcome.won:
            continue
        assert outcome.win_turn is not None
        exact[int(outcome.win_turn) - 1] += 1
        wins += 1
        if outcome.win_family:
            families[outcome.win_family] += 1
    n = len(outcomes)
    return WinDistributionValue(
        horizon=horizon,
        exact_win=tuple(x / n for x in exact),
        no_win=(n - wins) / n,
        win_families=tuple((name, count / n) for name, count in sorted(families.items())),
    )



@dataclass
class Phase5DecisionCacheStats:
    hits: int = 0
    misses: int = 0
    evictions: int = 0


@dataclass(frozen=True, slots=True)
class _PackedEpisodeOutcomes:
    payload: bytes
    families: Tuple[str, ...]
    reasons: Tuple[str, ...]


def _pack_episode_outcomes(outcomes: Sequence[EpisodeOutcome]) -> _PackedEpisodeOutcomes:
    rows=tuple(outcomes)
    families=tuple(sorted(set(outcome.win_family for outcome in rows if outcome.win_family)))
    reasons=tuple(sorted(set(outcome.terminal_reason for outcome in rows)))
    family_index={"":0,**{name:index+1 for index,name in enumerate(families)}}
    reason_index={name:index for index,name in enumerate(reasons)}
    if len(families)>=255 or len(reasons)>=256:
        raise ValueError("too many compact outcome enum values")
    payload=bytearray()
    for outcome in rows:
        win_turn=0 if outcome.win_turn is None else int(outcome.win_turn)
        terminal_turn=int(outcome.terminal_turn)
        horizon=int(outcome.horizon)
        if not all(0<=value<=255 for value in (win_turn,terminal_turn,horizon)):
            raise ValueError("compact outcome integer outside byte range")
        payload.extend((
            win_turn,
            terminal_turn,
            horizon,
            family_index.get(outcome.win_family,0),
            reason_index[outcome.terminal_reason],
        ))
    return _PackedEpisodeOutcomes(bytes(payload),families,reasons)


def _unpack_episode_outcomes(packed: _PackedEpisodeOutcomes) -> Tuple[EpisodeOutcome, ...]:
    data=packed.payload
    if len(data)%5:
        raise ValueError("malformed compact outcome payload")
    rows=[]
    for offset in range(0,len(data),5):
        win_turn,terminal_turn,horizon,family_id,reason_id=data[offset:offset+5]
        family="" if family_id==0 else packed.families[family_id-1]
        reason=packed.reasons[reason_id]
        rows.append(EpisodeOutcome(
            won=bool(win_turn),
            win_turn=None if win_turn==0 else int(win_turn),
            terminal_turn=int(terminal_turn),
            horizon=int(horizon),
            win_family=family,
            terminal_reason=reason,
        ))
    return tuple(rows)


@dataclass(frozen=True, slots=True)
class _CachedPhase5ActionEstimate:
    strategic_action_key_packed: bytes
    value: WinDistributionValue
    rollouts: int
    terminal_reason_counts: Tuple[Tuple[str, int], ...]
    win_probability_wilson95: Tuple[float, float]
    packed_outcomes: _PackedEpisodeOutcomes


@dataclass(frozen=True, slots=True)
class _CachedPhase5Decision:
    best_strategic_action_key_packed: bytes
    estimates: Tuple[_CachedPhase5ActionEstimate, ...]


class Phase5DecisionCache:
    """Expected-value LRU cache keyed by strategic runtime/action identity.

    Cached rows never retain execution-specific ActionIntent objects. On a hit,
    the evaluator recovers the current legal action object by strategic_key(),
    mirroring the Phase-3 action-cache discipline.

    max_entries is a runtime-memory bound only. Eviction cannot change a Q value
    because every miss is recomputed from explicit deterministic seeds and the
    same information-safe strategic state. None preserves historical unbounded
    behavior for provenance tests.
    """

    def __init__(self, max_entries: int | None = None):
        if max_entries is not None and int(max_entries) < 1:
            raise ValueError("max_entries must be >= 1 or None")
        self.max_entries = None if max_entries is None else int(max_entries)
        self._rows = OrderedDict()
        self.stats = Phase5DecisionCacheStats()

    def get(self, key):
        if key not in self._rows:
            self.stats.misses += 1
            return None
        self.stats.hits += 1
        value = self._rows[key]
        self._rows.move_to_end(key)
        return value

    def set(self, key, value):
        if key in self._rows:
            self._rows[key] = value
            self._rows.move_to_end(key)
            return
        self._rows[key] = value
        if self.max_entries is not None and len(self._rows) > self.max_entries:
            self._rows.popitem(last=False)
            self.stats.evictions += 1

    def clear(self):
        self._rows.clear()

    def __len__(self):
        return len(self._rows)


class Phase5MonteCarloDecisionEvaluator:
    """Common-random-number Q estimate for the current visible decision."""

    def __init__(
        self,
        *,
        rollout_count: int = 8,
        mc_root_seed: int = 20260826,
        horizon: int = 6,
        objective: str = PHASE3_OBJECTIVE_ID,
        continuation_policy: DeterministicBasePolicy,
        max_episode_steps: int = 512,
        strict_terminal_reasons: bool = True,
        cache: Phase5DecisionCache | None = None,
        continuation_runner=None,
        continuation_id: str | None = None,
        sample_namespace: str = "default",
    ):
        if rollout_count < 1:
            raise ValueError("rollout_count must be >= 1")
        self.rollout_count = int(rollout_count)
        self.mc_root_seed = int(mc_root_seed)
        self.horizon = int(horizon)
        self.objective = str(objective)
        self.continuation_policy = continuation_policy
        self.max_episode_steps = int(max_episode_steps)
        self.strict_terminal_reasons = bool(strict_terminal_reasons)
        self.sampler = HiddenWorldSampler(self.mc_root_seed)
        self.cache = cache
        self.continuation_runner = continuation_runner
        self.continuation_id = str(
            continuation_id
            if continuation_id is not None
            else "deterministic-episode:" + self.continuation_policy.policy_id
        )
        self.sample_namespace = str(sample_namespace)

    def _request(self, runtime):
        return rules_decision_request(
            runtime,
            horizon=self.horizon,
            objective=self.objective,
            policy_id=self.continuation_policy.policy_id,
        )

    @staticmethod
    def _map(actions):
        return {
            packed_action_strategic_key(action): action
            for action in _representatives(actions)
        }


    def _cache_key(self, runtime, candidate_keys):
        return packed_phase5_decision_cache_key(
            runtime=runtime,
            candidate_action_keys=candidate_keys,
            rollout_count=self.rollout_count,
            mc_root_seed=self.mc_root_seed,
            horizon=self.horizon,
            objective=self.objective,
            policy_id=self.continuation_policy.policy_id,
            continuation_id=self.continuation_id,
            sample_namespace=self.sample_namespace,
            max_episode_steps=self.max_episode_steps,
            strict_terminal_reasons=self.strict_terminal_reasons,
        )

    def _restore_cached(self, cached, root_map):
        estimates=[]
        for row in cached.estimates:
            action=root_map.get(row.strategic_action_key_packed)
            if action is None:
                raise Phase5MonteCarloError(
                    "cached strategic action is not legal in current equivalent runtime"
                )
            estimates.append(Phase5ActionEstimate(
                action=action,
                value=row.value,
                rollouts=row.rollouts,
                terminal_reason_counts=row.terminal_reason_counts,
                win_probability_wilson95=row.win_probability_wilson95,
                outcomes=_unpack_episode_outcomes(row.packed_outcomes),
            ))
        best=root_map.get(cached.best_strategic_action_key_packed)
        if best is None:
            raise Phase5MonteCarloError(
                "cached best strategic action is not legal in current equivalent runtime"
            )
        return Phase5DecisionEvaluation(
            best_action=best,
            estimates=tuple(estimates),
            rollout_count_per_action=self.rollout_count,
            mc_root_seed=self.mc_root_seed,
            horizon=self.horizon,
            continuation_policy_id=self.continuation_policy.policy_id,
            candidate_count=len(candidate_keys),
            branch_pruned_count=len(branch_pruned),
            pareto_pruned_count=len(pareto_pruned),
        )

    def evaluate(
        self,
        runtime,
        *,
        candidate_actions=None,
        retain_top_n: int | None = None,
        must_retain_actions=(),
        exact_branch_bound: bool = False,
    ) -> Phase5DecisionEvaluation:
        root_request = self._request(runtime)
        all_root = _representatives(root_request.actions)
        if not all_root:
            raise Phase5MonteCarloError("decision has no modeled actions")

        if candidate_actions is None:
            root_actions = all_root
        else:
            allowed = {
                packed_action_strategic_key(action)
                for action in candidate_actions
            }
            root_actions = tuple(
                action for action in all_root
                if packed_action_strategic_key(action) in allowed
            )
            if not root_actions:
                raise Phase5MonteCarloError("candidate action subset is empty")

        root_observation_key = packed_observation_key(root_request.observation)
        root_keys = frozenset(
            packed_action_strategic_key(action)
            for action in all_root
        )
        candidate_keys = frozenset(
            packed_action_strategic_key(action)
            for action in root_actions
        )
        root_map = {
            packed_action_strategic_key(action): action
            for action in root_actions
        }

        must_retain_keys=frozenset(
            packed_action_strategic_key(action)
            for action in tuple(must_retain_actions or ())
        )
        if not must_retain_keys.issubset(candidate_keys):
            raise Phase5MonteCarloError(
                "must-retain action is absent from candidate action subset"
            )
        retain_n=(
            len(candidate_keys)
            if retain_top_n is None
            else max(1,min(int(retain_top_n),len(candidate_keys)))
        )

        cache_key=None
        if self.cache is not None:
            cache_key=self._cache_key(runtime,candidate_keys)
            if exact_branch_bound:
                cache_key += (
                    b"\x00branch-bound-v1\x00"
                    + str(retain_n).encode("ascii")
                    + b"\x00"
                    + b"".join(sorted(must_retain_keys))
                )
            cached=self.cache.get(cache_key)
            if cached is not None:
                return self._restore_cached(cached,root_map)

        belief = LibraryBeliefKey.from_state(runtime.true_state, runtime.information)

        outcomes = {key: [] for key in candidate_keys}
        reasons = {key: Counter() for key in candidate_keys}
        active_keys=set(candidate_keys)
        branch_pruned=set()
        pareto_pruned=set()

        for sample_index in range(self.rollout_count):
            world = self.sampler.sample(
                belief,
                sample_id=(
                    "phase5-q",
                    self.sample_namespace,
                    sample_index,
                ),
            )
            sampled_runtime = materialize_hidden_world(runtime, world)
            sampled_request = self._request(sampled_runtime)
            if packed_observation_key(sampled_request.observation) != root_observation_key:
                raise Phase5MonteCarloError(
                    "sampled hidden world changed current PolicyView before observation"
                )
            sampled_all = self._map(sampled_request.actions)
            if frozenset(sampled_all) != root_keys:
                raise Phase5MonteCarloError(
                    "sampled hidden world changed the policy-visible action set"
                )

            for key in sorted(active_keys, key=repr):
                action = sampled_all[key]
                after = apply_main_action(sampled_runtime, action)
                if self.continuation_runner is None:
                    result = run_deterministic_episode(
                        after,
                        horizon=self.horizon,
                        policy=self.continuation_policy,
                        max_steps=self.max_episode_steps,
                        max_recorded_steps=12,
                    )
                else:
                    result = self.continuation_runner(
                        after,
                        root_action=action,
                        horizon=self.horizon,
                        policy=self.continuation_policy,
                        max_steps=self.max_episode_steps,
                    )
                reason = str(result.terminal_reason)
                reasons[key][reason] += 1
                if self.strict_terminal_reasons and reason not in MODELED_TERMINALS:
                    tail = tuple(
                        (step.turn_before, step.action_kind, step.action_label)
                        for step in result.steps[-12:]
                    )
                    public_board = tuple(
                        (perm.name, bool(perm.tapped), int(perm.counters), perm.mode)
                        for perm in result.runtime.true_state.battlefield
                    )
                    raise Phase5MonteCarloError(
                        "rollout hard blocker: "
                        f"sample={sample_index}; "
                        f"root_action={sampled_all[key].label!r}; "
                        f"action_id={sampled_all[key].action_id!r}; "
                        f"reason={reason!r}; "
                        f"turn={result.runtime.true_state.turn}; "
                        f"hand={tuple(result.runtime.true_state.hand)!r}; "
                        f"battlefield={public_board!r}; "
                        f"tail={tail!r}"
                    )
                outcomes[key].append(_episode_outcome(result, horizon=self.horizon))

            if exact_branch_bound and len(active_keys)>retain_n:
                newly_pruned,newly_pareto=_bound_prunable_keys(
                    active_keys,
                    outcomes,
                    total_rollouts=self.rollout_count,
                    horizon=self.horizon,
                    retain_top_n=retain_n,
                    must_retain_keys=must_retain_keys,
                )
                if newly_pruned:
                    active_keys.difference_update(newly_pruned)
                    branch_pruned.update(newly_pruned)
                    pareto_pruned.update(newly_pareto)

        estimates = []
        for key in sorted(active_keys, key=repr):
            rows = tuple(outcomes[key])
            value = _value(rows, horizon=self.horizon)
            wins = sum(x.won for x in rows)
            estimates.append(
                Phase5ActionEstimate(
                    action=root_map[key],
                    value=value,
                    rollouts=len(rows),
                    terminal_reason_counts=tuple(sorted(reasons[key].items())),
                    win_probability_wilson95=_wilson(wins, len(rows)),
                    outcomes=rows,
                )
            )

        ranked = tuple(
            sorted(
                estimates,
                key=lambda est: (
                    est.value.comparison_key(),
                    repr(est.action.strategic_key()),
                ),
                reverse=True,
            )
        )
        evaluation=Phase5DecisionEvaluation(
            best_action=ranked[0].action,
            estimates=ranked,
            rollout_count_per_action=self.rollout_count,
            mc_root_seed=self.mc_root_seed,
            horizon=self.horizon,
            continuation_policy_id=self.continuation_policy.policy_id,
        )
        if self.cache is not None and cache_key is not None:
            self.cache.set(cache_key,_CachedPhase5Decision(
                best_strategic_action_key_packed=packed_action_strategic_key(
                    evaluation.best_action
                ),
                estimates=tuple(
                    _CachedPhase5ActionEstimate(
                        strategic_action_key_packed=packed_action_strategic_key(
                            estimate.action
                        ),
                        value=estimate.value,
                        rollouts=estimate.rollouts,
                        terminal_reason_counts=estimate.terminal_reason_counts,
                        win_probability_wilson95=estimate.win_probability_wilson95,
                        packed_outcomes=_pack_episode_outcomes(estimate.outcomes),
                    )
                    for estimate in evaluation.estimates
                ),
            ))
        return evaluation
