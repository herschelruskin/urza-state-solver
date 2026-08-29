# Urza Simulator — Rust Engine Rebuild Specification

**Status:** audited v2 clean-room rebuild specification
**Audit date:** 2026-08-28
**Rust branch:** `rust-engine-rebuild`
**Authoritative accepted Python validation run:** `33202063879` at workflow head `206282ba72413e61f18c6d5119d880126506bd8f`
**Accepted rules repair included in that baseline:** zero-target simple-tutor no-find `c7dd2b8b14fcacfd8ef03fdf511f8cbb2dfd7e72`
**Performance experiment only:** `phase5i-mulligan-runtime-v2` at `c35b963acef211efa674a8e7af3aab18b9da7268`

## Source-of-truth hierarchy

The Rust engine is **not** a byte-for-byte port of Python. If sources disagree:

1. Current Magic Comprehensive Rules + current Oracle card text + explicit project abstraction decisions.
2. Audited rules/information fixtures encoding those decisions.
3. Final accepted non-oracle Python behavior as a regression witness and fixture generator.
4. Historical Oracle code, rejected branches, old comments, and performance experiments as evidence only.

Every important behavior should be classified as **RULE**, **MODEL**, **POLICY**, **PARITY**, or **EXPERIMENT**. Never force Rust to match Python solely because Python did it first.

## Purpose

Rebuild the accepted non-oracle Urza solver architecture in Rust so performance no longer forces policy simplification. Preserve validated information/policy/model contracts from Python, but correct audited rules mistakes instead of preserving them for superficial parity. Retain legal-information boundaries, reproducible hidden worlds, canonical strategic state, replayability, selective bounded Q, London mulligan DP, deck-specific rules coverage, and regression testing.

The Rust engine should become faster by making representation, caching, factoring, branch bounds, and parallel execution better — not by teaching the player that weird but legal lines do not exist.

## Why Rust now

The Python engine has largely solved the earlier memory explosion. Symbolic Whir/Reshape staging and packed state reduced pathological requests from thousands of simultaneously materialized actions and multi-GB RSS to low-hundreds fanout and roughly 55–57 MB in representative probes.

CPU/search churn remains pathological.

Human benchmark Hand 25:
- seven: Hydroelectric Specimen; Minamo, School at Water's Edge; Whir of Invention; Sapphire Medallion; Uthros Research Craft; Voltaic Key; Island
- mulligan stage 2 / keep 6
- only 7 legal bottoms
- frozen Phase 5I runtime about 2 h 15 min
- Hydroelectric bottom / world 2: about 1,667 s, 762,012 decision requests, max immediate fanout 168
- Island / world 2: about 933 s, 143,502 requests, max fanout 948
- Island / world 0: about 741 s, roughly 253k requests
- Voltaic Key / world 1: about 501 s, roughly 200k requests

Therefore the main remaining problem is repeated small-state work: action generation, state cloning, strategic-key construction, cache probing, transitions, and Q evaluation across long engine-rich trajectories.

## Final product goals

1. Mulligan archetypes
   - classify hands into strategic families
   - estimate keep/mull by London stage
   - recommend bottoms
   - allow equivalent/near-equivalent recommendations instead of false certainty from tiny MC differences

2. Tutor policy
   - estimate best visible-state tutor target
   - distinguish win, value-engine, mana-engine, setup and protection goals

3. Probabilistic win timing
   - exact T1–T6 distribution
   - no win by end of T6 is primary-objective loss
   - prefer earlier wins after total win probability

4. Interaction/protection
   - report how often protection is available
   - do not hard-require protection when a faster unprotected line is rational

5. Card-swap analysis
   - compare deck variants on identical seeds/worlds where possible
   - measure keep rate, win timing, protection and tutor behavior

6. Explainability
   - replayable trajectories
   - named win families and policy reasons
   - no ANN required initially

## Scope

This is a deck-specific engine, not a full Magic Comprehensive Rules implementation.

Initially out of scope:
- full four-agent opponent simulation
- every obscure Commander interaction
- exhaustive opponent targeting
- opponent life/damage strategy unless a later interaction model needs it; **our own life total starts at 40 and is intrinsic state from R1** because it constrains life payments/self-damage
- neural value/policy approximation before exact/factored methods are exhausted

