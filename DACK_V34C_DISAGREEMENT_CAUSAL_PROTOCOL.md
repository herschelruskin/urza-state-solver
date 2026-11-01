# DACK v34c — Actual London KEEP/MULL disagreement counterfactual

Branch: `dack-v34c-keep-disagreement-20261101`.
No production changes. Preserve all frozen baseline branches and v34
rejected calibration pilot.

## Why this specifically

v34 8064 real physical rollouts and zero-beam rank audit found v27
Qkeep broadly discriminates favorable vs unfavorable hands; global
Qkeep/C shrinkage altered only one heldout action and REDUCED one-step
T2 value. The earlier v5-v27 decomposition (115k: 19 net T2 games
in different actual stage category) was observational only, not causal.
The next test MUST ask whether an actual policy disagreement on KEEP/MULL
is favorable under identical continuation and bottom policies.

## Precommitted selection and physical protocol

Read ALL 64 archived 115k prospective physical four-game shards.
For each of 256 game IDs, select iff actual final v5 and frozen v27
kept at DIFFERENT London stage indices. This is based ONLY on policy
decisions, not observed 115k deployment turns or v5 outcome.
Expected about 100 such independent physical games. Take the
earliest disagreement `s=min(v5_kept_stage,v27_kept_stage)`.
At this stage both saw the exact same seven, seat and physical
99-card inventory. One elected KEEP, the other elected MULL.
Actual stages 0 and 1 must NEVER be merged just because both
retain seven. Expected class v27-keeps-first ~61; v5-keeps-first ~39.

Fix both action arms to the SAME already trained, UNCHANGED
v33b downstream policy:

- Forced KEEP: use the exact frozen v33b legal bottom candidate
  on the actual seven, then individually shuffle its 92 unseen
  physical cards; append the bottom cards; run unchanged
  stable-chance beam160 gameplay to T3.
- Forced MULL: restore all 99 cards and follow the frozen v27
  keep decision + frozen v33b bottom after the next stage. As the
  future deck is freshly shuffled, Q(MULL) does not depend on
  the rejected visible seven. Therefore REUSE the existing
  independent v34 28-cell ×(64 train+32 validation) TRUE PHYSICAL
  Q(MULL) continuation outcomes, with matching seat/stage/policy;
  **zero new mulligan simulator calls**. Do not use its surrogate
  v27 DP predictions as truth.
- Keep outcomes: 16 fresh unseen92 physical futures on a
  `calibration` seed split and another 16 independent futures
  on `replication`, for 32 independent physical futures per
  selected actual disagreement group. 100×32=3200
  actual strict beam160 gameplay calls. Same blind chance model,
  same real card IDs; no current-stage hidden order supplied
  to action selection. Eight parallel shards by original game
  ordinal, not by realized outcome.
- Separate original 115k game outcomes from replay labels;
  don't include them in policy features or select by whether
  either original policy won. No v5 beam search in replays.

## Primary estimand and inference

Let A=Qkeep_v33b(seven,seat,stage)−
Qmull_frozen_v33b(seat,stage), both actual T2 deployment
probabilities under a common continuation. Define v5-first
action's advantage relative to v27-first action as:
  - A if v5 kept at earliest disagreement stage,
  - −A if v27 kept at earliest disagreement stage.

This is a *one-step causal action contrast at selected disagreements
under the SAME v33b future policy*. It is not the winrate of the
full v5 policy, because v5 selects its own bottom/future keeps.
T3 analogous safeguard.

Report overall and by who kept first/actual stage/seat, empirical
T1/T2/T3 keep arms, Qmull from the 96 independent source lotteries,
paired group-bootstrap confidence intervals that resample outer
physical game IDs AND the shared seat-stage Qmull lottery, and
independent calibration/replication keep split agreement.

Do not fit or promote a keep policy from these selected 115k
disagreements; 115k was already used to choose this diagnostic
question, so use independent later prospective cohorts before
any promotion. The direction of conditional advantage provides
mechanistic evidence for or against keep-stage decision quality,
NOT a causal decomposition of complete policy differences.

Never merge actual search states using heuristic capability keys.
Preserve first/second free seven, all 99 cards on mull, true
physical 92 plus bottom on keep, seat-dependent draw mechanics,
and stable-dice beam160 gameplay.
