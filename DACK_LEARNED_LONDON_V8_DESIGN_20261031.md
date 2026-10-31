# DACK learned London mulligan v8 — research and implementation protocol

Status: EXPERIMENTAL. The real-outcome dataset generator passed its first smoke test; the
full model train/calibrate/export/continuation/deployment pipeline passed only a
clearly marked SYNTHETIC-LABEL integration test. There is NO validated trained
real-outcome policy yet.

## Decision model

Predict exactly four mutually exclusive outcomes conditional on an observable
London hand, proposed bottom, seat, and known hidden-library card multiset:

- 0 = no deployment through turn 3
- 1 = commander deployed on turn 1
- 2 = deployed on turn 2
- 3 = deployed on turn 3

Use the model's normalized class probabilities to score each bottom option:
U = p(T1) + p(T2 exact) + 0.5*p(T3 exact).

A tiny probabilistic model replaces mulligan-only searches. It does NOT replace
the beam-160 actual deployment simulator and does not magically make the
four-player outcome or imperfect-information tutor policy realistic.

## Files

- dack_simulator/validation/generate_offline_london_labels_v8.py:
  samples complete shuffled hidden libraries independently, runs the strict
  beam-160 reference engine, and records categorical deployment-turn labels.
  Saved features never contain hidden future draw order. Each game ID groups
  all candidate bottoms and future rollouts.
- dack_mulligan_learned_features_v8_20261031.py:
  visible-hand feature extraction, native Python softmax, JSON model export
  validation. The deployed model requires neither sklearn nor a beam.
- dack_simulator/validation/train_offline_london_v8.py:
  multinomial logistic baseline, separate training and calibration data,
  four-class temperature scaling, report Brier/log-loss and export a small
  deterministic JSON model.
- dack_simulator/validation/derive_learned_london_dp_v8.py:
  compute per-deck, per-seat London continuation values from the trained
  model by Monte Carlo backward induction with ALL legal physical bottoms.
- dack_paired_counterfactual_v8_learned_london_20261031.py:
  opt-in learned-policy gameplay runner. Refuses to run without a model and
  all nine per-deck continuation tables. Hashes them in policy identity.
- tests: test_offline_learning_v8.py and test_learned_london_dp_v8.py
- workflows: dack_offline_learning_v8_smoke.yml and
  dack_learned_london_v8_integration.yml

## Independent split boundaries (outer physical game IDs)

- Training: 20000-29999
- Calibration: 30000-39999
- Held-out paired policy comparison: 40000-49999
- DP threshold sampling: 50000+ (no actual gameplay outcomes)

All labels from the same game ID, including distinct London bottom candidates
and different deck variants, must remain in the SAME split. Never split
individual rollout rows at random. This avoids highly correlated information
leakage.

## Backward induction and the free London mulligan

For random seven-card opening at keep size k, let M_k be max over all physical
bottom choices of predicted U. Set C_0=0, C_1=E[M_1],
C_k=E[max(M_k,C_(k-1))] for k=2..7.

At a k-card London stage, compare M_k to C_(k-1). EXCEPTION: the first seven
may take its free mulligan into another seven, so compare to C_7. The second
seven compares to C_6. The DP samples each deck and player seat separately.
Model thresholds are not equivalent to the frozen v5 beam-policy continuations.

## Why not train only on old v5 decisions?

The expensive v5 mulligan can select flawed keeps or exploit overly optimistic
search. Pure behavior cloning would reproduce that policy's decisions but
would not learn P(T1), P(T2), P(T3). Prefer supervised real-outcome labels
under the intact gameplay engine. Teacher behavior data may inform a
low-cost pretraining warm-start, but its historical mulligan beam is 60,
whereas actual gameplay is beam 160: such pseudo-labels are NOT the target
outcome distribution without additional corrections.

The dataset generator currently samples a structural favorite, a naive
analytic favorite, and an exploratory random bottom candidate per opening.
This is sufficient to test the mechanics, NOT full action-support coverage.
Expand to uniform and near-tie choices across all nine decks, and actively
sample genuinely uncertain cases without leaking the final holdout.
Models trained on a restricted action distribution can exploit unseen
bottom combinations when maximized over all choices (model exploitation).

## Validation and promotion criteria

1. Sufficient real beam-160 labels covering all four classes, stages, seats,
   and nine variants. Retain training CPU time as part of any amortization
   calculation; the historical 95x figure excludes offline training cost.