Add a new card mechanic only when it causes a reproducible blocker, illegal state, hidden-information leak, material benchmark distortion, or a required final capability.

## Non-negotiable correctness contracts

### True state and observation are separate

TrueState contains the sampled hidden world, including actual hidden library order.

InformationState / PolicyView contains only legally available information.

Policy code must never read unknown TrueState library order.

The player may deduce exact remaining library membership/counts without knowing unknown order.

### Rules and policy are separate

Rules answer:
- legal actions
- costs
- observations
- transitions

Policy chooses among legal actions using only PolicyView.

Never select an action by inspecting hidden successors.

### Decision → observation → contingent decision

Any effect that reveals hidden information before a later choice must be staged. Never flatten tutor, scry, Top or similar effects into one oracle action.

### Deterministic randomness

Randomness must not depend on:
- time
- thread scheduling
- trace length
- memory address/object identity
- unordered-container iteration

Every event derives from root seed/world ID + versioned namespace + stable semantic coordinate + an explicit stochastic-event occurrence/cursor. A repeated physical shuffle/random event after revisiting the same state/action must be able to consume a fresh random result. Counterfactual branches representing the **same logical random event** deliberately share the occurrence coordinate for common-random-number coupling. Occurrence IDs must never depend on thread scheduling.

Keep game randomness, outer hidden-world sampling, environment randomness, and optional policy/tie randomness in independent namespaces so consuming one domain cannot perturb another.

### Distinct identities

Maintain:
- replay/debug true-state identity
- exact sampled-world transition/cycle identity
- seed/order-independent strategic ValueKey

Trace/profiling provenance must not enter ValueKey.

### Exact win-turn objective

Record won, win turn, win family, terminal reason and terminal turn.

Comparison:
1. maximize P(win by horizon)
2. then lexicographically maximize cumulative earlier-win probability

Prefer integer rollout counts/rational comparisons internally; convert to float for reports.

### Exact card identity

Do not merge cards just because strategic roles look similar. Identity can alter future draws, search availability, mana value, sacrifice value, recursion and information.

Prefer structural factoring over semantic merging.

## Recommended Rust workspace

rust/
  Cargo.toml
  crates/
    urza-core
    urza-rules
    urza-info
    urza-rng
    urza-policy
    urza-value
    urza-mc
    urza-mulligan
    urza-cards
    urza-cli
    urza-python-parity

Keep Python initially as the executable reference and fixture generator.

## Compact native representation

### Card IDs

Use a definition ID such as `CardDefId(u16)`; strings stay at parsing/logging boundaries. `u16` avoids a future format migration when card-swap experiments expand the catalog beyond this deck. Use a separate execution-only `ObjectId` for physical battlefield/stack objects.

Version the registry and save a digest in benchmark artifacts.

### Library

A 99-card true library can be represented as a fixed array of `CardDefId` values plus length/index metadata (about 198 bytes at u16). Copying a few hundred bytes may be faster than complex arenas/COW; benchmark before adding indirection.

Strategic library belief stores:
- remaining multiset/counts
- known top
- known bottom
- deduced counts
- no unknown order

Mana should use compact typed pools (at minimum blue/colorless plus special stored typed mana). **Generic is a cost requirement, not a mana type.**

### Permanents

Do **not** port the Python State layout 1:1. Prefer authoritative per-object state:

- `CardDefId`, tapped/sick/type/mode flags;
- Ring burden counters on the exact Ring;
- Uthros charge counters on the exact Uthros;
- Saga lore counters on each Saga;
- Power Artifact / Reality Chip attachments to exact objects;
- Knack/Helix grants on exact creatures;
- Chrome Dome copy objects and lifetime obligations.

Execution `ObjectId` values distinguish physical objects for transitions. Strategic equality should canonicalize same-name objects deterministically while preserving attachment/relationship distinctions that affect future legality.

Do not recover gameplay state from trace text. Use typed delayed events such as pending Bauble draws, Chrome-copy sacrifice, Mana Drain credit, and permission expiry. Trace is reporting only.

### Actions

Use a compact enum, not strings/dictionaries. Stage contingent choices rather than materializing huge combined actions.

