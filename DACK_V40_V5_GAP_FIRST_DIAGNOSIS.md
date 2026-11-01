# DACK v40 — target the actual v5 win-rate gap, not another marginal v39 retune

**2026-11-01 | research-only diagnosis | NO candidate promotion or new v40 physics.**

## Recovered primary prospective benchmark (115000–115255)

Source: `benchmark_results/v33b_prospective_115k_N256.json` (the immutable N256 three-policy physical benchmark).

| Policy | by T1 | by T2 | by T3 | T2 / 256 |
|---|---:|---:|---:|---:|
| Original v5 reference | 7 | 132 | 214 | 51.5625% |
| Frozen v27 keep, v14 bottom | 7 | 106 | 189 | 41.40625% |
| Frozen v27 keep, v33b bottom | 8 | 111 | 196 | 43.359375% |

Paired N256: v5 outperforms v27 by 10.15625 percentage points at T2; v5 outperforms v33b by 8.203125 percentage points. v33b changed the bottom in 52/256 games and recovered only five T2 deployments. This is compelling experimental evidence of a deficit but NOT a reliable estimate of long-run population policy effect at subpercentage-point precision. Also by T3 v5 outperforms v33b by 7.03125pp: recovering T2 by sacrificing T3 is not automatically v5 parity.

The independent, corrected **v34c forced-action** experiment addresses 100/256 cases where original v5 and v27 first selected different *actual retained London stages*. Under a common v33b bottom and frozen v27 continuation, following v5's first different KEEP/MULL decision yielded +10.59375pp T2 (two-source 95% CI +6.2083,+15.25pp) **conditional on the 100 selected games**, NOT unconditional global policy gain:
- 61 v27-keeps-first: following v5 MULL +13.0635pp T2.
- 39 v5-keeps-first: following v5 KEEP +6.7308pp T2.
- The largest stage-specific conditional differences are stages 0/1/2; simply raising/lowering every keep threshold cannot solve errors in both directions.
- Teacher decisions are not ground-truth optimal; the result is empirical support for focusing sampling on actual teacher disagreements.

## Why direct-regret v37/v38/v39 did not close this gap

**Low effective sample size in informative action regions.** v37 trained on only 384 independent physical outer groups / 896 stage states, with 256 random groups times three stages (8 KEEP futures per state) and 128 *v13-proxy*, not genuine v5, discordant groups (48 KEEP futures each). 12,288 K rollouts are NOT 12,288 independent hands. The 75-dimensional forest must learn rare card interactions and a signed K−C boundary from noisy hand means. The v39 holdout changed 47/3072 stages and reached 30/1024 actual end-game London paths; its population one-step T2 gain +0.1035pp had CI crossing zero, with a significant −0.2607pp by T3. This is not a credible v5 gap closure.

**A joint keep/bottom inconsistency.** The v27 Qkeep and v27 DP are computed for the v14-selected candidate, then the v33b wrapper may *replace that bottom only after the KEEP decision*. The policy therefore values one retained hand and deploys another in some games. The v33b switch improved performance but this score/selected-hand mismatch is a plausible source of missed or mis-ranked marginal keep decisions; it is NOT yet established how much it causes.

**Teacher imitation alone previously underperformed.** The frozen v14 teacher study trained on 144 genuine v5 natural game groups / 538 visited stage records. On 40 teacher-visited validation groups, the bottom-choice top-1 agreement was only ~64%, the SAME as always choosing the first structural finalist. Joint keep+bottom accuracy remained ~58%. v15 student-state DAgger improved keep agreement but not bottom ranking. This makes another naive imitation-only forest insufficient. `benchmark_results/teacher_scale_v14_v15_probability_v16_full_research_handoff.json` contains original group and physical benchmark evidence.

**Target mismatch.** Original v5 rewards `P(byT2)+0.5*P(exactly T3)`. v27 and v39 prioritize T2, while some earlier action-regret comparisons used `P(byT2)+0.5*P(byT3)`, overweighting early success relative to the original utility. Primary deployment target must be fixed *before* comparing policies; also report both utilities and byT3.

## Revised order of research: first identify mechanism, then train

1. **Separate first-action KEEP/MULL from actual bottom choice.** In a predeclared fresh cohort of common physical 99-slot London deals, log the original v5 and frozen v27 *same-stage* decisions (no future-library peeking). Stratify by earliest disagreement and direction, especially stages 0/1/2. For changed-stage actions, compare KEEP and MULL under the SAME frozen v33b bottom and downstream policy. A separate factorial bottom audit compares v5-selected, v14-selected, and v33b-selected legal bottoms on **the same retained stage/seven**. These interventions isolate the causes of the original policy gap; don't multiply conditional deltas into unconditional winrate claims.
2. **Audit keep-value / bottom coupling.** At every marginal original v27 decision, compute or estimate `Qkeep` for the exact retained hand/bottom that would actually be played. Mark v33b bottom overrides explicitly, and analyze whether the sign of `Qkeep−Qmull` reverses. Do NOT compare incompatible policies under unpaired future random seeds or use realized unknown-card order to choose.
3. **Actual-v5 disagreement source sampling + unbiased source sampling.** Reuse 134000–134383 for true teacher/v27 sampling if the prior information-boundary regression passes, and 134384–134767 for random early-stage coverage. Obtain *physical* K/C labels under common continuation, group by original game ID, use enough independent distinct hands and per-hand futures to stabilize signs. Future-99 MULL probabilities remain shared seat/stage but shared C uncertainty is resampled ONCE per bootstrap replicate. Stratify and include actual stage0 and stage1 separately.
4. **Run two deliberately different learning baselines, on the SAME held-out splits:** (a) compact true T2 signed-action-regret model and (b) *real-v5* KEEP/MULL residual classifier (with teacher actions as TRAINING annotations, not deployment features or assumed truth). A teacher-student two-head model can be explored only if the bottom-candidate accuracy exceeds structural-only and the keep recall for consequential disagreements is adequate. Prefer clear small-capacity line features or targeted supervised capability terms over untested higher-dimensional forests. Evaluate teacher agreement and real physical action regret separately.
5. **Require a decisive frozen-policy test before promotion.** On the untouched 135000–136023 groups, report first-disagreement recall in both action directions, calibration by group/stage, the fraction of actual complete London paths altered, and two-source physically bootstrapped T1/T2/T3 effects. Do not tune using prior 115k/127k/129k/131k. Only after passing predeclared gates should we run paired whole-game `137000–137511` and the expensive v5 reference where practical.

## Immediate implementation priorities

- Run the v40 read-only audit and the new synthetic v5 unseen-order smoke. Both are **committed but no successful execution is verified**.
- Before initiating any costly labels, lock fresh IDs, scenario counts and weights, reference teacher implementation fingerprints, common bottom/continuation policies, and the T3 harm budget.
- Build a concise source-census + counterfactual design around **actual first v5 disagreements**; do not run v39 threshold tweaks and call them a new discovery.
- Keep untouched code and previous physical 115k/v34c/v37–v39 archives. This file is a diagnosis and pretraining roadmap, not a result of new simulation.

**Success criterion:** approach v5's independent prospective T2 deployment probability *without introducing a comparably large T3 deficit*, at far lower mulligan runtime. A point improvement at one-step K−C without changed reached paths or full-game validation does not meet this criterion.
