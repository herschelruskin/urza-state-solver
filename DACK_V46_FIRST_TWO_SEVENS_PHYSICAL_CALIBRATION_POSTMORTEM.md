# DACK v46 — first and second London seven physical calibration: complete negative result

**2026-11-02. Model rejected for promotion. v43 remains best confirmed fast challenger.** v46 was developed on isolated `dack-v46-early-seven-physical-calibration-20261101`, with all older source solvers and benchmarks preserved and **155k sealed acceptance never opened**.

## Experiment and source data

- Previously matched original-v5 vs v43 on 151k N128: byT2 73 v5 vs 65 v43; **44 different kept stages explain +9 net T2**, same-stage different bottom/hand 30 deals explain −1, identical 54 deals explain 0. Actual first decisions differ in stages0–2 for 34/44. Earlier v45 real physical actions favored v5 on selected conflicts (+8.416pp T2 with group/K/C CI [−0.249,+16.406]pp).
- We accordingly isolated stages0 and1, each a seven-card no-bottom London hand. **Stage0 is always seen. Stage1 is seen only if stage0 mulled.** All stage≥2 stages were preserved as frozen v43.
- Independent train deals **160000..160127, N128**, independent dev **160128..160191, N64**. For each source deal evaluate stages 0 and1 as distinct *hypothetical* visible sevens, 24 fresh blind unknown92 future gameplay outcomes each = **384 stage states, 9,216 real strict beam160 KEEP games**.
- Independent real MULL continuation: 4 seats×2 stages×128 independent full99 redraws = **1,024 strict goldfish futures** using unchanged frozen v43 for all later decisions. First 64 of each cell provide train-only physical C; last 64 are reserved for independent dev scoring with two-source group/K/C bootstrap.
- Fit **80-tree depth7 minleaf8 physical Q2 residual forest**, with source legal seven/card capability and pair features, excluding literal card one-hot, using original frozen v43 Q2 as anchor. Output: `Q46=clip(Q43 + .5 * clip(model_residual,−.25,+.25),0,1)`. Override original v43 at stage0 or stage1 only if `|Q46−physical_Ctrain|>=.06`; otherwise preserve v43 KEEP/MULL. No original v5 teacher labels, future physical order, or conditional stage-reach leakage in fit.
- Original-source, model hash, features, goldfish engine and 99 card slots validated. Exported pure-Python scorer was numerically checked by refitting original sklearn forest on training-only physical K labels and comparing predictions; 32 deterministic parity checks passed before opening new full-game 161k.

## Development N64: directional criterion technically passed, but coverage was nearly zero

On **128 hypothetical stage observations** across N64 independent development deals, the model changed **just one** stage0 decision (MULL to KEEP) and **zero** stage1 decisions.

| Heldout *conditional one-step* estimate | v46−v43 |
|---|---:|
| T1 | −0.0041pp |
| T2 | **+0.4883pp** |
| T3 | +0.2319pp |
| T2 group/K/C bootstrap 95% | [0,+1.5747]pp |
| T3 group/K/C bootstrap 95% | [0,+0.7813]pp |

Stage0 contributed +0.9766pp (one of 64 state changes); stage1 had 0/64 changes. The development gate was predefined as nonzero action changes, positive T2 mean, T3 decline no worse than −2pp, and therefore technically passed. **But a single successful development intervention is not sufficient evidence of a broadly learned rule**. The zero lower confidence limit is a product of resampling an effect concentrated in one source group, NOT strong proof of general improvement.

Additional read-only diagnostic on the 64 independent dev groups: frozen v43 predicted Q2 was very close to empirical physical QKEEP **on average**:
- stage0: v43 Q2 mean 0.17158, 24-physical-future mean 0.18294 (prediction underestimation ~0.01136); v43 chose KEEP on 10/64 hypothetical stage0 hands
- stage1: v43 Q2 mean 0.20030, physical mean 0.19466 (prediction overestimation ~0.00564); v43 KEEP on 15/64 hypothetical stage1 hands
- against the **independent C-eval64** conditional benchmark, only 4 stage0 and 4 stage1 predictions disagreed with the empirical K−C sign, with 24-future hand label and shared C uncertainty. This is merely a noisy diagnostic; labels are not proof of true optimal decisions.
- Consequently an *average* Q2 calibration will not necessarily recover rare high-value combination hand errors. The current correction simply barely disagrees with v43.

