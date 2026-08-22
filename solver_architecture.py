#!/usr/bin/env python3
"""Architecture contracts for the Urza state solver.

This module is intentionally rules-light.  It provides the boundaries needed by
future knowledge-constrained / DP / Monte-Carlo solvers without changing the
validated Oracle engine in ``urza_solver.py``.

The key design rule is that rules execution may hold a complete true state, but a
policy receives only a derived ``PolicyView`` plus opaque ``PolicyAction``
objects.  The helpers here are deterministic and use only the Python standard
library.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields, is_dataclass
from hashlib import sha256
from typing import (
    Any,
    Dict,
    Generic,
    Iterable,
    Mapping,
    MutableMapping,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    TypeVar,
)
import json
import random


TState = TypeVar("TState")
TValue = TypeVar("TValue")

RNG_SCHEME_VERSION = "urza-rng-v1"
STATE_KEY_VERSION = "urza-state-key-v1"
POLICY_VIEW_VERSION = "urza-policy-view-v1"
TRAJECTORY_VERSION = "urza-trajectory-v1"


def _tagged(value: Any) -> Any:
    """Return a deterministic, hashable representation of ``value``.

    The representation deliberately keeps list/tuple/set/dict distinctions so
    unrelated Python objects cannot silently collide after canonicalization.
    Dataclass field order is stable by definition; mapping and set members are
    sorted by their canonical representation.
    """

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
        members = sorted((_tagged(v) for v in value), key=repr)
        return ("set", tuple(members))
    if isinstance(value, Mapping):
        items = sorted(
            ((_tagged(k), _tagged(v)) for k, v in value.items()),
            key=lambda kv: repr(kv[0]),
        )
        return ("mapping", tuple(items))
    if hasattr(value, "__dict__"):
        items = sorted(
            ((str(k), _tagged(v)) for k, v in vars(value).items()),
            key=lambda kv: kv[0],
        )
        return ("object", value.__class__.__qualname__, tuple(items))
    raise TypeError(f"Cannot canonicalize value of type {type(value)!r}")


def stable_key(value: Any, *, version: str = STATE_KEY_VERSION) -> Tuple[Any, ...]:
    """Return a process-independent hashable key.

    Unlike Python's built-in ``hash()``, this key is stable across interpreter
    processes and ``PYTHONHASHSEED`` values.
    """

    return (version, _tagged(value))


def stable_digest(value: Any, *, version: str = STATE_KEY_VERSION) -> str:
    """Return a compact SHA-256 fingerprint for logs / persistent caches."""

    payload = repr(stable_key(value, version=version)).encode("utf-8")
    return sha256(payload).hexdigest()


def _public_perm(perm: Any) -> "PublicPermanent":
    return PublicPermanent(
        name=str(getattr(perm, "name")),
        tapped=bool(getattr(perm, "tapped", False)),
        sick=bool(getattr(perm, "sick", False)),
        counters=int(getattr(perm, "counters", 0)),
        mode=str(getattr(perm, "mode", "")),
    )


def canonical_true_state_key(state: Any) -> Tuple[Any, ...]:
    """Canonical *complete* state key for exact transposition / replay checks.

    This is conservative by design: every dataclass field is represented,
    including ordered library contents and legacy trace data.  That makes it
    safe for the current Oracle implementation, whose shuffle helper still
    depends on ``len(trace)``.  Once all randomness is explicit and history
    independent, callers may introduce a narrower strategic projection for
    value caching, but they must do so deliberately and with tests.

    Hand and battlefield iteration order are canonicalized because the current
    solver already treats those zones as strategically unordered.  Other zones
    are kept in their stored order unless a future rules audit proves otherwise.
    """

    if not is_dataclass(state):
        return stable_key(state)

    values: Dict[str, Any] = {}
    for f in fields(state):
        value = getattr(state, f.name)
        if f.name == "hand":
            value = tuple(sorted(value))
        elif f.name == "battlefield":
            value = tuple(
                sorted(
                    (_public_perm(p) for p in value),
                    key=lambda p: (p.name, p.tapped, p.sick, p.counters, p.mode),
                )
            )
        values[f.name] = value
    return stable_key(values)


@dataclass(frozen=True)
class InformationState:
    """Persistent player knowledge about otherwise hidden library information."""

    known_top: Tuple[str, ...] = ()
    known_bottom: Tuple[str, ...] = ()
    known_library_counts: Tuple[Tuple[str, int], ...] = ()
    shuffle_epoch: int = 0

    def key(self) -> Tuple[Any, ...]:
        return stable_key(self, version=POLICY_VIEW_VERSION)

    def after_shuffle(self) -> "InformationState":
        """Invalidate positional knowledge while preserving known composition."""

        return InformationState(
            known_top=(),
            known_bottom=(),
            known_library_counts=self.known_library_counts,
            shuffle_epoch=self.shuffle_epoch + 1,
        )


@dataclass(frozen=True, order=True)
class PublicPermanent:
    name: str
    tapped: bool = False
    sick: bool = False
    counters: int = 0
    mode: str = ""


@dataclass(frozen=True)
class PolicyView:
    """Read-only observation given to a policy.

    There is intentionally no raw ``library`` field.  Hidden positional
    knowledge may appear only through ``known_top`` / ``known_bottom``.
    """

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
    ring_counters: int
    ftt_level: int
    uthros_counters: int
    urza: bool
    construct: bool
    top_access: bool
    chip_attached: bool
    chip_target: str
    spell_cast_this_turn: bool
    knack_target: str
    pa_target: str
    vfc_pumps: int
    commander_in_command_zone: bool
    commander_casts_from_zone: int
    known_top: Tuple[str, ...] = ()
    known_bottom: Tuple[str, ...] = ()
    known_library_counts: Tuple[Tuple[str, int], ...] = ()
    caverns_live: Optional[bool] = None

    def key(self) -> Tuple[Any, ...]:
        return stable_key(self, version=POLICY_VIEW_VERSION)


def make_policy_view(
    true_state: Any,
    information: InformationState,
    *,
    caverns_live: Optional[bool] = None,
) -> PolicyView:
    """Derive a policy-safe observation from a complete simulator state."""

    battlefield = tuple(
        sorted(
            (_public_perm(p) for p in getattr(true_state, "battlefield", ())),
            key=lambda p: (p.name, p.tapped, p.sick, p.counters, p.mode),
        )
    )
    return PolicyView(
        turn=int(getattr(true_state, "turn")),
        hand=tuple(sorted(getattr(true_state, "hand", ()))),
        battlefield=battlefield,
        graveyard=tuple(getattr(true_state, "graveyard", ())),
        exile=tuple(getattr(true_state, "exile", ())),
        blue=int(getattr(true_state, "blue", 0)),
        colorless=int(getattr(true_state, "colorless", 0)),
        land_played=bool(getattr(true_state, "land_played", False)),
        drain_bank=int(getattr(true_state, "drain_bank", 0)),
        bauble_draws=int(getattr(true_state, "bauble_draws", 0)),
        remora_age=int(getattr(true_state, "remora_age", 0)),
        ring_counters=int(getattr(true_state, "ring_counters", 0)),
        ftt_level=int(getattr(true_state, "ftt_level", 1)),
        uthros_counters=int(getattr(true_state, "uthros_counters", 0)),
        urza=bool(getattr(true_state, "urza", False)),
        construct=bool(getattr(true_state, "construct", False)),
        top_access=bool(getattr(true_state, "top_access", False)),
        chip_attached=bool(getattr(true_state, "chip_attached", False)),
        chip_target=str(getattr(true_state, "chip_target", "")),
        spell_cast_this_turn=bool(getattr(true_state, "spell_cast_this_turn", False)),
        knack_target=str(getattr(true_state, "knack_target", "")),
        pa_target=str(getattr(true_state, "pa_target", "")),
        vfc_pumps=int(getattr(true_state, "vfc_pumps", 0)),
        commander_in_command_zone=bool(
            getattr(true_state, "commander_in_command_zone", True)
        ),
        commander_casts_from_zone=int(
            getattr(true_state, "commander_casts_from_zone", 0)
        ),
        known_top=tuple(information.known_top),
        known_bottom=tuple(information.known_bottom),
        known_library_counts=tuple(sorted(information.known_library_counts)),
        caverns_live=caverns_live,
    )


@dataclass(frozen=True)
class PolicyAction:
    """Opaque action descriptor visible to a policy.

    ``action_id`` is the replay identity.  ``equivalence_key`` describes the
    future-relevant strategic effect used for safe duplicate collapsing.
    ``parameters`` contain only information the player is legally entitled to
    use at this decision point.
    """

    action_id: str
    kind: str
    parameters: Tuple[Tuple[str, Any], ...] = ()
    equivalence_key: Tuple[Any, ...] = ()
    label: str = ""

    def canonical_key(self) -> Tuple[Any, ...]:
        return stable_key(
            (self.kind, tuple(sorted(self.parameters)), self.action_id),
            version=STATE_KEY_VERSION,
        )

    def strategic_key(self) -> Tuple[Any, ...]:
        if self.equivalence_key:
            return stable_key(self.equivalence_key, version=STATE_KEY_VERSION)
        return self.canonical_key()


@dataclass(frozen=True)
class PolicyContext:
    root_seed: int
    horizon: int
    objective: str = "win_by_horizon"
    policy_id: str = "base"


class Policy(Protocol):
    """Decision policy boundary.  No true state is accepted here."""

    def choose(
        self,
        observation: PolicyView,
        actions: Sequence[PolicyAction],
        context: PolicyContext,
    ) -> PolicyAction:
        ...


class RulesEngine(Protocol, Generic[TState]):
    """Rules-execution boundary kept separate from ``Policy``."""

    def legal_actions(self, state: TState) -> Sequence[PolicyAction]:
        ...

    def apply_action(
        self,
        state: TState,
        action: PolicyAction,
        rng: random.Random,
    ) -> TState:
        ...


class ReplayRules(RulesEngine[TState], Protocol):
    def action_from_id(self, state: TState, action_id: str) -> PolicyAction:
        ...


def collapse_action_equivalence(
    actions: Iterable[PolicyAction],
) -> Tuple[PolicyAction, ...]:
    """Collapse provably equivalent actions deterministically.

    The representative with the lexicographically smallest ``action_id`` wins.
    Strategically distinct tutor targets therefore remain distinct unless their
    caller explicitly gives them the same ``equivalence_key``.
    """

    representatives: Dict[Tuple[Any, ...], PolicyAction] = {}
    for action in sorted(actions, key=lambda a: a.action_id):
        key = action.strategic_key()
        representatives.setdefault(key, action)
    return tuple(sorted(representatives.values(), key=lambda a: a.action_id))


@dataclass(frozen=True)
class RandomStreams:
    """Deterministic independent RNG namespaces derived from one root seed.

    RNG coordinates are explicit: ``namespace`` and ``event_id`` determine a
    stream.  Increasing Monte-Carlo rollout count cannot perturb the actual game
    stream because policy samples live in a different namespace.
    """

    root_seed: int
    scheme_version: str = RNG_SCHEME_VERSION

    def seed_for(self, namespace: str, event_id: Any) -> int:
        payload = (
            f"{self.scheme_version}|{self.root_seed}|{namespace}|{repr(event_id)}"
        ).encode("utf-8")
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
            raise ValueError(
                f"trajectory index {event.index} != expected {len(self.events)}"
            )
        return Trajectory(
            root_seed=self.root_seed,
            horizon=self.horizon,
            events=self.events + (event,),
            version=self.version,
        )

    def digest(self) -> str:
        return stable_digest(self, version=self.version)

    def to_jsonl(self) -> str:
        header = json.dumps(
            {
                "type": "trajectory",
                "version": self.version,
                "root_seed": self.root_seed,
                "horizon": self.horizon,
            },
            sort_keys=True,
        )
        rows = [header]
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
        trajectory = cls(
            root_seed=int(header["root_seed"]),
            horizon=int(header["horizon"]),
            version=str(header["version"]),
        )
        for raw in rows[1:]:
            if raw.pop("type", None) != "event":
                raise ValueError("unexpected trajectory row")
            trajectory = trajectory.append(TrajectoryEvent(**raw))
        return trajectory


def replay_trajectory(
    engine: ReplayRules[TState],
    initial_state: TState,
    trajectory: Trajectory,
) -> TState:
    """Replay and verify a trajectory using stable action/RNG coordinates."""

    streams = RandomStreams(trajectory.root_seed)
    state = initial_state
    for event in trajectory.events:
        before = stable_digest(canonical_true_state_key(state))
        if before != event.state_before:
            raise AssertionError(
                f"replay divergence before event {event.index}: {before} != {event.state_before}"
            )
        action = engine.action_from_id(state, event.action_id)
        namespace = event.rng_namespace or "game"
        rng = streams.rng(namespace, event.rng_event or event.index)
        state = engine.apply_action(state, action, rng)
        after = stable_digest(canonical_true_state_key(state))
        if after != event.state_after:
            raise AssertionError(
                f"replay divergence after event {event.index}: {after} != {event.state_after}"
            )
    return state


_MISSING = object()


@dataclass
class MemoizationStats:
    v_hits: int = 0
    v_misses: int = 0
    q_hits: int = 0
    q_misses: int = 0


class MemoizationStore(Generic[TValue]):
    """In-memory hooks for ``V(state)`` and ``Q(state, action)``.

    Objective, horizon, policy and information state are part of the cache key so
    values from incompatible experiments cannot be mixed accidentally.
    """

    def __init__(self) -> None:
        self._v: MutableMapping[Tuple[Any, ...], TValue] = {}
        self._q: MutableMapping[Tuple[Any, ...], TValue] = {}
        self.stats = MemoizationStats()

    @staticmethod
    def value_key(
        state_key: Tuple[Any, ...],
        *,
        horizon: int,
        objective: str,
        policy_id: str,
        information_key: Optional[Tuple[Any, ...]] = None,
    ) -> Tuple[Any, ...]:
        return (
            "V",
            horizon,
            objective,
            policy_id,
            information_key,
            state_key,
        )

    @staticmethod
    def q_key(
        state_key: Tuple[Any, ...],
        action_key: Tuple[Any, ...],
        *,
        horizon: int,
        objective: str,
        policy_id: str,
        information_key: Optional[Tuple[Any, ...]] = None,
    ) -> Tuple[Any, ...]:
        return (
            "Q",
            horizon,
            objective,
            policy_id,
            information_key,
            state_key,
            action_key,
        )

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

    def clear(self) -> None:
        self._v.clear()
        self._q.clear()
        self.stats = MemoizationStats()


@dataclass(frozen=True)
class EpisodeOutcome:
    """Terminal record that preserves *when* a win happened."""

    won: bool
    win_turn: Optional[int]
    terminal_turn: int
    horizon: int
    win_family: str = ""
    terminal_reason: str = "horizon"

    def __post_init__(self) -> None:
        if self.won and self.win_turn is None:
            raise ValueError("won outcome requires win_turn")
        if not self.won and self.win_turn is not None:
            raise ValueError("non-win outcome cannot have win_turn")
        if self.win_turn is not None and self.win_turn > self.horizon:
            raise ValueError("win_turn cannot exceed experimental horizon")
        if self.terminal_turn > self.horizon:
            raise ValueError("terminal_turn cannot exceed experimental horizon")

    def win_by(self, turn: int) -> bool:
        return self.won and self.win_turn is not None and self.win_turn <= turn


def terminal_outcome_from_state(state: Any, *, horizon: int) -> EpisodeOutcome:
    """Create a complete terminal record from a legacy/new solver state."""

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


def cumulative_win_curve(
    outcomes: Iterable[EpisodeOutcome], horizon: int
) -> Tuple[Tuple[int, float], ...]:
    rows = tuple(outcomes)
    n = len(rows)
    if n == 0:
        return tuple((turn, 0.0) for turn in range(1, horizon + 1))
    return tuple(
        (
            turn,
            sum(1 for outcome in rows if outcome.win_by(turn)) / n,
        )
        for turn in range(1, horizon + 1)
    )