### Pending/window/stack

Strategic state includes:
- main-empty vs priority vs post-observation choice
- pending tutor/scry/Top/Transmute/Whir/Reshape/Bay/trigger/Coliseum decisions
- ordered unresolved stack/triggers
- live Urza permissions and multiplicity

## RNG and common random numbers

Use a stable PRF/seed derivation such as BLAKE3 plus a versioned reproducible RNG.

Maintain three identities separately:
1. strategic expected-value state, excluding RNG provenance;
2. exact sampled-world/replay state, including stochastic-event progression;
3. common-random-number coordinates intentionally shared by counterfactual candidates.

The accepted Python state-fingerprint RNG scheme is a compatibility witness, not mandatory production semantics. If exact old replay is useful, implement a versioned compatibility mode. Production Rust should use occurrence-indexed random events so a genuinely repeated random event is fresh.

Critical tutor-search rule learned in Python:

1. derive one random permutation/ranking from the common **pre-target** library/search event and its occurrence ID;
2. each candidate-target branch deletes its exact selected target from that same permutation;
3. remaining order is the branch library.

Do not independently reshuffle target branches. The corrected common-random-number construction materially improves finite-sample comparisons.

## Observation-boundary catalog

### Sensei's Divining Top
Activate/reveal top 3 → observe → choose order.

Top draw is one committed activation whose resolution is: draw a card, then if Top is still on the battlefield put Top on top of its owner's library. The drawn card becomes known during resolution, but no unrelated policy action occurs between those instructions.

### Scry
Commit/resolve source → observe N → choose top/bottom arrangement.

Artificer's Assistant must trigger on a **historic spell**, not artifact spells only. Historic includes artifacts, legendary spells, and Sagas; lands are played rather than cast.

### Simple tutors
Commit/pay → observe legal search set → choose target or legal no-find → placement/shuffle.

Zero legal targets must resolve mechanically when no-find is legal. Python previously blocked on empty Spellseeker; Rust must not.

### Transmute Artifact
Cast/pay UU → choose sacrifice on resolution → observe search → choose target → pay MV difference or decline as legal → shuffle/battlefield transition.

### Reshape
Choose X + sacrifice as casting commitment → search observation → choose MV<=X target → shuffle.

### Whir of Invention
Choose X + improvise/payment while casting → search observation → choose MV<=X target → shuffle.

### Repurposing Bay
Pay {2}, tap Bay, sacrifice another artifact → exact MV+1 search observation → choose target → battlefield → shuffle/ETB. Activate only as a sorcery.

### Tezzeret, Cruel Captain
- 0: untap target artifact or creature; if it is an artifact creature, put a +1/+1 counter on it.
- -3: commit loyalty → observe artifact MV<=1 search → choose/reveal target → **put it into hand** → shuffle.
- -7/combat-emblem support is explicit deferred scope until needed; never invent a shortcut.

### Urza's Saga III
Independent pending trigger. Can resolve after Saga leaves. Chapter III searches an artifact card with **printed mana cost exactly {0} or {1}** (not merely mana value <=1), puts it onto the battlefield, then shuffles. Search decision happens at trigger resolution; final-chapter sacrifice timing must be correct.

### Scour for Scrap
{3}{U} instant; choose one or both. Its library mode searches an artifact card, reveals it, puts it **into hand**, then shuffles. Its graveyard mode returns target artifact card from graveyard to hand. A graveyard target is locked when the spell is cast and cannot be created later and retroactively targeted.

### Cephalid Coliseum
Activate threshold ability → draw 3 observations → choose discard 3.

### Urza spin
Pay 5 → shuffle → exile/observe top → create persistent until-EOT play permission → return to ordinary sequencing.

Multiple permissions can coexist. Free cast obeys timing; MDFC faces remain legal; X=0 when cast without paying mana cost.

### Draw/mill
Commit action before revealing unknown result. Update InformationState before next decision.

### Fetchlands
Commit crack before shuffled future is known. Current target may be deterministic Island but shuffle invalidates stale top/bottom knowledge.

## Continuous visibility and Cage

Reality Chip and Fortune Teller's Talent expose top information according to their modeled look permissions; top knowledge refreshes after every top-changing event.

