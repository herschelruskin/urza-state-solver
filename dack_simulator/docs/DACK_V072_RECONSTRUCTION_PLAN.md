# DACK v0.72 reconstruction plan

Status: **documentation only**. No engine code change is authorized by this document.

## 1. Reproducible base

v0.72 must branch from the exact persisted v0.68 solver:
`src/dack_t3_solver_v0_68_color_canonicalization.py`

Known v0.68 behavior:
- flexible white-capable lands canonicalize their colored mode to W when no current card can distinguish another color;
- when Pentad Prism is in hand, those sources retain unrestricted colored mana so Sunburst remains distinguishable;
- exhaustive payment branching remains present;
- existing T2/T3 frontier regressions remain mandatory.

## 2. What is recoverable about transient v0.69/v0.70

Recovered project notes describe v0.70 as a **search-stability/performance checkpoint**:
- payment-dominance reduction;
- search-state/frontier dominance reduction;
- no new game actions or card-rule changes;
- Pentad Prism color-sensitive payment branches were explicitly preserved.

Recovered validation history:
- full solver self-test passed;
- a 100-context beam-400 dominance audit (50 City of Brass, 50 Mana Confluence) produced zero impossible target-worse-than-Plains outcomes;
- a later fresh beam-240 audit of City of Brass, Mana Confluence, and Tarnished Citadel (10 contexts each) also produced zero impossible losses.

The exact v0.69/v0.70 source was not persisted. Therefore the following are **not recoverable with confidence**:
- exact separation of v0.69 versus v0.70;
- precise dominance comparator;
- exact function placement;
- branch-order/tie-breaking details;
- exact number of branches removed;
- whether frontier dominance was applied before or after scoring/diversity selection.

Transient v0.70 data are diagnostic only and must not be pooled with reproducible v0.68/v0.72 results.

## 3. Current v0.68 constraints that v0.72 must preserve

### Payment branching
A generic cost paid from W+C must preserve both legal residual states. Do not collapse them blindly.

### Payment-history-sensitive rules
The following require preserving semantically distinct payment paths:
- Pentad Prism Sunburst / distinct-color abstraction;
- Void Mirror colored-vs-colorless payment;
- Vexing Bauble zero-vs-nonzero total payment;
- exact WW+generic Dack payment;
- restricted legend/artifact/Dack-white pools;
- variable payments such as Everflowing Chalice and Kozilek's Command.

### Search survival
Known Vault/Tutor and Saga/Opal T3 continuations must survive the bounded search at their existing regression settings.

## 4. Proposed v0.72 implementation sequence

### Patch A — semantic payment signature
Before pruning anything, define an explicit payment semantic signature containing at least:
- residual W, C, unrestricted colored, restricted legend, restricted artifact, restricted Dack-white;
- total mana spent;
- colored mana spent;
- a Prism-sensitive spent-color class sufficient to reproduce current Sunburst behavior.

No pruning in Patch A.

### Patch B — exact semantic deduplication
Deduplicate only payment outcomes whose:
- post-payment non-resource state is identical;
- residual resource capability is identical;
- payment semantic signature is identical.

This is deliberately weaker than general dominance and should be behavior-preserving by construction.

### Patch C — conservative payment dominance
Only after Patch B passes all regressions, allow one payment result to dominate another when every modeled future spending capability of the dominated state is a subset of the retained state **and** all payment-history-sensitive tags are equal.

Never use raw total mana alone.
Never merge restricted and unrestricted pools.
Never merge W/C/unrestricted-colored states when the current or pending action can distinguish them.
Pentad Prism casts may bypass dominance entirely in the first v0.72 implementation.

### Patch D — frontier/state dominance
Apply dominance only among states with identical non-resource strategic identity:
- same turn, hand, library information, battlefield identities/tap/counters, grave/exile, land-play status, spell counters, treasures/spawn, and other rule-relevant fields.

Resource dominance may prune a state only when the retained state has a provable superset of future legal mana capability. If that proof is not simple, keep both states.

Do not replace the existing exact `key()` deduplication with a lossy canonical key.

## 5. Required validation before production

1. Existing v0.68 full self-test passes unchanged.
2. W+C generic-1 regression retains both residual states.
3. Pentad Prism retains both one-counter and two-counter cases where currently legal.
4. Void Mirror and Vexing Bauble payment regressions pass.
5. Exact Dack WW/restricted-white regressions pass.
6. Known Vault/Tutor and Saga/Opal T3 regressions pass.
7. Compare v0.68 vs v0.72 exhaustively on a small deterministic state fixture set; win/no-win and earliest win turn must match.
8. Strict Plains-dominance audit:
   - City of Brass >= Plains;
   - Mana Confluence >= Plains;
   - Tarnished Citadel >= Plains.
9. Benchmark branch/state counts and wall time separately from correctness.
10. Only after all above pass may v0.72 become a new reproducible production engine.

## 6. Versioning rule

Do **not** call the rebuilt engine v0.70. The original transient v0.70 source cannot be reproduced exactly.

The rebuilt engine should be named something like:
`dack_t3_solver_v0_72_payment_dominance_rebuild.py`

Its Git commit SHA and solver SHA-256 must be recorded before generating production data.
