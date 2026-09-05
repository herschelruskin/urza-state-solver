# R5 candidate bridge checkpoint

## Scope

This checkpoint completes the public execution-to-policy candidate bridge over the frozen accepted R4 action surface. It does not broaden R4 rules or card coverage, and it does not begin multi-step rollout or Monte Carlo evaluation.

## Architecture boundary

`urza-policy` remains isolated from `urza-core` and `urza-rules`. The separate `urza-policy-bridge` crate owns execution-side enumeration and exact `Action` round-tripping.

Policy receives only `InformationState` plus `PolicyCandidate` records. Unknown library order, physical `ObjectId` numbering, and execution RNG provenance are not policy inputs.

## Exhaustive accepted action mapping

The bridge maps the complete frozen R4 `Action` enum: 26 ordinary action families and 8 contingent action families. Every variant has a distinct public action-kind code.

Public candidate identity preserves all strategically distinct public parameters, including six-component mana payments, canonical sources/targets/sacrifices, X values, Whir improvise multisets with multiplicity, permission slots/faces, Top reorder sequences, Scry top/bottom sequences, and optional/may choices.

Equivalent physical actions collapse only when they have the same public canonical semantics. The selected opaque `ActionToken` maps back to one exact legal execution `Action` representative.

## Legality ownership

The bridge does not duplicate the Rust rules engine. It generates choices from public visible state, then delegates final legality to the authoritative accepted R4 transition API on a cloned state. This dry-run RNG context is execution-only and never enters policy identity.

During `Transmute Artifact` difference payment, mana abilities that are legal while the pending cost is unresolved remain in the candidate set and are classified as contingent choices, so the policy cannot accidentally filter them out.

## Canonical multiplicity

`urza-info` now exposes an execution-side `resolve_canonical_objects` helper so a canonical equivalence class can map to all corresponding physical objects. This is necessary for costs such as Whir improvise that may consume multiple publicly equivalent permanents. `InformationState` itself is unchanged, so the frozen R4 information schema remains `information_state_v7_r4`.

## Namespaces

- rules: `r4_acceptance_v6`;
- model: `urza_model_r4c_2026_09_04`;
- information: `information_state_v7_r4`;
- ValueKey: `value_key_v7_r4`;
- policy: `r5_candidate_contract_v2`;
- candidate bridge: `r5_public_candidate_bridge_v1`.

## Acceptance

Acceptance requires raw-ObjectId renaming invariance, hidden-library permutation invariance, exact payment/X/improvise preservation, canonical deduplication of equivalent source objects, pending Transmute mana continuation, full token round-trip, strict Clippy, workspace tests, benchmark compilation, and cumulative R0-R5 audits.

## Next R5 block

Build deterministic multi-step rollout sequencing using `CandidateBridge` at every public decision point. Only after rollout determinism and replayability are accepted should `urza-mc` begin sampled-world evaluation.

Python gameplay/policy logic remains out of scope.
