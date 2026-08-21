# Non-Oracle Solver Design & Implementation Guide

**Project:** Urza State Solver  
**Status:** Living pre-implementation specification  
**Target:** Future knowledge-constrained / Monte Carlo branch  
**Primary goals:** information-faithful play, useful decision guidance, reproducible large-sample data, and throughput that materially exceeds manual goldfishing.

---

## 1. Purpose

The existing Oracle solver answers an intentionally unrealistic but useful question:

> Given the exact hidden future of the library, what is the fastest legal winning line the search can find?

That mode should remain preserved as a theoretical ceiling and as a rules/search validation environment.

The next branch should answer a different question:

> Given only information a player is legally entitled to know at the current decision point, what action maximizes the probability of winning by the experimental horizon?

The intended progression is:

**Oracle ceiling → deterministic knowledge-constrained policy → Monte Carlo policy improvement → comparison with real/manual play**

The non-Oracle system should ultimately serve two related but distinct purposes:

1. **High-throughput population simulation**
   - run hundreds or thousands of hands;
   - estimate cumulative win probabilities;
   - compare cards/deck configurations;
   - measure mulligan behavior and win-family frequencies;
   - substantially outpace manual goldfishing.

2. **Deep decision analysis**
   - evaluate a particular opening hand or game state;
   - estimate keep versus mulligan value;
   - recommend bottom cards;
   - compare tutor targets;
   - evaluate Top/scry decisions;
   - explain expected-value differences between plausible lines.

These two use cases should share one rules engine and information model but may use different compute budgets.

---

## 2. Terminology: “non-cheating” versus “realistic”

These terms must not be conflated.

### Information-faithful / non-cheating

A policy is information-faithful if it never chooses an action using hidden information unavailable to a real player.

Examples:

- it cannot know the next natural draw before that card is revealed;
- it cannot bottom Sea Gate Restoration because it secretly knows three lands are coming;
- it cannot decide to activate Top because the hidden top three happen to be perfect;
- after a shuffle, it cannot retain knowledge of the new hidden order.

### Realistic

A fully realistic game model would additionally require realistic opponents, interaction, spell timing, table position, threat assessment, and opponent card choices.

The initial non-Oracle branch is therefore better described as:

> **an information-faithful goldfish / abstract-table policy**

rather than a complete cEDH table simulator.

This distinction should appear in reports and documentation.

---

## 3. Preserve the Oracle as a separate baseline

Do not weaken, overwrite, or gradually “de-clairvoyance” the Oracle until its original meaning is lost.

Maintain:

- **Oracle mode:** exact hidden information; best line found under the search limits.
- **Knowledge policy mode:** no illegal information access; deterministic policy.
- **Monte Carlo policy mode:** no illegal information access; decisions improved using sampled plausible futures.

For paired experiments, all modes should use the same:

- deck version;
- rules engine;
- environmental assumptions;
- turn horizon;
- starting-seat model;
- root seed set where meaningful.

The difference between Oracle and policy is itself useful data.

---

## 4. Core architecture: TrueState, InformationState, and PolicyView

The original design proposed duplicating public game information in a `KnowledgeState`. A safer architecture is to avoid maintaining two copies of the same battlefield/hand data.

Use three conceptual layers.

### 4.1 TrueState

Contains the complete concrete game needed to resolve events:

- exact hidden library order;
- hand;
- battlefield;
- graveyard;
- exile;
- command zone;
- mana;
- tapped/untapped/sick status;
- counters;
- turn and timing window;
- pending triggers/effects;
- actual randomized outcomes;
- any future opponent/environment events if those are later modeled.

Only the simulator/rules engine may directly inspect all of TrueState.

### 4.2 InformationState

Stores persistent facts about hidden information that the player legitimately knows.

Examples:

- exact known top sequence;
- exact known bottom sequence where rules permit it;
- cards revealed by scry/Top;
- cards known to have moved to hidden zones;
- whether positional information has been invalidated by a shuffle;
- known remaining library multiset;
- revealed opponent/environment information if introduced later.

This should be a compact set of constraints, **not an explicitly enumerated probability distribution over every possible library order**.

### 4.3 PolicyView

A read-only observation derived from `TrueState + InformationState`.

The policy receives PolicyView, not TrueState.

It may expose:

