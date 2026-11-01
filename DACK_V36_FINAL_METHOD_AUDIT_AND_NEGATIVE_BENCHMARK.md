# DACK v36 — final training, independent physical benchmark, and method audit

**Research branch**: `dack-v36-targeted-keep-value-20261101`.
**Date**: 2026-11-01.
**Final verdict**: **FAIL / NOT PROMOTED**. The prepared 125k
full-game prospective benchmark was deliberately **NOT STARTED**:
v36 failed the independent precommitted decision-coverage and T2
action-value gates. All historic v5, v27, v33b, v34c and v35
models and physical gameplay files remain unchanged.

## 1. Source hypothesis, trained model, and exact data provenance

v34c showed a conditional +10.59pp by-T2 advantage of v5's
KEEP/MULL action over v27's action, on 100 *selected actual*
v5-v27 disagreements evaluated with shared frozen-v33b future
continuation. That is not an unconditional deck winrate.
v35's 19-feature ridge translated this into only 8/896
changed independent stage actions and +0.0645pp T2
(bootstrap 95% CI [-0.1569,+0.3139]), failing validation.

v36 replaced ridge with a frozen 73-dimensional
observable-capability two-head random forest:
8 independent 256-physical-group bootstrap fits, 32
trees/head, depth8, minimum leaf10, max_features0.8;
per-state training target is TRUE physical P(deploy by T2)
and P(deploy by T3), not a v5 keep-label imitation.
T2 score mixes 35% existing v27 Qkeep +65% new
Pkeep physical forest. Shared C from **actual**
128 independent later full99 v27+v33b continuations per
seat/stage. No future library order or outcome is an input
to the inference model. v33b bottom retained exactly.

Pre-outcome train manifest generated before any label:
- 128 random independent physical groups 123000..123127
- 128 targeted groups from 512 independent candidate
  IDs 123128..123639, six selection strata:
  stage0 KEEP/MULL 24 each; stage1 20 each;
  stage2 20 each. Chosen only by the smallest absolute
  v27 Qkeep−old-C margin. No actual rollout or v5
  action used in selection.
- Every group evaluated at stages0,1,2 and 16
  independent true hidden92 shuffle futures. Hence
  **12,288 true beam160 KEEP outcomes** across
  768 physical stage states.
- 4 seats×3 early stages×128 independent restored
  full99 future London continuations = **1,536
  strict beam160 Qmull physical outcomes**.
- **13,824 new physically evaluated outcomes** for
  training; 256 independent outer physical groups.
- Random groups received sample group weight 1,
  boundary-enriched weight0.5. Three stage
  observations share 1/3 group weight.

Frozen unapproved model SHA256:
`3b52271ec600e2bedb35d3f5698e39b980d0695bdd3d5295e5f4ff108e5c2b48`.
No earlier 117k, 121k holdout, v34c 115k
replication, v5 policy labels or original 115k
full-game outcomes were used for this new model.

Training in-sample **action** diagnostics (NOT a
population winrate or model validation):
- 128 random groups×3 =384 stage states:
  2 MULL→KEEP and 0 KEEP→MULL;
- 128 boundary-enriched groups×3 =384 states:
  5 MULL→KEEP and 1 KEEP→MULL;
- only **8/768** training stage decisions altered.

## 2. Unseen physical 124k benchmark

Before any 124k gameplay outcome was sampled,
a complete outcome-blind census replayed the already
frozen model on **256 new random physical outer
game IDs 124000..124255×3 actual early
stage indices =768 states**. Exactly **2/768**
stage decisions differed from frozen v27:
- 124022, seat0, stage2: v27 MULL, v36 KEEP
- 124189, seat2, stage1: v27 KEEP, v36 MULL

This failed the precommitted minimum >=8
intervention gate **independently of outcome**.

An *algebraically exact* sparse counterfactual
experiment was predeclared **before any
124k physical labels**:

  D_i = (I[KEEP_v36] − I[KEEP_v27])
        × (Q_i[KEEP under frozen v33b bottom]
           − C[seat_i,stage_i under frozen v33b future]).

For 766 identical-action states, D_i is
**exactly zero in EVERY physical future**, so
it is unnecessary to waste 12 physical
simulations on each of those states. The full
768-state denominator remains unchanged,
avoiding selection inflation of the per-stage
population-average effect. A further exact
saving: shared C at unaltered seat-stage
cells is also never multiplied by a nonzero
action difference.

