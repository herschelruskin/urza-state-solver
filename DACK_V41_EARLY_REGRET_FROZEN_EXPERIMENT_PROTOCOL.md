# DACK v41 — predeclared early-stage action-regret residual experiment

**Research-only protocol, 2026-11-01. No v41 model fitted, no new physical outcomes, no promotion.** Isolated on branch `dack-v41-early-action-regret-20261101`.

## Trigger for architectural change

v40 learned from 1,288 distinct natural original-v5 training groups, with 256 separate historical replay groups and 48 student-visited groups. The full/portable classifiers had apparently good ~86–87% heldout stage KEEP/MULL agreement, yet on 100 retrospective v5-v27 physically audited first-action conflicts they matched v5 only 29/31 times, respectively, and only 9/11 times among 61 early-stage conflicts. Under the same frozen v33b bottom, original v5 beat v27 by +10.594 pp conditional T2; full/portable students recovered +1.198/+2.396 pp only. Independent new strict full-game 147k N16: v5 12/16 by T2, v27 10/16, both v40 students 10/16. These results do NOT prove general-population performance differences given selection and N16 uncertainty, but support **decisive early-regret misclassification** as the next target.

## Train-data roles

- **Historical physical training:** `benchmark_results/v34c_forced_keep_shards/v34c_keep_*.json.gz`: 100 original 115k different-stage conflicts; 32 real strict-beam160 Qkeep futures per group, matched frozen v33b bottom. `benchmark_results/v34_consistent_regret_shards/v34_C_*.json.gz`: 28 independent seat-stage MULL lottery cells, with 64 train +32 validation physical futures per cell. The old train/validation naming is historical only; **both are already consumed for v41** and are not a fresh validation set.
- **Unbiased physical training:** `benchmark_results/v34_consistent_regret_shards/v34_K_train_*.json.gz`: 64 independent outer 116k groups, eight physical Qkeep futures for EACH stage 0–6 using exact frozen v33b bottom. Match the existing 28 seat-stage Qmull libraries. Distinct outer group vs stage vs continuation lottery units.
- **Archived original-v5 annotations:** full 1592 natural historical groups and 6101 visits are available for **auxiliary teacher classification**, but never treat this as real T2 value. Initial v41 direct-regret training must explicitly compare its performance to using NO teacher-imitation labels.
- **Never train/tune/choose model from:** 117k v34 'untouched' physical results (already consumed in v34 development); historical 115k as an independent holdout; fresh v40 147k N16 (already examined); any source containing the final prospective holdout.

## Residual estimator and action gate

At London stage 0, 1, or 2 ONLY, estimate `Qkeep−Qmull` for the EXACT legal retained hand chosen by a frozen bottom policy (v33b) and frozen-v27 downstream continuation. Learn a small, strong-regularization model with fixed, feature-invariant hand capability descriptors (land, white, generic mana, tutors, fast mana, protected combo contamination, etc.) and the v27 Qkeep-vs-DP margin, stage and seat; no future draw order, actual real outcomes, v5 lookahead scores, or oracle cards at deployment. Train a paired direct-regret baseline and a v5-teacher disagreement weighted comparator, but count all labels from a shared hand only once, and shared C uncertainty once per bootstrap replicate. Disagreement-selected vs random source requires explicit source stratum and weighting so direct-regret validation cannot be inflated by biased sampling.

No model is approved merely for teacher agreement. Reject proposed overrides unless the model's physically estimated *incremental action advantage* is positive, with a conservative T3 harm bound. Freeze the exact objective (primary byT2; byT3 a separately reported safety bound) before labels. Respect v5's `P(byT2)+0.5 P(exactly T3)` as a separately reported metric, not identical to direct byT2.

## Next genuinely new physical evidence

- Reserve `148000..148255` as prospective independent **diagnostic physical action-regret** groups. Record original v5 decisions and frozen v27/v40 residual on the SAME real London stage/deal, with sample source denominators and sign directions. Select earliest *actually reachable* disagreement, not all hypothetical stage disagreements. The original v5 teacher requires expensive beam lookahead; budget a small correctness/cost pilot before launching full N256.
- For every selected disagreement sample real strict-beam160 KEEP under the exact frozen bottom (e.g. 16–32 independent shuffled unseen92 futures) and common independent full99 MULL continuation. Record T1/T2/T3. Bootstrap physical outer groups + K trials + shared C lottery separately.
- Reserve `149000..149511` as **completely untouched N512 full-game outcome acceptance** cohort for any FINAL model frozen before opening those IDs. If model selection uses 148k, then 148k is development, never a promotion holdout. N512 is still incapable of proving sub-1pp non-inferiority; report confidence intervals. If v41 fails development, do not run costly 149k acceptance or call v41 improved.

## Mandatory failure checks

1. **Information boundaries:** no revealed future deck order or future realized chance effects in decisions; no v5 scorer at runtime.
2. **Hand-score coupling:** any KEEP score refers to precisely the hand/bottom subsequently deployed, avoiding the v27-Qkeep/v33b-override inconsistency.
3. **Conditional versus population:** first-disagreement physical regret != full-game T2 win rate.
4. **Scoring uncertainty:** do not threshold against an empirical maximum selected from just 8 K rollouts; shrink and estimate group uncertainty.
5. **Later stages:** preserve proven frozen baseline after stage 2 until properly validated; an early-only change can cause downstream distribution shift even when later policy unchanged.
6. **Deck changes:** capability transfer across 1–2 substitutions is plausible but not demonstrated. Test original deck first, then compare real changed-deck conditions using correct 99-card definitions.
7. **Accounting:** keep baseline v5/v27/v40 archives immutable. New training and physical results stay isolated on v41, models permanently `policy_approved:false` until the prospective gate genuinely passes.
