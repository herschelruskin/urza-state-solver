# Solver Architecture Hardening

This patch prepares the validated Oracle engine for the later information-faithful Markov/DP/Monte-Carlo solver without changing Oracle search semantics.

## Contracts added

`solver_architecture.py` establishes eight boundaries that future solver code should use:

1. **True state vs observation** — `PolicyView` is derived from complete state plus `InformationState` and deliberately exposes no raw library order.
2. **Canonical/hashable state** — `canonical_true_state_key()` is deterministic across Python processes and does not use the process-randomized built-in `hash()`.
3. **Policy/rules separation** — `Policy` receives only `PolicyView`, opaque `PolicyAction` objects, and `PolicyContext`; `RulesEngine` owns state mutation.
4. **Explicit RNG streams** — `RandomStreams` derives independent `game`, `environment`, `policy`, and `tie` streams from a root seed plus explicit event coordinates.
5. **Replayable trajectories** — `Trajectory` stores stable action IDs, before/after state fingerprints, and RNG coordinates; `replay_trajectory()` verifies deterministic replay.
6. **Action-equivalence collapsing** — `collapse_action_equivalence()` only merges actions whose caller supplies the same future-relevant equivalence key. Distinct tutor targets are not merged implicitly.
7. **V/Q memoization hooks** — `MemoizationStore` keeps objective, horizon, policy ID, and optional information-state key in cache identities.
8. **Terminal horizon + win turn** — `EpisodeOutcome` records exact win turn, terminal turn, family, horizon, and reason; `cumulative_win_curve()` produces P(win by T1..Tn).

Run the focused smoke with:

```powershell
py -3 architecture_smoke.py
```

Expected marker:

```text
ARCHITECTURE SMOKE: ALL PASS
```

## Important legacy findings

These are deliberately **not** changed by this compatibility patch because Oracle behavior is a regression target.

### 1. Current `State.key()` is not an exact future-state identity

The legacy key sorts hand/battlefield and fingerprints library using `hash(self.library)`, but it omits multiple stored fields. That is acceptable only if every omitted field is proven irrelevant to future legality/value. It is not a safe basis for new DP caches without an audit.

New DP / transposition code should start from `canonical_true_state_key()` or an explicitly tested strategic projection rather than silently inheriting `State.key()`.

### 2. Current shuffle helper is history dependent

`shuffled_library()` derives its RNG seed from `salt`, turn, `len(trace)`, and the current library representation. Therefore two otherwise identical game states reached through different trace lengths can resolve a future shuffle differently.

That violates the Markov assumption required to merge those states solely by board/hand/library state. Before activating aggressive DP memoization, migrate shuffle/random events to `RandomStreams` and store/derive RNG coordinates explicitly.

### 3. `legal_actions()` currently returns successor states

The new architecture uses stable `PolicyAction` identities because policy choice, replay, Q-caching, and action-equivalence analysis all need an action object independent from mutation. The Oracle can remain successor-state based for now. The future policy branch should adapt each legal choice into `PolicyAction` and keep execution inside the rules layer.

## Migration order

1. Add the architecture contracts and focused smoke (this patch).
2. Route new non-Oracle code through `PolicyView`/`PolicyAction`; never pass raw state to a policy.
3. Replace legacy shuffle/random helpers with explicit `RandomStreams` coordinates while checking deterministic Oracle regression seeds.
4. Add a stable action adapter around current action generation.
5. Introduce a tested strategic state projection for `V(s)` only after confirming every omitted field cannot affect future legality, stochastic evolution, or the objective.
6. Turn on V/Q memoization and measure cache hit rate before considering a learned value approximator.

## Why no ANN yet

The architecture intentionally exposes a value-cache seam but no neural model. Exact DP/transposition caching plus Monte Carlo rollout policy improvement should be measured first. If `V(s)` evaluation later becomes the actual bottleneck, a learned approximation can be added behind the same value interface without redesigning the rules or policy boundaries.
