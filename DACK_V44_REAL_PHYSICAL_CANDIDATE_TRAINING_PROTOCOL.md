# DACK v44 — candidate-level real physical value model (frozen protocol)

**Research only; no model approved.** Isolated branch `dack-v44-physical-candidate-values-20261101`. The original v5, v27, v43 and all existing results are unchanged.

## Background anchored in real observed outcomes

On 128 matched previously-inspected 151k games, original v5 reached T2 in 73, v43 candidate MAX-Q2 in 65, and original frozen v27 in 57. The v43 experiment on an independent new N256 151k cohort showed 122/256 byT2 versus 111/256 for original v27 (paired +4.297pp; CI +1.172 to +7.813). The original v5 reference on the first 128 of that same cohort was executed *after* examining 151k: this is an archival retrospective comparison, not new prospective acceptance.

v43 fixed the **disconnected bottom selection from KEEP evaluation** by evaluating all 7–12 original legal bottom candidates with frozen v27 Q2, choosing the highest, and deciding KEEP with that same candidate. However, original v27 Q2 was trained mainly for its original v14 selected bottom (only four true futures per training state), so MAX over off-policy candidates risks estimation/selection bias. v44 attacks that precise limitation with real physical labels for every candidate, keeping v43's candidate-search structure.

## New physical candidate dataset — predeclared 154k

- Exactly `one_key_34` 99 physical slots, original saved seed_base/stride, same actual seat, strict terminal beam160, and original stable chance rules.
- TRAIN independently dealt IDs `154000..154191`: 192 distinct physical source deals. DEV independently dealt IDs `154192..154255`: 64 distinct physical source deals, never used to fit.
- One London stage per source deal, cycled evenly through stages 2 (6-card kept), 3 (5-card kept), 4 (4-card kept), 5 (3-card kept). Stage0/1 has no bottom choice; stages6/7 will use unchanged v43 Q2-max to avoid untrained extrapolation.
- Evaluate EVERY original top12 structural finalist (7 at stage2 and up to 12 at other stages), not just old v14 choice. Exactly **8 physical hidden92+stable-chance futures per candidate**. Use the same blinded unknown92 shuffle and same chance seed for each candidate in a particular game/stage/future index, and append the exact legal London bottom after hidden92. No realized future draw order enters candidate features or model decisions.
- Store original selected hand, exact ordered bottom, original v27 predicted Q2 and seat-stage DP threshold, T1/T2/T3 physical outcomes per candidate, physical source game and stage.
- 192/64 source groups, NOT `N candidate rows × futures` independent original hands. Dev analyses bootstrap whole source deals and same paired candidate futures.

## Frozen model and estimated objective

- Model: 96-tree random-forest regressor, max_depth 8, min_leaf 12, max_features 0.65, seed 441920, with candidate rows weighted `1 / number_of_candidates_in_this_deal`.
- Target: **direct observed physical P(byT2 | exact candidate kept hand and bottom) minus frozen v27 estimated Q2**. This is a real-gameplay residual, *not v5 decision imitation*.
- Features: existing 167 capability/line features, omitting literal individual `seven:<card>` and `bottom:<card>` flags; includes stage, seat, key combinations, mana/tutor and structural candidate rank. A small 1–2 card deck change is plausible but has NOT been evaluated, and v27 underlying predictor is deck-specific.
- Frozen policy: `adjusted_Q2 = clip01(v27_Q2 + 0.50 × clip(forest_residual, -0.20, +0.20))`. Choose the original legal candidate with highest adjusted_Q2, tie-break by original structural finalist order; **decide KEEP using that exact chosen candidate's adjusted_Q2 and frozen v27 original seat-stage continuation**. No new DP fitting or acceptance threshold tuning. At stages 0,1,6,7 no correction (identical to v43).
- Export a pure Python forest; confirm numeric parity with sklearn float32 tree input. No original v5 lookahead at runtime. Both baseline v43 and v44 remain unapproved until physically tested.

## Development gate before consuming fresh 155k

The dev set is diagnostic **candidate-choice** physical outcome, not an end-to-end whole-game win rate. Compare picked candidate by the frozen v43 Q2-max to the v44-adjusted pick on exactly same dev seven/stage/future. Report empirical T2 and T3 changes across ALL 64 dev physical groups, changed-candidate subset, stages, and group + paired future two-source bootstrap 95% CIs.

Proceed to prospective full-game 155k **only if** the one fixed candidate-level v44 fit has:
1. all archive, source model and feature parity/nominal invariants passed;
2. strictly **positive** physical byT2 point-estimate across 64 independent dev source groups;
3. no more than 2.0 percentage-point physical byT3 decrease across all dev source groups.

A CI crossing zero in the small dev is not an automatic stop, because a *new* N256 whole-game test can assess uncertainty. A negative dev mean byT2, substantial T3 harm, or any source/schema/method failure means **do not launch the reserved prospective N256**. Do NOT tweak forest, shrinkage, threshold or split after seeing dev labels and then call 155k independent model acceptance.

## Prospective 155k full-game comparison, conditional on gate

- Reserve IDs `155000..155255` ONLY for one fixed v44 candidate, versus unchanged frozen v43 and frozen v27; isolated Python interpreter for each policy, same 99-card shuffled physical game, seat and London sevens, strict actual beam160 and stable dice.
- Real goldfish **byT1, byT2, byT3**, exact v5 utility `U_exact=PbyT2+.5P(exactT3)`, full sample counts and paired group bootstrap CI, stage/bottom differences and runtime.
- No v5 reference on 155k until a genuine reason to pay for it; v5's old 115k/151k performance cannot be compared by direct subtraction to 155k.
- A positive paired 95% CI lower bound for v44-v43 byT2 supports a real improvement on the benchmark; failing or crossing zero means uncertain/no promotion. Check T3 and T1 separately. Even success does NOT establish full original-v5 parity or multiplayer win rate.
- No repeated threshold tuning using 155k; after reading 155k it is permanently development/consumed.

## Caveats

The tiny per-candidate N8 physical Q2 target is noisy; max-over-candidates remains vulnerable to winner's curse, and v43's fast Q2 baseline is OOD for alternative bottoms. The fixed .50 residual shrinkage and ±.20 cap limit but do not eliminate that risk. Learned continuation threshold was trained for old policy and can be miscalibrated under v44; prospective whole-game gameplay is essential. Keep exact legal bottom order; do not collapse order-different hands if it changes observed library ordering.

**Status at protocol creation:** source-collector N4 smoke passed; full 192 train /64 dev collection running; model not yet fitted and prospective 155k never opened.
