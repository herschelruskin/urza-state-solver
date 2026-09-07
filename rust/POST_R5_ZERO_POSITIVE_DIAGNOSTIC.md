# Post-R5 zero-positive diagnostic ladder

## Status

This checkpoint records the response to the frozen R5 natural-terminal search producing no positive trajectory. It is diagnostic work only: no R4 rules/card semantics, terminal definitions, R5 deterministic policy identity, rollout-v3 semantics, RNG contract, or `max_steps = 4096` setting may change unless a reproducible correctness defect is isolated.

Fresh negative evidence before this ladder:

- hidden worlds `228928..245311`, 16 accepted pilot openings: 262,144 rollouts;
- hidden worlds `245312..261695`, 16 accepted pilot openings: 262,144 rollouts;
- combined: **524,288 fresh rollouts**;
- result: every rollout stopped at `Horizon`; zero natural terminals, zero `StepLimit`, zero `NoCandidate`.

This is sufficient to stop blind hidden-world widening and diagnose reachability/policy separation instead.

## Five-step ladder

1. **Freeze the negative checkpoint.** Preserve the 524,288-rollout result and frozen semantics above. **DONE.**
2. **Revalidate terminal reachability.** Re-run the accepted R4 terminal-family gate: all 13 registered families must retain a real-catalog positive witness and an executable final-step transition through the public Rust rules API. Any failure is a concrete rules/terminal defect and stops policy broadening. **DONE.**
3. **One-deviation natural-state search.** On real frozen-policy Horizon worlds, enumerate legal public candidates through `CandidateBridge`, force exactly one alternate semantic action inside the same rollout execution, and continue with the accepted deterministic policy while preserving root/world/logical RNG coordinates and execution-local liveness history. **DONE: bounded exact pass clean/negative.**
4. **Two/three-deviation search with state deduplication.** Only if step 3 is clean and negative. This remains diagnostic POLICY/search work, not production-policy replacement. **PENDING.**
5. **Policy-independent legal trajectory search.** Only if bounded deviations remain negative. Use a diagnostic best-first/beam search over the accepted Rust candidate bridge and rules engine to answer whether a legal positive path exists; never port Python gameplay logic or silently install the diagnostic search as production policy. **PENDING.**

## Terminal reachability revalidation

Current-head diagnostic CI revalidated the accepted R4 terminal boundary without changing rules or terminal definitions:

- `cargo test --locked -p urza-rules --lib`: **41/41 tests passed**;
- `cargo run --locked -p urza-cli -- r4-audit`: `rules_version = r4_acceptance_v6`;
- **13/13 registered terminal families** remain represented by the accepted real-catalog/final-step gate;
- terminal detection remains on public `InformationState`, with accepted stack/pending/Cage and invariance guards.

Conclusion: there is no evidence that terminal recognition or the accepted executable final-step boundary is dead. A zero-positive natural rollout population must be diagnosed farther upstream in reachability/search/policy unless a new concrete rules defect is isolated.

## One-deviation diagnostic

Diagnostic implementation: `rust/crates/urza-mulligan/src/bin/post-r5-one-deviation-search.rs` plus the diagnostic-only forced-semantic hook in `urza-rollout`.

The exact runner recreates accepted pilot openings, samples real hidden worlds, runs the frozen deterministic baseline, enumerates legal public candidates at each baseline decision, then reruns from the original sampled state and forces exactly one alternate semantic action at that executed trace index inside the same rollout loop. The production path still supplies no forced action. `ROLLOUT_VERSION` remains `r5_deterministic_rollout_v3`.

The forced run therefore reconstructs and preserves the same execution-local deterministic-attempt, monotone-attempt, and mana-recurrence history before the intervention, uses the same root/world/logical RNG coordinates, and continues through the same R5 rollout machinery afterward. A regression test also forces the baseline semantic action through a liveness-sensitive Basalt Monolith / Forensic Gadgeteer path and requires exact equality with the ordinary baseline result.

### Initial breadth check

On hidden world `245312` for each of all 16 accepted pilot openings:

- baseline worlds: **16**;
- baseline decisions: **686**;
- legal alternate actions tested: **427**;
- Horizon continuations: **427**;
- natural/one-deviation terminals: **0**;
- `StepLimit`: **0**;
- `NoCandidate`: **0**;
- widest decision: **21 legal candidates**.

### Exact 64-world-per-opening pass

On the already-known clean Horizon block `245312..245375`, for all 16 accepted pilot openings, with the exact in-rollout forced-decision implementation:

- baseline worlds: **1,024**;
- baseline decisions: **42,554**;
- legal alternate actions tested: **27,217**;
- Horizon continuations: **27,217**;
- natural/one-deviation terminals: **0**;
- `StepLimit`: **0**;
- `NoCandidate`: **0**;
- maximum baseline trace length observed: **131**;
- widest decision observed: **25 legal candidates**;
- execution-local liveness history: **preserved**.

This closes the bounded one-deviation step as a clean finite negative. It does not prove that no one-deviation positive exists anywhere, but within this deliberately broad natural-state sample there is no evidence that one legal action correction followed by the frozen R5 policy is sufficient to reach a registered terminal. The earlier fresh-continuation caveat is removed for this pass.

## Decision boundary

- R4 final acceptance states that all 13 audited terminal families have a real-catalog positive witness and an executable final-step witness through the public rules transition API; current-head revalidation passed.
- If future terminal revalidation fails, isolate and repair only the reproducible correctness defect before continuing.
- If a future one-deviation execution produces a natural terminal, record the opening world, hidden world, decision index, baseline semantic action, forced semantic action, terminal family/turn, and complete semantic trace. That identifies a concrete deterministic-policy miss.
- If any bounded-deviation continuation produces `StepLimit` or `NoCandidate`, stop expansion and isolate that exact opening/hidden world/deviation.
- Step 4 may now be attempted if explicitly desired, but it must remain a diagnostic two/three-deviation search with state deduplication; the one-deviation result is not permission to alter rules or production policy.
- If bounded deviations are negative but policy-independent search wins, classify the gap as POLICY/search evidence rather than permission to mutate rules.
- An all-Horizon teacher is not adequate evidence for R7 mulligan-value separation; positive reachability/density must be established before relying on that signal for learning.
