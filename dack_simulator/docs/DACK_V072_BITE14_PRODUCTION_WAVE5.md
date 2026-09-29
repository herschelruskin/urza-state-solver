# DACK v0.72 Bite 14 — permanent production wave 5

Status: **permanent production dataset expanded to 50/60 targets**.

Experiment remains frozen:
- ID: `mana_vs_plains_v072_b240_s1_prod1`
- solver SHA-256: `abba6f0baa7bedfb0b248bdd62501dae10157ba90bd5a3952fbeffbdcca48a7a`
- beam: 240
- samples/context: 1
- seed base: 7202401001

Wave 5 added target indices 40-49:
Jeweled Amulet, Kozilek's Command, Lion's Eye Diamond, Liquimetal Torque,
Lotus Petal, Loyal Tutor, Mana Vault, Manifold Key, Moonsilver Key, and Mox Diamond.

All 10 new atomic tasks completed successfully with no timeout recovery.

Combined pool:
- complete tasks: **50**
- independent context rows: **50**
- future/seat rows: **54**
- represented targets: **50/60**
- City of Brass / Mana Confluence / Tarnished Citadel strict comparisons: clean and tied with Plains

Persistence:
- raw archive: `/DACK simulator/production/mana_vs_plains_v072_b240_s1_prod1/checkpoints/bite14_wave5_raw.zip`
- raw archive SHA-256: `a43aaaa4404add787db0f5c232948f31531288ddc1d36b548eb97fe52f90b847`
- pooled contexts: `37e3d0ac37bc9098c6afb438f1da73f162c7e5b90cd2d4a6d87c159edf3cfaa5`
- pooled trials: `3288607d4b7aa464d4e5ddd643b4df82213a0f4c5f32f82ad4028a8248fe687a`
- pooled summary: `c4e503593bf86bcb20a6bd06169e624c30ba37871e9a8a2be82336ea3d3d5439`
- task index: `6a5b898523c50a7adbb4d5f29f5af16dceba595bfd14c425668910c7397156a1`
- pool manifest: `e32102682226ea956cd358fb6964f79a075c913c176456862262188fe6649846`

Annotation v1 was regenerated over all 50 rows:
- annotation SHA: `f9568316be8c93874e77e3ef41c682fd3200ad701b77197e2ca012378639fa63`
- derived SHA: `91a42c73c5d8923fb5697961c8b789a3ac113c16e7ae14709ee5abc223f5dd0c`

All persisted Library copies were re-materialized and hash-verified.

This remains N=1 per represented target and is not ranking-quality yet.
