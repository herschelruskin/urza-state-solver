# DACK v32 — Shared physical London continuation, independent evaluation

## Central simplification

After a London mulligan, all 99 physical cards are shuffled back.
Therefore, conditioning on seat and stage, the expected deployment
probability of rejecting a hand is independent of the exact card identities
we have just seen. A per-hand Q(MULL) estimate wastes simulation budget
and adds label noise. Under a *fixed downstream policy*, estimate
C(seat, stage) **once**, then compare the visible hand's estimated keep
value to the common threshold.

This is a *one-step policy improvement* under frozen downstream v27,
not a re-optimized fixed-point DP after changing the policy.

## Experimental controls

- Research branch: `dack-v32-shared-continuation-calibration-20261031`.
- v5, v14, v26, v27 and v31 remain untouched.
- 99 physical cards and strict stable dice + beam160 gameplay remain fixed.
- The hand Q(KEEP) model is unchanged from v27, fit from 93k 256-group
  all-eight-stage dataset (2048 stage states, 8192 beam160 future outcomes).
- Bottom selector remains frozen v14 128 on all eight London stages;
  neither bottom identity imitation nor sampled future outcomes enter
  the policy.
- Q(MULL) is measured by rejecting a hypothetical current hand entirely,
  shuffling all 99 cards afresh at each later London stage, following
  the frozen v27 policy (all eight-stage value model with old 92k DP),
  and evaluating the chosen resulting hand using beam160.
- Independent new trials: 28=(4 seats x 7 nonterminal stages) cells,
  96 calibration outcomes and 32 validation outcomes per cell.
  2,688 training and 896 separate validation real games.
- Precommitted fixed shrinkage to reduce cell noise:
  `C_v32 = 0.75 * observed_96 + 0.25 * v27_predicted_continuation`.
  Do NOT tune this weight using validation or prospective outcomes.
- Frozen model: `models/dack_v32_shared_Qmull_continuation_EXPERIMENTAL.json`.
- Calibration report:
  `benchmark_results/v32_shared_continuation_108k_diagnostic.json`.

## Calibration result

Across 896 independently held-out continuation outcomes pooled across
seat-by-stage cells, Brier old v27 = 0.12500863, raw sample C = 0.12444584,
v32 fixed-shrink C = 0.12437705. This is a small predictive improvement,
not evidence of better end-to-end Turn 2 deployment.

Each cell has only 96 independent calibration outcomes; threshold standard
errors remain nonzero. The model explicitly records the observed rates,
32 validation outcomes, prior rates, shrinkage and source hashes.

## Prospective test

Fresh physical game IDs `110000..110255`, N256 across 64 shards of 4.
Comparators: reference v5, frozen v27, and precommitted v32. Each game
has the identical first seven and seat across policies. Each policy gets
its own separate process to prevent module-global policy monkeypatches.

Primary endpoint is *cumulative deployment by Turn 2*. Report exact T1,
T2 and T3 numerators, paired wins/losses, game-level bootstrap CIs,
McNemar discordance and actual gameplay CPU. Unmodified opponent-free
goldfish scoring remains distinct from interactive cEDH win probability.

### Design caveats

1. Q(MULL) under v27 downstream is independent of the rejected seven, but
   Q(MULL) for a fully v32-controlled policy may differ. This is a
   one-step offline policy-improvement experiment.
2. Q(KEEP) is still a noisy and possibly biased 93k-fitted regression. A
   better C alone cannot repair systematic Q(KEEP) miscalibration.
3. Small Brier gains on 896 calibration-validation outcomes do not show
   significant improvement. The 110k cohort must not be used to fit the
   model or rewrite the v32 threshold.
4. Do not collapse actual beam gameplay states by heuristic functional
   bottom keys. Mox imprintability, metalcraft, land counts, combos,
   tutor abilities, and action-search order remain exact.

No model is approved or promoted from this branch without prospective evidence.
