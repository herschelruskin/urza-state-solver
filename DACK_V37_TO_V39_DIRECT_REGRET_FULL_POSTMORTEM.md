# DACK v37 → v39: direct-regret model, physical speed/consistency trade-off, and independent negative validation

**2026-11-01. Research-only branches; NO model promoted.**
`dack-v37-direct-action-regret-20261101`,
`dack-v38-weighted-action-regret-20261101`,
`dack-v39-t2-risk-bounded-regret-20261101`.

## 1. Key empirical finding: real action-regret signal is present but not yet a superior deck policy

v37 replaced v35/v36 absolute Qkeep/regression+old-value blend with
**direct true physical signed action advantage**
`A2=QKEEP(byT2)-QMULL(byT2)` and
`A3=QKEEP(byT3)-QMULL(byT3)`.
All physical rollouts fixed exact existing v33b bottom,
frozen v27 downstream keep, strict stable-dice beam160,
the complete 99-slot deck and London free-seven/second-seven distinction.

v37: 384 independent training physical game groups,
896 observed action-stage states, with **12,288 new true
KEEP beam160 futures** (256 random groups×3 stages×8 and
128 outcome-blind v13-proxy-discordant groups×48)
plus **3,072 actual shared full99 future C**. The v13 proxy
was used ONLY for selection, not as a v5 target label;
it is not the expensive actual v5 policy. 12 physical
outer-group/bootstrap forests, with shared cell-wise
C resampled once per ensemble. No T2 value from old
v27 mixed into the direct-target training label.

On 256 completely new random 127k physical games,
stages0/1/2, frozen strict v37 safety policy changed
**ZERO of 768 decisions**. Read-only diagnostics:
736 original v27 actions matched the predicted
T2-regret median sign, 8 disagreed but failed
ensemble stability/margin, and 24 passed the T2
sign margin but were vetoed by the T3 safeguard.

Physical 127k posthoc, selected 24-case T3-blocked
diagnostic (768 fresh forced KEEP and 1,152 fresh
full99 MULL futures; all original source shards
recovered and archive-stamped after correcting
a pooling self-test formatting mistake):
- New MULL vs original KEEP, byT1 **+3.223pp**,
  two-source physical bootstrap CI [+1.732,+4.883].
- ByT2 **+15.592pp**, CI [+7.779,+22.113].
- ByT3 **−18.945pp**, CI [−28.363,−8.094].
- Frozen model had predicted T2 +12.125pp and
  T3 −18.999pp on these selected cases.
- Original strict T3 veto therefore prevented
  real T3 losses while also suppressing T2 gains.
- This 24-case evaluation was **posthoc and
  selected on model predictions**, NOT an
  independent population policy validation.
  No model-selection claim is justified on it.

## 2. The incompatible reward definitions MUST be explicit

`U_cum=P(win by T2)+.5*P(win by T3)`
=1.5 PbyT2+.5 PexactlyT3.

`U_exact=P(win by T2)+.5*P(win EXACTLY T3)`
=.5(PbyT2+PbyT3).

The older search reference v5 used the second
score (a half-weight on exact T3). These are
NOT interchangeable. In the selected 24-case
physical diagnostic, the same MULL changes
averaged +6.12pp on U_cum, but −1.68pp on
U_exact. Even an objectively faster T2 policy
can be worse on the historical v5 objective.

An isolated **v38** selected the first
U_cum objective via paired T2/T3 *same-member*
bootstrap predictions (not independent
sorted-quantile marginals), with ±.02
ensemble-quartile margin. On 512 entirely new
129k physical groups ×3 stages (1,536 decisions),
it altered only **3 actions**, with only **2
actual London final physical states** changing.
The predeclared coverage gate failed, so no
129k physical outcome labels or costly full-game
test were generated for v38. It remains unapproved.

## 3. v39: independently test T2-first with per-hand bounded T3 sacrifice

v39 preserved EXACT frozen v37 T2/T3 regressors,
v33b bottoms, real 99 card deck and engine.
A single predeclared new action rule:
- MULL→KEEP if lower quartile of A2>+.02 and
  lower quartile of A3≥−.25.
- KEEP→MULL if upper quartile of A2<−.02 and
  upper quartile of A3≤+.25.
- Original v27 otherwise; only actual London
  stages0/1/2 eligible.
- T3 guard of 25pp here is an **experimental
  predicted per-hand risk budget**; does NOT
  license 25pp actual T3 losses as acceptable.

The untouched **131000..132023** cohort included
1,024 independently dealt physical game groups
×3 stages=**3,072 physical action states**.
Census completed/archived BEFORE any 131k physical
outcome labels. Found 47 stage changes
(46 KEEP→MULL, 1 MULL→KEEP), and 30/1,024
actual final retained hand/ordered libraries
differed. Other 994/1,024 final physical
game states were EXACTLY identical and must
produce identical stable-seeded engine outcomes.
Stage changes 0:4; stage1:18; stage2:25.
The coverage gate passed, not the improvement gate.

