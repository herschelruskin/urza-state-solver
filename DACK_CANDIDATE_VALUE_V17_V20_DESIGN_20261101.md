# DACK candidate utility modelling: v17–v20 experimental handoff

**Branch:** `dack-counterfactual-engine-v1-20261030`. **Production policy:** v5 unchanged. All learned policies remain unapproved.

## Research objective

Train conditional deployment value of alternative bottoming choices, rather than only imitating the v5 teacher's chosen candidate. Use actual fixed-rules, full beam-160, legal 99-physical-slot game outcomes after a sampled London keep. Maintain no hidden future-order leakage into features. At inference, use model scoring only; no mulligan beams.

Utility for exact deployment classes: `U=P(T1 exact)+P(T2 exact)+0.5*P(T3 exact)`. Actual experimental goldfish deployment is not four-player cEDH win probability.

## v17 paired bottom candidate pilot

GitHub Actions run `41260233508` SUCCESS. Eight archived v5-visited states, 27 candidate choices, 216 actual rollout outcomes, eight independently sampled futures for every candidate within a decision group. All candidates share the hidden 92-card future permutations and seed-matched stable dice within a group.

v5's preferred bottom had higher empirical U than structural-first in three cases, lower in one, and equal in four. An example showed v5 U 0.5 versus structural-first U 0.0625 (eight rollouts, noisy).

## v18 full paired candidate corpus

GitHub Actions run `41260593011` SUCCESS.
- Physical input scenarios: 144 prior v5 teacher-training game IDs 60000–60143; 40 separate teacher-validation game IDs 61000–61039.
- Eligibility, fixed before outcome sampling: final teacher-visited London stage with keep_n 3..6 and more than one legal structural candidate; the choice is determined by teacher path, not by the new candidate's outcome.
- Eligible training: **113 game groups**, **390 candidate hands**, **3,120 beam-160 futures**; 31 unqualified groups excluded by the eligibility rule.
- Eligible validation: **32 independent groups**, **108 candidate hands**, **864 real futures**; 8 ineligible groups.
- Candidate set: structural first three, plus original v5-selected option if outside first three. The original teacher choice is offline additional training/evaluation evidence; it is NOT available to the new model at decision time.
- All real future library orders are discarded after labeling. Every label retains the grouped game ID and exact candidate bottom; the training and validation groups do not overlap. SHA-256 provenance at `datasets/v18_paired_real_candidates/manifest.json`.

## v18 regression student and validation

GitHub Actions run `41260875697` SUCCESS. Model `models/dack_v18_paired_candidate_utility_EXPERIMENTAL.json`; metrics `benchmark_results/v18_paired_candidate_utility_validation.json`.

Learner: 128-tree depth-7 RandomForestRegressor, minimum leaf 4, 65% feature sampling, stage-balanced weights; exports pure-Python tree nodes with complete sklearn-equivalence check. Predicts conditional early-deployment *utility*, not multiclass probabilities. Inference strictly chooses only among the visible structural top-three and never reads the v5 teacher index. The same line-aware feature schema used by the prior teacher-imitator (including tutor, lands and pair-interaction flags) is retained.

On 32 separate validation decision groups, measured on their paired real futures:

| Metric | Structural-first | v18 predicted-value choice | v5 teacher (can choose outside top 3) |
|---|---:|---:|---:|
| Mean actual U | 0.50977 | **0.57617** | 0.65039 |
| Mean actual cumulative T2 fraction | 0.35938 | **0.41406** | 0.48828 |

The v18 model chooses a different candidate from structural-first in 65.625% of groups, with mean paired utility gain +0.06641. Group-bootstrap 95% CI [+0.00195,+0.13086], but a separate exploratory paired sign-flip two-sided p~0.068; **evidence is promising, not decisive**. Its measured regret against the noisy retrospectively best top-three candidate is 0.03711. The teacher's bottom was outside top-three in 37.5% of these validation groups. Old v16 conditional probability forest selected a mean actual utility of 0.56055 when applied to these alternatives, but was trained on v5-kept hands only.

## v19 end-to-end isolated policy

Module `dack_paired_counterfactual_v19_real_candidate_value_20261101.py`:
- Keep/reject classifier is the unmodified frozen 128-game v14 student.
- For hand sizes keep_n 3..6, select bottom based on v18 predicted utility among first three legal structural finalists, never knowing teacher's choice.
- For keep_n 7, 2, and 1, use previous v14-128 candidate-choice classifier (since direct candidate-value model lacks coverage).
- Actual post-keep game is unchanged beam-160 strict/stable-dice physical goldfish solver. No speculative gameplay beams in student mulligans.
- Model files are checksummed and production approval remains false.

Fresh independent full-game research comparison against v5 and v14-128 uses reserved 72k outer game IDs (16 paired games) under Actions run `41260922057`. The 72k results MUST NOT be used for model fitting or adjusting the existing regression without making them development data.

## v20 top-six coverage diagnostic

GitHub Actions run `41261019537` SUCCESS. From 16 development validation game IDs, 11 states were eligible. V5 selected outside top-three in 4 states and outside top-six in 2. Mean empirical-best U among first three=0.60227, among first six=0.60795, measured incremental +0.00568. These best-of-eight-real-futures are optimistic, noisy *oracles*, not attainable calibrated values; the diagnostic cannot establish that enlarging candidate choice is useless. Results belong to **development** and may not be treated as an untouched validation set.

## Outstanding direction

- Interpret actual fresh 72k paired-game result before claiming online policy improvement.
- If v19 improves or matches v14 speed and deployment, sample fresh 74k+ games at higher N (keep future test IDs independent).
- Whether v19 improves or not, collect richer **student-visited** candidate-value states, because the original v18 stage sampling uses only v5-reached decisions and a restricted final eligible stage.
- Increase number of independent candidate states and consider repeated 16-future labels for near-tied high-regret decisions, with independent group-disjoint calibration.
- Extend candidate-value support to k 7/2/1 and derive London keep/mull continuation by offline probabilistic dynamic programming; only then remove fixed teacher keep-head if better paired-game evidence exists.
- Never pool N16 results as though they establish equivalence or replace the stable v5 baseline.