2. Group-disjoint calibration. Proper scoring (Brier and log loss) and
   reliability diagrams for T1, cumulative T2 and cumulative T3. Temperature
   scaling on independent calibration labels; isotonic risks overfit when
   small. Separate calibration scores from a THIRD independent test.
3. Freeze model, selected features and per-seat/per-deck continuations before
   comparing full policy on held-out matched seeds.
4. Compare actual T1, cumulative T2 and T3, keep distributions, paired
   discordances, confidence intervals, CPU per game and seed trace parity
   of physical deck/seat/hidden draws.
5. Prefer a simple logistic baseline first; compare a shallow boosted tree
   if nonlinear interactions dominate, never a from-scratch transformer.
6. Iteratively add labels from new learned-policy states on TRAINING IDs
   to address distribution shift, then recalibrate on disjoint data.
   Never tune to the final gameplay holdout.
7. Require a large independent comparison for non-inferiority; N16 cannot
   establish that an early-deployment loss of a few percentage points is real.

## Prior diagnostic (not a policy selection)

Paired holdout N16, GitHub Actions run 41245401673:
- v5 beam mulligans: T1 1/16, T2-or-earlier 8/16, T3-or-earlier 11/16,
  mean keep 4.875, online execution 429.151 seconds.
- v7 untrained analytic mulligans: T1 0/16, T2-or-earlier 6/16,
  T3-or-earlier 11/16, mean keep 4.8125, execution 4.529 seconds.
- 94.8x observed speed difference but very wide paired T2 uncertainty.
  V7 was an engineering control, not the trained policy.

## Relevant reading

- scikit-learn probability calibration, independent calibration data,
  Brier/log-loss, low-sample isotonic caution:
  https://scikit-learn.org/stable/modules/calibration
- Ross, Gordon and Bagnell (2011), training/deployment distribution shift
  in sequential imitation learning:
  https://proceedings.mlr.press/v15/ross11a
- Stanford AI Measurement Science, contextual bandit/off-policy limitations:
  https://aims.stanford.edu/textbook/src/chap9.html

Do not conflate calibrated goldfish turn probabilities with real four-player
Magic win probabilities, regardless of the mulligan optimizer.


## Initial real-label pilot and rare-event coverage failure

GitHub Actions 41246601250 generated 32 independent training opening-hand
scenarios and 32 disjoint calibration scenarios with two candidate bottom
choices (or fewer when identical) and four independently sampled futures per
candidate. The 16 label-generation shards all passed and produced:

| Split | T0 (no deployment) | T1 | T2 exact | T3 exact | Total |
|---|---:|---:|---:|---:|---:|
| Training | 141 | **0** | 13 | 70 | 224 |
| Calibration | 143 | **0** | 25 | 56 | 224 |

The four-class trainer **correctly refused to fit**, because there are
no turn-one outcomes to learn. This is insufficient outcome support,
not a simulator crash. Sampling unselected random seven-card hands
across arbitrary mulligan stages grossly undersamples the fast, retained
hands we actually care about. Thus a simple random corpus is inadequate
even when its total label count looks reasonably large.

The corrected real-label pilot workflow now explicitly assesses all
four class counts and reports MORE_LABELS_REQUIRED rather than falsely
promoting an uncalibrated model. It requires at least eight labels of
each class in EACH independent split just to attempt an experimental
fit; this low gate does not establish scientifically adequate T1
calibration.

Before scaling:

1. Training should deliberately include a predeclared fast-hand stratum,
   e.g. hands with early LED/Sol Ring/Mana Vault/Ancient Tomb access and
   potentially meaningful white sources, as well as uniform random
   hands at multiple keep sizes. Log the stratum and sampling scheme.
2. Calibration should remain independent and represent the expected
   decision distribution or be appropriately stratified/weighted with
   explicitly known inclusion probabilities. Do not calibrate raw T1
   probabilities on a biased, unweighted fast-hand sample.
3. Include samples of the *actual hands selected by existing/learned
   policies* and near decision thresholds (DAgger-style corrective data).
4. Do not optimize a policy by greedily maximizing an under-supported
   model over 35 bottom choices. Ensure coverage of all relevant action
   combinations and inspect newly preferred choices.
5. Keep explicit class coverage tests and use a fresh, untouched paired
   policy holdout even when the model achieves attractive training
   log-loss or a large deployment speedup.

This is an important finding: a real model cannot emerge just from
trying to replace every expensive hypothetical beam with a few hundred
random nonrepresentative labels. The computation has been moved to an
offline stage, but careful training design still matters.
