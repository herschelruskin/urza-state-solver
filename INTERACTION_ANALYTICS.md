# Interaction / Protection Analytics Foundation

The simulator should preserve interaction as a first-class research output without
putting historical reporting fields into the Markov/DP transition key.

## Separation of concerns

`interaction_analytics.py` is observational. It does not execute Magic rules and
it does not modify `State`. A rollout/search supplies successive states to an
`InteractionEpisodeTracker`; the tracker records analytics outside the strategic
state used for transpositions.

This lets two physically identical future positions share `V(s)` even if one
trajectory saw a counterspell earlier, while still preserving that earlier
interaction exposure in the episode result.

## Card classes

The initial taxonomy records:

- `counterspell`
- `broad_counter`
- `narrow_counter`
- `free_counter_own_turn`
- `conditional_free_counter`
- `bounce`
- `proactive_protection`
- `free_spell_lock`
- `proactive_disruption`
- `stax_hate`

The classes are analytical labels, not replacements for rules text.

Important examples:

- Force of Will / Fierce Guardianship / Pact of Negation are broad own-turn free
  protection only when their actual alternate-cost conditions are live.
- Force of Negation is *not* treated as free protection on our own combo turn.
- Mindbreak Trap's free condition is not assumed without an opponent spell-count
  model.
- Defense Grid is tracked separately as proactive protection.
- Vexing Bauble is tracked as a free-spell lock and also suppresses our own
  no-mana-spent counter protection while it remains online.
- Disruptor Flute is proactive disruption, but is not automatically counted as a
  generic protected combo line because the named opposing card is not yet modeled.

## Snapshot metrics

For any current state, `interaction_snapshot()` records:

- unique interaction cards seen so far;
- count by interaction class;
- interaction currently in hand;
- interaction currently on the battlefield;
- counterspells in hand;
- counterspells actually representable as castable on our turn;
- broad castable counters;
- zero-current-mana counters;
- Defense Grid / proactive protection online;
- Vexing Bauble / free-spell lock online;
- proactive disruption online;
- a raw protection-piece count;
- a conservative `protected_line_capable` flag.

`protection_piece_count_available` is intentionally **not** called independent
protection layers. For example, two one-mana counters with only one blue mana are
two available cards/options but not necessarily two sequential stack exchanges.
Exact layer counting belongs to the future opponent/stack interaction model.

## Episode metrics

`InteractionEpisodeTracker` additionally records:

- first turn each interaction card was seen;
- first turn each interaction class was seen;
- total unique interaction seen;
- terminal/winning interaction snapshot;
- whether a winning line had any represented protection available;
- whether a winning line had a counterspell available;
- whether a broad counter was available;
- whether zero-current-mana protection was available;
- whether Defense Grid was online;
- whether a free-spell lock was online.

The tracker must observe the rollout as it advances if accurate first-seen turns
are required. A terminal state alone cannot reconstruct when a historical card
was first encountered.

## Intended Monte-Carlo outputs

Once connected to rollouts, the same episode data can estimate quantities such as:

- `P(any counterspell seen by T2/T3)`
- `P(any interaction seen by T2/T3)`
- `P(counterspell available on the win turn)`
- `P(broad counter available on the win turn)`
- `P(zero-current-mana counter available on the win turn)`
- `P(Defense Grid online on the win turn)`
- `P(protected line | win)`
- `E[protection pieces available at win]`
- win-turn distributions conditional on protected vs unprotected lines.

These metrics are especially important for paired deck-swap experiments. A card
change that slightly improves raw goldfish speed but materially reduces protected
win rate should be visible rather than being mislabeled an unconditional upgrade.

## Scope boundary

This foundation does **not** yet claim a real probability that a combo survives
opposing interaction. That requires an explicit opponent/stack model describing
opponent holdings, target restrictions, priority, mana, and the number/order of
stack exchanges. The current output measures our represented defensive
capability, which is the correct prerequisite for that later model.
