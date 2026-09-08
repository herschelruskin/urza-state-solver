# Post-R7 parallel modeling completeness tracker

## Purpose

This document is the operational coordinator for clearing the post-R7 modeling-completeness gate. It exists to make the remaining card-rule work parallelizable without recreating the earlier failure mode where catalog presence, primitive support, or historical milestone labels were mistaken for complete gameplay modeling.

The strategic-policy, terminal-sequencing, pruning, rollout-interpretation, and performance-tuning workstreams are frozen while this tracker is active. The only accepted work is card-model auditing, rules repair, fixture expansion, and completeness-gate infrastructure needed to reach a fully resolved 95-card model.

## Authority and source-of-truth order

1. Current Comprehensive Rules + pinned/current Oracle text + explicit audited model decisions.
2. `rust/AGENTS.md`.
3. `rust/POST_R7_MODELING_COMPLETENESS_GATE.md`.
4. `rust/data/goldfish_model_gate.v1.tsv` — authoritative per-card disposition.
5. `rust/POST_R7_MODELING_COMPLETENESS_GATE_RESULT.md` — generated aggregate status.
6. This tracker — work decomposition, dependencies, lane ownership, and integration history.
7. Focused fixtures and CI runs.

This tracker never overrides the TSV registry or executable rules evidence. A lane may call a card "candidate complete", but only an integration gate may promote its authoritative disposition.

## Current baseline

As of 2026-09-08:

- Repository: `herschelruskin/urza-state-solver`
- Integration branch: `rust-engine-rebuild`
- Current working branch head: `44f885152d7d61d2986f9a51fd2e434f2cae1a85`
- Last accepted completeness promotion head: `3716b84d719fe651a6fee442e45275b5e4b52483` (`[R7] Audit Battered Golem completeness`)
- Active catalog identities: 95
- Accepted resolved dispositions: 11
- Accepted unresolved dispositions: 84
- Accepted `AUDIT_REQUIRED`: 41
- Accepted `IMPLEMENTATION_REQUIRED`: 40
- Accepted `ENVIRONMENT_SPLIT_REQUIRED`: 3
- Accepted `COMPLETE`: 11
- Accepted `GOLDFISH_IRRELEVANT`: 0
- Accepted `ENVIRONMENT_DEFERRED`: 0

Important: the working branch contains staging/harness commits after the last accepted completeness promotion. Do not infer card acceptance from branch head alone. The generated gate result + successful integration CI are authoritative.

### Currently staged but not accepted repair

The `rules-active repair v1` slice is intended to repair shared interactions and potentially promote Artificer's Assistant, Chrome Dome, and Valley Floodcaller. Banishing Knack and Retraction Helix are being repaired but must remain unresolved until their targeted-cast surfaces work from all modeled permission zones.

Latest attempted run at tracker creation:

- Workflow: `Post-R7 rules-active completeness repair v1`
- Run: `34258780207`
- Result: RED before semantic tests because the separate fixture compile-fix staging step failed.
- Therefore: no promotion from this repair slice is accepted yet.

## Non-negotiable completion rule

No strategic-policy, terminal-sequencing, pruning, rollout-conclusion, or performance result may be accepted until every active identity is resolved as exactly one of:

- `COMPLETE`
- `GOLDFISH_IRRELEVANT`
- `ENVIRONMENT_DEFERRED`

`AUDIT_REQUIRED`, `IMPLEMENTATION_REQUIRED`, and `ENVIRONMENT_SPLIT_REQUIRED` are blocking.

The unit of completeness is the relevant Oracle clause, not the card name.

## Parallel execution architecture

The remaining work should no longer proceed as one-card/one-workflow serial promotion. Use dependency-aware waves and independent card-family shards.

### Wave 0 — shared rules primitives

This lane has priority over leaf-card implementation because multiple cards depend on the same rules machinery. Repair shared primitives once, then let dependent shards consume them.

Current known shared defects / requirements include:

