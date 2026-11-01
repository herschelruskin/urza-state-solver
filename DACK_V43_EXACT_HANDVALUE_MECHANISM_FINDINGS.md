# DACK v43 — source-verified original-v5 candidate microscope, physical hand value and bottom hybrid

**2026-11-01. COMPLETE. Research only.** Branch `dack-v43-v5-candidate-mechanism-20261101`. No student fit, no model promotion, no claims of multiplayer cEDH win rate. Original v5, v27, v33b and v42 branches left untouched.

## Critical finding: v27 fails to value certain legal seven-card resource combinations

The original v5 engine evaluates each opening hand using short actual gameplay lookahead (typically eight, sometimes sixteen hidden future rollouts, beam60); v27 has a random-forest conditional T2 value trained on the frozen v14 bottom, with 256 source physical groups × eight London stages × four strict physical continuation futures per stage. v27's broad learned hand features can smooth away high-order mana lines. It is NOT simply a lower-fidelity implementation of the same v5 policy: v5 also has a distinct objective and additional assertive KEEP thresholds as diagnosed in v42.

### Independently simulated truth for *exactly the same* candidate

The no-new-simulation v43 same-hand analysis reused corrected v34c true physical QKEEP (32 independent real strict-beam160 futures per selected hand) and previously inspected original 115k first-decision v5-v27 disagreements. It **excluded 41 cases** where v5, v27, or the physical v33b forced-KEEP bottom differed; 59 remained. All 41 early stage0/1 first-disagreement cases naturally have no bottom and were included. The physical target is 32 noisy trials, not a known exact probability, and the cases were *selected by teacher-student disagreement*, not sampled from the general opening-hand population.