- our hand;
- public battlefield/graveyard/exile;
- mana/resources;
- known top/bottom cards;
- known library composition;
- turn/timing;
- legal actions at the current information set;
- visible pregame conditions such as seat / Caverns eligibility.

It must not expose:

- exact unknown library order;
- unknown future shuffle results;
- unrevealed future random events.

### Why this design is safer

Duplicating hand/battlefield inside a separate knowledge object risks stale or inconsistent copies. A derived PolicyView makes public information authoritative in one place while creating a hard API boundary around hidden data.

---

## 5. Make information leakage difficult by construction

Do not rely only on developer discipline.

Architectural constraints should make cheating hard.

Recommended rules:

- policy functions never accept a raw `TrueState`;
- policy functions accept only `PolicyView` / `InformationState`;
- hidden library fields are not reachable through the policy object;
- define a `true_state_key()` for simulation/transposition;
- define a separate `information_state_key()` for policy caching;
- never reuse a true-state key as a policy-state key;
- sort/canonicalize collections used in policy decisions so Python hash iteration does not silently change choices;
- pin and report `PYTHONHASHSEED`, but also remove avoidable hash-order dependence from production decisions.

A dedicated test should fail if a policy-facing object exposes exact hidden library order.

---

## 6. Prevent indirect clairvoyance

Simply hiding `library[0]` from `score()` is not sufficient.

Suppose two actions are considered from the same visible state:

- Action A eventually draws a hidden combo card in the actual library.
- Action B eventually draws a land.

If the solver searches both actions through the **one actual hidden future** and chooses A because it sees that future outcome, the solver has cheated even though no scoring function directly read the top card.

Therefore:

> **The actual hidden future may resolve the action after the policy chooses it; it may not be used to choose the action.**

This is the central anti-clairvoyance invariant.

---

## 7. A second major leakage risk: strategy fusion in Monte Carlo rollouts

This is important enough to treat as a hard design rule.

A tempting implementation is:

1. sample 50 possible hidden libraries;
2. run the existing Oracle search inside each sampled library;
3. average each candidate action’s Oracle result.

Do **not** treat that as a valid realistic policy estimate.

Why?

Inside each sampled world, Oracle would make future decisions using that world’s hidden information. It would effectively use a different clairvoyant strategy in every possible world.

That is a classic **strategy-fusion / determinization** problem.

It overestimates what a single information-constrained player can actually achieve.

### Required rule

All future decisions inside a Monte Carlo rollout must also be made by an information-constrained rollout policy that only uses information revealed by that point in that rollout.

The Oracle engine may be used as:

- an upper bound;
- a diagnostic;
- a rules-transition reference;

but not as the default continuation policy inside “realistic” rollouts.

---

## 8. Recommended Monte Carlo method: rollout policy improvement

The first Monte Carlo implementation should use a **base deterministic policy** plus one-step rollout improvement.

At an important decision:

1. enumerate serious legal root actions;
2. sample hidden worlds consistent with current InformationState;
3. apply one candidate root action;
4. for the rest of that sampled game, follow the fast deterministic knowledge-constrained base policy;
5. estimate each root action’s outcome over many sampled worlds;
6. choose the root action with the best expected value.

This gives a strong practical property:

> Monte Carlo improves decisions without recursively running expensive Monte Carlo at every future node.

Later, selective recursive Monte Carlo may be explored, but it should not be the starting architecture.

---

## 9. Action → observation → contingent choice must be modeled explicitly

Many Magic actions reveal information *after* the player commits to an action.

The non-Oracle engine must not collapse those stages into one clairvoyant branch.

### Example: Sensei’s Divining Top

Incorrect non-Oracle action generation:

```text
choose among all six reorderings of the actual hidden top three
```

before the policy has chosen to activate Top.

That leaks the top three into the activation decision.

Correct structure:

```text
Decision 1: activate Top or not?
    ↓
pay cost / activate
    ↓
Observation: reveal actual top three
    ↓
Decision 2: choose ordering using the now-known three cards
```

### Example: scry

Casting Witching Well must be chosen without seeing unknown top cards.

After the spell resolves and scry occurs, the cards become known and the scry ordering decision may use them.

### Example: tutor/search

Choosing to spend a tutor is made under current knowledge.

Once the search effect resolves, inspecting the library and choosing a legal target is legitimate.

