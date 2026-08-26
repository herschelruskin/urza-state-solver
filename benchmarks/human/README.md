# Human Benchmarks

This directory contains human-play calibration fixtures for the Urza solver.
They are **benchmarks/calibration data**, not Magic rules and not hardcoded policy weights.

## 1. Annotated mulligan / bottoming hands

Files:

- `human_mulligan_exact_hands.json` — compact machine-readable exact visible-state fixture.
- `human_mulligan_benchmark_summary.json` — benchmark semantics, QC, and aggregate annotations.

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
- Counterfactual `keep this same seven as a six?` annotations are exploratory. `Uncertain` must remain uncertainty rather than being coerced into a binary label.
- Free-text justifications are qualitative policy evidence, not permission to hardcode the prose as rules.

QC and recovered source information:

- 36 annotated rows total.
- 35 exact visible states are usable and runnable against the normalized current benchmark deck snapshot.
- Hand 10 is unrecoverable and remains excluded from exact-state regression.
- Hand 30's missing seventh card was recovered as `Swan Song`.
- Hand 36's missing seventh card was recovered as `Uthros Research Craft`.
- Hands 24 and 34 were recorded during a tentative late `Fugitive Droid` trial replacing `Codex Shredder`. For common-snapshot evaluation they are normalized back to `Codex Shredder`, while the recorded Fugitive Droid seven remains stored as provenance.

Counterfactual keep-at-six notes:

- Hand 22: keep as six, bottom `Vexing Bauble`.
- Hand 23: uncertain, leaning mulligan; if kept as six, provisional bottom `Saprazzan Skerry`.
- Hand 32: uncertain, leaning mulligan; if kept as six, provisional bottom `Mana Drain`.
- Hand 35: still mulligan as six.

Recommended evaluation:

- keep/mull agreement by mulligan stage / keep size;
- bottom-choice agreement or value regret on reconstructable keeps;
- disagreement reports with estimated `V(keep)` vs `V(mull)`;
- explicit reporting of borderline / low-value-gap hands;
- explanation diagnostics against the human justifications.

Do not require exact human agreement as a rules-engine regression gate. A Monte Carlo policy may legitimately outperform or disagree with a human label.

## 2. Historical 250-run human goldfish baseline

Files:

- `human_goldfish_baseline.json` — aggregate calibration targets.
- the cleaned row-level CSV remains an analysis artifact and need not be loaded by production code.

Deck snapshot:

- The 250 historical goldfishes are treated as the same `Codex Shredder` deck snapshot used for benchmark normalization. The only known deck deviation in the annotated-hand material is the tentative Fugitive Droid trial in hands 24 and 34.

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
