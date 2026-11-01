# DACK v46 — first and second seven-card physically calibrated KEEP model, completed

**2026-11-01. Disposition: FAILS PREDECLARED DEVELOPMENT GATE. Do not promote v46. The 157000–157255 full-game cohort and the unrelated 155k cohort remain unopened. Original v43 policy unchanged.**

## Why the experiment

v45 found that nearly all of v5's remaining advantage over v43 on matched 151k games was associated with different London stopping stages, especially stages 0 and 1. At both stages the retained hand is all seven cards; no bottom selection. Stage0 is visited by every game, while stage1 is visited **only if the policy mulled stage0**; for training we sample stage1's potential seven independently even when the natural policy would not reach it.

## Physical source and engineering audit

Branch: `dack-v46-seven-card-physical-calibration-20261101`. Fully executed physical collection [Actions 41363387475](https://github.com/herschelruskin/urza-state-solver/actions/runs/41363387475) **SUCCESS**. All 20 source jobs plus archive passed: 12 KEEP shards, eight MULL cells.

- 192 distinct original physical deal IDs `156000..156191`: 128 training groups `156000..156127`, and 64 independent dev groups `156128..156191`. Two potential seven-card stages per deal => 384 stage states but **192 independent source deal groups**.
- Every seven-card hand passed strict multiset identity and empty-bottom check. K physical: 16 independent shuffled unknown92 and stable chance seed per state => **6,144 real beam160 goldfish games**.
- Shared C physical: 128 independently reshuffled full99 future London continuations in each seat(4)×stage(2) cell => **1,024 C games**. Every later stage uses the exact unchanged v43 max-Q2 policy, same 99 slots restored, no initial-current-seven cards leaked. Finite C is **shared** across all training/dev source hands in that seat/stage and resampled once per cell in bootstrap.
- An initial source workflow [41363230184] failed on a *validation-only* assertion comparing unsorted seven with internally sorted retained cards; corrected to compare exact card **multisets** and use frozen-v43 sorted hand in game state. All K sources were regenerated and the subsequent completed collection passed.
- Separate feature/extraction [Actions 41363712311](https://github.com/herschelruskin/urza-state-solver/actions/runs/41363712311) passed for multiple stage0/1 sevens.

Source shards archived under `benchmark_results/v46_new_156k_KC_physical_shards/`. No original v5 teacher decisions were used for labels or model features.

## Trained model and dev result

[Training+gate GitHub Actions 41364044149](https://github.com/herschelruskin/urza-state-solver/actions/runs/41364044149) **SUCCESS** with no full-game 157k jobs launched (correctly skipped by development gate). The model is an 80-tree depth5 min-leaf12 random forest for each PbyT2 and PbyT3 fitted to real physical K outcomes from 128 train groups, group balanced 0.5 per stage. Uses a selected subset of visible-card features (including card interactions), original frozen-v43 predicted Q2, seat and stage, but no physical future order; T2 is 50% blended with frozen v43 score for shrinkage. PbyT2 vs physically estimated C2 controls early override with ±0.05 deadband; predicted T3 risk >10pp blocks an override. Later London stages 2–7 exactly unchanged frozen v43.

JSON model: `models/v46_real_first_two_sevens_RESEARCH.json` (SHA256 `9d1a4a2a347ddd4b15fdeaa6ed2fc9cfbac680bd2e3bcc843e5e43f3c3163093`). Model is `policy_approved:false`. Training/export verified 100 sklearn-versus-dependency-free pure-Python inference parity examples. Independent development case report: `benchmark_results/v46_156k_two_sevens_physical_train_dev.json`.

| Dev endpoint | Frozen v43 → v46 |
|---|---:|
| Independent source deals | 64 |
| Stage states (potential stage0 + stage1) | 128 |
| Actual early decisions changed | **1/128** (stage0 KEEP→MULL) |
| Stage1 changes | **0/64** potential stage1 states |
| Conditional physical T2 one-step change | **+0.2502pp** |
| Conditional physical T3 one-step change | **−0.0610pp** |
| Hierarchical group/K/shared-C T2 95% CI | **[0,+0.8667]pp** |
| T3 95% CI | [−0.2808,+0.0366]pp |
| Predeclared gate | **FAIL**: fewer than 5 changed early actions |

Exactly one stage0 changed hand, game ID `156172`. Frozen v43 kept, calibrated v46 mulled. On 16 new K futures the physical K2 was 3/16=.1875 versus shared seat1-stage0 C2=.5078125; it is a plausible beneficial MULL *on this selected example*, but 16 futures and shared C uncertainty do not establish ground truth. Because 127/128 decisions were unchanged, the small conditional positive estimate is **not useful evidence of a significant fast-policy improvement**.

No independent full-game 157k results are available. **Do not** use `156128..156191` as a fresh new holdout for retuning this or successor models.

## Post-hoc forensic: stage1 rare combinations

Read-only diagnostic [workflow 41364229774](https://github.com/herschelruskin/urza-state-solver/actions/runs/41364229774) and `benchmark_results/v46_exploratory_dev_early_seven_hand_failures.json` marks the dev corpus as already consumed. Among all 128 dev states, **7** original v43 actions had an unfavorable sign versus the very noisy K16−C128 estimate; **6** were stage1 and one was stage0. This is descriptive diagnostics only; a 16-future observed advantage is NOT an exact optimal action label.

Illustrations:
- ID **156150**, stage1 seat0: `Staff of Compleation; Moonsilver Key; Gift of Immortality; Krark-Clan Ironworks; Mishra's Workshop; Mind Stone; Eiganjo, Seat of the Empire`. Frozen v43 predicted T2 **.2435** and MULLED (seat0 stage1 DP=.3133); v46 predicted **.2144** and also MULLED. New actual-gameplay KEEP sampling yielded **16/16 T2 deployments**, versus the independently sampled full99 C128 **42/128=.3281**. **This particular deterministic-looking success requires a legal mana-line and rules/witness audit before treating it as evidence of a real reproducible combo.**
- ID **156180**, stage1 seat1: `Unwanted Remake; Jeweled Amulet; Mantle of the Ancients; Voltaic Key; Implements of Sacrifice; Ancient Tomb; Chrome Mox`. Frozen v43 predicted T2 **.0555**, v46 **.0682**, both MULL; sampled KEEP **10/16 byT2** versus shared C128 **59/128=.4609**. The T2 advantage is 16.4pp on only 16 futures, so highly uncertain.
- ID **156128**, stage1 seat3: `Erode; Plains; Krark-Clan Ironworks; Trinisphere; City of Traitors; Plains; Crystal Vein`. Frozen v43 predicted T2 **.4022** and KEPT; new physical K2 **1/16=.0625** versus C128 **43/128=.3359**. v46 predicted **.3857** and also KEPT. Again this could reflect missing card-specific opportunity cost or finite-future noise.
- Stage0 exception `156172`: `Arcane Signet; Mana Tithe; Lunarch Mantle; Basalt Monolith; Gemstone Caverns; Tezzeret, Cruel Captain; Plains`, sampled KEEP 3/16 by T2 and shared C 65/128, frozen v43 kept vs v46 mull.

## Conclusions and controls

1. **General seven-card recalibration on only 128 source groups did not alter enough early decisions.** Across random dev states the learned scores were near baseline; the main remaining errors are apparently rare and combination-specific, not an everywhere-shifted seven-card threshold. Do not just make v43 mulligan more.
2. Stage1 accounts for 6/7 observed sign disagreements, but stage1 estimates were also sampled hypothetically even when stage0 would already keep. A later actual full-game policy should be evaluated on **naturally reached stage1** states and with its **own** downstream stage1 continuation, not only the frozen-v43 C assumption.
3. **Investigate legal deterministic mana/tutor lines** behind extreme 16/16 result before collecting more training labels, especially workshop/restricted mana and KCI. Physical gameplay parity with the simulator is not proof the simulator rules perfectly match Magic. Preserve state-level witnesses for audit.
4. Consider targeted **candidate-specific early seven mechanistic model** or selective cheap physical-rollout fallback, but define the trigger from visible hand features and new random source groups, not from this already-examined dev sample. Distinct untouched physical game IDs must be reserved for later acceptance.
5. **No v46 promotion.** Frozen v43 remains our strongest tested fast policy. Both the 157k and original 155k acceptance cohorts remain untouched.
