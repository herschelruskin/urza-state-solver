# R6 Keep-vs-Mull Value Checkpoint

Baseline: `rust-engine-rebuild` commit `4d8c2c1d139e95ae8f0ac1b06d69c40388410967` (green R6 opening-state slice).

Classification: POLICY / VALUE integration only. No R4 rules/card broadening and no Python gameplay/policy port.

## This slice

- [x] Added exhaustive value evaluation for every legal London-bottom package using the accepted R5 hidden-world Monte-Carlo evaluator and deterministic continuation policy.
- [x] Preserved exact bottom enumeration; no beam pruning or package suppression is introduced.
- [x] Added exact normalized `WinByHorizon` comparison using integer rational outcome rates rather than floating-point policy identity.
- [x] Preserved the R5 objective ordering: maximize total win rate first, then prefer earlier exact-turn win rates T1 through T6.
- [x] Added recursive expected mull-again continuation values through the experimental keep-3 floor.
- [x] Added a continuation cache keyed by deck version, target stage, fixed pregame facts, R6 decision/objective versions, R5 policy version, horizon/environment, continuation sample root/world range, future-hand sample count, and R5 rollout sampling/budget identity.
- [x] The continuation cache key contains no rejected-hand identity and no actual unrevealed next-seven world.
- [x] Added a public `evaluate_mull_again` API that structurally accepts only stage/pregame/configuration inputs, so rejected-card identity cannot enter continuation value.
- [x] Added deterministic KEEP-vs-MULL selection. Exact objective ties keep the current hand.
- [x] Added an exact primary total-win-rate gap plus the full objective preference, so an equal total-win rate can still be distinguished by earlier-turn objective ordering.
- [x] Added cached continuation keep/mull decision counts for auditability.
- [x] Added a real R5 integration regression that values the visible initial keep package, plus exact-rate normalization/gap/accounting regressions.

## Important semantics

A mull-again continuation value is an expectation over a configured fixed set of future fresh-seven sample worlds. It is not the value of the actual unrevealed next seven. The actual current game world is deliberately absent from the continuation API and cache identity.

Nested continuation sample counts differ by stage, so raw R5 win counts cannot be compared directly. R6 therefore scales the accepted R5 T1-T6/loss outcomes to exact rational rates using integer arithmetic. No floating point enters deterministic keep/mull identity.

## Still required before R6 acceptance

- [ ] Add user-facing mulligan report output with T1-T6 probabilities, confidence/uncertainty presentation, selected bottom package, mull-again value, value gap, and alternative bottom packages.
- [ ] Add the independent brute-force toy mulligan oracle and compare it with the R6 dynamic-program result.
- [ ] Add fixed-seed sequential trace acceptance proving an actual future seven is not generated before the decision that consumes it.
- [ ] Add an R6-specific cumulative audit/gate once the remaining acceptance artifacts exist.

This checkpoint does not change frozen R4 gameplay semantics or accepted R5 rollout/Monte-Carlo semantics; it composes those accepted layers into the first R6 keep-vs-mull decision value.
