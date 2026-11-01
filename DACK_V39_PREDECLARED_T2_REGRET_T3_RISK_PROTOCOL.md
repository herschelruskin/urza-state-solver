# DACK v39: precommitted T2-first action regret with a bounded T3 trade-off

**Independent experimental branch:** `dack-v39-t2-risk-bounded-regret-20261101`.
Do not modify or promote v5, v27, v33b, v37, or v38.

## The causal motivation and the deliberately different objective

The archived v37 model was trained on 384 physical groups and 15,360
true 126k strict-beam160 futures directly labeling signed
A2=Qkeep(byT2)−Qmull(byT2), A3=Qkeep(byT3)−Qmull(byT3), under
the EXACT frozen-v27 future keep/frozen-v33b bottom. It was NOT
fitted to teacher action labels. v37's actual strict T3 guard
caused zero of 768 independent 127k early actions to change.
Physical posthoc *selected* 24-case diagnostic found new MULL
T2 +15.59pp and T3 −18.95pp, with physically resampled shared C.
v38 cumulative-weighted utility policy changed only 3 of
1536 fully random new 129k stage states, reaching only two
full London paths, and failed its pre-outcome coverage gate.
The 127k and 129k cohorts are consumed; neither may validate v39.

For this new **single v39 candidate**, prioritize positive real
T2 action regret subject to an explicit **maximum predicted
25pp loss of byT3 for any one changed action**. This is an
experimental tolerance, NOT a normative recommendation to
sacrifice 25pp byT3 in real cEDH. No refit of v37, no
change to game engine, no new hidden-future peeking.

12 v37 group/bootstrap value forest members:
- Original frozen v27 MULL -> v39 KEEP only if the
  lower quartile predicted A2 >+0.02 AND lower
  quartile predicted A3 >=−0.25.
- Original frozen v27 KEEP -> v39 MULL only if
  upper quartile predicted A2 <−0.02 AND upper
  quartile predicted A3 <=+0.25.
- Otherwise unchanged original v27 keep action.
- Stages0/1/2 only. Later London keep unchanged.
  If keep, retained cards/bottom are exact immutable
  frozen-v33b pairwise regret output. Terminal stage7
  force KEEP.
- Note model bootstrap quartiles are a heuristic
  decision consistency filter, NOT well-calibrated CI.
- The 25pp value was chosen to examine the T2/T3
  Pareto frontier after a failed strict T3 veto;
  no claim of prior independence from the 127k
  diagnostic. Therefore **131k fresh data is mandatory**.

## Frozen first-phase unseen 131k cohort

Physical independent random game IDs 131000..132023,
N=1,024 groups × every actual early London stage0,1,2
= **3,072 full population stage states**. Before drawing
ANY new gameplay outcome, enumerate the observable
sevens, original v27 actions, v39 actions, and complete
real 99-slot final hand+library under both policies.
Archive complete outcome-blind census. Count exact
reached divergences, not hypothetical unreachable
stages. Respect first free seven vs second seven.

Stop WITHOUT physical gameplay if fewer than 24
changed early-stage actions or fewer than 12
complete physical London trajectories differ.
Do not loosen either rule after looking at census.

Otherwise independently sample only changed KEEP
action outcomes: 32 independent hidden92 physical
shuffles per altered stage × same original selected
v33b bottom, stable dice, actual strict beam160.
Physical shared C for only relevant seat-stage
cells: 128 independent restored-full99 later London
continuations each, exact frozen v27 keep+v33b bottom.
ALL untouched 3,072 stage states have algebraically
ZERO conditional action regret and remain in the
denominator; do not treat the changed subset as
representative. Bootstrap N1024 independent physical
outer game IDs; within-hand futures; per-cell shared
C draw sampled ONCE per bootstrap replication.
Primary T2 change, T1/T3 secondary safety metrics.

Acceptance gate for a prospective new 133k full-game
physical paired benchmark is:
- at least 24 stage and 12 reached path changes;
- strictly positive lower 95% two-source bootstrap
  interval for random-population mean byT2 action gain;
- non-negative upper 95% CI for byT1 effect
  (no convincing T1 harm);
- mean random-population byT3 decline no more
  than 1.5 percentage points.
Only if satisfied, 133k paired v33b-v39 end-to-end
physical goldfish benchmark; v5 expensive reference
only if improvement survives. Do not assert
one-step policy-value = full-policy Bellman value.

This v39 objective intentionally differs from
v38 U=PbyT2+.5 PbyT3, because the user prioritizes
speed while wishing to observe consistency cost.
Never erase or conceal the T3 downside. This is
NOT multiplayer cEDH win probability or full
cards-rules proof.
