# DACK v33b postmortem — search-free pairwise bottom regret (2026-11-01)

**Status: completed independent 115k N256 prospective pilot; candidate remains
UNAPPROVED. Preserve v5/v14/v27/v32/v33.** Branch:
`dack-v33b-capability-regret-20261101`.

## 1. Objective and frozen intervention

Recover v5 deployment without its expensive per-London beam search,
while preserving physical 99-card shuffles and strict game beam160.
v33b is deliberately a **bottom-only intervention**:
the ENTIRE v27 keep-versus-mull path, v27 value model and v27 continuation
thresholds are executed unchanged. Only after the same final KEEP is chosen
may a search-free bottom selector override v14. This isolates the cause
of any v33b-v27 difference but is NOT a new Bellman-consistent keep policy.

Training source 112000–112127, 128 independent physical groups,
77 eligible with nonempty bottom, 61 with alternative options,
90 paired label comparisons, eight true beam160 futures per choice.
Only 27 of 90 comparisons had nonzero observed T2 differences.
27 compact mana, white access, combo, tutors, artifacts, imprint,
metalcraft, land and seat features (NOT an equivalence fingerprint).
16 group-bootstrap regularized linear ridge fits, lambda=12.
T2 primary and T3 safeguard, no random forest added.
At inference allow only four search-free TRAINING-SUPPORTED candidate
generators, then require 25%-quantile across fits of predicted
T2 advantage > +0.01 and median T3 disadvantage >= -0.025.
The quantile is a heuristic stability gate, not a formal interval.

### The false shortcut rejected first

A direct reuse of the existing v27 absolute Qkeep model to rank
alternative bottoms produced +7.14pp T2 conditional training advantage
but only +0.56pp (group-bootstrap CI -5.0..+4.72pp) in independent
113k validation. Neither v27 Qkeep bottoming, v18 top-three,
nor analytic proxy was promoted. This establishes that off-policy
absolute Qkeep extrapolation was NOT an adequate solution.

## 2. Fresh independent 114k conditional validation

Frozen v27 naturally chosen final hands, physically new unseen draws:
- 64 independent physical groups; 46 bottom eligible, 18 no bottom;
- v33b changed 10 bottoms;
- T1: +0.78125pp conditional over 64 groups;
- T2: +2.9296875pp; paired-group 95% bootstrap
  [+0.1953125,+6.640625]pp;
- T3: +2.9296875pp.

Only FOUR groups had positive nonzero T2 estimates and zero negative.
This is promising, extremely sparse, and NOT complete prospective
policy performance. No 114k outcomes were used to fit or tune the model.

## 3. Actual prospective goldfish N256, 115000..115255

GitHub Actions run 41273676882, SUCCESS, all 64 four-game physical
shards and pooling. Input deck one_key_34; same seat and canonical
physical first seven across arms. Each policy in an isolated Python
interpreter. Source result `benchmark_results/v33b_prospective_115k_N256.json`.

| Policy | T1 exact | By T2 | By T3 | Mean keep size | Sum gameplay time |
|---|---:|---:|---:|---:|---:|
| v5 reference | 7/256 (2.73%) | 132/256 (51.56%) | 214/256 (83.59%) | 5.0625 | 6158.46s |
| v27 frozen | 7/256 (2.73%) | 106/256 (41.41%) | 189/256 (73.83%) | 5.2266 | 98.98s |
| v33b bottom-only | 8/256 (3.13%) | 111/256 (43.36%) | 196/256 (76.56%) | **5.2266** | 99.97s |

v33b minus v27:
- **T2 +5 games = +1.953125pp**, five paired gains / zero
  paired losses; paired bootstrap 95% CI [+0.390625,+3.90625]pp,
  exploratory two-sided exact McNemar p=.0625.
- T3 +7 net games = +2.734375pp, nine paired gains / two losses;
  paired bootstrap CI [+0.390625,+5.46875]pp,
  exploratory exact McNemar p=.06543.
- T1 +1 game = +0.390625pp, one gain / zero loss.
- 52/256 bottoms changed, 204 unchanged.
- **All 256 London keep/mull stage and action histories identical**
  between v27 and v33b. An independent read-only audit confirmed
  all 204 same-hand replays have EXACTLY the same deployment turn.
- Actual measured gameplay speedup v5/v33b = **61.60x**;
  v5/v27 = 62.22x. Model fitting/validation runtime excluded.

