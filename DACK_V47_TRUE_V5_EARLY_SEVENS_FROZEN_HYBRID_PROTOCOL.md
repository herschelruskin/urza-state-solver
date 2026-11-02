# DACK v47 — original-v5 sampled lookahead ONLY on the first two seven-card hands

**FROZEN before new 165k outcomes, 2026-11-01 Toronto local. Experimental only; not a zero-beam model.** Branch `dack-v47-original-v5-first-two-seven-fallback-20261101`. No prior engine branch overwritten.

## Motivation and scientific target

The v45 first-disagreement analysis found the remaining original-v5 vs v43 T2 gap concentrated in stages0–2. The v46 attempt to adjust first-two-seven Q2 predictions using physical K8192/C1024, Ridge and physically calibrated C failed its held-out 64-group development gate: no stage0 decisions changed, only 2–3 stage1 decisions changed (+0.35 to +0.61pp imprecise conditional T2). The retrospective original-v5 151k early conflict transfer showed neither v46 correction rescued 6 v5-KEEP/v43-MULL hands.

A fundamental alternative is to preserve **the actual original-v5 gameplay value evaluation when the candidate-choice problem is trivial**: London 0 and 1 each keep 7 and therefore have **only one legal candidate** and **no bottom choice**. Original v5 normally can evaluate up to 12 possible retained bottom candidates at later stages. At stages0/1 it has only one, which should reduce the cost of authentic v5-style value evaluation.

## v47 policy, no fitted teacher imitation

- On stage0 and (only if stage0 MULL) stage1, invoke the **original v5** stable-dice, bounded branch-and-bound, sampled-real-gameplay **beam60, 8/16 futures** original `batch.evaluate_keep(seven,7,unknown92,seat)`, with original (P(exact T1)+P(exact T2)+0.5P(exact T3)) reward, original frozen C7=.55603 and original extra +.20 seven-card accept penalty; apply original T1-positive waiver exactly. No illegal future-order information. If KEEP, use exactly the original v5 returned unknown-order library and unchanged seven. If MULL, all 99 restored for next independently dealt London stage.
- On stage2–7, use **unchanged v43 frozen max-Q2 candidate and threshold** for both bottom and KEEP. No original v5 beam beyond stage1; never modify the v43 policy's source or the deck. Hence this is a *selective search hybrid*, NOT a fully distilled no-beam student. Its first-two-stage original v5 continuation threshold is provisional and calibrated for original-v5 downstream, not v43 downstream; full-game validation is essential.
- Use exact 99-card `one_key_34`, original strict game rules, physical beam160 and original stateless dice. Preserve stage0/stage1 distinct physical redraws and the original multiplayer seat sampling. Benchmark the number of actual sampled v5 scoring calls and real end-to-end time, not theoretical speed.

## Mandatory archived original v5 evaluation parity before new 165k cohort

The 16 previously inspected exact physical original v5 N128 archived 151k cohort first shard `151000..151015` was replayed. **All actually reached stage0/1 values, sampled T1, KEEP/MULL actions, legal hand/bottom, selected original game slots, and thresholds match the original v5 history exactly.** Original v5 stage1 was naturally reached in 13/16. On that tiny previously inspected pilot, full original v5 and hybrid each deployed Dack by T2 in 10/16, but that does NOT establish population equivalence. Hybrid 16-game runtime 38.146s, not yet a matched full-v5 speedup comparison. [Pilot workflow 41364986119](https://github.com/herschelruskin/urza-state-solver/actions/runs/41364986119) succeeded after a first failure caused solely by a historical source path under `validation/` rather than repo root. Exact original scores unchanged.

## New frozen physical full-game comparison

An entirely new independent goldfish cohort `165000..165255`, not in 115k/116k/151k/154k/155k/163k/164k, was reserved BEFORE benchmark outcome inspection.

- **N256** matched seat, all original 99 physical slots, stateful chance + original stable dice, strict game-play beam160: original v43 vs v47 stage0/1 true-v5 hybrid.
- **N128** predeclared first half `165000..165127`: also run full, **untouched original v5** in a separate isolated interpreter; compare three policies with EXACT initial physical seven, seat, original stable dice and rules. Verify original-v5 and v47 first-two-stage history parity on every naturally reached stage while their later stages may diverge.
- Report **T1, byT2, byT3**, matched outer-group bootstrap 95% intervals, same-cohort full v5-v47 runtime ratio, kept card count, and actual London stopping-stage changes. No coefficient/threshold selection from 165k results; no arbitrary reinterpretation of historical cross-cohort rates as matched data.
- Goldfish Dack deployment probabilities are **not real four-player cEDH match win probabilities**. Even a positive 256-group improvement is not sufficient to infer a sub-1pp noninferiority guarantee.

**This hybrid is a diagnostic speed-quality architectural candidate, not an automatic deck or policy promotion.** It may fail to improve v43 or may be too slow; either outcome must be reported.

Data script `dack_simulator/validation/v47_fresh_165k_paired.py`, pooling `dack_simulator/validation/v47_pool_165k_original_v5_hybrid.py`, workflow `.github/workflows/dack_v47_new165k_matched_three_policy.yml`.
