# DACK v41 physical early-regret attempt — final source-based postmortem (2026-11-01)

**Disposition: REJECT the v41 capability ridge and anchored ridge as unproven. No model promoted. Do not launch sealed 149k whole-game acceptance on these candidates.**

## Predeclared research candidate and historical warning

The v41 design trained regularized models to predict actual physical P(Dack deployed by T2 if KEEP) and P(by T3 if KEEP), using the EXACT frozen v33b retained hand/bottom and v27/v33b continuation. Predictors used only the visible seven, hand-capability descriptors, stage/seat and (for anchored only) the old v27 score; none used actual v5 teacher labels or hidden realized future order. An early action would override baseline only if predicted Qkeep-Qmull exceeded ±5pp, with a predicted T3 harm guard at -10pp. Stages 3+ remain frozen.

The original 115k, 116k and preexisting shared-C 96-future archives were all consumed development material. The group-separated five-fold historical exercise was **not prospective**. It produced 125 independent physical deals, 253 early hypothetical states (64 unbiased 116k deals×3 +61 retrospectively selected early real-v5/v27 disagreements), KEEP outcomes from eight futures per unbiased state versus 32 per selected disagreement state, and Qmull from 96 archived physical futures per seat/stage cell.

Predeclared results: capability model 25/253 actions changed, retrospective sample-balanced conditional T2 +2.869pp / T3 -1.317pp; anchored 21 changes, T2 +2.131pp / T3 -1.272pp. **Distributional breakdown exposes weakness**: on the *unbiased* 116k physical groups, capability +0.282pp T2 (only eight action changes); anchored -0.054pp. The selected 115k v5/v27 early-disagreement groups drove capability +5.584pp. The model learned a high-level signal that performed in selected disagreements but showed near-zero unconditional physical advantage. There was no evidence for a robust T2 gain from historical data alone.

Source: `benchmark_results/v41_early_physical_regret_cv.json`, [CV Actions 41354356548](https://github.com/herschelruskin/urza-state-solver/actions/runs/41354356548).

## NEW physically independent 148k conditional test — completed

Source: `benchmark_results/v41_fresh_148k_N64_conditional.json` and 20 fully archived raw KEEP/C shards in `benchmark_results/v41_148k_conditional_physical_shards/`. [New physical workflow 41354642489](https://github.com/herschelruskin/urza-state-solver/actions/runs/41354642489) **SUCCESS**.

- 64 new independent full-99-slot source groups `148000..148063`; stages 0,1,2 all scored before any outcomes = 192 early states. The capability model and all its hyperparameters had been frozen before this cohort; no v5 teacher calls and no fitting from the fresh outcome.
- 8 new independently shuffled unknown92 strict beam160 KEEP futures per hand = **1,536 real gameplay runs**, always exactly frozen v33b selected hand/bottom.
- 64 independently sampled full99, all-cards-restored, frozen-v27+v33b future MULL runs per seat/stage cell ×12 = **768 new physical continuation gameplay runs**.
- Bootstrap physical outer deals, all KEEP futures, and each shared seat-stage C lottery with independent resampling (2,500 replicates). Distinct stage0 versus stage1 maintained; same exact 99 physical cards; no realized unseen future order in policy score. Conditional *one-step* contrast, NOT end-to-end full-game T2 probability.
- Candidate changed only **10/192 hypothetical early-stage decisions**, across 9/64 groups: **9 KEEP→MULL and 1 MULL→KEEP**. No guarantee those are naturally reached by the candidate in a full game.
- Full early-state population mean conditional T1 **+0.1953pp**, T2 **-0.9521pp**, T3 **-0.3743pp**. T2 95% dual-source bootstrap **[-2.4821,+0.3662]pp**; T3 **[-1.5462,+0.9196]pp**. These are not statistically persuasive improvements.
- **Changed decisions only**: mean physical T2 v41−v27 conditional advantage **-18.28125pp**, T3 **-7.1875pp** across the 10 changed states. These low-N, eight-future outcomes are noisy; do not infer precise per-hand effects.
- Stage0: one change, T2 -0.8789pp across 64 stage states. Stage1: six changes, T2 -1.2207pp. Stage2: three changes, T2 -0.7568pp.
- Technical workflow and physical checks all PASSED. **Scientific acceptance gate failed**: negative point estimate, CI includes adverse outcomes and crosses zero, and no plausible full-game improvement claim.

## What went wrong / remaining methodological limits

1. The fixed model learned from only 125 independent source groups, not 253 independent hands. Eight independent physical futures per random-stage QKEEP creates large label variance; 32 for selected conflict K lowers noise but oversamples a special source distribution. Stratification/weighted grouping did not erase that selection shift.
2. Earlier +2.87pp cross-fold T2 conditional advantage was heavily driven by the v5-selected, previously explored conflict stratum; the random stratum never exhibited a convincing gain. The sign reversal on fresh unbiased states is not surprising.
3. The predicted Qkeep under the v33b hand was explicitly coupled to the actually deployed hand (a meaningful improvement over old mismatched K-value features), but the regression remained too weakly discriminative at the early decision boundary. Further threshold tuning on the new 148k results would be **validation leakage**.
4. The new 148k test samples all three early stages, including hypothetical stages not naturally reached. It cannot establish cumulative full-game deployment gains/losses. The model's stage0/1/2 override changes future hand-path distribution; the frozen downstream C model approximates one-step causal comparison, not fully refitted v41 continuation.
5. The new N64 diagnostic has limited power, because only ten actions changed and the KEEP estimator has eight trials per state. That imprecision does **not** justify treating a negative direction as evidence for improvement or increasing to full-game 149k N512.
6. Portability across one- or two-card deck substitutions remains completely untested and cannot be inferred from the "capability" model name.

## Disposition and rational next steps

- **Stop v41 candidate:** retain trained JSON and raw sources for reproducibility, keep `model_approved=false`, never overwrite v5/v27/v33b/v40 branches.
- Do not use the consumed 115k, 116k, 117k, 147k or 148k results as future untouched acceptance data or to repeatedly optimize thresholds. Keep reserved 149k acceptance unexamined.
- A serious next attempt must either (i) collect a substantially broader independent pool of *genuine v5 early disagreement decisions with correctly paired real K/C and richer hand/line feature descriptors*, or (ii) test a **selective v5 lookahead fallback** on predeclared uncertain/high-leverage states to trade runtime for accuracy. Neither is proven and neither should silently be presented as the winner.
- Before further expensive physics, audit the model's decision rankings and representation of actual mana/topological line constraints, how v5 lookahead prices opportunity cost, and whether low-dimensional aggregate proxies erase the very hand combinations causing early errors. Aim for a physically meaningful decision boundary, not overall 86% imitation accuracy.
