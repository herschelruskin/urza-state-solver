# Rust rebuild instructions

These instructions apply to rust/ and override Python/Oracle-era repository guidance where it conflicts.

## Authority

1. Current Comprehensive Rules + current Oracle text + explicit audited model decisions.
2. The audited v2 Rust rebuild specification and deterministic fixtures.
3. Accepted non-oracle Python behavior only as a parity witness/fixture generator.
4. Historical Oracle code, comments, rejected branches, and performance experiments as evidence only.

Every material behavior should be classified as RULE, MODEL, POLICY, PARITY, or EXPERIMENT.

## Non-negotiable architecture

- Policy code never reads unknown TrueState library order.
- Rules execution, observations, and policy choices are separate boundaries.
- ReplayKey/exact sampled-world identity is distinct from strategic ValueKey.
- RNG is explicit, versioned, domain-separated, occurrence-aware, and independent of thread scheduling.
- Common-random-number coordinates are shared only for the same logical stochastic event.
- Per-object state and typed delayed events are authoritative; traces are reporting only.
- Performance work must prefer representation, memoization, factoring, exact bounds, adaptive sampling, and parallelism before policy restrictions.
- No active card may silently lack a coverage status.

R0 is foundation-only. Do not claim card rules are implemented until focused rules fixtures exist.
