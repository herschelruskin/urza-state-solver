# v46: physically calibrated first and second seven-card KEEP/MULL (frozen experiment)

**Research-only, 2026-11-01.** New isolated branch. The frozen experimental v43 max-Q2 candidate policy remains unchanged for stages 2–7 and is the required comparator.

## Core structural advantage

At London stage 0 and stage 1, both retain all seven cards and there is no bottom selection. Every game necessarily visits stage 0. Stage 1 is visited only if stage 0 is mulliganed. Stage1 random seven-card *potential* states can be sampled independently of the stage0 decision to learn generic stage1 hand values, but **full-game stage1 visitation and actual policy value differ**; final deployment must be evaluated on actual trajectories.

The primary endpoint is **P(deploy by turn 2)** (inclusive). Secondary endpoints: by T1, by T3, and T3 harm when changing an early KEEP. This is goldfish Dack deployment, not multiplayer victories.

## Physical value sources, fixed before outcomes

**New distinct outer physical game IDs:** 156000..156191, split *chronologically and sealed*, 156000..156127 **training (128 distinct IDs)** and 156128..156191 **development (64 distinct IDs)**. Reserve **157000..157255** for full-game paired evaluation only if the dev gate passes. Do not consume the previously reserved 155k cohort. Neither 115k nor 151k nor 154k physical outcomes may be used for fitting or model selection here.

At each new independent ID, obtain the original physical seat and London stage0 and stage1 randomized 99-slot deals using canonical `ref.stage_slots`. Both sevens retain all seven. This gives **two hypothetical stage states per physical ID**, but only **one independent physical parent deal group**. For every stage state:
- Verify that frozen v43 `choose_at` matches original v43 stage history: full retained seven, no bottom and exact v27 max Q2 and frozen DP threshold.
- Run **16** blind independently reshuffled unknown92 strict actual beam160 KEEP futures (same state/seat, independent gameplay chance); measure raw T1/byT2/byT3 and preserve each discrete turn, not just a mean.
- Keep all stage1 examples in the *training* source (even if hypothetical/not reached). Track stage1 observed visitation separately in full-game evaluation.
- Exactly **128** independently sampled full99 MULL continuations per seat and stage (8 cells), each starting at stage+1, randomizing ALL 99 cards again at EVERY subsequent London stage and following **exact frozen v43**. All source hands sharing a cell share that one finite C lottery, counted only ONCE per bootstrap replicate. These C futures train and compare value against the frozen-v43 downstream continuation, **not the new stage1 policy**; this distribution shift must be tested in a final actual full-game paired test.

Total physically simulated futures: **192 groups × 2 stages × 16 = 6,144 K**, plus **8×128 = 1,024 C** = **7,168** strict actual game runs. Training, dev split independent in their KEEP outcomes. C source is independently generated but SHARED between train and dev; explicitly report this and resample shared C uncertainty in validation, never call C a new independent dev set.

## Model and guardrails

Use stage0/1 baseline frozen v43 max-Q2 `Qkeep`, legal visible-hand features and seat as input; never actual hidden 92 ordering, future card realizations, old goldfish result, or v5 teacher decision. Target **actual physical byT2 KEEP** (binomial average over 16 outcomes) with group-balanced weights and a strongly regularized low-capacity scorer, compared against a raw-v43 model/calibration baseline. Independently estimate C2 from the 128 strict full99 v43 continuation runs in each seat/stage cell. Keep the KEEP-vs-MULL decision coupled to exactly the seven-card hand physically scored.

Use a **conservative gate**: change a frozen-v43 early-stage decision only when estimated physical Qkeep−C2 has a prespecified margin of >=0.05 (KEEP) or <=−0.05 (MULL), and predicted T3 cost of overriding the original early action is not worse than 0.10. Return to frozen-v43 decision for smaller or uncertain margins. Avoid tuning multiple model thresholds on the small dev cohort: model parameters and margin are frozen in the training script before observing dev.

**Dev gate to permit separate full-game N256 157k run**: new candidate must produce positive out-of-sample *conditional physical T2 action-regret gain* over frozen v43 across the **random development source**, with no worse than −2.0pp conditional T3; report a two-source bootstrap (outer groups, K futures, shared C lottery). This is a screening criterion, not a statistical proof or policy promotion. In addition, require at least 5 actual changed actions across 128 potential stage states to ensure the signal is informative; otherwise report inconclusive and do NOT run costly full game. Dev is used once for gating and then consumed.

No performance improvements are claimed until the physical dev outcomes are archived and the numerical gate passes. Even if dev passes, 157k full-game is an independent real physical benchmark and no policy is approved without it. No work on new deck variants, no dynamic v5 fallback.
