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


## October 31 data collection outcome — reproducible archived corpora

Both real-outcome sets are now committed on isolated branch
dack-counterfactual-engine-v1-20261030 with per-file SHA-256 manifests.

- datasets/natural_v8_20261031/manifest.json: 448 real labeled beam-160
  rollouts, 32 separate training + 32 calibration seven-card scenarios
  (IDs 20000–20031 and 30000–30031). Class counts training:
  [T0 141, T1 0, T2 13, T3 70]; calibration:
  [T0 143, T1 0, T2 25, T3 56].
  These are naturally dealt but UNSELECTED sevens sampled across London
  stages, not a representative policy-kept distribution.
- datasets/stratified_v9_20261031/manifest.json: 320 additional labeled
  beam-160 rollouts, 32 new training + 32 new calibration scenarios,
  IDs 20200–20231 and 30200–30231. Class counts training:
  [T0 56, T1 77, T2 11, T3 16]; calibration:
  [T0 63, T1 68, T2 15, T3 14].
  All stratified label rows record selection_stratum and forced card core.
  Physical seven cards are drawn conditional on predefined fast-mana cores,
  or naturally from a shuffled 99. NO model feature includes future draw
  order. Oversampled fast strata intentionally distort class prevalence.
- 768 total persisted rollout labels from 128 independent scenarios.
  Training vs calibration scenario IDs never overlap. Every individual
  hidden future is independently sampled conditional on that scenario.
- Initial real enriched-data four-class softmax was trained only as an
  experiment: 32 training groups, 32 calibration groups, 160 labels
  per split. On its separate, enriched-distribution calibration data,
  multiclass Brier score=0.30449, log loss=0.61760,
  temperature=1.51270. This is NOT a deployment calibration result,
  and no independent learned-policy win-rate holdout has been run.
- New exported models carry diagnostic_only=true,
  deployed_policy_approved=false. The learned policy runner refuses
  unapproved models for gameplay; --diagnostic-audit-only allows merely
  inspecting an experimental model artifact.

Experimental enriched model and CI reports:
https://github.com/herschelruskin/urza-state-solver/actions/runs/41253501291

Permanent corpus archival validations:
https://github.com/herschelruskin/urza-state-solver/actions/runs/41253660290
https://github.com/herschelruskin/urza-state-solver/actions/runs/41253698800

NEXT: balanced and independently sampled policy-kept calibration cases
with sufficient T1 coverage. Mix the archived natural and fast-stratum
training corpora for diverse learning, but DO NOT simply concatenate
both calibration sets and present the unweighted result as a natural
deployment probability. The final paired v5-versus-learned policy
comparison must use entirely new unused game seeds.

## October 31 continued experimentation — policy-selected data, corrective training, and hybrid screening

**Total persisted actual beam-160 conditional outcome labels:** 3,328
across (a) natural v8=448, (b) deliberately enriched v9=320,
(c) v7-policy-kept v10=1,024, (d) independent v7-selected predictive
holdout=512, and (e) learned-v8-selected corrective v11=1,024.
The holdout outcomes are NOT training data. Independent splits and
per-file SHA-256 manifests are preserved in their respective datasets.

### Naturally policy-kept calibration

The v10 model trained on 896 mixed real outcomes (192 independent
training scenarios) and fit temperature on 512 new v7-policy-kept
outcomes (128 calibration scenarios). The independent 128-scenario
predictive holdout (512 rollouts; GitHub Actions 41254178107)
showed: P(T1) expected 8.50% vs actual 5.27%; P(T<=2) 35.61%
vs 40.04%; P(T<=3) 70.11% vs 76.17%. Four-class Brier=.63566,
log-loss=1.12148. The model is not fully calibrated.

All nine per-deck/per-seat London DP tables were computed with
64 independent sampled sevens per seat and keep size. These tables
are hashed to the exact corresponding model; do not swap v10 and
v11 DP tables.

### First realized learned-policy comparison (fresh 41k game IDs)

