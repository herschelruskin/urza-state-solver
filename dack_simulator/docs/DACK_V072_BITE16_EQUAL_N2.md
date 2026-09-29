# DACK v0.72 Bite 16 — balanced equal-N expansion to N=2

Status: **all 60 targets now have two independent production contexts**.

The production experiment remains frozen:
- experiment: `mana_vs_plains_v072_b240_s1_prod1`
- solver SHA-256: `abba6f0baa7bedfb0b248bdd62501dae10157ba90bd5a3952fbeffbdcca48a7a`
- beam: 240
- samples/context: 1
- seed base: 7202401001

Bite 16 added replicate 1 for every target index 0-59. The resulting pool is exactly balanced:
- complete atomic tasks: **120**
- targets: **60/60**
- independent contexts: **120**
- N per target: **2 for every target**
- future/seat rows: **128**
- summary cards: **60**

An intermediate checkpoint was persisted after replicate-1 targets 0-29:
- 90 total tasks / 90 pooled contexts
- raw archive SHA-256: `92d51b59d17fc2ca915824767337e65d82cac87610b55dbc884f630215aa6466`

Two outer execution-window interruptions occurred during replicate 1:
- Ruins of Trokair (target 14)
- Everflowing Chalice (target 34)

Both were left as same-identity `started` tasks and recovered cleanly by rerunning only the incomplete task. No completed task was overwritten.

Strict invariants across both contexts remain clean:
- City of Brass: 0/2 violations
- Mana Confluence: 0/2 violations
- Tarnished Citadel: 0/2 violations

## Persistence

Full balanced N=2 archive:
- Library: `/DACK simulator/production/mana_vs_plains_v072_b240_s1_prod1/checkpoints/bite16_n2_raw.zip`
- SHA-256: `80895dac4021f8e317aa97ea24014f6baa407a0c3a1c8145634020bb4462b946`
- size: 664,738 bytes
- raw files: 600

Canonical pool:
- contexts: `713781007321b620578ff74b349a99e1408d4c0d80e6dcdb1c0be2bc0310da30`
- trials: `ef2a716c5a3ad25980cddda90b67f374315290403a74c3fb7388df342ef24195`
- summary: `ae16d99852219e3f545a391fd7f10bc14c1c88cb41a84ae33c47f9415c2aeef3`
- task index: `41552ecd577a2582c9653f404650f8c2ff2f68c1223b3f93c295d898e9b5432c`
- pool manifest: `ccaaf69e12fa1553147e1cd482573632b21091f2afc8be4c8a0678ab88df5f3c`

Annotation v1 regenerated over all 120 context rows:
- annotation SHA: `f9568316be8c93874e77e3ef41c682fd3200ad701b77197e2ca012378639fa63`
- derived SHA: `af2e8176dac4ab35e4d6d7edc90baff2bba1838161e75e10b8af5a8ce1cd7d8a`

All persisted Library copies were re-materialized and hash-verified.

N=2 is still exploratory and should not be treated as ranking-quality inference. The next balanced expansion should add replicate 2 for all 60 targets, moving the complete set to N=3.
