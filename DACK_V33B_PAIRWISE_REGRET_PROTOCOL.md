# DACK v33b — Paired action-regret ridge, frozen protocol

Research ONLY. Keep existing physical 99, v5 reference, v14, v27,
v32, v33 diagnostic and existing v33b screen immutable.

The first v33b predeclared screen rejected direct v27 Q(KEEP)
bottom ranking as a generalizable substitution:
training +7.14pp T2 vs frozen v14 on 77 eligible hands;
untouched 113k validation +0.56pp (group bootstrap CI -5.0..+4.72pp)
on 45 eligible hands. Other approaches were exploratory. None promoted.

## Model and objectives

Instead of yet another absolute Qkeep regression, fit a small **pairwise
action-regret** model. Training only from completed 112000..112127
physical game groups, heldout 113k discarded for any further training or
threshold selection. A new 114k band is reserved for independent
conditional evaluation and a still-new 115k band for any prospective
full-game comparison IF validation convincingly improves. No 110k
diagnostic outcome enters training.

- Encode capability differences between alternative hand and baseline
  v14 hand (not exact bottom-index matches).
- 27 prespecified mana, color, fast-ramp, combo/tutor access,
  Mox imprint/metalcraft/land/seat features. They are features, NEVER
  equivalence assertions or keys for collapsing gameplay states.
- Outcome: directly measured paired `P(deploy by T2)` and
  `P(deploy by T3)` differences, eight common physical futures
  per candidate in 112k. No teacher future peek.
- Weight all action pairs from one physical game equally in aggregate
  so multi-alternative groups do not dominate.
- 16 group-bootstrap ridge regressions, shared full-training
  feature RMS scaling min=0.25, regularization lambda=12.
  No hyperparameter tuning on validation.
- Candidate proposals restricted to four **already observed during
  training** zero-beam methods: v14, v27 value, v18 top-3, and
  analytical T2. Do not rank arbitrary 12 off-policy candidates.
- Preserve v14 if no candidate has lower-quartile across bootstrap
  predictions for T2 > +0.010 AND median predicted T3 >= -0.025.
  These quantiles are conservative heuristic stability measures, NOT
  calibrated Bayesian credible intervals or guarantees.
- Do not use labels for v18 off-policy combinations outside its
  documented top-three support.
- At prospective inference freeze v27 KEEP/MULL decisions using
  its original v14-selected Qkeep; alter bottom only AFTER the keep
  choice, if independently validated.
- Refit Qkeep and backward continuation if bottom selector later
  becomes a candidate for general replacement. No self-consistent
  DP claim for this isolated intervention.

## Reporting and stopping

Training fit diagnostics are not performance verification.
Validate on NEW unseen 114000..114063 physical v27-kept hands, with
8 fresh shared hidden 92-card permutations per arm, strict stable
beam160, grouped CI. Compare v33b pairwise to v14 plus archived
search-free selectors as controls; report T1/T2/T3 and changed hands,
seat/stage distributions, independent game groups and runtime.

Do not promote unless independent T2 improves without material
T1/T3 loss. If conditional value is not established, stop expanding
the model family. Prefer fixing candidate-selection/label precision
over another RF sweep.

This is a physical goldfish Dack deployment study; not interactive
cEDH multiplayer win probability.
