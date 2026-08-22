# Non-Oracle Markov / DP / Monte-Carlo Implementation Roadmap

**Project:** Urza State Solver  
**Branch:** `development`  
**Status:** Active execution checklist  
**Companion design:** `NON_ORACLE_SOLVER_DESIGN.md`  
**Primary objective:** Build an information-faithful finite-horizon decision engine using Markov state abstraction, dynamic programming/memoization, and Monte Carlo sampling before considering any ANN/value-network approximation.

---

## 1. Why this document exists

`NON_ORACLE_SOLVER_DESIGN.md` is the conceptual specification. This file is the implementation checklist and audit ledger.

The project should use this document to answer four questions at all times:

1. What is already complete and validated?
2. What is the next dependency-safe implementation step?
3. What tests/audits must pass before a milestone is considered complete?
4. Which experimental outputs are trustworthy at the current stage?

A checkbox is not complete because code exists. It is complete only when the relevant regression/smoke tests pass and the implementation preserves the information boundary described below.

---

## 2. Final product goals

The non-Oracle system is being built primarily to answer these questions.

### Goal A — Mulligan policy and human-readable hand classes

For a presented seven and mulligan depth:

- recommend **KEEP / MULLIGAN**;
- if keeping below seven, evaluate legal London-bottom subsets;
- identify the best bottom package;
- estimate the value gap between the best keep and another mulligan;
- eventually cluster evaluated hands into useful strategic archetypes that humans can recognize at the table.

The experimental keep floor is 3 cards.

### Goal B — Tutor decisions from broad strategic states

For a legal information state:

- evaluate whether using a tutor now is worthwhile;
- compare legal tutor targets after the search information is legitimately available;
- summarize recurring target choices into broad strategic rules.

Tutor recommendations are useful infrastructure, but are secondary to mulligan and win-time analysis.

### Goal C — Hand-specific win-turn distribution

Given a hand, mulligan stage, policy, and environment, estimate:

- `P(win by T1)` through `P(win by T6)`;
- conditional win-turn distribution;
- no-win-within-horizon probability;
- common winning lines/families;
- common failure modes.

The primary horizon is the end of our turn 6. A miss is **no win within the modeled horizon**, not proof that the deck cannot eventually win.

### Goal D — Interaction sensitivity

Evaluate the same hand/deck under explicit interaction environments rather than pretending there is one universal win rate.

Future parameters may include probabilities/types such as:

- counterspell / stack interaction;
- artifact interaction;
- creature interaction;
- proactive protection / lock effects;
- table-action assumptions that drive Remora/Rhystic/Mastermind-style draws.

### Goal E — Paired deck/card comparison

For one or more swaps, estimate changes in:

- `P(win by T3/T4/T5/T6)`;
- keep/mulligan rate;
- kept-hand size;
- win-turn distribution;
- interaction resilience;
- tutor behavior;
- card appearance/draw/tutor/win-line frequency.

Use paired root seeds and common random numbers wherever compatible.

---

## 3. Core mathematical model

The rules engine owns the true concrete game state `S`.

The policy acts on legal information `I`, derived from public state plus legitimate hidden-zone knowledge.

The target finite-horizon decision quantities are conceptually:

```text
Q(I, a) = E[ future outcome | current information I, action a ]
V(I)    = max_a Q(I, a)
```

The expectation may be exact for small branches and Monte-Carlo estimated when hidden/random futures are too large to enumerate.

Important: the final value object should preserve the win-turn distribution, not only one scalar, even if a scalar/lexicographic objective is used to choose actions.

---

## 4. Non-negotiable invariants

These are architecture rules, not optimization suggestions.

- [x] Preserve the Oracle as a separate perfect-information ceiling and rules/search diagnostic.
- [x] Separate replay/debug identity from concrete Markov transition identity.
- [x] Separate concrete Markov identity from seed-independent strategic expected-value identity.
- [x] Exact unknown library order is not policy-visible.
- [x] Game randomness is derived from explicit deterministic RNG streams rather than trace length/history.
- [x] Policy/rollout RNG cannot perturb the actual game RNG stream.
- [x] Strategic value identity replaces unknown library order with legal information/belief representation.
- [x] Full win turn is retained through the configured horizon.
- [ ] A policy must never receive a raw `State`/TrueState reference capable of exposing hidden order.
- [ ] A non-Oracle root decision must be invariant to changing unrevealed future cards while holding PolicyView and policy RNG fixed.
- [ ] Future rollout decisions must remain information-constrained; sampled hidden worlds must not receive Oracle continuation policies.
- [ ] Commit-to-action and post-action observation decisions must be separate whenever new information is revealed.
- [ ] No production non-Oracle value cache may use Oracle `State.key()` as its strategic identity.

