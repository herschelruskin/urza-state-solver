# DACK v40 — recovered v38/v39 and next-action research plan

**Branch:** `dack-v40-true-disagreement-reassessment-20261101` (fork of v39; isolated research, NOT promoted).
**Status:** design and correctness audit only. **No v40 model fitted, no v40 physical gameplay, no new holdout opened.**
**Date:** 2026-11-01.

## Evidence recovered from the interrupted v38 line

- v37: direct signed physical KEEP-minus-MULL T2/T3 forests trained on 384 independent physical groups, 12,288 hidden92 KEEP futures and 3,072 shared complete99 later-London MULL futures. Selected 128 additional groups using the inexpensive **v13 proxy disagreement**, NOT an actual v5 action disagreement. On new 127k N256, 0/768 stage changes. Selected 24 T3-vetoed cases physically supported T2 versus T3 tension but did not validate population improvement.
- v38: frozen v37 members combined *within each same ensemble member* for `U_cum = P(byT2)+0.5 P(byT3)`. On independent 129k N512, 3/1536 stage changes, 2/512 actually reached altered complete physical London paths. Failed its predeclared >=12 stage / >=8 reached gate. No 129k physical outcomes were generated.
- v39: T2 first, up to 25 percentage points *predicted* per-action T3 loss, on independent 131k N1024. 47/3072 early-stage changes, 30/1024 reached changed final hands/libraries. True 1504 KEEP + 1408 shared MULL beam160 rollouts. Mean population *one-step stage-value* delta, percentage points: byT1 +0.0504 [0.0239,0.0821], byT2 +0.1035 [-0.0351,0.2396], byT3 -0.2607 [-0.3927,-0.1437]. Posthoc read-only `U_cum` -0.02683 [-0.19557,0.13301]; `U_exact=P(byT2)+0.5 P(exactly T3)` -0.07858 [-0.18082,0.01755]. FAILED primary T2 positive-lower-CI gate; no 133k whole-game test and no promotion.
- v34c **distinct prior evidence:** on 100 actual v5-v27 first-stage disagreements from 115k (61 v27 kept first, 39 v5 kept first), physically measured v5-action advantage under the same v33b bottom / frozen v27 downstream: byT2 +10.59 pp [6.21,15.25] **conditional on the selected 100**. This was not a random-population policy gain and was not evidence that v5 action is always correct.

## Working diagnosis (hypotheses, NOT yet established causal explanations)

1. v37's v13 proxy-selected training distribution may miss the physically consequential real v5-v27 disagreements; testing this requires *fresh actual* v5 action labels, not reusing previously analyzed 115k/127k/129k/131k cases as new holdout.
2. v37's 75 features and random forests may confound T2 tactical fast-line capability with T3 consistency of otherwise keepable hands. v39's mixed effects suggest a utility Pareto frontier; classifier/objective mismatch can be separated from genuine model ranking error.
3. One-step action advantages assume future frozen v27 policy. Changed-policy trajectories are not Bellman-consistent; only fresh end-to-end prospective goldfish evaluation can substantiate win rates.
4. A **teacher-information audit is mandatory:** ensure v5 disagreement selection uses only the seen 7, remaining card multiset, seat, stage and fresh independent simulation chance; never selection based on a realized hidden 92-card library or future London deal. If unable to establish this, stop and redesign source selection.
5. GitHub's frozen results are statistically informative but not a rules-complete multiplayer cEDH win estimate. Do not merge game states using approximate functional equivalence.

## v40 implementation gate A — audit before new expensive work

- Verify v5 and v27 are compared on the SAME physical first/second 7-card London hands, stage IDs, seat, and remaining-known deck composition.
- Inspect actual v5 teacher's unknown-card treatment, seeding, rollout action search, legal bottom definition and per-hand CPU; document whether teacher is information-faithful. **Do not assume v5 teacher choices are ground truth.**
- Audit v34c action direction and physically confirmed early-stage conditional advantage, v37 feature and proxy implementation, and frozen v39 K / shared-C pooling.
- Run cheap, read-only self-checks of archived v38 and v39 counts and cumulative/EXACT T3 algebra; no tuning on consumed cohorts.
- No v40 GitHub Actions gameplay workflow until gate A findings and executable code tests are committed.

