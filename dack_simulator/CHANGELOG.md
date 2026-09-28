# Changelog

## v0.65-instrumentation
- No game-rule changes from validated v0.64 engine.
- Added deterministic sharded target-vs-Plains mana/infrastructure screen.
- Added raw future/seat-class CSV logging.
- Added per-context paired CSV metrics and feature counts.
- Added exact shard pooling/deduplication and card-level SE/CI summary.
- Added 99-card and 60-target manifests with functional role tags.

## v0.64-engine
See `docs/DACK_v0_64_REPAIR_AND_LAND_AUDIT.md`.

### Repository packaging fix
- `scripts/dack_v065_sharded_mana_screen.py` now resolves the validated v0.64 engine from `src/` in the Git-ready layout, with a fallback for older flat checkpoints.
- Repo-layout smoke test and v0.64 self-test both pass after the fix.
