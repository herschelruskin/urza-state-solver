# Strategic / Value-State Audit

This document classifies every current `State` and `Perm` field before the solver
gets a seed-independent `V(s)` / `Q(s,a)` cache key.

The audit is intentionally conservative.  No Oracle rule, search behavior, or
canonical key changes are made in this branch.  The purpose is to establish which
facts are true future state, which are hidden-information/chance state, and which
are trajectory analytics that should not fragment the base value function.

The executable source of truth is `state_field_audit.py`; `state_field_audit_smoke.py`
fails if a future `State` or `Perm` field is added without being classified.

## Three different identities

The simulator should not force one universal hash to serve three different jobs.

### 1. Replay / diagnostic identity

Use a conservative full-state identity for replay, debugging and trajectory
verification.  It may include exact hidden library order, `rng_root_seed`, trace,
interaction history, win family, Urza cast turn and other provenance.

### 2. Concrete Markov transition identity

This is the deterministic sampled-world identity used by the current keyed RNG.
It needs exact hidden library order and the root random tape, plus every current
fact that can change future rules/legality.  Reporting text/history should not
change a transition.

### 3. Strategic expected-value identity

This is the future `V(s)` / `Q(s,a)` identity for non-Oracle DP/Monte Carlo.  It
must merge states that have the same expected future reward under the selected
objective and legal-information policy, even if they were reached through a
different seed or reporting history.

Crucially, strategic value is **not** obtained by merely deleting a few fields
from concrete true state.

## The library is a projection, not an exclusion

For Oracle/replay, exact `library` order is real true state and must remain exact.
For a non-clairvoyant policy value function, unknown order cannot be part of the
policy's state identity because doing so would create strategy fusion: two hidden
worlds that look identical to the player would receive separate values/policies.

The non-Oracle value state should therefore replace exact unknown order with a
belief/information representation containing, at minimum:

- remaining library composition/counts;
- legally known top cards and their order;
- legally known bottom cards/constraints when relevant;
- shuffle/information reset state;
- any other observation-derived hidden-zone constraint required by the rules.

The existing `InformationState` is the starting contract for this projection.
A later implementation should build a dedicated `LibraryBeliefKey` or equivalent
rather than hashing the true hidden tuple.

## Base scalar objective: `P(win by horizon)`

For the first value function, the default objective is the probability of winning
by the configured horizon (main production horizon T6).  The base key should:

### Retain current future-legality/resources

Retain:

- `turn`;
- hand multiset;
- battlefield with future-relevant permanent attributes;
- graveyard and exile contents;
- floating blue/colorless mana;
- `land_played`;
- `drain_bank`;
- `bauble_draws`;
- `remora_age` and `remora_upkeep_pending`;
- `saga3_pending`;
- `ring_counters`;
- `ftt_level`;
- `uthros_counters`;
- `urza`;
- `construct` (conservatively retained until proven redundant);
- `top_access` (conservatively retained until proven redundant);
- Reality Chip attachment state/target;
- `spell_cast_this_turn`;
- Power Artifact target;
- `vfc_pumps`;
- commander zone/tax state;
- terminal `won` status, unless terminal states are guaranteed to short-circuit
  before value-key construction.

`spell_cast_this_turn` is a useful example of **history that belongs in Markov
state**: it summarizes past events because FTT level 2 makes that fact affect what
can legally happen next.  Historical does not automatically mean removable.

### Replace exact unknown library order

`library` becomes belief/information state for non-Oracle expected value.  Exact
order remains in Oracle/concrete transition identity.

### Exclude from the base scalar value key

- `rng_root_seed`: needed for deterministic sampled worlds/replay, but keeping it
  in `V(s)` would prevent the cache from merging identical strategic states across
  Monte-Carlo seeds;
- `trace`: debugging/replay text only.

### Preserve but treat as objective-specific memory/analytics

- `urza_cast_turn`;
- `interaction_seen`;
- `win_family`.

For ordinary `P(win by T6)`, these do not change future legality and should not
fragment the base `V(s)` cache.  They remain valuable episode outputs.

If an objective's *future reward* depends on one of these historical facts, do not
blindly put the entire history tuple back into the base game key.  Augment value
state with the **minimal sufficient objective memory** instead.  Examples:

- `P(interaction seen by T3)`: a boolean/count/class summary needed until T3;
- `P(win with >=1 protection layer)`: current protection availability may be
  derived from game state; historical seen-but-spent cards generally belong only
  to episode analytics;
- distribution of first Urza cast turn: record the first-turn statistic as an
  objective accumulator/outcome field;
- win-family distribution: use terminal family as the reward/category rather than
  separating all live states by a future-irrelevant family string.

This preserves the interaction analytics work without sacrificing DP merge rate.

## Permanent-state audit

Strategic permanent identity retains:

- `name`;
- `tapped`;
- `sick`;
- `counters`;
- `mode`;
- `knack_granted`;
- `producer_urza_ready`.

The last field is especially important.  It is an engine compression resource,
not ordinary printed Magic state, but it represents a still-refundable producer
`+U` and therefore changes which future native/Knack tap action remains available.
A value key must not merge credit-bearing and credit-less states merely because
old Oracle `State.key()` handles this resource through dominance scoring.

Strategic permanent identity excludes:

- `knack_source`: provenance only; Knack and Helix grant the same modeled ability;
- `instance_tag`: ephemeral identity used while executing multi-step macros.

## Policy observation audit

The executable audit verifies that all fields classified as directly player- or
engine-visible match `PolicyView`, and that all strategic permanent attributes
match `PublicPermanent`.

Exact `library` is deliberately absent from `PolicyView`.  Legal knowledge about
hidden zones enters through `InformationState` (`known_top`, `known_bottom`,
`known_library_counts`, etc.).  `rng_root_seed`, trace, analytics history and
terminal reporting fields are not policy observations.

`producer_urza_ready` is classified as `engine_derived`: it is not literal card
text, but the policy/rules adapter must know the strategic option represented by
that compression state.

## Static usage evidence

`state_field_audit.py` also parses `urza_solver.py` with Python's AST and reports
attribute and keyword mentions for every audited field.  This is an evidence aid,
not a proof of semantic necessity: generic `getattr()` adapters and dataclass
iteration can evade a simple static count.

A field with zero static mentions is therefore flagged for manual review rather
than automatically deleted.  This is particularly important for conservative
fields such as `construct` or `top_access`: we should only collapse them after a
focused equivalence proof/test demonstrates no future behavioral distinction.

## What this audit deliberately does not do

This branch does **not**:

- change `State.key()`;
- change `canonical_true_state_key()`;
- change `canonical_markov_state_key()`;
- add an actual `canonical_strategic_state_key()` yet;
- change Oracle pruning, beam behavior or rules;
- wire V/Q memoization into production search.

Those changes come only after this classification passes locally and we review the
static usage report.

## Next implementation after audit validation

Once the audit smoke and usage report are reviewed, the next patch should add an
explicit strategic value projection, probably along these lines:

```text
StrategicValueState
    objective_id / objective-memory schema
    turn + public/current rules state
    hand / graveyard / exile multisets
    canonical future-relevant battlefield
    LibraryBeliefKey
        remaining composition
        known top/bottom constraints
        shuffle/information state
```

The key should be seed-independent and policy-information-safe.  We should then
instrument current search/rollouts to measure:

- raw states generated;
- concrete Markov unique states;
- strategic-value unique states;
- merge/collapse ratio;
- estimated `V`/`Q` cache hit rate by turn/depth.

Only after measuring those ratios should the solver begin using strategic memoized
values to alter production search decisions.
