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

Validation:
- GitHub Actions run `33274504574`: PASS on commit `5e39de6aa97db159c42c5158d782113f66e7c2b7`.
- locked dependency graph: PASS.
- rustfmt: PASS.
- strict Clippy (`-D warnings`): PASS.
- workspace/all-target tests: PASS; 39 passed, 0 failed.
- benchmark compilation: PASS.
- R0 audit: PASS.
- R1 catalog audit: PASS.

R1 acceptance gate is closed. R2 sequencing/rules work may begin from this checkpoint.


## 2026-09-01 — R2 proper started: core sequencing/rules kernel

Classification: RULE/MODEL kernel. No POLICY implementation and no Python gameplay logic port.

Started directly from validated R1 checkpoint `ec8d320b6686cf2a4a76e208f37210fa7e3ad34d`.

Initial R2 slice implements:
- typed R2 actions for priority pass, basic Island play/mana, generic artifact casting, command-zone Urza casting, and Urza artifact mana;
- exact mana-cost parsing/payment enumeration for the currently supported simple symbols, preserving payment-choice distinctions;
- stack-based spell casting/resolution rather than cast/ETB macros;
- Urza command tax/cast count, battlefield entry, and a synthetic execution-only Construct token definition outside the pinned 95-card active-deck catalog;
- turn/phase progression through the modeled T1-T6 horizon, with normal draw observation before main phase;
- explicit draw transition, knowledge-bound updates, deterministic shuffle using the R1 occurrence-aware RNG cursor, and search-observation candidate projection sorted independently of true hidden order;
- explicit unsupported-mechanic errors rather than silently treating unimplemented cards as vanilla permanents.

Coverage is advanced only for Island, Urza, and Voltaic Key as `PRIMITIVE_ACTIVE`; this means the specific R2 primitive surface is available, not that their full intrinsic card text is implemented. Urza spin remains R3; Voltaic Key's untap ability remains later rules work.

Focused unit fixtures cover mana payment, hidden-order-safe search observation, draw knowledge updates, shuffle occurrence consumption, deterministic land/artifact/Urza sequencing, artifact mana, and horizon progression.

Validation:
- GitHub Actions run `33552829600`: PASS on commit `e6e0b6bd0e5e0953d0970568ebb19b509936e6da`.
- locked dependency graph: PASS.
- rustfmt: PASS.
- strict Clippy (`-D warnings`): PASS.
- workspace/all-target tests: PASS; 46 passed, 0 failed.
- benchmark compilation: PASS.
- R0 audit: PASS.
- R1 catalog audit: PASS.

This is an R2-start checkpoint, not the R2 acceptance gate. Remaining R2 work includes broadening the supported land/mana and simple-artifact primitive surface, then adding audited deterministic trajectory/parity fixtures before R2 is declared complete.


## 2026-09-01 — R2 acceptance gate complete

Classification: RULE/MODEL kernel plus PARITY fixtures. No POLICY implementation and no Python gameplay-logic port.

R2 was broadened from the initial three-card primitive slice to the audited acceptance surface and then closed against the specification's simple deterministic trajectory gate.

Changes:
- added explicit `CardFace` to permanent state and observation/canonicalization so MDFC back faces are future-relevant state rather than opaque modes;
- bumped model/information/ValueKey namespaces to R2 schemas and rules to `r2_core_kernel_v2`;
- generalized land play, entry choices, intrinsic mana abilities, self-damage, and mana payment while retaining typed life/mana state;
- added the three active MDFC land backs with explicit pay-3-life-or-enter-tapped behavior and blue mana, while leaving their front spells unsupported;
- added Ancient Tomb, Cephalid Coliseum, Crystal Vein, ordinary blue-producing land primitives, Seat artifact-land identity, and Sol Ring mana;
- broadened ordinary artifact cast/stack/battlefield-entry primitives only for cards without an automatic entry/replacement rule that R2 would otherwise falsify;
- retained explicit stack/priority resolution and added typed permanent-entry observations;
- added automatic opponent-cycle/untap advancement while preserving explicit priority phases;
- made search observations hidden-order invariant and duplicate-identity collapsed;
- made horizon failure and mana overflow paths non-mutating where covered;
- expanded `PRIMITIVE_ACTIVE` coverage to exactly 22 active identities with per-card statements of what remains deferred;
- added bidirectional R2 profile/coverage validation and an `r2-audit` CI gate;
- added a real-catalog deterministic acceptance trajectory covering land, mana, artifact cast/stack/resolution, turn advance/natural draw, Urza command-zone cast, Construct entry, and Urza artifact mana.

