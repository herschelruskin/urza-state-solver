# Dack Assertive ramp-piece leaderboard

**LIVE SCREENING STATUS — not a finalized card ranking.** The provisional table only appears once at least 24 completed matched games from a screen are available. Both screens preserve the same frozen Assertive mulligan policy, and all numbers are conditional on the optimistic goldfish Dack-cast model.

| Trial | Games recovered | Completed shards | Data status |
|---|---:|---:|---|
| screen20 | 252/256 | 63/64 | Partial exploratory evidence |
| flex41 | 70/128 | 35/64 | Partial exploratory evidence |

---


**Primary metric:** probability of Dack cast by T2 under the promoted Assertive London policy, with T1 and T3 tracked as checks.

> All results are optimistic full-beam goldfish Dack-cast rates, not verified complete combo lines or multiplayer wins. Small-sample rankings are exploratory and susceptible to winner's curse.

## Live evidence status

- **screen20**: PARTIAL_252_OF_256, 20 decks × 256 matched game IDs — https://github.com/herschelruskin/urza-state-solver/actions/runs/40444150025
- **flex41**: PARTIAL_70_OF_128, 41 decks × 128 matched game IDs — https://github.com/herschelruskin/urza-state-solver/actions/runs/40445020227

## Ramp-card ranking (only controlled single-card comparisons)

| Rank | Card | Observed context-weighted T2 signal (pp) | Matched contexts | Trial sets | Positive / negative contexts |
|---:|---|---:|---:|---:|---:|
| 1 | Giant's Boulder | +1.25 | 32 | 2 | 21 / 11 |
| 2 | Plains | +1.10 | 52 | 2 | 30 / 17 |
| 3 | Voltaic Key | +1.07 | 27 | 2 | 16 / 8 |
| 4 | Hardlight Containment | +0.79 | 1 | 1 | 1 / 0 |
| 5 | Tooth of Ramos | +0.75 | 18 | 2 | 11 / 6 |
| 6 | Pentad Prism | +0.13 | 22 | 2 | 10 / 9 |
| 7 | Manifold Key | +0.10 | 37 | 2 | 16 / 16 |
| 8 | Basalt Monolith | -0.06 | 37 | 2 | 17 / 17 |
| 9 | Lunarch Mantle | -0.53 | 20 | 2 | 6 / 13 |
| 10 | World Map | -0.84 | 29 | 1 | 9 / 17 |
| 11 | Implements of Sacrifice | -1.98 | 1 | 1 | 0 / 1 |
| 12 | Candelabra of Tawnos | -3.32 | 24 | 2 | 0 / 22 |

**Interpretation:** The score averages results across the *observed replacement options and deck backgrounds*, not the intrinsic value of a card. Contexts share hands and games; the displayed score has **no valid pooled confidence interval**. Strong claims require a held-out card comparison.

## Leading one-slot head-to-head comparisons

