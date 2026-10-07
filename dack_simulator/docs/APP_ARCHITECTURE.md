# DACK distributable application architecture

## Goal

Turn the research simulator into a stable local application where a user can load a
99-card deck, lock required cards, remove/add a fixed number of cards, compare legal
variants, reuse prior simulation work, and inspect uncertainty without managing Python
scripts or GitHub Actions.

The GUI is intentionally **not** the first layer.  The stable dependency direction is:

```
GUI
  -> application/service API
      -> scheduler + cache
          -> deterministic engine adapter
              -> validated solver
      -> SQLite result store
```

The existing solver experiments remain valid research artifacts.  They are not the
application database.

## Non-negotiable reproducibility rule

A simulation result is identified by:

```
deck_hash + engine_hash + policy_hash + seed block + outcome schema
```

The same identity must produce byte-identical primary outcomes regardless of worker,
process, machine, or scheduling order.  A disagreement is an engine/reproducibility
failure, not a second observation to average in.

The current compact-run reproducibility audit is therefore a release gate before the
legacy solver is connected to the app cache.

## Storage model

### Decks and configuration

Decks, policies, engines, experiments, and variant deltas are canonical JSON hashed with
SHA-256.  The UI can display names, but cache identity never depends on a filename.

### Primary game outcomes

The hot-path T1--T3 deployment outcome uses `outcome_u8_v1`:

- 2 bits seat
- 3 bits London keep size
- 2 bits win turn (0 = fail through T3)
- 1 reserved bit

That is exactly **one byte per game**.  A 4096-game result block is 4 KiB of outcome
payload.  Game ids/seeds are implicit from the block manifest instead of repeated on
every row.

### Traces

Hands, mulligan audits, and action traces are sparse side records, not normal production
rows.  Store them only for:

- discordant paired games,
- failed assertions / impossible states,
- explicit audit samples,
- user-requested replay.

Every compact result can be deterministically replayed from its content key and game
offset once the engine passes the reproducibility gate.

### SQLite first

SQLite is the distribution target because it is embedded, transactional, portable, and
requires no server.  WAL mode allows the GUI to read while workers commit completed
blocks.  Later analytics can export to DuckDB/Parquet without changing canonical ids.

## Cache behavior

The GUI should never think in terms of "run this N again."  It asks for coverage.

Example: if a deck/config already contains seed games 0--4095 and the user requests
N=8192, the scheduler computes only 4096--8191.  If a user returns to a deck six months
later with the same engine/policy, the existing blocks are reused automatically.

Completed result blocks are immutable.  A second computation of the same content key is
accepted only if the bytes match exactly.

## Worker/scheduler direction

GitHub Actions is useful for development but should not be the end-user execution model.

The application scheduler will:

1. expand a user comparison into legal deck variants;
2. query cached coverage;
3. split missing coverage into modest seed blocks;
4. run a bounded local worker pool;
5. commit each completed block atomically;
6. retry an interrupted block without invalidating completed work;
7. calculate paired summaries from common seed coverage.

For broad searches, staged allocation is the default:

- cheap discovery (e.g. N=64/128),
- promote plausible variants to N=512,
- promote close finalists to N=1024+,
- spend N=4096 only where the decision remains sensitive.

This is compute allocation, not a change in estimand.

## GUI target

A first useful GUI can expose:

- **Current deck** panel with lock icons.
- **Candidate pool** with search and card categories.
- **Change tray** enforcing equal add/remove counts and 99-card legality.
- **Run** controls: sample target, objective, trace policy.
- **Results**: T1, <=T2, <=T3, utility, paired confidence intervals, mean keep, and
  faster/slower discordant counts.
- **Cache status**: already-computed N and incremental work required.
- **Replay** button for selected discordant games.

The GUI must call an application API; it must not import mutable experiment scripts.

## Distribution milestones

### M0 — reproducibility gate
Eliminate hash/set/process-order dependence and establish regression fixtures.

### M1 — application foundation (current branch)
Package metadata, canonical ids, compact outcome codec, SQLite content-addressed store,
cache coverage queries, sparse trace table, and smoke tests.

### M2 — engine adapter
Wrap one validated solver version behind a narrow API:
`simulate(deck, policy, game_ids) -> outcomes`.

### M3 — local scheduler
Resumable seed blocks, bounded multiprocessing, progress reporting, cancellation, and
adaptive N promotion.

### M4 — GUI
Start with a local web UI or lightweight desktop shell against the same service API.
The storage/scheduler layer remains UI-agnostic.

### M5 — distributable builds
Versioned application database migrations, packaged card/rules registry, signed desktop
or standalone builds, import/export bundles, and automated regression tests.