Accepted Python non-oracle tests were used only as regression witnesses for sequencing expectations (artifact remains on stack until pass/resolution; natural draw is exposed only after committed turn progression). Rust implementation structures and Python gameplay logic were not ported.

Validation:
- implementation commit: `841b2f32d9054dcaebfaf37b8893e67959f201d6`;
- GitHub Actions run `33554550014`: PASS;
- locked dependency graph: PASS;
- rustfmt: PASS;
- strict Clippy (`-D warnings`): PASS;
- workspace/all-target tests: PASS; 50 passed, 0 failed;
- benchmark compilation: PASS;
- R0 audit: PASS;
- R1 catalog audit: PASS;
- R2 core audit: PASS, reporting 22 supported active identities and horizon 6.

R2 acceptance is closed. R3 search/tutor staging may begin from this checkpoint. R3 remains responsible for simple tutors, Whir, Reshape, Transmute, Bay, Saga III, Tezzeret, Top/scry, and Urza spin permission; R4 remains responsible for broader engine-card interactions and win-catalog coverage.


## 2026-09-01 — R3 proper started: staged simple-tutor foundation

Classification: RULE/MODEL/PARITY boundary work. No POLICY heuristic implementation and no Python gameplay-logic port.

Started from validated R2 acceptance head `7d01f098fa32d2df453d828b8cba509e4f950814`.

Implemented the first R3 slice around the shared decision -> observation -> contingent-decision contract:

- Spellseeker, Merchant Scroll, and Mystical Tutor now resolve through explicit staged searches;
- policy-visible contingent target/no-find actions are generated from `InformationState` only;
- hidden library permutation cannot alter the search observation or target action set;
- zero-target legal no-find is a forced continuation rather than a blocker;
- Spellseeker enters the battlefield before its ETB search decision;
- selected targets go to the correct destination (hand or known top);
- search branches use one common pre-target shuffled ranking and delete the selected target, rather than independently reshuffling post-target libraries;
- static search-class indexes are carried by the R3 card database;
- R2's historical 22-card audit surface is preserved while current R3 coverage advances to 25 supported identities;
- CI now includes an `r3-audit` gate.

Validation:
- implementation checkpoint `9834759df176aca4809c74d959a9f5f9fc2ed0d5`;
- GitHub Actions run `33567546432`: PASS;
- locked dependencies, rustfmt, strict Clippy, benchmark compilation, R0/R1/R2 audits, and R3 staged-search audit: PASS;
- workspace/all-target tests: 56 passed, 0 failed.

This is an R3-start checkpoint, not R3 acceptance. Remaining R3 scope is Whir, Reshape, Transmute, Bay, Saga III, Tezzeret, Top/scry, and Urza spin permission.

## 2026-09-02 — R4 proper started: mana-engine and terminal-catalog foundation

Classification: RULE engine mechanics plus public terminal-catalog infrastructure. No POLICY implementation and no Python gameplay-logic port.

Started from accepted R3 head `83f314546b80e6ac23feb6463b0cdcc2e09ba63d`.

The first coherent R4 slice establishes the engine/terminal architecture with Basalt Monolith, Grim Monolith, and Forensic Gadgeteer:

- added an R4 card-database layer while freezing the historical R3 database at exactly 32 active identities;
- modeled Basalt/Grim tap-for-three mana, skipped normal untap, and stack-based native untap activations;
- added shared artifact activated-ability cost reduction with Forensic Gadgeteer's exact one-mana floor;
- applied that shared reducer to existing artifact activation-cost paths rather than adding per-card special cases;
- made untap-step handling profile-aware;
- added a public-InformationState terminal catalog API and the first accepted family, Basalt + Gadgeteer, conservatively requiring Urza context and a ready Basalt;
- promoted Basalt Monolith, Grim Monolith, and Forensic Gadgeteer to PRIMITIVE_ACTIVE, bringing current R4 coverage to 35 active identities;
- added `r4-audit` to CI while preserving the frozen R3 audit namespace.

No TrueState/InformationState/ValueKey field changed in this slice. Model/information/value schemas therefore remain the accepted R3 versions; current rules namespace is `r4_engine_start_v1`.

Validation:
- implementation commit: `d4f7a4033d8cef88c514ee094b9da8d5ca376d4d`;
- GitHub Actions run `33586517441`: PASS;
- locked dependencies, rustfmt, strict Clippy, benchmark compilation, and R0/R1/R2/R3/R4 audits: PASS;
- workspace/all-target tests: 75 passed, 0 failed;
- R4 audit reports 35 supported active identities and initial terminal family `Basalt + Gadgeteer`.

This is an R4-start checkpoint, not R4 acceptance. Power Artifact, Chip/FTT, Chrome Dome, Station/Golem, Knack/Helix recurrence, and the remainder of the audited terminal catalog stay in R4.

