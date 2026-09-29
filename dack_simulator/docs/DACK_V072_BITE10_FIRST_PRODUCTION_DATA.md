# DACK v0.72 Bite 10 — first permanent production data

Status: **production data collection started successfully**.

## Experiment lock

- Experiment ID: `mana_vs_plains_v072_b240_s1`
- Experiment type: `conditional_forced_opening_slot`
- Comparison: target vs Plains
- Engine: v0.72 production
- Solver SHA-256: `abba6f0baa7bedfb0b248bdd62501dae10157ba90bd5a3952fbeffbdcca48a7a`
- Production-config SHA-256: `4d639e67262266a4067073e682e8e8cb9546ba0b136c2ba831dc3fa570cebab3`
- Statistical runner SHA-256: `93ed23ac1a63e2ae4acd60d77ba09c7023df7c0cbbc1acdc2330b72e39a3b23f`
- Atomic microtask runner SHA-256: `d040e5ee2d40ac17be53ae017e814f00ab815c0ee38ad9a5abaa5456e0c84ec0`
- Atomic pooler SHA-256: `1514c91a1e8b33d03ab9564c28160b25301bbdc99f5595d79b4ccd202e7ea303`
- Canonical deck SHA-256: `6c19aebc8dafd0f21897e7670be1c1c18ae94211470538609fcdfe1a2496c54c`
- Beam: 240
- Samples/context: 1
- Seed namespace: `7202401001`
- Independent unit: one opening-hand context
- Initial equal-N goal: 25 contexts/target
- Experiment-config SHA-256: `e01f73ef1500bb28d2c88bb2a3fd78f5ce23e7a34fa0eed34da61799c80e1037`

The experiment config was committed before any production row was generated.

## First permanent microbatch

Replicate 0 completed for target indices 0–4:

1. Ancient Den
2. Ancient Tomb
3. Cavern of Souls
4. City of Brass
5. City of Traitors

All five tasks completed with `status=complete`.

Each task directory was persisted immediately to:

`/DACK simulator/data_lake/mana_vs_plains_v072_b240_s1/tasks/<task_id>/`

before additional tasks were started.

## First pooled snapshot

Five complete tasks pooled to:

- independent context rows: **5**
- nested trial rows: **6**
- summary cards: **5**
- incompatible tasks: **0**

Pool hashes:

- `pooled_contexts.csv`: `0ad4433051687e76d260ac21961f9c66562db5389266fd2cd2fdee7f6b39f3c1`
- `pooled_trials.csv`: `82475de467f23aefa9812a698f80f622d94bee2ffeedc5ce355e1b2395189a34`
- `pooled_summary_by_card.csv`: `4b3c6d9bfef776b669aa6a0d9ecb622ff483b46fa5bcefeb2f643b810623398b`
- `pooled_task_index.csv`: `1b04d65b16d5b33a4f717be066d9757f9868b1c6bbc58f4406921b9d6172b187`
- `pool_manifest.json`: `fda7067c000641e47c612ea946bf5f131bbe6472e3f92dc185f18e0763d17a01`

Persistent pool path:

`/DACK simulator/data_lake/mana_vs_plains_v072_b240_s1/pool/`

## Durability/rebuild proof

A second workspace was built from the **Library-persisted task files only**. No live task
files from the original execution directory were used.

The atomic pooler was rerun on that reconstructed task tree.

Result: all five pooled artifacts were **byte-for-byte identical** to the live-runtime pool,
including `pool_manifest.json`.

This proves the production dataset can be reconstructed after a chat/container reset from
the persistent Library data lake.

## Statistical interpretation

This Bite-10 microbatch is a persistence/provenance milestone, not an inferential result.
Every tested card currently has only N=1 independent context, so no card ranking/cut
conclusion should be drawn from this snapshot.

## Next collection step

Continue replicate 0 across target indices 5–59 in small atomic batches. After each small
batch:
1. persist completed task directories to the Library;
2. leave timeout/failed tasks as explicit provenance;
3. rerun the deterministic pooler;
4. persist the refreshed pool snapshot.

After all 60 targets have N=1, continue equal-N replicate sweeps toward N=25 before adaptive
extension of ambiguous/decision-relevant cards.
