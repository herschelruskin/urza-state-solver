# DACK data-lake schema v2

## Scope
This schema is for the reproducible v0.72 `conditional_forced_opening_slot` experiment family. It is distinct from future full-99 `deck_swap`, land-count, tutor-policy, or other estimands.

## Identity hierarchy
- `experiment_id`: one estimand plus one compatible engine/deck/search configuration.
- `task_id`: `experiment_id + replicate + target_index`; globally unique within the experiment.
- `replicate`: independent opening-hand context index for that target.
- `context_id`: lower-level runner context identifier retained for traceability.
- `future_index` and `seat_class`: nested outcomes inside one independent context.

Independent opening-hand contexts are the primary statistical units. Future/seat rows are retained for weighted outcome construction and diagnosis; they are not counted as independent hands.

## Required task provenance
Every task manifest records:
- data-lake schema version;
- experiment ID/type and comparison;
- target/control card, target index, replicate, shard ID;
- beam, future samples per context, seed namespace;
- frozen engine version, solver filename, solver SHA-256;
- frozen production-config filename and SHA-256;
- canonical deck SHA-256 and deck size;
- statistical runner filename and SHA-256;
- atomic microtask-runner filename and SHA-256;
- status, runtime, row counts;
- on completion, SHA-256 for context CSV, trial CSV, and lower-level runner manifest.

## Atomic task/restart rules
One task is one target x one replicate x one opening-hand context. A task writes only inside its own task directory.

- If no manifest exists, the task starts normally.
- If an incomplete manifest exists and its identity/provenance exactly matches the requested task, only that task's partial runner outputs may be cleaned and rerun.
- If a completed manifest exists and output hashes/row counts validate, rerunning returns `complete_existing` and writes nothing.
- If an existing task ID has conflicting provenance (solver/config/deck/runner/beam/samples/seed/etc.), the microtask runner refuses to overwrite it.
- A completed task whose recorded outputs fail integrity checks is a hard failure, not an automatic overwrite.

## Pooling compatibility guard
The v0.72 atomic pooler recursively discovers task manifests and pools only `status=complete` tasks.

All completed tasks in one pool must match exactly on:
- schema version;
- experiment ID/type/comparison;
- engine version and solver SHA;
- production-config SHA;
- deck SHA;
- statistical-runner SHA;
- microtask-runner SHA;
- beam;
- samples per context;
- seed namespace.

Any incompatible completed task aborts pooling. Timeout/failed/incomplete tasks are counted in pool provenance but contribute no statistical rows.

## Pooled outputs
- `pooled_contexts.csv`: one row per completed independent context, augmented with task/engine/config/runner provenance.
- `pooled_trials.csv`: nested future/seat rows, also provenance-augmented.
- `pooled_summary_by_card.csv`: context-level card summaries and uncertainty.
- `pooled_task_index.csv`: one row per included atomic task with compatibility identity and manifest SHA.
- `pool_manifest.json`: compatibility signature, discovered/completed status counts, row counts, and hashes of pooled outputs.

Pooling is deterministic for an unchanged set of completed task files.

## Future experiment families
A full card-for-card deck replacement uses a different experiment type such as `deck_swap` and a separate experiment ID/table slice. Land-count sweeps and policy changes likewise use distinct experiment IDs/configuration hashes. Their rows must never be silently merged with forced-opening-slot results.
