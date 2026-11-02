# DACK v43 — continuation-consistent DP and selective physical fallback, Nov 1 2026

**Decision: NO PROMOTION. Frozen v43 remains the best demonstrated fast baseline.** All development was isolated on `dack-v43-policy-consistent-hybrid-dev-20261101`, branched from the independent v43 audit. Original v5/v27/v43 files, models and prior branches were not modified. Sealed 155k and previously consumed 115k/151k/154k/160k/161k/165k were not used as new acceptance sets.

## Physical N256 — model-only policy-consistent continuation

Fixed policy and continuation table *before* the new source outcomes. Source DP was previously calculated on 1,024 physical seven-deal groups 163700–164723, and was piloted on disjoint development 164800–164863 (not re-used here). Frozen v43 versus **same v43 candidate Q2-max, different seat-specific continuation thresholds only**, on 166000–166255 (256 new independent full99 goldfish deals, eight N32 shards; strict original beam160 actual gameplay; isolated interpreter per arm; identical seats/shuffles/chance).

| Metric | Frozen v43 | Consistent model-only DP | Paired contrast |
|---|---:|---:|---|
| T1 | 17/256 | 17/256 | 1 DP-only, 1 v43-only; 0pp; CI [-1.172,+1.172]pp |
| **by T2** | **126/256** | **131/256** | 11 DP-only, 6 v43-only; **+1.953pp**, paired bootstrap 95% **[-1.172,+5.078]pp** |
| by T3 | 206/256 | 199/256 | 6 DP-only, 13 v43-only; **-2.734pp**, paired CI [-6.25,+0.391]pp |
| Mean kept | 5.5547 | 5.1953 | DP mulligans deeper |

