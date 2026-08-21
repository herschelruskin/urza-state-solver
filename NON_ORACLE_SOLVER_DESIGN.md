# Non-Oracle Solver Design & Implementation Guide

**Project:** Urza State Solver\
**Status:** Living pre-implementation specification\
**Target:** Future knowledge-constrained / Monte Carlo branch

## 1. Purpose

The existing Oracle solver should remain the validated theoretical
ceiling: given the exact hidden future of the library, what is the best
line the search can find?

The next branch should answer a different question:

> Given only information a player is legally entitled to know, what
> action maximizes the probability of winning by the experimental
> horizon?

The intended progression is:

**Oracle ceiling → knowledge-constrained heuristic policy → Monte Carlo
policy → comparison with real/manual play**

The non-Oracle tool should eventually provide both high-throughput
simulation and actionable play guidance: keep/mulligan probabilities,
bottom recommendations, tutor decisions, Top/scry choices, and engine
commitments.

## 2. Fundamental architecture: reality versus knowledge

The simulator must separate the true game state from the information
available to the decision-maker.

### TrueState

Contains everything required to resolve one concrete game: exact library
order, hand, battlefield, graveyard, command zone, exile, mana, tapped
state, counters, turn/phase, pending effects, and hidden random
outcomes.

### KnowledgeState

Contains only information the player may legally know: hand, public
zones, revealed cards, cards viewed with Top/scry, known top/bottom
ordering, tutor/search information, and known library composition.

The policy must never inspect hidden portions of TrueState.

A shuffle is a hard information boundary: the simulator generates or
retains a concrete shuffled library, while KnowledgeState loses
positional information invalidated by that shuffle.

## 3. Prevent indirect clairvoyance

Hiding `library[0]` from a scoring function is insufficient.

If two actions are searched through the one actual hidden future and the
solver chooses the action that happens to draw the better hidden card,
it has still cheated.

Therefore decisions must not be selected by comparing outcomes from the
actual hidden future. The actual true library resolves the action only
after the policy has chosen it.

## 4. Knowledge transitions

-   **Draw:** reveal the actual top card only when drawn.
-   **Scry:** reveal exactly the permitted cards; retain only legally
    justified ordering knowledge.
-   **Sensei's Divining Top:** reveal the top three and preserve chosen
    ordering until disrupted.
-   **Tutor/search:** library inspection permitted by the effect is
    legitimate information.
-   **Shuffle:** erase invalidated top/bottom positional knowledge.
-   **Reality Chip/Future Sight effects:** the exposed top card is
    legitimate knowledge; deeper cards remain hidden.

Dedicated regression tests should cover each transition.

## 5. Experimental horizon

Primary endpoint:

> Win by the end of our turn 6 = success; otherwise experimental loss.

This bounds the most complex late-game states and reflects the intended
competitive goldfish question. Oracle and non-Oracle comparisons should
use the same horizon.

## 6. Mulligans are the first priority

Mulligans are expected to be the largest source of Oracle advantage.

The realistic branch should support Commander London mulligans to a
keep-3 floor, but decisions must use only the visible seven and legal
information.

### First implementation

Build a deterministic knowledge-only mulligan heuristic using visible
features such as lands, colored mana, acceleration, Urza accessibility,
card advantage, tutors, engines, combo pieces, interaction, redundancy,
and dependence on future draws.

### Monte Carlo mulligans

Mulligans should be the first Monte Carlo decision class.

For each candidate keep/bottom package:

1.  condition only on visible information;
2.  sample plausible hidden libraries consistent with that information;
3.  simulate the candidate across those worlds;
4.  estimate P(win by T6) and secondary metrics;
5.  choose by expected performance rather than the one actual hidden
    future.

Example output:

``` text
Keep 6; bottom Sea Gate Restoration
P(win by T6) = 0.61

Alternative: bottom Mystic Remora
P(win by T6) = 0.48
```

## 7. Selective Monte Carlo, not Monte Carlo everywhere

Naively evaluating every action over many deep rollout worlds will
explode computationally.

Use tiers:

1.  **Deterministic policy** for routine or clearly dominant actions.
2.  **Monte Carlo** for high-impact uncertain decisions: mulligans,
    Top/scry, tutor timing/targets, major engine commitments.
3.  **Adaptive sampling:** start with perhaps 8--16 worlds, eliminate
    clearly inferior actions, then spend 32--64 or 100+ only where
    needed.

Exact budgets must be calibrated empirically.

## 8. Hidden-world sampling

