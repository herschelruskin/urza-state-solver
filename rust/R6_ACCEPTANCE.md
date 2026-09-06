# R6 Acceptance

Baseline before final acceptance work: `c46c5427f8dbe43d24363831ee17361a4113d7b7`.

Classification: POLICY / RNG / INFORMATION-BOUNDARY / REPORTING acceptance. R6 does not broaden R4 card/rules coverage and does not port Python gameplay or policy logic.

## Accepted R6 surface

- [x] Commander deck construction is exactly 99 main-deck cards plus Urza in the command zone.
- [x] Pregame seat/Caverns eligibility is sampled before the opening hand and remains fixed through the mulligan sequence.
- [x] Fresh sevens are generated lazily and only after the current visible seven is rejected.
- [x] Mulligan policy never receives the rejected-hand identity in continuation cache identity and never receives an actual unrevealed next seven.
- [x] London bottom subsets are exhaustively enumerated: `1, 1, 7, 21, 35, 35` across InitialSeven, FreeSeven, Six, Five, Four, Three.
- [x] Every legal bottom package is valued through the accepted R5 hidden-world Monte Carlo and deterministic rollout stack; no beam pruning is used.
- [x] Keep-vs-mull continuation values use exact integer rational arithmetic and the accepted WinByHorizon ordering: total wins first, then exact-turn wins T1 through T6.
- [x] Exact sampled ties keep the current hand.
- [x] Mull-again continuation values are cached by deck/stage/pregame/policy/objective/environment/sample identity without rejected-hand or actual future-seven identity.
- [x] The stable report surface includes current/starting seven, mulligan depth, seat/Caverns facts, policy/horizon/environment identity, exact cumulative P(win by T1..T6), best keep, mull-again continuation, exact primary value gap, finite-sample uncertainty resolution, sampled decision-confidence classification, and all alternate bottom packages.
- [x] Uncertainty reporting is explicitly non-statistical for recursive continuation aggregates: it reports exact finite-sample resolution rather than pretending recursively reused child values are independent Bernoulli samples.
- [x] An independent brute-force toy acceptance oracle enumerates every deterministic policy in a two-future-hand keep-3 instance (`35 x 35 = 1225` policies) and must match the production DP continuation value exactly.
- [x] A fixed-seed sequential trace records `DecisionMade(Mulligan)` before `FreshSevenGenerated` and proves that keeping an initial seven generates zero future hands.
- [x] A future-invariance regression samples two distinct hypothetical next sevens outside the decision inputs and proves the current mull-again continuation result/cache identity is unchanged.
- [x] A dedicated `r6-audit` binary checks deck size, bottom-subset counts, experimental floor, fixed-seed sequential generation count, and reports the frozen R6 version/contract identifiers.
- [x] The foundation workflow includes the R6 audit after the accepted R0-R5 gates.

## Versioned R6 contracts

- `MULLIGAN_ENGINE_VERSION = r6_sequential_london_v2`
- `OPENING_RUNTIME_VERSION = r6_opening_state_v1`
- `MULLIGAN_DECISION_VERSION = r6_keep_vs_mull_dp_v1`
- `MULLIGAN_OBJECTIVE_VERSION = r6_normalized_win_by_horizon_v1`
- `MULLIGAN_REPORT_VERSION = r6_mulligan_report_v1`
- `MULLIGAN_UNCERTAINTY_VERSION = r6_finite_sample_resolution_v1`
- `MULLIGAN_TRACE_VERSION = r6_fixed_seed_sequential_trace_v1`

## Acceptance gate

The branch is R6-accepted only when all of the following pass together on the same head SHA:

1. `cargo metadata --locked --format-version 1 --no-deps`
2. `cargo fmt --all -- --check`
3. `cargo clippy --locked --workspace --all-targets --all-features -- -D warnings`
4. `cargo test --locked --workspace --all-targets`
5. `cargo check --locked --workspace --benches`
6. R0 audit
7. R1 audit
8. R2 audit
9. R3 audit
10. R4 audit
11. R5 audit
12. `cargo run --locked -p urza-mulligan --bin r6-audit`

The brute-force oracle, sequential trace regression, report contract tests, exhaustive-bottom tests, and future-invariance regression are part of the workspace test gate rather than separate ad hoc scripts.

## Deliberately outside R6 acceptance

- No new Gemstone Caverns gameplay implementation is added here; only pregame eligibility remains visible.
- No new card/rules mechanics beyond accepted R4 are introduced.
- No Python gameplay/policy logic is ported.
- No claim is made that finite sampled values are exact population probabilities; report uncertainty states the finite-sample resolution and keeps statistical inference outside policy identity.