Sources `benchmark_results/v46_first_two_sevens_160k_dev_N64.json`, `models/v46_first_two_sevens_Q2_residual_RESEARCH.json`, 32 archived original source shards; [physical source collection and training run 41364824206](https://github.com/herschelruskin/urza-state-solver/actions/runs/41364824206), success.

## Independent complete-policy N256 — no primary T2 gain

After dev passed, tested the frozen v43 baseline versus v46 on **256 new independent physical 99-card deals `161000..161255`** using isolated Python interpreters, identical seat, initial London sevens, stateless chance, strict original beam160 and exact retained bottoms. The first workflow attempt [41366144376](https://github.com/herschelruskin/urza-state-solver/actions/runs/41366144376) failed at a standalone Python import-path check **before any 161k gameplay**, fixed without changing physics/model; second workflow [41366220195](https://github.com/herschelruskin/urza-state-solver/actions/runs/41366220195) passed parity and all 8 physical shards and pool.

| Matched independent 161k N256 | v43 | v46 |
|---|---:|---:|
| by T1 | 12/256 | 12/256 |
| **by T2** | **121/256 (47.266%)** | **121/256 (47.266%)** |
| by T3 | 204/256 (79.688%) | 205/256 (80.078%) |
| Mean number of cards kept | 5.4727 | 5.4805 |
| Gameplay-only sum across N256 | 102.36s | 102.73s |

**T2 delta 0 net games, exactly 0pp**, paired bootstrap CI [0,0] *for the zero-observed-difference sample*, **not** proof of theoretical equivalence. T3 net +1 game (+0.391pp), paired bootstrap CI [0,+1.172]pp, entirely unconvincing at N256. Only **3/256 games** changed final kept stage; v46 kept earlier in two and v43 earlier in one. The other **253/256** had the exact same kept stage, hand and ordered bottom, and exact terminal gameplay parity.

Policy stage1 reach (the second seven) was **212/256** for v43 and **210/256** for v46: the second seven is not always seen, and must not be weighted as if it were a fresh seven reached by everyone during full gameplay.

Results `benchmark_results/v46_161k_N256_full_policy_paired.json` and eight complete compressed 161k raw shards, [full successful paired workflow 41366220195](https://github.com/herschelruskin/urza-state-solver/actions/runs/41366220195).

## Disposition and better architectural direction

- **Reject v46 as an improvement**, not because it harmed physical win rate, but because it did not change the target behavior often enough to recover any of v5's established same-seed T2 advantage. No v46 model is approved.
- Keep v43 candidate-max Q2 before KEEP as frozen baseline, and preserve original v5 simulator. The current v46 source and 161k cohorts are now consumed; cannot be used as a fresh acceptance set or repeatedly tune thresholds. Do not reinterpret matching T2 counts as model equivalence.
- The next model should target **rare conditional early-action errors and their game-path mechanisms**, not average physical-QKEEP calibration. Potentially reconstruct a *bounded exact visible-hand mana/tutor/T1–T2 line feasibility evaluator* for the first two sevens, or a **selective physically evaluated fallback** triggered by observable risk/uncertainty of a hand that the v43 Q2 model is likely to miss. Such a detector should train on broad random source hands plus separately accounted rare line-rich hands and preserve correct full99 continuation. It must be predeclared and tested on new independent real complete-game seeds.
- Original v5's first-/second-seven +0.20 assertive KEEP veto alone helped v5 on the old 115k sample, but blanket threshold retuning is inappropriate: some v5-only early KEEPs also have positive physical action value.
- No claim about physical deck-transfer performance after one- or two-card changes or actual multiplayer cEDH match win rates.

**Scientific takeaway:** The early-seven objective was isolated and measured correctly, but the current modest forest correction did not learn a useful action boundary. Physical calibration averaged across ordinary hands cannot substitute for recognizing the specific rare hand combinations driving actual early KEEP/MULL regret.
