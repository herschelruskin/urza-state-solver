# Markov / Monte-Carlo Foundation

This branch is based on the finalized Oracle rules/search audit at commit `0d724b8e`.
It adds architecture contracts without changing Oracle rules execution.

## Guarantees added

1. Strict separation between full simulator state and policy observation.
2. Deterministic canonical true-state keys with no Python `hash()` dependence.
3. Policy and rules-engine interfaces are separate.
4. Independent RNG namespaces derived from one root seed.
5. Replayable trajectories with state fingerprints and RNG coordinates.
6. Explicit action-equivalence collapsing.
7. V(state) and Q(state, action) memoization hooks.
8. Exact win-turn / terminal-horizon output and cumulative win curves.

## Final-Oracle compatibility

The architecture layer explicitly preserves the finalized future-legality fields:

- `State.remora_age`
- `State.remora_upkeep_pending`
- `State.saga3_pending`
- `Perm.knack_granted`
- `Perm.producer_urza_ready`
- attachment/tap/sickness/counter/mode fields

It deliberately excludes ephemeral/provenance-only permanent fields such as
`instance_tag` and `knack_source` from strategic permanent identity.

The policy view does not expose exact unknown library order.

## Important remaining migration before using narrow DP state merging

The existing Oracle shuffle helper still derives deterministic shuffle behavior
from legacy history (`len(trace)`). Therefore the conservative exact true-state
key includes trace history. Do not yet build a narrower Markov value cache that
drops history until all game randomness has been migrated to `RandomStreams`.

The next implementation step should be explicit RNG migration with pinned-seed
regression testing. Only after the old Oracle outputs are reproduced should a
history-free strategic DP key become authoritative.

## Local validation

First run the architecture compatibility smoke:

```powershell
py -3 architecture_smoke.py
```

Expected terminal marker:

```text
ARCHITECTURE SMOKE: ALL PASS
```

Then run the full finalized Oracle regression suite from `TEST_PLAN.md`.
