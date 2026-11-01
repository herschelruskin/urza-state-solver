# DACK v43 — source-grounded original v5 candidate ranking, controlled hybrids and fresh coupled-value test

**2026-11-01. Experimental v43 policy NOT promoted.** All earlier v5/v27/v33b/v40/v41/v42 branches preserved. This report covers runs completed and fully verified as of writing. No claims about real four-player multiplayer victories; all T1/T2/T3 figures are optimistic goldfish Dack deployment.

## Why original v5 makes different decisions

The strongest *confirmed architectural difference* is **joint search over candidate kept hands before making the KEEP/MULL decision**.

- Original v5 screens up to 12 structurally legal London bottoms, then runs actual beam60 sampled T1–T3 gameplay for each candidate, yielding `U=P(T1)+P(exact T2)+0.5P(exact T3)`, with 8 deterministic candidate-specific sampled futures and optional 16-future refinement. It uses the **winning candidate's** score against an aggressive historical continuation threshold; it does not decide on a predetermined bottom. The difference includes coarse/noisy sample estimates and original engine candidate ranking.
- Frozen v27 selects a bottom using a separately trained v14 *teacher-imitation candidate-choice classifier*, then evaluates **only that candidate** using a different T2-only random-forest QKEEP and its own offline DP continuation. Its feature model was trained primarily on frozen v14 candidate bottoms, so maximization of Q over other bottom candidates is an out-of-distribution intervention.
- v33b fixes some bottom choices after frozen v27's keep decision but does not recompute the keep decision for that substituted hand. This is a coupling inconsistency; v43 closes it by scoring the bottom and deciding KEEP/MULL with the SAME selected hand.

## Four full original-v5 top-finalist profiles, archival parity proved

Original v5 `batch.evaluate_keep` was called on identical physical seven, known unseen92 card multiset, stage and seat from original 115k traces. For each of the four preselected earliest actual v5/v27 conflicts (IDs 115003, 115004, 115012, 115017), exact selected hand, bottom, original raw score, T1 sampled score and refinement matched archived original v5. The original unpruned EV scoring of every one of 7 or 12 structurally legal candidates was then recorded at the teacher's original n8 (and where refined, n16) beam60 budget alongside the original frozen v27 candidate's Q2 and v14 classifier votes. Actual original branch-and-bound prunes some candidates; full scorer values do not claim to be old trace's executed prefixes.