Required independent physical outcomes:
- 2 changed state actions×32 independent
  physically shuffled unknown92 KEEP outcomes
  each: **64**.
- 2 actual changed seat-stage cells×64 independent
  full99 later London MULL continuations each:
  **128**.
- **192 new strict beam160 outcomes**, all archived.
  Saved **9,792** physical beam160 outcomes compared
  with the all-768-KEEP-and-all-12-C planned design.
- Group bootstrap resamples independent outer
  physical game IDs (all 256), actual KEEP shuffled
  futures for changed actions, and the two shared
  C lotteries once each per bootstrap draw.

Correct cumulative by-T1/by-T2/by-T3 (not exact
turn equality) held-out results:

| Metric | v36 minus v27 frozen-action policy | Two-source 95% bootstrap interval |
|---|---:|---:|
| By T1 | +0.0020 percentage points | [-0.0163,+0.0244] |
| **By T2** | **+0.0183 percentage points** | **[-0.0448,+0.1058]** |
| By T3 | +0.0346 percentage points | [-0.0122,+0.1241] |

There was one observed positive T2 action
effect and one observed negative effect. Gate
**FAIL**; no claim of improvement. This is a
uniform-early-stage ONE-STEP conditional
comparison under the frozen v33b downstream
policy; it is not actual end-to-end policy
winrate. The changed v36 future policy is
not Bellman-refit in the Qmull labels.

## 3. Zero-beam method audit of the failure

The 768-action frozen model attribution:
- **750**: new model's T2 median itself
  agrees with the original v27 action.
- **15**: T2 median favors the opposite action,
  but lower/upper quartile and/or noisy C
  margin gates block it.
- **1**: T2 supports changing, but the
  predeclared by-T3 safeguard blocks it.
- **2**: both T2 and T3 gates passed,
  actual v36 changed actions.

Thus overly restrictive thresholding is **not
the primary defect**. Simply relaxing the
threshold or T3 guard would mostly affect
a small subset and invalidate the already
consumed 124k holdout as a model-selection
set. Strong regularization, teacher prior
blend, model class / targeted feature
coverage may have driven broad preference
agreement with v27; the current audit
cannot distinguish those causes without
new labeled groups. v36 did not learn a
generalizable alternative to v27.

Complete *actual* 256-game London replay,
zero gameplay beam:
- 255/256 games: EXACT same final physical
  hand and library under v36 and v33b.
  Consequently their true strict seeded
  game deployment turns must be identical.
- 1/256 games genuinely diverged:
  game124022, stage2 KEEP under v36 vs
  frozen v27/v33b continuing to stage4.
- game124189 had a hypothetical stage1
  differing action, but was not reached
  in the actual London path and therefore
  cannot alter that game's outcome.
- On these exact 256 physical deals,
  an end-to-end T2/T3 difference
  is limited to at most **1/256=0.390625pp**
  by physical final-state identity.
  This is a **cohort-specific logical
  upper bound**, not a population CI.
- Uniform all-stage one-step bound
  likewise max 2/768=0.2604167pp
  on this cohort, even with perfect
  value for both changed actions.

## 4. Actual CPU timing independent of gameplay outcome

Same original physical 99-slot deals,
seat, London sevens, four game IDs
125900..125903, separate interpreter
for each policy. Measure **mulligan
choose_keep only**, excluding any
actual beam160 turn gameplay.

| Policy | Sum chooser-only time on 4 games |
|---|---:|
| v5 search-based reference | 73.5896 seconds |
| v27 fast | 0.0162 seconds |
| v33b bottom-only | 0.0375 seconds |
| v36 keep value forest | 0.0585 seconds |

**v5/v36 chooser speed ratio ≈1258.3×**;
v36 costs ~1.56× v33b's chooser CPU,
but all remain fast versus v5.
This tiny N4 timing is NOT a full
gameplay runtime or whole-population
variance estimate. The previous
v33b N256 prospective benchmark
measured ~61.6× FULL-GAME runtime
versus v5; do not confuse metrics.

## 5. Engine, sampling and external-method pitfalls