FTT look and play permissions are distinct. Current terminal model includes FTT L3 + Top and FTT L2 + Top + producer.

Grafdigger's Cage:
- blocks creature cards entering from libraries
- blocks applicable spells cast from libraries through Chip/FTT
- does not stop lands from library
- does not stop Urza spin because the card is exiled first

Policy decisions to remove Cage are not rules legality.

## Trigger ordering

Controlled simultaneous cast triggers may include:
- Valley Floodcaller
- Artificer's Assistant when a **historic spell** is cast
- Uthros
- Forensic Gadgeteer
- Vexing Bauble

Chip/FTT are continuous, not triggers.

After cast:
1. refresh legally visible top
2. collect simultaneous controlled triggers
3. choose legal order using current observation
4. persist ordered stack
5. resolve one at a time
6. return priority between resolutions
7. newly created triggers go above older unresolved objects

## Important card/rules lessons

### Urza
Track command-zone tax/status, Construct ETB, artifact mana and persistent spin permissions. Many artifacts become mana only after Urza resolves, which heavily affects policy.

### Gemstone Caverns
Seat is fixed across mulligan candidates.
- seat 1 dead: 25%
- seats 2–4 live: 75%, currently mechanically equivalent
Optimize inside known seat, then mix.

### Lands/mana
Preserve:
- Ancient Tomb
- City of Traitors self-sac trigger timing
- Crystal Vein sacrifice
- Saprazzan Skerry depletion
- Oboro bounce/replay
- Minamo untaps
- Coliseum threshold
- Ipnu Desert mill
- Seat of the Synod artifact+land identity
- MDFC face legality

### Chrome Mox / Mox Diamond / Amulet
Imprint/discard are public choices. Policy must not use hidden future draws to decide. Jeweled Amulet stores typed mana.

### Monolith / Power Artifact / Gadgeteer
Native untaps and reductions matter.
Known terminal families include PA+Grim, PA+Basalt, Basalt+Gadgeteer with required Urza context.
Pre-Urza infinite colorless is not a win without UU to cast Urza.

### Top / Keys / Ring
Top is staged; Key/Minamo/Ring untap choices can create repeated decision churn. Keep rules general and solve performance structurally.

### Mystic Remora / Rhystic / Faerie
Current environment assumptions:
- Remora +2 opponent-fed cards/cycle, separate from cumulative upkeep
- Rhystic +2/cycle
- Faerie +1/cycle

These are environment assumptions, not intrinsic rules.

Remora cumulative upkeep is a real pending upkeep decision with responses before resolution, increasing age/pay-or-sacrifice on resolution, and reset on recast.

### Uthros
Counters/draw trigger matter. May activate with different eligible untapped creatures; recalculate power each time.

### Gadgeteer / Floodcaller / Assistant
Separate triggers/copies. Floodcaller timing permission affects hand/top/Urza-permission casts during legal priority windows.

### Knack / Helix
Grant belongs to exact creature. Tapped/sick state matters. Known terminal families include Floodcaller, Battered Golem and Sewer-veillance Cam recurrence.

### Chain of Vapor
Rules must support recursive legal copies and stopping after each bounce.

Python's final goldfish policy used visible-payoff factoring to avoid land×target explosion. That was a policy optimization, not Magic legality. Rust should first seek factored/compact representations rather than hard restrictions.

### Otawara / Aether Spellbomb / Well / Cam / Baubles / Vexing / Shredder / Jar
Preserve exact printed-style costs/tap/sacrifice semantics already captured by Python fixtures, especially which artifacts can be tapped to Urza first and still use a non-tap sacrifice ability later.

### Native rules corrections from the audit

These are RULE-level corrections/clarifications and must not be replaced with Python convenience behavior:

