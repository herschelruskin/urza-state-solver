# R6 Mulligan Start Checkpoint

Baseline: `rust-engine-rebuild` commit `53f57bcda4e2569d2f9e7a2997872ad75265e767` (finalized R5 parallel-scaling closure).

Classification: POLICY / VALUE application architecture. No rules/card broadening and no Python gameplay/policy port.

R6 begins the first flagship application from the retained non-Oracle roadmap: an information-faithful sequential Commander/London mulligan engine in the already reserved `urza-mulligan` crate.

## Contract recovered from the audited architecture trail

The mulligan engine must:

- evaluate the current seven before any later seven is generated or revealed;
- model the sequence `initial seven -> free multiplayer seven -> keep 6 -> keep 5 -> keep 4 -> keep 3`;
- treat keep-3 as an experimental simulation floor, not a Magic rules floor;
- expose pregame seat / Gemstone Caverns eligibility before mulligan decisions when those facts are known;
- enumerate every legal London-bottom subset in deep/single-hand analysis (`7`, `21`, `35`, `35` subsets for bottom counts 1 through 4);
- avoid beam-search suppression of legal bottom packages;
- carry chosen bottom knowledge forward under a documented canonical ordering until a reachable rule requires bottom-order branching;
- cache the expected value of taking another mulligan by deck/stage/pregame/policy/objective/horizon/environment identity without including the rejected hand when the fresh-seven distribution is independent of it.

## R6 start slice implemented

- [x] Added explicit `MulliganStage` values for the six sequential Commander stages.
- [x] Added exact kept-card and bottom-count semantics for every stage.
- [x] Preserved one free multiplayer seven.
- [x] Enforced the experimental keep-3 floor as policy behavior.
- [x] Added `PregameContext` carrying seat and Gemstone Caverns eligibility into every stage.
- [x] Added `MulliganState` containing only the currently visible seven plus pregame facts.
- [x] Made next-seven generation lazy and available only on the mulligan branch; the generator receives stage/pregame facts, never the rejected hand.
- [x] Added exhaustive unordered bottom-subset enumeration with exact counts `1, 1, 7, 21, 35, 35` across the six stages.
- [x] Added exact bottom-choice validation for count, duplicate indices, and out-of-range indices.
- [x] Added canonical kept-hand / known-bottom ordering to avoid meaningless bottom-order branching at this checkpoint.
- [x] Added a continuation-cache key and deterministic `BTreeMap` cache whose type does not contain rejected-hand identity.
- [x] Added unit regressions covering the stage schedule, exhaustive subset accounting, lazy future-seven generation, floor behavior, malformed bottoms, canonical bottom knowledge, and rejected-hand-independent continuation identity.

## Still required before R6 acceptance

- [ ] Add the actual Game-domain opening-hand / reshuffle generator using the accepted coordinate RNG scheme.
- [ ] Add batch pregame seat/Caverns sampling and prove the sampled fact is fixed before mulligan policy evaluation.
- [ ] Bridge a kept hand plus known-bottom package into the accepted `TrueState` / `InformationState` opening state without exposing hidden order.
- [ ] Evaluate every legal bottom package with the accepted deterministic/Monte-Carlo continuation stack.
- [ ] Add cached mull-again continuation values and keep-vs-mull comparison.
- [ ] Report best keep value, mull-again value, value gap / confidence, full T1-T6 win curve, and optional alternative bottom packages.
- [ ] Add the independent brute-force toy mulligan oracle and compare it with the R6 result.
- [ ] Add fixed-seed sequential trace acceptance proving future sevens are not generated before a mulligan decision requires them.
- [ ] Run locked formatting, workspace tests, strict all-target/all-feature Clippy, and cumulative acceptance/audit commands in GitHub Actions.

This checkpoint starts R6 proper without changing the frozen R4 rules semantics or the accepted R5 rollout/Monte-Carlo semantics.