---

## 5. Existing foundation — current audit status

### 5.1 Reproducible concrete Markov state

- [x] `RandomStreams` exists with independent game/environment/policy/tie namespaces.
- [x] In-game shuffles use explicit Markov RNG rather than `len(trace)`.
- [x] `canonical_markov_state_key()` excludes reporting history while retaining concrete future-relevant state and sampled-world identity.
- [x] Architecture/RNG regression smoke coverage exists.

Relevant files:

- `solver_architecture.py`
- `urza_solver.py`
- `architecture_smoke.py`
- `ARCHITECTURE_HARDENING.md`

### 5.2 Strategic expected-value identity

- [x] `StrategicValueState` exists.
- [x] `LibraryBeliefKey` replaces exact unknown order with remaining counts + legitimate top/bottom/count knowledge.
- [x] `canonical_strategic_state_key()` is seed-independent.
- [x] Strategic field audit classifies live state versus provenance/analytics.
- [x] Objective-specific memory extension exists for path-dependent objectives.
- [x] Strategic collapse profiling exists.

Relevant files:

- `strategic_value_state.py`
- `strategic_value_state_smoke.py`
- `STRATEGIC_VALUE_KEY.md`
- `STRATEGIC_VALUE_STATE_AUDIT.md`
- `state_field_audit.py`
- `strategic_collapse_profile.py`

### 5.3 Legal information-state foundation

- [x] `InformationState` exists.
- [x] `PolicyView` omits exact unknown library order.
- [x] Known-top / known-bottom knowledge exists.
- [x] London-bottom information can be seeded without inferring hidden Oracle knowledge.
- [x] Shuffle resets invalid positional information.
- [x] Current propagation handles Top, scry, tutors/search shuffles, draws/top consumption, and continuous top visibility in a sidecar/instrumentation layer.
- [x] Legal-information collapse profiler carries `InformationState` alongside the existing Oracle graph without changing Oracle choices.

Relevant files:

- `opening_information_state.py`
- `information_state_propagation.py`
- `legal_information_collapse_profile.py`
- associated smoke files

### 5.4 DP/output scaffolding

- [x] `MemoizationStore` exposes V/Q cache namespaces.
- [x] Cache namespace includes horizon/objective/policy/information identity.
- [x] `EpisodeOutcome` stores win/no-win, exact win turn, terminal turn, horizon, family/reason.
- [x] Cumulative win-curve helper exists.
- [x] Replay trajectory structures exist.
- [x] Action-equivalence contract exists at the architecture layer.
- [ ] Production non-Oracle Bellman/DP evaluation uses these components.

### 5.5 Interaction analytics foundation

- [x] Own-deck interaction/protection taxonomy and episode analytics exist.
- [x] Historical analytics are intentionally kept outside the base Markov/value key.
- [ ] Opponent/environment interaction is a stochastic transition model rather than only observational analytics.

---

## 6. Phase 1 — Explicit non-Oracle decision / observation boundary

**This is the next implementation phase. Do not start Monte Carlo before this phase is complete.**

Current Oracle actions often return already-resolved successor `State` objects. That is valid for Oracle search but cannot be the policy-facing contract where an action reveals hidden information.

### 6.1 Introduce explicit decision objects

- [ ] Add/extend an explicit `PolicyAction` / `ActionIntent` representation for policy-facing actions.
- [ ] Give each action deterministic canonical identity.
- [ ] Give strategically equivalent actions an explicit equivalence identity.
- [ ] Ensure policy-facing action generation never requires inspection of an unknown future merely to decide which root actions exist.

### 6.2 Introduce typed observation events

Replace trace-string interpretation as the eventual production information mechanism.

Candidate event categories:

```text
Draw(card)
RevealTop(cards)
SearchZone(legal_cards / search context)
Shuffle()
MoveKnownCard(...)
PublicZoneChange(...)
EnvironmentObservation(...)
```

