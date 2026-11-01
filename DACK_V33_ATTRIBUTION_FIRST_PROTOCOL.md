# DACK v33 — Attribution first, no model fitting

Branch: `dack-v33-attribution-first-20261101` (isolated from v32).
**Research only, no policy promotion.**

## Motivating result

v32 slightly improved continuation Brier but worsened the 110k N256
prospective deployment rate, demonstrating that improving Q(MULL)
prediction is not automatically action-value improvement.

v27 already uses a backward Bellman-style, shared continuation table
derived from its own Q(KEEP) predictions on independent stage sevens.
The v32 real-world continuation table is a useful calibration audit,
but does not solve noisy or misspecified Q(KEEP), and is not a fixed point
under the changed policy.

## Precommitted bounded experiment 0: zero additional beam calls

Before choosing another model or requesting GPU/Actions simulation budget,
read the archived full-game N256, independent 99k bottom intervention, and
103k forced keep/mull intervention.

* Source A: 64 archived 110k shards, three matched policies.
  Partition paired v5-v27 and v5-v32 T1/T2/T3 differences into:
  same exact final kept-hand multiset; same London stage but different
  kept cards; different London stage (keep/bottom confounded).
  Report N and paired bootstrap confidence intervals by game ID.
  **This is descriptive, NOT causal decomposition.**
* Source B: v28 controlled 16-future comparisons of v5 bottom and
  v14 bottom on the same 50 v5-selected kept-hand states. This is
  action-counterfactual evidence conditional on v5 hand selection;
  it does not measure global full-game bottom-policy gains.
* Source C: untouched v31 103k forced KEEP-versus-MULL audit
  (only 16 physical groups, stages 0/1/3/5, six futures per arm).
  Report the pre-existing held-out outcomes without inventing
  stage 2/4/6/7 direct labels.
* Verify 110k result counts and archived hashes. Never train on 110k.
* Collect no new beam160 games in this experiment. Make no gameplay
  or bottoming rule modifications.

Executable: `python dack_simulator/validation/v33_attribution_first_readonly.py`.
Output: `benchmark_results/v33_attribution_first_readonly.json`.
A branch-specific, push-scoped GitHub Action runs selftests and the audit,
then archives its results. It cannot trigger v32 workflow.

## Decision rule for a subsequent experiment

If the v5-v14 controlled T2 bottoming advantage remains small/noisy, and
the 110k contrast is heavily concentrated in different London keep
stages, prioritize a **direct-policy regret audit on sampled early-stage
boundary hands** with shared Q(MULL), independent future draws, and
preserved bottom policy, not a fresh random forest.

If the controlled T3 bottoming advantage is consistently larger than
T2, isolate bottom selection to recover T3 first. Do not interpret
exact card disagreement as deployment regret.

An eventual next *causal factorial* should cross keep-stage policies
(v5/v27) with bottom selectors (v5/v14) on the SAME physical hands and
fresh matched gameplay futures, respecting candidate rules, no hidden
order access, and action-independent chance coupling. Teacher choices
at unseen later stages require fresh v5 calls, not guessed bottoms.

All future policy candidates require independent training, validation,
and prospective full games, paired T1/T2/T3 and actual runtime.

## Known structural concerns to revisit

* v27's 2048 stage observations have only four Bernoulli rollouts per
  state; target labels are extremely noisy near the action boundary.
  The 350+ features contain card-identity indicators plus redundant
  group-level summaries; extra tree depth is not automatically helpful.
* One-step corrected Q(MULL) under v27 is not Bellman-consistent under
  changed later policy; changes in continuation values alone are not
  guaranteed to improve an approximate policy.
* v5’s assertive keep heuristics and blended T3 reward do not optimize
  the identical objective as v27 T2-only values. This objective mismatch
  can affect the early-stage distribution.
* 99k v28 was selected by v5 keeps. The T2 causal bottom difference
  is not a population-wide advantage. State-keyed random artifacts and
  beam search require separate reproducibility audits.
* Goldfish Dack deployment never establishes interactive cEDH winrate.

No deployment policy, engine module, existing branch, or model is changed.

## 2026-11-01 correction to initial v33 report

The first read-only v33 run incorrectly equated identical `keep_n` with the
same London **stage**. London stages 0 and 1 both have `keep_n=7`, so
this comparison is invalid. The initial 56-case `same_stage` tally and
its +8/-0 T2 outcome are **superseded, not verified** until recalculated.
The correction compares the actual `history[-1]["stage"]` values, and the
unit self-test separately covers repeated 7-card London stages. The next
counterfactual replay must select only actual-index-matched groups.
This is a v33 attribution script error, not a proven engine defect.
