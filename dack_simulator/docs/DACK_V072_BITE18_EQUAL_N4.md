# DACK v0.72 Bite 18 — balanced equal-N expansion to N=4

Status: **all 60 targets now have four independent production contexts**.

The experiment remains frozen:
- experiment: `mana_vs_plains_v072_b240_s1_prod1`
- solver SHA-256: `abba6f0baa7bedfb0b248bdd62501dae10157ba90bd5a3952fbeffbdcca48a7a`
- beam: 240
- samples/context: 1
- seed base: 7202401001

Bite 18 completed replicate 3 for every target index 0-59. Existing complete replicate-3 task identities discovered during recovery were verified against the same frozen provenance and reused; only missing identities were computed.

Final balanced pool:
- complete atomic tasks: **240**
- targets: **60/60**
- independent contexts: **240**
- N per target: **4 for every target**
- future/seat rows: **257**
- summary cards: **60**
- replicate context counts: **60 each for replicates 0, 1, 2, and 3**

A clean midpoint subset checkpoint was frozen for replicates 0-2 plus replicate-3 targets 0-29:
- complete tasks: **210**
- pooled contexts: **210**
- pooled trial rows: **225**
- raw archive SHA-256: `73618dfda6921b289618a825c3f6d512ff9b4d8da71aef80eb74a6f9855e10d3`
- midpoint pool manifest SHA-256: `93554863199251a341006f3efbe06a5dea24635eecef364a267a1ca53b55482f`

Strict invariants across all four contexts remain clean:
- City of Brass: **0/4 violations**
- Mana Confluence: **0/4 violations**
- Tarnished Citadel: **0/4 violations**

## Persistence

Full balanced N=4 archive:
- Library: `/DACK simulator/production/mana_vs_plains_v072_b240_s1_prod1/checkpoints/bite18_n4_raw.zip`
- SHA-256: `ca71ea478f0f4e4f2380f39730fe0e312788568ec21b6c5aa99a1f06e2649a08`
- size: **1,193,850 bytes**
- raw task files: **1,200**

Canonical pool:
- contexts: `26de45d828d6cf811af2216e1c5313310aa24b11b7f6129827b10cbc7d39e866`
- trials: `d2a1588d76b702a567bc5d6d8376ca5576fd8a184be337151dbe2bea5c2d76c2`
- summary: `6a1c07b00e2283880521290b5e0820d2b604ae91399a39338bc2f6512f1a62b1`
- task index: `e4ee0bd4b36621bec03dce2c2f3dce63d1c5c50b8c6c2bb122448955a80559c5`
- pool manifest: `d7196d68ff79fb54d0d263c52b66a95fe346f4b61a5c4467c2ad44d74a5be388`

Annotation v1 regenerated over all **240** canonical context rows:
- annotation SHA: `f9568316be8c93874e77e3ef41c682fd3200ad701b77197e2ca012378639fa63`
- derived SHA: `beaac3b3b0a73b7f4e3fc058c1dbb2d61f2770350fd96b6975a171e95487978d`

All final Library artifacts were re-materialized and matched the locally generated hashes exactly.

N=4 is still exploratory; it is not yet stable ranking-quality inference. The next balanced expansion should add replicate 4 for all 60 targets, moving the complete set to N=5.
