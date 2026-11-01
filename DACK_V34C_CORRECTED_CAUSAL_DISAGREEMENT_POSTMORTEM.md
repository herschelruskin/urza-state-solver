# DACK v34c corrected postmortem — actual early keep/mull disagreement value

**Completed, research only. No model promotion, no engine changes.**
Branch `dack-v34c-keep-disagreement-20261101`.
Original GitHub Actions physical run `41275420492`;
corrected pooled report rerun `41275917293` (SUCCESS).

## Scientific issue: was a v5-v27 different-stage outcome gap causal?

The earlier v33b 115k paired N256 cohort observed v5 ahead of v27
by +26 T2 deployments. Of those 26 net wins, +19 were in the
100 games whose policies kept at different ACTUAL London stages.
This descriptive grouping could **not** establish whether one
policy's KEEP decision was superior: v5 and v27 also differ in
bottom selection and subsequent mulligan strategy.

v34 checked unconditional physical stage hands and shared
continuations under fixed v33b. A global stage-bias/continuation
threshold correction failed untouched 117k conditional validation
(-0.112pp T2). That model was REJECTED and not used here.
The v34 score discrimination audit found v27 generally recognized
strong versus weak keep hands, but could not test whether its
specific high-leverage disagreements with v5 were erroneous.

## Frozen causal intervention

Select all **100/256** original 115k games in which v5 and
frozen v27 kept at DIFFERENT ACTUAL stage indices. No original
115k win turns enter selection. Let s be the EARLIEST
stage where one policy kept and the other mulled; both saw
the same actual seven/seat. Stage indices 0 and 1 remain
distinct despite both having seven cards.

- 61 games: v27 first kept while v5 rejected the seven.
- 39 games: v5 first kept while v27 rejected the seven.
- Stage counts at first divergence: {0:17,1:24,2:20,3:18,
  4:7,5:10,6:4}.

Forced KEEP: frozen **v33b** bottom selection, then 16 independently
shuffled real unknown-92 futures in a `calibration` split and 16
more in independent `replication`; strict stable-dice gameplay
beam160, actual legal bottom appended.

Forced MULL: EXACT frozen v27 future keep choices and v33b bottom
policy, all 99 cards physically restored and later stages reshuffled.
Because full reshuffle makes Qmull independent of rejected hand,
reuse the 28-seat-stage source cells of v34 REAL outcomes:
64 independent `train` and 32 independent `validation` futures
per cell. No new Qmull beams; they are separate physical lotteries
from the selected 115k cohort. The 64 C futures match calibration,
32 C futures match replication. Pooled 96 C futures and 32 KEEP
futures per selected group.

Total **3200 new true beam160 KEEP games** across eight CI shards.
No new v5 teacher lookahead or v27 engine modifications.
Bootstrap independently resamples outer original physical groups,
within-hand KEEP futures and the shared seat-stage C lotteries.
This measures the conditional Q(KEEP)-Q(MULL) under one common
downstream policy, NOT whole original v5 versus v27 policy winrate.

## A crucial pooling bug caught and repaired

First v34c pooled script incorrectly declared `y(t,turn)`
while callers passed `y(turn,t)`, reversing the inequality
and producing physically impossible decreasing cumulative
T3<T2 rates. That pooled report is **INVALID** and must NEVER
be quoted. All original 3200 physical gameplay shards were
correct. The new pool fixed the predicate to `y(turn,t)`
and added explicit cumulative T1 <= T2 <= T3 assertions
at every group/split. A new recovery-only workflow
`41275917293` re-pooled the original eight shards, and
**overwrote the old invalid report**. All results below use
ONLY that corrected report, with
`cumulative_turn_monotonicity_asserted=true`.

## Corrected action-value result

The primary outcome is choosing **v5's KEEP or MULL action
instead of v27's** at the first disagreement under fixed
v33b future decisions. Signed advantage is
`+ (Qkeep-Qmull)` if v5 kept first and
`-(Qkeep-Qmull)` if v27 kept first.

| Physical future split | T1 advantage | **T2 advantage** | T3 advantage |
|---|---:|---:|---:|
| 16 KEEP / 64 C calibration | +0.78pp | **+10.52pp** | +3.69pp |
| 16 KEEP / 32 C independent replication | +1.97pp | **+10.06pp** | +4.28pp |
| All 32 KEEP / 96 C | +1.25pp | **+10.59pp** | +3.69pp |

Primary pooled T2 two-source bootstrap 95% CI
**[+6.21,+15.25] percentage points**; calibration
[+5.61,+15.36], replication [+4.88,+15.31].
Pooled T3 95% CI **[-2.35,+9.59]pp**:
no proven T3 improvement on this diagnostic, but no
convincing systematic harm. T1 +1.25pp,
bootstrap CI [+0.21,+2.39]pp.

By direction at first disagreement:
- 61 **v27-keeps-first**: **v5's MULL superior by +13.06pp
  T2** under v33b continuation.
- 39 **v5-keeps-first**: **v5's KEEP superior by +6.73pp
  T2**.
- Both kinds of error occur; simply instructing every
  early hand to mull more would be wrong.

By earliest divergence stage, the conditional v5
action advantage T2:
0: +21.14pp (n17); 1: +15.80pp (n24);
2: +16.20pp (n20); 3: +0.75pp (n18);
4: -3.87pp (n7); 5: +1.15pp (n10);
6: -0.26pp (n4). This supports targeting
**decision-boundary quality specifically at stages 0–2**,
not uniform changes to all London thresholds.

## Verdict

A clear, replicating conditional causal T2 advantage for
the earlier-stage v5 ACTION at the 100 selected actual
disagreements, under the common v33b future policy.
Therefore the old 115k descriptive stage-gap association
has now been supported by a separate physical
forced-action test. However, +10.59pp is **conditional on
selection**, not a global T2 winrate gain, and v5
and v33b still select different bottoms/future paths.

v27's average score discrimination on all random stage
hands can coexist with important systematic errors on
its hand-decision disagreements with v5. Global
stage-intercept correction was too coarse: it changed
only one heldout decision and worsened T2.

Do NOT promote any new keep policy yet.

## Next bounded research candidate

Train a compact, strong-regularization, real-value
**action-advantage ranking / correction model** rather
than v5 keep-label imitation or global C threshold tweaks.
Retain unmodified 27-feature visible capability descriptors
(mana, white sources, Mox fuel, tutoring, LED, fast mana),
seat, stage, and frozen v27 predicted Qkeep-vs-C margin.
Target TRUE T2 advantage under fixed v33b future from
physical paired/independent action samples. Upweight
early stages 0–2 and real disagreement states but
weight independent physical game ID groups to prevent
32 future rolls per hand from masquerading as 32 hands.

Candidate source training data 116k (real unbiased
all-stage KEEP) and v34c selected 115k direct outcomes.
The 117k validation cohort has already been consumed:
NEVER tune against it again. Reserve a completely new
independent 121k physical conditional action-regret
cohort for validation; only then an untouched 122k
N256 full-game paired prospective benchmark if warranted.
If the new model's conditional T2 benefit is not robust
or T1/T3 suffer, do not promote. Maintain no-beam
mulligan runtime, strict actual beam160 gameplay,
full 99 restored on mull, correct stage0/1, and no
functional-fingerprint game-state collapse.

This is goldfish Dack deployment probability; it
is not multiplayer cEDH win probability.