Checklist:

- [ ] Transition execution can emit typed observation events.
- [ ] `InformationState` can update from typed events.
- [ ] Existing trace text remains available for human audit/replay.
- [ ] Existing trace-parsing propagation is retained temporarily as a regression/reference adapter until typed events cover all required cases.

### 6.3 Split commit-before-observation actions

These must not remain one clairvoyant policy decision.

#### Sensei's Divining Top

- [ ] Decision 1: activate Top or not, without seeing unknown top three.
- [ ] Observation: reveal legal top cards after activation/cost.
- [ ] Decision 2: choose ordering using newly known cards.

#### Scry

- [ ] Decision to cast/activate the scry source occurs before seeing unknown cards.
- [ ] Scry observation reveals the legal cards.
- [ ] Top/bottom/order decision occurs only after reveal.

#### Tutors/search

- [ ] Decision to spend/cast/activate tutor occurs under current information.
- [ ] Search resolution exposes only legally searchable information.
- [ ] Target decision occurs after that observation.
- [ ] Post-search shuffle clears invalid positional knowledge.

#### Other reveal/draw-then-choose effects

- [ ] Audit all current card/action macros for the same decision→observation→decision requirement.

### Phase 1 acceptance gate

Do not check Phase 1 complete until all pass:

- [ ] Hidden-top invariance test.
- [ ] Hidden-future invariance test.
- [ ] Commit-before-observation test for Top.
- [ ] Post-observation Top-order sensitivity test.
- [ ] Equivalent scry tests.
- [ ] Tutor-use decision cannot depend on unknown concrete permutation.
- [ ] Policy-facing objects expose no exact unknown library order or root game RNG seed.
- [ ] Existing Oracle regression suite remains unchanged/passing.

---

## 7. Phase 2 — Non-Oracle rules adapter and deterministic base policy

Monte Carlo needs a legal continuation policy first; otherwise rollout evaluation suffers strategy fusion.

### 7.1 Non-Oracle rules adapter

Target conceptual interface:

```text
observation(true_state, information_state) -> PolicyView
legal_policy_actions(true_state, information_state) -> actions
apply_policy_action(true_state, information_state, action, game_rng)
    -> true_state + observations + updated information
is_terminal(...)
outcome(...)
```

Checklist:

- [ ] Create the adapter without reimplementing validated Magic mechanics.
- [ ] Adapter delegates resolution to shared Oracle rules functions where possible.
- [ ] Only the adapter/rules layer receives concrete hidden state.
- [ ] Policies receive `PolicyView`, actions, context, and their own RNG only.
- [ ] End-turn/upkeep/Saga mandatory windows remain correctly represented.

### 7.2 Deterministic knowledge-constrained base policy

The first base policy should be fast and interpretable, not perfect.

It should use only visible/legal features such as:

- mana/resources;
- land-drop availability;
- Urza access;
- fast mana;
- tutors;
- combo proximity;
- card advantage/engines;
- interaction/protection;
- known top/bottom information;
- turn/horizon urgency.

Checklist:

- [ ] Policy is deterministic for fixed policy version and visible input.
- [ ] Tie handling is deterministic or uses the isolated tie RNG.
- [ ] Policy version is recorded in outputs/cache namespace.
- [ ] Root action and continuation policy use the same information rules.
- [ ] Base policy can complete full T1–T6 episodes without Oracle search deciding future actions.

### Phase 2 acceptance gate

- [ ] Same PolicyView + same policy config => same deterministic choice despite different unknown futures.
- [ ] Full episode can be replayed from root seed/action sequence.
- [ ] No rollout/decision function accepts raw hidden state as a policy input.
- [ ] Base-policy batch produces complete win/no-win + exact win-turn records.

---

## 8. Phase 3 — First real DP / memoized value engine

### 8.1 Value representation

Prefer a distribution-rich value object over a single float, for example conceptually:

```text
P(win by T1)
P(win by T2)
...
P(win by T6)
```

plus optional terminal-family statistics.

The decision objective can remain versioned and simple, e.g.:

1. maximize `P(win by T6)`;
2. prefer earlier win distribution when primary value is effectively tied;
3. later add robustness/protection objectives only through explicit objective IDs/memory.

Checklist:

