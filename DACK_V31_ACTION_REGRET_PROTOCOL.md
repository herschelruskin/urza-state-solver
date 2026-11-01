# DACK v31: Real-action-regret pilot (isolated experiment)

Goal: determine whether a learner can predict **whether keeping the current
London hand actually matters** relative to taking the next mulligan, not
whether it chooses the same bottom cards as v5.

Previous v28/v29/v30 audits showed that exact bottom-choice agreement is an
unreliable target: card identities may be irrelevant for T2, and state-keyed
random outcomes can create spurious paired speed differences. However, truly
different cards can affect Chrome Mox imprint fuel, Mox Opal metalcraft,
land drops, mana/white sources, and tutoring.

## Frozen intervention and estimand

- Physical 99 cards, four seat positions and strict stable-dice beam160
  deployment are unchanged.
- v14-128 bottom selector is unchanged for either intervention; v31 tests
  the keep decision only. We deliberately avoid confounding bottom-policy
  changes with keep/mull losses.
- For every preselected `gid,stage` and visible seven, the first
  counterfactual **forces KEEP** the frozen v14-selected bottom hand, then
  shuffles the unseen 92 and plays by T3.
- The second **forces MULL**, restores all 99 physical slots to the deck,
  samples fresh next-stage London sevens, uses unmodified frozen v27 value-DP
  policy to decide subsequent keeps and bottoms, and plays by T3.
- Both actions share the game ID, seat and a keyed dice seed; future London
  reshuffles and post-keep unknown orders are sampled independently of
  card-choice features. Hash-seed sharing does *not* assert identical hidden
  future information sets across the two distinct actions.
- Direct labels: `Q_keep_T2`, `Q_mull_T2`, `advantage = Q_keep - Q_mull`
  from six real rollouts of *each* action. Identical observed rates receive
  no preference. Turn 3 is secondary, not part of the training reward.
- These Qs are conditional under the FROZEN v27 continuation policy. They
  are not optimal-action values nor a multiplayer cEDH winrate.

## Immutable protocol

London stages: 0, 1, 3 and 5 for every independent physical game ID.
All shuffles re-keyed independently by physical group, London stage and
counterfactual future. Six sample futures each, two action arms, four
stages per game.

Physical outer game groups: train 103000-103047 (48), validation
103048-103063 (16), untouched test 103064-103079 (16). Total 80
independent physical groups, 320 decision-stage states, 3,840 actual
beam160 post-keep or post-mull deployments. Never pool stages from the
same game group as independent bootstrap units.

Small pilot fit: a fixed 128-tree depth-6, minleaf-8, 65%-feature
RandomForestRegressor trained on real advantage minus v27 baseline
`predicted_Q_keep - offline_v27_continuation`; add back HALF of the
estimated residual at inference. This is a predeclared regularization
strength, not tuned on validation or test. All inputs come from the
visible seven and unknown 92-card *multiset*, not realized future order.

## Evaluation and limitations

Evaluate paired corrected-policy-minus-frozen-v27 conditional actual
T2 success **on held-out groups**, with bootstrap resampling physical
outer-game groups, reporting action changes, empirical regret,
uncertainty and observed ties. The `max(Q_keep,Q_mull)` retrospective
per-hand oracle is sample-optimistic and cannot establish optimal
future win probability.

Do **not** promote based on conditional Q label accuracy alone. Only if
held-out action regret is credible should v31 be converted into a
separate code path that uses a pure-Python exported model and checked
by a new fresh prospective FULL-GAME physical cohort (not 96k-99k
evaluation cohorts). Keep the old v5, v14, v22, v26, v27 policies intact.

**All numerical values from v31 remain experimental.**