- **Voltaic Key:** {1},{T}: untap target artifact; it may target itself.
- **Manifold Key:** {1},{T}: untap **another** target artifact; it cannot target itself. Its {3},{T} unblockable mode can be explicitly combat-deferred.
- **Moonsnare Prototype:** {T} plus tapping another untapped artifact/creature we control adds {C}; Channel {4}{U}, discard: owner of target nonland permanent puts it on top or bottom. Our own nonland permanent may be a strategic target.
- **Otawara:** Channel {3}{U}, reduced by {1} per legendary creature we control; returns target artifact, creature, enchantment, or planeswalker. Being a land does not automatically disqualify an otherwise valid artifact/enchantment permanent.
- **Giant's Boulder:** ETB scry 2; {1},{T} any-color mana; {7},{T},sacrifice destroys target permanent. Our own permanents are legal targets, so only opponent-facing valuation is environment-deferred.
- **The One Ring:** exact Ring object carries burden counters; upkeep life loss and tap/draw ability are intrinsic, and own life is modeled.
- **Mana Vault:** does not untap normally; upkeep pay-4 untap option and tapped draw-step damage are real state/actions.
- **Aether Spellbomb:** its draw mode is {1}, sacrifice: draw; no tap is required.
- **Sewer-veillance Cam:** ETB/LTB trigger may tap **or untap** target creature; draw mode is {3}{U}, sacrifice: draw two.
- **Uthros Research Craft:** exact object carries charge counters; its 3+ artifact-cast trigger draws and adds a charge counter and resolves before the triggering artifact spell.
- **Forensic Gadgeteer / Power Artifact:** activated-ability reductions have their actual one-mana floor; do not implement unrestricted subtraction.

### Grinding Station
Strategically live mill/sacrifice lines can create huge repeated request counts. Use compact artifact sets and incremental information updates before restricting behavior.

### Bay / Saga / Tezzeret
Search staging and exact target MV constraints matter. Bay fixture includes Sapphire Medallion MV2 → Battered Golem MV3.

### Offer
An Offer You Can't Refuse can counter our own legal noncreature spell to create two Treasures. Spell must actually be on stack and priority must be real.

### Prized Statue / Chalice / Treasure
Prized Statue second Treasure only on battlefield→graveyard.
Everflowing Chalice has multikicker/counters/native mana; direct-to-battlefield Chalice has zero counters unless specified.
Treasure cannot be double-used without untap.

### Chrome Dome
Preserve actual copy behavior/timing. Known terminal families include Dome+Station, Dome+Golem, and PA+Dome+Gadgeteer+Mana Vault.

## Human strategic policy learnings

These are policy priors, not rules.

- Cast Urza early by default; exceptions include powerful visible early value engines.
- Tutor promptly when lacking an engine or immediate win.
- Tutor categories: direct win, value engine, mana/producer engine, setup/protection.
- Deploy fast mana/artifacts early unless a visible cast/ETB payoff makes timing important.
- Value engines can be preferable to blindly forcing a fragile line.
- Fast unprotected wins can be correct; protection should be modeled probabilistically, not as a hard gate.
- Chain copies should usually require visible downstream payoff.
- Preserve visibly assembled synergy such as Top+Chip/FTT, PA+Monolith, Knack/producer and live Uthros.
- Never preserve/sacrifice based on a hidden future draw.

## Win catalog parity targets

Known terminal families:
- Power Artifact + Grim Monolith
- Power Artifact + Basalt Monolith
- Top + attached Reality Chip + producer
- Top + FTT L3
- Top + FTT L2 + producer
- Basalt + Gadgeteer
- Top + Gadgeteer + producer
- Chrome Dome + Grinding Station
- Chrome Dome + Battered Golem
- Chrome Dome + PA + Gadgeteer + Mana Vault
- Knack/Helix + Valley Floodcaller
- Knack/Helix + Battered Golem
- Knack/Helix + Cam

Spellseeker presence is not automatically terminal; conversion must be executed or proven.

## Production policy reference

Architecture:
- deterministic rollout-v6 for ordinary sequencing
- selective Q for strategically important search/tutor choices
- common-random-number MC
- screen → shortlist → confirm
- bounded contingent lookahead
- confidence/sign gate
- rollout-v6 wins ties

Frozen configuration:
- Q screen 1
- Q confirm 2
- shortlist 3
- contingent true
- confidence gate true
- validation 2→4→8
- max validation 8
- one-sided paired sign alpha .25

Final corrected Phase 5H gate:
- v6 5/40
- one-step Q 11/40
- contingent Q 13/40
- one-step worse than v6: 0
- contingent worse than v6: 0