## Candidate v40 experiment, to lock before collecting any fresh outcomes

**Keep a single fixed project objective:** primary P(deploy by T2). Always report byT1, byT3, `U_exact=PbyT2+0.5 PexactT3 = 0.5(PbyT2+PbyT3)`, and `U_cum=PbyT2+.5PbyT3`. A measured T3 reduction is not silently offset by the earlier T2 target.

**Training/source sample, independent physical 99-slot groups:**
- Proposed fresh IDs 134000..134383 (384): actual v5 and v27 paired first-action London decisions, for candidate *disagreement-enriched* selection. Record every seen early stage (0/1/2), but select only each game's earliest actually encountered v5-v27 discordance, avoiding duplicate physical groups. Preserve both action directions and stratify on stage and v27-margin; selection uses decisions, **never observed physical win turns**. If the v5 information-boundary audit fails, do not run this stratum.
- Proposed fresh IDs 134384..134767 (384): unbiased random complete physical groups, ALL actual stage0/1/2 sevens; stratify by stage, keep/mull, seat and line capability for calibration. These are a separate source stratum; do not claim the enriched group represents population frequency.
- Physically label actual KEEP under immutable v33b legal bottoms and multiple fresh independent shuffled unknown92 futures, and MULL under independently reassembled full99 later-London frozen v27/v33b futures. C(seat,stage) is shared, **never treat repeated futures as independent physical hands**. Predeclare run counts, seed domains, game and shard manifest, exact hashes, and fitting weights *before* any game label.
- Consider a small interpretable / strongly regularized signed T2 action-regret classifier or regressor with separate T3 predictions. Use only information-legal capability indicators, actual stage/seat, frozen v27 margin, and possibly a v13 score **as an observed feature only if validated**. Actual v5 action is for **training stratum membership and diagnostics**, NOT a deployment feature, target label or automatic instruction.
- Cross-fit groupwise by original physical ID; enriched-conditional results must not be represented as random-population success. Paired K/C T2/T3 outcomes share one underlying win turn and should use that correlation.
- The chosen single trained policy, thresholds, model hashes, coverage and safety rules must be frozen **before** any new holdout labels.

**Independent randomized policy validation, only after training is frozen:**
- Reserve fresh IDs 135000..136023 (1024 physical groups, 3072 unconditional early-stage actions) as a candidate holdout; no training, hyperparameter selection, or calibrations there. Initial outcome-blind full-path action census followed only if coverage passes by strict shared-C / independent-K physical counterfactuals.
- Suggested advance gate (final numbers must be formally frozen before running): at least 24 of 3072 early-stage action changes and >=12 of 1024 reached changed London paths; positive two-source grouped-bootstrap lower 95% endpoint for population byT2 one-step gain; no convincing T1 loss; clinically meaningful byT3 harm bounded and both utilities transparently reported. Explicitly choose and precommit T3 noninferiority margin based on desired strategy, NOT 131k data.
- If and only if gate passes, reserve fresh 137000..137511 for matched identical-seed complete physical v33b-v40 gameplay and evaluate end-to-end byT1/byT2/byT3 and chooser time. Compare v5 only if warranted by cost. No `same-action` pruning at changed downstream policy paths.
- Never relabel already-inspected 115k, 117k, 121k, 124k, 127k, 129k or 131k as an untouched validation set.

## Operational state

Preserve original v5, v27, v33b, v37, v38, v39 branches. Nothing on this v40 research branch is production-approved. Current artifact is a **reassessment/design checkpoint** rather than a claim that v40 research has already run.