Same final hand+bottom: **204/256**, exact terminal parity. Per-child measured runtime DP/v43 0.874, but includes interpreter startup and cannot be read as an intrinsic gameplay speedup. The predeclared gate required positive lower bound on paired byT2 bootstrap, and T1/T3 decline and runtime limits. **Gate failed on primary T2 uncertainty**, so no promotion. [Successful N256 run #41377645268](https://github.com/herschelruskin/urza-state-solver/actions/runs/41377645268).

## Independent strict physical selective fallback N128 (three arms)

Designed a second isolated research policy `dack_paired_counterfactual_v43_selective_line_20261101.py` to address rare early-seven sequencing errors, **without pretending to infer unseen deck order**. At stages 0 and 1 only, a predeclared list of 15 special mana/tutor two-card interaction patterns plus predicted Q2 closeness to a consistent DP threshold (within .18) triggers 6 *independently shuffled* hidden92 real beam160 future outcomes. Resample seed is a cryptographic hash of **only visible seven-card multiset, unknown 92-card multiset, seat, stage, and future index**; it never sees actual physical future ordering. The internal chance seed is restored before the real post-KEEP game. Predicted Q2 is shrunk toward the sample with prior weight 8; KEEP/MULL changes require both absolute movement >.12 and new margin >.06. This is a selective physical Monte Carlo search, **not** a mathematically exact no-draw line-feasibility prover and not a learned model.

No-fallback exact v43 candidate/decision parity selftest passed; an adversarial hidden-order-reversal and RNG-restoration test passed [#41378067632](https://github.com/herschelruskin/urza-state-solver/actions/runs/41378067632).

Full matched real goldfish N128 on fresh 167000–167127, 4×32 shards, 3 isolated physical policies:

| Metric | Frozen v43 | Consistent DP | DP + selective physical search |
|---|---:|---:|---:|
| T1 | 5/128 | 5/128 | 5/128 |
| **byT2** | **69/128** | **67/128** | **67/128** |
| byT3 | 111/128 | 106/128 | 106/128 |

- Physical search triggered **4 total** times (2 first-seven, 2 second-seven) across 128 outer games, changed **0** KEEP/MULL decisions.
- **128/128** DP and hybrid final hand+bottom identical, exact physical terminal parity.
- Additional search cost: **1.340x** DP-only runtime in child elapsed wall clock.
- The prespecified useful intervention coverage gate required at least 5 changed full games; **failed**. T2 difference vs DP is exactly zero *in this pilot* but neither is proven equivalent. This resembles the failed low-intervention coverage of v46.
- [Successful N128 three-arm run #41377978607](https://github.com/herschelruskin/urza-state-solver/actions/runs/41377978607).

## Exploratory across-cohort read-only pooled interpretation

These were two disjoint development experiments and not originally planned as a single confirmatory N384 gate. For DP versus frozen v43, combining their paired counts for descriptive context: byT2 DP-only 14 versus v43-only 11 = **+3/384 (+0.781pp)**, approximate group-level resampling CI **[-1.823,+3.385]pp**; byT3 DP-only 8 versus v43-only 20 = **-12/384 (-3.125pp)**, approximate CI **[-5.990,-0.521]pp**. The T3 decline may be substantive. Do not reframe this post-hoc combination as an untouched, confirmatory prospective result.

## Why the selective fallback failed: independent coverage, then historical examples

It was not a source-seed leakage, candidate mismatch or invalid physical probability. **The observable trigger is too rare**, and six futures plus shrinkage and conservative intervention requirements alter even fewer decisions. Reducing intervention thresholds without fresh physical evidence risks repeating original v5's noisy maximum-of-small-samples bias.

An explicitly **retrospective, read-only** review of 26 archived first/second-seven actual v5/v43 conflicts from already inspected 151k (not training data or confirmation): the new *observable* trigger would fire in 5/26; only 3/10 cases where v5 uniquely deployed T2 and v43 did not were covered. Examples missed:
- 151009: Gemstone Caverns + Mox Diamond + Coalition Relic + two Plains, Q2 .094 versus new seat-specific cutoff .437; flagged as a rare pair but excluded because `|Q2-cutoff| > .18`. Original v5 kept and deployed T2, while v43 mulled and failed. The model may *underestimate* unusual hands beyond the boundary, exactly where margin-only sampling never looks.
- 151038: City of Traitors + Gemstone Caverns + Coalition Relic + Mycosynth Gardens + Razorgrass Ambush, with first-two-seven Q2 .129 versus cutoff .417 and **no predefined pair flag**; v5 kept and deployed T2. Pattern-based triggers miss unanticipated multi-card interactions.
- 151091: Grim Monolith + Moonsilver Key + Mox Opal + Brainstone but Q2 .774 versus cutoff .468, so excluded by wide margin; here v43 already KEPT the seven and v5 MULLED, and historical outcome favored v5's later hand. A preselective hand-quality score alone cannot prove the future mulligan's value.

This is hindsight example selection; it must not be used as a new success rate or for tuning and retesting on 151k.

## Architecture decision

1. Keep original v43 untouched. The DP mismatch is an *internally provable* issue, but fixing the threshold table alone has so far produced modest uncertain T2 gains at a meaningful T3 cost. A **T2-only objective** may be insufficient for the stated priority (T1 especially, T3 secondary). Avoid promoting a deeper-mulligan policy based solely on the analytic DP values.
2. Reject the present six-future risk-triggered fallback as a useful policy; it changed zero decisions and consumed 34% extra measured runtime. **Do not widen its triggers using the 167k outcome data and call the same cohort fresh.**
3. Next meaningful structural work is a lightweight **visible-hand, turn-aware exact/legal mana/tutor reachability witness** (with an explicit no-hidden-order boundary), plus independent empirical KEEP-vs-MULL regret estimation on *representative* first-two-seven source groups. A witness needs to prove a *feasible* T1/T2 line rather than approximate generic ramp value, and needs to be sufficiently cheap to replace, not merely add, Monte Carlo rollouts.
4. Quantify how often this witness detects a v43 blindspot and whether changing that specific action improves full physical T1/T2 without excessively reducing T3. Validate separately from any old teacher conflict cohort.
5. No acceptance benchmark was justified or opened. **155k remains sealed.** No original v5/v27/v43 model or rules were changed.

## Reproduction and preserved outputs

- Frozen model-only DP research table `models/dack_v43_model_only_policy_consistent_DP_163700_N1024_RESEARCH.json`.
- `dack_simulator/validation/v43_DP_fresh_166k_N256_20261101.py`, `v43_DP_pool_166k_N256_20261101.py`, associated eight-shard GitHub Actions workflow.
- `dack_paired_counterfactual_v43_selective_line_20261101.py` (research only), `dack_simulator/validation/v43_hybrid_fresh_167k_N128_20261101.py`, `v43_hybrid_pool_167k_N128_20261101.py`, and six-future RNG-order invariance regression and Actions workflows.
- All 8+4 raw physical shard files, pooled JSON outcome histories, per-game fallback samples and runtime data uploaded under GitHub Actions runs #41377645268 and #41377978607. The branch report and code are committed, whereas Actions artifacts are subject to ordinary GitHub retention. No source model/experimental deck overwrites.
