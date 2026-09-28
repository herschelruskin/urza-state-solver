# DACK simulator checkpoint — v0.65 instrumentation on v0.64 engine

Canonical engine in this package: `src/dack_t3_solver_v0_64_repaired.py`.
The engine itself is unchanged from the validated v0.64 repair checkpoint; **v0.65 refers only to the new sharded mana-screen instrumentation**.

## Current deck mana-base count
- 99 cards total.
- 28 literal land cards.
- 25 unique literal land names because `Plains` appears four times.
- 2 land-capable MDFCs: `Emeria's Call` and `Razorgrass Ambush`.
- Therefore **30 land-access cards** in the current 99.
- The matched land screen has **26 non-Plains targets**: 24 unique non-Plains literal lands + 2 MDFCs. `Plains` is the control, so it is not itself a target.

## Expanded mana/infrastructure screen
The new runner tests 60 matched targets against an extra Plains:
- 26 land-access alternatives.
- 34 nonland cards currently in the solver's `RAMP_PROTECTED` set.

The 34 infrastructure cards are tagged by role (`fast_mana`, `mana_rock`, `cost_reducer`, `mana_untap`, `conditional_mana`, `mana_tutor`, `repair_selection`) so analyses can distinguish literal mana acceleration from tutors/repair cards.

### Matching
For each target/context:
1. Target is forced into a creature-free opening seven with six sampled common cards.
2. Control replaces that target slot with `Plains`.
3. The six other cards are identical.
4. The remaining unknown library is exactly identical.
5. Future library orders are exactly identical.
6. Starting/nonstarting seat weighting is retained (Gemstone Caverns receives explicit 1:3 weighting).
7. Utility is `P(<=T2) + 0.5 * P(exact T3)`.

This gives paired target-vs-Plains deltas rather than observational correlations.

## Sharding
`dack_v065_sharded_mana_screen.py` writes:
- `shard_XXXX_trials.csv`: future/seat-class outcomes.
- `shard_XXXX_contexts.csv`: per-context distributions and paired deltas.
- `shard_XXXX_manifest.json`: seed, beam, samples, solver hash, target list.

`pool_dack_mana_shards.py` concatenates raw rows, removes duplicate keys, and computes the card-level paired summary and SE/95% CI from **pooled context rows**, not from averages of shard percentages.

## Included result
`results/mana_screen_N2/` is an **instrumentation validation only**: 2 independent contexts per each of 60 targets, beam 40, four future samples/context. It is deliberately too small for card rankings. Keep the raw rows; append independent shards for production inference.

## Suggested production progression
Run equal-N shards first, then allocate additional contexts to cards whose paired confidence intervals remain decision-relevant. Never overwrite an existing shard; use a new shard ID/seed range and repool.
