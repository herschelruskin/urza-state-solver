# DACK v0.72 Bite 17 — balanced equal-N expansion to N=3

Status: **all 60 targets now have three independent production contexts**.

The experiment remains frozen:
- experiment: `mana_vs_plains_v072_b240_s1_prod1`
- solver SHA-256: `abba6f0baa7bedfb0b248bdd62501dae10157ba90bd5a3952fbeffbdcca48a7a`
- beam: 240
- samples/context: 1
- seed base: 7202401001

Bite 17 added replicate 2 for every target index 0-59.

Final balanced pool:
- complete atomic tasks: **180**
- targets: **60/60**
- independent contexts: **180**
- N per target: **3 for every target**
- future/seat rows: **192**
- summary cards: **60**

A midpoint checkpoint was persisted after replicate-2 targets 0-29:
- 150 total tasks / 150 contexts / 160 trial rows
- raw archive SHA-256: `0709bc633a7227227a178116ea22cba1676f6b7d87540f225745297fe9392ae9`
- midpoint pool manifest SHA-256: `f187ccb53ffca9cec41ebb724ba33b4da75862f0b6f414377c424031fdd855e1`

Two outer execution-window interruptions left same-identity tasks in `started` state:
- Ruins of Trokair (replicate 2, target 14)
- Urza's Saga (replicate 2, target 23)

Both were recovered by rerunning only the incomplete task. No completed task was overwritten.

Strict invariants across all three contexts remain clean:
- City of Brass: **0/3 violations**
- Mana Confluence: **0/3 violations**
- Tarnished Citadel: **0/3 violations**

## Persistence

Full balanced N=3 archive:
- Library: `/DACK simulator/production/mana_vs_plains_v072_b240_s1_prod1/checkpoints/bite17_n3_raw.zip`
- SHA-256: `da158242fdfd006ecae272dcdf0bdb1a5890150679c464c76ded7db187469621`
- size: **997,294 bytes**
- raw files: **900**

Canonical pool:
- contexts: `3cbbcad35ec726c49ce0d344499448df9fc1bd2715954ee210279c6defd9e829`
- trials: `66740cad7fea18ec3d4e5c238416f97be7e4350e8ab0795a918b70289faf7b3f`
- summary: `dbdbe270226fd7c7dfbd7874675f3300979755bdec2097ad364639d06d332d47`
- task index: `80e45fdb73b90a87449dd9712ab68183e8b5e92392a284d489b228f1d3a0f650`
- pool manifest: `a347273acae16a16a8f358711dc7da7a3cdfb3496350e57b8955c936c6fd057a`

Annotation v1 regenerated over all **180** canonical rows:
- annotation SHA: `f9568316be8c93874e77e3ef41c682fd3200ad701b77197e2ca012378639fa63`
- derived SHA: `1154dedf11a750d802048ecbe68291a32fec933d15b54e7f1182e407c0976a18`

All persisted Library copies were re-materialized and hash-verified.

N=3 is still exploratory and should not be treated as stable ranking-quality inference. The next balanced expansion should add replicate 3 for all 60 targets, moving the complete set to N=4.