- generic permanent-leaves-battlefield attachment cleanup for bounce/sacrifice;
- temporary power/toughness modifiers and end-of-turn expiration;
- haste state where relevant to copied creatures / granted tap abilities;
- flash / timing permissions for noncreature spells and relevant permanent spells;
- targeted spell casting from hand, library-top permissions, and Urza exile permissions through one legality path;
- artifact activation cost reduction applied consistently to all artifact activated abilities, including Clue;
- cost-reduction floors where Comprehensive Rules require a nonzero generic activation cost to remain at least one;
- copy effects preserving/copied characteristics while applying explicit token modifications;
- centralized leave/sacrifice/bounce zone movement so attachments, delayed events, tokens, and LTB triggers remain consistent.

A shared primitive is accepted only when full-workspace compilation, direct rules fixtures, cross-card interaction fixtures, and frozen R4 regressions are green.

### Shard A — mana and resource conversion

Scope examples:

- Chrome Mox
- City of Traitors
- Crystal Vein sacrifice mode
- Everflowing Chalice
- Gemstone Caverns
- Jeweled Amulet
- Lotus Petal — already COMPLETE
- Mox Diamond
- Mox Opal — already COMPLETE
- Moonsnare Prototype
- Sapphire Medallion
- Saprazzan Skerry
- Ancient Tomb / Island / Seat of the Synod / Sol Ring — already COMPLETE baseline primitives
- Mana Vault and other mana rocks whose nontrivial upkeep/untap clauses still require audit

Required evidence includes play/cast legality, entry state, mana production, alternate/additional costs, counters, sacrifice, life changes, pregame state, timing restrictions, and solver-visible actions.

### Shard B — tutors, search, draw, filter, recursion, and library information

Scope examples:

- Dizzy Spell
- Muddle the Mixture
- Gitaxian Probe
- Scour for Scrap
- Witching Well
- Aether Spellbomb
- Codex Shredder
- Mishra's Bauble
- Urza's Bauble
- Merchant Scroll
- Mystical Tutor
- Spellseeker
- Whir of Invention
- Reshape
- Transmute Artifact
- Repurposing Bay
- Sensei's Divining Top
- Fortune Teller's Talent
- Reality Chip
- Cephalid Coliseum threshold mode

Required evidence includes search classes, destination, shuffle behavior, costs, draw timing, delayed draws, top-library knowledge, scry/surveil/order semantics, recursion, and public-information boundaries.

### Shard C — artifact/permanent activated and triggered abilities

Scope examples:

- Sewer-veillance Cam, including `{3}{U}, sacrifice: draw two`
- Manifold Key
- Voltaic Key
- Grinding Station
- Battered Golem — already COMPLETE
- Forensic Gadgeteer — COMPLETE but must stay under cross-card regression after Clue-cost repair
- Power Artifact — already COMPLETE
- Chrome Dome
- Prized Statue
- Tormod's Crypt
- Welding Jar
- Pithing Needle
- Grafdigger's Cage
- Uthros Research Craft
- The One Ring
- Tezzeret, Cruel Captain

Required evidence includes activation costs, tap/sacrifice costs, reducers, triggers, target legality, LKI where required, token behavior, counters, delayed events, and bridge visibility.

### Shard D — casting permissions, targeting, alternate/free costs, and modal spell faces

Scope examples:

- Banishing Knack
- Retraction Helix
- Hydroelectric Specimen front face
- Sea Gate Restoration front face
- Sink into Stupor front face
- Otawara channel mode
- Force of Will
- Force of Negation
- Fierce Guardianship
- Pact of Negation
- interaction spells whose alternate/free costs or own-spell/self-target lines can affect cast triggers, graveyard state, or combo assembly

Required evidence includes timing, targets, alternate costs, exile/discard/additional costs, own-spell/self-target utility, library-top casting, Urza permission casting, and exact zone movement.

### Shard E — lands, pregame, counters, and special utility modes

Scope examples:

- City of Traitors land-sacrifice trigger
- Gemstone Caverns pregame luck-counter/exile behavior
- Ipnu Rivulet
- Minamo
- Oboro
- Otawara
- Crystal Vein
- Cephalid Coliseum
- Urza's Saga
- modal DFC land faces

