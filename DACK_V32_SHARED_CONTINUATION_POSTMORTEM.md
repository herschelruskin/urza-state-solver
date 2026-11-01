# DACK v32 postmortem — shared London continuation calibration

**Frozen experiment completed; do not promote.** Branch:
`dack-v32-shared-continuation-calibration-20261031`.

## What worked

Rejecting a London hand restores all 99 physical slots, so under a fixed
future policy Q(MULL) really is a shared quantity C(seat,stage). The 28
cells were sampled independently and archived; current card identities
do not enter C. The earlier v31 sampled Q(MULL) six times **for every
hand**. Future learner training should use a shared continuation
estimate to eliminate that avoidable variance and redundant game search.

- 4 seats x 7 nonterminal stages.
- 96 measured v27-downstream beam160 futures per cell = **2688**.
- 32 separate validation futures per cell = **896**.
- Fixed predeclared shrinkage `0.75 empirical + 0.25 v27 old DP prior`.
- Frozen v27 keep model trained on 93k all-eight-stage physical outcomes,
  frozen v14 bottom selection, strict physical 99 and actual beam160.
- Validation Brier old v27 C = 0.12500863, empirical-only C = 0.12444584,
  predeclared v32 C = 0.12437705. **Small, uncertain calibration gain.**

## Prospective N256, entirely new 110k physical IDs

| Policy | T1 exact | T2 cumulative | T3 cumulative | mean keep size |
|---|---:|---:|---:|---:|
| Full v5 reference | 19/256 | 131/256 (51.17%) | 212/256 (82.81%) | 5.1445 |
| Frozen v27 | 18/256 | 124/256 (48.44%) | 198/256 (77.34%) | 5.3672 |
| v32 shared C | 18/256 | 121/256 (47.27%) | 196/256 (76.56%) | 5.4609 |

The actual v32–v27 Turn 2 difference was **−1.171875 percentage points**,
paired wins 2, losses 5, paired bootstrap 95% CI
[−3.125, +0.78125] percentage points. No improvement demonstrated.

Against v5, Turn 2 v32 was −3.90625 points (13 paired gains, 23 losses;
CI [−8.59375, +0.78125]), while Turn 3 lagged 6.25 points
(CI [−11.328125, −1.171875]). Full v5 summed game execution
time 5633.35s versus 87.50s for v32 on N256, **64.38x** gameplay-speed
difference (this excludes model training and continuation sampling).

v32 and v27 returned *exactly the same final kept hand* in 230/256
physical games. Remaining 26 had different final keep depths. In
23 of those 26 v32 kept **more cards** than v27, in three fewer.
Of the changed games, two gained Turn 2 deployment and five lost it.
Most changed hands did not alter early deployment at all.

## Reassessment: what is and is not a pitfall

- **Mathematical continuation sharing is sound.** Reusing a single
  calibrated Q(MULL) for a fixed seat, stage and downstream policy
  is a structural reduction of estimator noise, not an apparent winrate
  improvement by itself.
- **Better continuation Brier does not guarantee policy improvement.**
  The 896 validation outcomes are insufficient to detect tiny gains in
  such low-probability cells, and the sampled Q(MULL) values still have
  nonzero standard error (96 future draws per cell).
- **The first-step target is not a self-consistent policy DP.** v32
  thresholds were sampled under *future v27 continuation*, while the
  deployed policy makes v32 decisions at later stages. A fixed-point
  recalculation might matter but would risk further overfitting without
  stronger keep-hand values and enough new evaluation.
- **Q(KEEP) model and bottom selection now dominate uncertainty.**
  The unmodified v27 model was trained on 256 physical groups with 4
  futures per stage state; outcomes are sparse for high-dimensional
  features and near the early keep/mull decision boundary.
  There is no evidence that refitting another small residual forest
  would fix this.
- **Observed data do not support promoting v32.** Original frozen v5
  remains best for deployment in this 110k sample, although it is
  much slower.

## Next proposed experiment, not yet run

Preserve the shared continuation estimator as reusable research
infrastructure. **Do not spend the next budget merely increasing the
per-seat C samples or fitting another correction forest.** Instead
obtain denser genuine beam160 Q(KEEP) labels on *independent* physical
hands, especially early-stage near-boundary hands; use multiple
independent future shuffles, explicit uncertainty intervals and
outcome-regret rather than exact bottom-card labels. Train on all
London stages, apply uncertainty-gated changes, and evaluate on truly
new paired full games. Where candidate bottoms preserve the same
deployment resources, treat observed near-equivalence as a tie
subject to Chrome Mox imprint and Mox Opal metalcraft exceptions.

Research-only; no production policy changed. Full source results:
`benchmark_results/v32_shared_continuation_108k_diagnostic.json`,
`benchmark_results/v32_prospective_110k_N256.json`.