- [ ] Define versioned value/outcome object.
- [ ] Define comparison/utility semantics.
- [ ] Define terminal value semantics.
- [ ] Define horizon transition semantics.

### 8.2 Bellman/DP evaluation

- [ ] Implement `V(I)` lookup/evaluation using `canonical_strategic_state_key()`.
- [ ] Implement `Q(I,a)` lookup/evaluation using strategic state + action identity.
- [ ] Wire `MemoizationStore` into real non-Oracle evaluation.
- [ ] Record V/Q cache hits/misses and memory use.
- [ ] Never include exact unknown order or `rng_root_seed` in strategic expected-value cache identity.
- [ ] Preserve objective/horizon/policy version in cache namespace.

### 8.3 Exact versus approximate branches

- [ ] Enumerate small deterministic decision sets exactly.
- [ ] Collapse proven-equivalent action/payment branches before expensive evaluation.
- [ ] Retain beam search only as an optional branch-control/search optimization where exact strategic enumeration is too expensive.
- [ ] Beam pruning must not be used to claim unbiased probability estimates.

### Phase 3 acceptance gate

- [ ] Repeated equivalent strategic states produce cache hits.
- [ ] Known-information distinctions that can alter optimal action do not incorrectly merge.
- [ ] Small toy states match exhaustive enumeration exactly.
- [ ] Changing root seed alone does not split expected-value identity when legal information/composition is otherwise equivalent.
- [ ] Cache-enabled and cache-disabled evaluation agree on controlled cases.

---

## 9. Phase 4 — Monte Carlo hidden-world sampling and policy improvement

### 9.1 Hidden-world sampler

Target:

```text
sample_hidden_world(information_state, policy_rng)
```

or equivalent using the strategic library belief.

Checklist:

- [ ] Samples satisfy remaining card-count constraints.
- [ ] Samples preserve legitimate known-top order.
- [ ] Samples preserve legitimate known-bottom constraints/order.
- [ ] Samples do not use the actual concrete hidden world except as the realized game after a policy decision is made.
- [ ] Policy RNG stream is independent from actual game RNG.

### 9.2 One-step rollout policy improvement

Initial algorithm:

1. enumerate serious legal root actions;
2. sample hidden worlds consistent with current information;
3. evaluate the same sampled worlds across competing actions where possible;
4. take one candidate root action;
5. continue with the deterministic information-constrained base policy;
6. record terminal outcome/win turn;
7. estimate action values and choose the best.

Checklist:

- [ ] Common random numbers across competing root actions.
- [ ] No Oracle continuation inside sampled worlds.
- [ ] Information state updates as sampled cards become legitimately revealed.
- [ ] Separate rollout traces from the actual game trace.
- [ ] Record rollout counts and uncertainty.

### 9.3 Adaptive/racing budgets

- [ ] Start contenders with a small shared batch.
- [ ] Allocate more samples to close contenders.
- [ ] Drop clearly inferior actions using documented criteria.
- [ ] Enforce maximum rollout budget.
- [ ] Report uncertainty using a documented method appropriate to endpoint/statistic.

### Phase 4 acceptance gate

- [ ] Monte Carlo actual-world isolation regression.
- [ ] Rollout no-strategy-fusion instrumentation/test.
- [ ] Increasing rollout budget does not change the realized actual game RNG tape.
- [ ] On toy problems with known exact values, MC estimates converge toward exact DP values.
- [ ] Common-random-number comparison has lower/equal empirical variance than independent action sampling in a calibration test.

---

## 10. Phase 5 — Mulligan engine (first flagship application)

This is the highest-priority end-user application.

### 10.1 Sequential mulligan state machine

Stages:

```text
7A initial seven
7B free multiplayer seven
6  = fresh seven, bottom 1
5  = fresh seven, bottom 2
4  = fresh seven, bottom 3
3  = fresh seven, bottom 4 (experimental floor)
```

Checklist:

- [ ] Current seven is evaluated before the next fresh seven is generated/revealed.
- [ ] Keep-vs-mull decision cannot depend on the actual unrevealed next seven.
- [ ] Seat/Caverns eligibility is sampled before mulliganing and exposed if the player would know it.
- [ ] Going below 3 is disabled by experimental policy, not misrepresented as a Magic rules floor.

### 10.2 Exact bottom enumeration

