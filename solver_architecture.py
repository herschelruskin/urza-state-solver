#!/usr/bin/env python3
"""Markov/DP/Monte-Carlo architecture contracts for the Urza solver.

This module deliberately does not execute Magic rules.  It provides the stable
interfaces around the validated Oracle engine that future non-Oracle policies,
DP, memoization, replay, and Monte-Carlo rollouts should consume.

Design invariants:
- policies never receive exact hidden library order;
- canonical keys are deterministic across Python processes;
- every future-relevant public permanent/state field is preserved;
- random streams are explicit and independently derived from one root seed;
- action identity is distinct from action-equivalence identity;
- V/Q cache namespaces include objective, horizon, policy and information state;
- trajectories record action/RNG coordinates and state fingerprints;
- terminal output preserves exact win turn through the configured horizon.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, fields, is_dataclass
from hashlib import sha256
from typing import Any, Dict, Generic, Iterable, Mapping, MutableMapping, Optional, Protocol, Sequence, Tuple, TypeVar
import json
import random

TState = TypeVar("TState")
TValue = TypeVar("TValue")

RNG_SCHEME_VERSION = "urza-rng-v3-keyed-state"
STATE_KEY_VERSION = "urza-state-key-v3"
POLICY_VIEW_VERSION = "urza-policy-view-v2"
TRAJECTORY_VERSION = "urza-trajectory-v2"


def _tagged(value: Any) -> Any:
    """Return a deterministic hashable representation without Python hash()."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if is_dataclass(value):
        return (
            "dataclass",
            value.__class__.__qualname__,
            tuple((f.name, _tagged(getattr(value, f.name))) for f in fields(value)),
        )
    if isinstance(value, tuple):
        return ("tuple", tuple(_tagged(v) for v in value))
    if isinstance(value, list):
        return ("list", tuple(_tagged(v) for v in value))
    if isinstance(value, (set, frozenset)):
        return ("set", tuple(sorted((_tagged(v) for v in value), key=repr)))
    if isinstance(value, Mapping):
        items = sorted(((_tagged(k), _tagged(v)) for k, v in value.items()), key=lambda kv: repr(kv[0]))
        return ("mapping", tuple(items))
    if hasattr(value, "__dict__"):
        items = sorted(((str(k), _tagged(v)) for k, v in vars(value).items()), key=lambda kv: kv[0])
        return ("object", value.__class__.__qualname__, tuple(items))
    raise TypeError(f"Cannot canonicalize {type(value)!r}")


def stable_key(value: Any, *, version: str = STATE_KEY_VERSION) -> Tuple[Any, ...]:
    return (version, _tagged(value))


def stable_digest(value: Any, *, version: str = STATE_KEY_VERSION) -> str:
    return sha256(repr(stable_key(value, version=version)).encode("utf-8")).hexdigest()


@dataclass(frozen=True, order=True)
class PublicPermanent:
    """Policy-visible permanent state.

    `knack_source` and `instance_tag` from Oracle Perm are intentionally omitted:
    they are provenance/runtime identity, not strategic state. `knack_granted`
    and `producer_urza_ready` are retained because they change future legality.
    """

    name: str
    tapped: bool = False
    sick: bool = False
    counters: int = 0
    mode: str = ""
    knack_granted: bool = False
    producer_urza_ready: bool = False


def _public_perm(perm: Any) -> PublicPermanent:
    return PublicPermanent(
        name=str(getattr(perm, "name")),
        tapped=bool(getattr(perm, "tapped", False)),
        sick=bool(getattr(perm, "sick", False)),
        counters=int(getattr(perm, "counters", 0)),
        mode=str(getattr(perm, "mode", "")),
        knack_granted=bool(getattr(perm, "knack_granted", False)),
        producer_urza_ready=bool(getattr(perm, "producer_urza_ready", False)),
    )


def _canonical_battlefield(permanents: Iterable[Any]) -> Tuple[PublicPermanent, ...]:
    return tuple(sorted((_public_perm(p) for p in permanents)))


def _canonical_state_values(state: Any, *, exclude: frozenset[str] = frozenset()) -> Dict[str, Any]:
    if not is_dataclass(state):
        raise TypeError("canonical state projection requires a dataclass state")
    values: Dict[str, Any] = {}
    for f in fields(state):
        if f.name in exclude:
            continue
        value = getattr(state, f.name)
        if f.name == "hand":
            value = tuple(sorted(value))
        elif f.name == "battlefield":
            value = _canonical_battlefield(value)
        elif f.name in {"graveyard", "exile", "interaction_seen"}:
            value = tuple(sorted(value))
        values[f.name] = value
    return values


