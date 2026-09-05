# R5 adaptive evaluation, cache, and instrumentation checkpoint

## Scope

This checkpoint optimizes the accepted fixed-budget common-world root-action evaluator without changing R4 rules/card coverage, policy semantics, hidden-world sampling, terminal semantics, or the fixed-budget value objective. The fixed evaluator remains the correctness oracle.

## Exact adaptive stopping

R5 adaptive evaluation consumes a canonical common `WorldId` sequence in batches. Every consumed world is paired across every public root action exactly as in the fixed evaluator.

V1 deliberately does **not** use an approximate statistical confidence interval. Instead it uses an exact finite-budget ranking certificate. After the configured minimum sample count, each current trailing root is given the strongest possible remaining completion for the `WinByHorizon` objective: every unconsumed world becomes a T1 win. Each root currently ahead of it is given the weakest possible completion: no additional wins. Early stopping is allowed only when every adjacent pair in the current deterministic ranking remains ordered even under those bounds, including the public root-key tie-break.

Therefore an early stop has zero false-positive ranking risk relative to the configured fixed sample budget: the complete final root ranking, not merely the current leader, is unable to change under any remaining outcomes. If that cannot be certified, evaluation consumes the full budget.

## Root-world cache

`InMemoryRootOutcomeCache` stores completed per-root/per-world outcomes. Cache identity includes:

- canonical public `ValueKey`;
- validated `EvaluationNamespace`;
- `RootSeed`;
- public `RootActionKey` (`PolicyActionClass + PolicyPublicKey`);
- `WorldId`;
- root-world cache schema version.

`current_r5_evaluation_namespace` fills the linked rules, model, policy, ValueKey, RNG, information/sampling, candidate-bridge, rollout, and root-action evaluator namespaces. The caller must supply the catalog digest and environment identity because the generic `CardDatabase` trait intentionally does not expose those identities. Namespace mismatches or empty caller identities are rejected before cache access. The rollout budget is part of the namespace.

Raw `ObjectId`, decision-local `ActionToken`, and preexisting hidden library order are not cache identity. Hidden-order-equivalent exact templates therefore reuse public strategic outcomes, while a root-seed, environment/catalog namespace, rollout budget, or linked semantic-version change cannot alias an old entry.

## Performance instrumentation

Adaptive results include deterministic counters for candidate roots, worlds consumed, actual hidden worlds sampled, batches, root-world requests, cache hits/misses, executed root-world rollouts, rollout steps executed, and rollout steps avoided by cache hits. These counters are observational only: no timing measurement or instrumentation field participates in policy choice, value ordering, early-stop certification, or cache identity.

## Shared execution path

Fixed and adaptive root evaluators share one root-world execution helper. It remaps the public semantic root through the sampled world's `CandidateBridge`, forces that exact action at Game logical event 0, then continues through `urza-rollout` from logical event 1. Cached values are reconstructed into the same `MonteCarloResult` aggregation path used by fresh evaluations.

`StepLimit`, `NoCandidate`, candidate-set drift, root remapping failures, and rule/rollout errors remain incomplete typed failures rather than losses or cacheable values.

## Acceptance

Acceptance requires:

- full-budget adaptive output exactly equals the fixed-budget reference evaluator;
- exact early ranking certification matches the complete configured-budget ranking;
- repeated identical evaluation is served entirely by cache with identical semantic output;
- hidden-order-equivalent templates can reuse the cache;
- namespace and root-seed changes cannot alias entries;
- invalid namespace metadata is rejected before cache access;
- strict Clippy, full workspace tests, benchmark compilation, and cumulative R0-R5 audits remain green.

## Namespaces

- rules: `r4_acceptance_v6`;
- model: `urza_model_r4c_2026_09_04`;
- information: `information_state_v7_r4`;
- ValueKey: `value_key_v7_r4`;
- policy: `r5_candidate_contract_v2`;
- candidate bridge: `r5_public_candidate_bridge_v1`;
- rollout: `r5_deterministic_rollout_v1`;
- Monte Carlo: `r5_hidden_world_mc_v1`;
- root-action value: `r5_root_action_value_v1`;
- adaptive root evaluation: `r5_exact_adaptive_root_eval_v1`;
- root-world cache: `r5_root_world_outcome_cache_v1`.

No frozen R4 namespace changes are made.

## Next work

Benchmark representative full-hand states using deterministic counters and wall-clock harnesses outside semantic results. Parallel world/root execution or an optional statistical confidence mode may be considered only after demonstrating parity with this exact adaptive/fixed reference and preserving common-world pairing and cache namespace safety.

Python gameplay/policy logic remains out of scope.

## Validation

Validated by the dedicated R5 adaptive/cache acceptance workflow. The exact run and closure commit are recorded by the follow-up branch commit after this gate is green.