Rollout worlds must satisfy KnowledgeState constraints. Known top cards,
known bottom cards, revealed information, and remaining library
composition must be respected.

After a shuffle, invalid positional constraints disappear.

For action comparison at one decision point, consider common random
numbers: evaluate competing actions against the same sampled worlds when
appropriate to reduce variance.

Random streams for the actual game, rollout sampling, and tie-breaking
should ideally be separated/deterministically derived.

## 9. Actual game versus rollout worlds

Each simulated game has one actual TrueState.

At a decision:

1.  observe KnowledgeState;
2.  sample temporary worlds consistent with it;
3.  evaluate legal actions across those worlds;
4.  choose one action;
5.  apply it to the actual TrueState;
6.  reveal/update KnowledgeState only as rules permit;
7.  continue.

The policy must not know whether the actual hidden world is favorable
before information is revealed.

## 10. Objective

Primary objective should be **P(win by T6)**.

Earlier expected win turn is a useful secondary objective. Do not
optimize only mean win turn if that favors fragile fast lines over
substantially more reliable lines.

The utility function should be configurable and documented.

## 11. Preserve Oracle

Do not weaken or delete Oracle mode.

For identical experimental configurations, retain:

-   Oracle perfect-information ceiling;
-   deterministic knowledge-constrained heuristic;
-   Monte Carlo knowledge-constrained policy.

Compare win rate, win turn, family distribution, keep sizes, and
Oracle-to-policy gap.

## 12. Throughput is a product requirement

The tool must ultimately outpace manual goldfishing.

Performance is part of correctness for the intended use case. Record
wall time, nodes, edges, policy decisions, Monte Carlo decisions,
rollout worlds, early stops, cache hits, and memory where practical.

The desired architecture is:

**fast deterministic policy for routine play + adaptive Monte Carlo for
important uncertainty.**

## 13. Parallelism and scaling

Independent rollout worlds and independent games are naturally parallel.

Order of work:

1.  establish single-process correctness;
2.  parallelize rollout worlds across CPU workers;
3.  parallelize games;
4.  profile memory/serialization;
5.  consider high-core workstations or cluster/cloud execution only
    after profiling.

GPU acceleration is not assumed initially because the workload is
dominated by branching, Python state transitions, hashing, and rules
evaluation.

## 14. Caching

Policy caching should consider normalized information states rather than
unknowable exact library orders.

Two different TrueStates may be identical from the player's perspective
and therefore share a policy decision.

A future information-state key may include observable zones, resources,
turn, known top/bottom information, remaining known library composition,
pending effects, and policy configuration.

## 15. Tutors

Tutors are not inherently Oracle behavior. If an effect legally searches
the library, selecting among legal targets using that information is
valid.

Potential uncertainty lies in whether to tutor now and which target has
the best expected value under uncertain future draws.

Reuse the validated target-aware tutor retention logic unless later
evidence justifies a change.

## 16. Shared rules engine

Do not independently rewrite Magic rules for the non-Oracle branch.

Reuse validated Oracle mechanics for casting, mana, commander tax,
tutors, transmute, artifacts, combo engines, Remora upkeep, bounce
legality, state transitions, card metadata, and terminal detection.

The branch point should primarily be the **information/decision layer**.

## 17. Auditability

Every draw should name the card and source.

Policy decisions should be capable of producing summaries such as:

``` text
Decision: activate Top?
Worlds: 64

Do nothing: P(win T6)=0.31
Activate Top: P(win T6)=0.46

Selected: activate Top
```

Actual-game traces and temporary rollout evaluation must be clearly
distinguished. Full rollout traces should be diagnostic-only to avoid
massive logs.

## 18. Statistical outputs

Per-game data should eventually include seed, opening seven, mulligan
sequence, final keep, bottoms, keep size, policy estimates, Urza cast
turn, win/loss, win turn, family, draw sources, tutors/targets, Monte
Carlo decision counts, rollout counts, wall time, graph metrics, and
final trace.

Large-run summaries should include uncertainty/confidence intervals
where appropriate.

## 19. Development phases

### Phase A --- freeze Oracle reference

Before branching, require rules smoke suites, tutor-cap tests,
Remora/upkeep tests, bounce legality, named draws, reproducibility
provenance, worker parameter propagation, T6, and keep-3 validation.

### Phase B --- KnowledgeState skeleton

Separate TrueState and KnowledgeState without Monte Carlo. Add
anti-clairvoyance tests.

### Phase C --- deterministic realistic policy

Implement knowledge-only mulligan and action heuristics. Benchmark
against Oracle.

### Phase D --- Monte Carlo mulligans

