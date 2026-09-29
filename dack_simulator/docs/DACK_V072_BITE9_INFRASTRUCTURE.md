# DACK v0.72 Bite 9 — atomic production data-lake infrastructure

Status: **validated infrastructure checkpoint; no production inference run performed**.

## Frozen engine/config
- Solver: `src/dack_t3_solver_v0_72_frontier_dominance.py`
- Solver SHA-256: `abba6f0baa7bedfb0b248bdd62501dae10157ba90bd5a3952fbeffbdcca48a7a`
- Production config: `config/v072_production_engine.json`
- Production-config SHA-256: `4d639e67262266a4067073e682e8e8cb9546ba0b136c2ba831dc3fa570cebab3`
- Production beam: 240
- Canonical deck SHA-256 observed by the runner: `6c19aebc8dafd0f21897e7670be1c1c18ae94211470538609fcdfe1a2496c54c`

## Bite-9 production infrastructure
- Statistical runner: `scripts/dack_v072_sharded_mana_screen.py`
  - SHA-256: `93ed23ac1a63e2ae4acd60d77ba09c7023df7c0cbbc1acdc2330b72e39a3b23f`
- Atomic microtask runner: `scripts/dack_v072_microtask.py`
  - SHA-256: `d040e5ee2d40ac17be53ae017e814f00ab815c0ee38ad9a5abaa5456e0c84ec0`
- Atomic pooler: `scripts/pool_dack_v072_atomic.py`
  - SHA-256: `1514c91a1e8b33d03ab9564c28160b25301bbdc99f5595d79b4ccd202e7ea303`

The runner still exposes exactly 60 targets: 26 land-access targets and 34 infrastructure targets.

## Smoke test
Experiment ID: `bite9_smoke_v072`

Three completed atomic tasks were produced:
1. Ancient Den, replicate 0
2. Ancient Tomb, replicate 0
3. Ancient Den, replicate 1

Each completed task contained exactly one context row and one trial row at samples=1 / beam=240.

### Completed-task restart
Ancient Den replicate 0 was rerun with identical identity.
- Result: `complete_existing`
- context/trial/runner-manifest/task-manifest hashes before vs after: byte-identical

### Interrupted-task recovery
Ancient Den replicate 1 was first forced to `timeout` with a 0.01 s child timeout.
- timeout manifest persisted with zero completed rows;
- rerunning the same identity with a normal timeout cleaned only that incomplete task;
- final status: `complete`, one context row, one trial row.

### Pooling
The three completed tasks pooled to:
- 3 context rows
- 3 trial rows
- 2 summary cards
- Ancient Den N=2
- Ancient Tomb N=1

Pooled output hashes:
- contexts: `df2c69b4a24beeb9abdf6ca77393f4895991932aa4cea3e46d614869fdd76738`
- trials: `c1128bb267671b48934b444113798ac1e7bfd91fb716cb6df5f6b56f245c6c0c`
- summary: `2f7393f79e079a85e78cb876d995ad66e7d3b08d97e786c809af94a8af959c14`
- task index: `8a99b356db40fb326bb8e14916b4aed06a3b2b34a49f97971751679b0dba1ac2`
- pool manifest: `325970dc6444eb1860c5be210588a3fd959d562f0c0944397882aec4723e58ae`

Rerunning the pool on the unchanged task set reproduced all five hashes exactly.

## Negative safety tests
### Conflicting task identity
The completed Ancient Den replicate-0 task was requested again with a different seed namespace.
- runner exit: nonzero
- message: existing task identity/provenance conflicts; refusing overwrite
- all pre-existing task file hashes remained unchanged.

### Incompatible pool member
A copied completed manifest was deliberately changed from beam 240 to beam 241.
- pooler exit: nonzero
- incompatibility was identified as `beam: (240, 241)`
- no mixed pool was produced.

## Infrastructure changes relative to v0.71
1. Statistical runner imports the frozen v0.72 production solver.
2. Every task manifest carries solver, production-config, deck, statistical-runner, and microtask-runner hashes.
3. Completed-task restart validates recorded output hashes and performs no writes.
4. Conflicting task identities are protected against overwrite.
5. Incomplete same-identity tasks can be retried atomically.
6. Pooler recursively discovers nested atomic task directories.
7. Compatibility guards stated in the schema are now actually enforced.
8. Pooled rows carry task/engine/config provenance for later mining.
9. Pooling is deterministic for a fixed task set.

## Production status
Bite 9 validates the infrastructure only. The smoke rows are not part of the scientific production pool.

The next step may begin the permanent v0.72 data lake using small atomic tasks and periodic deterministic pooling. Production experiment IDs/seeds should be distinct from `bite9_smoke_v072`.