Older comments may show 12/40 and 14/40 from pre-RNG-coupling history. The final Python 5/11/13 result is a **finite-sample parity witness under the accepted Python RNG tape**, not a Magic invariant. Exact count parity is required only in an explicit Python-compatible tape mode; production occurrence-indexed Rust RNG gets its own paired quality gate on identical Rust worlds.

## Cache lesson

Python production bounded Q cache at 512 mainly for memory.

Rust should benchmark larger caches:
- 512
- 4k
- 32k
- 256k/unbounded coordinate

Record hit/miss/eviction, bytes per entry and wall time. A native compact cache may remove major recomputation that Python tolerated to stay memory-safe.

A cached Monte Carlo estimate must be namespaced by more than ValueKey: include rules/model/card-catalog version, policy/Q configuration, objective/horizon, environment version, RNG/sample namespace or tape, rollout budget, and continuation identity as applicable. Never reuse an estimate from a different tape/budget as if it were the same estimate.

## London mulligan model

Stages:
0 first 7
1 free second 7
2 keep 6
3 keep 5
4 keep 4
5 keep 3
6 keep 2 forced floor

For visible seven h:
V6 = E[K6(h)]
Vs = E[max(Ks(h), V(s+1))]

Human benchmark:
- 35 exact usable hands
- labels held out from scoring
- rating is relative to keep size
- seat missing in source, so Caverns is seat-conditioned

Runtime lesson: a one-world screen can create cutoff ties and accidentally confirm all bottoms. Runtime-v2 explores:
- parallel bottom evaluation
- extra paired worlds only for cutoff ties
- exact early confirmation stop when all unseen worlds as T1 wins still cannot catch incumbent

These are mulligan-layer changes only.

The outer parallel/tie-racing/early-stop work on `phase5i-mulligan-runtime-v2` is an **EXPERIMENT**, not inherited game semantics. Exact early stopping is safe only after all internal choice dimensions for that candidate (for example a Caverns pregame plan) are fixed; equality remains live.

## Symbolic/factored action lessons

Do not materialize Cartesian commitments.

Whir:
choose X/payment → cast → observe targets → choose target

Reshape:
choose X → choose sacrifice → cast → observe targets → choose target

Python symbolic work showed a 20-choose-7 subset space of 77,520 represented by about 98 reduced ZDD nodes in the test.

Before factoring:
- pathological request about 4,131 actions
- 4,097 X-artifact commitments
- multi-GB Python RSS

After factoring/packing:
- low-hundreds max requests
- about 55–57 MB representative RSS
- no OOM signature

Rejected lesson: broad Whir target frontiers changed downstream behavior. Preserve exact identity unless equivalence is proven.

## Cycle handling

Maintain an attempted-action ledger by exact sampled-world cycle state.

At a repeated cycle state:
- remember attempted strategic action IDs/mask
- do not choose the same action forever
- terminate diagnostically if all legal strategic actions are exhausted

Use bitsets where possible.

## Strategic ValueKey contents

Include:
- turn
- remaining library multiset
- known top/bottom/deduced counts
- hand multiset
- canonical battlefield and relevant permanent fields
- graveyard/exile multisets
- mana/stored mana
- land-play state
- Remora age/pending
- Ring/FTT/Uthros state
- commander state
- Chip attachment
- Power Artifact target
- spell-cast-this-turn
- Saga III pending
- live Urza permissions
- ordered runtime stack
- current window
- pending decision

Exclude unless objective needs:
- trace
- profiling
- ephemeral execution IDs
- RNG seed/unknown order
- interaction_seen for pure win objective
- reporting-only Urza cast turn

Strategic ValueKey must be built from the normalized Rust state and include all future-relevant public/known state: turn + explicit phase/step, own life, library belief, hand/public zones, canonical per-object battlefield state/attachments, typed mana/stored mana, land-play status, commander state, live permissions, ordered stack/window/pending choice, and typed delayed obligations. It excludes trace/profiling, unknown library order, and execution-only object/RNG provenance unless an objective explicitly needs that memory.