This separation is essential for:

- Top;
- scry;
- tutors;
- draw-then-discard effects;
- random reveal effects;
- future opponent/environment observations.

---

## 10. Knowledge transitions

Every information-changing rule should explicitly update InformationState.

### Draw

The actual top card moves to hand and becomes known at that moment.

### Scry N

- reveal exactly the top N cards;
- policy may choose the legal top/bottom arrangement;
- retained top order becomes known;
- bottomed cards become known to the degree the effect permits.

For standard scry, the player chooses the order of cards placed on top/bottom and can therefore know that chosen order.

### Sensei’s Divining Top

The viewed top three are legitimate knowledge. Chosen ordering remains known until cards move or a shuffle invalidates it.

### Reality Chip / top-card visibility

If the top card is legally exposed/viewable, that card is known.

Do not expose deeper cards.

### Tutor/search

Information explicitly available through the search is legitimate.

### Shuffle

A shuffle is a hard positional-information reset.

After a shuffle:

- the actual game gets a concrete random library order;
- known top/bottom positional facts invalidated by the shuffle are cleared;
- the player still knows the remaining library composition to the extent inferable from decklist and known zones;
- the policy cannot inspect the new actual hidden permutation.

### Draw from a known top

If the player knows the top card, drawing it should consume that known-top entry and expose the next known entry if one exists.

---

## 11. Belief state should be represented implicitly

Do not store millions of possible libraries.

For this deck, a compact belief representation is normally enough:

- exact remaining card multiset;
- known ordered prefix;
- known ordered suffix where applicable;
- known cards in other zones;
- constraints created by recent observations.

A function such as:

```text
sample_hidden_world(information_state, rng)
```

can generate concrete library orders consistent with those constraints.

This keeps the information model exact enough for play while avoiding an enormous explicit POMDP belief distribution.

---

## 12. Randomness must be split into independent deterministic streams

This should be mandatory, not optional.

The actual game’s randomness must not change because the policy used more or fewer rollout samples.

Derive independent RNG streams from the root seed, for example:

- `game_rng` — actual opening hands, actual shuffles, actual hidden world;
- `environment_rng` — future abstract opponent events if modeled;
- `policy_rng` — Monte Carlo world sampling;
- `tie_rng` — policy tie-breaking if stochastic tie-breaking is retained.

Changing rollout budget must not change the actual game’s library order.

Reports should record the root seed and RNG scheme/version.

---

## 13. Mulligans are the first and highest-value realistic decision

Mulligans are likely the largest source of Oracle advantage.

The realistic implementation must be **sequential**, not retrospective.

### 13.1 Critical rule

A real player sees the current seven and must decide:

> keep this hand, or take another mulligan?

They do not get to inspect the next fresh seven first.

Therefore the policy must never generate all future mulligan hands and retrospectively choose the best stage.

### 13.2 Stages

The current Commander model should remain the rules source of truth, with the experimental keep floor of 3:

- initial seven;
- free multiplayer seven;
- keep 6: fresh seven, bottom 1;
- keep 5: fresh seven, bottom 2;
- keep 4: fresh seven, bottom 3;
- keep 3: fresh seven, bottom 4.

Keep-3 is an **experimental simulation floor**, not a Magic rules floor.

### 13.3 Sequential policy

At each stage:

1. observe the current seven;
2. evaluate the best legal keep/bottom option using only current information;
3. compare it with the expected value of taking the next mulligan;
4. keep or mull;
5. only if mulligan is chosen does the actual next fresh seven get generated/revealed.

### 13.4 Useful computational shortcut

Because the hand is shuffled back before drawing a new seven, the distribution of the **next fresh seven** at a given mulligan stage does not depend on the identities in the current rejected hand, assuming no earlier effect changed deck composition.

Therefore the expected value of “mulligan again” can often be precomputed/cached by:

- deck version;
- mulligan stage;
- seat/Caverns eligibility;
- policy configuration;
- environmental model.

This can make realistic mulligan decisions substantially cheaper.

---

## 14. Bottom-card selection

Bottom selection must also avoid hidden-future knowledge.

At keep 3 or 4 there are only:

```text
C(7,4) = 35
C(7,3) = 35
```

possible card subsets.

