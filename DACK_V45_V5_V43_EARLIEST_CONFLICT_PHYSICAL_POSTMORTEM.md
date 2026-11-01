# DACK v45 — original v5 vs v43 first real KEEP conflict: full physical investigation

**Completed 2026-11-01, all workflows PASS. Research only. No policy promoted; 155k acceptance cohort remains unopened.**

## Stage/bottom contribution from 128 previously inspected matched 151k physical games

Original v5 and frozen v43 max-Q2 have matched initial 99-slot shuffles and seat, strict beam160 and original stable dice. Read-only all-history replay: [run 41361338465](https://github.com/herschelruskin/urza-state-solver/actions/runs/41361338465), raw `benchmark_results/v45_v5_v43_matched_151k_N128_first_conflict.json`. Original v5 **73/128** by T2, v43 **65/128**, gap **+8 games**.

- **44/128 different final London stages** yielded v5 **+9 net T2 games** (+13 v5-only, −4 v43-only). The first actual different keep action was found on the earliest stage **both policies actually visited**, not inferred from later hypothetical outcomes. Original v5 kept first in 16 cases; v43 kept first in 28.
- **30/128 same final stage, different retained hand/bottom** yielded v5 **−1 net T2 game** (0 v5-only, 1 v43-only).
- **54/128 same stage and exactly same retained hand/ordered bottom** yielded **perfect original terminal physical win-turn parity**.
- Stage distribution for the 44 first actual conflicts: stage0 13, stage1 13, stage2 8, stage3 6, stage4 4. The 34 early stage0–2 conflicts account for v5 **+10 net T2 games**; the 10 later stage3–4 cases account for −1.
- These are DESCRIPTIVE differences in the already inspected complete policy histories, not causal intervention by KEEP or MULL.

## Genuine independent-physical-future test on the 44 actual historical conflicts

All K and C jobs, 24-deal frozen v43 continuation replay parity, and the pooled two-source bootstrap PASS: [GitHub Actions 41361665920](https://github.com/herschelruskin/urza-state-solver/actions/runs/41361665920). Raw report `benchmark_results/v45_true_v5_v43_first_conflict_new_physics.json`, complete 28 source K/C shards `benchmark_results/v45_true_first_conflict_physical_shards/`. The source 151k outer deals were PREVIOUSLY INSPECTED, selected because original v5 and v43 differed; new trial futures are independent but conditional on that selected population.

- **44 distinct source deals ×32 independent unseen92 reshuffles** under the exact retained hand of the policy that first KEEPS = **1,408 strict actual beam160 KEEP games**. For stage0/1 legal hand is the same between policies; at later stages, use the ORIGINAL v5 hand if v5 first KEEP, ORIGINAL v43 maxQ2 chosen hand if v43 first KEEP. No future hidden draw order in either decision.
- **64 independent full99 future redraw London continuations per relevant seat-stage**, for **15 occupied seat-stage cells = 960 real MULL+subsequent-gameplay trials**. The current original seven is discarded and all 99 slots restored before independent future-stage shuffles. Subsequent hands, candidate bottoms and KEEP decisions follow frozen v43 exactly, as demonstrated by the 24-deal parity selftest, NOT frozen v27 or v33b. C is one SHARED sample per seat+stage, counted once in each two-source bootstrap replicate.
- **All 44 first actual conflicts conditional mean physical action advantage for original v5: +8.416pp T2**, 95% two-source group/K/C bootstrap **[−0.249,+16.406]pp**. T1 +0.426pp [−0.994,+2.024]pp; T3 +6.072pp [−2.237,+14.134]pp.
- **28 v43-KEEP-v5-MULL conflicts**: v5 MULL **+6.864pp T2** (on new shared-v43 future), **−6.752pp T3**; 17 physical state-level positive T2, 9 negative. Indicates v43 early overkeeping under the primary T2 objective while preserving some T3 upside.
- **16 v5-KEEP-v43-MULL conflicts**: v5 KEEP **+11.133pp T2**, **+28.516pp T3**; 9 state-level positive T2, 7 negative. Indicates v43 under-recognizing some strong hands.
- Stage0 n13 +18.630pp T2; stage1 n13 +10.938pp; stage2 n8 +4.297pp; stage3 n6 −4.688pp; stage4 n4 −5.078pp. N per stage and confidence intervals of subgroups are small; **do NOT treat stage-specific point estimates as promotion thresholds**.
- The group-conditional physical contrast follows frozen v43 **after** MULL, including when original v5 is the first KEEP. It is NOT the full native v5-versus-v43 end-to-end policy reward, and its mean on the 44 selected conflicts must **not** be interpreted as a full-population T2 win-rate change. It does not imply original v5 is always the better action.
- The historical source group's old physical goldfish outcome was NEVER used to choose future physical K or C rollouts; selection used only first original natural decision conflict. However these old groups were already observed in prior experiments, so no novelty/acceptance claim.

## Root cause, with direct evidence

v43's **joint candidate-max and KEEP decision** improved fresh T2 relative to v27 and appears to have almost solved generic bottom choice. The remaining 151k original v5 gap is overwhelmingly concentrated in **which London stage to stop at**, notably first and second sevens. The original v5's 8/16 sampled beam60 hand EV plus provisional +0.20 assertive seven-card acceptance bump measures and prices the opportunity cost of continuing differently from frozen v43's T2-only Q2 forest and seat-stage offline DP continuation. Both its occasional early MULL and occasional early KEEP decisions outperform v43 in this deliberately selected action-regret sample, so blindly adding a constant mulligan aggressiveness penalty is unjustified.

This does not justify overfitting v43 thresholds to 151k or v45. The v5 and v43 raw value predictions have different objectives/calibrations, and original v5 itself can suffer candidate-max Monte Carlo noise.

## Recommended next controlled design (not executed)

1. Focus initial runtime/model budget on **stages 0 and 1** first. There is no bottom ambiguity at either stage, allowing a clean paired direct T2 KEEP-vs-MULL estimator conditioned on visible seven, seat and whole-deck multiset.
2. Collect fresh **random physical seven-deal groups** plus **targeted, observable-feature-defined decision-margin oversampling** (not selecting by hindsight outcome). Preserve source sampling probabilities and report both random and selected strata independently.
3. For each, estimate real Q2KEEP from 16–32 blind unknown92 futures and real Q2MULL from 64+ full99 future redraws using exact frozen v43 continuation; train an explicit differential Qkeep−Qmull conservative model or calibrated stage0/1 correction, comparing to frozen v43, with group-disjoint folds and shared-C uncertainty. Pairwise decision-regret needs real action advantage, not v5 imitation top1.
4. Evaluate a frozen policy on a **new, untouched full-game cohort** distinct from 115k/151k/154k/155k; keep 155k sealed if it is reserved for separately specified v44 acceptance. Compare v43 vs candidate with matched strict beam160 T1, byT2, byT3 and time, and if feasible matched original v5.
5. Do not spend time refining near-T2-equivalent stage2–5 bottom candidates on current deck. Preserve existing exact combination and card-specific mana constraints to allow true early KEEP hand evaluation. Changes of 1–2 deck cards remain untested.

**Disposition:** v43 remains strongest experimentally validated fast student; v45 is a diagnostic campaign only, no new model trained or approved.
