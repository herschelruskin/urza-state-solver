# R5 hidden-world Monte Carlo checkpoint

## Scope

This checkpoint adds fixed-budget hidden-world sampling and Monte Carlo root-state evaluation on top of the accepted deterministic rollout API. It does not broaden R4 rules/card coverage and does not add a second gameplay or policy implementation.

## Architecture boundary

`urza-mc` is an outer evaluator. It samples exact hidden library worlds, delegates every sampled world to `urza-rollout`, and aggregates completed outcomes. `urza-policy` remains public-state-only; `urza-policy-bridge` remains the sole action-enumeration/canonicalization boundary.

## Hidden-world sampling

The caller supplies a valid exact `TrueState` as execution scaffolding. Sampling observes that state, preserves known top and known bottom cards exactly, discards the preexisting order of the unknown middle, sorts the unknown middle into its public multiset, and shuffles that canonical multiset.

The sampling RNG coordinate uses domain `OuterHiddenWorld`, a dedicated R5 hidden-library event type, the explicit `WorldId`, occurrence zero, and a concrete fingerprint derived only from the public `LibraryBelief`. Therefore two exact templates with the same public information but different unknown library order produce the same sampled exact library for the same root/world coordinate.

Each sampled state is re-observed and must equal the template `InformationState`; any public drift is an error.

## Monte Carlo evaluation

`MonteCarloConfig` supplies `RootSeed`, the first `WorldId`, sample count, and deterministic rollout step bound. World IDs are semantic sample identities. The evaluator also accepts an explicit set of world IDs, rejects duplicates, canonicalizes execution order by numeric `WorldId`, and returns per-world outcomes in that same order.

Each exact sampled world is evaluated through `urza-rollout` using the same root and that sampled `WorldId`. Game randomness remains in the existing `Game` RNG domain while outer world sampling remains in `OuterHiddenWorld`.

Completed terminal samples are accumulated into `WinDistribution::t1_through_t6` and a stable 13-family win table. A true R4 T6 horizon is accumulated as a loss. `StepLimit` and `NoCandidate` are incomplete evaluations and fail the Monte Carlo call instead of silently becoming losses.

## Acceptance

Acceptance fixtures prove public-state preservation, exact known library edges, preexisting-hidden-order noninterference, `OuterHiddenWorld` domain separation, same-root/world repeatability, world-order independence, hidden-order-equivalent Monte Carlo invariance, exact turn/family aggregation, horizon-loss aggregation, incomplete-stop rejection, and duplicate-world rejection. The full Rust quality gate also requires strict Clippy, workspace tests, benchmark compilation, and cumulative R0-R5 audits.

Validated closure commit: `db64a98e085128d882833a8704664d9969c82f0c` (`Close R5 hidden-world Monte Carlo checkpoint`). Dedicated validation run: GitHub Actions `33943692139`, result PASS. Locked dependency metadata, formatting, strict all-target/all-feature Clippy, full workspace tests, benchmark compilation, and cumulative R0-R5 audits all passed. The temporary Monte Carlo workflows removed themselves in the validated closure commit.

## Namespaces

- rules: `r4_acceptance_v6`;
- model: `urza_model_r4c_2026_09_04`;
- information: `information_state_v7_r4`;
- ValueKey: `value_key_v7_r4`;
- policy: `r5_candidate_contract_v2`;
- candidate bridge: `r5_public_candidate_bridge_v1`;
- rollout: `r5_deterministic_rollout_v1`;
- Monte Carlo: `r5_hidden_world_mc_v1`.

No frozen R4 namespace changes are made in this block.

## Next R5 block

Build audited root-action comparison/value integration using common sampled `WorldId`s across candidate roots. Adaptive confidence, caching, and performance policy should come only after that comparison contract is deterministic and replayable.

Python gameplay/policy logic remains out of scope.
