# R6 Opening-State Checkpoint

Baseline: `rust-engine-rebuild` commit `55298ad635e7b5b828e83647f95c2f1fa87398c3` (R6 sequential mulligan start).

Classification: POLICY / RNG / INFORMATION-BOUNDARY application architecture. No R4 rules/card broadening and no Python gameplay/policy port.

## This slice

- [x] Replaced the initial R6 source layout with a formatted `engine` module while preserving the sequential mulligan API and acceptance regressions.
- [x] Loaded the audited Commander deck as exactly 99 main-deck cards plus the single commander.
- [x] Added fixed pregame seat sampling before the initial seven. Seat uses the accepted coordinate PRF under the `Environment` RNG domain and exposes Gemstone Caverns eligibility as `seat != 1`.
- [x] Added stage-scoped fresh-seven generation under the accepted `Game` RNG domain with a dedicated R6 event type and deterministic stage logical-event identity.
- [x] Kept exact hidden remainder order outside `MulliganState`; `draw_fresh_seven` returns only the visible seven.
- [x] Added `start_mulligan_game` and `take_mulligan` so the sampled pregame context remains fixed while fresh sevens are generated only after a mulligan is actually taken.
- [x] Added a kept-hand bridge that deterministically reconstructs the accepted exact shuffle from `(deck, root, world, stage)`, verifies the visible kept package, then builds a turn-1 `TrueState` with Urza in the command zone.
- [x] London-bottom cards are appended in the documented canonical order and represented as exact `known_bottom` information; the unknown library middle remains hidden in `InformationState`.
- [x] Added a bridge regression proving that permuting only the exact unknown middle changes `TrueState` but not the legal information projection.
- [x] Added explicit 99+Urza, RNG-domain separation, replayability, fixed-pregame, bridge-size, mismatch-rejection, and canonical-bottom regressions.
- [x] Updated the locked workspace graph for direct `urza-core`, `urza-info`, and `urza-rng` use by `urza-mulligan`.

## Deliberately not claimed yet

- [ ] No bottom package is value-ranked yet.
- [ ] No keep-vs-mull continuation value is computed yet.
- [ ] Gemstone Caverns eligibility is visible pregame context, but this checkpoint does not add a new Caverns pregame rules implementation.
- [ ] No mulligan output report / confidence gap exists yet.
- [ ] R6 acceptance still requires the brute-force toy oracle and fixed-seed sequential trace acceptance.

## Next slice

Wire every legal bottom package into the accepted R5 deterministic/Monte-Carlo continuation evaluator, then add cached mull-again continuation values and the keep-vs-mull comparison without allowing the rejected hand or unrevealed future seven into strategic identity.
