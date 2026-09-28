# DACK data lake — v0.71 instrumentation

This checkpoint is a **data/instrumentation layer**, not a new game-rules engine. The reproducible engine is the exact persisted `v0.68` source in `src/`.

## Why microtasks
Long monolithic runs were repeatedly interrupted by execution-window/process timeouts. The new atomic unit is one target card × one independent opening-hand context. Each task writes its own context CSV, trial CSV, runner manifest, and `task_manifest.json`. A killed process can lose only the currently running context; completed tasks are never restarted.

## Current experiment
`mana_vs_plains_v068_b240_s1`

- 60 targets: 26 land-access cards + 34 ramp/infrastructure cards.
- control: Plains.
- beam: 240.
- one future order per independent context.
- seat weighting retained (Gemstone Caverns: starting 1/4, nonstarting 3/4).
- utility: `P(<=T2) + 0.5 * P(exact T3)`.
- initial milestone: N=25 independent contexts per target, then adaptive extension for ambiguous/decision-relevant cards.

This is a **conditional forced-opening-slot screen**, not a full-deck card-swap win-rate estimate.

## Data products
Every task includes exact solver SHA, runner SHA, deck SHA, target/control, replicate, seed namespace, beam, sample count, runtime, and status.

`pool_dack_v071.py` creates:
- `contexts.csv`: independent context-level paired observations (primary inferential unit)
- `trials.csv`: future/seat-class detail
- `summary_by_card.csv`: paired means, SE, approximate 95% CI
- `dack_data_lake.sqlite`: queryable mirror for later mining
- `pool_manifest.json`: compatibility fingerprint and row counts

## Future experiments
The same top-level data lake will hold separate experiment IDs for:
- full-deck card-for-card swaps
- land-count sweeps
- tutor-policy changes
- new printed cards
- mulligan-policy experiments

Different experiment types/config fingerprints are **never pooled as if they estimate the same quantity**.

## v0.70 transient archive
A partial v0.70 dataset survived, but its exact source code was never persisted. Those files are archived under `archive/v070_transient/` and must not be mixed into the reproducible v0.68 pool.