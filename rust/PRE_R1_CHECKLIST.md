# Pre-R1 readiness checkpoint

This checkpoint hardens the validated R0 foundation without beginning R1 card metadata or Magic rules.

## Authority

The audited v2 Rust rebuild specification remains normative. Python is only a fixture/parity witness. No R1 implementation may import Python state layout, hidden-order policy access, state-hash-only RNG semantics, trace-backed gameplay state, Oracle search shortcuts, or experimental policy pruning.

## Completed before R1

- Cargo dependency resolution is committed as `rust/Cargo.lock`, and CI uses `--locked` for dependency graph/build/test commands.
- `urza-policy` has no direct dependency on `urza-core`; policy must enter through `urza-info`.
- R0 active-card identity catalog has an explicit pinned BLAKE3 digest.
- `ValueKey` canonicalization merges equivalent library-count representations.
- Permission sequence/slot IDs are treated as provenance and canonicalized out of strategic equality while delayed expiry relationships are preserved.
- Ordered known-top information and ordered stack objects remain strategically distinct.
- RNG tests cover domain, root-seed, logical-event, and occurrence separation plus same-logical-event CRN sharing.
- Mystic Remora age is represented by per-object age counters rather than a singleton information-state field.
- Saga-III/remora singleton pending flags were removed from `InformationState`; R1 must represent these through per-object state, stack, pending decisions, and windows.
- Hand 25 remains a fixture only; no rule or policy is specialized to it.

## R1 implementation status

R1 proper has now implemented:

1. DONE — pinned/versioned active-card Oracle metadata: stable Oracle identity, representative printing identity, mana cost/value, type line, Oracle-text SHA-256 and snapshot timestamp, MDFC faces, and derived syntactic indexes.
2. DONE — normalized unordered card/battlefield storage and ordered `TrueLibrary` with explicit knowledge bounds.
3. DONE — structural canonical object projection including attachment and external-role relationships.
4. DONE — typed pending-decision payloads sufficient for future legality decisions.
5. DONE — production coordinate-stream bounded RNG and Fisher–Yates permutation.
6. DONE — exact validated `TrueState -> InformationState` observation/projection.
7. DONE — exact ReplayKey and InformationState JSON round-trip fixtures.
8. DONE — hidden-order leakage fixtures and raw ObjectId renaming fixtures.
9. DONE — structural state invariants for library knowledge, object uniqueness, attachments, sources, delayed references, and permissions.
10. DONE — pinned R1 catalog digest `4b39c7db7bfd2c6f68d7a49efa515cdffb2c6a9716022bc0b21eeec56754a983`.

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


## Validated checkpoint

- implementation commit: `7f95a6142cef25493f7a2e9725e3b42e65c6a9f2`;
- validation run: GitHub Actions `33273083782`;
- result: PASS;
- focused/workspace tests: 22 passed, 0 failed;
- R1 may now begin from this locked foundation.
