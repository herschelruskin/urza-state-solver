# DACK v0.72 Bite 18 — balanced equal-N expansion to N=4

Status: **all 60 targets now have four independent production contexts**.

The production experiment remains frozen:
- experiment: `mana_vs_plains_v072_b240_s1_prod1`
- solver SHA-256: `abba6f0baa7bedfb0b248bdd62501dae10157ba90bd5a3952fbeffbdcca48a7a`
- beam: 240
- samples/context: 1
- seed base: 7202401001

Bite 18 added replicate 3 for every target index 0-59.

Final balanced pool:
- complete atomic tasks: **240**
- targets: **60/60**
- independent contexts: **240**
- N per target: **4 for every target**
- future/seat rows: **257**
- summary cards: **60**

A midpoint checkpoint was already persisted after replicate-3 targets 0-29:
- midpoint raw archive SHA-256: `8c42345c7785654b4be8f4fa2b992afc4eeb8470136c4fb992649930cd76c5e7`
- midpoint pool-manifest SHA-256: `edaae6485e4ddedb16925638dcffcb80cbae71d852f9f156fc11b6bdc22aa335`

## Recovery during Bite 18

A transient local-workspace reset after the midpoint removed replicate-3 task directories 11-37 from the working copy. This was caught by the pooler because the first attempted N=4 pool contained only 212 tasks and mixed N=3/N=4 coverage.

No incomplete pool was persisted as the canonical latest dataset.

Recovery:
1. restored the persisted Bite-18 midpoint archive, recovering replicate-3 targets 0-29;
2. retained already-complete replicate-3 targets 38-59;
3. reran only missing targets 30-37 under the same task identities;
4. rebuilt the pool and required exact N=4 across all 60 targets before persistence.

Final validation therefore has exactly one complete task for every target/replicate pair.

Strict invariants across all four contexts remain clean:
- City of Brass: **0/4 violations**
- Mana Confluence: **0/4 violations**
- Tarnished Citadel: **0/4 violations**

## Persistence

Full balanced N=4 archive:
- Library: `/DACK simulator/production/mana_vs_plains_v072_b240_s1_prod1/checkpoints/bite18_n4_raw.zip`
- SHA-256: `c251612bdee175e45c13416d10ab258cc887c15dcc1dd118e51892808582ea83`
- size: **1,329,614 bytes**
- raw files: **1,200**

Canonical pool:
- contexts: `26de45d828d6cf811af2216e1c5313310aa24b11b7f6129827b10cbc7d39e866`
- trials: `d2a1588d76b702a567bc5d6d8376ca5576fd8a184be337151dbe2bea5c2d76c2`
- summary: `6a1c07b00e2283880521290b5e0820d2b604ae91399a39338bc2f6512f1a62b1`
- task index: `e4ee0bd4b36621bec03dce2c2f3dce63d1c5c50b8c6c2bb122448955a80559c5`
- pool manifest: `d7196d68ff79fb54d0d263c52b66a95fe346f4b61a5c4467c2ad44d74a5be388`

Annotation v1 regenerated over all **240** canonical rows:
- annotation SHA: `f9568316be8c93874e77e3ef41c682fd3200ad701b77197e2ca012378639fa63`
- derived SHA: `beaac3b3b0a73b7f4e3fc058c1dbb2d61f2770350fd96b6975a171e95487978d`

All persisted Library copies were re-materialized and hash-verified.

N=4 is still exploratory rather than stable ranking-quality inference. The next balanced expansion should add replicate 4 for all 60 targets, moving the complete set to N=5.