Artifacts: `benchmark_results/v43_original_v5_candidate_profiles/v43_original_v5_candidates_<gid>.json`. Successful GitHub Actions [41356582570](https://github.com/herschelruskin/urza-state-solver/actions/runs/41356582570).

**Example game 115017**, five cards (two bottoms), seat1:
- Frozen v27's v14 candidate bottoms Ruins of Trokair + Paladin Class; v27's Q2 estimate 0.04050 **below its 0.12879 continuation** ⇒ MULL. Original v5 beam60 simulated utility of this bottom: 0.0625.
- Original v5 picks bottom Fellwar Stone + Paladin Class, teacher U8 **0.625**; frozen v27's **own** Q2 for that alternative is 0.25070 **above its continuation** ⇒ KEEP if selected. The frozen v27 Q2-max bottom (Tezzeret + Paladin Class) is estimated 0.26705 and also would KEEP.
- Thus, the **independent bottom selector can cause a mistaken KEEP/MULL**, not merely bottom the wrong card after keeping.

**Example game 115003**: original v5 picked bottom Scroll Rack with U8=0.625 (U16 refined=0.5625), while v14 picked Trinisphere (v5 U8=.50). Original v5 still MULL because refined U=.5625 < aggressive six-card cutoff .63025, whereas v27 Q2=.48986 exceeds its continuation .22252 and KEEP. This demonstrates a *separate threshold/utility incompatibility*. No same-scale subtraction of U8 vs Q2 permitted.

## Independent physical check on the two selected examples

Each candidate for game 115003 (7 candidates) and 115017 (12) was independently evaluated with 16 common, blinded hidden92 reshuffles and strict real beam160, using matching chance seeds by future. This recheck was **conditional on deliberately preselected old conflict sevens**, not a random-sample generalization or a novel full-game benchmark. Successful GitHub Actions [41357108798](https://github.com/herschelruskin/urza-state-solver/actions/runs/41357108798). Raw results: `benchmark_results/v43_independent_candidate_physical/`.

- For 115017, original v5 selected bottom produced **4/16 by T2, 16/16 by T3** versus frozen v14 original bottom **2/16 by T2, 9/16 by T3**. v27's Q2-max alternate produced the same **4/16 T2, 16/16 T3** as v5-selected in this tiny sample. This is evidence for meaningful real hand-combination scoring.
- For 115003, **all seven** candidate bottoms gave **0/16 by T2**. Original v5 sample had U8=0.625 for its selected Scroll Rack bottom, while independent strict sample U=.4375, lower than 0.5 on the original v14 Trinisphere bottom. This is *direct evidence of candidate-specific Monte Carlo noise / winner-selection risk*. Do not treat the original v5's 8-future maxima as perfectly calibrated probabilities.

## Original KEEP-stage fixed, swap only bottom selector (exact physical 115k N256)

On each archived physical 115k deal, replayed actual original v5 terminal gameplay with exact parity, then retained original v5's final London stage and substituted **only v14 candidate bottom at that stage**, using original unseen physical order, strict gameplay beam160 and stable chance. **No original teacher lookahead was needed.**

| Same 256 deals, original v5 stopping stage | By T1 | By T2 | By T3 |
|---|---:|---:|---:|
| Original v5 candidate bottom | 7 | **132** | **214** |
| Frozen v14/v27 candidate bottom | 6 | **121** | **197** |

Bottom changed in 134/256 deals. For byT2, among changed bottoms v5 won 14 unique games; v14 won 3: net **11 real deployments** / **4.297pp** on same matched cohort, CI v14−v5 = [−7.422,−1.172]pp. Again this is previously inspected 115k, not a new prospective acceptance sample. Compare with v42 threshold-only original-v5 ablation −8 net byT2 games to see both contributors, but **do not add their effects as independent causes**.

Physical outcome and raw replay: `benchmark_results/v43_fixed_v5_stage_v14_bottom_N256.json`, `benchmark_results/v43_fixed_v5_stage_v14_bottom_shards/`; [Actions 41356718429](https://github.com/herschelruskin/urza-state-solver/actions/runs/41356718429).

## v27 self-inconsistency census on old 115k N256 (read only)

All 256 v27 original candidate Q2 values, retained hands, bottoms, thresholds and KEEP/MULL choices were reproduced exactly from original frozen forest/model. Frozen v27's maximum predicted Q2 candidate differs from its **actual v14-chosen** candidate in **102/256** physical games. Replacing v14 choice with max-Q2 on the first reached original v5/v27 conflict would switch **11/39** original v5-KEEP/v27-MULL cases toward v5 KEEP; it would not repair the other 28 or the 61 v5-MULL/v27-KEEP conflicts. No claim that alternative predicted maxima are calibrated.

`benchmark_results/v43_v27_candidate_maxQ2_readonly_115k_N256.json`; [Actions 41356828241](https://github.com/herschelruskin/urza-state-solver/actions/runs/41356828241).

## Frozen *new* 151k N256 physical experiment: self-consistent MAX-Q2 policy

Experimental, new physical 99-card outer groups 151000..151255, frozen policy and models before opening outcomes; each policy in isolated Python interpreter; identical physical seat/shuffle, original stable dice, strict beam160. The **ONLY policy change** versus v27: choose highest estimated Q2 from original legal top12 candidates and decide KEEP using Q2 for **that exact chosen hand**, rather than using v14's bottom-classifier choice and only evaluating its Q2. No extra v5 beams.

| Frozen policy on new 151k N256 | T1 | By T2 | By T3 | Mean kept-card count |
|---|---:|---:|---:|---:|
| v27 baseline | 11/256 | 111/256 (43.36%) | 194/256 (75.78%) | 5.25 |
| v43 coupled max-Q2 | 10/256 | **122/256 (47.66%)** | **211/256 (82.42%)** | 5.492 |

Paired byT2 **+11 net games, +4.297pp**, 15 maxQ2-only / 4 v27-only, paired 95% bootstrap CI **[+1.172,+7.813]pp**. ByT3 **+17 net games, +6.641pp**, 22 maxQ2-only/5 v27-only, CI [+2.734,+10.547]pp. T1 one fewer game; uncertainty ~1pp. 33/256 final keep stages and 102/256 final bottoms changed. This is material, fresh evidence but still a single N256 experiment and **does not certify parity with the original v5** (which was not run in that N256 cohort when original v43-v27 result was fixed). No model trained/tuned or promoted from 151k.

Raw results `benchmark_results/v43_fresh_151k_maxQ2_shards/` and `benchmark_results/v43_fresh_151k_v27_vs_maxQ2_N256.json`, [Actions 41356977947](https://github.com/herschelruskin/urza-state-solver/actions/runs/41356977947).

## Remaining scientific and architectural risks

- v27 Q2 was originally fitted using v14-selected bottom candidates and only FOUR physical gameplay future trials for each training-stage state (2048 stage states/256 training original deals). Picking MAX over 12 generally amplifies model misspecification, OOD extrapolation and winning-noise bias, despite this promising independent physical result.
- Original v5's provisional frozen continuation thresholds and assertive bumps, plus its T1-weighted exception, still differ. One cannot clone v5 by adding +.2 to the v27 Q2 because scales/objectives and continuations differ.
- v43's +4.3pp gain could partly reflect more-kept-card stage distribution and not only retained-hand quality; actual full-game policy changed both in coupled mode.
- Additional original-v5 reference comparison should use **matching physical 151k seed IDs**, not subtract its historical 115k rate from the new v43 cohort. If run after looking at 151k results, that comparison is retrospective, not a new prospective gate.
- Portability across 1–2 deck substitutions remains untested; frozen v27 trained for `one_key_34`.
- No significant early-predicted-T3 safeguards or unmodeled interaction are included in goldfish; deck recommendation or cEDH win probability cannot be inferred.

**Best new architecture:** learn a **candidate-level physical value ranking and KEEP score jointly**, with realistic physical outcomes on many *candidate alternatives*, more than four independent future labels for key hands, group-aware design, calibrated continuum per stage and seat, with a structural top12 legal candidate limit. Preserve original-v5 maximal-candidate search but remove heavy every-candidate gameplay rollouts. Keep unchanged v43 frozen as strong challenger and evaluate future variants on independent new physical game IDs (not 115k or 151k) against v27 and, when budget permits, v5. All models remain unapproved until these checks pass.