def canonical_true_state_key(state: Any) -> Tuple[Any, ...]:
    """Conservative replay/debug key including trajectory provenance."""
    if not is_dataclass(state):
        return stable_key(state)
    return stable_key(_canonical_state_values(state))


def canonical_markov_state_key(state: Any) -> Tuple[Any, ...]:
    """Canonical future-relevant true state for Markov transitions.

    `trace`, `interaction_seen`, and `urza_cast_turn` are reporting/provenance
    history rather than rules state.  They must not influence future shuffles or
    transposition identity.  Hidden library order, the explicit RNG root seed,
    pending phases, mana, exact permanent grants/refund credits, commander state,
    and all other dataclass fields remain represented.
    """
    if not is_dataclass(state):
        return stable_key(state)
    return stable_key(
        _canonical_state_values(
            state,
            exclude=frozenset({"trace", "interaction_seen", "urza_cast_turn"}),
        )
    )


def deduced_library_counts(true_state: Any) -> Tuple[Tuple[str, int], ...]:
    """Return the order-free multiset a player can deduce remains in their library.

    This simulator models one known Commander deck and the player's own zones.
    Every modeled movement into or out of that library is known to the player.
    Therefore card membership/count is logically knowable even when positional
    order is not.  Reading the concrete library Counter is an implementation
    shortcut for subtracting all known nonlibrary zones from the fixed decklist.
    """
    counts = Counter(str(card) for card in getattr(true_state, "library", ()))
    return tuple(sorted(
        (card, int(count))
        for card, count in counts.items()
        if int(count) > 0
    ))


@dataclass(frozen=True)
class InformationState:
    """Persistent legal knowledge about hidden zones."""

    known_top: Tuple[str, ...] = ()
    known_bottom: Tuple[str, ...] = ()
    known_library_counts: Tuple[Tuple[str, int], ...] = ()
    shuffle_epoch: int = 0

    def key(self) -> Tuple[Any, ...]:
        return stable_key(self, version=POLICY_VIEW_VERSION)

    def after_shuffle(self) -> "InformationState":
        return InformationState(
            known_top=(),
            known_bottom=(),
            known_library_counts=self.known_library_counts,
            shuffle_epoch=self.shuffle_epoch + 1,
        )


@dataclass(frozen=True)
class PolicyView:
    """Read-only player observation. Exact unknown library order is absent."""

    turn: int
    hand: Tuple[str, ...]
    battlefield: Tuple[PublicPermanent, ...]
    graveyard: Tuple[str, ...]
    exile: Tuple[str, ...]
    blue: int
    colorless: int
    land_played: bool
    drain_bank: int
    bauble_draws: int
    remora_age: int
    remora_upkeep_pending: bool
    saga3_pending: bool
    ring_counters: int
    ftt_level: int
    uthros_counters: int
    urza: bool
    construct: bool
    top_access: bool
    chip_attached: bool
    chip_target: str
    spell_cast_this_turn: bool
    pa_target: str
    vfc_pumps: int
    commander_in_command_zone: bool
    commander_casts_from_zone: int
    urza_exile_permissions: Tuple[str, ...] = ()
    known_top: Tuple[str, ...] = ()
    known_bottom: Tuple[str, ...] = ()
    known_library_counts: Tuple[Tuple[str, int], ...] = ()
    caverns_live: Optional[bool] = None

    def key(self) -> Tuple[Any, ...]:
        return stable_key(self, version=POLICY_VIEW_VERSION)


def make_policy_view(true_state: Any, information: InformationState, *, caverns_live: Optional[bool] = None) -> PolicyView:
    """Derive a policy-safe observation from TrueState + InformationState."""
    return PolicyView(
        turn=int(getattr(true_state, "turn")),
        hand=tuple(sorted(getattr(true_state, "hand", ()))),
        battlefield=_canonical_battlefield(getattr(true_state, "battlefield", ())),
        graveyard=tuple(sorted(getattr(true_state, "graveyard", ()))),
        exile=tuple(sorted(getattr(true_state, "exile", ()))),
        blue=int(getattr(true_state, "blue", 0)),
        colorless=int(getattr(true_state, "colorless", 0)),
        land_played=bool(getattr(true_state, "land_played", False)),
        drain_bank=int(getattr(true_state, "drain_bank", 0)),
        bauble_draws=int(getattr(true_state, "bauble_draws", 0)),
        remora_age=int(getattr(true_state, "remora_age", 0)),
        remora_upkeep_pending=bool(getattr(true_state, "remora_upkeep_pending", False)),
        saga3_pending=bool(getattr(true_state, "saga3_pending", False)),
        ring_counters=int(getattr(true_state, "ring_counters", 0)),
        ftt_level=int(getattr(true_state, "ftt_level", 1)),
        uthros_counters=int(getattr(true_state, "uthros_counters", 0)),
        urza=bool(getattr(true_state, "urza", False)),
        construct=bool(getattr(true_state, "construct", False)),
        top_access=bool(getattr(true_state, "top_access", False)),
        chip_attached=bool(getattr(true_state, "chip_attached", False)),
        chip_target=str(getattr(true_state, "chip_target", "")),
        spell_cast_this_turn=bool(getattr(true_state, "spell_cast_this_turn", False)),
        pa_target=str(getattr(true_state, "pa_target", "")),
        vfc_pumps=int(getattr(true_state, "vfc_pumps", 0)),
        commander_in_command_zone=bool(getattr(true_state, "commander_in_command_zone", True)),
        commander_casts_from_zone=int(getattr(true_state, "commander_casts_from_zone", 0)),
        urza_exile_permissions=tuple(sorted(getattr(true_state, "urza_exile_permissions", ()))),
        known_top=tuple(information.known_top),
        known_bottom=tuple(information.known_bottom),
        known_library_counts=deduced_library_counts(true_state),
        caverns_live=caverns_live,
    )


