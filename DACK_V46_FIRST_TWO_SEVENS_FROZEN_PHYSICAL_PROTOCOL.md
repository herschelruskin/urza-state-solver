# DACK v46 — first two London sevens: physically calibrated early action

**Predeclared 2026-11-01 before observing any 163k K outcomes or fitting the model. RESEARCH-ONLY.** Branch: `dack-v46-first-two-sevens-physical-Q2-20261101`. Original v5/v27/v43/v45 and all old results remain untouched; sealed former v44 `155k` full-game acceptance remains unopened.

## Scientific question and necessary correction to the initial premise

Every Commander goldfish game sees the initial seven-card hand (London stage0). The next seven at London stage1 is seen **only if stage0 was rejected**. Both stages have `keep_n=7`; there is no bottom selection. That uniquely isolates the binary action KEEP versus MULL, but demands estimating the future MULL action value with the **same downstream policy being compared**.

We MUST NOT change both stages at once and use the original-v43 stage0 MULL continuation. Changing stage1 changes the stage0 continuation distribution and invalidates the threshold comparison. First fit and test two **separate stage-isolated variants**:
- **Stage0-only edit:** stage1 and all later original frozen v43; C0 from true frozen v43 future re-deal is exact.
- **Stage1-only edit:** stage0 and stages2+ original frozen v43; C1 from true frozen v43 future re-deal is exact.
Only combine after new C0 physics under the newly altered stage1, on a separate branch with sealed new independent assessment.

## Experimental source and protocol

Random independent real physical source IDs **163000–163255**, each producing both a randomly dealt stage0 seven and an independently shuffled hypothetical stage1 seven for the same seat; these two stage states are **correlated within the same outer group**. Stage1's random marginal seven distribution is valid for assessment independent of the stage0 decision, but is *not* the same as the population frequency of actual stage1 visits under a particular policy.

Train **192 independent groups** (`163000..163191`), dev **64 independent groups** (`163192..163255`) sealed from fit. Each stage's KEEP exact seven has 16 physical unseen92 reshuffles, original 99 card deck `one_key_34`, stable original gameplay dice, strict physical beam160. So 256×2×16 = **8192 KEEP physical future simulations**.

For each of **four seats × two early stages**, collect **128 independent full99 re-shuffle C future games**. All 99 original cards return before every later London stage. Later decisions use original frozen v43 max-Q2 and original rules, yielding 8×128 = **1024 independent shared C outcome simulations**. These are distinct from all previous v45 source C future seeds.

## Two fixed predeclared correction candidates

1. `C_only`: retain exactly v43's cheap frozen Q2 estimate for the seven; KEEP if predicted `Q2 >= physical C2(seat,stage)` estimated from the independent 128 real MULL continuations. This isolates continuation calibration from KEEP model reconstruction.
2. `ridge_C`: train exactly one small, regularized ridge model on all 384 train stage observations, using target = observed K16 mean-by-T2 − original v43 estimated Q2. Group-weight both stages at 1/2 per independent outer deal. Features are v13 capability/land/mana/tutor proxies and named pair/group interactions but **no hand/seven/bottom literal card one-hot**. Fix alpha32, residual shrinkage0.55, clip residual at ±0.20, then KEEP if `Q2_corrected >= physical C2(seat,stage)`. Dev labels never enter model fitting; source seven and unknown **multiset** only, not realized unseen future order.

Original frozen v43 is the unmodified control. No candidate gets v5-oracle scores at inference, any runtime teacher lookahead or any data from 155k/164k.

## Stage-isolated development gate and leakage protection

On the 64 random dev outer groups (128 stage observations) compute `(I_new_KEEP−I_v43_KEEP)×(K2−shared_C2)` separately for stage0 and stage1, using exact heldout 16 blind K futures and one shared C128 per seat/stage. Report T1, T2, T3 separately; bootstrap groups, K futures and C lottery independently (same lottery reused in every game at its cell) with 2,400 predeclared replicates.

For each of four predeclared stage×model candidate combinations, require ALL:
- At least three action changes on that stage's 64 random dev sevens.
- Physical conditional T2 gain ≥ **+1.0 pp** over original v43.
- Conditional T3 decline no more than **2.0 pp**.
- Group and two-source 95% bootstrap T2 lower CI **greater than −3.0 pp**.

This is **an exploratory screening rule**, not proof of positive effects at p<.05. Choosing a candidate after seeing dev results consumes the dev cohort for model selection. If more than one passes, select highest dev conditional T2 gain, preferring `C_only` for a tie, and ONLY then compare against original v43 on a NEW independent full-game N256 cohort `164000..164255` with strict paired physical outcomes; no revision based on 164k results. Do not interpret dev conditional percentage-point improvement as population full-game gain. If none passes, do NOT spend the 164k prospective cohort on an unproven v46 candidate.

The later physical acceptance is distinct from the frozen former v44 155k and from all earlier 115k, 116k, 117k, 147k, 148k, 151k, 154k data.

## Mandatory failure gates

- v43 first-two-seven legal bottom count must be zero; sorted/canonical stored hands and physical dealt order may differ, but card **multisets** must be equal. Explicit physical win-turn parity test between those two representations before fit or final use.
- Same initial physical 99-slot seed and seat for eventual whole-game comparisons, same original game rules and stable dice, strict beam160. Fail loudly for hidden information, illicit card bottoms, outcome mismatch or cross-policy path contamination.
- `stage0` is always reached; `stage1` only after stage0 MULL. Stage1 counterfactual random hands in training are not independent of the same physical group's stage0, and are not all naturally reached.
- The stage1-only variant is particularly prone to apparent static action improvement that fails to translate into full-game T2 if stage1 is rarely reached. Test actual policy end-to-end.
- Shared C samples are a cell-level Monte Carlo measurement; never count them as independent repeats for every physical seven. The regression may itself be misspecified; retain original v43 baseline until prospective test confirms a gain.
- The user may change one or two deck cards eventually, but neither v46 model nor C table is portable without recalibration and a physical matched test. No candidate is approved for another deck.

No v46 policy is currently approved. This document establishes a frozen design, not a predicted outcome.