For bottom counts 1–4, legal subset counts are at most 35.

- [ ] Enumerate all legal bottom subsets for deep/single-hand analysis.
- [ ] Do not use beam search to hide bottom subsets.
- [ ] Model bottom order only if it can alter reachable gameplay; otherwise use documented canonical ordering.
- [ ] Carry chosen bottom knowledge into `InformationState`.

### 10.3 Mulligan continuation cache

Because a rejected seven is shuffled back before the next fresh seven, the expected value of taking another mulligan at a stage can often be cached by:

- deck version;
- stage;
- seat/Caverns eligibility;
- policy/environment configuration.

- [ ] Implement/reuse stage continuation-value cache.
- [ ] Validate that current rejected hand identity is not incorrectly included when the rules distribution is independent of it.

### 10.4 Required output

For each analyzed hand/stage:

- [ ] KEEP/MULL recommendation.
- [ ] Best bottom set if keeping.
- [ ] Keep value.
- [ ] Mull-again continuation value.
- [ ] Value gap/decision confidence.
- [ ] Full win-turn curve under chosen line/policy.
- [ ] Alternative bottom packages and values in deep-analysis mode.

### Phase 5 acceptance gate

- [ ] Mulligan future-invariance regression.
- [ ] All bottom subsets accounted for in deep mode.
- [ ] Independent brute-force toy mulligan calculation agrees with DP result.
- [ ] Fixed-seed sequential trace proves future sevens are not generated before the keep/mull decision requires them.

---

## 11. Phase 6 — Human-readable hand archetypes

Do not let hand tags control the value function. First obtain trustworthy evaluated hands, then summarize them.

Potential descriptive features:

- lands / initial mana;
- fast mana;
- colored-mana access;
- commander deployment speed;
- tutor count/type;
- combo pieces / redundancy;
- draw/engine access;
- interaction/protection;
- dead/conditional cards;
- earliest feasible win turn;
- modeled resilience.

Checklist:

- [ ] Create versioned card-role metadata used for interpretation, not hidden policy cheating.
- [ ] Store evaluated hand feature vectors + mulligan stage + recommended action/value.
- [ ] Cluster/group similar evaluated hands with an interpretable method first.
- [ ] Assign human-readable labels only after inspecting cluster contents.
- [ ] Validate archetype recommendation accuracy against direct DP/MC evaluation on held-out hands.
- [ ] Provide nearest-archetype + confidence/distance for new human-entered hands.

ANN/CNN is **not required** for this step. Start with transparent clustering/classification/rules derived from evaluated data.

---

## 12. Phase 7 — Tutor/state decision analysis

- [ ] Separate tutor-use timing from post-search target selection.
- [ ] Preserve all materially distinct legal targets before expensive evaluation.
- [ ] Evaluate target `Q(I,a)` values under the same sampled worlds where applicable.
- [ ] Produce target rankings and value gaps.
- [ ] Summarize recurring target choices into broad state→target guidance.
- [ ] Audit whether beam/action caps ever remove strategically distinct tutor routes in the non-Oracle layer.

---

## 13. Phase 8 — Hand win-probability / win-turn calculator

Input should include at least:

- current/starting hand;
- mulligan depth/bottom knowledge;
- policy version;
- horizon;
- interaction/environment configuration;
- seat/Caverns facts where relevant.

Output:

- [ ] `P(win by T1..T6)`.
- [ ] exact/estimated uncertainty.
- [ ] no-win-within-horizon probability.
- [ ] conditional median/mean win turn where meaningful.
- [ ] win-family distribution.
- [ ] tutor/engine line frequencies.
- [ ] common failure modes.
- [ ] computation budget/cache statistics for auditability.

Important reporting language:

```text
P(win | hand, policy, environment, horizon)
```

not an unconditional universal `P(win | hand)`.

---

## 14. Phase 9 — Stochastic interaction/environment model

Start simple and parameterized before attempting full opponent-deck simulation.

### 14.1 Environment transition model

- [ ] Define versioned environment state/configuration.
- [ ] Use `environment_rng` only.
- [ ] Sample events only when they occur; policy cannot inspect future environment events.
- [ ] Preserve baseline deterministic/goldfish environment for comparison.

### 14.2 Interaction scenarios

Possible first modes:

