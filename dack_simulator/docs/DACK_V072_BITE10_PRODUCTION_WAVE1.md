# DACK v0.72 Bite 10 — first permanent production wave

Status: **permanent production data started**.

## Experiment
- Experiment ID: `mana_vs_plains_v072_b240_s1_prod1`
- Experiment type: `conditional_forced_opening_slot`
- Comparison: target vs Plains
- Frozen solver SHA-256: `abba6f0baa7bedfb0b248bdd62501dae10157ba90bd5a3952fbeffbdcca48a7a`
- Beam: 240
- Future samples/context: 1
- Seed namespace: `7202401001`
- Initial equal-N goal: 25 independent contexts per target

Bite-9 smoke rows and all earlier v0.68/v0.70-transient rows are excluded.

## Wave 1
Target indices 0-9, replicate 0:
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

Results:
- completed atomic tasks: **10/10**
- pooled independent context rows: **10**
- pooled future/seat rows: **12**
- pooled cards: **10**

Gemstone Caverns produced its expected distinct starting/nonstarting seat rows.

The outer execution window interrupted City of Traitors while its manifest was `started`.
Rerunning the exact same task identity cleaned only that incomplete task and completed it
normally. This is a real-production confirmation of the Bite-9 restart design.

## Persistence
Raw task archive:
- Library: `/DACK simulator/production/mana_vs_plains_v072_b240_s1_prod1/checkpoints/bite10_wave1_raw.zip`
- SHA-256: `2ed97001010bed17467410eb6dde4a74dc2f5812443f6cf5a75036790854e12e`

Latest pooled outputs are persisted under:
`/DACK simulator/production/mana_vs_plains_v072_b240_s1_prod1/latest/`

Hashes:
- pooled contexts: `3b35b44ea7d004ab3aa0db8521c7c651f8445d0f6fcb2cb64ae66094716f953f`
- pooled trials: `0a05f8a76c799922f979c3c1336900aea61072c19810a6d49067269bd1b469fd`
- pooled summary: `f1cc2747a84063ce53c90c11d07140b2ff4b3feace2b6bb06fcad8ede293d7ee`
- pooled task index: `6a458f8e4b76db4ec8f643ec5922ea5b227b9fe407ccd1335b18a5535010cb0e`

## Interpretation
Wave 1 is **N=1 for only ten targets** and is not used for card rankings, cuts, or inferential
claims. Its purpose is to establish the first durable scientific production rows and prove
that interrupted production tasks can resume without invalidating completed work.

## Next
Resume from this raw archive and add further atomic tasks under the same experiment ID,
hashes, beam, sample count, and seed namespace. Periodically rebuild the deterministic pool.
