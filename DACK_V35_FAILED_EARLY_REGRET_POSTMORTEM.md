# DACK v35 postmortem — early direct action regret does NOT generalize

**Date:** 2026-11-01. **Verdict: stop; no prospective 122k run,
no model promotion or engine change.** Research branch:
`dack-v35-early-action-regret-20261101`.

## Why v35 was attempted

Corrected v34c identified 100 first actual London KEEP/MULL
disagreements between expensive v5 and zero-beam v27 in 115k.
Forced actions with a common frozen v33b bottom/continuation gave
+10.59pp expected T2 value when following the v5 action on
THOSE SELECTED disagreements, with a two-source bootstrap
CI +6.21..+15.25pp. The result was conditional on v5-v27
disagreement; it did NOT claim a whole-deck gain. Earlier
v34 globally shifted keep-value bias and continuation and
failed heldout validation (-0.11pp expected T2).

v35 was designed to learn direct **Q(KEEP)-Q(MULL)**,
not imitate the v5 keep label or use exact card-ID fingerprints.
After correction, retaining an early seven still uses the exact
frozen v33b bottom candidate. Actual gameplay engine,
physical 99, terminal stage, stable chance and beam160 remain
identical. v35 only considered London stages 0..2, preserving
later v27 decisions.

## Frozen training before inspecting any 121k outcomes

Single 19-feature low-dimensional regularized ridge ensemble:
24 outer-game-group bootstrap models, lambda16, fixed prior
frozen v27 Qkeep-vs-C margin with bounded residual [-0.35,+0.35].
Features: old Qkeep/margin, stage0/1/2, seat, mana/white/two-mana
lands, ramp/zero mana, tutor, Chrome Mox fuel, Opal support,
combo brick, analytic T2 capability. NOT a gameplay-state
identity key or card-text substitute.

Only source data:
- 64 independent 116000–116063 physical groups × 7 London
  stages × 8 true beam160 keep futures.
- 100 separately selected 115k first-policy-disagreement
  groups × 16 fresh `calibration` keep futures.
- v34 shared frozen-v33b Qmull 64 physical `train`
  futures per seat-stage. ALL 99 physically returned on
  mull; later stages reshuffled independently.
- Outer-group weighting, 116k 7 stages weighted
  1/7 each; selected 115k groups weight .75; early stage
  multiplier ×2. No v5 label imitation.

**Not used:** 117k previously inspected validation,
v34c replication, realized original 115k win turns or
any 121k future. Full training census 164 independently
grouped physical games, 548 action-stage states. Frozen
training model SHA256:
`eb943aa0c65e3d00e7f6f22f32afc3477b9ab1cfdfcbb473f81a0bbf8c911e02`.

Predeclared action stability gates: override only stages
0–2, T2 ensemble lower quartile > +0.06 (mull→keep)
or upper quartile < −0.06 (keep→mull), and symmetrical
T3 model safeguard allowing no more than 4pp
predicted T3 decline in either direction. Quartiles
are ensemble heuristic stability, NOT calibrated
confidence intervals. All other states keep frozen v27
action. Terminal stage7 always KEEP.

## Fresh 121k independent physical validation

GitHub Actions run 41277741822 **SUCCESS**:
all **60 physical shards** completed, all archived.
- KEEP: 128 independently dealt physical 99-card
  outer game IDs 121000..121127; every actual
  stage0..6 (896 stage states), 8 fresh physical
  hidden-92 reshuffles per state = 7168 strict
  beam160 deployments.
- MULL: 4 seats ×7 London decision stages ×64 independent
  physical later full99 reshuffles under EXACT frozen
  v27 keep/frozen v33b bottom = 1792 deployments.
- Grand total **8960 new actual beam160 outcomes**.
  No peeking or new model fitting.
- Estimate one-step expected value of candidate chosen
  action minus frozen v27 action, with true
  Qkeep–shared Qmull. Bootstrap resamples independent
  outer physical groups, all within-hand KEEP futures,
  and shared seat-stage Qmull lotteries (only once
  per cell per replication).
- This is still a *one-step conditional comparison*;
  a changed full policy would require a further
  self-consistent continuation/prospective check.

### Correctly gated held-out result

| Measure | Changed actions / 896 stage states | Conditional mean difference | Two-source 95% bootstrap |
|---|---:|---:|---:|
| T1 safeguard | 8 | +0.026pp | [−0.009,+0.071]pp |
| **T2 primary** | **8** | **+0.0645pp** | **[−0.1569,+0.3139]pp** |
| T3 safeguard | 8 | −0.1011pp | [−0.2703,+0.0366]pp |

- 1 MULL→KEEP, 7 KEEP→MULL, among 896 sampled
  stage states; **only 8/384** early stage0-2 states changed.
- T2: four positive, four negative measured changed-stage
  differences. No statistically convincing improvement.
- T3: one positive, seven negative measured changes.
  The CI includes zero, but the direction is an
  additional reason not to advance this model.
- Stage 0: +0.488pp T2 averaged over 128 stage0 states,
  from one changed decision.
- Stage 1: +0.012pp T2 over 128 stage1 states,
  five changed decisions.
- Stage 2: −0.049pp T2 over 128 stage2 states,
  two changed decisions.
- Stage3–6: zero interventions by design. No policy is
  silently trained or optimized on those labels.

## Interpretation and failure mode

The causal v34c disagreement advantage was real on
selected policy-discordant hands, but **v35 did not
generalize a useful decision rule** to independent
unselected physical hands. The sparse 19-feature
regularized correction with conservative bootstrap gates
almost always reproduced v27. Even its eight decisions
were not clearly better than v27 on physically replayed
independent hands. We cannot infer that loosening the
gate, strengthening regularization or changing feature
weights would help; trying such changes *on 121k*
would invalidate 121k as a holdout.

This result is NOT proof v27 is optimal, nor proof
that the underlying v34c causal result was false.
It shows that our PARTICULAR v35 decision policy
has not recovered a meaningfully deployable fraction
of the opportunity. In retrospect, more precise
and diverse actual action-regret supervision is needed,
not another quick forest or an arbitrary continuation
threshold adjustment.

## Recommendations (not run or promoted)

1. Freeze v35 as a **failed experimental model**.
   Do not launch preprepared `122k` four-policy
   prospective script: the independent conditional
   acceptance gate did not pass.
2. Recover the strong earlier baseline: v33b bottom-only
   policy had prospective +5/256 by T2 versus v27,
   with about 61.6× speedup versus v5 in 115k.
3. For a potential v36, reserve NEW independent physical
   123k+ training hands and separate subsequent validation.
   Improve **label precision and coverage near early-stage
   action boundaries**; focus on action *regret* and
   per-game grouped training rather than imitation of
   v5 keep labels.
4. Prioritize real physically sampled KEEP outcomes on
   diverse early-stage high-leverage lines (two-white
   access, LED, fast mana, Mox resource constraints,
   uncastable combo pieces), not exact irrelevant bottom
   IDs. Estimate uncertainty of the shared seat-stage
   Qmull in inference; 24 model bootstraps alone are
   not formal C uncertainty.
5. Test a NEW frozen candidate on truly independent
   physical validation, then full-game prospective
   paired T1/T2/T3 and wall/runtime only if a clear
   conditional improvement holds. Retain 99-card
   physical shuffles, London stage0/1 distinction,
   stable chance and strict gameplay beam160.

All physical outcomes, scripts and trained files
are archived under the research branch. Goldfish
Dack deployment is NOT multiplayer cEDH win probability.
