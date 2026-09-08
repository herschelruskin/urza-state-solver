# Post-R7 full card modeling coverage audit

**This report distinguishes catalog presence from actual runtime gameplay support.**

- Distinct deck identities including commander: **95**
- Current runtime-supported identities: **50**
- Current runtime-unsupported identities: **45**
- Coverage registry `RULES_ACTIVE`: **10**
- Coverage registry `PRIMITIVE_ACTIVE`: **40**
- Coverage registry `ENVIRONMENT_DEFERRED`: **3**
- Coverage registry `POLICY_ONLY`: **0**
- Coverage registry `INTENTIONALLY_UNMODELED`: **42**

## Runtime-unsupported identities

| ID | Card | Coverage registry | Reason |
| ---: | --- | --- | --- |
| 1 | An Offer You Can't Refuse | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |
| 8 | Chain of Vapor | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |
| 10 | Chrome Mox | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |
| 11 | City of Traitors | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |
| 14 | Defense Grid | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |
| 15 | Disruptor Flute | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |
| 16 | Dizzy Spell | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |
| 17 | Dramatic Reversal | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |
| 18 | Everflowing Chalice | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |
| 19 | Faerie Mastermind | EnvironmentDeferred | Pinned Oracle text is validated. Faerie Mastermind's opponent-second-card draw trigger belongs to the explicit goldfish environment model; its real {3}{U} each-player-draw activation remains a future rules slice. |
| 20 | Fierce Guardianship | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |
| 21 | Flooded Strand | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |
| 22 | Flusterstorm | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |
| 23 | Force of Negation | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |
| 24 | Force of Will | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |
| 27 | Gemstone Caverns | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |
| 28 | Giant's Boulder | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |
| 29 | Gitaxian Probe | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |
| 35 | Imposter Mech | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |
| 36 | Ipnu Rivulet | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |
| 38 | Jeweled Amulet | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |
| 39 | Lotus Petal | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |
| 40 | Mana Drain | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |
| 43 | Mental Misstep | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |
| 46 | Mindbreak Trap | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |
| 48 | Misty Rainforest | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |
| 49 | Moonsnare Prototype | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |
| 50 | Mox Diamond | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |
| 51 | Mox Opal | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |
| 52 | Muddle the Mixture | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |
| 53 | Mystic Remora | EnvironmentDeferred | Pinned Oracle text is validated. Mystic Remora's opponent noncreature-spell draw rate and cumulative-upkeep survival belong to the explicit goldfish environment abstraction rather than hidden rules shortcuts. |
| 57 | Pact of Negation | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |
| 58 | Pithing Needle | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |
| 59 | Polluted Delta | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |
| 61 | Prismatic Vista | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |
| 62 | Prized Statue | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |
| 66 | Rhystic Study | EnvironmentDeferred | Pinned Oracle text is validated. Rhystic Study's opponent-spell tax/draw rate belongs to the explicit goldfish environment abstraction rather than the intrinsic rules engine. |
| 67 | Sapphire Medallion | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |
| 68 | Saprazzan Skerry | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |
| 69 | Scalding Tarn | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |
| 70 | Scour for Scrap | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |
| 78 | Spellskite | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |
| 79 | Swan Song | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |
| 90 | Vexing Bauble | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |
| 94 | Witching Well | IntentionallyUnmodeled | R0 foundation: intrinsic card rules are intentionally not implemented yet |

## Runtime-supported but not marked RULES_ACTIVE

These cards have some executable gameplay surface, but their registry classification explicitly says the implementation is primitive, environment-deferred, policy-only, or intentionally unmodeled. They must not be treated as fully modeled without a card-by-card rules review.

