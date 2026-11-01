# DACK v33b — Search-free bottom screening protocol (2026-11-01)

Research branch: `dack-v33b-capability-regret-20261101`, branched from completed
`dack-v33-attribution-first-20261101`. Preserve the physical engine,
v5, v14, v27, v32 and original v33 diagnostics; no policy is promoted.

## Why this experiment, before another trained model

The completed v33 fresh-future same-stage counterfactual established
+7.19pp T2 for actual v5 versus v14 bottoms conditional on 53
policy-discordant hands (CI +2.00 to +13.56pp). This is not a
full-deck gain. The observed different-London-stage T3 gap warrants
a separate future keep-policy study. We first need to determine whether
a **cheap existing candidate value model**, with no new fitted parameters,
contains practical bottom-selection signal.

Crucially, v27 Q(KEEP) was trained on v14-selected bottoms: using
it to rank off-policy alternatives is extrapolation, NOT an already
calibrated or safe optimal-choice procedure.

## Frozen design and assumptions

- One physical London game per independent physical group ID.
  Use the *frozen* v27 all-stage zero-beam keep/mull policy and frozen
  v14 bottom only to identify the final London stage, visible seven,
  seat, and 92-card remaining multiset.
- For each final kept hand with a legal nonempty bottom, enumerate
  the existing structural top-12 candidates *without altering the
  candidate generator*, then score with four **frozen** rules:
  1. v14 choice forest (baseline).
  2. v27 T2 Qkeep forest, argmax of all structural finalists
     (**predeclared primary test**).
  3. Existing v18 real-outcome utility forest: top three only,
     respecting its documented training support (exploratory).
  4. v6 analytical T2 mana/white proxy across finalists (exploratory).
- The selectors cannot access draw-order information or sampled game
  outcomes. Frozen original v27 keep decision is retained by
  construction for all four options, avoiding Qkeep/continuation
  policy mixing *within* the conditional comparison.
- Sample 128 fresh independent physical game groups (112000..112127)
  as training/design band and another 64 fresh groups
  (113000..113063) as untouched validation. Neither group range
  reuses old 110k, 103k, 99k, etc.
- For EACH distinct selected bottom in a group, run exactly 8 fresh
  independently hashed 92-card shuffles, with the same blind dice
  seeds and unseen-card permutation across alternatives, plus the
  already legal selected bottoms in the correct library positions.
  Strict stable dice and beam160 gameplay, to T3. Distinct identical
  alternatives are evaluated only once. No bottom => no extra beam.
- Report paired physical-group T1/T2/T3 gain/loss/ties,
  approximate bootstrap uncertainty, changed-bottom frequency,
  and actual simulation count. Split train and validation; do not
  mix them to tune or fit any model.
- T2 is primary, T1/T3 safeguards. Neither raw Qkeep score nor v18
  predicted probability is treated as calibrated counterfactual value.
- The same seed across actions cannot guarantee exact event-level
  coupling when different action paths consume random effects.
  No engine or game-state fingerprint collapse allowed.

## Go/no-go before building any new bottom policy

If v27 candidate-value selection has clearly positive T2 conditional
value on untouched 113k validation and does not meaningfully damage
T1/T3, prototype it as a *bottom-only override after frozen v27 KEEP*,
then test fresh prospective full games under identical physical starts.
If not, **do not** deploy it; create an outcome-regret-trained
small structured pairwise ranker only after demonstrating useful
candidate coverage and label signal on independent training groups.
The v18 and analytical alternatives are exploratory; choosing a
winner from them would require a NEW validation cohort.

Do NOT interpret the best observed candidate on eight sampled futures
as an attainable oracle, promote on validation Brier alone,
or call conditional results a global deployment win rate.

Run:
`python -u dack_simulator/validation/v33b_screen_existing_rankers.py --split train --start 112000 --out shards/one.json.gz`
and pool all 48 four-game shards through
`dack_simulator/validation/v33b_pool_ranker_screen.py`.
Output:
`benchmark_results/v33b_existing_bottom_ranker_screen.json`.

This is an explicitly bounded experiment, not an invitation to
automatically iterate through forests or thresholds after seeing test
outcomes.
