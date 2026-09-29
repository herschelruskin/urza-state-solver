# DACK v0.72 Bite 10 — first permanent production batch

Status: **permanent production data started**.

## Experiment
- experiment ID: `mana_vs_plains_v072_b240_s1_prod`
- experiment type: `conditional_forced_opening_slot`
- comparison: target vs Plains
- solver SHA-256: `abba6f0baa7bedfb0b248bdd62501dae10157ba90bd5a3952fbeffbdcca48a7a`
- production engine config SHA-256: `4d639e67262266a4067073e682e8e8cb9546ba0b136c2ba831dc3fa570cebab3`
- runner SHA-256: `93ed23ac1a63e2ae4acd60d77ba09c7023df7c0cbbc1acdc2330b72e39a3b23f`
- microtask runner SHA-256: `d040e5ee2d40ac17be53ae017e814f00ab815c0ee38ad9a5abaa5456e0c84ec0`
- beam: 240
- samples/context: 1
- seed namespace: 72025001
- intended first equal-N milestone: 25 independent contexts per target

## Bite-10 permanent wave
Replicate 0 was completed for canonical target indices 0–9:
1. Ancient Den
2. Ancient Tomb
3. Cavern of Souls
4. City of Brass
5. City of Traitors
6. Command Beacon
7. Crystal Vein
8. Eiganjo, Seat of the Empire
9. Gemstone Caverns
10. Gemstone Mine

All 10 atomic tasks completed successfully; there were no timeouts or failed tasks.

Pool result:
- complete tasks: **10**
- independent context rows: **10**
- nested trial rows: **12**
- represented cards: **10**
- deterministic pool rerun: **byte-identical**

Pool hashes:
- pooled contexts: `82763e6cc836e9798b4eed47fb6897332908a709790734387e0225446999bcf7`
- pooled trials: `d091db8d1c3fce47215fd93b31c178adc0d2c7fe49f052de3d3482757c6a3e51`
- pooled task index: `24e9e7ea281a6b622912d4c424a7c1db9cf3fb0852297586de83b8c10bde8f0a`
- pooled summary: `5608dd793a971a3658b61dba27218ec41d21cc4b2c2c241e054d370153c625fa`
- pool manifest: `7177383601aa895abfc4a8fe914c40b1f0a19bac2a2c066db9f882ee3473ccbf`

## N=1 interpretation
All ten first contexts happened to tie their Plains controls. Raw opening hands and raw win-turn rows were checked and the target/control slots differ correctly; this is not a pooling/identity bug. N=1 per card is not inferential and no card conclusion should be drawn from this batch.

## Persistence
The complete raw task tree, experiment config, pooled outputs, and checkpoint manifest are persisted as:
`/DACK simulator/production_data/v072/DACK_v072_production_bite10_rep0_t00_t09.zip`

Snapshot SHA-256:
`ff6f18e88eb62800c22729e6d8dc31792fae9f7310fc0aae75534da3704b9413`

Checkpoint manifest SHA-256:
`9fb10ab111bf3073c736ebc5e9791dd151e40e7386bbd0f484348b32d21163f1`

These rows are permanent production data. Bite-9 smoke rows are not included.

## Next
Continue replicate 0 across target indices 10–59 in similarly small recoverable batches, periodically snapshotting and deterministically pooling. After all 60 targets have N=1, continue equal-N replicates toward N=25 before adaptive extension.
