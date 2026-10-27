# Dack Assertive ramp-piece leaderboard

**LIVE SCREENING STATUS — not a finalized card ranking.** The provisional table only appears once at least 24 completed matched games from a screen are available. Both screens preserve the same frozen Assertive mulligan policy, and all numbers are conditional on the optimistic goldfish Dack-cast model.

| Trial | Games recovered | Completed shards | Data status |
|---|---:|---:|---|
| screen20 | 40/256 | 10/64 | Partial exploratory evidence |
| flex41 | 8/128 | 4/64 | Partial exploratory evidence |

---


**Primary metric:** probability of Dack cast by T2 under the promoted Assertive London policy, with T1 and T3 tracked as checks.

> All results are optimistic full-beam goldfish Dack-cast rates, not verified complete combo lines or multiplayer wins. Small-sample rankings are exploratory and susceptible to winner's curse.

## Live evidence status

- **screen20**: PARTIAL_40_OF_256, 20 decks × 256 matched game IDs — https://github.com/herschelruskin/urza-state-solver/actions/runs/40444150025
- **flex41**: PARTIAL_8_OF_128, 41 decks × 128 matched game IDs — https://github.com/herschelruskin/urza-state-solver/actions/runs/40445020227

## Ramp-card ranking (only controlled single-card comparisons)

| Rank | Card | Observed context-weighted T2 signal (pp) | Matched contexts | Trial sets | Positive / negative contexts |
|---:|---|---:|---:|---:|---:|
| 1 | Tooth of Ramos | +6.07 | 7 | 1 | 7 / 0 |
| 2 | Implements of Sacrifice | +2.50 | 1 | 1 | 1 / 0 |
| 3 | Pentad Prism | +1.25 | 4 | 1 | 3 / 1 |
| 4 | Manifold Key | +0.71 | 7 | 1 | 1 / 1 |
| 5 | Voltaic Key | +0.71 | 7 | 1 | 3 / 1 |
| 6 | Plains | +0.00 | 2 | 1 | 0 / 0 |
| 7 | Giant's Boulder | -0.36 | 7 | 1 | 1 / 2 |
| 8 | Lunarch Mantle | -1.11 | 9 | 1 | 2 / 4 |
| 9 | Basalt Monolith | -1.25 | 4 | 1 | 0 / 2 |
| 10 | Hardlight Containment | -2.50 | 1 | 1 | 0 / 1 |
| 11 | Candelabra of Tawnos | -4.44 | 9 | 1 | 0 / 6 |

**Interpretation:** The score averages results across the *observed replacement options and deck backgrounds*, not the intrinsic value of a card. Contexts share hands and games; the displayed score has **no valid pooled confidence interval**. Strong claims require a held-out card comparison.

## Leading one-slot head-to-head comparisons