Required evidence includes land-play limits, entry choices, counters, sacrifice/channel/bounce modes, tap abilities, chapter timing, and interaction with library-top/Urza permissions.

### Shard F — environment and interaction classification

Scope examples:

- Faerie Mastermind
- Mystic Remora
- Rhystic Study
- Defense Grid
- Disruptor Flute
- Pithing Needle
- Spellskite
- counterspells and protection pieces

This shard must separate intrinsic/base behavior from opponent-driven behavior. Do not fake opponent action rates. An `ENVIRONMENT_DEFERRED` promotion is legal only after all intrinsic card behavior relevant to the goldfish engine is complete and the remaining unresolved text genuinely belongs to an explicit environment model.

Cards normally called "interaction" may be `GOLDFISH_IRRELEVANT` only after own-spell/self-target, alternate-cost, cast-trigger, graveyard, resource-conversion, and terminal interactions are explicitly ruled out.

## Branch and integration protocol

To make work genuinely parallel, use an integration branch plus short-lived shard branches rather than multiple bots mutating `rust-engine-rebuild` concurrently.

Recommended branch pattern from the current integration baseline:

- `rust-modeling/shared-primitives`
- `rust-modeling/mana`
- `rust-modeling/tutors-cardflow`
- `rust-modeling/artifact-abilities`
- `rust-modeling/casting-targeting`
- `rust-modeling/lands-pregame`
- `rust-modeling/environment`

Rules:

1. Every shard records its exact base SHA.
2. A shard should minimize edits to central match statements; prefer shared helper APIs, dedicated modules, tables, and focused test files when architecture allows.
3. A shard may add mechanics and fixtures, but should not independently change the authoritative completeness counts on the integration branch.
4. Shared-primitives changes integrate before dependent shard promotions.
5. When a shard is ready, record candidate cards, touched files, focused test commands, CI run, and any cross-shard dependencies.
6. Integrate compatible shard commits into `rust-engine-rebuild` in a controlled wave.
7. Only the integration wave updates `goldfish_model_gate.v1.tsv`, generated count assertions, and `POST_R7_MODELING_COMPLETENESS_GATE_RESULT.md`.
8. Run the complete integration gate after every wave.
9. If integration exposes a cross-card defect in a previously COMPLETE card, repair it immediately; if necessary, temporarily demote that card rather than preserving a false COMPLETE status.

## CI structure

Prefer reusable validation workflows over one-shot patch-application workflows.

Each shard gate should run, at minimum:

1. `cargo fmt --all -- --check`
2. full or dependency-appropriate workspace/all-target compile
3. shard clause-level fixtures
4. shard bridge/action-visibility fixtures where applicable
5. relevant prior COMPLETE-card cross-interaction regressions
6. frozen R4 card regression
7. frozen R4 terminal regression when combo/terminal mechanics are touched
8. strict Clippy with `-D warnings`

The integration gate additionally runs:

- all shard fixtures;
- all previously accepted completeness fixtures;
- modeling gate unit test;
- authoritative registry/inventory generation;
- exact resolved/unresolved count assertion;
- no unresolved duplicate/missing registry identities;
- full frozen acceptance regressions.

Avoid CI designs where generated patch scripts mutate production source and then bot-commit it as the primary implementation mechanism. Those scripts have repeatedly created staging/format/borrow-checker noise. Prefer committing the actual Rust/test changes to a shard branch and using CI as validation.

## Per-card audit record schema

Each card promoted or exempted should have an auditable record containing:

- Card name / CardDefId
- Starting disposition
- Final disposition
- Oracle clauses reviewed
- Goldfish-relevant clauses
- Explicitly irrelevant/environment-owned clauses
- Shared primitive dependencies
- Runtime profile changes
- Rules/action/bridge changes
- Fixture files
- Cross-card fixtures
- Focused CI run
- Integration CI run
- Accepted commit SHA
- Remaining known limitations: none for `COMPLETE`; environment-only for `ENVIRONMENT_DEFERRED`

