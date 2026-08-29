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

Validation:
- GitHub Actions run `33273083782`: PASS on commit `7f95a6142cef25493f7a2e9725e3b42e65c6a9f2`.
- committed `rust/Cargo.lock`; CI dependency resolution and every Cargo build/test command run with `--locked`;
- format: PASS;
- strict Clippy (`-D warnings`): PASS;
- workspace/all-target tests: PASS, 22 tests, 0 failures;
- benchmark compilation: PASS;
- R0 audit CLI: PASS with the original pinned R0 catalog digest and deck-count invariants unchanged.

Pre-R1 is complete. No Oracle metadata, card-rule handlers, sequencing kernel, policy heuristics, or Python implementation structures were introduced.


## 2026-08-29 — R1 proper started: Oracle catalog bootstrap

Classification: RULE-source metadata acquisition only; no gameplay RULE handlers. The transformation script is migration/build tooling.

R1 begins by snapshotting the current active-card Oracle metadata through Scryfall's bulk Oracle-card export, with the discovered bulk ID/update timestamp/download URI and source-file SHA-256 pinned into the resulting catalog. Stable R0 CardDefId assignments are preserved. MDFC/multiface records retain face metadata and the deck-facing matched face index. Derived feature flags are syntactic indexes over type lines/layout/mana costs, not gameplay rules.

Bootstrap attempt 1 reached the live Scryfall snapshot successfully but rejected 12 same-name ambiguities. Inspection showed the bulk Oracle dataset also carries non-paper/digital identities. The transform now filters to records whose `games` include `paper`; R1 will not pick among Oracle IDs using simulator/Python heuristics.

Bootstrap attempt 2 proved that filtering the Oracle Cards export by its representative printing's `games` field is also insufficient: six historical paper cards disappeared because their representative record was not a paper printing, and same-name ambiguities remained. The acquisition source is therefore changed to Scryfall `default_cards`: first select actual English paper printings, then group those printings by stable `oracle_id`, choosing the newest paper printing only as the snapshot carrier. The stable identity remains `oracle_id`.

Bootstrap attempt 3 reached the Default Cards export but encountered non-Oracle objects without `oracle_id` (for example tokens/emblems). These are now excluded before indexing; the active deck itself still requires one stable Oracle ID per CardDefId.

Bootstrap attempt 4 resolved the historical-card issue and reduced all remaining same-name ambiguity to Scryfall Art Series objects. A representative example is the separate `Mana Drain // Mana Drain` Art Series identity (`Card // Card`) versus the gameplay Mana Drain Oracle identity. The transform now excludes `layout == "art_series"`; this avoids format-legality heuristics and keeps only gameplay-card identities.

Bootstrap attempt 5 succeeded: all 95 active CardDefIds resolved uniquely from the 2026-08-29 Scryfall Default Cards bulk snapshot after restricting to English paper gameplay objects and excluding Art Series layouts. The pinned source bulk ID is `e2ef41e3-5778-4bc2-af3f-78eca4dd9c23`, updated `2026-08-29T09:05:30.581+00:00`, with downloaded-file SHA-256 `1f47981292cda34437b22e80de15ab435503f0b12e02df471bb405d83ac58425`.

The committed R1 catalog intentionally stores no full Oracle rules text. It stores a per-card SHA-256 of the current Oracle text, the source snapshot timestamp, stable Oracle ID, representative Scryfall ID, mana cost/value, type line, MDFC face identity/cost/type metadata, layout, and syntactic feature flags. This satisfies the R1 metadata pinning contract while keeping full rules text out of the repository.

Validation/result: R1 catalog validation is green on GitHub Actions run `33273988174`; pinned R1 catalog BLAKE3 is `4b39c7db7bfd2c6f68d7a49efa515cdffb2c6a9716022bc0b21eeec56754a983`.

## 2026-08-29 — R1 normalized state, RNG, and information boundary

Classification: MODEL architecture and deterministic infrastructure. No card gameplay RULE handlers.

Implemented:
- normalized unordered `CardZone` storage and ObjectId-sorted battlefield storage so container insertion order is not replay-semantic;
- exact `TrueLibrary` with ordered hidden cards plus explicit known-top/known-bottom bounds;
- typed `SourceRef`, stack source identity, delayed-object card identity, and typed pending-decision payloads;
- structural state validation for library knowledge bounds, duplicate object/permission IDs, missing/self/cyclic attachments, source-card mismatches, delayed object references, and permission expiry references;
- serde replay round-trip for exact state keys;
- production deterministic coordinate stream, unbiased bounded draws, and Fisher–Yates shuffle on the R0 coordinate PRF;
- exact `TrueState -> InformationState` projection;
- structural `CanonicalObjectId` equivalence classes using local permanent state, attachments, incoming attachment classes, and future-relevant external roles rather than raw ObjectId;
- canonical policy-visible permission slots with raw PermissionId removed;
- hidden middle library order projected only as card counts while known top/bottom order is preserved;
- R1 ValueKey schema `value_key_v1_r1`;
- model version `urza_model_r1_2026_08_29` and information schema `information_state_v1_r1`.

Acceptance tests include hidden-order leakage, raw ObjectId renaming, symmetric duplicate objects, attachments, exact replay JSON round-trip, information JSON round-trip, known top/bottom fidelity, RNG occurrence separation and deterministic shuffle, plus future-relevant pending/window/counter/life/mana/permission/delayed state.

Validation: final R1 acceptance CI pending.
