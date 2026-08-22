# Markov / Monte-Carlo Foundation

This branch is based on the finalized Oracle rules/search audit and the merged
Markov/Monte-Carlo architecture foundation. It prepares the validated rules engine
for history-independent stochastic transitions without changing Magic legality.

## Guarantees added

1. Strict separation between full simulator state and policy observation.
2. Deterministic canonical state keys with no Python `hash()` dependence.
3. Policy and rules-engine interfaces are separate.
4. Independent RNG namespaces derived from one root seed.
5. Replayable trajectories with state fingerprints and RNG coordinates.
6. Explicit action-equivalence collapsing.
7. V(state) and Q(state, action) memoization hooks.
8. Exact win-turn / terminal-horizon output and cumulative win curves.

## Final-Oracle compatibility

The architecture layer explicitly preserves finalized future-legality fields,
including:

- `State.remora_age`
- `State.remora_upkeep_pending`
- `State.saga3_pending`
- `Perm.knack_granted`
- `Perm.producer_urza_ready`
- attachment/tap/sickness/counter/mode fields

It deliberately excludes ephemeral/provenance-only permanent fields such as
`instance_tag` and `knack_source` from strategic permanent identity.

The policy view does not expose exact unknown library order.

## In-game RNG migration

The legacy Oracle shuffle helper previously derived shuffle outcomes from
`len(trace)`. That made future randomness depend on the path used to reach an
otherwise identical game state.

In-game shuffles now use the versioned `RandomStreams` infrastructure. A shuffle
is keyed by:

- the root game seed;
- the game RNG namespace;
- an action/search salt; and
- a canonical concrete-state fingerprint that excludes trace/reporting history.

Consequences:

- changing trace text cannot change a shuffle;
- identical concrete seeded state + action reproduces the same result;
- different root seeds select different deterministic game worlds;
- policy/Monte-Carlo RNG use cannot perturb the actual game stream.

`canonical_true_state_key()` remains the conservative replay/debug identity and
therefore retains provenance. `canonical_markov_state_key()` is the concrete
seeded transition identity and drops `trace`, `interaction_seen`, and
`urza_cast_turn` because those do not affect rules transitions.

## Next state-key step

Do **not** automatically use the seeded transition key as the final `V(s)` cache
identity across Monte-Carlo rollouts. The root RNG seed identifies a sampled
world, not strategic game position. The next DP patch should define a separate
seed-independent strategic/value-state projection, with objective-specific
history added only when required (for example an interaction-seen objective).

This separation lets replay remain exact while allowing the future value cache to
merge equivalent strategic states across rollout seeds.

## Local validation

The RNG migration was validated locally with:

```powershell
py -3 architecture_smoke.py
py -3 urza_solver.py --metadata-smoke
py -3 urza_solver.py --tutor-smoke
py -3 urza_solver.py --cam-smoke
py -3 urza_solver.py --commander-smoke
py -3 urza_solver.py --combo-smoke
py -3 urza_solver.py --remora-smoke
py -3 urza_solver.py --bounce-smoke --action-cap 60 --bottom-cap 4
py -3 urza_solver.py --bay-smoke --action-cap 60 --bottom-cap 4
py -3 urza_solver.py --draw-trace-smoke
py -3 urza_solver.py --mulligan-smoke
py -3 urza_solver.py --worker-config-smoke
```

All suites reported `ALL PASS` after the migration.