Algebraically exact zero-action-regret pruning
on 3,025 identical stage actions retained
all **3,072** physical states in denominator.
Only 47 distinct physical KEEP hands ×32 fresh
unseen92 shuffled game futures = **1,504**
beam160 deployments. Shared actual C for the
eleven required seat-stage cells ×128 independent
full99 later London physical futures = **1,408**
beam160 deployments. Total **2,912 new strict
beam160 physical trials**. Original shard archives
complete and preserved in 28 files. A read-only
group-bootstrap aggregation initially used a
`gid`/`game_id` key typo; corrected and
re-pooled **the same 28 success artifacts**,
without replaying or changing any physical sample.

Each 95% CI resamples original 1,024 independent
physical outer groups; each hand's 32 physical
unknown92 futures; and each shared 128-future
seat-stage C lottery ONCE per replicate.
Correct cumulative turn metrics:

| N1,024 random early-stage population comparison | v39 minus v27/v33b action, percentage points | Two-source 95% bootstrap |
|---|---:|---:|
| By T1 | +0.0504 | [+0.0239,+0.0821] |
| **By T2 (primary)** | **+0.1035** | **[−0.0351,+0.2396]** |
| By T3 | −0.2607 | [−0.3927,−0.1437] |

T2 improved on 37 of 47 changed stage states;
10 were physically worse at T2. ByT3 was
worse on 38 of 47 changes. Stage0 T2 −0.120pp
over 1,024 stage0 states, stage1 T2 +0.314pp,
stage2 T2 +0.117pp. DO NOT exploit that
posthoc stage pattern by editing v39 and then
calling this 131k set an untouched holdout.

**Gate FAIL**: the byT2 two-source lower 95% CI
remains below zero despite a positive point
estimate. Thus do NOT run the preprepared 133k
N1,024 paired v33b/v39 full-game benchmark.
No v39 model promotion or new engine assumptions.

A further fully read-only, **correlated** utility
analysis reused SAME actual K and shared C
physical turn draws when computing T2 and T3
within every bootstrap draw:
- U_cum = PbyT2+.5 PbyT3:
  **−0.02683pp**, 95% [−0.19557,+0.13301].
- U_exact = PbyT2+.5 PexactlyT3:
  **−0.07858pp**, 95% [−0.18082,+0.01755].
Neither confirms a speed/consistency utility
gain. This analysis is descriptive after
131k inspection and not a new holdout.

## 4. Explicit identified pitfalls and next action-regret research

1. **Training-example representativeness.** v37 used
   v13 student *proxy* disagreements rather than
   true expensive v5 disagreements. Its source
   selection is outcome-blind but may not capture
   the same consequential lines as v34c's 100
   actual v5-v27 first-policy disagreements,
   which under a common v33b continuation
   favored the v5 action by +10.59pp byT2
   conditional on selected disagreements.
2. **Regression and policy improvement are distinct.**
   The model can accurately predict a T2/T3 tradeoff
   on 24 posthoc hand states without learning
   a useful generalizable policy; v37 changed 0/768,
   v38 3/1536, and v39 47/3072,
   many sacrificing byT3.
3. **Target-horizon selection.** The v5 teacher
   score rewards T3 exact differently from a
   T2-first objective; do not assume
   teacher-action agreement is always optimal
   for the user's speed objective.
4. **Same-action zero-regret pruning** is exactly
   valid for one-step action-value comparisons;
   it is NOT a license to merge different physical
   gameplay states, assume similar bottoms are
   identical, or skip changed action deployment
   full-game evaluation.
5. **Frozen future C is not a changed-policy
   Bellman fixed point.** Actual future
   KEEP decisions may change after earlier
   v39 decisions; full-game paired prospective
   replay remains mandatory before promotion.
6. **Shared C and correlated turn horizons.**
   One seat-stage C lottery is shared by many
   physical hand rows, and byT1/byT2/byT3
   are cumulative correlated measurements;
   never treat the rollouts or different
   outcomes as independent game groups.
7. **Unseen cohort discipline.** The v37 127k,
   v38 129k, and v39 131k cohorts have been
   inspected. New thresholds, weights, stage
   limitations or model classes require
   **completely new** training and validation
   cohorts; no retrospective "repair" can
   recover an untouched 131k set.
8. **Real cEDH vs goldfish.** All physical
   win rates represent strict beam160 solver
   ability to deploy Dack by turn 1/2/3,
   without opponents. It is not a calibrated
   four-player match winning probability.

Recommended future path:
- FIRST test **true v5/v27 disagreement as a
  sampling stratum** using fresh random source
  game IDs and exact actual reference decision,
  not merely zero-beam v13 vote. Pair with
  independent random hands at ALL early stages.
- Physically label true KEEP and full99
  MULL actions under a matched downstream
  at sufficient independent outer group counts,
  and evaluate regret-signed calibration
  with grouped out-of-fold training rather
  than teacher decision imitation.
- Consider a small **interpretable action
  classifier** on residual advantage and
  separate known T2 fast-line capabilities;
  do not blindly blend absolute v27 Qkeep
  nor trade significant byT3 harm for tiny T2.
- Reserve fresh independent holdout and
  new full-game prospective only if the
  policy both changes reached London paths
  and improves physical T2 with acceptable
  T3 tradeoff and uncertainty.

Full raw outcomes, signed model, census,
read-only utility comparisons, and workflows
are archived to the isolated research
branches. v33b remains the strongest previously
tested fast bottom selector, still experimental.
