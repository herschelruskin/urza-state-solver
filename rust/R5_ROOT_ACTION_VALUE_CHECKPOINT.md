# R5 root-action / value integration checkpoint

## Scope

This checkpoint adds fixed-budget root-action comparison and deterministic value selection on top of the accepted hidden-world Monte Carlo and deterministic rollout layers. It does not broaden R4 rules/card coverage, add adaptive stopping, or add a second gameplay/policy implementation.

## Common-world root branching

The evaluator builds the legal root `CandidateBridge` once from the current public decision point and records only each candidate's public `PolicyActionClass + PolicyPublicKey`. For every requested `WorldId`, it samples one exact hidden world, verifies that the sampled world's public root candidate set is identical, and then clones that same sampled exact world once per root candidate.

Each public root key is remapped through the sampled world's bridge to one exact execution `Action`. Decision-local tokens and raw `ObjectId`s are never root-action identity. Candidate-set drift, missing/ambiguous semantic roots, and unresolved execution actions are typed errors.

## RNG sequencing

A forced root action is executed with the existing `Game` RNG domain at logical event 0. Its deterministic continuation runs through `urza-rollout` beginning at logical event 1. The rollout crate now exposes an offset continuation entry point while retaining the original zero-offset API unchanged. This makes forced-root evaluation coordinate-equivalent to choosing that root action normally at rollout step zero and prevents logical-event reuse.

## Value contract

Each root candidate receives a complete `MonteCarloResult` over the same canonical `WorldId` set. Only true terminal wins and T6 horizon losses are values; `StepLimit` and `NoCandidate` remain incomplete errors.

`WinByHorizonScore` is exact integer value metadata derived from `WinDistribution`. It first maximizes total wins by the horizon. When total wins tie, it maximizes exact-turn wins lexicographically from T1 through T6. No floating-point estimate enters deterministic root identity or tie-breaking. If scores are exactly equal, the smallest public `RootActionKey` wins the tie.

## Acceptance

Acceptance covers the fixed-budget value ordering, identical common worlds for every root, canonical world-order independence, hidden-template-order invariance, public candidate-set equality across sampled worlds, semantic root remapping, already-terminal rejection, positive root+continuation step budgeting, strict Clippy, full workspace tests, benchmark compilation, and cumulative R0-R5 audits.

## Namespaces

- rules: `r4_acceptance_v6`;
- model: `urza_model_r4c_2026_09_04`;
- information: `information_state_v7_r4`;
- ValueKey: `value_key_v7_r4`;
- policy: `r5_candidate_contract_v2`;
- candidate bridge: `r5_public_candidate_bridge_v1`;
- rollout: `r5_deterministic_rollout_v1`;
- Monte Carlo: `r5_hidden_world_mc_v1`;
- root-action value evaluation: `r5_root_action_value_v1`.

No frozen R4 namespace changes are made in this block.

## Next R5 block

Adaptive-confidence stopping, result/value caching, and performance instrumentation may now be built around this fixed-budget reference contract. Those optimizations must preserve common `WorldId` pairing, public semantic root identity, completion/error semantics, and fixed-budget parity fixtures.

Python gameplay/policy logic remains out of scope.