Do not promote a card based only on a profile field, catalog flag, historical coverage status, or successful cast smoke test.

## Wave board

| Wave / lane | State | Accepted impact | Blocking / next work |
| --- | --- | ---: | --- |
| Baseline simple mana | ACCEPTED | 4 COMPLETE | Island, Ancient Tomb, Sol Ring, Seat of the Synod |
| Fast mana v1 | ACCEPTED | +2 COMPLETE | Lotus Petal, Mox Opal |
| Monolith audit | ACCEPTED | +2 COMPLETE | Basalt Monolith, Grim Monolith |
| Power Artifact audit | ACCEPTED | +1 COMPLETE | Power Artifact |
| Forensic Gadgeteer audit | ACCEPTED WITH CROSS-REGRESSION REQUIRED | +1 COMPLETE | Clue activation reducer defect must be repaired without losing COMPLETE |
| Battered Golem audit | ACCEPTED | +1 COMPLETE | Accepted head `3716b84d719fe651a6fee442e45275b5e4b52483` |
| Shared/rules-active repair v1 | RED / NOT ACCEPTED | +0 | Repair harness staging; then test Assistant, Chrome Dome, Floodcaller; repair Knack/Helix and Gadgeteer interactions |
| Shared primitives wave | NEXT HIGHEST PRIORITY | +0 until integrated | attachment cleanup, temporary P/T, haste, flash, targeted permission casting, reducer consistency |
| Mana/resource shard | PLANNED | — | batch high-impact missing acceleration/resource cards |
| Tutor/card-flow shard | PLANNED | — | batch search/draw/filter/recursion cards |
| Artifact ability shard | PLANNED | — | Cam/Keys/utility artifacts and cross-card reductions |
| Casting/targeting shard | PLANNED | — | Knack/Helix zone-complete casting, MDFC fronts, alternate/free-cost spells |
| Land/pregame shard | PLANNED | — | special lands, channel/bounce/sacrifice/pregame rules |
| Environment shard | PLANNED | — | split intrinsic vs opponent-owned text; explicit exemptions only |

Accepted total at tracker creation: **11 / 95 resolved**.

## Integration-wave checklist

Before accepting any wave:

- [ ] Shared dependencies are integrated first.
- [ ] Every candidate card has a clause-level audit record.
- [ ] Every `COMPLETE` candidate has focused execution fixtures.
- [ ] Solver/bridge visibility is tested for every selectable action/decision.
- [ ] Cross-card reducers/triggers/attachments/copies are exercised where applicable.
- [ ] Previously COMPLETE cards touched by shared changes are re-tested.
- [ ] Workspace all-target compile is green.
- [ ] `cargo fmt` is green.
- [ ] Strict Clippy is green.
- [ ] Frozen R4 card regression is green.
- [ ] Frozen R4 terminal regression is green when applicable.
- [ ] TSV dispositions and gate count assertions are changed only at integration.
- [ ] Generated completeness result matches the committed registry exactly.
- [ ] Accepted SHA and CI run are recorded in this tracker.

## Completion condition

This tracker closes only when the generated modeling gate is GREEN at 95/95 resolved identities and the final integration run is green.

Only after that point should the project rerun the frozen 128 strategic worlds and return to terminal-precursor / sacrifice-resource timing diagnosis.

## Fresh-chat handoff

A new project chat should begin by reading, in this order:

1. `rust/AGENTS.md`
2. `rust/POST_R7_MODELING_COMPLETENESS_GATE.md`
3. `rust/POST_R7_PARALLEL_MODELING_COMPLETENESS_TRACKER.md`
4. `rust/POST_R7_MODELING_COMPLETENESS_GATE_RESULT.md`
5. `rust/data/goldfish_model_gate.v1.tsv`

Then verify the current branch head and latest relevant CI before making writes. Do not assume the numeric baseline in this tracker is still current if later integration commits exist; update this tracker after every accepted integration wave.
