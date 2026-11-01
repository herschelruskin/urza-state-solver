# DACK v34: consistent policy keep-versus-mull counterfactual protocol

Research branch `dack-v34-consistent-keep-regret-20261101`, forked
from finished v33b. **No engine, v5, v14, v27, v32, v33 or v33b
changes and NO policy promotion.**

## Why

In 115k N256, unmodified v5 exceeded v27 by 26 games at T2;
19 net differences arose in games that kept at different ACTUAL
London stages, while the validated v33b bottom-only policy recovered
five T2 games relative to v27. This is descriptive, not a causal
keep/mull diagnosis. v32 previously changed Q(MULL) while leaving an
often noisy v27 Q(KEEP), and its simulated downstream policy was
inconsistent with the new bottom selector.

## Frozen continuation definition

At stage s (0..6), all seven rejected cards return to the entire
99-card physical deck. Future stages s+1..7 are independently dealt
from shuffled 99-card deck. Under a FIXED future London policy,
C(seat,s)=Q(MULL | seat,s) is independent of which visible seven was
rejected. That is a valid distributional identity, not a game-state
hash or permission to peek at future shuffles.

Future policy after mull uses the EXACT v27 T2-only Qkeep forest and
EXACT frozen v27 DP threshold, followed at final KEEP by the
ALREADY TRAINED unmodified v33b pairwise-regret bottom. It must
match v33b's complete London histories at stage0 and final
actual retained hand and future physical deck. The KEEP arm at
the current stage also uses this exact v33b bottom selection
(only seven and unknown 92-card multiset observable). Both arms
use strict beam160 stable-dice actual gameplay.

No additional training on v5 actions, past 103k/110k/115k outcomes,
or original teacher bottom labels. All eight London stage indices
handled explicitly; stages0 and1 each have seven cards, while
stage7 is forced KEEP (no C7 needed).

## Data collection (fixed before inspecting outcomes)

- Q(MULL) for each of 4 seats x 7 decision-capable stages, each
  with **64 training + 32 untouched validation** physically fresh
  full-99 continuations (28 independent CI jobs, 2688 actual game
  rollouts), trial-index and split seeded independently.
- Q(KEEP) for **64 new physical training game IDs 116000..116063**
  and **32 untouched validation IDs 117000..117031**. Every
  stage s=0..6 sampled even if not reached by v27 actual play.
  For each of 96x7 visible stage sevens, fixed v33b bottom,
  **8 independent physical unseen-92 shuffled futures** and
  blind stable chance seed, totaling 5376 actual game rollouts.
  Four-game shards, 16+8=24 CI jobs.
- No currently dealt seven can influence Q(MULL) continuations.
  Seat and stage are preserved; keep sees exactly seven and the
  unknown multiset. All gameplay physical state/order unchanged.
  Expected total 8064 strict beam160 game deployments,
  in parallel shards. All source hashes archived.

## Predeclared minimal correction candidate — RESEARCH ONLY

Do not train any new random forest or optimize thresholds after
seeing validation. Freeze the following single transparent candidate:

- For each stage s=0..6, estimate pooled (all four seats) model
  QKEEP bias b_s = mean[empirical T2 success of fixed v33b KEEP
  minus the v27 absolute Qkeep prediction] on the training 116k
  groups; adjust every v27 score by **0.50 x b_s**, clipped to
  [0,1]. Shrinkage coefficient predeclared, no tuning.
- For each seat/stage, estimate C_emp on 64 independent TRAIN
  Q(MULL) continuations. Set C_new = 0.5 C_emp +
  0.5 C_old, where C_old is frozen v27 DP threshold for
  that seat and stage. Shrinkage coefficient predeclared.
- Candidate keep if adjusted QKEEP minus C_new > +0.03;
  candidate mull if < -0.03; otherwise take the *original
  frozen v27 decision*. No change at stage7, which always
  keeps. The +0.03 deadband prevents spurious near-zero
  corrections and is predeclared, not optimized.

Test this single policy on 117k heldout *conditional-stage*
action-value labels, comparing expected T2 of chosen versus
original v27 action using (a) true fresh Qkeep outcomes from
eight unseen-92 futures and (b) independent 32 trial per-seat-stage
true future C values. All differences grouped by physical game
and resample BOTH 117k game IDs and validation C lotteries for
uncertainty. T3 expected outcome is a safeguard.

This CONDITIONAL diagnostic is not full-game policy performance
because sampling all stages does not model altered path
visitation. If positive evidence material, implement an isolated
candidate and test new 118k N256 physically matched full
games versus v27, v33b and v5. If conditional value is uncertain
or negative, do not deploy and instead pursue more informative
near-boundary Qkeep labels/line-aware feature calibration.
Never silently patch v27's DP table or reuse a continuation
sample estimated under a DIFFERENT downstream policy.

## Failure checks

No hidden draw order in policy features; first and second free
seven distinct by stage index; exact 99 returned on mull; exact
v33b retained hand on keep; no cross-split game IDs; seat-specific
drawing; no cache or dice carryover between arms; no assumption
that a common RNG seed couples different decision paths perfectly;
no functional-fingerprint merges of actual game states.

The goldfish metric is casting Dack by T1/T2/T3, NOT multiplayer
cEDH win probability.
