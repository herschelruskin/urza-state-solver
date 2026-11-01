# DACK v40 — original-v5 student high-regret failure and fresh N16 physical pilot

**2026-11-01. Research-only; do not promote either v40 student.** All values source archived verified GitHub Actions output, not extrapolated game probabilities.

## Corrected 100-hand v34c physical-regret overlay (read-only)

Source: `benchmark_results/v40_student_v5_vs_v27_115k_physical_overlay.json`, GitHub Actions [41344891494](https://github.com/herschelruskin/urza-state-solver/actions/runs/41344891494). Compares predeclared frozen full and portable student at exactly the earliest historical 115k v5/v27 differing keep-stage, with archived 32 forced-KEEP and 96 shared frozen-v27+v33b MULL futures. Neither original 115k full-game win turns nor new physical samples are used. **Conditional, retrospective, nonindependent from earlier project diagnosis, and student may have already diverged at an earlier stage.**

| Measured item | v5 action | v40 full action | v40 portable action |
|---|---:|---:|---:|
| Signed conditional T2 advantage over frozen v27 on 100 selected hands | **+10.59375pp** | +1.19792pp | +2.39583pp |
| T3 conditional advantage | +3.6875pp | +5.6771pp | +5.6354pp |
| Matches v5 at first v5/v27 differing stage | 100 | 29 | 31 |
| Matches v5 at stages 0–2, among 61 selected cases | 61 | **9** | **11** |
| Reaches original first v5/v27 differing stage without already keeping | 100 | 87 | 89 |

Among 61 original v27-first-KEEP, v5-first-MULL cases, full copied v5 MULL only 9 times, portable 12 times. Across the 39 original v5-first-KEEP cases, full copied v5 KEEP 20 and portable 19. Early 0–2 is the high-value failure: original v5 action has **+17.418pp** T2 versus v27 in these 61 retrospectively selected groups, whereas full student +2.169pp, portable +3.484pp. At stage 0 specifically portable agreed with v5 on **0/17** original conflicts (the stage0 prospective significance is not estimable).

The pooled T3 conditional advantage of student over v27 is **not** evidence of better T3 full-game deployment; selection, shared C sampling and earlier student divergences prevent a population win-rate inference.

## Independent, frozen full-game N16 pilot (new 147000–147015 seed IDs)

Source `benchmark_results/v40_fresh_147k_N16_strict_pilot.json`, GitHub Actions [41345140891](https://github.com/herschelruskin/urza-state-solver/actions/runs/41345140891). Separate interpreter per policy, original same 99-slot physical seeds and first seven/seat, strict actual beam160, original stable chance, unchanged v5/v27, no fitting on 147k.

| Policy | exact T1 | by T2 | by T3 | total 16 games execution time |
|---|---:|---:|---:|---:|
| v5 | 1 | **12/16** | 14/16 | 299.94 s |
| frozen v27 | 1 | 10/16 | 16/16 | 5.76 s |
| v40 full | 0 | 10/16 | 15/16 | 6.08 s |
| v40 portable | 0 | 10/16 | 15/16 | 6.12 s |

Each v40 student −12.5pp by-T2 vs v5 on N16, paired bootstrap 95% CI [−37.5,+12.5]pp; each is therefore **unproven** to match or beat v5. The same by-T2 count as v27 does not prove numerical equality. The v40 students are ~50× faster than v5 in this particular tiny sample; no new universal runtime speedup claim. Crucially only N16; avoid promotion.

## Root-cause reading

Overall behavior cloning was >86% KEEP/MULL correct and ~66% exact bottom among all natural stages on a *previously inspected* 256-group cohort. That accuracy was dominated by ordinary MULL decisions and free stage0/1 bottom choices (no bottom possible). It offered almost no coverage of the physically consequential first-stage conflicts and appears **not to capture the original teacher's nonlinear decision boundary**. Original v5 is not an optimal physical oracle, but actual prior v34c K-versus-C outcomes strongly support its decisions in the selected stage0–2 conflicts.

**Do not** threshold-retune v40 from the already inspected 100 hand overlay or the 147k N16. This would overfit precisely the retrospective failures uncovered. Better next candidate must explicitly source new *student-v5* disagreement states, not merely v27-v5 teacher hard groups. Train a bounded residual/action-regret comparator on archived physical 115k/v34c plus independent v34/v37 random hands, with groups as units and v33b bottoms/frozen continuation held constant, preserving both keep and bottom policy semantics. Reconstruct honest heldout selection and obtain independent new physical K/M observations where student and v5 actually disagree. Evaluate T2/T3 regret with a two-source bootstrap and a separate, sealed whole-game N256+; do not use 147k/115k for selection.

## v41 experimental change budget

- Favor a **narrow early-stage residual policy** activated at London stages 0,1,2, trained on group-weighted *physical Q(KEEP)-Q(MULL)* rather than another unconditional v5 KEEP forest.
- Report keep/mull and bottoming impact separately; keep values must correspond to **exact retained hand** used if keeping. Use a shared continuation defined consistently for both forced actions.
- Maintain exact 99 cards, legally restored full deck on mull, distinct stage0 and stage1, strict real beam160, randomized hidden92 physics, stable dice and reference v5 fingerprints.
- Teacher-only or physical rollout *counts* are not independent hand counts. Retrospectively selected disagreement samples are not population samples.
- Do not let game ID cohorts 115k or 147k become a new acceptance holdout. Reserve new, independently drawn 148k+ IDs before fitting/test. No model is currently promoted.
