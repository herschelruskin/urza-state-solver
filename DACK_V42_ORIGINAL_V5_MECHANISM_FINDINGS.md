# DACK v42 — forensic explanation for v5's persistent decision advantage

**2026-11-01, COMPLETE. No new model trained, no deck mutated, no older branch overwritten.** Isolated branch `dack-v42-v5-decision-mechanism-audit-20261101`.

## Three independent source-grounded findings

The original `v5` policy is **structurally different** from every post-v5 no-beam learner:

1. **It values legal seven-card candidate hands with game-engine lookahead**, not just generic hand or card presence features. Original v5 picks from structural top-12 London bottom candidates, simulates 8 sampled unknown-library futures (refines to 16 near thresholds), using mulligan evaluation beam60, selects the maximum estimated `P(exact T1)+P(exact T2)+0.5 P(exact T3)`, with deterministic structural tie-breaks. Its branch-and-bound optimization prunes only candidates provably inferior to the current incumbent on those same sampled futures. Subsequent v27 predicts `P(by T2)` using a random forest (trained on real but only four physical futures per training-stage state) and uses a learned v14 bottom-choice forest; v33b replaces only that bottom chooser. Both use offline DP continuation and no real gameplay search for the current hand.
2. **Its acceptance thresholds and objective differ.** The original `v5` frozen native continuation: C7=.55603, C6=.51025, C5=.42268, C4=.31419, C3=.19234, C2=.06171875 (old provisional constant tables). Assertive v5 additionally adds +.200 to *each* first and second seven-card threshold, +.120 for keep6, +.055 for keep5, +.015 for keep4, except where the native v5 threshold is met and simulated T1 sample >0 (do not sacrifice an apparent T1 opportunity). v27 uses separate per-seat model-derived DP continuation (e.g. first-seven ~.364–.412, second-seven ~.312–.331) and a **different T2-only output scale**. Never directly subtract raw v5 U from predicted v27 PbyT2.
3. **Both kept-hand selection and stage decisions matter.** All numerical claims below are based on the archived 115000..115255 source cohort with original exact same 99 physical slots, seat, stable dice and beam160 gameplay.

## Read-only historical first KEEP/MULL divergence audit

