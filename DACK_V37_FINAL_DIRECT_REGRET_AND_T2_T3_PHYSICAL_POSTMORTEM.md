# DACK v37 final: direct physical action regret, zero population action coverage, true T2–T3 tradeoff

**2026-11-01 · Isolated experimental branch:** `dack-v37-direct-action-regret-20261101`.

**Production verdict: NOT APPROVED, do not promote.** Independent 127k
stage-decision coverage was **0/768**, and complete physical final
hand+library paths were unchanged on **256/256** random physical deals.
Therefore by-T1/by-T2/by-T3 full-game strict stable-seed outcomes
would be identical to frozen v33b on THOSE exact games. The planned
fresh 128k N256 full-game prospective benchmark was not launched.
No 127k game outcomes were needed to establish this cohort equality.

## 1. What was actually implemented and trained

The original experimental baseline remains frozen v27 KEEP/MULL and
v33b bottom-only pairwise regret. v37 predicts **signed true
physical action advantage** rather than blended KEEP probability:

  A₂(x,s,seat) = Q₂(KEEP with frozen v33b legal bottom) −
                 C₂(MULL, restored full99, frozen v27 future KEEP
                    and frozen v33b future bottom).

  A₃ analogous for cumulative deployment by turn3.

Actual London stages0,1,2 only can change; later stage decisions and
terminal stage 7 unchanged. Unknown92 shuffle order is never a model
input. The model is a 12-member outer-physical-group and shared
seat/stage-C-lottery bootstrap of 32-tree random forests for A₂ and
A₃; 75 observable capability/line/proxy features. It does not
interpolate back to frozen v27 QKEEP predictions.

Physical training is exactly new:
- 256 random outer physical 126k groups × stages0,1,2 ×8
  blinded hidden92 true beam160 futures = **6,144 KEEP rollouts**.
- 128 other selected physical groups from 768 candidate IDs:
  64 near-boundary and 64 high-v27-margin v13-proxy/v27
  discordances, 48 independent KEEP futures each = **6,144**.
  The v13 score is only an outcome-blind proxy for v5,
  emphatically **NOT original v5 and not a training label**.
- 4 seats×3 actual stages×256 independently sampled,
  full99 restored-and-reshuffled, frozen-future
  Q(MULL) = **3,072** real beam160 rollouts.
- **15,360 independent physical gameplay outcomes**,
  clustered across 384 physical outer game groups.
  The independent *number of outer opening-hand groups* is
  384, not 15,360; future shuffles within one group
  aren't additional independent hands.
- The shared Q(MULL) lottery is resampled ONCE per seat-stage
  cell inside each bootstrap fit.
- 96 KEEP +12 C training shard archives complete and pass;
  unapproved model SHA256
  `b1aabf15c0f6d7ff8334769d076a505f2cf33848e849232f513499f70e4099c5`.
- In-sample: only **5/896** training-stage actions changed.
  This descriptive training count is not winrate validation.

## 2. Frozen independent random 127k action benchmark

No outcome labels generated before this census.
256 other physical game IDs 127200..127455 ×3 actual
early London stages =768 independent-stage decision states.

- **0/768 action changes** under frozen v37 vs v27.
- **0/256 complete London final physical hand or library changes**
  under v37 vs v33b, verified by full action trace.
- Strict deterministic stable-effect beam160 games must therefore
  have identical by-T1, by-T2, by-T3 outcomes for these exact
  256 already-seeded physical games, without replaying
  expensive identical gameplay.
- This is a **cohort-specific exact equality**.
  It is NOT a population-generalization CI and
  does not prove v37 equals v33b for every possible deal.
- Zero coverage fails the precommitted >=12 independent
  early-stage changes and >=5 reached full-path changes
  gates. No 128k prospective full-game replay.
- No new action training/threshold tuning performed on 127k.

Independent holdout signed-action gate attribution:
- **736** early hands: direct model's T2 sign
  agrees with frozen v27 action.
- **8**: opposite median A2 direction, but T2
  prediction quartiles/margin lack stability.
- **24**: T2 quartile/action gap supports reversing
  original KEEP→MULL, but separate T3 safeguard blocks it.
- **0** actually change.

This differs from v36, where almost all states failed
to even favor opposite T2 actions.

## 3. Posthoc T3-blocked reachability and physically measured tradeoff

The 24 T3-blocked states were identified **after inspecting
the 127k frozen candidate predictions**. This diagnostic
is explicitly POSTHOC, not independent population validation.
Among those 24, a hypothetical T2-only action rule would
change the **actual complete London final physical state in
16/256** of the original cohort's games, with the other
eight disagreements counterfactual/unreached.

All 24 model conflicts have original v27 KEEP,
while direct v37 favors MULL by T2.
Their mean **model-predicted** MULL−KEEP:
- byT2 **+12.125 percentage points**;
- byT3 **−18.999 percentage points**.

Independently sampled **new posthoc physical outcomes**:
- 24 hand states×32 NEW independent hidden92 true
  beam160 forced KEEP outcomes = **768**.
- 9 required shared seat-stage C cells×128 NEW full99
  future MULL outcomes = **1,152**.
