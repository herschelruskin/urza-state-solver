# DACK v0.72 Bite 8 — production promotion

Status: **PROMOTED TO PRODUCTION ENGINE**

## Frozen engine
- Branch: `dack-simulator-v0.72-production`
- Solver: `src/dack_t3_solver_v0_72_frontier_dominance.py`
- Solver SHA-256: `abba6f0baa7bedfb0b248bdd62501dae10157ba90bd5a3952fbeffbdcca48a7a`
- Production beam: **240**
- Horizon: T3
- Utility: `P(<=T2)+0.5*P(exact T3)`

Patch D retains Patch C's conservative payment dominance and adds conservative
frontier/state dominance without changing card rules, the exact state `key()`, or scoring.

## Promotion validation

Fresh Bite-8 sample:
- **90 completed Patch-C vs Patch-D matched contexts**
- **60/60 target cards covered**
- **0 target exact-outcome mismatches**
- **0 Plains-control exact-outcome mismatches**
- **0 target utility mismatches**
- **0 control utility mismatches**

Strict promotion audit:
- City of Brass: 10 designated fresh contexts
- Mana Confluence: 10 designated fresh contexts
- Tarnished Citadel: 10 designated fresh contexts
- designated strict Plains-dominance violations: **0 / 30**

The broad sweep also contained one independent context for each strict land, so across all
Bite-8 strict-land observations:
- strict contexts: **33**
- target-worse-than-Plains violations: **0 / 33**

Both Patch C and Patch D passed their complete inherited self-tests immediately before the
promotion sample.

## Runtime

Across the 90 completed promotion contexts:
- Patch C wall time: ~188.533 s
- Patch D wall time: ~188.824 s

Patch D is therefore promoted for **validated correctness and real frontier-state
reduction**, not because Bite 8 demonstrated a material wall-time speedup.

## Runtime pathology retained, not hidden

Four broad contexts initially exceeded the 18-second microtask cap:
- City of Traitors
- Great Hall of the Citadel
- Brainstone
- Manifold Key

City of Traitors, Great Hall, and Manifold Key completed on isolated rerun and matched
Patch C exactly.

The original Brainstone context (`namespace=720800, local=0`) remained pathological even
beyond 90 seconds. It is retained in the timeout provenance. A fresh independent Brainstone
context (`local=1`) completed and matched Patch C exactly, so Brainstone remains represented
in the 60-target promotion coverage without pretending the pathological context completed.

## Validation artifacts

Persistent raw snapshots:
- `/DACK simulator/validation/v072_bite8_results.csv`
- `/DACK simulator/validation/v072_bite8_timeouts.csv`

SHA-256:
- results: `88bd0cc9bc6ee1a12b3fdcc609dd46c837dd000daeb46d62c00c9d5bc91df5b7`
- timeout provenance: `8f265afb493f33be2d762e710996e58604f6324d9972e629c742c6ae25eb4c13`

Production lock:
- `config/v072_production_engine.json`

## Next step

Do **not** start the large statistical pool with the old v0.68 runner unchanged.
The next bite should update the atomic/microtask data-lake runner to import the frozen v0.72
solver, record the v0.72 solver/config hashes in every task manifest, and verify a tiny
end-to-end shard/pool/restart test. Only after that should the large pooled N expansion begin.
