# Post-R7 StepLimit diagnostic

## Status

Diagnostic only. This document records the isolated `RolloutStop::StepLimit` found while scanning accepted natural R7 pilot openings. It does **not** change R4 gameplay rules, R5 policy ranking, mulligan behavior, cache identity, or search semantics.

## Reproduction

- accepted opening profile: `r7_pilot_16_worlds_1x1_v1`
- opening world: `100004`
- opening hand: `Mystical Tutor | Saprazzan Skerry | Sink into Stupor | Force of Will | Mindbreak Trap | Disruptor Flute | Manifold Key`
- hidden world: `216536`
- scan root: `RootSeed([2, 0, 76, 76, 79, 82, 55, 82, 253, 255, 179, 179, 176, 173, 200, 173, 110, 164, 4, 0, 152, 152, 158, 164, 128, 137, 233, 73, 234, 70, 74, 0])`
- rollout maximum: `4096` policy actions
- stop: `RolloutStop::StepLimit`
- final turn: `6`
- trace length: `4096`
- isolation workflow run: `34077885691`

The exact diagnostic sidecar is `post-r7-step-limit-isolate`; it scans only the supplied accepted opening/range and emits the first StepLimit world plus its full public semantic trace.

## Exact repeating suffix

The trace becomes exactly period-3 at trace index `82`, on turn 6 Upkeep, and remains period-3 through the step cap. The suffix contains `4014` actions, exactly `1338` full cycles:

1. `ActivateAbility` — Basalt Monolith (`CardDefId(5)`) native untap, public payment detail ending in `2` colorless;
2. `PassPriority` — resolves the native untap stack object;
3. `ProduceMana` — Basalt Monolith taps for `3` colorless.

The next action is the same two-colorless native untap, so each completed cycle returns the battlefield/phase/window/stack shape to the same decision shape while increasing colorless mana by exactly one.

Immediately before the repeating suffix, turn 6 Upkeep uses:

- trace 79: Ancient Tomb mana;
- trace 80: Seat of the Synod mana;
- trace 81: Sink into Stupor land-face mana.

Forensic Gadgeteer (`CardDefId(25)`) was cast and resolved on turn 5 at trace 75/76. The accepted R4 rules profile gives Gadgeteer artifact-activation reduction 1; Basalt's native untap therefore costs 2 instead of 3. This is an intentionally modeled positive-mana engine, not a Basalt rules-cost error.

## Why the accepted exact-state cycle guard misses it

R5 rollout v2 remembers an ordinary RNG-free semantic action only for the exact pre-action `TrueState`. This correctly escapes net-zero Basalt tap/pay-3-untap loops because the exact state recurs.

Here the loop is monotone: every Basalt/Gadgeteer lap adds one colorless mana. The exact `TrueState` therefore never recurs, so the v2 guard never suppresses the selected action. The public action sequence is stationary while one resource component grows.

This is a distinct **monotone resource recurrence** class, not a regression in the existing exact recurrence implementation.

## Why this is not a terminal-win detection fix

The accepted R4 terminal contract intentionally requires the relevant Urza context before `BasaltGadgeteer` is a terminal family. This isolated loop begins during turn 6 Upkeep without Urza on the battlefield. Reclassifying the state as terminal merely to stop the rollout would change accepted R4 win semantics and would manufacture a positive result, so that is out of scope.

## Why this is an R5 liveness defect

The deterministic baseline ranks ordinary empty-stack actions as `PlayLand`, then `ProduceMana`, then `CastSpell`, then `ActivateAbility`, then `PassPriority`. Once the turn-6 Basalt/Gadgeteer engine is live, the selected sequence can always regenerate more colorless before pass can advance the phase.

The loop occurs in Upkeep. Under the accepted sequencing kernel, floating mana is cleared on phase advancement, and command-zone Urza cannot be cast until sorcery timing. Repeating the upkeep loop indefinitely therefore prevents the rollout from reaching the phase in which its strategic continuation could occur.

R5 Monte Carlo treats `StepLimit` as an incomplete rollout/error boundary rather than a modeled loss. The finite scanner finding is therefore a production rollout-liveness bug even though the underlying mana engine is legal and positive.

## Repair constraints

A repair should remain in R5 rollout/policy liveness unless new evidence contradicts this diagnosis. It should satisfy all of the following:

- do not change R4 card legality, mana costs/effects, terminal families, or horizon semantics;
- do not special-case Basalt Monolith, Forensic Gadgeteer, or this hidden-world ID;
- do not globally erase or normalize mana from `TrueState`, replay identity, information, or value/cache keys;
- preserve the `urza-policy` public-state-only boundary;
- preserve stochastic retry eligibility and RNG-coordinate semantics;
- distinguish a genuinely progressing positive-resource recurrence from an exact no-progress recurrence;
- avoid exiting a positive-resource loop before additional resource could unlock a legal higher-ranked spend action;
- canonicalize only a proven deterministic liveness exit, with explicit namespace invalidation if rollout continuation semantics change.

## Required regression gate for a production repair

At minimum:

1. exact opening `100004` / hidden world `216536` must no longer stop at StepLimit;
2. the existing net-zero Basalt cycle escape tests must remain green;
3. a positive-resource loop must still be able to generate enough mana to unlock and take a useful legal spend action in a phase where such an action exists;
4. stochastic actions must not be suppressed by the new recurrence mechanism;
5. raw-ObjectId renaming must not change the public trace/exit semantics;
6. strict Clippy, workspace tests, bench compilation, cumulative audits, and the natural positive-trajectory scanner must pass;
7. the repaired exact seed must be inspected before widening the hidden-world scan again.

## Current conclusion

The isolated StepLimit is explained: it is a deterministic Basalt Monolith + Forensic Gadgeteer positive-colorless recurrence that changes only the accumulating mana resource while the public semantic action cycle repeats. R4 rules are behaving as accepted; R5 exact-state recurrence handling is too narrow for this monotone-resource liveness case.