Sources: `benchmark_results/v42_original_v5_vs_v27_threshold_mechanism_115k.json`; GitHub Actions [41355434189](https://github.com/herschelruskin/urza-state-solver/actions/runs/41355434189), SUCCESS. Among 256 matched v5-v27 outcomes, 100 first naturally reached keep/mull stages differ and 156 terminate at the same stage.

| First different decision type | Source games | v5 action vs v27 action mean *conditional physical* T2 advantage | T3 advantage |
|---|---:|---:|---:|
| v5 MULL due **only** to extra assertive bump; its native cutoff would KEEP | 30 | **+8.82pp** | **−23.78pp** |
| v5 MULL even under v5 native continuation cutoff; v27 KEEP | 31 | **+17.17pp** | −4.50pp |
| v5 KEEP despite extra bump; v27 MULL | 39 | **+6.73pp** | +31.33pp |
| All selected first disagreements | 100 | **+10.594pp** | +3.688pp |

These latter figures reuse **actual independent strict beam160 KEEP trials** from v34c (32 per selected hand) and physically independent **shared frozen-v27+v33b C lottery** values (96 per seat-stage). They are conditional, specifically selected by *actual v5-v27 disagreement*, and KEEP uses the **v33b** bottom, not necessarily original v5. The 100 cases are already inspected historical samples; not a new unbiased empirical win-rate. First divergence stages 0–2 represent 61 games (26 bump-only vetoes, 24 native-rejects, 11 v5-keeps-first).

## New exact physical v5-threshold-only ablation (the decisive experiment)

Four-game strict original-v5 terminal parity smoke [41355728878](https://github.com/herschelruskin/urza-state-solver/actions/runs/41355728878) passed after correcting an original script assertion that failed to permit the legitimate `0` no-deployment sentinel. The first pilot [41355682909] **failed due to that test assertion**, not a gameplay-parity discrepancy; it was corrected without changing game rules, source hands, or test objective.

A complete **N256 eight-shard physical gameplay replay** then passed [41355832086](https://github.com/herschelruskin/urza-state-solver/actions/runs/41355832086). Every one of the **256 original v5 archived terminal outcomes** was reproduced exactly under original strict rules and same hidden-order/canonical stable dice, proving physical parity. Each archived v5 natural history had already scored all stages up to its assertive final keep. For the alternative `v5-native-no-bump`, simply accept the earliest of those original recorded v5 stages for which original v5 raw utility exceeded **v5's own native frozen threshold**, retaining its EXACT original v5-selected hand/bottom. This counterfactual requires **zero new v5 lookahead beams** and no model fitting. Simulate native kept state with the same 99 slots, same actual unknown92 order, stable dice and strict beam160. Original v5 and no-bump differ **only** in the extra assertive threshold.

| Frozen matched 115k sample | By T1 | **By T2** | By T3 |
|---|---:|---:|---:|
| Original **v5 assertive** | 7/256 | **132/256 (51.56%)** | 214/256 |
| **v5 native, extra penalty removed** | 7/256 | **124/256 (48.44%)** | 219/256 |
| v27 frozen | 7/256 | 106/256 (41.41%) | 189/256 |
| v33b bottom variant | 8/256 | 111/256 (43.36%) | 196/256 |

Removing v5's extra acceptance penalty changed 68/256 final London keep stages (native stops earlier), resulting in 8 native T2 wins vs 16 original v5 T2 wins among the changed games, net **−8 by-T2 games** or **−3.125pp** on the entire N256; physical paired bootstrap 95% CI **[−7.031,+0.391]pp** (inconclusive on general population). At T3 no-bump gained 5 net games (+1.953pp, CI [−1.172,+5.078]pp), illustrating the T2-versus-T3 tradeoff. This is a genuine threshold-only causal contrast **on this specific finite sample**. It is not a new prospective accept/reject benchmark for another model.

Thus on this same 256-deal sample, the original v5-v27 byT2 numerical gap is +26 games. Removing only the explicit assertive penalty reduces it from **+26 to +18**, leaving most of the numerical difference even when v5 uses native acceptance. This decomposition is descriptive for these matched games, not an additive universal causal guarantee of independent components.

Raw and pooled result: `benchmark_results/v42_native_no_bump_115k_physical_shards/`, `benchmark_results/v42_native_no_bump_v5_physical_N256.json`.

## Same-stage hand/bottom audit and terminal gameplay parity

Read-only archival [41355937884](https://github.com/herschelruskin/urza-state-solver/actions/runs/41355937884) PASS; report `benchmark_results/v42_115k_bottom_vs_stage_split.json`.

- In **100/256 different-final-London-stage games**, original v5 beat v27 by **+19 net byT2 games**; the same-stage group contributes +7 net.
- Of **156 same-stage games**, only **100** had a legal bottoming choice (the other 56 kept seven). Of these 100, v5 and v27 chose **different kept hands/bottoms in 70**, producing **+7 net byT2 games** for v5 over v27 (9 v5-only successes, 2 v27-only). Relative to v33b, 62/100 same-stage eligible hands still differ from v5, accounting for **+4 net byT2 games**.
- Among **86 same-stage and identical final-hand/ordered-bottom games**, v5 and v27 terminal T1/T2/T3 outcomes agreed **perfectly**. For v5 vs v33b, 94 identical final-hands had perfect terminal agreement. So an alleged separate gameplay-engine discrepancy does **not** explain the difference when final hands and chosen orders truly match.
- The overall v5-v27 gap +26 byT2 = +19 different stage +7 same-stage different retained hand, on the archived finite sample. The overall v5-v33b gap +21 = +17 different stage +4 same-stage different retained hand.

This importantly prevents a mistaken conclusion that **only** decision thresholds matter: both *which seven to keep* and *which cards to bottom* visibly contribute to v5's goldfish advantage. And a no-bump version of the original full outcome search still significantly numerically exceeds v27 on the same historical cohort, even though statistical uncertainty remains to be quantified.

## What has NOT been established

- Original v5's advantage is not proof that the v5 internal 8/16 sampled scores are unbiased or that v5 always chooses the physically optimal action. Candidate-specific seeded hidden draws and max-over-12 candidates may create high-variance optimistic selection. Its frozen C constants are *provisional*, not calibrated to the exact current deck and objective.
- The conditional 100-hand physical analysis used v33b bottom, and cannot isolate different bottom selection from eventual full-game behavior in cases where the kept stage also changes.
- Current 99 deck is *one_key_34*. There is no evidence yet that these exact C thresholds remain optimal under 1–2 card substitutions.
- v5's fast-beam-60 internal approximation is not identical to the strict real beam160 terminal, though all 256 original outcomes were successfully reproduced with terminal engine parity.
- The isolated threshold-only ablation is **not** a new independent 256 game sample; it reuses the old 115k outer groups.
- No v42 model, shortcut heuristic, or engine override has been promoted.

## A more informed next experiment

**Do not train another generic hand classifier.** Instead separate three causes with controlled *hybrid teacher ablations* on new, sealed independent groups, keeping original v5 engine/source intact:

1. Test an **assertive v5 threshold rule** applied to v27's directly predicted and calibrated hand utility by an explicit **rank-preserving conversion** to the same comparable objective, rather than naively adding .2 to a predicted T2 score. Audit whether a high-margin T1-positive exception can be implemented without the original v5 beam.
2. Replay original v5's own **choice of retained hand** under a fast learned keep threshold and vice versa, with exact shared stage/seat/deck and unseen order. The first part requires recording the original candidate-choice scores/thresholds on new physical sevens; no v5 at runtime in a final student.
3. Capture the full top-12 v5 candidate EV profile on a **small stratified set** of real v5-v27 conflict sevens to discover which combinations it values (e.g. exact mana sequences/tutor/LED, tap-order and restricted white mana). This is far more informative than another 4096 unstructured teacher labels.
4. Compare against a **selective fallback** that invokes original v5 only on uncertain high-consequence early hands and can be predeclared using purely observable features; this explicitly trades speed for fidelity. Measure actual fallback fraction, runtime, stage decisions, T1/T2/T3 with a fresh physical holdout.

First recover these causal mechanisms before collecting more 1000s of low-information v5 action-label-only sevens or claiming v5 parity.
