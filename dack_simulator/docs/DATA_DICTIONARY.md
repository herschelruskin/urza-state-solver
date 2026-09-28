# Mana-screen CSV data dictionary

## `pooled_trials.csv`
Lowest retained outcome level. One row is a matched target/control result for one sampled future order and one rules-distinct seat class. `seat_weight=4` means all seats are equivalent; Gemstone Caverns contexts instead use starting weight 1 and nonstarting weight 3.

Important columns: `target_card`, `target_role`, `target_group`, `context_id`, `future_index`, `seat_class`, `seat_weight`, `target_win_turn`, `control_win_turn`, `target_wins_by_t2`, `control_wins_by_t2`, `target_wins_by_t3`, `control_wins_by_t3`, `future_seed`.

## `pooled_contexts.csv`
One row per target/context after aggregating its sampled futures/seats. Contains the exact six common cards, target/control hands, hand-composition features, target/control T1/T2/T3 distributions, <=T2/<=T3, balanced utility, and paired deltas.

This is the preferred table for card-level inferential summaries because contexts are the independent sampling units.

## `pooled_summary_by_card.csv`
Derived from pooled context rows. Contains N, mean paired deltas, standard error, approximate 95% CI, positive/negative/tie counts, and absolute target/control means.

## `card_manifest.csv`
All 99 deck slots with copy index, multiplicity, land/MDFC status, solver `RAMP_PROTECTED` membership, role tag, and whether that card is a matched-screen target.

## `target_manifest.csv`
Unique list of the 60 current screen targets and their role/control metadata.