```text
goldfish
low interaction
moderate interaction
high interaction
```

or explicit class probabilities.

- [ ] Record which interaction event occurred and when.
- [ ] Define which lines are vulnerable to which interaction classes.
- [ ] Model protection/counterplay with explicit rules/assumptions.
- [ ] Report sensitivity curves rather than one supposedly universal win rate.

### Phase 9 acceptance gate

- [ ] Environment future-invariance: policy decision before event realization cannot depend on future sampled event.
- [ ] Environment RNG changes do not alter game/policy RNG streams.
- [ ] Goldfish mode reproduces the no-opponent-event baseline within the same policy semantics.

---

## 15. Phase 10 — Paired deck/card-swap experiments

### Single swap

- [ ] Same root seed set.
- [ ] Same seat/environment streams.
- [ ] Same policy/objective/horizon.
- [ ] Common rollout worlds where compatible.
- [ ] Paired outcome differences retained per seed/scenario.

Report at least:

- [ ] delta `P(win by T3/T4/T5/T6)`;
- [ ] delta keep/mull rate;
- [ ] delta kept-hand-size distribution;
- [ ] delta win-turn distribution;
- [ ] archetypes helped/hurt;
- [ ] card appearance/draw/tutor/win-line frequency;
- [ ] uncertainty on paired differences.

### Multiple swaps

- [ ] Support factorial/combination experiments for small candidate sets.
- [ ] Estimate interaction effects between swaps rather than assuming additive card values.

---

## 16. Beam-search policy in the final architecture

Beam search remains allowed, but is not the mathematical definition of value.

Use beam search for:

- finding promising complex sequencing candidates;
- controlling pathological action branching;
- tutor/engine line candidate generation when exact search is too large;
- Oracle ceiling/search diagnostics.

Do **not** use beam pruning as if discarded branches had zero probability when reporting an unbiased probability estimate.

Specific policy:

- Mulligan bottom subsets: exact enumeration.
- Small strategic action sets: exact enumeration.
- Stochastic outcomes: correct weighting / Monte Carlo sampling.
- Large mechanical sequence space: action equivalence first, beam only if still necessary.
- Final candidate comparison: DP/Monte-Carlo value, not raw Oracle heuristic score.

---

## 17. ANN / neural value model decision gate

Default: **do not build one.**

Only reconsider an ANN/lightweight learned value approximation after the exact/interpretable system has been profiled and one or more measured bottlenecks remain, such as:

- strategic cache hit rate is too low;
- `V(I)` evaluation remains too slow for useful batch throughput;
- Monte Carlo policy improvement is accurate but too expensive;
- an already trustworthy MC/DP teacher dataset exists.

If introduced later, the learned model should initially approximate/distill a trusted value/policy target rather than replace the rules engine or information model.

Required gate before any neural model:

- [ ] DP/MC baseline is correct and validated.
- [ ] Throughput bottleneck is measured, not assumed.
- [ ] Teacher labels/dataset are versioned and reproducible.
- [ ] Learned approximation is benchmarked against held-out high-budget DP/MC evaluations.

---

## 18. Test/audit matrix that must grow with the project

### Information safety

- [ ] hidden-top invariance;
- [ ] hidden-future invariance;
- [ ] mulligan-future invariance;
- [ ] shuffle knowledge reset;
- [ ] known-top sensitivity after legitimate reveal;
- [ ] commit-before-observation;
- [ ] post-observation contingent-choice sensitivity;
- [ ] Monte-Carlo actual-world isolation;
- [ ] rollout no-strategy-fusion.

### State/value correctness

- [x] strategic state field audit coverage.
- [x] strategic-key seed independence smoke coverage.
- [x] legal-information propagation smoke coverage.
- [ ] V/Q cache key collision/equivalence controlled tests.
- [ ] cache-on versus cache-off result equality on exhaustive toy states.
- [ ] value-distribution aggregation tests.

### RNG/replay

- [x] trace-independent in-game shuffle.
- [x] explicit root-seed Markov RNG.
- [x] isolated RNG namespaces at architecture level.
- [ ] changing MC budget cannot alter actual game trajectory given same chosen actual actions.
- [ ] environment RNG isolation integration test.
- [ ] full non-Oracle trajectory replay test.

### Statistical calibration