## 2026-09-02 — R4 broadened: Power Artifact and Top-access engine families

Classification: RULE/MODEL/PARITY engine work. No POLICY implementation and no Python gameplay-logic port.

R4 was broadened from the initial Basalt/Grim/Gadgeteer foundation through two connected engine clusters.

Power Artifact:
- added typed targeted Aura stack state with an exact artifact target locked at cast time;
- projected that target through canonical InformationState and ValueKey so strategically different targets cannot merge;
- resolved to an exact attachment or graveyard on an invalid target;
- applied the attached-only `{2}` activated-ability reduction through the shared one-mana-floor reducer;
- supported exact targeting when Power Artifact is cast from an Urza permission;
- added named terminal families Power Artifact + Grim and Power Artifact + Basalt.

Top access:
- added typed Reality Chip creature/attached modes and stack-based reconfigure/detach with an exact public creature target;
- added FTT Level 1/2/3 permanent modes and stack-based level progression;
- added continuous top visibility for Chip/FTT;
- added explicit library-top land-play and spell-cast primitives;
- enforced FTT Level 2/3 spell-this-turn permission and Level 3 non-hand generic reduction;
- added Grafdigger's Cage blocking for library spell casts while retaining land plays;
- promoted exact producer identities Grinding Station, Battered Golem, and Forensic Gadgeteer without merging their identities;
- modeled Battered Golem's skipped normal untap while keeping its artifact-ETB trigger deferred;
- added terminal families Top + Reality Chip, Top + FTT L3, Top + FTT L2 + producer, and Top + Gadgeteer + producer.

Current namespaces:
- model `urza_model_r4b_2026_09_01`;
- information `information_state_v6_r4`;
- ValueKey `value_key_v6_r4`;
- rules `r4_top_access_v3`.

Current R4 surface:
- 41 supported active identities;
- 7 of 13 audited terminal families represented;
- historical R3 database/audit remains frozen at 32 identities and the accepted R3 namespaces.

Validation:
- current implementation head: `6578b369ef7c857ef0574ae6d2552a85f90377a4`;
- GitHub Actions run `33588985108`: PASS;
- locked dependencies, rustfmt, strict Clippy, benchmark compilation, R0/R1/R2/R3/R4 audits: PASS;
- workspace/all-target tests: **90 passed, 0 failed**.

This remains an R4 broadening checkpoint, not acceptance. Station/Golem/Gadgeteer trigger execution, broader Cage behavior, Chrome Dome/Vault families, and Knack/Helix recurrence remain in R4.


## 2026-09-04 — R4 terminal-family acceptance hardening

Classification: RULE/MODEL acceptance hardening plus PARITY/real-catalog witnesses. No POLICY implementation and no Python gameplay-logic port.

This pass closes the terminal-family acceptance surface without broadening into unrelated card text:

- centralizes the audited 13-family registry in `WinFamily::ALL`, eliminating the stale seven-family CLI audit list;
- hardens Knack/Helix + Cam recognition so the temporary grant must still be on a creature permanent, including Reality Chip's attached noncreature mode;
- adds real R4-catalog positive snapshots for all 13 terminal families;
- adds one-factor near-miss rejection for every family, plus universal Urza-presence and unresolved-stack rejection;
- verifies terminal recognition is invariant to raw ObjectId renaming and, for Top families, hidden library permutation;
- verifies Grafdigger's Cage blocks every Top/library-cast terminal family;
- adds executable final-step witnesses for all 13 families using the actual rules transitions: Power Artifact attachment, Reality Chip reconfigure, FTT cast enablement, Basalt untap, Top/Gadgeteer producer execution, Chrome mana/Vault enablement, and Knack/Helix targeted-grant resolution;
- updates `r4-audit` to report all 13 families and the full current recurrence primitive set from the single registry.

Acceptance boundary: these witnesses validate the terminal-family contracts and the modeled recurrence mechanisms they depend on. Deferred card text already called out by R4 coverage (for example Mana Vault upkeep/damage, Cam sacrifice-draw, and Floodcaller combat sizing) remains outside this terminal-family gate rather than being approximated.

## 2026-09-04 — R4 final acceptance closed

Classification: RULE/MODEL acceptance audit plus real-catalog PARITY witnesses. No POLICY implementation and no Python gameplay-logic port.

The final broader R4 pass closes the milestone around the already implemented engine/recurrence surface rather than adding unrelated card breadth:

- freezes R4 as exactly 47 active identities, an exact 15-card extension over the frozen 32-identity R3 surface;
- strengthens `validate_r4_database` so R4 validation is cumulative over R1/R2/R3 and rejects identity-set substitution even when the total active count remains 47;
- requires every R4-only active identity to retain an R4-specific coverage reason;
- freezes the final rules namespace at `r4_acceptance_v6` while retaining the already-required R4c model / v7 information / v7 ValueKey schemas;
- extends the R4 audit to report the information and ValueKey namespaces, exact R4-only identity list, terminal count, policy boundary, and explicitly unmodeled remainder;
- adds final integration acceptance for exact R3->R4 registry extension, recurrence-state propagation through InformationState/ValueKey, hidden-order noninterference, and actual public contingent-choice reachability for Top, producer may-untap, and Cam target/effect decisions;
- records the full R4 acceptance boundary in `R4_ACCEPTANCE.md` and marks R5 deterministic policy/rollout work as the next milestone.

R4 acceptance deliberately does not convert the remaining 48 unsupported active identities into vanilla approximations, and does not claim full text for `PRIMITIVE_ACTIVE` cards whose coverage reason still names deferred behavior.

Validation: the closure commit is produced only after locked dependency metadata, rustfmt, strict all-target/all-feature Clippy, workspace/all-target tests, benchmark compilation, and R0-R4 audit commands all pass in the dedicated closure workflow. The ordinary Rust foundation workflow is then expected to revalidate the committed result.


## 2026-09-05 — R5 deterministic policy start

Classification: POLICY architecture. No rules/card broadening and no Python gameplay-logic port.

R5 begins from the accepted R4 closure with a deterministic one-step policy kernel in `urza-policy`. The policy crate remains isolated from `urza-core` and `urza-rules`, receives `InformationState` plus public candidate records only, enforces that pending contingent decisions cannot be bypassed, and selects independently of candidate enumeration order. Public semantic identity is compared before opaque bridge tokens so execution numbering is not strategic state.

Policy namespace: `r5_deterministic_start_v1`. R4 rules/model/information/value namespaces remain frozen. Ordinary-action candidate generation, multi-step rollout sequencing, and Monte Carlo integration remain the next R5 work rather than being silently approximated in this checkpoint.

## R5 candidate bridge

Added the isolated `urza-policy-bridge` execution layer over the frozen R4 action surface. The bridge canonicalizes exact legal actions into public collision-free policy candidates, preserves all public payment/target/X/ordered-choice distinctions, deduplicates raw-object-equivalent choices, and round-trips opaque tokens to exact execution actions. Transmute difference-payment mana continuations are explicitly retained. R4 rules/model/info/value namespaces remain frozen; deterministic multi-step rollout is next.

## R5 deterministic multi-step rollout

POLICY/ENGINE-SEQUENCING checkpoint. Added isolated `urza-rollout` over the accepted R5 candidate bridge. Each step performs terminal/automatic-window handling, rebuilds public candidates, selects deterministically, resolves to an exact Rust `Action`, applies explicit root/world/logical-event RNG context, and repeats. Added public semantic trace replay with decision-point drift rejection, same-seed randomized-search replay coverage, raw-ObjectId-renaming invariance, stack continuation, and horizon termination. R4 rules/model/information/value namespaces remain frozen and `urza-mc` is still untouched.

## R5 hidden-world Monte Carlo

Added fixed-budget outer hidden-world sampling and Monte Carlo root-state evaluation in `urza-mc`. Sampling canonicalizes the unknown library middle before `OuterHiddenWorld` shuffling so preexisting secret order cannot leak into samples, preserves known library edges, and verifies public-information equality after sampling. Each world is evaluated only through accepted deterministic rollout; terminal outcomes aggregate by T1-T6/family, horizon is the only modeled loss, and incomplete rollout stops remain errors. World IDs are explicit, unique sample identities and evaluation order is canonicalized. R4 namespaces remain frozen. Root-action comparison/value integration is next.

## 2026-09-05 — R5 common-world root-action value integration

Classification: VALUE/POLICY evaluation architecture. No R4 rules/card broadening and no Python gameplay/policy port.

Added fixed-budget root-action comparison in `urza-mc`. Every legal public root candidate is evaluated on the same canonical hidden-world `WorldId` set, remapped to each sampled world's exact execution action through `CandidateBridge`, then continued through deterministic rollout. Forced root actions use logical event 0 and continuation begins at logical event 1. Added exact `WinByHorizonScore`: total wins first, then T1-T6 exact-turn wins; exact ties use the smallest public semantic root key. Incomplete rollout stops remain errors. Namespace: `r5_root_action_value_v1`; frozen R4 and earlier R5 namespaces unchanged. Adaptive confidence/caching/performance remain deferred until after this fixed-budget reference contract.