| ID | Card | Coverage registry | Role | Engine | Utility | Search | Spell effect | Reason |
| ---: | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | Aether Spellbomb | PrimitiveActive | ArtifactPermanent | None | None | None / None | None | R2 primitive: ordinary artifact cast/stack/battlefield entry; activated abilities are deferred |
| 2 | Ancient Tomb | PrimitiveActive | Land | None | None | None / None | None | R2 primitive: land play and intrinsic tap for two colorless with 2 self-damage |
| 5 | Basalt Monolith | PrimitiveActive | ArtifactPermanent | BasaltMonolith | None | None / None | None | R4-start primitive: ordinary artifact cast, tap for three colorless, no normal untap, native {3} untap activation, and Forensic Gadgeteer cost reduction with the one-mana floor; broader combo catalog continues in R4 |
| 7 | Cephalid Coliseum | PrimitiveActive | Land | None | None | None / None | None | R2 primitive: land play and intrinsic blue-mana ability with 1 self-damage; threshold loot is deferred |
| 12 | Codex Shredder | PrimitiveActive | ArtifactPermanent | None | None | None / None | None | R2 primitive: ordinary artifact cast/stack/battlefield entry; activated abilities are deferred |
| 13 | Crystal Vein | PrimitiveActive | Land | None | None | None / None | None | R2 primitive: land play and intrinsic tap for one colorless; sacrifice mana mode is deferred |
| 26 | Fortune Teller's Talent | PrimitiveActive | EnchantmentPermanent | None | FortuneTellersTalent | None / None | None | R4 top-access primitive: Level 1 continuous top look, stack-based Level 2/3 progression at printed costs, spell-this-turn Level 2 play permission, and Level 3 non-hand generic cost reduction; broader top-cast modes remain in R4 |
| 30 | Grafdigger's Cage | PrimitiveActive | ArtifactPermanent | None | GrafdiggersCage | None / None | None | R4 top-access primitive: ordinary artifact cast plus blocking of Chip/FTT spell casts from library and corresponding terminal-family proofs; direct library-to-battlefield creature prevention remains in R4 |
| 31 | Grim Monolith | PrimitiveActive | ArtifactPermanent | GrimMonolith | None | None / None | None | R4-start primitive: ordinary artifact cast, tap for three colorless, no normal untap, native {4} untap activation, and artifact-activation cost reductions with the one-mana floor |
| 33 | Hope of Ghirapur | PrimitiveActive | ArtifactPermanent | None | None | None / None | None | R2 primitive: ordinary artifact-creature cast/stack/battlefield entry; combat/sacrifice ability is deferred |
| 34 | Hydroelectric Specimen | PrimitiveActive | Land | None | None | None / None | None | R2 primitive: back land face, pay-3-life-or-enter-tapped choice, and blue mana; front spell is deferred |
| 37 | Island | PrimitiveActive | Land | None | None | None / None | None | R2 primitive: land play and intrinsic blue mana |
| 41 | Mana Vault | PrimitiveActive | ArtifactPermanent | ManaVault | None | None / None | None | R4 recurrence primitive: tap for three colorless, skips normal untap, and participates in the Chrome Dome/Power Artifact/Gadgeteer terminal proof; upkeep untap and draw-step damage remain deferred. |
| 42 | Manifold Key | PrimitiveActive | ArtifactPermanent | None | None | None / None | None | R2 primitive: ordinary artifact cast/stack/battlefield entry; untap/unblockable activations are deferred |
| 44 | Merchant Scroll | PrimitiveActive | SearchSpell | None | None | Some(MerchantScroll) / None | None | R3 primitive active: sorcery cast resolves to a staged blue-instant library search; target/no-find choice occurs only after the search observation, target goes to hand, then the shared pre-target search permutation determines the shuffle |
| 45 | Minamo, School at Water's Edge | PrimitiveActive | Land | None | None | None / None | None | R2 primitive: land play and intrinsic blue mana; legendary-permanent untap ability is deferred |
| 47 | Mishra's Bauble | PrimitiveActive | ArtifactPermanent | None | None | None / None | None | R2 primitive: ordinary artifact cast/stack/battlefield entry; delayed-draw activation is deferred |
| 54 | Mystical Tutor | PrimitiveActive | SearchSpell | None | None | Some(MysticalTutor) / None | None | R3 primitive active: instant-speed cast resolves to a staged instant-or-sorcery library search; target/no-find choice occurs only after observation, selected target is placed on top after the shared pre-target shuffle |
| 55 | Oboro, Palace in the Clouds | PrimitiveActive | Land | None | None | None / None | None | R2 primitive: land play and intrinsic blue mana; self-bounce ability is deferred |
| 56 | Otawara, Soaring City | PrimitiveActive | Land | None | None | None / None | None | R2 primitive: land play and intrinsic blue mana; Channel ability is deferred |
| 63 | Repurposing Bay | PrimitiveActive | ArtifactPermanent | None | None | None / RepurposingBay | None | R3 primitive active: sorcery-speed {2}, tap, and sacrifice-another-artifact costs are committed before its activated ability resolves; resolution observes exact sacrificed-MV+1 artifact targets, then target/no-find puts the chosen artifact onto the battlefield and shuffles |
| 64 | Reshape | PrimitiveActive | SearchSpell | None | None | None / Reshape | None | R3 primitive active: X, mana payment, and artifact sacrifice are committed as casting costs; after resolution an MV<=X artifact search is observed, then target/no-find is chosen and the selected artifact is put onto the battlefield using the shared pre-target search shuffle |
| 71 | Sea Gate Restoration | PrimitiveActive | Land | None | None | None / None | None | R2 primitive: back land face, pay-3-life-or-enter-tapped choice, and blue mana; front spell is deferred |
| 72 | Seat of the Synod | PrimitiveActive | Land | None | None | None / None | None | R2 primitive: artifact-land play, intrinsic blue mana, and Urza artifact-mana eligibility |
| 73 | Sensei's Divining Top | PrimitiveActive | ArtifactPermanent | None | SenseisDiviningTop | None / None | None | R3 primitive active: ordinary artifact cast, staged {1} top-three look -> post-observation reorder choice, and atomic tap/draw-then-put-Top-on-library resolution |
| 75 | Sink into Stupor | PrimitiveActive | Land | None | None | None / None | None | R2 primitive: back land face, pay-3-life-or-enter-tapped choice, and blue mana; front spell is deferred |
| 76 | Sol Ring | PrimitiveActive | ArtifactPermanent | None | None | None / None | None | R2 primitive: ordinary artifact cast/entry and intrinsic tap for two colorless |
| 77 | Spellseeker | PrimitiveActive | CreaturePermanent | None | None | Some(Spellseeker) / None | None | R3 primitive active: creature cast/ETB is explicit, then its MV<=2 instant-or-sorcery search becomes a post-observation contingent target/no-find decision; selected target goes to hand before the shared search shuffle |
| 80 | Tezzeret, Cruel Captain | PrimitiveActive | PlaneswalkerPermanent | None | TezzeretCruelCaptain | None / None | None | R3 primitive active: ordinary planeswalker cast with starting loyalty, -3 loyalty paid before resolution, then staged artifact-MV<=1 search to hand using the shared pre-target shuffle; 0, -7, and artifact-ETB loyalty trigger remain deferred |
| 81 | The One Ring | PrimitiveActive | ArtifactPermanent | None | TheOneRing | None / None | None | Post-R7 second-pass One Ring primitive: normal artifact cast, burden upkeep life loss, and tap-to-add-burden/draw are modeled on the production stack. Cast protection, indestructible, and exotic LKI interleavings after intervening burden changes remain deferred. |
| 82 | The Reality Chip | PrimitiveActive | CreaturePermanent | None | RealityChip | None / None | None | R4 top-access primitive: ordinary artifact-creature cast, continuous top look, exact reconfigure target on the stack, exact attachment/detach state, and library-top land/spell permission while attached; broader trigger/cast-mode coverage remains in R4 |
| 83 | Tormod's Crypt | PrimitiveActive | ArtifactPermanent | None | None | None / None | None | R2 primitive: ordinary artifact cast/stack/battlefield entry; exile activation is deferred |
| 84 | Transmute Artifact | PrimitiveActive | SearchSpell | None | None | None / TransmuteArtifact | None | R3 primitive active: cast for UU, choose/sacrifice an artifact during resolution before search information, then observe artifact targets; a higher-MV target creates a later exact generic-difference pay-or-decline decision, with mana abilities legal during that payment window |
| 85 | Urza, Lord High Artificer | PrimitiveActive | UrzaCommander | None | None | None / None | None | R3 primitive: command-zone cast/tax, Construct ETB, artifact mana, plus five-mana spin that shuffles with occurrence-aware RNG, exiles/observes the top card, creates an until-EOT free-play permission, and supports consuming that permission for currently modeled legal card faces |
| 86 | Urza's Bauble | PrimitiveActive | ArtifactPermanent | None | None | None / None | None | R2 primitive: ordinary artifact cast/stack/battlefield entry; delayed-draw activation is deferred |
| 87 | Urza's Saga | PrimitiveActive | Land | None | UrzasSaga | None / None | None | R3 primitive active: explicit lore/chapter I–III sequencing, chapter I grants colorless mana, chapter II creates the shared Construct token, and chapter III stages an exact printed-{0}/{1} artifact search before final-chapter sacrifice after the search finishes |
| 88 | Uthros Research Craft | PrimitiveActive | ArtifactPermanent | None | UthrosResearchCraft | None / None | None | Post-R7 second-pass Uthros primitive: normal artifact cast, sorcery-speed station by tapping another untapped creature, charge counters from current modeled power with the official leave-before-resolution LKI fallback, and the 3+ artifact-cast draw-then-charge trigger are modeled. The 12+ creature/flying/power striation and otherwise unmodeled temporary/static power modifiers remain deferred. |
| 91 | Voltaic Key | PrimitiveActive | ArtifactPermanent | None | None | None / None | None | R2 primitive: ordinary artifact cast/stack/battlefield entry; untap activation is deferred |
| 92 | Welding Jar | PrimitiveActive | ArtifactPermanent | None | None | None / None | None | R2 primitive: ordinary artifact cast/stack/battlefield entry; regeneration activation is deferred |
| 93 | Whir of Invention | PrimitiveActive | SearchSpell | None | None | None / Whir | None | R3 primitive active: X and improvise sources are committed while casting; after resolution an MV<=X artifact search is observed, then target/no-find is chosen and the selected artifact is put onto the battlefield using the shared pre-target search shuffle |

## Registry RULES_ACTIVE identities

Artificer's Assistant, Banishing Knack, Battered Golem, Chrome Dome, Forensic Gadgeteer, Grinding Station, Power Artifact, Retraction Helix, Sewer-veillance Cam, Valley Floodcaller

## Environment-deferred identities

Faerie Mastermind, Mystic Remora, Rhystic Study

## Audit interpretation

A card appearing in the 95-identity catalog proves only deck identity/oracle metadata coverage. It does not prove that the current rules engine can cast/play it or execute all of its relevant Oracle text. Runtime support and rules completeness must be audited separately before policy conclusions are accepted.