Physical cycle detection uses a separate exact sampled-world key including ordered hidden library and replay/random-event progression. Never use ValueKey as a concrete-world cycle key.

## Rust key/cache strategy

Benchmark:
1. direct compact typed Eq+Hash ValueKey
2. stable packed fingerprint with equality verification

Do not automatically reproduce Python SHA-256 hot-key cost.

Map iteration order must never affect action ordering/ties.

## Real parallelism

Use Rayon initially.

Natural levels:
- hands
- mulligan bottoms
- hidden worlds
- Q candidates

Avoid nested oversubscription.

First recommendation:
- many hands: parallel hands
- pathological one hand: parallel bottom/world coordinates
- one coordinate: single-thread Q first for profiling/cache locality
- only later try Q-candidate parallelism

Results must be scheduling-independent:
- explicit coordinates/seeds
- deterministic sort/reduction
- explicit tie order

Start with thread-local/coordinate-local caches. Benchmark shared sharded L2 only if profiling shows worthwhile cross-task reuse.

## Performance telemetry required from day one

Record:
- wall time / CPU time
- peak RSS
- allocations
- states visited
- decision requests
- actions before/after factoring
- max fanout and decision kind
- V/Q cache hits/misses/evictions
- time in key construction
- time in action generation
- time in transition application
- time in cache
- time in policy/Q
- terminal result / step count

Use Criterion, perf/cargo flamegraph and structured counters. Optimize deterministic fixtures, not intuition.

## Benchmark corpus

### Focused rules/information fixtures
Port the Python smokes for information boundaries, RNG, search-shuffle coupling, pending decisions, stack priority, permissions, top visibility, key equality, cycles, card mechanics and win catalog.

### Phase 5H quality corpus
Hands 12,13,19,20,21,24,25,27,29,33 × four paired worlds.

Target final corrected outcomes: v6 5/40, one-step 11/40, contingent 13/40, zero Q regressions vs v6.

### Human mulligan corpus
Port all 35 exact benchmark hands from benchmarks/human/human_mulligan_exact_hands.json.

### Hand 25 stress corpus
Run full hand and 7 bottoms × worlds 0..3, especially Hydro/world2, Island/world0, Island/world2 and Key/world1.

Initial performance goals:
- packed single-thread coordinate at least 5× faster than Python pathology if feasible
- full native multithread Hand 25 eventually single-digit minutes
- if not, flamegraph before policy restrictions

## Precomputed indexes

Build immutable CardId bitsets/tables for:
- artifact
- creature
- land
- legendary creature
- mana-value buckets
- MV0/1
- Whir/Reshape eligibility by X
- Transmute
- Bay exact MV
- Saga III
- Spellseeker / Merchant / Mystical / Muddle / Dizzy classes
- mana sources/producers
- value-engine pieces
- interaction/protection pieces

Target enumeration should be bitset intersections against current library membership rather than repeated string scans.

## Active-card coverage gate

The branch decklist is 99 cards excluding Urza and contains 95 distinct names including the commander. R0 must generate a versioned card catalog and a machine-readable coverage registry. Every active card must have exactly one explicit status:
- RULES_ACTIVE
- PRIMITIVE_ACTIVE
- ENVIRONMENT_DEFERRED
- POLICY_ONLY
- INTENTIONALLY_UNMODELED(reason)

CI must fail on a missing, duplicate, or unclassified active card. A prose mention or old Python handler does **not** count as implemented. Printed card metadata comes from the pinned/current Oracle catalog, not from duplicated hand-written constants.

## Preferred performance-reduction order

1. compact representation
2. memoization
3. temporal/factored actions
4. exact dominance and branch bounds
5. adaptive sampling
6. parallel execution
7. approximate policy pruning only as last resort with quality gate reopened

## Replay/data strategy

Normal run saves compact:
- seed/coordinate
- opening hand/bottom
- terminal/win turn/family
- strategic action IDs
- cache/performance summary

Diagnostic run adds:
- named full trace
- observations
- pending states
- action fanout
- Q decisions

Do not store full verbose traces for every Monte Carlo rollout.

## Environment model must be separate

Current goldfish assumptions:
- Remora +2/cycle
- Rhystic +2/cycle
- Faerie +1/cycle
- Battered Golem starts our turn untapped due to likely opponent artifact ETB
- simplified Mana Drain bank
- otherwise opponents mostly ignored

