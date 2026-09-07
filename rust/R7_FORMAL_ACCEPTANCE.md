# Formal R7 Acceptance — London mulligan DP

Status: **ACCEPTED** against the audited v2 Rust rebuild roadmap.

This file uses the audited specification's milestone numbering. Historical Rust identifiers such as `r6_*` are retained for provenance; see `rust/AUDITED_MILESTONE_MAP.md`.

## Audited R7 scope

Formal R7 is the London mulligan DP milestone. Its audited deliverables are:

- exact London bottom enumeration;
- seat-conditioned Gemstone Caverns context;
- adaptive bottom racing only as an EXPERIMENT, not inherited gameplay semantics;
- exact confirmation bounds only under their documented preconditions;
- backward stage DP.

The audited gate is human-hand evaluation parity plus Stage 5I fixtures.

## Accepted Rust implementation

The historical Rust `r6_*` mulligan surface is the implementation of formal audited R7.

Accepted contracts include:

- Commander construction as exactly 99 main-deck cards plus Urza in the command zone;
- seat/Caverns eligibility sampled before the opening hand and held fixed across the mulligan sequence;
- lazy fresh sevens generated only after rejection;
- exhaustive unordered London bottom subsets `1, 1, 7, 21, 35, 35` for InitialSeven, FreeSeven, Six, Five, Four, Three;
- every legal bottom package valued through the accepted hidden-world Monte Carlo plus deterministic rollout stack, without beam pruning;
- exact integer/rational keep-vs-mull objective using total win probability first and T1..T6 lexicographic timing second;
- backward stage continuation with cache identity excluding the rejected hand and any actual unrevealed future seven;
- exact finite-sample ties keep the current hand;
- a brute-force independent toy oracle over `35 x 35 = 1225` deterministic keep-3 policies matching production DP exactly;
- fixed-seed sequential trace and future-invariance regressions proving no future-seven oracle leakage;
- execution bridge from the accepted kept package into a turn-1 `TrueState` with exact sampled execution library plus legally known London bottom information.

The accepted Rust baseline intentionally remains exhaustive. Adaptive bottom racing is not silently promoted into normative Rust semantics.

## Adaptive-racing experiment status

The audited source describes bottom racing as EXPERIMENT rather than a rules/policy contract. The historical Phase-5I runtime-v2 work supplies that experiment: parallel bottom evaluation, bounded paired tie re-screening, and exact optimistic early elimination were implemented and tested without redefining gameplay semantics.

Formal R7 acceptance does **not** require those runtime-v2 heuristics to become the Rust production evaluator. Any future Rust racing implementation must remain deterministic, preserve the fixed evaluation contract/common-random-number coordinates, and reopen parity/performance gates before promotion.

## Human-hand and Stage-5I witness

The authoritative accepted non-oracle Python validation run is GitHub Actions run `33202063879` at source head `206282ba72413e61f18c6d5119d880126506bd8f`. The run completed successfully.

Its retained aggregate artifact:

- artifact: `phase5i-final-symbolic-benchmark`;
- artifact id: `9703149385`;
- digest: `sha256:4014db47fb2130594627f586ce88903a6e6b2d3a0a89b17c522f09a6e3f0570b`;
- contains the final human benchmark summary, disagreement report, and live/dead factorized Stage-5I models.

The human summary contains all **35 exact usable human benchmark hands**. The homogeneous Phase-5I campaign also evaluates the factorized London continuation sample grid; the launch record identifies **112 stage-continuation samples** and requires homogeneous aggregation only after all source artifacts complete.

Human decisions remain held-out evaluation labels. Formal R7 parity does not mean tuning Rust until it copies the human keep/mull answer. The accepted Python outputs are PARITY witnesses for the solver/evaluation architecture and fixtures.

## Rust-vs-Python parity interpretation

The audited source hierarchy is controlling:

1. current rules/Oracle + explicit model decisions;
2. audited information/deterministic fixtures;
3. accepted Python behavior as a regression witness;
4. historical/rejected/experimental behavior as evidence only.

Therefore historical Python finite-sample values are not treated as a Magic invariant. Production Rust intentionally differs where the audited rebuild corrected the model, including occurrence-indexed RNG and own-life accounting from 40. A mismatch caused solely by those versioned corrections is classified rather than forced back to Python.

Formal R7 closure means the Rust London DP, information boundary, exact bottom enumeration, stage recursion, objective, and fixed acceptance fixtures satisfy the audited contract while the accepted 35-hand/Stage-5I campaign remains the external parity witness.

## Rust acceptance evidence

Historical implementation acceptance is recorded in `rust/R6_ACCEPTANCE.md`; under the formal roadmap that document is the core-R7 implementation gate.

The latest pre-reanchor fully accepted Rust engine head is `908ed44b07dc02e1efdf3e2f6c84d9d1775b876f` with cumulative foundation run `34070622761` green across format, strict Clippy, workspace tests, bench compile, R0-R6 historical audits, and the post-R7 teacher/corpus checks.

The post-R7 teacher/signal-boundary work is not used to redefine the formal R7 gate.

## Formal close

**R7 (London mulligan DP) is closed.**

The next work before formal R8 is explicitly post-R7 validation: move the teacher/signal-boundary ladder backward into replayable actual game states, keep the teacher read-only, and repair production only when that diagnostic identifies a reproducible correctness defect. Formal R8 remains native performance hardening, with Hand 25 plus no semantic regression as its gate.
