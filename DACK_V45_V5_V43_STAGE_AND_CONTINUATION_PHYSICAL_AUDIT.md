# DACK v45 — v43 residual gap localized to London acceptance, physical C calibration

**2026-11-01. Read-only source audits complete; true first-disagreement K recheck in GitHub Actions. No replacement policy or threshold approved.**

## Background and counterfactual constraint

The source-matched original v5 versus frozen v43 N128 old 151000–151127 physically identical 99-slot deals gave:
- original v5 73/128 byT2, v43 65/128; original v5 115/128 byT3, v43 107/128. Fresh 151k N256 v43 vs v27 had been examined BEFORE adding the v5 reference to the first N128, so this is a **retrospective comparison, not an independent acceptance test**.
- When keeping the same final stage **and same ordered bottom/hand**, the original physical T1/T2/T3 outcome was exactly identical in all 54/128 cases. When same stage but bottom differed, 30/128: the net T2 advantage was **v43 +1 game** (v5 +0).
- In 44/128 cases where original v5 and v43 kept at **different London stages**, the net T2 advantage was **v5 +9 games** (v5-only 13, v43-only 4), giving the entire observed residual v5-v43 +8 net T2 after offsetting the -1 bottom group.
- Of 44 first genuine KEEP/MULL conflicts, **v43 KEPT EARLIER 28 times**; **v5 KEPT EARLIER 16 times**. v43's earlier-keep group accounts for +6 net T2 to v5, v5 earlier for +3. First conflict stage0 or stage1 accounts for **26/44**, a majority. Stage0: 9 v43 earlier, 4 v5 earlier. Stage1: 11 v43 earlier, 2 v5 earlier.
- This is a descriptive *matched-deal* decomposition, not a universal causal effect of stopping stage; both later stages and retained hands differ when stop stage changes.

Read-only source `benchmark_results/v45_v5_v43_remaining_T2_gap_same151k_N128.json`, successful [Actions 41360219517](https://github.com/herschelruskin/urza-state-solver/actions/runs/41360219517).

## NEW actual v43 future-mulligan continuation values

Complete 20 seat-by-rejected-stage (four seats × stages0..4), **96 independent full99 future London sequences per cell = 1,920 strict real beam160 physical goldfish games**, without original v5 beams. Original v43 candidate-max scoring and KEEP/MULL logic were separately reconstructed and checked for **exact state/hand/bottom/history parity** against original `v43.choose_keep` on 12 physical deals before any conditional continuation trials.

Each physical C trial:
- Rejected current seven is returned to the 99-card physical deck;
- reshuffle all99 independently for each next possible London stage (not a single hidden92 current hand future);
- follow unchanged v43 max-frozen-v27 Q2 candidate selection coupled to its exact KEEP choice and inherited frozen seat/stage v27 DP;
- simulate the resulting retained hand under strict beam160 + independent stable chance.

Actual future v43 `P(Dack byT2 | MULL again)`, pooled across 4 seat strata (384 future lotteries per stage):
| Rejected stage | True future v43 PbyT2 | Original inherited v27-DP average predicted continuation score |
|---|---:|---:|
| 0, first seven | .4141 | .3844 |
| 1, second seven | .3646 | .3181 |
| 2, six-card keep opportunity | .2943 | .2338 |
| 3, five-card keep opportunity | .2318 | .1384 |
| 4, four-card keep opportunity | .1380 | .0777 |

All 20 C cells and pool passed. The actual physical v43 continuation probability exceeds the original inherited v27 DP score on average at all five stages, by +.030 to +.093. **Caution:** v27-DP is a *predicted model utility* and not guaranteed the same calibrated physical probability scale as C; differences are a diagnosis, not authorization for replacing all DP thresholds or a proof that aggressive deep mulliganing improves byT2. Actual real Qkeep may have comparable model bias.

C source `benchmark_results/v45_v43_physical_continuation_vs_v27_DP_20cells.json`, 20 raw source cell shards `benchmark_results/v45_real_v43_continuation_20cells_shards/`, successful [Actions 41360432206](https://github.com/herschelruskin/urza-state-solver/actions/runs/41360432206).

## Targeted direct QKEEP versus true v43 C experiment — separate physical outcomes

To decide whether the discrepancy really produces better action choices, v45 explicitly samples the EXACT 44 first original-v5-v43 actual action-conflict hands (selected by old 151k v5/v43 policies, not physical label values). For each hand:
- use **the archived exact v43-selected legal hand + ordered bottom** at the first conflict stage (even if v43 originally mulled);
- **32 independent unseen92 plus stable-chance strict beam160 physical KEEP futures**, blind and disjoint from original 151k actual future (44×32 = 1,408 real simulations);
- compare against corresponding independently sampled shared v43 full99 future MULL continuation C from the 20 source cells above (20×96 = 1,920);
- sign the K-C contrast so positive is the ORIGINAL V5 FIRST ACTION advantage over v43: if v5 kept, sign +; if v5 mulled, sign -;
- report overall and v43-earlier vs v5-earlier, stage0/1 vs 2–4, T1/T2/T3, and a two-source bootstrap resampling original source groups + 32 K rolls + **each shared 96 C lottery ONCE per replicate**. Do not pretend 32 K and 96 C are independent new original seven-card hands.
- The original v5 chosen *bottom* when v5 keeps may differ; this experiment holds exact v43 bottom fixed on the forced KEEP arm specifically to isolate first KEEP/MULL action, not replay original v5's complete policy. These are **retrospectively selected physical opening hands** (previously examined 151k), so conditional action regret is NOT whole-game population T2 probability.

K workflow [41360603549](https://github.com/herschelruskin/urza-state-solver/actions/runs/41360603549) plus future pool `.github/workflows/dack_v45_pool_after_44_K_complete.yml`, research only. No initial v45 policy has been fitted or approved.

## Next decision, regardless of K outcome

If original v5 first actions show positive physical conditional regret for v43 on these conflicts, that confirms the early-stage acceptance objective is a real target under v43's own better candidate/bottom selection; the next model must learn observable *physical KEEP minus matched v43 continuation* rather than v5 imitation or raw Q2 uncalibrated scores. Train on independent physical first-stage *student-v5* conflicts plus an **unbiased hand distribution**, with group-aware variance and full retained-hand consistency, not only retrospective selected conflicts. A selective original-v5 fallback at high-impact early states is an alternative speed–fidelity control.

If the true conditional regret is near zero or reverses, the v5-v43 +8/128 original terminal difference could reflect finite-sample variance and/or original v5-specific bottom and later-stage effects. Do not train thresholds to reproduce old 151k outcomes.

Preserve uninspected 155k and 149k bands as future independent whole-game evaluations, subject to proper freezing and no peeking.

As always, these are simulator *goldfish Dack deployment* outcomes, not four-player multiplayer cEDH winning chances.
