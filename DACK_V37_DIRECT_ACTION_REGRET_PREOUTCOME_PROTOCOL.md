# DACK v37 — PRE-OUTCOME DIRECT KEEP-minus-MULL ACTION REGRET

**Isolated branch** `dack-v37-direct-action-regret-20261101`. No production promotion.
All 99 physical cards, paired original London 7,7,6,5,4,3,2,1,
stable stochastic engine and strictly beam160 gameplay unchanged.
The original v27 KEEP, v33b bottom and original v5 stay frozen.

## Failure to avoid

v35's low-dimensional residual and v36's larger KEEP-value forest both
rarely changed v27 actions. v36 changed only 2 of 768 completely fresh
124k early states, one of which was never encountered in an actual
London game. The principal defect was *the model agreed with v27* on
750/768 states, not the T3 safety gate (blocked one).
Avoid a value-forest→v27 blended score which simply inherits v27.
Do not relax prior holdout thresholds after seeing outcomes.

## Direct policy-value target, labels and independence

For visible seven, seat and actual London stage s∈{0,1,2},
let h be EXACT frozen v33b legal final kept hand, b its bottom,
q2=Pr(strict goldfish deploy by T2 | force KEEP h,b);
c2=Pr(deploy by T2 | force MULL at stage s then follow frozen
v27 KEEP and frozen v33b bottom at all later stages).
Train the DIRECT signed difference **A2=q2−c2**;
separate **A3=q3−c3** for T3 safeguard.
Never use v5 teacher action as a training label, and never use
realized unknown library order as a prediction feature.

The physically sampled C is shared by seat×stage, not independently
observed per hand; its 256 fresh full99 future shuffles per cell
should be explicitly bootstrapped *once per cell* when evaluating.
The model trains on estimated C and cannot claim its ensemble quartiles
calibrate the uncertainty in C perfectly. A2 may be negative.
For a new policy's future MULL decisions, these are one-step values
under the frozen v33b downstream policy, NOT a solved Bellman fixed point.

## Pre-outcome sample (new 126k training IDs)

First freeze manifest WITHOUT any outcome:
- 256 independent random game IDs 126000..126255, observe ALL
  actual decision stages0,1,2; **8 separate true physical
  unseen92 future outcomes** per hand. 256×3×8=6144 KEEP outcomes.
- A different physical 768-game candidate pool 126256..127023:
  use only visible-hand/known multiset, stage, seat, frozen v27
  score, and FROZEN **v13 zero-beam teacher-imitation score** to
  select 128 *distinct physical games* where the v13 keep
  recommendation disagrees with frozen v27.
  Choose 64 smallest-absolute-v27-margin disagreements,
  then 64 largest-absolute-margin among remaining IDs.
  v13 is a PROXY of v5, NOT v5 itself; teacher prediction
  is not an outcome label, and teacher is not presumed optimal.
  For each selected ID evaluate only the one selected stage,
  **48 blinded true physical KEEP futures** =6144 additional.
- Four seats×three early actual stages×256 new independently
  shuffled complete-99 future London MULL continuations,
  fixed v27 future KEEP+fixed v33b bottom, and stable
  actual beam160 strict game. **3072 MULL outcomes**.
- TOTAL **15,360 new training physical gameplay outcomes**.
  Random and selected outer IDs never overlap, and their
  individual KEEP futures never overlap with validation.
- Uniform physical-group bootstrap is the statistical unit;
  random three stages weighted 1/3 each, targeted selected
  single stage weighted 0.6. Do not inflate 8/48 repeated
  futures as separate physical opening hands. Exactly
  preserve the actual stage0 free-seven vs stage1 seven.
- Training regressors are TWO direct action-advantage
  random forests (A2 and A3), 12 independently group
  bootstrapped models, 32 trees/head, max_depth9,
  min_samples_leaf6, max_features0.85, no posthoc
  parameter sweeps. Model input uses the v36 explicit
  hand line/capability vector plus (1) zero-beam v13
  predicted KEEP vote and (2) its signed distance
  from teacher cutoff, which are **observable proxies**
  rather than teacher action labels. Original v27
  keep estimate/margin are features but are not a
  prediction blend or fallback target.
- Empirical probability clamp enforces signed A2/A3 within
  [-1,+1]. No direct exact card-specific game-state merge.

## Frozen deployment before any holdout label

At actual stages0,1,2:
- If v27 originally MULL and lower quartile of 12 predicted
  direct A2 > +0.020 and predicted median A3 >= -0.040,
  choose KEEP.
- If v27 originally KEEP and upper quartile of 12 predicted
  direct A2 < -0.020 and median predicted A3 <= +0.040,
  choose MULL.
- Otherwise original v27 KEEP/MULL unchanged;
  final bottom always selected by *frozen* v33b.
  Stage3..7 unchanged; stage7 forced KEEP.
Quartiles are selection-stability heuristics, NOT
calibrated posterior probabilities or confidence intervals.

## New independent 127k population test

Holdout game IDs 127200..127455 (256 independent complete
physical 99-card games), all early stages0,1,2.
First archive an **outcome-blind 768-state action census**
with frozen model and hashes.
For one-step policy contrast, unchanged action states contribute
**exactly ZERO** to (new−old)*(Qkeep−Qmull), with population
denominator 768 intact. For EACH changed state sample 32
new hidden92 strict beam160 KEEP outcomes, and for every
seat×stage actually used by a changed action sample 128
new full99 frozen-v33b future MULL continuations; reuse
each C lottery as a shared random variable in group bootstrap.
Do not simulate irrelevant unchanged-action games.
Use hierarchical physical-group, within-hand rollout,
and seat/stage C-lottery resampling.

Precommitted conditional gate: >=12 changed stage actions
across all 768 independent early-stage states, strictly
positive lower endpoint of 95% two-source bootstrap
for by-T2 *population stage-value improvement*, no
convincing by-T1/by-T3 harm, and at least 5
genuinely reached changed London-path decisions.
No failure-based retuning on 127k.

If and only if all pass, benchmark fresh paired 128k
N256 complete game trajectories with v5, v27, v33b and
v37, exact same 99-slot deals, strict stable dice
beam160 and measured real full-game wall time.
New policy downstream may need re-evaluated continuations
before production even if prospective result is good.

## Predeclared method validity audits

- physical and seed equivalence if same action/final hand/library
- full99 restoration at MULL and exact 92 unknown on KEEP
- first free London seven distinct from second seven
- same validated strict key, stable chance, effects and gameplay beam160
- duplicate Plains physically distinct slots
- zero unseen-order leakage into hand features/teacher-score
- per-game group resampling, shared C treated once per seat×stage
- selected-discordance distribution is NOT random population
- v13 proxy fidelity uncertain; compare only with true physical labels
- one-step A cannot replace full-policy end-to-end benchmark
- no in-game beam160 action search cheating claim: output is
  deployment under goldfish engine, not multiplayer winrate.

All 115k, 117k, 121k, 124k outcomes are *consumed*
and NEVER reused for tuning or validation of v37.