| New card over old | Background | Δ T2 (pp) | Paired 95% CI (pp) | n |
|---|---|---:|---|---:|
| Lunarch Mantle over Candelabra of Tawnos | screen20: full_candelabra_instead_tooth → full_preserve_mantle | +7.50 | -0.77 to +15.77 | 40 |
| Pentad Prism over Hardlight Containment | screen20: legal_four_rainbow → four_rainbow_plus_prism | +2.50 | -2.40 to +7.40 | 40 |
| Voltaic Key over Lunarch Mantle | screen20: four_rainbow_plus_prism → full_basalt_instead_boulder | +0.00 | +0.00 to +0.00 | 40 |
| Candelabra of Tawnos over Voltaic Key | screen20: full_prism_voltaic_boulder → full_prism_candelabra_boulder | +0.00 | +0.00 to +0.00 | 40 |
| Basalt Monolith over Giant's Boulder | screen20: full_prism_voltaic_boulder → full_basalt_instead_boulder | +0.00 | +0.00 to +0.00 | 40 |
| Plains over Voltaic Key | screen20: full_prism_voltaic_boulder → full_35lands_instead_voltaic | +0.00 | +0.00 to +0.00 | 40 |
| Manifold Key over Giant's Boulder | screen20: full_prism_voltaic_boulder → full_2keys_instead_boulder | +0.00 | -7.02 to +7.02 | 40 |
| Plains over Candelabra of Tawnos | screen20: full_prism_candelabra_boulder → full_35lands_instead_voltaic | +0.00 | +0.00 to +0.00 | 40 |
| Manifold Key over Basalt Monolith | screen20: full_basalt_instead_boulder → full_2keys_instead_boulder | +0.00 | -7.02 to +7.02 | 40 |
| Lunarch Mantle over Manifold Key | screen20: full_3keys_instead_tooth → full_preserve_mantle | +0.00 | +0.00 to +0.00 | 40 |
| Lunarch Mantle over Giant's Boulder | screen20: full_3keys_instead_tooth → full_preserve_mantle_2keys | +0.00 | -7.02 to +7.02 | 40 |
| Manifold Key over Giant's Boulder | screen20: full_preserve_mantle → full_preserve_mantle_2keys | +0.00 | -7.02 to +7.02 | 40 |
| Candelabra of Tawnos over Manifold Key | screen20: current_2keys → current_voltaic_candelabra | +0.00 | +0.00 to +0.00 | 40 |
| Pentad Prism over Implements of Sacrifice | screen20: current → prism_only | -2.50 | -7.40 to +2.40 | 40 |
| Candelabra of Tawnos over Lunarch Mantle | screen20: four_rainbow_plus_prism → full_basalt_and_candelabra | -2.50 | -7.40 to +2.40 | 40 |
| Basalt Monolith over Pentad Prism | screen20: full_prism_voltaic_boulder → full_basalt_instead_prism | -2.50 | -7.40 to +2.40 | 40 |
| Manifold Key over Tooth of Ramos | screen20: full_prism_voltaic_boulder → full_3keys_instead_tooth | -2.50 | -7.40 to +2.40 | 40 |
| Lunarch Mantle over Tooth of Ramos | screen20: full_prism_voltaic_boulder → full_preserve_mantle | -2.50 | -7.40 to +2.40 | 40 |
| Basalt Monolith over Giant's Boulder | screen20: full_prism_candelabra_boulder → full_basalt_and_candelabra | -2.50 | -7.40 to +2.40 | 40 |
| Giant's Boulder over Pentad Prism | screen20: full_basalt_instead_boulder → full_basalt_instead_prism | -2.50 | -7.40 to +2.40 | 40 |
| Candelabra of Tawnos over Voltaic Key | screen20: full_basalt_instead_boulder → full_basalt_and_candelabra | -2.50 | -7.40 to +2.40 | 40 |
| Giant's Boulder over Tooth of Ramos | screen20: full_2keys_instead_boulder → full_3keys_instead_tooth | -2.50 | -11.06 to +6.06 | 40 |
| Lunarch Mantle over Tooth of Ramos | screen20: full_2keys_instead_boulder → full_preserve_mantle_2keys | -2.50 | -7.40 to +2.40 | 40 |
| Lunarch Mantle over Voltaic Key | screen20: full_candelabra_instead_tooth → full_preserve_mantle_candelabra | -2.50 | -11.06 to +6.06 | 40 |
| Candelabra of Tawnos over Manifold Key | screen20: full_3keys_instead_tooth → full_candelabra_instead_tooth | -7.50 | -15.77 to +0.77 | 40 |
| Candelabra of Tawnos over Tooth of Ramos | screen20: full_prism_voltaic_boulder → full_candelabra_instead_tooth | -10.00 | -19.42 to -0.58 | 40 |
| Voltaic Key over Tooth of Ramos | screen20: full_prism_candelabra_boulder → full_candelabra_instead_tooth | -10.00 | -19.42 to -0.58 | 40 |
| Candelabra of Tawnos over Voltaic Key | screen20: full_preserve_mantle → full_preserve_mantle_candelabra | -10.00 | -19.42 to -0.58 | 40 |
| Lunarch Mantle over Tooth of Ramos | screen20: full_prism_candelabra_boulder → full_preserve_mantle_candelabra | -12.50 | -22.88 to -2.12 | 40 |

## Historical controls — Standard mulligans only

- The old 256-game held-out six-arm screen had **double-Key** at 48.83% by T2 versus 45.31% for the baseline; paired difference +3.52 pp with 95% CI [-0.138, 7.169]. The interval crosses zero.
- The old 128-game Key vs Candelabra direct swap had Voltaic Key at 47.66% by T2 and Candelabra at 46.09%; also not a settled ranking.

## What's not ranked yet

Some powerful rocks are present in every test deck and consequently have no controlled 'card absent' comparator in these screens. Their omission from the rankings **does not mean they are weak**. Dedicated same-slot replacement tests are needed for: Sol Ring, Mana Vault, Grim Monolith, Lion's Eye Diamond, Chrome Mox, Mox Diamond, Mox Opal, Lotus Petal, Ancient Tomb, City of Traitors, Crystal Vein, Mishra's Workshop, Moonsilver Key, Coalition Relic, Everflowing Chalice, Jeweled Amulet, Arcane Signet, Fellwar Stone, Mind Stone, The Mind Stone, World Map.

**Promotion rule:** No deck cut is decided by this leaderboard. Identify repeatable T2-leading combinations, separately verify full combo functionality and multiplayer constraints, then run independent held-out paired tests.
