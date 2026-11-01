# DACK v33 — Attribution-first postmortem (2026-11-01)

**Research experiment completed: NO deployment policy promoted.**

Branch: `dack-v33-attribution-first-20261101`, based on frozen v32.
Protocol: `DACK_V33_ATTRIBUTION_FIRST_PROTOCOL.md` and
`DACK_V33_BOTTOM_REPLAY_PROTOCOL.md`.

## 1. Read-only attribution audit — SUCCESS

GitHub Actions run 41272454144, archive:
`benchmark_results/v33_attribution_first_readonly.json`.

Matched 110k, N=256 v5 vs v27 prospective games:
- Same exact final hand: 93. Identical T1/T2/T3 outcomes.
- Same **recorded London stage**, different final hand: 53.
  Observed v5-v27 T2 +6 net (6 gains, 0 losses), T3 -1 net.
- Different recorded London stage: 110.
  Observed v5-v27 T2 +1 net (17 gains, 16 losses),
  T3 +15 net (26 gains, 11 losses).
- Overall v5-v27: T1 19 vs 18; T2 131 vs 124
  (+2.734375pp, bootstrap 95% CI [-1.953125,+7.421875]);
  T3 212 vs 198 (+5.46875pp,
  bootstrap 95% CI [+0.390625,+10.546875]).

**Correction logged:** First v33 read-only script erroneously used
`keep_n` to indicate London stage. Stages 0 and 1 are BOTH seven-card
London stages. Initial 56 "same-stage" records were invalid. Replaced
comparison with `history[-1]["stage"]`; 53 correct same-stage
disagreements; tests/Actions rerun, all pass. Old 56-case classification
and 8-game apparent T2 gain MUST NOT be cited as true-stage result.
This was a v33 diagnostic issue, not a demonstrated gameplay-engine bug.

These are **descriptive observational partitions**, not causal attribution.

## 2. Conditional fresh-future bottom intervention — SUCCESS

GitHub Actions run 41272460336 (eight matrix shards + pooling succeeded).
Frozen archived choices for all 53 true same-stage v5/v27 disagreements,
selected WITHOUT looking at their realized T2/T3 outcome.
Same seat, visible seven, and 92 unknown physical-card inventory.
Each arm played the same 8 new future shuffles in a calibration split
and another independent 8 shuffles in an untouched validation split.
No fitting, no bottom-change inference, no new v5 mulligan beam calls.
Strict physical-99, unchanged stable dice, actual beam160 to T3.

Total: 53 groups x 2 arms x 16 fresh futures = **1696**
beam160 games. Physical-group paired bootstrap, not rollout bootstrap.
Output:
`benchmark_results/v33_bottom_replay_actual_stage_x16.json`.
Eight raw shards:
`benchmark_results/v33_bottom_replay_shards/v33_bottom_0.json.gz`
through `v33_bottom_7.json.gz`.

Difference in CONDITIONAL expected deployment: v5 chosen bottoms minus
frozen v27/v14 chosen bottoms **on this selected disagreement set**:

| Deadline | First eight | Other eight | Both (16/arm/hand) | Group bootstrap 95% CI (pooled) |
|---|---:|---:|---:|---|
| T1 | +0.472pp | +0.236pp | +0.354pp | 0.000 to +0.825pp |
| T2 | +8.019pp | +6.368pp | **+7.193pp** | **+2.005 to +13.561pp** |
| T3 | +5.425pp | +5.660pp | **+5.542pp** | **+0.590 to +11.321pp** |

By actual London stage among selected hand disagreements:
stage 0=0, stage 1=0, stage 2=16, stage 3=16, stage 4=13,
stage 5=6, stage 6=2, stage 7=0.

In the pooled T2 comparison, 12 groups favored v5 bottoming,
six favored v27 bottoming, and 35 had identical observed T2 rates.
Pooled T3: 14 positive, eight negative, 31 tied.

Interpretation:
- Repeated fresh futures support REAL bottom-selection value within
  cases where policies disagree; an observational 110k +6/53 T2 signal
  is not explained entirely by one favorable observed physical draw.
- This does **NOT** establish a 7.19pp overall improvement, nor prove
  that a compact deployable bottom selection can reproduce v5.
- The two future splits are independent **within the same 53 selected
  decision groups**, not two independent decision populations.
- Some chance effects can remain imperfectly coupled across different
  action paths despite common unknown order and seed.
- The v28 v5-selected-bottom audit (different conditioning)
  had T2 +1.375pp, CI -2.0 to +5.875pp on N50 and T3 +7.875pp;
  do not conflate those estimates.
- No prospective fresh full-game v33 policy was implemented or tested.
  The old 110k v5-v32 ~64x gameplay speed ratio remains historical,
  not an achieved v33 speedup.

## 3. Architecture and statistical reassessment

The v27 keep regression is already trained for all eight stages and has
347 features, 2048 stage states, and only FOUR Bernoulli beam160 rollouts
per state (8192 training outcomes). Its 192-tree forest predicting
absolute T2 keep probability may be high-variance near action boundaries.
But this remains a **hypothesized** bottleneck, not causal evidence.
Increasing forest size is not the first choice.

The v27 DP already does a backward Bellman-style expected-maximum
recursion over independent 92k physical stage sevens and learned Q(KEEP)
for frozen downstream v14 bottoming. v32 instead samples real shared
Q(MULL) under frozen v27 and makes different later keep decisions.
Its continuation-calibration gain was tiny and was not associated
with improved N256 end-to-end T2. The mathematical reset-to-99 sharing
is sound; value mismatch remains.

Strongest directly tested remaining bottleneck is **bottom choice on
same-stage policy disagreements**, with a reproducible conditional T2
difference. The largest descriptive T3 gap occurs in different-stage
groups, also consistent with the fact v27 trains strictly on T2 while
v5 uses assertive/mixed-T3 criteria. Neither observation proves full-game
causal contribution.

## 4. Next bounded experiment (not implemented)

Prioritize a lean, **regret-oriented bottom selector**, not a generic
wider random forest:

1. Retain v27 keep-depth decisions and its shared continuation table as
   a frozen baseline, and preserve actual 99-slot shuffles and gameplay.
2. For selected same-stage hands where candidate bottoms differ in
   actual ramp/combo/tutor capability (rather than mere card identity),
   compute true matched-future T2/T3 regrets of legal v14/v5/candidate
   actions. Identify cases with `>0` reproducible regret.
3. Compare a **small structured candidate rule** (and optionally
   low-dimensional pairwise ranker) to the frozen v14 bottom selection
   on independent physical states. Preserve Chrome Mox imprint,
   Mox Opal metalcraft, Mox Diamond, Gemstone Caverns, tutor access,
   and actual combo integrity; do not collapse runtime game states.
4. If improving bottoming also changes Q(KEEP) labels, recalibrate
   keep-value/continuation for the changed bottom policy; do not mix
   incompatible conditional value functions.
5. Preserve independent training and validation game IDs, group-level
   uncertainty, and require a **NEW prospective 256+ physical-game**
   paired v5/v27/new-policy test with T1/T2/T3 and actual runtime.
6. T3 stage-related regret is a separate later experiment and must
   preserve the hierarchy of T2 primary, T1 and T3 safeguards.

No existing policy, model, reference, or gameplay engine was changed.
