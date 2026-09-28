# DACK data-lake schema

## Identity hierarchy
- `experiment_id`: one estimand + one compatible engine/deck/search configuration.
- `task_id`: `experiment_id + replicate + target_index`; globally unique within the experiment.
- `context_id`: engine runner's context identifier, retained for traceability.
- `future_index` and `seat_class`: nested outcomes within a context.

## Independence
For the current screen, independent opening-hand contexts are the primary statistical units. Future/seat rows nested inside a context are retained for diagnosis and weighted outcome construction, not counted as independent hands.

## Required provenance
Every completed task records:
- exact engine filename and SHA-256
- exact runner SHA-256
- exact canonical deck SHA-256
- experiment type
- target and control cards
- target index and replicate
- beam
- future samples per context
- seed namespace
- runtime/status

## Pooling guard
The pooler refuses to combine task manifests with different engine SHA, deck SHA, beam, sample count, or seed namespace inside one experiment output.

## Card swaps
A future `deck_swap` experiment will compare complete 99-card configurations under common random numbers. It will be a different estimand from the current forced-opening-slot screen and therefore gets a different experiment ID/table slice.