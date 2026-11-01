# DACK v38 — single frozen weighted direct-action-regret experiment

Research branch `dack-v38-weighted-action-regret-20261101`.
**Predeclared before evaluating any NEW 129k gameplay outcomes.**
v5, v27, v33b and v37 remain unchanged. No automatic promotion.

## Why this is a different objective, NOT threshold tuning on old holdout

The v37 physical direct-action learner was trained on 126k
(384 independent 99-card physical groups, 12,288 true K futures,
3,072 complete-99 real C futures). It was NOT taught v5's KEEP
labels. Its strict T3-protection rule changed ZERO of 768 new
random 127k early-stage actions. A posthoc physical study on the
24 *T3-blocked* 127k actions found MULL-vs-KEEP +15.59pp byT2
(95% selected-case grouped CI +7.78 to +22.11) but −18.95pp
byT3 (−28.36 to −8.09). The opposite directions were predicted
by the model. This is evidence of an authentic speed/consistency
tradeoff in the SELECTED cases, not generalization evidence.

The project's early objective `P(T2)+0.5*P(T3)` is now defined
explicitly for this experiment as
**U = P(win BY T2) + 0.5 × P(win BY T3)**.
This gives greater weight to earlier wins but preserves positive
credit for slower wins. It is DIFFERENT from
`P(byT2) +0.5*P(win EXACTLY T3)` used by the old v5 teacher:

  U_cumulative = 1.5 P(byT2) + .5 P(exactly T3)
  U_v5_exact3  = .5 P(byT2) + .5 P(byT3)

An observed action advantage for U_cumulative therefore does
not prove the old v5 blended utility improves or that every
T3 sacrifice is acceptable. This policy explicitly prioritizes
T2 more. The original v37 T2/T3 model remains completely frozen;
this is not a new fit and not an inference from 127k physical
outcomes.

## Single fixed pre-129k action policy

For the SAME one of 12 v37 physical-group/C-bootstrap forest
members, compute signed
`A2 = Qkeep_byT2 − Qmull_byT2`,
`A3 = Qkeep_byT3 − Qmull_byT3`,
`Uregret = A2 + 0.5*A3`. Pair U2 and U3 for each SAME
bootstrap member before obtaining quartiles; independently
sorting Q2/Q3 first destroys their correlation.
Only original actual London stages0/1/2 may change:
- v27 MULL -> v38 KEEP if ensemble 25th percentile
  Uregret is > +.02.
- v27 KEEP -> v38 MULL if ensemble 75th percentile
  Uregret is < −.02.
- all other cases unchanged original frozen v27 KEEP.
- v33b bottom original 99-slot legal hand retained;
  no difference in card bottom if KEEP and no hidden
  physical future knowledge; stage7 forces KEEP.
- NO separate T3 veto: its expected cost is already
  penalized with a positive half-weight in utility,
  and must be reported. No accuracy claim before fresh validation.

## New independent validation and acceptance

Untouched independent physical IDs **129000..129511**
(512 outer physical games), all three actual stage0/1/2
sevens per game = 1,536 decision states. Compute
action census and actual full London paths BEFORE ANY
129k gameplay labels; completely freeze model and
entire 1,536 denominator. Do not use 127k selected
physical outcomes or 129k outcomes to choose a policy.

If at least 12 stage interventions and at least eight
actual London *full-path* changes occur, proceed to
exact-zero-regret sparse two-source physical validation:
- 32 independent shuffled-unknown92 actual beam160
  KEEP outcomes for each of the altered stage decisions.
- 128 restored-full99 later London MULL continuations
  for each affected (seat,stage), exactly one C cell
  shared across all corresponding selected hands.
- No outcomes for 1,536 minus changed SAME-action
  states because their signed one-step action difference
  is algebraically exactly zero. Preserve all 1,536
  stage states and all 512 outer physical IDs when
  computing population-average signed changes.
- Bootstrap independent 512 outer physical group IDs,
  within-hand actual KEEP futures, and each shared
  C lottery exactly ONCE per bootstrap draw.
- Report (not hide) byT1, byT2, byT3 and
  U=PbyT2+.5 PbyT3, absolute percentage-point
  population-average differences, stage/direction
  breakdown, actual-path change count and uncertainty.

**Acceptance gate** precommitted:
1. At least 12 actual stage changes among 1536 and at
   least eight real London final-state changed games.
2. Strictly positive two-source 95% bootstrap lower
   endpoint for mean U conditional action improvement.
3. Positive estimated by-T2 gain, no convincing by-T1
   harm, and overall by-T3 estimated decline no more
   than 1.5 percentage points across all 1,536
   random stage decisions.
If failed, STOP; no prospective whole-game test.
Do NOT choose a different U weight or policy gate
based on 129k results and call 129k untouched again.

If passed, independent 130k physical N256 full-game
paired v33b-v38 first, with no hidden draw access,
exact real 99-card initial slots, same first seven and
seat, stable chance and actual gameplay beam160.
Only then consider whether expensive v5 full-game
reference is worth its runtime. A one-step Q
under the frozen v27 future is NOT
Bellman self-consistent for modified v38 future paths.

## Distinct statistical pitfalls

- v37 127k T3-blocked retrospective 24-case study is
  posthoc, not a valid generalizable validation.
- T3 cumulative and EXACT T3 rewards must not be
  conflated; both should be displayed for insights,
  but only stated U is the primary 129k objective.
- Physical futures of a single hand share the hand
  and are NOT independent opening hands.
- Shared C is NOT a per-hand independent sample:
  resample once per seat-stage cell per bootstrap.
- Original London stage0 and stage1 are distinct
  despite both 7-card hands.
- Never canonicalize real beam game states by
  approximate feature equivalence; zero-action
  regret pruning is valid ONLY for policy comparison.
- This is an individual goldfish Dack-deployment
  simulation, not actual four-player cEDH match win
  probability.