1. **Unknown deck order leakage**: A separate
   explicit v5 permutation/metamorphic test
   kept visible sevens and seat fixed while
   reversing the unknown 92 physical slots
   at every London stage for three games.
   v5's action history, legal bottom, raw
   Q estimate and decision were identical
   across permutations. PASS; supports
   no *direct realized unknown order peeking*
   on those tested decisions, but does NOT
   establish general perfect-information
   fidelity or absence of teacher/model bias.
2. **Selection bias**: v34c's teacher
   disagreements are not ordinary
   randomly sampled hands; v36 used a
   random group stratum alongside its
   outcome-blind enrichment. This
   prevents treating targeted conditional
   gains as full-deck probabilities.
3. **Seat balance**: manifest metadata
   initially overstated that seats were
   balanced. Quotas enforced only
   London stage×original KEEP/MULL.
   Explicit archived no-beam seat census:
   random seats(0..3) = 21/31/39/37;
   enriched = 34/31/27/36.
   Training weighted effective outer
   sample count before stage
   correlation =230.4, not 768.
4. **Incorrect action-value continuation**
   risk: Qmull returns full99 cards,
   independently reshuffles every later
   London stage, uses frozen v27 keep
   and frozen v33b bottom. This
   successfully fixes older v32/v33
   downstream-policy inconsistency,
   but remains ONE-STEP for any
   new downstream policy.
5. **Bootstrap correlation**:
   32 futures of same hand are NOT 32
   independent opening sevens; 64 C
   futures of one seat-stage are a
   common noisy variable shared by
   many observed hands. All three
   hierarchical levels resampled
   separately, preserving the
   physical outer game as unit.
6. **Action-equivalence pruning**:
   identical action D=0 is exact
   for a *one-step difference*, NOT
   authorization to collapse
   capability-similar hands or
   distinct physical game states,
   and NOT an excuse to skip
   full-game evaluation after
   actually changed policy paths.
7. **Objective & search limitations**:
   all T2 probabilities mean
   casting Dack by Turn 2 under
   a restricted single-player
   goldfish game/search engine with
   no opponent interaction. In-game
   beam160 explores decisions
   under the supplied physical
   library; do not present this as
   cEDH match-winning probability
   or complete rules-engine
   certification. v5 search-value
   uses a different hypothetical
   rollout beam and a T3 blend
   than v27's strictly T2 objective.
8. **Repeated holdout tuning**:
   124k is now fully consumed,
   even though only two actions
   required physical outcomes.
   Do NOT lower thresholds,
   drop T3 guard, change blending
   or select a new architecture
   based on its two realized
   action outcomes and then claim
   124k as untouched validation.

Related methodology:
- Huang & Wu (2024), *Robustly Improving
  Bandit Algorithms with Confounded and
  Selection Biased Offline Data*,
  https://doi.org/10.1609/aaai.v38i18.30027
- Yang et al. (2022), *Offline Policy
  Selection under Uncertainty*,
  https://proceedings.mlr.press/v151/yang22a.html
- Dudík et al. (2012), *Sample-efficient
  Nonstationary Policy Evaluation for
  Contextual Bandits*,
  https://proceedings.mlr.press/r10/dudik12a.html

These sources motivate independent
policy evaluation and respect for
selection bias/uncertainty; they do
not by themselves prove validity of
this particular DACK engine.

## 6. Development verdict and next candidate

No evidence supports replacing v33b's
keep policy with v36. Candidate is
**not promoted** and 125k N256
prospective full-game tests are not
justified on this evidence. Retain
the frozen v33b bottom improvement
as previously observed experimental
fast candidate; do not claim that
its N256 +5 T2 wins over v27
were definitive (two-sided exact
McNemar p≈.0625).

For any genuinely different v37
candidate, do not repeat just another
forest with more features plus stronger
teacher anchoring. First test
**representation error and conditional
action-regret discrimination**, with
cross-fitted true physical QKEEP−CMULL
labels on diverse high-margin and
low-margin teacher-discordant hands,
not only the old v27 *predicted*
Qkeep−C near-boundary pool.
Reduce model selection bias with
independent random physical groups;
account for shared C lottery.
Use independently seeded NEW
training groups 126k+, disjoint
validation 127k+, full-game 128k+
only if the new conditional policy
has frequent, physically valuable
changes. Recompute self-consistent
continuations for promising early
policy candidates before any
promotion; retain the exact-zero
regret pruning and deterministic
London parity tests.

This research result is **completed,
fully archived, reproducible, and
negative**.
