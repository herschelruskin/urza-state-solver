# Human Benchmarks

This directory contains human-play calibration fixtures for the Urza solver.
They are **benchmarks/calibration data**, not Magic rules and not hardcoded policy weights.

## 1. Annotated mulligan / bottoming hands

Files:

- `human_mulligan_benchmark.json` — canonical machine-readable fixture.
- `human_mulligan_hands_clean.csv` — flat inspection/analysis form when needed outside CI.

Semantics:

- `mulligan_count=0`: initial seven.
- `mulligan_count=1`: free multiplayer second seven.
- `mulligan_count=2`: fresh seven, keep 6 / bottom 1.
- `mulligan_count=3`: keep 5 / bottom 2.
- `mulligan_count=4`: keep 4 / bottom 3.
- `mulligan_count=5`: keep 3 / bottom 4.
- `Decision` is the primary human label.
- Recorded London bottoms are a secondary label when the row is reconstructable.
- Hand ratings are conditional on keep size. Do **not** compare a numeric rating across different keep sizes.
- `Would Keep at` / `Would Bottom` are exploratory only because completion/semantics were inconsistent.
- Free-text justifications are qualitative policy evidence, not permission to hardcode the prose as rules.

QC:

- 36 annotated rows total.
- 33 exact visible states are usable as human decision fixtures.
- Hands 10, 30, and 36 are excluded from exact-state regression until corrected.
- Hands 24 and 34 contain `Fugitive Droid`. They are valid historical annotations, but that card is absent from the current `decklist.txt`; runners should report/skip deck-snapshot drift instead of silently changing the fixture.

Recommended evaluation:

- keep/mull agreement by mulligan stage / keep size;
- bottom-choice agreement or value regret on reconstructable keeps;
- disagreement reports with estimated `V(keep)` vs `V(mull)`;
- explanation diagnostics against the human justifications.

Do not require exact human agreement as a rules-engine regression gate. A Monte Carlo policy may legitimately outperform or disagree with a human label.

## 2. Historical 250-run human goldfish baseline

Files:

- `human_goldfish_baseline.json` — aggregate calibration targets.
- the cleaned row-level CSV remains an analysis artifact and need not be loaded by production code.

Core endpoint semantics:

- blank historical `Winning Turn` means `>T7 / never`, not missing data;
- current solver comparison horizon is end of T6;
- therefore historical T7 wins and `>T7 / never` are losses at the T6 horizon;
- Mystic Remora / Rhystic Study goldfish modeling uses a standardized assumption of **2 additional cards per full turn cycle while active** because their true table output is opponent-dependent.

Observed historical calibration targets:

- win by T3: 31.6%;
- win by T4: 83.2%;
- win by T5: 94.0%;
- win by T6: 97.6%;
- loss at T6 horizon: 2.4%.

These are sanity/calibration targets, not exact pass/fail expectations. Report sampling uncertainty and distributional distance.

## Design principle

The intended comparison is:

`human annotated decisions` ↔ `knowledge-constrained policy` ↔ `Monte Carlo-improved policy` ↔ `Oracle ceiling`

while the 250-run baseline checks whether population-level simulated outcomes remain plausible.