@dataclass(frozen=True)
class PolicyAction:
    action_id: str
    kind: str
    parameters: Tuple[Tuple[str, Any], ...] = ()
    equivalence_key: Tuple[Any, ...] = ()
    label: str = ""

    def canonical_key(self) -> Tuple[Any, ...]:
        return stable_key((self.kind, tuple(sorted(self.parameters)), self.action_id))

    def strategic_key(self) -> Tuple[Any, ...]:
        return stable_key(self.equivalence_key) if self.equivalence_key else self.canonical_key()


@dataclass(frozen=True)
class PolicyContext:
    root_seed: int
    horizon: int
    objective: str = "win_by_horizon"
    policy_id: str = "base"


class Policy(Protocol):
    def choose(self, observation: PolicyView, actions: Sequence[PolicyAction], context: PolicyContext) -> PolicyAction:
        ...


class RulesEngine(Protocol, Generic[TState]):
    def legal_actions(self, state: TState) -> Sequence[PolicyAction]:
        ...

    def apply_action(self, state: TState, action: PolicyAction, rng: random.Random) -> TState:
        ...


class ReplayRules(RulesEngine[TState], Protocol):
    def action_from_id(self, state: TState, action_id: str) -> PolicyAction:
        ...


def collapse_action_equivalence(actions: Iterable[PolicyAction]) -> Tuple[PolicyAction, ...]:
    """Keep one deterministic representative per explicitly equivalent action."""
    representatives: Dict[Tuple[Any, ...], PolicyAction] = {}
    for action in sorted(actions, key=lambda a: a.action_id):
        representatives.setdefault(action.strategic_key(), action)
    return tuple(sorted(representatives.values(), key=lambda a: a.action_id))


@dataclass(frozen=True)
class RandomStreams:
    root_seed: int
    scheme_version: str = RNG_SCHEME_VERSION

    def seed_for(self, namespace: str, event_id: Any) -> int:
        payload = f"{self.scheme_version}|{self.root_seed}|{namespace}|{repr(event_id)}".encode("utf-8")
        return int.from_bytes(sha256(payload).digest()[:16], "big")

    def rng(self, namespace: str, event_id: Any) -> random.Random:
        return random.Random(self.seed_for(namespace, event_id))

    def game_rng(self, event_id: Any) -> random.Random:
        return self.rng("game", event_id)

    def environment_rng(self, event_id: Any) -> random.Random:
        return self.rng("environment", event_id)

    def policy_rng(self, event_id: Any) -> random.Random:
        return self.rng("policy", event_id)

    def tie_rng(self, event_id: Any) -> random.Random:
        return self.rng("tie", event_id)


@dataclass(frozen=True)
class TrajectoryEvent:
    index: int
    turn: int
    action_id: str
    state_before: str
    state_after: str
    observation: str = ""
    rng_namespace: str = ""
    rng_event: str = ""
    note: str = ""


@dataclass(frozen=True)
class Trajectory:
    root_seed: int
    horizon: int
    events: Tuple[TrajectoryEvent, ...] = ()
    version: str = TRAJECTORY_VERSION

    def append(self, event: TrajectoryEvent) -> "Trajectory":
        if event.index != len(self.events):
            raise ValueError(f"trajectory index {event.index} != expected {len(self.events)}")
        return Trajectory(self.root_seed, self.horizon, self.events + (event,), self.version)

    def digest(self) -> str:
        return stable_digest(self, version=self.version)

    def to_jsonl(self) -> str:
        rows = [json.dumps({"type": "trajectory", "version": self.version, "root_seed": self.root_seed, "horizon": self.horizon}, sort_keys=True)]
        for event in self.events:
            row = asdict(event)
            row["type"] = "event"
            rows.append(json.dumps(row, sort_keys=True))
        return "\n".join(rows) + "\n"

    @classmethod
    def from_jsonl(cls, text: str) -> "Trajectory":
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
        if not rows or rows[0].get("type") != "trajectory":
            raise ValueError("missing trajectory header")
        header = rows[0]
        out = cls(int(header["root_seed"]), int(header["horizon"]), version=str(header["version"]))
        for raw in rows[1:]:
            if raw.pop("type", None) != "event":
                raise ValueError("unexpected trajectory row")
            out = out.append(TrajectoryEvent(**raw))
        return out