That is small enough that the realistic policy should not blindly inherit a heuristic that might permanently hide strong bottom choices.

Recommended approach:

### Fast deterministic mode

- score all legal bottom subsets using visible hand features;
- choose the best policy score;
- no hidden library inspection.

### Monte Carlo mode

Use a two-stage procedure:

1. cheaply score **all** legal bottom subsets;
2. retain a diverse top K;
3. evaluate those finalists with Monte Carlo.

For calibration or single-hand analysis, exhaustive Monte Carlo over all 35 subsets is feasible.

Bottom ordering should be modeled only if it can matter to reachable gameplay; otherwise use a documented canonical ordering to avoid meaningless branching.

---

## 15. Pregame information must be visible to the policy

If seating/start position is known before mulligans, the policy may use it.

This matters for:

- Gemstone Caverns;
- whether the player is first;
- future abstract opponent-turn assumptions.

Do not encode Caverns as a hidden 75% fact if the simulated player should already know whether they are eligible in that game.

If a 75% seat approximation is retained for batch simulation, first sample seat/eligibility as part of the actual game environment, then expose that fact to the mulligan policy.

---

## 16. Experimental horizon and outputs

Primary goldfish endpoint:

> **Win by the end of our turn 6 = success; otherwise no win within horizon.**

Do not describe a T6 miss as proof the deck cannot win.

Reports should preserve the full cumulative curve:

- P(win by T1);
- P(win by T2);
- P(win by T3);
- P(win by T4);
- P(win by T5);
- P(win by T6).

This is more informative than only a binary T6 result and supports card/deck comparisons.

Conditional win-turn distributions should also be retained.

---

## 17. Environmental assumptions must be explicit

Removing clairvoyance does not automatically make the simulation realistic.

Current or historical abstractions have included effects such as:

- Mystic Remora drawing an assumed number of cards from opponents;
- Rhystic Study drawing an assumed number;
- Faerie Mastermind environmental draws;
- Mana Drain banking assumed mana;
- Battered Golem receiving multiplayer artifact untaps;
- Chrome Dome use in an opponent end step.

These assumptions can materially affect results.

### Initial plan

Preserve validated assumptions so Oracle and policy remain comparable, but expose them as a named configuration such as:

```text
environment = baseline_goldfish
```

### Later plan

Introduce stochastic abstract-table scenarios rather than fixed guaranteed events.

Possible modes:

- conservative;
- baseline;
- high-action table.

The policy must not know future sampled opponent events before they occur.

This should be a later branch milestone, not mixed into the first anti-clairvoyance implementation.

---

## 18. Deterministic knowledge-constrained base policy

Before Monte Carlo, build a fast base policy that chooses one action from PolicyView.

It should use only legal information.

Possible features:

- current mana and future visible mana;
- land drop availability;
- ability to cast Urza;
- fast mana;
- card advantage;
- tutors;
- engine pieces;
- combo proximity;
- redundancy;
- interaction;
- known top cards;
- graveyard recursion;
- turn/horizon urgency.

The policy should be deterministic under a fixed policy version unless an explicit stochastic policy is being tested.

This base policy has three roles:

1. fast high-throughput simulation;
2. future continuation policy for Monte Carlo rollouts;
3. baseline against which Monte Carlo improvement is measured.

---

## 19. Decision classes for Monte Carlo

Do not invoke Monte Carlo because an action “looks complicated.”

Invoke it when uncertainty about hidden information plausibly changes the best action.

Initial priority:

1. mulligan / keep;
2. bottom-card selection;
3. Top activation and post-look ordering;
4. scry commit and post-look ordering;
5. tutor timing;
6. tutor target when multiple strategic targets compete;
7. major engine deployment;
8. resource-preservation choices only if later profiling shows meaningful value.

Mechanical combo continuation after all relevant information is public should normally use deterministic rules/policy.

---

## 20. Monte Carlo rollout procedure

At an eligible decision state:

1. derive PolicyView and InformationState;
2. enumerate serious root actions without using hidden information;
3. sample N hidden worlds consistent with InformationState;
4. preferably use the same sampled worlds for competing root actions;
5. apply each root action in each world;
6. continue each rollout using the deterministic knowledge-constrained base policy;
7. update InformationState normally as cards are revealed during each rollout;
8. stop at win, T6 horizon, or other defined rollout terminal;
9. aggregate outcomes;
10. select the root action.

