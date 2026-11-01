# DACK v36 — precommitted targeted early-stage value-recalibration protocol

**Branch** `dack-v36-targeted-keep-value-20261101`, isolated from v35.
No v5/v27/v33b/v34/v35/engine modification. **No approved policy**.

## Audit findings motivating v36

- v34c's physical common-continuation action comparison favored
  v5's action by +10.59pp T2 **only among the 100 selected first
  v5/v27 disagreements**. That was not an ordinary-hand policy winrate.
- v35 attempted a 19-dimensional direct T2 residual fit on 164
  physical training groups, but changed only 8/896 independent 121k
  stage decisions: expected T2 +0.0645pp, 95% two-source
  bootstrap [−0.157,+0.314]pp; T3 −0.101pp. v35 failed.
- v5's internal London evaluator receives visible seven, physical
  *multiset* of unknown 92, seat, and 50-beam simulated hypothetical
  futures generated independently from a deterministic shuffle of
  that multiset. Source audit found **no use of original future
  92 order in v5's keep choice**, but it is a search-based surrogate
  with different beam and T3 weight. Do not assume oracle quality
  or transfer full-game v5 outcomes to new policy.
- Important general modeling pitfalls: (1) training on teacher
  disagreements causes selection bias; (2) shared Qmull is
  sampled, noisy and seat/stage-specific; (3) model bootstrap
  tree variation is not calibrated action-value uncertainty;
  (4) 7/7 London stages MUST NOT be identified by keep_n; (5)
  action-value learning under frozen future policy is not a
  Bellman-consistent full changed policy; (6) outcome labels
  under beam160 are *solver success*, not realized multiplayer
  match win probability; (7) exact card IDs in a hand are legal
  features, but heuristic approximate capabilities are NOT
  legal game-state equivalences.

## Training selection FROZEN before outcome labels

Use 123000..123127 **128 independent, unselected random physical
game IDs**, plus candidate pool 123128..123639, 512 other
physical game IDs, select **128 near-boundary IDs** using only
visible stage0–2 seven and frozen v27 Qkeep−C margin. Six
selection strata: stage0 keep and mull each 24, stage1
keep and mull each 20, stage2 keep and mull each 20;
pick smallest |margin| within stratum, each selected outer
game ID used at most once. No actual gameplay or v5 action
label used in selection. Archive the manifest BEFORE drawing
any outcomes. Selection is deterministic and seeded by
the existing physical 99-card and seat distribution.

For ALL 256 selected/random physical outer games,
evaluate every stage0,1,2, each using frozen v33b
legal bottom selector, and 16 independent shuffled
hidden-92 physical futures with stable-effect beam160
gameplay. 256×3×16=**12,288 actual physical KEEP outcomes**.

For each of 4 seats × 3 early stages, estimate REAL
Qmull by 128 independent full99 future London stage
reshuffles under EXACT frozen v27 future keep and v33b
bottom; 4×3×128=**1,536 physical MULL deployments**.
No rejected visible seven or original future shuffle
in C. Each C sample is shared across all training hands
of that seat+stage; it is not a separate per-hand label.

Total TRAIN physical deployments **13,824**.
The 128 targeted training groups are deliberately
selection biased, so give them group weight 0.5 versus
random group's 1.0, and give each of 3 stage observations
1/3 weight. Neither group acts as an unbiased estimate
of population winrate, which only fresh random validation
can supply.

## Candidate frozen before holdout

A single predetermined model:
8 independent outer-*physical-group* bootstrap fits,
scikit-learn RandomForestRegressor, 32 trees per ensemble
per outcome (T2 direct KEEP and T3 direct KEEP), depth8,
minimum leaf 10, max_features 0.8, random_state derived
only from bootstrap index, no hyperparameter sweep.
Each training row is a 16-physical-future by-T2/by-T3
empirical probability for the EXACT v33b bottom hand.
Separate real T2/T3 Qmull is estimated using only 123k
independent future outcomes.

Features: 27 compact v33b mana/ability features,
20 hand-level key-card indicator features, 16 specific
engine-line pair indicators, original frozen v27 Qkeep,
original v27 continuation, margin, stage0/1/2 and seat
one-hot. These are approximately 73 feature dimensions
and are observational features, NOT full game-state keys.

For candidate KEEP probability ensemble, blend
0.35×frozen v27 Qkeep with 0.65×new predicted Qkeep(T2)
(to preserve large-margin baseline discrimination).
Direct T3 predicted only by new T3 forest.
The C(train) score is the actual physical Qmull
per seat/stage. Account for its binomial uncertainty
in the decision gate with a conservative 0.5 standard
error allowance.

Actual stage0–2 actions may override original v27:
KEEP instead of MULL iff ensemble lower-quartile T2
KEEP−C exceeds **+0.02**, accounting for half a C
standard error; T3 ensemble lower-quartile KEEP−C3
not below **−0.04**.
MULL instead of KEEP iff ensemble upper-quartile T2
KEEP−C below **−0.02**, accounting for half a C
standard error; T3 ensemble upper-quartile
KEEP−C3 not above **+0.04**.
Otherwise default to frozen v27 original action.
At later stages keep unchanged v27, and at stage7
force KEEP. No model inference may see future unknown
library *order*. Quartiles are stability heuristics,
not formal statistical confidence intervals.

## Untouched population validation, independent of all development

**124000..124255** 256 randomly dealt independent games,
all early actual stages0,1,2, 12 blind physical unseen92
futures per state: **9,216 KEEP outcomes**.
Separately fresh Qmull for 4×3 seat-stage cells
×64 full99 physical futures =**768 MULL outcomes**.
Total **9,984 independent beam160 validations**.
Both strata fully separate from 123k/115k/116k/121k,
and from any model fitting.

Compare changed policy to frozen v27 action using
actual heldout Qkeep and shared C. Report unconditional
conditional-action improvement over all 768 stage
decisions, by-stage improvement, directions and counts.
Paired hierarchical bootstrap resamples 256 physical
outer game groups, 12 fresh unseen92 per hand and
each seat-stage C lottery ONCE per resample.

Acceptance gate: meaningful **strictly positive T2**
bootstrap lower endpoint, no convincing T1/T3 damage,
at least several real changed actions, and policy
frozen/untouched validation integrity. If failed, STOP:
do not tune on 124k. If passed, fresh 125k N256
four-policy full-game comparison (v5/v27/v33b/v36),
same physical deals, stable beam160 and measured
runtime. Neither 124k screening nor group bootstrap
alone establishes policy improvement.

## Rules fidelity

- 99 unique physical slot IDs, London stages (7,7,6,5,4,3,2,1)
- First free seven stage0 distinct from stage1
- Full 99-card reshuffle after forced MULL
- Keep uses *v33b original* selected hand and bottom;
  exact 92 hidden cards in their simulated physical
  order, bottoms appended
- Actual gameplay remains strict v5-search-order-invariant
  chance and 160 beam, no mulligan beams for candidate
- Goldfish commander by T1/T2/T3, NOT multiplayer cEDH
  winning rate, NOT strategically realistic opponent responses

No original 115k outcomes, inspected 117k, v34c
replication, or inspected 121k validation may
enter model fitting, thresholds, or group selection.
