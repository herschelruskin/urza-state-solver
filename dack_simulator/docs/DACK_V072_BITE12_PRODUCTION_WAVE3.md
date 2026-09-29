# DACK v0.72 Bite 12 — permanent production wave 3

Status: **permanent production dataset expanded to 30/60 targets**.

## Experiment
- Experiment ID: `mana_vs_plains_v072_b240_s1_prod1`
- Frozen solver SHA-256: `abba6f0baa7bedfb0b248bdd62501dae10157ba90bd5a3952fbeffbdcca48a7a`
- Beam: **240**
- Future samples/context: **1**
- Seed namespace: `7202401001`
- Primary statistical unit: independent opening-hand context
- Initial equal-N goal: 25 contexts per target

No engine, deck, runner, beam, sample-count, or seed-namespace change was made in Bite 12.

## Wave 3 additions

Target indices 20-29, replicate 0:

1. The Mycosynth Gardens
2. Untaidake, the Cloud Keeper
3. Urza's Cave
4. Urza's Saga
5. Emeria's Call
6. Razorgrass Ambush
7. Arcane Signet
8. Basalt Monolith
9. Brainstone
10. Candelabra of Tawnos

All **10/10 new atomic tasks completed successfully**. Brainstone was run in isolation because
of its previous pathological validation context, but this production context completed normally
in about 8.7 seconds; no timeout recovery was needed.

## Combined permanent pool

Bites 10-12:
- complete atomic tasks: **30**
- independent context rows: **30**
- future/seat rows: **32**
- represented targets: **30/60**

All completed manifests share one exact compatibility signature:
- solver SHA: `abba6f0baa7bedfb0b248bdd62501dae10157ba90bd5a3952fbeffbdcca48a7a`
- production-config SHA: `4d639e67262266a4067073e682e8e8cb9546ba0b136c2ba831dc3fa570cebab3`
- deck SHA: `6c19aebc8dafd0f21897e7670be1c1c18ae94211470538609fcdfe1a2496c54c`
- statistical-runner SHA: `93ed23ac1a63e2ae4acd60d77ba09c7023df7c0cbbc1acdc2330b72e39a3b23f`
- microtask-runner SHA: `d040e5ee2d40ac17be53ae017e814f00ab815c0ee38ad9a5abaa5456e0c84ec0`
- beam 240 / samples 1 / seed base 7202401001.

The strict rainbow-land checks represented in the permanent pool remain clean:
- City of Brass vs Plains: tied in its current context
- Mana Confluence vs Plains: tied in its current context
- Tarnished Citadel vs Plains: tied in its current context

## Persistence

Full 30-task raw archive:
- Library: `/DACK simulator/production/mana_vs_plains_v072_b240_s1_prod1/checkpoints/bite12_wave3_raw.zip`
- SHA-256: `e671f3b8d6b748c0aacc558d7964e44684125e59fa0a931e9202e7440a63f73e`

The persistent `latest/` pool has been replaced with the 30-context version.

Hashes:
- pooled contexts: `231d10e3de9ae21947bbdda17c0a5501e94b92ce56fa51b35278eed8907c1187`
- pooled trials: `3e450d97e7fcce6f6efb2636664578dbd3f7b701ffbdc4ce01dca2c0ea215b67`
- pooled summary: `979f3c6c63f7d0b5f0faef868e86000193e138b5518bee3497058f3757f90a2e`
- pooled task index: `8155bd8810f3498cf157bce9452a54d58201a0037e2d2db2def775051729034a`
- pool manifest: `dc62aaafcccf3f1cf529a06776205f23a4605d4713b572606d3201b902ab1304`

All persisted copies were re-materialized after upload and matched these hashes exactly.

## Annotation v1 regeneration

The canonical annotation table is unchanged:
- annotation SHA: `f9568316be8c93874e77e3ef41c682fd3200ad701b77197e2ca012378639fa63`

The v1 derived view was regenerated over the new 30-row source pool:
- rows: **30**
- source pool SHA: `231d10e3de9ae21947bbdda17c0a5501e94b92ce56fa51b35278eed8907c1187`
- derived SHA: `89ea2c5e5c428fefdcea18019becf4eb0995803434af5faf48b4a7a07fd5fc91`
- Library: `/DACK simulator/production/mana_vs_plains_v072_b240_s1_prod1/derived/v1/pooled_contexts_annotated_v1.csv`

This remains analysis metadata only and does not affect production task compatibility.

## Interpretation

This is still **N=1 for 30 targets**, so it is not appropriate for stable rankings or cut
decisions yet.

## Next

Bite 13 should add target indices **30-39** at replicate 0, rebuild/checkpoint the 40-target
pool, and regenerate the same annotation-v1 derived view.