Do not let continuation policy inspect the sampled world’s hidden library.

---

## 21. Common random numbers and paired action evaluation

When comparing root actions, evaluate them against the same sampled hidden worlds where possible.

This produces paired outcomes such as:

```text
world 1: A wins T4, B wins T5
world 2: A loses,   B wins T4
world 3: A wins T3, B wins T3
...
```

Paired sampling substantially reduces noise in action-value differences.

For statistical comparison, track the paired difference in utility, not only two independent means.

---

## 22. Adaptive rollout budgets

Do not assign 100 rollouts to every decision automatically.

A practical “racing” strategy:

1. evaluate all serious actions over a small initial batch, e.g. 8–16 worlds;
2. drop actions that are clearly inferior;
3. allocate additional worlds to close contenders;
4. stop when:
   - one action is sufficiently ahead;
   - the maximum budget is reached;
   - the actions are effectively tied within a configured tolerance.

The exact confidence method and thresholds should be calibrated empirically.

For a Bernoulli endpoint such as win-by-T6, use a documented interval method such as Wilson or a beta-binomial posterior rather than a naive normal approximation at very small N.

---

## 23. Utility function

Primary objective:

> maximize P(win by T6)

Secondary preferences may include:

1. earlier win turn conditional on comparable win probability;
2. resource robustness;
3. retained interaction.

Do not optimize only mean win turn if that favors a fragile T3 line with a much lower win probability than a reliable T4 line.

A practical lexicographic utility may be easier to interpret than an arbitrary weighted scalar.

The exact policy utility must be versioned and reported.

---

## 24. High-throughput mode versus deep-analysis mode

One compute configuration should not be forced to serve every purpose.

### `policy-fast`

Goal: maximum hands/hour.

- deterministic knowledge policy;
- no or minimal Monte Carlo;
- ideal for thousands of games and broad deck comparisons.

### `policy-mc`

Goal: realistic large-sample estimate with selective policy improvement.

- Monte Carlo at high-value decisions only;
- adaptive budgets;
- intended for hundreds or thousands of games if throughput permits.

### `decision-analysis`

Goal: robust advice for one opening hand/state.

- larger rollout budgets;
- exhaustive bottom packages where feasible;
- detailed action-value table;
- confidence intervals;
- slower runtime acceptable.

These modes should share semantics and differ primarily in compute budget.

---

## 25. Throughput is a first-class product requirement

The tool should materially outpace manual goldfishing.

Track:

- hands/hour;
- CPU-seconds/hand;
- wall time/hand;
- median and tail latency;
- number of policy decisions;
- number of Monte Carlo decisions;
- rollout worlds;
- early-stopped worlds;
- nodes/edges if search remains inside rollouts;
- cache hit rate;
- memory.

Do not optimize only median runtime. A handful of pathological 20-minute hands can dominate total batch cost.

Profile P50, P90, P95, and worst-case runtime.

---

## 26. Parallelism strategy

Avoid uncontrolled nested multiprocessing.

For large batch throughput, the simplest efficient first design is often:

> **one process per game, with rollouts executed locally/sequentially inside that game**

Advantages:

- low cross-process serialization;
- simple deterministic RNG ownership;
- independent games scale naturally;
- easier cancellation/progress accounting.

For deep analysis of one hand, parallelizing rollout worlds across workers may be preferable.

Eventually support a worker-budget policy:

```text
batch mode: parallelize games
single-hand analysis: parallelize rollouts
never multiply both axes beyond configured CPU budget
```

This is particularly important on Windows where worker startup/interrupt behavior has already required care.

---

## 27. Caching

Different TrueStates can correspond to the same information state.

Potential cache layers:

### Policy action cache

Keyed by normalized InformationState/PolicyView plus policy configuration.

### Mulligan stage value cache

Expected value of taking another mulligan at a given stage can be reused extensively.

### Monte Carlo statistics cache

For repeated decision states, accumulate rollout statistics rather than restarting from zero, but only if RNG/reproducibility semantics are carefully defined.

### True-state engine cache

Existing rules/search caches may remain keyed by concrete state where appropriate.

Never include unknowable exact hidden order in a policy cache key.

---

## 28. Policy distillation as a future speed path

