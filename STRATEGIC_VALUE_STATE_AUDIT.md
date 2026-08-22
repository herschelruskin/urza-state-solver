# Strategic / Value-State Audit

This audit classifies every current `State` and `Perm` field before the solver gets
a seed-independent `V(s)` / `Q(s,a)` cache key. It does **not** change Oracle
rules, pruning, search behavior, or the existing concrete Markov key.

The executable source of truth is `state_field_audit.py`; the smoke suite fails if
a future `State` or `Perm` field is added without classification.

## Three identities, not one universal hash

### Replay / diagnostic identity

Conservative identity used for replay/debugging. It may contain exact hidden
library order, `rng_root_seed`, trace text, interaction history, win family, Urza
cast turn, and other provenance.

### Concrete Markov transition identity

Identity for one deterministic sampled world. It needs exact hidden order,
`rng_root_seed`, and every fact required to reproduce the next concrete transition.
Reporting-only history must not affect it.

### Strategic expected-value identity

Identity for future `V(s)` / `Q(s,a)` under a non-clairvoyant policy. It must merge
states with the same expected future reward and legal observation even if they
came from different seeds, hidden permutations, or reporting histories.

This third identity is **not** merely concrete state minus a few fields.

## Library treatment

For Oracle/replay, exact `library` order remains true hidden state.

For non-Oracle value, exact unknown order must be replaced by a belief/information
projection. At minimum the future key needs:

- remaining library composition/counts;
- legally known top cards in order;
- legally known bottom cards/constraints when relevant;
- any additional hidden-zone constraint required by the policy/rules adapter.

The existing `InformationState` is the starting contract. A future
`LibraryBeliefKey` should combine remaining composition with `known_top` /
`known_bottom` knowledge without exposing the sampled hidden permutation.

`shuffle_epoch` should not automatically enter value identity merely because a
shuffle occurred in the past. If two information states have the same remaining
composition and the same present knowledge constraints, the epoch number itself
is history unless a future policy/RNG contract explicitly requires it.

## Base objective: `P(win by horizon)`

The first strategic value function is scalar probability of winning by the chosen
horizon (production target T6).

### Retain

The base key retains current future-legality/resource state:

- `turn`;
- hand multiset;
- battlefield with future-relevant permanent attributes;
- graveyard and exile contents;
- floating blue/colorless mana;
- `land_played`;
- `drain_bank`;
- `bauble_draws`;
- `remora_age`, `remora_upkeep_pending`;
- `saga3_pending`;
- `ring_counters`;
- `ftt_level`;
- `uthros_counters`;
- `urza`;
- Reality Chip attachment state and target;
- `spell_cast_this_turn`;
- Power Artifact target;
- `vfc_pumps`;
- commander zone/tax state;
- terminal `won` status.

`spell_cast_this_turn` is a useful example of history that **must** remain Markov
state: FTT level 2 makes it affect future legal top access.

### Replace

`library` is replaced by the non-clairvoyant library-belief/information projection.

### Exclude from base `V_win_by_horizon`

- `rng_root_seed`: concrete random tape, not expected-value identity;
- `trace`: replay text;
- `construct`: legacy compatibility flag;
- `top_access`: legacy/unused compatibility flag.

The last two decisions were made only after reviewing the static usage report.

#### `construct`

The field is written when Urza is cast, but current legality/rules code does not
read `State.construct`. The actual Construct token exists in `battlefield` and its
`mode="construct"` representation is what artifact/creature/tutor/sacrifice logic
uses. Therefore `State.construct` must not split base value states. We keep the
field for compatibility until a separate cleanup patch proves it can be deleted
without breaking external/reporting contracts.

#### `top_access`

The usage report showed no runtime writes and no rule/legality reads beyond state
/key machinery. Actual top access is determined by Reality Chip and Fortune
Teller's Talent state. Therefore this field must not split base value states. It
also remains in `State`/`PolicyView` temporarily for compatibility rather than
being deleted during the audit.

### Objective-specific memory / analytics

Preserve but do not place in the base scalar value key:

- `urza_cast_turn`;
- `interaction_seen`;
- `win_family`.

For path-dependent objectives, add only the **minimal sufficient objective memory**
rather than reintroducing full history. Examples:

- `P(interaction seen by T3)`: seen/not-seen or required type/count summary;
- protected-win objectives: current protection availability is mostly derivable
  from current hand/battlefield/mana, while historical seen-but-spent interaction
  remains episode analytics;
- first-Urza-turn distribution: objective accumulator/outcome statistic;
- win-family distribution: terminal reward/category rather than live-state family
  history.

This is why the separate interaction analytics foundation remains valuable without
forcing `interaction_seen` into every `V(s)` cache key.

## Terminal state

`won` remains part of strategic identity because it changes terminal semantics and
legal continuation. `win_family` does not: scalar win probability only needs to
know that the state is terminal-winning, not which combo label produced it.

## Permanent identity

Strategic permanent identity retains:

- `name`;
- `tapped`;
- `sick`;
- `counters`;
- `mode`;
- `knack_granted`;
- `producer_urza_ready`.

`producer_urza_ready` is particularly important. It is an engine compression
resource representing a still-refundable producer `+U`; it changes which native or
Knack/Helix action remains available. The strategic key must distinguish it even
though legacy Oracle `State.key()` handles the credit through dominance behavior.

Permanent strategic identity excludes:

- `knack_source`: provenance only;
- `instance_tag`: ephemeral macro object identity.

## Policy observation

Exact unknown library order and `rng_root_seed` are never policy-visible.
`InformationState` carries legal hidden-zone knowledge instead.

The audit currently leaves `construct` and `top_access` in `PolicyView` for
backward compatibility even though they are excluded from base value identity.
Before production policy learning/DP uses `PolicyView.key()` as policy identity, we
should remove or normalize those redundant fields there as a separate architecture
cleanup. That cleanup is not required to change Oracle behavior.

`producer_urza_ready` remains engine-derived policy state because it represents a
real strategic option created by the Oracle compression.

## Static usage report conclusion

The reviewed report contained 33 `State` fields and 9 `Perm` fields, with no
completely unmentioned fields. The low-usage signals prompted focused source
tracing rather than automatic deletion.

Conclusions:

- `top_access`: no rules read / no runtime write -> exclude from base value key;
- `construct`: writes but no rules read; battlefield token is authoritative ->
  exclude from base value key;
- `urza_cast_turn`: analytics only -> objective-specific;
- `interaction_seen`: analytics/reward history -> objective-specific;
- `rng_root_seed`: concrete stochastic coordinate -> exclude from expected value;
- all other low-frequency legality/resource fields remain retained unless a later
  equivalence proof says otherwise.

## What this branch deliberately does not do

This audit branch does **not**:

- change `State.key()`;
- change `canonical_true_state_key()`;
- change `canonical_markov_state_key()`;
- add `canonical_strategic_state_key()`;
- change Oracle action generation or pruning;
- wire V/Q memoization into production search.

## Next patch

After this audit passes, implement a seed-independent strategic projection with a
library belief key. Then instrument current search/rollouts **without changing
search decisions** to measure:

- raw generated states;
- concrete Markov unique states;
- strategic-value unique states;
- collapse/merge ratio;
- estimated V/Q cache hit rate by turn/depth.

Only after those measurements should memoized values begin influencing production
policy/search behavior.
