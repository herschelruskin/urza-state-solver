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

CI result: pending at initial commit creation; update after the executed workflow result is inspected.
