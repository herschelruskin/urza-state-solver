# Rust rebuild development log

## 2026-08-29 — R0 foundation implementation

Classification: architecture contracts are RULE/MODEL boundary infrastructure; card behavior remains explicitly INTENTIONALLY_UNMODELED in R0. The Hand 25 loader is PARITY/benchmark infrastructure. Criterion/workflow scaffolding is EXPERIMENT/performance infrastructure only.

Pre-implementation audit found no foundational contradiction in the audited v2 design. Two scope reconciliations were made:

- R0 contains an identity/count-only active-card catalog because the current request requires a catalog now, while pinned Oracle/rules metadata remains an R1 deliverable.
- root AGENTS.md contains Python/Oracle-era branch guidance, so rust/AGENTS.md scopes the audited clean-room authority hierarchy to the Rust workspace.

Implemented in R0:

- ten-crate workspace and pinned Rust 1.89 toolchain;
- CardDefId(u16), separate ObjectId, typed phase/window/mana/permanent/stack/pending/delayed/permission skeletons, and own-life default 40;
- exact ReplayKey retaining true library order and RNG progression;
- InformationState/PolicyView containing library belief but no true hidden order;
- strategic ValueKey skeleton plus a separate MC evaluation namespace contract;
- BLAKE3 coordinate PRF with game/outer-world/environment/policy domains, logical event IDs, occurrence IDs, concrete fingerprints, and pre-target CRN coordinates;
- active-card identity catalog and total coverage registry: 99 noncommander cards, 95 distinct names including Urza, every card explicitly INTENTIONALLY_UNMODELED with a reason in R0;
- Hand 25 benchmark fixture loader from the existing human benchmark corpus;
- structured engine counter/timing scaffolding and a Criterion replay-key microbenchmark;
- GitHub Actions format/clippy/test/bench-compile/audit workflow.

Validation:
- GitHub Actions run `33271673785`: PASS on commit `c8c49b85f66021299e0a4aee744fae60496e3860`.
- `cargo fmt --all -- --check`: PASS.
- `cargo clippy --workspace --all-targets --all-features -- -D warnings`: PASS.
- `cargo test --workspace --all-targets`: PASS; 12 focused R0 tests, 0 failures.
- `cargo check --workspace --benches`: PASS.
- Criterion replay-key smoke: PASS.
- `cargo run -p urza-cli -- r0-audit`: PASS.
- R0 catalog BLAKE3 digest: `2ef2f7dd52b72af46d24a0183096803ef9fb9d65524b9e77f7d87da4e2809f21`.
- Audit output confirms 95 distinct active names including Urza, 99 noncommander cards, 95 explicit coverage entries, own life 40, and Hand 25 fixture identity.

The first three workflow attempts found and drove fixes for formatting, a Clippy test-construction warning, and deprecated Criterion `black_box` use. No semantic test failures occurred.


## 2026-08-29 — pre-R1 foundation hardening

Classification: MODEL/architecture hardening; no card RULE implementation. Strategic-key tests are MODEL correctness contracts. RNG tests are MODEL/reproducibility contracts. Dependency locking and CI are EXPERIMENT/development infrastructure.

Purpose: close R0 loopholes before beginning R1 metadata/state work.

Changes:
- removed the direct `urza-core` dependency from `urza-policy` and added a manifest-level regression test so policy code cannot accidentally import `TrueState`/ReplayKey execution types;
- pinned the exact R0 catalog digest in code;
- upgraded strategic ValueKey canonicalization to merge duplicate library-count representations and canonicalize permission slot IDs out of strategic identity while preserving typed expiry relationships;
- added model/value namespace fields for model version and ValueKey schema version;
- retained known-top order and stack order as value-relevant distinctions with focused tests;
- added stronger RNG tests for root/domain/logical-event/occurrence separation and same-logical-event CRN sharing;
- removed unused singleton Saga-III/Remora pending fields from InformationState and added a per-object age counter for cumulative-upkeep state;
- added PRE_R1_CHECKLIST.md defining what R1 must still deliver and its acceptance gate;
- dependency lockfile capture/locked-CI conversion pending validation in this checkpoint.

Validation: pending CI.