- Total **1,920 additional strict real physical rollouts**.
  The 20 physical shards completed successfully; pooling
  was corrected for a test-script argument-order typo
  and syntax typo **without rerunning any gameplay**.
- 24 selected states arise from 23 independent outer
  physical game IDs; physical-group, within-KEEP-future
  and shared-C future two-source bootstrap.

| Physical contrast: choose MULL instead of frozen KEEP | Mean (percentage points) | Two-source grouped 95% bootstrap |
|---|---:|---:|
| By T1 | +3.223 | [+1.732,+4.883] |
| **By T2** | **+15.592** | **[+7.779,+22.113]** |
| By T3 | **−18.945** | **[−28.363,−8.094]** |

The direct action model was **directionally informative**:
it correctly predicted selected T2 gain and T3 sacrifice
to within a few percentage points on average.
But these are *selected hands* under frozen common
downstream continuation, NOT population-average
or complete-game causal benefits.

## 4. A previously hidden OBJECTIVE mismatch

Do NOT use the ambiguous label "T3" without distinguishing
cumulative byT3 from **exactly on turn3**. They imply
different marginal rewards for T2 success.

Let p₂=P(deploy by T2), p₃=P(deploy by T3),
e₃=p₃−p₂=P(deploy exactly on T3). Then:

- **Historical v5-style weighted score**
  `U_exact = p₂ + 0.5 e₃ = 0.5(p₂+p₃)`.
  For these 24 physically selected hands, MULL−KEEP
  = **−1.676pp**, joint-bootstrap 95%
  **[−8.708,+5.225]pp**. No clear gain.
- **Cumulative assertive score**
  `U_cum = p₂ + 0.5 p₃`.
  MULL−KEEP = **+6.120pp**, joint-bootstrap
  95% **[−4.232,+16.270]pp**.
  Still uncertain and NOT an independent prospective gain.
  This utility assigns 1.5 total units to a T1/T2
  success and 0.5 to a T3-only success.
- **T2-only target** favors MULL by +15.592pp,
  but accepts the substantial byT3 sacrifice.
- These rewards are not interchangeable.
  Even with correct card physics and predictor
  calibration, models optimize different decisions
  if an objective uses cumulative p₃ vs exact e₃.

The hard T3 <=4pp safeguard in v37 prevented any
actual policy changes even where T2 regret signal
was real. Removing it based on these 127k
posthoc data would **not** restore independent
validation. A future candidate must commit
to its scalar reward BEFORE new holdout outcomes.

## 5. Other method pitfalls and runtime

- V13 imitation proxy: in the high-v27-confidence
  sample, v27 said KEEP in 55/64 states;
  proxy said KEEP in only 9/64. Mean
  proxy score distance from cutoff was
  ~0.087. High-v27 confidence does
  NOT mean the teacher proxy is also confident
  or correct. This is informative sampling,
  not teacher correctness.
- Direct A regression is not magically independent
  of QKEEP regression: for a fixed seat×stage,
  C is a constant under the frozen continuation.
  A flexible estimator of A can effectively
  learn the same information as a QKEEP estimator
  minus C. The real advances here were
  source selection, physical labels, explicit C
  lottery uncertainty, and a distinguishable
  action target; **not a theorem that direct
  regression must outperform a KEEP forest**.
- Two-stage London 7/7 must remain distinct;
  full99 restored on MULL; no inferred
  physical-equivalence collapse of game states.
- 127k one-step Q(MULL) uses frozen v27
  future and v33b bottom, not a Bellman
  value recalculated for a new policy.
- Actual goldfish deployment under beam160
  is NOT multiplayer cEDH victory probability,
  nor complete rules-engine certification.

Actual chooser-only CPU on same four new
physical 128900..128903 game IDs, excluding
beam160 gameplay:
- v5: **193.579 s**
- v27: **0.0904 s**
- v33b: **0.1479 s**
- v37: **0.3340 s**
- v5/v37 chooser speed ratio **~579.7×**.
  Tiny N4 measurement not a population runtime
  nor an end-to-end gameplay speedup.

## 6. Next experiment should be OBJECTIVE-FIRST and decision-sensitive

Before a v38 experiment, specify a
single scalar *deployment speed utility*:
`U_exact=p₂+w*e₃` or
`U_cum=p₂+w*p₃`, with a clear
predeclared weight w and corresponding
interpretation. For example a T2-assertive
weight on exact T3 may differ meaningfully
from the inherited v5 weight 0.5.
This is a strategic preference, not a
model calibration constant to tune using 127k.

Then **train signed physical advantage of that
one scalar utility DIRECTLY**, or compute
the same scalar from paired physical T2 and
T3 outcomes with consistent uncertainty.
Use regret-weighted decision-error loss
or an explicitly preference-optimized policy;
don't repeat a pair of marginal
regressors with an arbitrarily conflicting
hard T3 gate. Reserve NEW independent
validation 129k+, not the consumed 127k.
Only if positive and reached on new hands,
run disjoint full-game 130k+ prospective
comparisons vs frozen v5/v27/v33b.

**Result: v37 research work complete and archived,
no model promoted, no 128k prospective full-game
benchmark conducted.** Its main advance was
identifying a verified multiobjective
T2-versus-T3 tradeoff obscured by policy
safeguards and by exact-vs-cumulative
T3 terminology.
