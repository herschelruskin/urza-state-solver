# Pre-R1 readiness checkpoint

This checkpoint hardens the validated R0 foundation without beginning R1 card metadata or Magic rules.

## Authority

The audited v2 Rust rebuild specification remains normative. Python is only a fixture/parity witness. No R1 implementation may import Python state layout, hidden-order policy access, state-hash-only RNG semantics, trace-backed gameplay state, Oracle search shortcuts, or experimental policy pruning.

## Completed before R1

- Cargo dependency resolution is to be committed as `rust/Cargo.lock` and CI switched to `--locked`.
- `urza-policy` has no direct dependency on `urza-core`; policy must enter through `urza-info`.
- R0 active-card identity catalog has an explicit pinned BLAKE3 digest.
- `ValueKey` canonicalization merges equivalent library-count representations.
- Permission sequence/slot IDs are treated as provenance and canonicalized out of strategic equality while delayed expiry relationships are preserved.
- Ordered known-top information and ordered stack objects remain strategically distinct.
- RNG tests cover domain, root-seed, logical-event, and occurrence separation plus same-logical-event CRN sharing.
- Mystic Remora age is represented by per-object age counters rather than a singleton information-state field.
- Saga-III/remora singleton pending flags were removed from `InformationState`; R1 must represent these through per-object state, stack, pending decisions, and windows.
- Hand 25 remains a fixture only; no rule or policy is specialized to it.

## R1 work intentionally not started here

R1 still owns:

1. pinned/versioned current Oracle metadata for every active card:
   - stable external identity;
   - mana cost and mana value;
   - type line;
   - Oracle text digest/version date;
   - MDFC faces;
   - generated feature flags/indexes;
2. compact fixed/normalized zone and true-library representations;
3. complete canonical object projection from execution `ObjectId` to strategic `CanonicalObjectId`, including attachments/relationships;
4. typed pending-decision payloads sufficient for future legality, not only decision-kind skeletons;
5. production random permutation/generator implementation built on the R0 coordinate PRF;
6. exact TrueState -> InformationState observation/projection logic;
7. replay/information round-trip fixtures;
8. information-leakage tests demonstrating that two worlds differing only in unknown order present equal policy observations;
9. structural state invariants and validation for object uniqueness/attachments;
10. an R1 catalog/version digest replacing the identity-only R0 catalog where appropriate.

## R1 acceptance gate

R1 is not complete merely because the new types compile. Before R2 sequencing begins:

- round-trip fixtures must pass;
- hidden-order leakage tests must pass;
- replay identity must distinguish exact hidden order and RNG occurrence;
- strategic identity must exclude unknown order, RNG provenance, trace/profiling data, and execution-only permission IDs;
- policy must remain unable to import `TrueState`;
- known top/bottom fidelity, stack order, pending/window state, counters, attachments, life, mana, permissions, and delayed obligations must remain represented where future-relevant;
- CI must be green with locked dependencies.

Do not port card rules during this gate.
