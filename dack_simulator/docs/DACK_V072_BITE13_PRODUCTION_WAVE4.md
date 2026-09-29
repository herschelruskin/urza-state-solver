# DACK v0.72 Bite 13 — production wave 4

Status: permanent production dataset expanded to **40/60 targets**.

Experiment remains unchanged:
- ID: `mana_vs_plains_v072_b240_s1_prod1`
- solver SHA-256: `abba6f0baa7bedfb0b248bdd62501dae10157ba90bd5a3952fbeffbdcca48a7a`
- beam: 240
- samples/context: 1
- seed base: 7202401001

Wave 4 added target indices 30-39:
Chrome Mox, Coalition Relic, Eldrazi Confluence, Enlightened Tutor,
Everflowing Chalice, Expedition Map, Fellwar Stone, Giant's Boulder,
Gleaming Splendor, and Grim Monolith.

All 10 new atomic tasks completed successfully with no timeout recovery.

Combined pool:
- complete tasks: 40
- context rows: 40
- future/seat rows: 44
- represented targets: 40/60
- strict City of Brass / Mana Confluence / Tarnished Citadel checks: clean

Persistence:
- raw archive: `/DACK simulator/production/mana_vs_plains_v072_b240_s1_prod1/checkpoints/bite13_wave4_raw.zip`
- raw archive SHA-256: `a52ad5757828125948cf1bee2c85b6a15f7dc087bf2631c050bbcdeca5741c4b`
- pooled contexts: `0f568a62ab5eebe5a30baff89142384adec081d0bd3e52cd7b7c32df8e25cffa`
- pooled trials: `13b38cfb037bbcc55f6e3957f49bce3c559df91b9b9740be8e2f1d28d6aa2975`
- pooled summary: `67c41241709129a4a81a893d2fc6f88f78c5264c09b5e42522077e3708bdfbf3`
- task index: `f76b81db638896aa8ff65406fe791cda400e2f6c143d69644736b5ef13aabe8b`
- pool manifest: `4e822eb5543566c88cb22e6d2a6f7acc1cb5f21c0d6c8e7a4097bd81251ffca2`

Annotation v1 was regenerated over all 40 source rows:
- annotation SHA: `f9568316be8c93874e77e3ef41c682fd3200ad701b77197e2ca012378639fa63`
- derived SHA: `18dc4841ede4a6fffa4b5887b1279d6414c8ff8809ff7252be4459bcd085518d`

Persisted Library copies were re-materialized and hash-verified.

This remains N=1 per represented target and is not ranking-quality yet.
