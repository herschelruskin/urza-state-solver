# DACK v35: prespecified early keep/mull action-regret experiment

Research branch `dack-v35-early-action-regret-20261101`, forked
from completed v34c. No changes to physical engine, v5/v14/v27,
v33b or v34c. No model/policy promotion without independent evidence.

## Established constraints

- Strict 99-card physical reshuffle and London 7,7,6,5,4,3,2,1;
  first free seven (stage0) is NOT the second seven (stage1).
- Goldfish Dack deployment by T2 primary; T1 and T3 safeguards.
  Strict stable-effects gameplay beam160 unchanged. No mulligan beams.
- v33b bottom-selection ridge frozen exactly, including legal bottom
  and hidden library order. Do not reuse heuristic functional feature
  vectors as gameplay-state canonicalization keys.
- Q(MULL) under fixed policy depends on seat and stage, not rejected
  seven; only after restoring all 99 cards and resampling later sevens.
- 117k existing validation already consumed. NEVER fit, select or tune
  this model on it. Original realized v5/v27 115k win-turns NEVER
  enter training, even though 115k early policy disagreements were
  selected based on actions.

## Predeclared training design

Use only existing archived physical data, no new training beams:
(1) 64 independent 116000..116063 physical game groups, seven
    stage states per group, eight blinded unseen-92 physical outcomes
    per stage (448 states);
(2) 100 independently grouped 115k v5/v27 first KEEP/MULL
    disagreements, using the 16 fresh `calibration` KEEP futures
    per group. The v34c `replication` trials stay unused in fit.
(3) For BOTH groups, Q(MULL) = the 64 v34 training future
    physical outcomes for the corresponding seat/stage, under
    unchanged frozen v27 future KEEP and frozen v33b bottom.
    NOT the previously inspected v34 untouched-validation C,
    and NOT model-predicted C.

Fit a single, 19-dimensional capability-aware regularized ridge:
target real `Qkeep(T2)-Qmull(T2) - [v27_Qkeep-v27_C]`,
plus a separate direct T3 keep-minus-mull regressor for safeguard.
Use prior original v27 margin at inference; shrink residual to
[-0.35, +0.35]. Lambda=16, 24 outer-physical-game-group
bootstrap fits, 116k seven states weighted 1/7 per group,
115k selected groups weighted 0.75, stages 0-2 weight ×2.
Fixed training-set RMS scales lower-bounded at 0.35.
Features: v27 margin/Qkeep; stage0/1/2, seat0/1/2, land,
white/two-mana land, ramp/zero mana, tutor, Chrome Mox
imprints, Opal support, combo brick, analytic T2 proxy.
No card-identity memorization, no v5 keep-label imitation.
24-model quartile stability is heuristic, NOT calibrated CI.

ONLY stages 0,1,2 may change:
- Frozen v27 MULL -> KEEP if the ensemble lower quartile
  of predicted T2 action advantage > +0.06, and median
  T3 keep-minus-mull >= -0.04.
- Frozen v27 KEEP -> MULL if ensemble upper quartile
  T2 action advantage < -0.06, and median T3
  keep-minus-mull <= +0.04.
- Otherwise keep the frozen v27 choice. Stage 7 always
  keeps. Preserve v33b bottom after any final KEEP.
This symmetric guard prevents substantial expected T3 damage
in either direction. No threshold sweeps or posthoc fitting.

## Prespecified independent 121k conditional validation

FRESH IDs 121000..121127: 128 independent physical dealt
games, every stage0..6 for each game (896 stage states),
eight independently shuffled physically unseen-92 outcomes
on frozen v33b chosen hand at each stage = 7168 strict
beam160 KEEP trials.

Separately, for each seat0..3 and stage0..6, 64 new full-99
physical MULL continuations under EXACT frozen v27 future
keep policy and frozen v33b bottom; 28×64=1792
strict beam160 MULL trials. Total fresh 8960 game
rollouts. Sample true KEEP without selecting on game result
or original v5 policy, and keep the separately sampled
C continuation as a *shared random variable* per seat/stage.
Freeze the fitted model before 121k data is generated.

Measure conditional chosen-v27 action T2 and T3 value
by direct KEEP and common Qmull, paired grouped bootstrap
resampling both outer game groups and the shared seat-stage
C trials. Report stage0/1/2 actions, seat strata, action
switch directions, label scarcity and source hashes.
Cumulative T1<=T2<=T3 asserted on every arm.

**STOP** if independent conditional T2 benefit is negative or
uncertain, or there is persuasive T1/T3 harm; the model remains
experimental. If it passes, independently test 122k physical
full-game N256 paired v5/v27/v33b/v35, exact game sevens,
strict beam160 and runtime. That prospective test is NOT
optional for any promotion. Regret validation with a frozen
downstream is a one-step estimate, NOT a self-consistent
Bellman fixed point after changing the policy.

No more adding forests or moving thresholds based on holdout
results. This is simulated Dack deployment, NOT multiplayer
cEDH match winning.
