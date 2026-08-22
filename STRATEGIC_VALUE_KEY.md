# Strategic Value-Key Foundation

This patch implements the first seed-independent identity intended for future
`V(s)` / `Q(s,a)` memoization. It is deliberately **instrumentation-only**:
Oracle rules, legal actions, pruning, beam search and winners are unchanged.

## Why this is separate from existing keys

The repository now has three intentionally different identities:

1. **Replay / true identity** — conservative exact state and provenance.
2. **Concrete Markov identity** — deterministic sampled-world transition identity,
   including exact hidden library order and `rng_root_seed`.
3. **Strategic expected-value identity** — legal-information state whose expected
   future reward can be shared across Monte-Carlo worlds and equivalent histories.

`canonical_markov_state_key()` remains the concrete transition key. The new
`canonical_strategic_state_key()` must not replace it in the RNG implementation.

## LibraryBeliefKey

Exact hidden order is replaced by:

- the remaining library card-count multiset;
- legally known top cards in order;
- legally known bottom constraints/order;
- any additional `InformationState.known_library_counts` facts.

This retains the information needed by a legal-information policy without
allowing the value function to condition on the Oracle's exact unknown order.

`shuffle_epoch` is intentionally omitted from the value key. Once current hidden-
zone knowledge is the same, the number of previous shuffles is provenance rather
than a predictor of future value. `InformationState.after_shuffle()` still clears
stale known-top/bottom information; the epoch remains available for replay and
knowledge-management bookkeeping.

## StrategicValueState

The base `P(win by horizon)` projection retains all current rules/resources found
necessary by the completed field audit:

- turn/horizon coordinate;
- hand, graveyard and exile multisets;
- canonical battlefield permanent state;
- floating mana and land-play status;
- delayed Mana Drain/Bauble resources;
- Remora/Saga pending state;
- Ring/FTT/Uthros state;
- Urza current availability;
- Reality Chip/Power Artifact attachment state;
- `spell_cast_this_turn` and current-turn Valley Floodcaller pumps;
- commander zone/tax state;
- terminal `won` status.

It intentionally omits:

- `rng_root_seed`;
- `trace`;
- legacy redundant `construct` and `top_access` flags;
- `urza_cast_turn`, `interaction_seen`, and `win_family` from the base objective.

Permanent identity uses `PublicPermanent`, which keeps
`producer_urza_ready`/`knack_granted` but drops `knack_source`/`instance_tag`.

## Objective-specific memory

Path-dependent objectives should not force all analytics history into every base
state. `objective_memory` is an explicit extension point for the minimal
sufficient statistic required by a selected objective, for example:

```text
("interaction_seen_by_t3", True)
("first_urza_turn_bucket", 2)
```

The cache namespace should still include objective ID/horizon/policy as already
specified by `MemoizationStore`; objective memory captures only path state that is
actually needed to evaluate future reward.

## StrategicKeyProfiler

`StrategicKeyProfiler` is a decision-neutral measurement helper. Supplying states
and their `InformationState` records:

- total observations;
- unique concrete Markov keys;
- unique strategic value keys;
- concrete-to-strategic collapse fraction;
- estimated strategic-cache hit fraction;
- the same metrics by turn;
- the same metrics by turn and action depth when callers provide `depth`.

It does **not** prune, merge, replace or score solver states.

## First real-search measurement harness

`strategic_collapse_profile.py` replays the validated Oracle search mechanics in a
separate diagnostic module. It imports and uses the production implementations of:

- `legal_actions()`;
- `State.key()` exact-state merging;
- `dominance_prune()`;
- `score()`/beam selection;
- `end_turn_frontier()` and pending-upkeep closure.

The only added behavior is observing generated candidate states before exact-state
merging. `urza_solver.py` itself is not modified.

For reproducibility, the harness uses `oracle_mulligan_deals()` and profiles the
exact **7A** opening candidate for each requested seed, including the fixed
Gemstone Caverns seating result. Mulligan-stage branching is deliberately excluded
from this first measurement so the result focuses on the in-game state graph.

### Critical interpretation limit

The current Oracle engine still does not propagate a legal `InformationState`.
Therefore the first measurement calls the strategic projector with an **empty
`InformationState` at every observation**.

That means the reported collapse is an **upper-bound collapse potential**, not a
final DP-cache hit rate. It correctly removes hidden exact library order, but it
also temporarily forgets legally acquired top/bottom/count knowledge from effects
such as tutors, scry, and top inspection. Once real information-state propagation
exists, some states currently merged by this diagnostic will correctly separate.

For that reason the JSON output labels itself:

```text
measurement_kind = strategic-collapse-potential
decision_neutral = true
search_scope = Oracle 7A opening candidate only; no mulligan branching
```

and includes the information-assumption warning verbatim.

## Running the measurement

A useful first fixed-seed run is:

```powershell
$env:PYTHONHASHSEED='0'
py -3 strategic_collapse_profile.py --seed 20260821 --count 5 --turns 4 --beam 500 --depth 40 --action-cap 80
```

The harness writes `strategic_collapse_profile.json` by default and prints per-seed
plus aggregate collapse/candidate-hit metrics. The JSON includes `by_turn` and
`by_turn_depth` tables for locating where most duplicate strategic states arise.

Start with this moderate diagnostic configuration before trying production-size
beam/depth settings; the goal is to characterize state collapse, not benchmark the
final Oracle throughput.

## Important scope limits

The current belief representation assumes the fixed known decklist model: the
remaining card multiset is legally inferable even though order is unknown. A
future opponent/deck-uncertainty model would need a richer probability distribution
rather than this exact remaining-count representation.

Pregame/mulligan-specific information such as whether Gemstone Caverns is live is
not encoded here. That belongs in the mulligan/pregame policy context until the
post-pregame game state fully represents its consequences.
