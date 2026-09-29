# DACK v0.72 Bite 11 — permanent production wave 2

Status: **permanent production dataset expanded to 20/60 targets**.

## Experiment
- Experiment ID: `mana_vs_plains_v072_b240_s1_prod1`
- Frozen solver SHA-256: `abba6f0baa7bedfb0b248bdd62501dae10157ba90bd5a3952fbeffbdcca48a7a`
- Beam: **240**
- Future samples/context: **1**
- Seed namespace: `7202401001`
- Primary statistical unit: independent opening-hand context
- Initial equal-N goal: 25 contexts per target

No engine, deck, runner, beam, sample-count, or seed-namespace change was made in Bite 11.

## Wave 2 additions

Target indices 10-19, replicate 0:

1. Great Hall of the Citadel
2. Mana Confluence
3. Mishra's Workshop
4. Remote Farm
5. Ruins of Trokair
6. Shefet Dunes
7. Spire of Industry
8. Starting Town
9. Talon Gates of Madara
10. Tarnished Citadel

All 10 new atomic tasks completed successfully. No timeout recovery was required in this wave.

## Combined permanent pool

Bite 10 + Bite 11:
- complete atomic tasks: **20**
- independent context rows: **20**
- future/seat rows: **22**
- represented targets: **20/60**

All 20 completed manifests have one exact compatibility signature:
- solver SHA: `abba6f0baa7bedfb0b248bdd62501dae10157ba90bd5a3952fbeffbdcca48a7a`
- production-config SHA: `4d639e67262266a4067073e682e8e8cb9546ba0b136c2ba831dc3fa570cebab3`
- deck SHA: `6c19aebc8dafd0f21897e7670be1c1c18ae94211470538609fcdfe1a2496c54c`
- statistical-runner SHA: `93ed23ac1a63e2ae4acd60d77ba09c7023df7c0cbbc1acdc2330b72e39a3b23f`
- microtask-runner SHA: `d040e5ee2d40ac17be53ae017e814f00ab815c0ee38ad9a5abaa5456e0c84ec0`
- beam 240 / samples 1 / seed base 7202401001.

The three strict rainbow-land checks represented in the current permanent pool remain clean:
- City of Brass vs Plains: tied in its current context
- Mana Confluence vs Plains: tied in its current context
- Tarnished Citadel vs Plains: tied in its current context

## Persistence

Full 20-task raw archive:
- Library: `/DACK simulator/production/mana_vs_plains_v072_b240_s1_prod1/checkpoints/bite11_wave2_raw.zip`
- SHA-256: `f853ba06f0c7456580129e240c10fa7aff05a82966a88c6aa2c19959c418ae6c`

The persistent `latest/` pool has been replaced with the 20-context version.

Hashes:
- pooled contexts: `39396f0a670db148b6451ca68b1e564bec016d0947d6f1b75158808e1f9cbe24`
- pooled trials: `b1803a39fc81f6cfc8aa612d5cc548239e3b6f3592e53709f4639b9c68822769`
- pooled summary: `abcbc6d486ae0b6c41c3cf566c0aa3e8e84f1427ef6084d2f315b60cbf3d9ed1`
- pooled task index: `79a511f335ffb17bb3bb060e0135d2d1e6116c1f2baf2e33465ccf22223120f6`
- pool manifest: `73aa77976dfe2b225938fe5c4c87740a17083b4d25cd9e0cf2c8fae493897ef5`

All persisted copies were re-materialized after upload and matched these hashes exactly.

## Interpretation

This remains **N=1 for only 20 targets**. It is not yet appropriate for ranking lands/cards, making cuts, or estimating stable effect sizes.

## Next

Bite 12 should add target indices 20-29 at replicate 0 under the same permanent experiment identity, then rebuild/checkpoint the 30-target pool.
