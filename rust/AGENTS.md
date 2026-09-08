# Rust rebuild instructions

These instructions apply to rust/ and override Python/Oracle-era repository guidance where it conflicts.

## Authority

1. Current Comprehensive Rules + current Oracle text + explicit audited model decisions.
2. The audited v2 Rust rebuild specification and deterministic fixtures.
3. Accepted non-oracle Python behavior only as a parity witness/fixture generator.
4. Historical Oracle code, comments, rejected branches, and performance experiments as evidence only.

Every material behavior should be classified as RULE, MODEL, POLICY, PARITY, or EXPERIMENT.

## Formal milestone naming

Read `rust/AUDITED_MILESTONE_MAP.md` before starting or naming a milestone.

The formal audited roadmap is R0 bootstrap, R1 normalized state/RNG/information, R2 core sequencing, R3 staged search/tutors, R4 engine cards/win catalog, R5 deterministic rollout, R6 hidden worlds/Monte Carlo Q, R7 London mulligan DP, R8 native performance hardening, and R9 final analysis.

Historical implementation identifiers are not retroactively renamed. In particular:

- historical Rust `r6_*` mulligan identifiers map to formal audited R7;
- historical `r7_teacher_*`, `r7_signal_boundary_*`, and `rust-r7-*` diagnostics are post-R7 validation rather than formal R7;
- new work must use the formal milestone name in documentation even when it consumes a historical-version API.

## Non-negotiable architecture

- Policy code never reads unknown TrueState library order.
- Rules execution, observations, and policy choices are separate boundaries.
- ReplayKey/exact sampled-world identity is distinct from strategic ValueKey.
- RNG is explicit, versioned, domain-separated, occurrence-aware, and independent of thread scheduling.
- Common-random-number coordinates are shared only for the same logical stochastic event.
- Per-object state and typed delayed events are authoritative; traces are reporting only.
- Performance work must prefer representation, memoization, factoring, exact bounds, adaptive sampling, and parallelism before policy restrictions.
- No active card may silently lack a coverage status.
- Catalog presence, runtime support, and historical coverage labels are not proof of gameplay completeness. The post-R7 modeling completeness gate in `POST_R7_MODELING_COMPLETENESS_GATE.md` must be GREEN before new strategic-policy or terminal-sequencing results are accepted.

## Post-R7 modeling completeness discipline

Every active deck identity must have an explicit entry in `data/goldfish_model_gate.v1.tsv`. The unit of completeness is the relevant Oracle clause, not the card name or historical milestone label.

A card may clear the modeling gate only as `COMPLETE`, `GOLDFISH_IRRELEVANT`, or `ENVIRONMENT_DEFERRED`, with an explicit rationale and the executable evidence required by `POST_R7_MODELING_COMPLETENESS_GATE.md`. `AUDIT_REQUIRED`, `IMPLEMENTATION_REQUIRED`, and `ENVIRONMENT_SPLIT_REQUIRED` are blocking states.

Do not classify a card as goldfish-irrelevant merely because it is normally used as interaction. Own-spell/self-target lines, cast triggers, graveyard movement, resource conversion, alternate costs, and other interactions with modeled engine cards must be considered first.

## Post-R7 teacher/diagnostic discipline

Teacher search is a read-only oracle/sidecar over states produced by the accepted engine. It may annotate or diagnose; it must not silently rerank London bottoms, replace production keep/mull decisions, alter R5/R6/formal-R7 policy identity, feed interpretation labels into gameplay, or mutate rules because it finds a stronger line.

For backward signal-boundary work, prefer replayable actual sampled opening/game states over synthetic abundant-resource states. Report complete wins, complete zeros, incomplete results, and timeouts separately. Never convert `StepLimit`, `NoCandidate`, all-candidates-incomplete, or wall-clock timeout into a loss.

Production repair requires a reproducible correctness defect: missing/illegal supported action, wrong transition/cost/target/resolution/timing, observation-boundary violation, RNG/replay/CRN violation, terminal-witness defect, or invalid state/cache equivalence. A teacher-only improvement or greater-depth win is POLICY/search evidence, not by itself permission to change production behavior.

## Milestone hygiene

R0 is foundation-only. Do not claim card rules are implemented until focused rules fixtures exist.

Before declaring a formal milestone closed, record the audited deliverables, the exact acceptance evidence, the accepted head SHA, and the CI run. Do not substitute a later diagnostic workflow for the milestone's audited gate.
