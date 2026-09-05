# R5 parallel root/world evaluation checkpoint

## Scope

This checkpoint adds deterministic parallel execution to the accepted R5 fixed-budget and adaptive root-action evaluators. It does not broaden R4 rules/card coverage, alter policy ranking, change hidden-world sampling, introduce a new value objective, or weaken the serial fixed-budget evaluator as the correctness oracle.

## Namespace

- parallel evaluator: `r5_parallel_root_world_v1`;
- rules: `r4_acceptance_v6`;
- model: `urza_model_r4c_2026_09_04`;
- information: `information_state_v7_r4`;
- ValueKey: `value_key_v7_r4`;
- policy: `r5_candidate_contract_v2`;
- candidate bridge: `r5_public_candidate_bridge_v2`;
- rollout: `r5_deterministic_rollout_v2`;
- Monte Carlo: `r5_hidden_world_mc_v1`;
- root action/value: `r5_root_action_value_v1`;
- adaptive evaluator: `r5_exact_adaptive_root_eval_v1`;
- root/world cache: `r5_root_world_outcome_cache_v1`.

Parallel scheduling is deliberately **not** part of root/world cache identity. A serial and a parallel evaluation of the same `(ValueKey, EvaluationNamespace, RootSeed, RootActionKey, WorldId)` must produce the same cached outcome, so both schedulers share cache entries.

## Architecture

`urza-mc` exposes `ParallelRootConfig { workers }` plus parallel fixed-budget and adaptive entry points. The implementation uses Rust scoped standard-library threads; no dependency or lockfile change is required.

Each call first performs the same public setup as the serial reference path:

1. canonicalize the requested `WorldId` set;
2. build the public template `CandidateBridge`;
3. reject already-terminal/no-candidate roots;
4. enumerate the canonical public `RootActionKey` set;
5. sample exact hidden worlds from the accepted public-belief sampler;
6. rebuild and validate the identical public root-candidate set in every sampled world.

Only after those boundaries are satisfied is work split into independent `(sampled world, public root action)` jobs. Every worker resolves that public root action against its own sampled exact world and delegates execution to the accepted root-action/rollout helper. Worker identity never enters RNG coordinates or semantic keys.

Completed worker outcomes are sorted back into canonical `(world index, root index)` order before any `MonteCarloResult`, score, or selection is aggregated. Thread completion order is therefore observationally irrelevant.

## Adaptive/cache boundary

The adaptive parallel path keeps all cache interaction on the calling thread:

- cache lookups occur in canonical world/root order;
- only cache misses become worker jobs;
- workers never read or mutate the cache;
- completed misses are sorted canonically before cache insertion and aggregation;
- deterministic adaptive counters have the same values as the serial path for the same cache state;
- exact finite-budget ranking certification still runs only after a complete configured batch has been aggregated.

This preserves the accepted cache namespace and adaptive stopping semantics while parallelizing only the expensive root/world rollouts.

## Determinism requirements

Acceptance requires:

- one-worker parallel evaluation is exactly equal to serial evaluation;
- 2-worker, 4-worker, and oversubscribed worker counts are exactly equal to serial evaluation;
- caller `WorldId` enumeration order remains non-semantic;
- hidden exact library order remains non-semantic;
- fixed-budget serial and parallel `RootActionComparison` values are exactly equal;
- full-budget adaptive serial and parallel results, rankings, and deterministic counters are exactly equal;
- cache entries created by the serial scheduler are reusable by the parallel scheduler without recomputation;
- zero workers are rejected before execution;
- worker scheduling cannot alter RNG coordinates, cache identity, or public result ordering.

## Performance probe

`urza-mc/examples/r5_perf_probe.rs` compares serial vs parallel fixed-budget and adaptive cold-cache execution on the same three representative seven-card states used by the cycle-repair profiling pass. It also rechecks warm-cache behavior and normal adaptive execution. The probe reports the runner's `available_parallelism`, serial/parallel wall clock, speedup, and the existing deterministic rollout/cache counters.

The accepted GitHub runner exposed four workers. Across three release runs with eight common sampled worlds, fixed-budget medians were:

- opening combo, 3 roots / 24 root-world jobs: `24.418 ms` serial -> `11.973 ms` parallel, about `2.04x`;
- tutor-heavy, 14 roots / 112 root-world jobs: `218.728 ms` serial -> `89.183 ms` parallel, about `2.45x`;
- artifact-heavy, 19 roots / 152 root-world jobs: `495.559 ms` serial -> `220.194 ms` parallel, about `2.25x`.

Adaptive cold-cache scaling was comparable (about `2.02x`, `2.46x`, and `2.24x` respectively). Warm-cache evaluation remained sub-millisecond and executed zero root-world rollouts, confirming that parallelism targets the expensive execution work rather than cache/aggregation overhead. The eight-world normal adaptive probes all reached `MaxSamples`; no statistical or heuristic stopping behavior was added in this checkpoint.

The performance numbers are evidence for scheduling decisions only. Wall-clock timing does not participate in engine semantics, value ranking, cache identity, or acceptance parity.

## Validation

Validated implementation closure: `ffe20db970ab3a31423e2eded837b0be3f33a9ec` (`Close R5 parallel root-world checkpoint`). Dedicated acceptance run: GitHub Actions `33949117962`, job `101260435609`, result PASS. The gate passed formatting, locked dependency metadata, strict all-target/all-feature Clippy, six dedicated serial/parallel parity regressions, full workspace tests, benchmark compilation, three release performance probes, and cumulative R0-R5 audits.

The closure removed the temporary parallel workflow and patch helper. Its commit contains only the intended R5 source/documentation changes plus those two temporary-file deletions; generated `rust/target` artifacts were not staged. A normal user-authored documentation follow-up triggers the permanent Rust foundation gate on the finalized tree.

Python gameplay/policy logic remains out of scope.
