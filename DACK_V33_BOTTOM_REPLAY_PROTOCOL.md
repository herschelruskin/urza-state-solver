# DACK v33 — preregistered same-stage bottom counterfactual

Isolated branch `dack-v33-attribution-first-20261101`. This is the
second bounded investigation after the zero-beam attribution census.
**Research only; do not promote any bottom-selection model.**

## Fixed selection rule, before inspecting new counterfactual outcomes

Read immutable 110k N256 matched v5/v27 results.
Include ALL physical games with the exact same terminal London stage
but different final kept-hand multiset between v5 and v27.
The archival census found **56** such games. Do not select on the
original 110k T1/T2/T3 outcome, whether v5 was faster, or any other
observed deployment result.

Hold seat, London stage, original visible seven, and the multiset
of 92 unseen physical cards fixed. Use v5 and v27 actual previously
selected bottom cards (no new v5 lookahead). For each:
* 8 new physical unknown-92 reshuffles, split `calibration`.
* Another independent 8 reshuffles, split `untouched_validation`.
* Both arms use the same shuffled unknown order and seed for chance,
  but each gets the cards in its own actual bottom.
* Strict, unchanged v5 stable-dice/physical beam160 gameplay to turn 3.
* Independently reset caches and install the exact same deck for every
  arm. Never access the 110k realized unknown draw order to select.
* No model fitting, feature selection, policy threshold changes or
  outcome-based selection of which groups to keep.
* Eight parallel GitHub shards, seven physical groups per shard.
  Exactly `56 × 2 arms × 8 futures × 2 splits = 1792`
  new beam160 outcomes. This is bounded, not a full N256 v5 rerun.

## Estimand and reporting

Difference in conditional deployment probability under v5 bottoms
minus v27 bottoms **on the policy-discordant same-stage population**;
not the global effect of replacing the bottom selector in every game.
Report T1/T2/T3 and physical-group bootstrap confidence intervals
separately in the two untouched seed splits and with pooled summaries.

Reevaluate initial 8/56 T2 wins and 0 losses without treating the single
realized 110k deployment of each policy as a value oracle.
Favorable original realized draws alone cannot establish bottom value.
Paired chance coupling can still be imperfect if game paths consume
or hash randomness differently; do not modify the stochastic engine
or assert exact action-independent event coupling.

Predeclare no go/no-go based on a single arbitrary threshold: a
positive, reproducible conditional T2 difference supports investigating
structural bottom-ranking features; overlapping-zero estimates or
split disagreement mean no demonstrated T2 advantage. Regardless,
no promotion without a separate fresh **full-game prospective** cohort
that compares a deployable policy.

Test files:
`dack_simulator/validation/v33_same_stage_bottom_replay.py`
and `dack_simulator/validation/v33_pool_same_stage_bottom.py`.
Output: `benchmark_results/v33_bottom_replay_N56_x16.json`.
No change to existing engine or reference policies.
