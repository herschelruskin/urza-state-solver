# DACK v40 large ORIGINAL-v5 teacher corpus — frozen source design

**Research-only.** Original v5 is preserved. No v40 student model or prospective policy is approved. These are v5 *decision annotations* from the original bounded-lookahead teacher; they are NOT new physically observed action-regret / goldfish win labels.

## Rationale

The actual untouched 115k physical N256 comparison was v5 132/256 by T2 (51.5625%), frozen v27 106/256 (41.40625%) and v33b bottom-only 111/256 (43.359375%). The early v14 actual-v5 imitation corpus trained on only 144 independent groups with 538 visited stage records, and on a 40-group teacher-heldout set the learned bottom classifier's ~64% accuracy did not outperform structural first. v37 trained physical action-regret on 384 independent groups; its disagreement enrichment was v13-proxy-selected rather than actual-v5-selected. New independent actual-v5 annotations are justified, but their value must be demonstrated on independent games.

## Dedicated source partitions (no collision with old consumed results)

| Split | Original game IDs | Independent physical groups | Guaranteed stages 0,1,2 |
|---|---|---:|---:|
| TRAIN | 140000..144095 | 4096 | 12,288 |
| DEV | 144096..144607 | 512 | 1536 |

Each deal is a separately seeded 99-physical-slot London game, with a known seat and eight independent full-deck per-stage Fisher–Yates reshuffles. The source group identifier is `one_key_34:{game_id}`. Every source group contributes **one** observation at each early London stage 0/1/2, where stages 0/1 both retain seven cards but are NOT equivalent. If the original v5 already kept before an early stage, ask the original v5 `batch.evaluate_keep` on that stage's *predealt real physical seven*, using the same original assertive KEEP threshold formula. This is a genuine v5 **counterfactual stage action** rather than a *naturally reached* v5 action. The record explicitly says whether v5 actually visited the stage.

Also record every later naturally visited v5 London stage 3..7. At a visited stage use the EXACT original `ref.choose_keep` history without re-evaluating it. Record teacher KEEP/MULL, original raw score, T1 estimate, original threshold, refinement flag, chosen top12 candidate, retained hand, ordered London bottoms, all top12 structural candidate rows, seat, stage and observed 7. Record only unseen92 **card-name counts**, not the realized future deck order. Group all rows by independent game ID. v5 original hypothetical sample rollouts remain dependent observations, not independent hands, and are NOT real `Qkeep−Qmull` labels.

Run frozen v27 keep and v33b bottom choice on the *same* game ID/seat/stage/physical seven in a **separate Python interpreter** because both code paths mutate the global simulator module. The baseline census records v27 Qkeep, frozen continuation, actual v27 keep decision, actual v33b bottom, v14 bottom and naturally reached status. The pool joins on group ID, seat, stage, 7-card ordered list and keep_n; fails on mismatched source hashes, gaps or duplicates. It identifies the first actually reached early-stage disagreement (both policies had to reach the stage), plus a separate unconditional all-three-stages disagreement census. No outcome labels enter this comparison.

## Operational rollout / budget protection

1. **Pilot 140000..140003, 4 groups**: compile all scripts; verify the v5 hypothetical sampler is invariant to permutations of unseen92; run real v5 stage queries and frozen v27 in separate processes; assert 3 early-stage rows for every game and merge. `dack_v40_actual_v5_pilot.yml` runs on its own limited push trigger.
2. If the pilot passes, use the **opt-in only** `dack_v40_4096_real_v5_teacher.yml` manually, choosing train or dev. Training is 64 shards ×64 independent games, max eight parallel workers. Dev is 16 shards ×32 independent games. Shards are archived with their fingerprints, raw true-teacher records and joined census. No threshold fitting, policy promotion or actual goldfish outcome screen occurs in these workflows.
3. After a successful training source run, run group-disjoint learning curves **within training** (e.g. 128, 512, 1024, 2048, 4096 original physical groups). The early stage observations and 12 candidate bottom rows do NOT multiply the number of independent groups.
4. Evaluate on 512 **untouched** DEV groups, stratifying by stage, actual-reached status, conditional first v5/v27 disagreement, and direction of decision difference. Report separately: v5 bottom top1 accuracy vs naive structural-first; v5 KEEP sensitivity/specificity and balanced accuracy; first-action disagreement recall in both directions; model calibration, runtime and student changed final London paths. Do not choose the most favorable model on a physical prospective holdout.
5. Only then obtain **new independent true physical KEEP-vs-MULL action regrets** with a matched bottom and frozen continuation, and strictly prospective end-to-end T1/T2/T3 tests against frozen v27, v33b and v5. The 512 dev teacher annotations are not independent physical outcome validation.

**Cost warning:** the original 115k v5 N256 cohort consumed ~6158 s of total v5 game runtime (~24 s / outer game on that run). Extrapolating very crudely, 4096 original v5 deals might require ~27 CPU-hours **before** any extra counterfactual-stage v5 evaluations and CI overhead. This is a budgeting estimate, not a measured v40 running-time prediction. Pilot performance should govern scheduling/cost, and partial train-source shards should not be called a completed 4096-group corpus.

## Source implementation and execution gate

- `dack_simulator/validation/v40_collect_actual_v5_teacher.py`
- `dack_simulator/validation/v40_collect_frozen_v27_matched.py`
- `dack_simulator/validation/v40_pool_true_v5_disagreements.py`
- `.github/workflows/dack_v40_actual_v5_pilot.yml`
- `.github/workflows/dack_v40_4096_real_v5_teacher.yml`

No student fitting should occur until the pilot is a verified pass and complete source shards have passed the join/integrity census. The earlier v40 *384-group physical-regret proposal* is a separate later phase; it is not silently pooled with these teacher annotations or treated as an interchangeable observation type. Existing 135k/137k proposed holdouts remain untouched.
