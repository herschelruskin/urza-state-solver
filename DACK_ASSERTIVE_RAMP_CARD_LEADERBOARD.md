# Dack Assertive ramp-piece leaderboard

**LIVE SCREENING STATUS — not a finalized card ranking.** The provisional table only appears once at least 24 completed matched games from a screen are available. Both screens preserve the same frozen Assertive mulligan policy, and all numbers are conditional on the optimistic goldfish Dack-cast model.

| Trial | Games recovered | Completed shards | Data status |
|---|---:|---:|---|
| screen20 | 72/256 | 18/64 | Partial exploratory evidence |
| flex41 | 18/128 | 9/64 | Partial exploratory evidence |

---


**Primary metric:** probability of Dack cast by T2 under the promoted Assertive London policy, with T1 and T3 tracked as checks.

> All results are optimistic full-beam goldfish Dack-cast rates, not verified complete combo lines or multiplayer wins. Small-sample rankings are exploratory and susceptible to winner's curse.

## Live evidence status

- **screen20**: PARTIAL_72_OF_256, 20 decks × 256 matched game IDs — https://github.com/herschelruskin/urza-state-solver/actions/runs/40444150025
- **flex41**: PARTIAL_18_OF_128, 41 decks × 128 matched game IDs — https://github.com/herschelruskin/urza-state-solver/actions/runs/40445020227

## Ramp-card ranking (only controlled single-card comparisons)

| Rank | Card | Observed context-weighted T2 signal (pp) | Matched contexts | Trial sets | Positive / negative contexts |
|---:|---|---:|---:|---:|---:|
| 1 | Tooth of Ramos | +3.77 | 7 | 1 | 7 / 0 |
| 2 | Manifold Key | +1.39 | 7 | 1 | 5 / 1 |
| 3 | Implements of Sacrifice | +1.39 | 1 | 1 | 1 / 0 |
| 4 | Pentad Prism | +0.35 | 4 | 1 | 2 / 1 |
| 5 | Hardlight Containment | +0.00 | 1 | 1 | 0 / 0 |
| 6 | Lunarch Mantle | -0.46 | 9 | 1 | 2 / 3 |
| 7 | Voltaic Key | -0.60 | 7 | 1 | 1 / 2 |
| 8 | Plains | -0.69 | 2 | 1 | 0 / 1 |
| 9 | Giant's Boulder | -0.99 | 7 | 1 | 1 / 5 |
| 10 | Basalt Monolith | -1.04 | 4 | 1 | 0 / 3 |
| 11 | Candelabra of Tawnos | -2.01 | 9 | 1 | 2 / 5 |

**Interpretation:** The score averages results across the *observed replacement options and deck backgrounds*, not the intrinsic value of a card. Contexts share hands and games; the displayed score has **no valid pooled confidence interval**. Strong claims require a held-out card comparison.

## Leading one-slot head-to-head comparisons

