# DACK v0.72 Bite 11.5 — card-role annotation layer v1

Status: **annotation-only checkpoint; canonical simulation data unchanged**.

## Purpose

Add human-semantic card roles such as removal, protection, stax, and interaction so
production contexts can later be analyzed as deckbuilding hands rather than only as mana
states.

This layer is deliberately separate from the solver. No card action, search rule, production
runner, task identity, seed namespace, or canonical pooled row was changed.

## Versioned annotation table

Canonical CSV in Library:
- `/DACK simulator/annotations/v1/card_annotations_v1.csv`
- SHA-256: `f9568316be8c93874e77e3ef41c682fd3200ad701b77197e2ca012378639fa63`

GitHub JSON mirror:
- `annotations/card_annotations_v1.json`
- SHA-256: `b6474187b7a22e8b7b14681c03b3a6e066343238def676980276267b6a785f37`

Coverage:
- **96 unique card names**
- **99 deck cards**

Multi-label categories are intentional. Examples:
- Swords to Plowshares = removal + interaction
- Silence = protection + interaction
- Rule of Law = stax + interaction
- Sheltered by Ghosts = combo Aura + protection + removal + interaction
- Razorgrass Ambush = MDFC land + removal + interaction
- Cavern of Souls = land + protection + interaction

v1 deck-copy counts:
- land: 28
- MDFC land: 2
- ramp: 34
- fast mana: 18
- tutors: 7
- repair: 4
- selection: 3
- combo pieces: 16
- combo creatures: 3
- Auras: 12
- protection: 14
- removal: 14
- interaction: 32
- stax: 11
- utility: 6
- safe Chrome Mox imprints: 16

Categories overlap, so these counts are not intended to sum to 99.

## Goldfish relevance

A separate descriptive field distinguishes:
- `direct`: 65 deck cards
- `interaction_noncore`: 18
- `combo_noncore`: 13
- `liability`: 3 combo creatures

This field is analysis metadata only. In particular, a card such as Swords to Plowshares
can be semantically a removal slot while the current deployment goldfish gives it no dedicated
proactive action beyond generic hand/imprint interactions.

## Enrichment script

`scripts/enrich_dack_context_annotations.py`
- SHA-256: `e31f1959eb29f0bb5e722a89799130fe5f0f908feabca5b86c640965332712c4`

For each of `base6`, `target_hand`, and `control_hand`, the derived view records both:
- category count, e.g. `base6_removal_n`
- exact matching card names, e.g. `base6_removal_cards`

The same is done for protection, interaction, stax, ramp, fast mana, tutor, repair,
selection, combo pieces/creatures, Auras, utility, lands, safe Chrome imprints, and
goldfish-relevance classes.

## Bite-11 derived proof

Source canonical Bite-11 contexts:
- rows: **20**
- SHA-256: `39396f0a670db148b6451ca68b1e564bec016d0947d6f1b75158808e1f9cbe24`

Derived annotated view:
- Library: `/DACK simulator/production/mana_vs_plains_v072_b240_s1_prod1/derived/v1/pooled_contexts_annotated_v1.csv`
- rows: **20**
- SHA-256: `c0dce33b481658bc605012873f6fec33fffe22a404171d461b27404d787f0a4d`

The row identities are unchanged. The first production context, for example, contains
Silence in its base six and now reports one protection/interaction slot. Other rows
correctly count multi-role cards in each relevant category.

## Versioning rule

Semantic labels may be revised in a future `v2` annotation table without changing or
invalidating canonical simulation rows. Analyses using semantic tags must record the exact
annotation version/SHA.

Bite 12 can therefore continue the existing production experiment with the exact same
solver/runner hashes; annotation enrichment can be regenerated afterward for any larger pool.
