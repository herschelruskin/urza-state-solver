# DACK v44 physical candidate regression — completed, FAILED development gate

**2026-11-01. No new policy promoted. Prospective 155000..155255 remain sealed.** Branch `dack-v44-physical-candidate-values-20261101`.

Original previous v43 improvement remained real on new 151k N256: byT2 122/256 vs frozen v27 111/256; matched original v5 on 151k N128 reached 73 byT2 vs v43 65. Thus we tried the explicitly identified weakness: off-policy candidate values trained mainly from selected bottoms.

## Exhaustive physical candidate collection: SUCCESS

[GitHub Actions run 41358924863](https://github.com/herschelruskin/urza-state-solver/actions/runs/41358924863). All 16 N16 physical train/dev shards and Python model-fitting/parity job passed, after earlier four-deal smoke [41358725603](https://github.com/herschelruskin/urza-state-solver/actions/runs/41358725603).

- 192 independent physical training deals, 2064 complete legal candidate bottom rows, 8 independent strict beam160 unknown92+chance futures each => **16,512 real retained-hand gameplay trials**.
- 64 separate independent physical dev deals, 688 legal candidate rows, same 8 trial count => **5,504 real gameplay trials**.
- Each full 99-slot source deal contributed one of stages 2,3,4,5, in balanced rotation. Each different candidate bottom used the SAME eight unseen92 physical shuffle futures and same corresponding stable chance seeds.
- All source rows are archived gzipped at `datasets/v44_original_legal_candidates_154k_shards/`; exact seven, unknown92 counts, legal finalists, baseline v27 Q2, actual T1/T2/T3 outcome arrays.
- No v5 teacher labels or lookahead, no hidden future order in model decisions, no game IDs shared between train and dev. Source groups, not physical rollouts or candidate rows, are independent original hands.

## Frozen v44 physical candidate residual fit: complete but NOT approved

`models/v44_all_candidate_Q2_residual_RESEARCH.json`, SHA256 `2c326278eb3119d32fc7ea0f6cc56a581588d8598ed918f903c66a9ee48eac4a`. Fixed 96-tree depth8 leaf12 random forest fitted to `physical Q2 − frozen v27 predicted Q2`, with 167 functional/line features and grouped candidate weighting. The predeclared bounded policy computed `new_Q2 = clip01(v27_Q2 + 0.5×clip(residual, -0.20,+0.20))`. It would use that same selected hand for the KEEP decision; stages0/1/6/7 remained unchanged v43.

## Group-separated 64-hand development results: REJECT

Full report `benchmark_results/v44_all_candidate_Q2_residual_dev_N64.json`.

| Condition | Actual on 64 dev deals | Predeclared gate |
|---|---:|---|
| Changed picked candidate | 19/64 | — |
| Mean physical candidate byT2 change | **0.000pp** | Strictly positive |
| Mean physical candidate byT3 change | **−2.7344pp** | ≥−2.0pp |
| Physical joint group + eight paired future bootstrap byT2 | **[0,0]pp** | — |
| Equivalent on all eight T2 futures | **19/19 changed bottoms** | — |
| T3 change among changed choices | **5 worse, 0 better, 14 tied** | — |
| KEEP/MULL threshold status changed | 2/64 | — |

The gate failed T2 and T3. **We did not create the 155k sentinel trigger and did NOT open the 155k physical comparison.** It remains available as a future independent evaluation cohort, but future variants must be frozen without any 155k peeking and explicitly declare the dev-driven model development decisions.

## Why regression could not improve on the selected development distribution

Read-only independent source audit `benchmark_results/v44_154k_dev_candidate_signal_equivalence_audit.json`, [successful workflow 41360031779](https://github.com/herschelruskin/urza-state-solver/actions/runs/41360031779):

- 27/64 deals had physically different byT2 signatures among at least some legal candidates. 37/64 had identical T2 signatures for **every** candidate.
- Yet **v43's original max-Q2 bottom was tied for the maximum empirical eight-future byT2 in 62/64 groups**. The two with nominal regret were stage3 and stage4. Selecting a hindsight max physical candidate yields at most +1.171875pp across all 64 groups, itself upward-biased by max selection noise.
- The new model changed 19 choices; EVERY ONE was tied with v43 on all eight physical byT2 trials. Some were ordering differences in bottomed identical `Plains` copies, or differences among non-T2-impacting Auras, protection and disruption. T3 harmed 5 of these cases, including a Brainstone vs Jeweled Amulet choice with severe T3 harm (−7/8).
- Therefore a generic low-dimensional physical Q2 residual model adds essentially no new information **where the already-improved v43 candidate picker is near saturated**. This does not establish physical optimality globally or under changed decks: N64 and N8 futures per candidate are noisy, stage selection is only 2–5 and a separate outer new cohort could differ.

## Recommended next direction

**Do not retry random-forest physical candidate ranking with slightly modified hyperparameters on already consumed 154k dev.** The remaining original-v5 gap is plausibly predominantly early London stage acceptance, conditional value versus actual mulligan opportunity cost, and/or rare combination-specific states absent from a uniformly random 64-hand dev sample.

First perform a read-only *same-seed* v5-v43 N128 full-game stage-vs-bottom decomposition on the already collected 151000..151127 reference shards. Find how many residual v5-only T2 wins arise from different kept stages versus same-stage different bottoms. If stage selection dominates, collect **targeted early KEEP-vs-MULL physical experiments** anchored to actual v5-v43 first conflicts and physical common continuations, not another generic classifier and no reusing the old v5-v27 first-conflict selection.

An alternative candidate training source should condition on *consequential* bottoms (actual positive physical T2 regret), with greater future count per selected hand, and group-disjoint validation. A new acceptance cohort must remain sealed until hypothesis, code and thresholds are frozen.

No actual multiplayer cEDH winning-rate claims can be made: all T1/T2/T3 outcomes are goldfish Dack deployment.