Add hidden-world sampling only for mulligans. Measure convergence,
stability, and runtime.

### Phase E --- selective in-game Monte Carlo

Add decision classes incrementally: Top/scry first, then tutor
timing/targets, then major engine decisions where justified.

### Phase F --- scale

Adaptive rollout budgets, caching, parallelism, and hundreds/thousands
of games.

## 20. Mandatory anti-clairvoyance tests

-   **Hidden-top invariance:** two TrueStates with identical visible
    information but different unknown top cards must yield the same
    deterministic policy action.
-   **Shuffle invariance:** known positional information disappears
    after shuffle.
-   **Known-top sensitivity:** after Top/scry legally reveals cards, the
    policy may react to those cards.
-   **Mulligan future invariance:** identical opening sevens with
    different hidden futures must produce the same deterministic
    mulligan decision.
-   **Actual-world isolation:** changing unrevealed actual future cards
    must not change a decision before those cards become known.
-   **Monte Carlo isolation:** rollout distributions must be sampled
    from KnowledgeState, not conditioned on the actual hidden future.

These should become mandatory regression tests.

## 21. Monte Carlo convergence tests

For representative decisions compare rollout budgets such as 8, 16, 32,
64, 128, and larger calibration runs.

Track selected action, estimated win probability, confidence interval,
ranking stability, and runtime.

Use the smallest budget that provides sufficiently stable decisions for
each decision class.

## 22. Prevent compute explosion

Candidate tools:

-   adaptive sampling;
-   early stopping;
-   safe heuristic action pre-filtering;
-   information-state caching;
-   common random numbers;
-   bounded rollout depth;
-   validated terminal combo shortcuts;
-   dominance pruning;
-   target-aware action retention;
-   selective Monte Carlo;
-   parallel rollouts.

Every optimization must be audited for strategic loss or information
leakage.

## 23. Manual goldfish comparison

Later, compare predetermined opening hands across human play,
deterministic policy, Monte Carlo policy, and Oracle.

Record keep/bottom choices, major decisions, win results, disagreements,
solver-discovered lines, and human-discovered missing behaviors.

This validates practical usefulness.

## 24. Git strategy

Recommended structure:

-   `oracle-stable`: preserved validated Oracle;
-   `development`: current Oracle development until freeze;
-   future `knowledge-policy` / `non-oracle`: knowledge-constrained
    architecture;
-   optional Monte Carlo sub-branches before merging.

Reports should record commit hashes and experimental configuration.

## 25. Initial Codex implementation order

When this document is handed to Codex, do **not** begin with Monte
Carlo.

1.  Read project docs and architecture.
2.  Freeze/confirm Oracle.
3.  Design KnowledgeState.
4.  Add anti-clairvoyance tests.
5.  Implement deterministic knowledge-constrained policy.
6.  Implement realistic mulligan heuristic.
7.  Run paired Oracle/heuristic experiments.
8.  Add hidden-world sampler.
9.  Add Monte Carlo only to mulligans.
10. Benchmark convergence/runtime.
11. Add selective Top/scry Monte Carlo.
12. Add tutor/engine Monte Carlo only if justified.
13. Add adaptive budgets.
14. Parallelize.
15. Scale.

At every stage:

**correctness → reproducibility → auditability → performance → scale**

## 26. Open design questions

Do not guess these prematurely:

-   exact mulligan heuristic;
-   rollout policy versus bounded search;
-   utility function;
-   early-stop/confidence thresholds;
-   rollout budgets by decision class;
-   information-state cache representation;
-   known-bottom representation;
-   which in-game decisions deserve Monte Carlo;
-   future opponent modeling;
-   evolution of environmental Remora/Rhystic assumptions beyond
    goldfish mode.

## 27. Success criteria

The non-Oracle solver should:

1.  never use hidden information illegally;
2.  preserve legally acquired information;
3.  forget positional information after shuffles;
4.  be reproducible;
5.  share the validated Oracle rules engine;
6.  estimate action value under uncertainty;
7.  explain recommendations;
8.  outpace manual goldfishing at useful volume;
9.  scale across CPU workers;
10. produce machine-readable large-run data;
11. compare directly with Oracle;
12. remain replayable/auditable card-by-card.

## 28. Guiding principle

Do not make the solver "realistic" by arbitrarily weakening it.

> **Give it exactly the information a player is legally entitled to
> possess, then make it as strong as computationally practical at
> reasoning from that information.**

Oracle asks what is possible with perfect foresight.

The knowledge-constrained Monte Carlo solver asks what the **best
decision is under uncertainty**.