| New card over old | Background | Δ T2 (pp) | Paired 95% CI (pp) | n |
|---|---|---:|---|---:|
| Lunarch Mantle over Candelabra of Tawnos | screen20: full_candelabra_instead_tooth → full_preserve_mantle | +4.17 | -1.89 to +10.22 | 72 |
| Candelabra of Tawnos over Voltaic Key | screen20: full_prism_voltaic_boulder → full_prism_candelabra_boulder | +1.39 | -3.35 to +6.13 | 72 |
| Manifold Key over Giant's Boulder | screen20: full_prism_voltaic_boulder → full_2keys_instead_boulder | +1.39 | -4.73 to +7.51 | 72 |
| Manifold Key over Basalt Monolith | screen20: full_basalt_instead_boulder → full_2keys_instead_boulder | +1.39 | -4.73 to +7.51 | 72 |
| Lunarch Mantle over Giant's Boulder | screen20: full_3keys_instead_tooth → full_preserve_mantle_2keys | +1.39 | -3.35 to +6.13 | 72 |
| Manifold Key over Giant's Boulder | screen20: full_preserve_mantle → full_preserve_mantle_2keys | +1.39 | -3.35 to +6.13 | 72 |
| Pentad Prism over Hardlight Containment | screen20: legal_four_rainbow → four_rainbow_plus_prism | +0.00 | -5.48 to +5.48 | 72 |
| Voltaic Key over Lunarch Mantle | screen20: four_rainbow_plus_prism → full_basalt_instead_boulder | +0.00 | -3.88 to +3.88 | 72 |
| Candelabra of Tawnos over Lunarch Mantle | screen20: four_rainbow_plus_prism → full_basalt_and_candelabra | +0.00 | -6.71 to +6.71 | 72 |
| Basalt Monolith over Giant's Boulder | screen20: full_prism_voltaic_boulder → full_basalt_instead_boulder | +0.00 | -3.88 to +3.88 | 72 |
| Plains over Voltaic Key | screen20: full_prism_voltaic_boulder → full_35lands_instead_voltaic | +0.00 | -3.88 to +3.88 | 72 |
| Candelabra of Tawnos over Voltaic Key | screen20: full_basalt_instead_boulder → full_basalt_and_candelabra | +0.00 | -5.48 to +5.48 | 72 |
| Lunarch Mantle over Manifold Key | screen20: full_3keys_instead_tooth → full_preserve_mantle | +0.00 | +0.00 to +0.00 | 72 |
| Lunarch Mantle over Voltaic Key | screen20: full_candelabra_instead_tooth → full_preserve_mantle_candelabra | +0.00 | -5.48 to +5.48 | 72 |
| Pentad Prism over Implements of Sacrifice | screen20: current → prism_only | -1.39 | -6.13 to +3.35 | 72 |
| Basalt Monolith over Pentad Prism | screen20: full_prism_voltaic_boulder → full_basalt_instead_prism | -1.39 | -6.13 to +3.35 | 72 |
| Manifold Key over Tooth of Ramos | screen20: full_prism_voltaic_boulder → full_3keys_instead_tooth | -1.39 | -6.13 to +3.35 | 72 |
| Lunarch Mantle over Tooth of Ramos | screen20: full_prism_voltaic_boulder → full_preserve_mantle | -1.39 | -6.13 to +3.35 | 72 |
| Plains over Candelabra of Tawnos | screen20: full_prism_candelabra_boulder → full_35lands_instead_voltaic | -1.39 | -4.11 to +1.33 | 72 |
| Basalt Monolith over Giant's Boulder | screen20: full_prism_candelabra_boulder → full_basalt_and_candelabra | -1.39 | -6.13 to +3.35 | 72 |
| Giant's Boulder over Pentad Prism | screen20: full_basalt_instead_boulder → full_basalt_instead_prism | -1.39 | -6.13 to +3.35 | 72 |
| Lunarch Mantle over Tooth of Ramos | screen20: full_2keys_instead_boulder → full_preserve_mantle_2keys | -1.39 | -6.13 to +3.35 | 72 |
| Giant's Boulder over Tooth of Ramos | screen20: full_2keys_instead_boulder → full_3keys_instead_tooth | -2.78 | -9.46 to +3.91 | 72 |
| Candelabra of Tawnos over Manifold Key | screen20: current_2keys → current_voltaic_candelabra | -2.78 | -8.22 to +2.67 | 72 |
| Candelabra of Tawnos over Manifold Key | screen20: full_3keys_instead_tooth → full_candelabra_instead_tooth | -4.17 | -10.22 to +1.89 | 72 |
| Candelabra of Tawnos over Voltaic Key | screen20: full_preserve_mantle → full_preserve_mantle_candelabra | -4.17 | -11.35 to +3.02 | 72 |
| Candelabra of Tawnos over Tooth of Ramos | screen20: full_prism_voltaic_boulder → full_candelabra_instead_tooth | -5.56 | -12.14 to +1.03 | 72 |
| Voltaic Key over Tooth of Ramos | screen20: full_prism_candelabra_boulder → full_candelabra_instead_tooth | -6.94 | -12.86 to -1.03 | 72 |
| Lunarch Mantle over Tooth of Ramos | screen20: full_prism_candelabra_boulder → full_preserve_mantle_candelabra | -6.94 | -12.86 to -1.03 | 72 |

## Historical controls — Standard mulligans only

- The old 256-game held-out six-arm screen had **double-Key** at 48.83% by T2 versus 45.31% for the baseline; paired difference +3.52 pp with 95% CI [-0.138, 7.169]. The interval crosses zero.
- The old 128-game Key vs Candelabra direct swap had Voltaic Key at 47.66% by T2 and Candelabra at 46.09%; also not a settled ranking.

## What's not ranked yet

Some powerful rocks are present in every test deck and consequently have no controlled 'card absent' comparator in these screens. Their omission from the rankings **does not mean they are weak**. Dedicated same-slot replacement tests are needed for: Sol Ring, Mana Vault, Grim Monolith, Lion's Eye Diamond, Chrome Mox, Mox Diamond, Mox Opal, Lotus Petal, Ancient Tomb, City of Traitors, Crystal Vein, Mishra's Workshop, Moonsilver Key, Coalition Relic, Everflowing Chalice, Jeweled Amulet, Arcane Signet, Fellwar Stone, Mind Stone, The Mind Stone, World Map.

**Promotion rule:** No deck cut is decided by this leaderboard. Identify repeatable T2-leading combinations, separately verify full combo functionality and multiplayer constraints, then run independent held-out paired tests.