- [ ] MC versus exact toy benchmark.
- [ ] convergence versus rollout count.
- [ ] paired/common-random-number variance benchmark.
- [ ] confidence/credible interval coverage sanity checks where practical.

### Oracle preservation

- [x] Oracle remains a separate mode.
- [ ] Every major non-Oracle refactor reruns the relevant Oracle regression suites.
- [ ] Any shared-rules behavior change must be explicitly identified as a rules fix, not silently introduced by policy work.

---

## 19. Performance metrics to record from the beginning

For batch simulations:

- hands/hour;
- wall time/hand;
- CPU-seconds/hand;
- P50/P90/P95/worst-case runtime;
- V/Q cache hit rate;
- strategic-state count;
- policy-decision count;
- MC-decision count;
- rollout worlds;
- adaptive early stops;
- beam/action-cap events where applicable;
- memory use.

Parallelism rule of thumb:

- batch mode: parallelize games;
- one-hand deep analysis: parallelize rollout worlds if useful;
- do not accidentally multiply both axes beyond the configured worker budget.

---

## 20. Required machine-readable experiment provenance

Every serious result should record enough to reproduce it:

- repository commit hash / dirty status;
- ordered deck hash/version;
- root seed(s);
- RNG scheme version;
- policy version;
- strategic-key version;
- objective/version;
- turn horizon;
- environment model/version;
- rollout budget/racing parameters;
- beam/action-cap settings if used;
- mulligan floor/rules configuration;
- worker/parallelism configuration.

Do not compare two deck/policy runs without verifying that all non-target experimental settings are matched or deliberately documented as changed.

---

## 21. Audit/update protocol

This file is intended to be modified throughout implementation.

For every meaningful milestone patch:

1. implement the smallest coherent dependency-safe change;
2. add/update focused smoke/regression tests;
3. run the relevant Oracle regression tests if shared rules/action behavior was touched;
4. update checkboxes in this roadmap only for behavior that is actually validated;
5. append one concise audit-log row below;
6. if architecture/design assumptions changed, update `NON_ORACLE_SOLVER_DESIGN.md` as well.

Do not mark an entire phase complete if only scaffolding/interfaces exist.

---

## 22. Current next action

**Next milestone: Phase 1 — explicit non-Oracle decision / observation boundary.**

Recommended first patch:

1. define typed policy-facing action intents and observation events;
2. build a thin non-Oracle transition result contract;
3. migrate one high-information action end-to-end (Sensei's Divining Top is the best first target);
4. prove commit-before-observation and post-observation-choice tests;
5. leave Oracle `legal_actions(State) -> successor States` unchanged while this parallel contract is validated.

Only after that pattern is proven should scry and tutor macros be migrated.

---

## 23. Audit log

| Date | Commit / state | Audit result |
|---|---|---|
| 2026-08-22 | `58a13aab...` | In-game shuffles migrated from trace-dependent randomness to explicit Markov RNG; concrete transition identity separated from replay identity. |
| 2026-08-22 | `09ea325...` and preceding audit commits | Strategic/value-state fields audited before seed-independent V/Q identity; reporting/history fields separated from future-legality state. |
| 2026-08-22 | `26581c2d...` | Seed-independent strategic value key, legal hidden-zone information propagation, London bottom knowledge, and decision-neutral strategic-collapse profiling present. Current state/RNG/value-key foundation judged aligned with Markov + DP + Monte-Carlo goal. Actual non-Oracle Bellman/MC decision engine not yet implemented. |
| 2026-08-22 | this roadmap patch | Consolidated execution order, phase gates, acceptance tests, beam-search role, ANN decision gate, and audit/update protocol so progress can be checked against one persistent implementation plan. |

---

## 24. Definition of project success

The project is successful without an ANN if the final system can reproducibly and information-faithfully:

1. recommend sequential mulligan/keep decisions and London bottoms;
2. generalize those evaluated hands into useful human-readable hand classes;
3. estimate hand-specific win-turn distributions through T6;
4. recommend major tutor decisions from broad states;
5. quantify sensitivity to interaction/environment assumptions;
6. run paired card/deck-swap experiments with uncertainty;
7. explain its assumptions, state identity, policy version, and simulation provenance well enough that results can be audited and reproduced.

A neural approximation is optional future optimization, not a requirement for reaching these goals.
