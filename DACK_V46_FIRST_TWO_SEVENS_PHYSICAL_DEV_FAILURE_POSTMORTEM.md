# DACK v46 — physically calibrated first two sevens: held-out rejection

**Completed 2026-11-01. Technical workflows PASS; scientific improvement gate FAIL. No v46 policy approved or promoted. No 164k full-game acceptance opened.** Branch `dack-v46-first-two-sevens-physical-Q2-20261101`.

## Source and methods

- Random source **256 independent real physical 99-slot game IDs 163000–163255**. For each source deal sample initial seven at stage0 and an independently reshuffled hypothetical seven at stage1; **stage1 is reached only if the first seven is rejected**. Those two stage observations are **correlated within the same game-group**.
- **8,192 strict beam160 real KKEEP futures** (16 shuffled unseen92 per seven per stage) and **1,024 independent MULL future games** (128 independent full-99 restored future London/strict-gameplay runs for four seats × two stages, with frozen v43 candidate-max and KEEP policy downstream).
- Group-split fit train 192 deals (163000..163191) / holdout development 64 deals (163192..163255), no overlap.
- Two predeclared per-stage alternatives: `C_only` retains v43 Q2 and replaces its old DP KEEP cutoff by measured physical C2(seat,stage); `ridge_C` learns a strongly regularized 71-feature target `QKEEP_16_future_byT2 − frozen_v43_Q2` with alpha=32, clips to ±0.20, shrinks 0.55, and compares to measured C2. Neither model is allowed to modify both stage0 and stage1 simultaneously under the old stage0 continuation, since altering stage1 changes the Qmull value of stage0.
- Original seven/canonical hand order passed **48 real strict-gameplay parity comparisons**; all physical conservation and no-bottom assertions passed. The first K collection workflow failed an incorrectly order-sensitive assertion; this was corrected to compare exact **card multisets**, and the full rerun passed. Physical K16 actually used the dealt seven; independent original strict engine test verified turn-equivalence to the original v43 canonical hand representation.
- Source physical successful [workflow 41363676536](https://github.com/herschelruskin/urza-state-solver/actions/runs/41363676536); 24 complete archived gz source shards `benchmark_results/v46_163k_early_K_C_shards/`. Feature/syntax and ordering parity workflows [41364111942](https://github.com/herschelruskin/urza-state-solver/actions/runs/41364111942) and [41363976334](https://github.com/herschelruskin/urza-state-solver/actions/runs/41363976334) PASS. Offline model and dev [41364502171](https://github.com/herschelruskin/urza-state-solver/actions/runs/41364502171) PASS technical; output `benchmark_results/v46_first_two_sevens_random_dev_N64.json`, `models/v46_early_Q2_residual_RESEARCH.json` retained with policy_approved=false.

## Frozen N64 random physical dev

| Stage / intervention | Action changes among 64 dev sevens | Mean physical one-step T2 vs v43 | Mean T3 vs v43 | Paired group+K+C 95% T2 interval |
|---|---:|---:|---:|---:|
| Stage0 C_only | **0** | 0.000pp | 0.000pp | [0,0] |
| Stage0 ridge_C | **0** | 0.000pp | 0.000pp | [0,0] |
| Stage1 C_only | 2 (both KEEP→MULL) | **+0.354pp** | −0.024pp | [−0.696,+1.782]pp |
| Stage1 ridge_C | 3 (all KEEP→MULL) | **+0.610pp** | −0.220pp | [−0.610,+2.148]pp |

None met the predeclared exploratory screen of ≥3 changes, ≥+1.0pp heldout T2 gain, no more than 2pp T3 harm and T2 lower bound >−3pp. No approval; NO full-game 164k acceptance.

Stage0 baseline v43 already kept **14/64** random dev initial sevens and stage1 baseline kept **10/64** hypothetical second sevens. The original v43 Q2 mean was stage0 .1988, stage1 .1477, with many hands far from the decision boundary; physical C2 means across seat distribution were stage0 .4183, stage1 .3807. Modest Q2 corrections and updated C values rarely changed actual decisions in the random development population.

## Independent earlier teacher-conflict transfer diagnostic (retrospective only)

A read-only [workflow 41364654614](https://github.com/herschelruskin/urza-state-solver/actions/runs/41364654614) replayed original v46 score/threshold on 26 previously inspected matched 151k v5-v43 actual first-action conflicts at stages0/1. It did NOT change training or use previously inspected outcomes to select v46 parameters. Report `benchmark_results/v46_old_151k_first_conflict_early_transfer_audit.json`.

- 20 cases v43 first KEEP, original v5 MULL; `C_only` moved 4 toward original v5, `ridge_C` moved 7 toward v5.
- **Six cases original v5 KEEP, v43 MULL; neither correction rescued any of these six.** This is a major missing mechanism: the model does not recover nonlinear fast-mana/tutor/combination-specific opportunities.
- This is a **deliberately selected historical conflict set**, not a new random validation dataset, and agreement with original v5 isn't itself a physical action advantage.

## Scientific interpretation

The isolated first-two-seven experiment was correct and informative, but the result was not strong enough to support a new fast policy. It does not imply original v43 is globally optimal at stage0/1; the random N64 development sample contained few hands close enough to the adjusted threshold to reveal a difference, while the original v5-v43 selected conflicts include rare consequential seven-card hands missing from the fit.

Simply recalibrating stage cutoffs or fitting a 71-feature smooth ridge residual still doesn't model rare line-level interactions with enough fidelity to mimic v5's early retained-hand valuation. Do **not** tune alpha, shrinkage, threshold or gate on these already inspected 163k or 151k results and call it independent evidence.

**Next experiment:** a strictly limited original-v5 early seven lookahead **only at stages0 and1**, using original `evaluate_keep` but no candidate-bottom search (only one retained hand), followed by original frozen v43 at stages2+. Test exact original-v5 stage0/1 decisions against archival traces before launching fresh physical full-game seeds on a distinct cohort (e.g. 165k). Measure runtime tradeoff and actual T2/T3; this may be a principled speed-versus-accuracy hybrid, NOT a no-beam policy.