def replay_trajectory(engine: ReplayRules[TState], initial_state: TState, trajectory: Trajectory) -> TState:
    streams = RandomStreams(trajectory.root_seed)
    state = initial_state
    for event in trajectory.events:
        before = stable_digest(canonical_true_state_key(state))
        if before != event.state_before:
            raise AssertionError(f"replay divergence before event {event.index}")
        action = engine.action_from_id(state, event.action_id)
        rng = streams.rng(event.rng_namespace or "game", event.rng_event or event.index)
        state = engine.apply_action(state, action, rng)
        after = stable_digest(canonical_true_state_key(state))
        if after != event.state_after:
            raise AssertionError(f"replay divergence after event {event.index}")
    return state


@dataclass
class MemoizationStats:
    v_hits: int = 0
    v_misses: int = 0
    q_hits: int = 0
    q_misses: int = 0


_MISSING = object()


class MemoizationStore(Generic[TValue]):
    def __init__(self) -> None:
        self._v: MutableMapping[Tuple[Any, ...], TValue] = {}
        self._q: MutableMapping[Tuple[Any, ...], TValue] = {}
        self.stats = MemoizationStats()

    @staticmethod
    def value_key(state_key: Tuple[Any, ...], *, horizon: int, objective: str, policy_id: str, information_key: Optional[Tuple[Any, ...]] = None) -> Tuple[Any, ...]:
        return ("V", horizon, objective, policy_id, information_key, state_key)

    @staticmethod
    def q_key(state_key: Tuple[Any, ...], action_key: Tuple[Any, ...], *, horizon: int, objective: str, policy_id: str, information_key: Optional[Tuple[Any, ...]] = None) -> Tuple[Any, ...]:
        return ("Q", horizon, objective, policy_id, information_key, state_key, action_key)

    def get_v(self, key: Tuple[Any, ...], default: Any = None) -> Any:
        value = self._v.get(key, _MISSING)
        if value is _MISSING:
            self.stats.v_misses += 1
            return default
        self.stats.v_hits += 1
        return value

    def set_v(self, key: Tuple[Any, ...], value: TValue) -> None:
        self._v[key] = value

    def get_q(self, key: Tuple[Any, ...], default: Any = None) -> Any:
        value = self._q.get(key, _MISSING)
        if value is _MISSING:
            self.stats.q_misses += 1
            return default
        self.stats.q_hits += 1
        return value

    def set_q(self, key: Tuple[Any, ...], value: TValue) -> None:
        self._q[key] = value


@dataclass(frozen=True)
class EpisodeOutcome:
    won: bool
    win_turn: Optional[int]
    terminal_turn: int
    horizon: int
    win_family: str = ""
    terminal_reason: str = "horizon"

    def __post_init__(self) -> None:
        if self.won != (self.win_turn is not None):
            raise ValueError("won and win_turn disagree")
        if self.win_turn is not None and not (1 <= self.win_turn <= self.horizon):
            raise ValueError("win_turn outside horizon")
        if not (0 <= self.terminal_turn <= self.horizon):
            raise ValueError("terminal_turn outside horizon")

    def win_by(self, turn: int) -> bool:
        return self.win_turn is not None and self.win_turn <= turn


def terminal_outcome_from_state(state: Any, *, horizon: int) -> EpisodeOutcome:
    won = bool(getattr(state, "won", False))
    turn = min(int(getattr(state, "turn", horizon)), horizon)
    return EpisodeOutcome(
        won=won,
        win_turn=turn if won else None,
        terminal_turn=turn,
        horizon=horizon,
        win_family=str(getattr(state, "win_family", "")) if won else "",
        terminal_reason="win" if won else "horizon",
    )


def cumulative_win_curve(outcomes: Iterable[EpisodeOutcome], horizon: int) -> Tuple[Tuple[int, float], ...]:
    rows = tuple(outcomes)
    if not rows:
        return tuple((turn, 0.0) for turn in range(1, horizon + 1))
    return tuple((turn, sum(outcome.win_by(turn) for outcome in rows) / len(rows)) for turn in range(1, horizon + 1))