If deep Monte Carlo becomes too expensive for large batches, use it as a teacher.

Possible later workflow:

1. collect many information states;
2. run high-budget Monte Carlo offline;
3. store action-value labels;
4. fit/refine a fast heuristic or lightweight model;
5. use that distilled policy in `policy-fast`;
6. periodically re-evaluate against the teacher.

This can preserve much of the Monte Carlo decision quality while dramatically increasing hands/hour.

Do not start here; first build trustworthy labels.

---

## 29. Tutors

Tutors are not inherently clairvoyant.

Once a search effect legally resolves, the player may inspect the permitted library information and choose a legal target.

The uncertainty often lies in:

- whether to tutor now;
- whether to preserve the tutor;
- which strategic target maximizes expected win probability.

Reuse the validated target-aware tutor retention infrastructure in underlying search/diagnostics.

In non-Oracle action sequencing:

```text
Decision: cast/activate tutor?
    ↓
resolve search / legal observation
    ↓
Decision: choose target using legally revealed library information
```

Do not expose exact post-shuffle order after the tutor.

---

## 30. Shared rules engine

The non-Oracle branch should not reimplement Magic rules independently.

Reuse validated mechanics for:

- casting;
- mana payment;
- commander tax;
- tutors/transmute;
- artifacts;
- combo engines;
- Remora cumulative upkeep;
- bounce legality;
- card metadata;
- draw sequencing;
- named draw traces;
- state transitions;
- terminal combo detection.

The main fork is the **decision/information layer**, not the underlying rules engine.

A rules bug fixed in one mode should ideally be fixed in shared code and inherited by all modes.

---

## 31. Traceability and auditability

Every actual draw should name the card and source.

Every important policy decision should be able to emit an audit record such as:

```text
Decision: Keep current 6?
Visible hand: ...
Stage: keep-6
Policy: MC-v1
Worlds evaluated: 64

Keep / bottom Sea Gate Restoration:
P(win by T6) = 0.61

Mulligan to 5:
Estimated continuation value = 0.52

Selected: KEEP
```

For in-game decisions:

```text
Decision: activate Top?
Worlds evaluated: 48

Do nothing:
P(win by T6)=0.31

Activate Top:
P(win by T6)=0.46

Selected: activate Top
```

Actual-game traces and temporary rollout traces must be distinct.

Full rollout traces should be disabled by default and available in diagnostic mode.

---

## 32. Machine-readable decision dataset

In addition to per-game output, create a decision-level dataset.

Each important decision row should record:

- game seed;
- decision ID;
- turn/timing window;
- information-state fingerprint;
- policy version;
- candidate actions;
- rollout counts;
- action value estimates;
- uncertainty intervals;
- chosen action;
- realized eventual game outcome.

This dataset will be valuable for:

- debugging;
- policy calibration;
- identifying recurring decision patterns;
- later policy distillation;
- studying actual keep/bottom recommendations.

---

## 33. Per-game and aggregate statistical outputs

Per-game fields should include:

- root seed;
- commit hash;
- policy version;
- environment configuration;
- starting seat/Caverns eligibility;
- opening hands shown sequentially;
- keep/mulligan decisions;
- final kept hand;
- bottoms;
- keep size;
- Urza cast turn;
- win/no-win by T6;
- win turn;
- win family;
- named draw sources;
- tutors and targets;
- number of policy/MC decisions;
- rollout count;
- wall time;
- resource metrics;
- actual trace.

Aggregate reports should include:

- cumulative win curve T1–T6;
- confidence intervals;
- keep-size distribution;
- mulligan rate by stage;
- family distribution;
- Urza cast-turn distribution;
- runtime distribution;
- policy decision frequencies.

---

## 34. Statistical uncertainty has two layers

Keep separate:

1. **Empirical game uncertainty**
   - how often games actually win across root seeds.

2. **Monte Carlo action-value uncertainty**
   - uncertainty in an estimated action value because only a finite number of hidden worlds were sampled.

Do not report a rollout confidence interval as if it were the confidence interval for the deck’s overall win rate.

---

## 35. Deck/card comparison experiments should be paired

A major intended use is comparing card choices or deck versions.

Whenever possible use paired experimental design:

- same root seeds;
- same seat/environment streams;
- same policy version;
- same rollout-budget rules;
- common random numbers where compatible.

