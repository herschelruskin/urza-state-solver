# DACK v26: frozen v25 diagnosis and independent real-outcome repair

**Research-only branch:** `dack-v26-trace-repair-20261031`. Keep v5 reference and previous v22 and v24/v25 models unchanged. No learned policy is approved.

## Why v26 is necessary

The fully archived v25 prospective test (96k physical IDs, N=256) showed v5 by-T2 127/256 versus v22 103/256, **−9.375 percentage points**, 95% paired bootstrap interval **−15.234375 to −3.515625 pp**, paired McNemar p=0.0036899643. Despite an observed ~58x speedup, the trained keep policy does not currently match the beam-based reference.

A **read-only loss trace** on the frozen 96k outcomes found:

| Condition | N | Interpretation |
|---|---:|---|
| v5 T2 success, v22 failure | 44 | Lost by-T2 games |
| v22 T2 success, v5 failure | 20 | Gained by-T2 games |
| Both by T2 | 83 | Paired concordant successes |
| Neither by T2 | 109 | Paired concordant failures |

Among the 44 lost cases, 36 had different final London keep depths; eight kept the same number of cards but different cards. **No loss involved identical final kept card multiset**, and all 256 games had zero same-final-hand different-outcome anomalies. Of 44 losses, 32 involved v22 keeping **more** cards than v5, four keeping fewer, and eight the same number. v22 also kept more cards in 19/20 of its T2 gains: a blanket "mulligan harder" heuristic could destroy real gains. Tracing observed outcomes reveals failure categories, not a counterfactual causal guarantee that the reference's decision had higher expectation in any particular initial hand.

**The primary repair hypothesis** is insufficiently trained conditional true-utility and London continuation estimates, rather than a hard gameplay-engine disagreement.

## Frozen v26 experiment

All 99 physical slots, seats, actual post-keep beam160 strict rules and stateless dice remain fixed. The frozen v14-128 bottom-choice model remains fixed, so only the **keep/reject** policy is allowed to differ.

1. Collect v26 93k *training* group IDs `93000..93255` (256 independent outer games) at all eight naturally shuffled London stages; one selected v14 bottom candidate per stage, with four independently shuffled hidden futures per candidate. That is 8,192 actual beam160 goldfish outcomes.
2. Separately collect v26 94k *validation* IDs `94000..94063` (64 groups; 2,048 actual outcomes). No model uses their observed game outcomes for fitted parameters.
3. Train fixed, preselected 192-tree depth-nine real-utility random forest (minimum leaf six) on 2,048 training hand states, using the original visible-only feature schema, no secret future order or labels. Compare v22 and v26 expected utility prediction error on separate 94k hands.
4. Compute four seat-specific physical London continuation tables from the new frozen value model using existing independent 92k unlabeled physical deals and the original free-first-seven DP recursion. Enforce model, deck and bottom-student SHA hashes.
5. Only after model and thresholds are archived, test v26 versus frozen v22 and strict beam-v5 on **fresh 97k** physical IDs `97000..97255`, N256 matched pairs; report cumulative T2 primary endpoint, T1/T3 secondary, paired bootstrap CIs, exact discordance and CPU. No changes to v26 from any 97k result without designating it development and reserving a further independent test.

No 96k loss example is used as a training input, model-label feature, threshold tune, or 94k validation data. The 97k cohort is reserved prospectively.

## Interpretation

These studies estimate actual **goldfish Dack deployment** under the modeled no-opponent engine, not multiplayer cEDH win probability. There is no model promotion without independent paired game evidence. A larger model that improves standalone expected-utility MSE may still reduce expected full-game performance if the London continuation selection is systematically biased or if candidate bottom selection is limiting.

If v26 fails to improve, prioritize an independently trained *keep-vs-mull action-value* policy with matched counterfactual futures and richer bottom candidate support, rather than silently adding arbitrary v5 threshold offsets.