v33b remains **-8.203125pp behind v5 by T2**, CI approximately
[-13.28,-3.52]pp, and -7.03125pp by T3.
The bottom-only model recovered 5/26 (~19.2%) of v5's observed
T2 advantage over v27 in this 115k sample.

Interpretation: Genuine, prospectively observed bottom-related
improvement without an observed runtime penalty, but only five
discordant T2 outcomes and a two-sided exact p=.0625.
Do NOT claim a universally proven or production-approved gain.

## 4. Remaining gap: two independent cohort audit

Read-only zero-new-beam GitHub Actions run 41274337535.
Archive: `benchmark_results/v33b_two_cohort_london_attribution.json`.

N256 each, v5-v27 matched:
- 110k: v5 131 by T2, v27 124: gap +7 games (+2.73pp).
  Different *actual stage* 110 groups, contributed net +1 T2;
  same-stage different final hand 53 groups contributed +6;
  identical final hand 93 groups contributed zero.
- 115k: v5 132 by T2, v27 106: gap +26 games (+10.16pp).
  Different *actual stage* 100 groups contributed net +19 T2;
  same-stage different final hand 70 groups contributed net +7;
  identical final hand 86 groups contributed zero.
- In 115k's 100 different-stage games, v27 kept at an earlier
  stage than v5 in 61 and later in 39.
- Cross-cohort shift in matched v5-minus-v27 T2 gap:
  +7.421875pp, independent-cohort grouped bootstrap 95% CI
  [+0.78125,+14.0625]pp. **Post-hoc descriptive comparison**;
  do NOT treat as a verified model-drift bug or stable general effect.
- v5 T1 was 19/256 in 110k but 7/256 in 115k.
  This is an important physical-cohort difficulty difference;
  seed shuffles should be independently audited if future cohorts
  systematically show shifts. Not evidence of peeking or a confirmed
  physical RNG defect.

The 115k residual gap is heavily associated with **different London
keep stages**, while the v33b-v27 intervention isolates bottom choice.
These stage-category contrasts are observational and not themselves
causal effects of an intervention.

## 5. Errors repaired, provenance, safeguards

1. Original v33 read-only diagnostic conflated keep_n with stage;
   London stages 0 and 1 both hold seven cards. Fixed before
   v33b training; all new audits use actual stage index.
2. v33b initial pooling had a Python script-path import error.
   Reused ALL 48 successfully archived physical shards through
   Actions pool-only recovery, no redundant game simulations.
3. Pairwise fit census initially failed to record no-bottom or
   identical-bottom physical groups. Repaired full 128-group
   accounting before fitting, with no validation data used.
4. No verified new physical London, hidden-future peeking, or
   stable-dice engine bug found in this project stage.
5. Functional similarity is only a feature. Never merge gameplay
   states by 27-feature vector; exact ability exceptions apply.
6. This is Dack goldfish deployment, NOT multiplayer cEDH winrate.

All original branches/models and the frozen v33b model retained.
No v33b policy promotion. Prospective matched gains still have
uncertainty and v5 remains substantially better on 115k.

## 6. Next highest-value bounded experiment (NOT yet run)

**Prioritize causal KEEP-vs-MULL regret, not more bottom forest fits.**
Predefine independent physical game groups beyond 115k, stratifying
actual London stages 0 and 1 separately and concentrating on
decision boundaries where existing policies disagree. For a visible
seven compare:

- Forced KEEP under the now-fixed v33b bottom policy, with many
  truly independent unseen 92-card futures.
- Forced MULL restoring all 99 slots, then **the same fixed v33b
  downstream policy** for future London stages.
- Share Q(MULL) continuation values only by seat/stage and this
  EXACT future policy. Estimate via backward Bellman-consistent
  policy evaluation / improvement, not v32's v27-to-v32 mismatch.
- Adaptively add rollouts where the action gap is near zero and
  uncertainty can change a decision; avoid oversampling obvious
  hands or overfitting to noisy per-hand binary labels.
- Crossfit by independent outer physical game; use direct regret
  and physical-group uncertainty, not imitation of v5 keep depth.
- Train low-dimensional line-aware features before considering
  any additional forest or model complexity.
- Preserve separate train/validation/prospective cohorts and paired
  T1/T2/T3, actual gameplay runtime, and strict beam160.
- Audit first/second seven free mulligan handling, chance coupling,
  tutor access and bottom order in targeted metamorphic tests.

We have made a real improvement to the bottom component while
retaining ~61.6x runtime advantage. The next bottleneck is plausibly
the keep decision (especially in tougher physical game cohorts),
but that conclusion remains to be tested causally.