| New card over old | Background | Δ T2 (pp) | Paired 95% CI (pp) | n |
|---|---|---:|---|---:|
| Voltaic Key over Pentad Prism | flex41: full35_minus_voltaic_key → full35_minus_pentad_prism | +8.57 | +1.97 to +15.18 | 70 |
| Basalt Monolith over Plains | flex41: safe35_minus_giants_boulder → safe_boulder_to_basalt | +8.57 | +0.86 to +16.29 | 70 |
| Plains over Voltaic Key | flex41: safe35_minus_giants_boulder → safe36_no_key_boulder | +7.14 | +1.07 to +13.22 | 70 |
| Basalt Monolith over Giant's Boulder | flex41: full_preserve_mantle → safe_boulder_to_basalt | +5.71 | +0.24 to +11.19 | 70 |
| Plains over World Map | flex41: full33_candelabra_of_tawnos → full_map_to_candelabra_of_tawnos | +5.71 | -3.96 to +15.39 | 70 |
| Plains over World Map | flex41: full33_basalt_monolith → full_map_to_basalt_monolith | +5.71 | -3.10 to +14.53 | 70 |
| Manifold Key over Pentad Prism | flex41: current33_pentad_prism → current33_manifold_key | +5.71 | +0.24 to +11.19 | 70 |
| Plains over World Map | flex41: current33_pentad_prism → current_map_to_pentad_prism | +5.71 | +0.24 to +11.19 | 70 |
| Giant's Boulder over Pentad Prism | flex41: full35_minus_giants_boulder → full35_minus_pentad_prism | +5.71 | -1.06 to +12.49 | 70 |
| Manifold Key over Plains | flex41: current → current33_manifold_key | +4.29 | -0.49 to +9.06 | 70 |
| Plains over Basalt Monolith | flex41: current → current35_minus_basalt_monolith | +4.29 | -3.11 to +11.68 | 70 |
| Pentad Prism over World Map | flex41: current → current_map_to_pentad_prism | +4.29 | -1.94 to +10.51 | 70 |
| Plains over Basalt Monolith | flex41: current33_pentad_prism → current_basalt_to_pentad_prism | +4.29 | -1.94 to +10.51 | 70 |
| Voltaic Key over World Map | flex41: full35_minus_voltaic_key → full35_minus_world_map | +4.29 | -0.49 to +9.06 | 70 |
| Lunarch Mantle over Tooth of Ramos | flex41: full35_minus_voltaic_key → safe35_minus_voltaic_key | +4.29 | -0.49 to +9.06 | 70 |
| Lunarch Mantle over Tooth of Ramos | flex41: full36_no_key_boulder → safe36_no_key_boulder | +4.29 | -3.11 to +11.68 | 70 |
| Pentad Prism over Voltaic Key | flex41: current_map_to_voltaic_key → current_map_to_pentad_prism | +4.29 | -3.11 to +11.68 | 70 |
| Lunarch Mantle over Candelabra of Tawnos | screen20: full_candelabra_instead_tooth → full_preserve_mantle | +3.97 | +0.18 to +7.75 | 252 |
| Giant's Boulder over Tooth of Ramos | screen20: full_2keys_instead_boulder → full_3keys_instead_tooth | +3.57 | -0.45 to +7.60 | 252 |
| Plains over World Map | flex41: current → current35_minus_world_map | +2.86 | -4.02 to +9.73 | 70 |
| Pentad Prism over Basalt Monolith | flex41: current → current_basalt_to_pentad_prism | +2.86 | -5.09 to +10.81 | 70 |
| Voltaic Key over Basalt Monolith | flex41: current → current_basalt_to_voltaic_key | +2.86 | -5.09 to +10.81 | 70 |
| Manifold Key over Basalt Monolith | flex41: current → current_basalt_to_manifold_key | +2.86 | -4.02 to +9.73 | 70 |
| Plains over Voltaic Key | flex41: full_preserve_mantle → safe35_minus_voltaic_key | +2.86 | -2.74 to +8.46 | 70 |
| Basalt Monolith over World Map | flex41: full_preserve_mantle → safe_map_to_basalt_monolith | +2.86 | -5.09 to +10.81 | 70 |
| Giant's Boulder over World Map | flex41: full_double_keys → full_map_to_manifold_key | +2.86 | -4.02 to +9.73 | 70 |
| Giant's Boulder over World Map | flex41: full_basalt_over_boulder → full_map_to_basalt_monolith | +2.86 | -4.02 to +9.73 | 70 |
| Lunarch Mantle over Tooth of Ramos | flex41: full_basalt_over_boulder → safe_boulder_to_basalt | +2.86 | -4.02 to +9.73 | 70 |
| Basalt Monolith over Candelabra of Tawnos | flex41: full33_candelabra_of_tawnos → full33_basalt_monolith | +2.86 | -2.74 to +8.46 | 70 |
| Plains over World Map | flex41: safe33_manifold_key → safe_map_to_manifold_key | +2.86 | -6.04 to +11.75 | 70 |

## Historical controls — Standard mulligans only

- The old 256-game held-out six-arm screen had **double-Key** at 48.83% by T2 versus 45.31% for the baseline; paired difference +3.52 pp with 95% CI [-0.138, 7.169]. The interval crosses zero.
- The old 128-game Key vs Candelabra direct swap had Voltaic Key at 47.66% by T2 and Candelabra at 46.09%; also not a settled ranking.

## What's not ranked yet

Some powerful rocks are present in every test deck and consequently have no controlled 'card absent' comparator in these screens. Their omission from the rankings **does not mean they are weak**. Dedicated same-slot replacement tests are needed for: Sol Ring, Mana Vault, Grim Monolith, Lion's Eye Diamond, Chrome Mox, Mox Diamond, Mox Opal, Lotus Petal, Ancient Tomb, City of Traitors, Crystal Vein, Mishra's Workshop, Moonsilver Key, Coalition Relic, Everflowing Chalice, Jeweled Amulet, Arcane Signet, Fellwar Stone, Mind Stone, The Mind Stone.

**Promotion rule:** No deck cut is decided by this leaderboard. Identify repeatable T2-leading combinations, separately verify full combo functionality and multiplayer constraints, then run independent held-out paired tests.