Read-only job [41356561262](https://github.com/herschelruskin/urza-state-solver/actions/runs/41356561262) PASS; source `benchmark_results/v43_v5_v27_same_hand_physical_K_calibration.json`.

| Among matched 59 v5-v27 original conflicts | N | Mean v27 predicted PbyT2 | Mean independent physical PbyT2 |
|---|---:|---:|---:|
| v5 KEEP, v27 MULL | 16 | **.1292** | **.4434** |
| v5 MULL, v27 KEEP | 43 | **.4657** | **.2573** |
| All early 7-card stages 0/1, mixed direction | 41 | .4563 | .3803 |

These are directional errors on this *selected* diagnostic set and do NOT imply v27 is globally miscalibrated or that such a large difference generalizes to random hands. v5's separate utility uses PbyT2 + .5×PexactT3: across 41 early matched hands, v5 U mean .5838 versus physically estimated U .6185. The **v5 U and v27 PbyT2 have different targets**, so do NOT compare their raw MSEs as an apples-to-apples estimator ranking.

The standout original first-seven hand `115025` (seat0): **Ancient Den; City of Traitors; Coalition Relic; Gemstone Caverns; Mox Diamond; Plains; Urza's Saga**. v5's original eight-sample estimate was **1.000 PbyT2** and its 16-sample view also **1.000**; original v27 forest estimated only **.252 PbyT2** and rejected the hand. The corrected independent 32-future physical strict-beam160 QKEEP was **31/32 = .96875 PbyT2**, also byT3. This is direct proof of a **large missed fast-hand pattern in v27 on this particular seat/hand**, not a mere change in risk preference or London threshold. The rare conjunction involving City, Gemstone, Diamond and Coalition Relic is a reasonable mechanistic lead, **not an action-trace-verified causal card combination yet**.

## All-eight original candidate profiles

The source `dack_simulator/validation/v43_candidate_microscope.py` first reproduces original v5's exact selected hand, bottom, raw estimated value, refinement flag and visible seven on each real archived first-disagreement stage. It then computes every legal structural top-12 option's **original-seeded beam60 EV8** and separately EV16 (not claiming previously pruned candidates were actually visited by branch-and-bound), plus the frozen v14 teacher-choice vote, frozen v27 conditional PbyT2 estimate, v18 proxy when available, and analytic proxy. Thus labels are original-v5 actual parity, and all-candidate profile scores are separate replays under the original scoring mechanism. It never uses realized future draw order to value a candidate.

Successful profiles: `benchmark_results/v43_candidate_profiles/v43_candidate_{115003,115004,115005,115025,115066,115086,115119,115153}.json` (eight profiles). Workflows: initial [41356419867](https://github.com/herschelruskin/urza-state-solver/actions/runs/41356419867), six-way collection [41356639928](https://github.com/herschelruskin/urza-state-solver/actions/runs/41356639928), and single-source archive retry [41356741559](https://github.com/herschelruskin/urza-state-solver/actions/runs/41356741559). The six-way workflow was marked failed due to one parallel commit conflict, *not a scoring failure*; its 115086 archive was retried and succeeded. All eight archived JSONs verified teacher parity.

Examples:
- At source 115003 stage2, v5 bottomed Scroll Rack (candidate6); original EV8 .625, refined EV16 .5625. v14/v27 bottomed Trinisphere (candidate0), original EV8 .500, EV16 .500. Same v27 conditional PbyT2 approximately .49 for both. V5 MULL despite ranking its own candidate above others, due to v5's strict continuation cutoff.
- At source 115119 stage2, original v5 bottomed Charitable Levy (candidate3), EV8 U .6875 vs EV8 U .5625 for v14's Deafening Silence bottom (candidate0), with v27 Q estimates .166 vs .155. Here v5 KEEP and v27 MULL. The v5 and v27 rankings disagree, but **the EV8 ranking need not be physically correct**.
- At source 115153 stage2, v5 bottomed Blast Zone (candidate3), original observed/refined U .6875 vs .500 EV16 for v27's Floating Shield bottom. This score superiority did NOT survive independent physical comparison.

## Independent paired physical experiment for four bottom-choice pairs

The v43 `v43_physical_pair_bottoms.py` used 32 independently reshuffled **same 92 physical slot identities** per hand, with same seat, same stable gameplay seed and same true beam160 terminal rules within each pair. The hands and bottoms were frozen before these fresh results; zero new original v5 lookahead. Only the chosen legal retained 6-card hand/bottom changed. This intentionally reused *selected, already investigated* first-disagreement sevens: new physical futures are independent, but the selection is not representative and does NOT establish global bottom superiority.

Source archive: `benchmark_results/v43_independent_physical_bottom_pairs/v43_bottom_115003_N32.json.gz`, similarly 115004, 115119, 115153. All four physical jobs SUCCESS [41356820636](https://github.com/herschelruskin/urza-state-solver/actions/runs/41356820636).

| Original selected gid | v5 selected bottom | v14/v27 bottom | v5 physical byT2 | v27 physical byT2 | Net v5−v27 T2 games |
|---|---|---|---:|---:|---:|
| 115003 | Scroll Rack | Trinisphere | 4/32 | 4/32 | 0 |
| 115004 | Portable Hole | Floating Shield | 7/32 | 7/32 | 0 |
| 115119 | Charitable Levy | Deafening Silence | 9/32 | 9/32 | 0 |
| 115153 | Blast Zone | Floating Shield | 6/32 | 9/32 | −3 |

In the first three examples, despite differing v5/v27 bottom choices and notably different small teacher EV estimates, the actual T2 counts were identical. The fourth favors v27 by 3/32, so the selected four do **not** support an across-the-board v5 bottom advantage. This does NOT contradict v42's larger finite-sample **+7 v5 net T2 games** among 70 same-kept-stage different-bottom cases, because the latter samples different hands and actual matched original future orders. Nor can v43's 128 paired futures over four *selected original groups* be treated as N128 independent opening-hand decisions.

## Architectural interpretation and falsifiable next steps

**Primary identified missing capability:** teacher's in-hand rules-engine search (including interactions among fast land sources, Mox Diamond, pregame Gemstone Caverns, three-mana ramp and charge counters, tutor-specific resources, restricted white requirements, tapped/untapped timing, and Boonweaver contamination handling) captures nonlinear feasibility of deployment that a tiny-source generic random forest with at most four physical outcomes per stage does not. A 347-feature classifier copied v5 KEEP labels ~86% on natural stages yet reproduced v5's action on only ~29% of physically consequential old disagreement cases. Earlier v41 regression based on only 125 physical groups failed fresh T2 conditional test (−0.95pp). Training on more of the **same** coarse labels or moving generic cutoff cannot address omitted exact resource-constraint transitions.

**Next architectural candidate:** small, deterministic **line-feasibility front end**, returning explicit audited reachable minimum turn / mana-white requirements / untapped sequencing / tutor availability for the *visible candidate kept hand*, with symbolic unknown draw probabilities and no hidden physical future order. Reuse existing audited action engine where feasible, but restrict horizon and canonicalize equivalent resources to be faster than full v5's 8×12 searches. Test deterministic first-2-turn resource and deployment witnesses against physical gameplay on confirmed fast hands *including 115025*, then augment a physically calibrated KEEP-vs-MULL estimator. Keep v5's own bonus/continuation objective separate and only compare on matched scales.

Run ablations with controlled same-hand physics rather than conflating bottom decisions and keep decisions; include new random and disagreement-stratified **group-disjoint** physical K/C calibration; evaluate first on unobserved 150k+ development groups and reserve untouched 149k sealed acceptance. An optional selective-v5 fallback is a computational performance compromise, but this has not yet been evaluated.

**What is not established:** no v43-trained student, no new final population T2 win-rate, no proof that source115025's proposed card combination is the specific winning action trace, no unbiased calibrated general win-probability model, and no demonstration that new deck substitutions transfer.