Actions 41254412065, 16 paired complete games:
- Strict beam-v5: T1=1, cumulative T2=4, T3=12, mean keep=4.625,
  CPU 555.688 seconds.
- Experimental learned-v8: T1=0, T2=2, T3=11, mean keep=5.0625,
  CPU 3.801 seconds.
- Paired T2 gains 1, losses 3. Approx 146.2x online runtime ratio,
  but *worse nominal T2*, not non-inferior.

### Corrective model and second full-policy comparison

Collect actual teacher outcomes on independent hands selected by the
first learned policy (fresh 22k training / 32k calibration groups).
In the corrective dataset, training T1 was scarce (5/512) and
calibration T1=24/512. The corrected training model reused the archived
natural/enriched/v7-selected training data, which provide sufficient
T1 examples: 1,408 training outcomes across 320 independent scenarios.
Temperature was calibrated only on the 512 corrective calibration
outcomes, not the first 41k game comparison.

v11 independent corrective calibration (Actions 41254895641):
temperature 1.73675; Brier .52462, log-loss .91026;
T1 predicted 4.23% vs observed 4.69%;
cumulative T2 34.82% vs 31.64%;
cumulative T3 69.07% vs 68.55%.
These are calibration-set numbers, NOT fresh-policy win rates.

Independent 42k full-game comparison (Actions 41255014354, N16):
- v5: T1=0, T2=3, T3=12; mean keep 4.3125; 563.979 s.
- corrective learned v11: T1=0, T2=0, T3=11;
  mean keep 4.5625; 7.412 s.
- Approx 76.1x faster but 3 lost T2s and no gains.
  Do NOT promote model.

Decision trace audit (Actions 41255286014;
benchmark_results/learned_v11_missed_T2_decision_audit.json):
ALL THREE lost T2s were **different mulligan keep stages**, not
a bottom-choice dispute at the same keep stage. One seven with
Gemstone Caverns + Enlightened Tutor + Mycosynth Gardens scored
0.610, just below the learned cutoff 0.634, then the learned policy
mulliganed deeply while v5 kept and won by T2. Another seven with
Grim Monolith/Mox Opal/Tezzeret/Trinisphere was kept by the learned
policy but rejected by v5 in favor of a later winning 3-card keep.

### Confidence-gated hybrid test: FAILED as a speed–performance tradeoff

A development-only v12 branch calls the original exact-sampled beam
mulligan evaluator when |learned score − DP cutoff| <= 0.075.
This band was chosen AFTER inspecting the 42k failure traces and
was then tested only on new 43k game IDs.

Dry-run on 256 separate sampled scenarios found 156/932 London stages
(16.74%) eligible for exact fallback.

Independent N16 paired full-game result, Actions 41255514274:
- v5: T1=2, T2=11, T3=13; mean keep=5.8125; CPU 210.442 s.
- hybrid v12: T1=2, T2=6, T3=10; mean keep=5.8125;
  CPU 74.650 s. Seven actual fallback stages over 44.
- Hybrid 2.82x faster, but 0 T2 gains and 5 T2 losses.
  Even a relatively low fallback frequency imposes substantial
  runtime cost and did not recover early deployment.
  N16 remains too small for precise population noninferiority claims.

**Current project choice:** Preserve strict stable-dice v5 as the
reference and all experimental models unapproved. Stop iterative
threshold tuning on reviewed holdouts. The strongest next research
option is a *line-aware teacher-policy distillation* model:
learn keep/mull and bottom-choice ranking directly from paired
v5 decisions and structural synergy features (tutor, white,
LED, Gardens, gemstone, untap/recovery), while separately
calibrating objective game-outcome probabilities. Use categorical
nonlinear interactions or modest tree ensembles; test exact
data provenance and unseen lines. Reassess on a completely fresh
physical-game-ID band (44k+) only AFTER freezing the next model.

A JSON research handoff with distinct seed bands and all results is
archived as benchmark_results/learned_mulligan_v8_v11_v12_research_handoff.json.
None of these experimental win rates should be presented as actual
four-player cEDH win probability, or pooled with old stochastic rules.
