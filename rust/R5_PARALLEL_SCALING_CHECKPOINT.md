# R5 parallel scaling and scheduler-granularity checkpoint

## Scope

This checkpoint is performance-only. It keeps the accepted R4 rules/card surface, R5 policy, hidden-world sampler, fixed/adaptive value semantics, RNG coordinates, strict incomplete-world handling, and root/world cache identity unchanged. The serial fixed-budget evaluator remains the correctness oracle.

## Namespace

- parallel evaluator: `r5_parallel_root_world_v2`;
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

The parallel namespace changes because the scheduler implementation contract changed. The root/world cache namespace does not: scheduling remains non-semantic, so serial, v1 parallel, and v2 parallel executions of the same public cache key intentionally share the same exact outcome identity.

## Measured problem

The accepted v1 scheduler assigned each worker one large contiguous slice of canonical `(world, root)` jobs. Larger-budget profiling on a 4-way GitHub-hosted runner showed nearly ideal two-worker scaling but a 4-worker plateau, consistent with unequal rollout costs leaving a tail worker active after other workers became idle.

The retained release probe `urza-mc/examples/r5_scaling_probe.rs` measures 32, 64, and 256 complete sampled worlds for three representative states with 3, 14, and 19 legal roots. It compares 1, 2, 4, and 8 requested workers and asserts exact equality with the serial oracle for every measurement.

A first naive contiguous-world probe found a typed `StepLimit` world at the accepted 4096-step budget. The benchmark was corrected rather than weakening semantics: it deterministically scans WorldIds and skips only `RootActionError::IncompleteWorld` while constructing the measurement set. This selection behavior is benchmark-only. Production evaluators still return incomplete worlds as errors and never count them as losses.

## v1 scaling baseline

Pre-tuning baseline run `33951225114` used `available_parallelism = 4`. Representative speedups versus serial were:

| Fixture | 32 worlds | 64 worlds | 256 worlds |
| --- | ---: | ---: | ---: |
| opening combo, 3 roots | 2.22x | 2.23x | 2.29x |
| tutor-heavy, 14 roots | 2.49x | 2.51x | 2.52x |
| artifact-heavy, 19 roots | 2.25x | 2.23x | 2.30x |

Two-worker runs were approximately 1.84x-1.99x. Requesting eight workers generally did not improve on four because the runner exposed four-way parallelism.

## v2 scheduler

`evaluate_jobs_parallel` now uses scoped standard-library threads plus an `AtomicUsize` claim counter. Each worker repeatedly claims the next canonical job index and evaluates exactly that already-prepared `(sampled world, public root action)` job. The atomic queue is execution scheduling only:

- worker identity is absent from RNG coordinates, semantic keys, cache keys, and public results;
- cache access remains on the calling thread in canonical order;
- roots/worlds are prepared and public-candidate validated before worker execution;
- workers never aggregate values;
- every attempted job keeps its canonical job index;
- after all workers join, attempts are sorted by job index;
- only then are `RootActionError`s propagated or successful outcomes aggregated.

Canonical post-join error interpretation is intentional: if more than one independent job fails, thread completion order cannot change which typed failure has precedence.

No Rayon or other scheduler dependency was added. `Ordering::Relaxed` is sufficient for the claim counter because it supplies unique indices only; it does not publish semantic state between workers.

## v2 scaling result

Dynamic-scheduler experiment run `33951419805` passed focused parity tests and strict `urza-mc` Clippy before measurement. On another 4-way hosted runner, representative speedups were:

| Fixture | 32 worlds | 64 worlds | 256 worlds |
| --- | ---: | ---: | ---: |
| opening combo, 3 roots | 2.53x | 2.60x | 2.39x |
| tutor-heavy, 14 roots | 2.78x | 2.78x | 2.80x |
| artifact-heavy, 19 roots | 2.55x | 2.56x | 2.56x |

Two-worker scaling remained approximately 1.94x-1.99x. Four-worker scaling improved consistently on the larger tutor/artifact workloads, while eight requested workers generally remained at the same plateau as four. One opening/256 measurement favored eight workers, treated as hosted-runner timing variance rather than a semantic or default-worker signal.

The default remains `available_parallelism()`; the tuning does not oversubscribe by default.

## Acceptance requirements

The production closure requires:

- Rust 1.89;
- formatting and locked dependency metadata;
- strict workspace all-target/all-feature Clippy;
- repeated parallel parity tests so varying claim schedules cannot change results;
- full workspace tests;
- benchmark compilation;
- release compilation and execution of the retained larger-budget scale probe;
- cumulative R0-R5 audits;
- no dependency/lockfile change attributable to this scheduler tuning;
- no Python gameplay/policy port.

Dedicated acceptance and permanent foundation run identifiers are recorded after validation.

Dedicated production acceptance run: GitHub Actions 33951783273, result PASS. The gate passed Rust 1.89 formatting, locked dependency metadata, strict workspace all-target/all-feature Clippy, four repeated parallel parity suites, full workspace tests, benchmark compilation, the release 32/64/256-world scaling matrix, and cumulative R0-R5 audits.


## Production scaling evidence

Dedicated production acceptance run `33951783273` executed the retained release probe on a runner reporting `available_parallelism = 4`. Every parallel measurement asserted exact equality with the corresponding serial `RootActionComparison` before timing was emitted.

Four-worker speedups were:

| Fixture | 32 worlds | 64 worlds | 256 worlds |
| --- | ---: | ---: | ---: |
| opening combo, 3 roots | 2.57x | 2.56x | 2.57x |
| tutor-heavy, 14 roots | 2.76x | 2.78x | 2.77x |
| artifact-heavy, 19 roots | 2.55x | 2.52x | 2.53x |

Two-worker speedups stayed between 1.96x and 2.00x. Requesting eight workers produced no material improvement over four on this four-way runner, supporting the existing `available_parallelism()` default rather than oversubscription.

The 256-world production timings were approximately 727 ms serial / 283 ms at four workers for the 3-root fixture, 5.64 s / 2.03 s for the 14-root fixture, and 12.07 s / 4.76 s for the 19-root fixture.

The opening fixture required skipping three typed incomplete worlds while constructing its benchmark-only 256-world set; tutor and artifact fixtures skipped none. This does not change production evaluation: `StepLimit` and `NoCandidate` remain typed incomplete errors, never losses.

Validated production closure commit: `ffcf8e0d98001bef7230d3c53cf038923b8609f8`. Formatting-only closure hygiene run `33952039708` produced `364f028ced5b829ccd4b9c72a635d6a693376ceb`; it confirmed rustfmt changed only the retained scaling probe and re-ran locked metadata, focused Clippy, and focused parallel tests successfully.