Report differences such as:

```text
Δ P(win by T4)
Δ P(win by T6)
Δ keep rate
Δ median win turn
Δ runtime
```

with paired uncertainty estimates.

This is far more sensitive than comparing two unrelated batches.

For a card swap, also record:

- how often each card appears in kept hands;
- how often it is drawn;
- how often tutored;
- how often it participates in the winning line;
- whether it changes mulligan decisions.

---

## 36. Anti-clairvoyance regression tests

These should become mandatory.

### Hidden-top invariance

Create two TrueStates with identical PolicyView but different unknown top cards.

A deterministic policy must choose the same action.

### Hidden-future invariance

Change several unrevealed future cards while keeping visible information identical.

The policy decision must remain identical.

### Mulligan future invariance

Same current seven, different actual next seven / future library.

The current keep/mull decision must not change.

### Monte Carlo actual-world isolation

With identical InformationState and identical policy RNG stream, changing the actual hidden world must not change the root Monte Carlo decision before any differing hidden card is revealed.

### Shuffle reset

Known top/bottom positional information disappears after shuffle.

### Known-top sensitivity

After Top/scry legitimately reveals cards, the policy may respond differently.

### Commit-before-observation

The decision to activate Top or cast a scry spell must not depend on the unknown cards that the action would reveal.

### Post-observation contingency

Once those cards are legitimately revealed, the follow-up ordering decision may depend on them.

### Rollout no-strategy-fusion

Instrument rollout policy access and prove it never receives the sampled world’s unknown library order.

---

## 37. Reproducibility tests

A formal benchmark should record:

- Git commit;
- deck hash/version;
- root seeds;
- turn horizon;
- action cap;
- beam/depth if used;
- mulligan floor;
- environment model;
- policy version;
- rollout budget;
- RNG scheme/version;
- `PYTHONHASHSEED`.

Repeated runs with the same configuration should reproduce:

- actual game hidden world;
- policy decision sequence;
- selected actions;
- final outcome;

except when intentionally testing stochastic-policy variance.

---

## 38. Monte Carlo convergence tests

For representative decision classes evaluate:

- 8 worlds;
- 16;
- 32;
- 64;
- 128;
- 256+ for calibration where useful.

Track:

- chosen action;
- P(win by T6);
- uncertainty interval;
- action ranking stability;
- wall time.

Different decision classes may need different budgets.

The objective is not “use as many rollouts as possible.”

It is:

> **find the smallest budget that produces sufficiently stable decisions for the intended mode.**

---

## 39. Oracle comparison must use the same rules/environment

If Oracle and policy use different Remora assumptions, horizon, bounce rules, or worker parameters, the gap is uninterpretable.

Before paired comparison, freeze a shared semantic configuration.

Oracle differs in information access and search policy—not in card rules.

---

## 40. Validation against manual goldfishing

Later, create a fixed set of opening hands.

For each:

1. human records keep/mulligan decision;
2. human records bottom choices;
3. human plays the hand without future knowledge;
4. deterministic policy evaluates it;
5. Monte Carlo policy evaluates it;
6. Oracle may provide ceiling.

Compare:

- keep agreement;
- bottom agreement;
- major decision agreement;
- realized win rate/turn;
- cases where solver finds a strong line human missed;
- cases where human reasoning reveals missing solver mechanics.

Do not use human agreement as the sole definition of correctness. The purpose is calibration and discovery.

---

## 41. Development phases

### Phase A — finish and freeze Oracle

Before branching:

- mandatory rules smoke suites pass;
- target-aware tutor retention passes;
- Remora cumulative upkeep passes;
- bounce-target/timing legality passes;
- named draw tracing passes;
- Repurposing Bay/mana and other suspicious traces are audited;
- reproducibility provenance is recorded;
- workers inherit all parameters;
- T6 horizon is validated;
- keep-3 Oracle stage is validated.

Freeze/tag the commit.

### Phase B — information-boundary skeleton

Implement:

- InformationState;
- PolicyView;
- separate true/information keys;
- independent RNG streams;
- action/observation split;
- anti-clairvoyance tests.

Do not add Monte Carlo yet.

### Phase C — deterministic base policy

Implement:

- sequential realistic mulligans;
- non-clairvoyant bottoms;
- deterministic in-game policy;
- fast batch mode.