Future interaction models should plug into EnvironmentModel rather than alter intrinsic rules.

## Rust implementation phases

### R0 Bootstrap
Cargo workspace, CardId registry, benchmark CLI, Criterion, counters, Hand25 fixture.

### R1 State/RNG/information
TrueState, InformationState, PolicyView, stack/window/pending/permissions, stable RNG, strategic/replay keys.

### R2 Core sequencing
Turns/horizon, lands, mana/payment, artifact casts/ETBs, Urza/Construct/mana, priority/stack, draws/shuffles/search framework.

### R3 Search/tutor staging
Simple tutors, Whir, Reshape, Transmute, Bay, Saga III, Tezzeret, Top/scry, Urza permission. Factored actions from the start.

### R4 Engine cards/win catalog
Port high-frequency mechanics and all terminal-family prerequisites.

### R5 Deterministic rollout policy
Recreate rollout-v6 on numeric observations/actions. Do not overfit Hand25.

### R6 Hidden worlds/selective Q
CRN, shared search shuffle, value counts, caches, screen/confirm, contingent Q, confidence gate.

### R7 London DP
Bottom enumeration, Caverns seat conditioning, adaptive racing, exact early bounds, backward stage recursion.

### R8 Performance hardening
Profile cache size, indexes, state clone cost, allocations, thread granularity, optional Q parallelism. Hand25 is primary gate.

### R9 Analysis
Mulligan archetypes, tutor summaries, win distributions, interaction/protection, card swaps.

## First decisive Rust performance experiment

As soon as enough R1/R2/R3/R4 mechanics exist, replay:

Hand 25 — Hydroelectric Specimen bottom — world 2.

Measure:
- requests/sec
- state clones/sec
- cache probes/sec
- allocations/request
- key time
- action generation time
- total wall time

Python reference: about 1,667 s and 762k requests.

If Rust is not dramatically faster here, fix representation/cache design before porting more cards.

## Suggested local worktree

git fetch origin
git branch rust-engine-rebuild origin/rust-engine-rebuild
git worktree add ../urza-state-solver-rust rust-engine-rebuild
cd ../urza-state-solver-rust

Keep Python files initially as reference.

## Suggested dependencies

Likely useful:
- smallvec
- rayon
- blake3
- rand / rand_chacha
- serde / serde_json
- thiserror
- criterion for benchmarks

Consider bitflags, rustc-hash/hashbrown and tracing only after profiling. Pin versions to the actual toolchain when implementation begins.

## Code-review rejection rules

Reject a change that:
- lets policy read unknown library order
- uses thread completion order as a tie-break
- mixes environment assumptions into card rules
- flattens hidden contingent search into an oracle action
- merges exact card identities based on role similarity
- adds a card-specific policy restriction only to speed a benchmark
- includes trace/profiling fields in ValueKey
- changes RNG coordinates without versioning/parity review
- optimizes without a deterministic reproducer
- silently converts a hard blocker to horizon loss

## Key lessons

1. Information correctness is harder than raw card legality.
2. Exact identity matters.
3. Factor decisions at the time information becomes available.
4. Memory and CPU pathologies are different.
5. Small max fanout can still mean hundreds of thousands of requests.
6. Native compact caches may be a major speedup.
7. Common random numbers are part of the algorithm.
8. Parallelism must not define semantics.
9. Do not solve runtime by making the player less capable.
10. Every performance claim needs a deterministic fixture.

## Definition of success

The Rust rebuild succeeds when it:
- reproduces information-safe Python semantics
- passes deterministic rules/observation fixtures
- reproduces the corrected Phase 5H paired quality benchmark
- evaluates the held-out mulligan corpus
- produces exact T1–T6 distributions and named win families
- is reproducible across repeated runs and thread counts
- makes Hand25 and its worst coordinates fast enough that runtime no longer dictates policy simplification
- provides profiling sufficient to identify remaining algorithmic bottlenecks
- supports future protection/interaction and card-swap experiments without redesign

Core principle:

**Make the engine faster by making representation and search smarter — not by making the player less capable.**