Benchmark against Oracle and manual spot checks.

### Phase D — Monte Carlo mulligans

Implement:

- hidden-world sampler;
- sequential keep-versus-mull value;
- Monte Carlo bottom finalists;
- stage-value caching;
- convergence tests.

### Phase E — selective in-game policy improvement

Add, one decision class at a time:

1. Top/scry;
2. tutor timing;
3. tutor target;
4. engine deployment;
5. other decisions only when profiling/data justify them.

### Phase F — performance engineering

Add:

- adaptive racing;
- caching;
- process-level batching;
- runtime-tail diagnostics;
- policy distillation if justified.

### Phase G — large experiments

Run:

- hundreds/thousands of hands;
- paired deck/card comparisons;
- Oracle versus policy comparisons;
- environment sensitivity analyses.

---

## 42. Initial Codex implementation order

When this document is handed to Codex, do not ask it to “build the Monte Carlo solver” in one task.

Recommended sequence:

1. read `AGENTS.md`, `URZA_SOLVER_SPEC.md`, `TEST_PLAN.md`, this document, and the frozen Oracle;
2. propose exact PolicyView/InformationState interfaces;
3. add anti-clairvoyance test fixtures;
4. implement the API boundary;
5. split commitment actions from post-observation choices;
6. implement independent RNG streams;
7. implement sequential deterministic mulligans;
8. implement deterministic bottom selection;
9. implement deterministic in-game base policy;
10. benchmark fast policy;
11. add hidden-world sampler;
12. add one-step Monte Carlo improvement for mulligans;
13. add convergence/racing;
14. add Top/scry Monte Carlo;
15. add tutors/engines only when justified;
16. parallelize within a strict worker budget;
17. scale experiments.

At every stage:

**rules correctness → information correctness → reproducibility → auditability → decision quality → performance → scale**

---

## 43. Things not to do

Do not:

- pass raw TrueState into the policy and merely promise not to read hidden fields;
- run Oracle independently inside each sampled hidden world and call the average “realistic”;
- retrospectively choose among future mulligan hands;
- let Top/scry reorder actions reveal cards before deciding whether to activate the effect;
- let a shuffle preserve invalid positional knowledge;
- use the actual game RNG for Monte Carlo sampling;
- use nested multiprocessing without a global worker budget;
- optimize only mean win turn;
- compare deck versions on unrelated random batches when paired seeds are possible;
- call the model fully realistic while opponent activity remains abstract.

---

## 44. Open design questions

These should be settled empirically rather than guessed:

- exact base-policy scoring/features;
- exact sequential mulligan keep thresholds;
- root action pre-filtering;
- utility tie-breaks;
- rollout budgets by decision class;
- racing/confidence thresholds;
- information-state cache representation;
- bottom-order relevance;
- extent of future stochastic opponent model;
- whether recursive Monte Carlo/MCTS is ever worth its compute;
- whether policy distillation is needed;
- environment scenarios for Remora/Rhystic/Mana Drain/opponent artifacts.

---

## 45. Success criteria

The project succeeds if the non-Oracle system:

1. never chooses actions using illegal hidden information;
2. correctly uses legally revealed information;
3. forgets positional information after shuffles;
4. makes mulligan decisions sequentially;
5. separates commitment from later information-revealing choices;
6. avoids strategy fusion in rollout evaluation;
7. is reproducible under fixed configuration;
8. shares the validated rules engine with Oracle;
9. estimates action value under uncertainty;
10. explains important recommendations;
11. materially outpaces manual goldfishing;
12. scales across CPU resources without uncontrolled process explosion;
13. produces cumulative T1–T6 and decision-level data;
14. supports statistically efficient paired deck comparisons;
15. remains replayable and auditable card-by-card.

---

## 46. Guiding principle

Do not make the solver “realistic” by arbitrarily weakening it.

> **Give it exactly the information a player is legally entitled to possess, then make it as strong as computationally practical at reasoning from that information.**

The Oracle asks:

> What is possible with perfect foresight?

The knowledge-constrained solver asks:

> What should a strong player do with the information actually available?

The Monte Carlo layer asks:

> Under uncertainty, how much better is each available decision in expectation?

The engineering objective is to answer those questions at enough speed to generate more reliable data than manual goldfishing can realistically produce.
