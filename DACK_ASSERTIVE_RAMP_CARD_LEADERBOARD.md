# Dack Assertive ramp-piece leaderboard

**LIVE SCREENING STATUS — not a finalized card ranking.** The provisional table only appears once at least 24 completed matched games from a screen are available. Both screens preserve the same frozen Assertive mulligan policy, and all numbers are conditional on the optimistic goldfish Dack-cast model.

| Trial | Games recovered | Completed shards | Data status |
|---|---:|---:|---|
| screen20 | 204/256 | 51/64 | Partial exploratory evidence |
| flex41 | 52/128 | 26/64 | Partial exploratory evidence |

---


**Primary metric:** probability of Dack cast by T2 under the promoted Assertive London policy, with T1 and T3 tracked as checks.

> All results are optimistic full-beam goldfish Dack-cast rates, not verified complete combo lines or multiplayer wins. Small-sample rankings are exploratory and susceptible to winner's curse.

## Live evidence status

- **screen20**: PARTIAL_204_OF_256, 20 decks × 256 matched game IDs — https://github.com/herschelruskin/urza-state-solver/actions/runs/40444150025
- **flex41**: PARTIAL_52_OF_128, 41 decks × 128 matched game IDs — https://github.com/herschelruskin/urza-state-solver/actions/runs/40445020227

## Ramp-card ranking (only controlled single-card comparisons)

| Rank | Card | Observed context-weighted T2 signal (pp) | Matched contexts | Trial sets | Positive / negative contexts |
|---:|---|---:|---:|---:|---:|
| 1 | Giant's Boulder | +1.72 | 32 | 2 | 20 / 8 |
| 2 | Plains | +1.60 | 52 | 2 | 29 / 14 |
| 3 | Hardlight Containment | +1.47 | 1 | 1 | 1 / 0 |
| 4 | Tooth of Ramos | +1.15 | 18 | 2 | 13 / 5 |
| 5 | Voltaic Key | +0.81 | 27 | 2 | 15 / 10 |
| 6 | Manifold Key | +0.44 | 37 | 2 | 18 / 14 |
| 7 | Pentad Prism | +0.23 | 22 | 2 | 9 / 10 |
| 8 | World Map | -0.86 | 29 | 1 | 11 / 15 |
| 9 | Basalt Monolith | -1.11 | 37 | 2 | 12 / 18 |
| 10 | Lunarch Mantle | -1.20 | 20 | 2 | 5 / 15 |
| 11 | Implements of Sacrifice | -1.96 | 1 | 1 | 0 / 1 |
| 12 | Candelabra of Tawnos | -3.21 | 24 | 2 | 0 / 23 |

**Interpretation:** The score averages results across the *observed replacement options and deck backgrounds*, not the intrinsic value of a card. Contexts share hands and games; the displayed score has **no valid pooled confidence interval**. Strong claims require a held-out card comparison.

## Leading one-slot head-to-head comparisons

| New card over old | Background | Δ T2 (pp) | Paired 95% CI (pp) | n |
|---|---|---:|---|---:|
| Pentad Prism over Voltaic Key | flex41: current_map_to_voltaic_key → current_map_to_pentad_prism | +9.62 | +1.52 to +17.71 | 52 |
| World Map over Basalt Monolith | flex41: current_map_to_voltaic_key → current_basalt_to_voltaic_key | +9.62 | -1.49 to +20.72 | 52 |
| Plains over World Map | flex41: full33_basalt_monolith → full_map_to_basalt_monolith | +7.69 | -2.86 to +18.25 | 52 |
| Plains over World Map | flex41: current33_pentad_prism → current_map_to_pentad_prism | +7.69 | +0.38 to +15.01 | 52 |
| Giant's Boulder over Pentad Prism | flex41: full35_minus_giants_boulder → full35_minus_pentad_prism | +7.69 | -1.39 to +16.77 | 52 |
| Plains over Basalt Monolith | flex41: current → current35_minus_basalt_monolith | +5.77 | -4.18 to +15.71 | 52 |
| Pentad Prism over World Map | flex41: current → current_map_to_pentad_prism | +5.77 | -2.59 to +14.13 | 52 |
| Voltaic Key over Basalt Monolith | flex41: current → current_basalt_to_voltaic_key | +5.77 | -4.18 to +15.71 | 52 |
| Manifold Key over Basalt Monolith | flex41: current → current_basalt_to_manifold_key | +5.77 | -2.59 to +14.13 | 52 |
| Giant's Boulder over World Map | flex41: full_basalt_over_boulder → full_map_to_basalt_monolith | +5.77 | -2.59 to +14.13 | 52 |
| Plains over World Map | flex41: full33_candelabra_of_tawnos → full_map_to_candelabra_of_tawnos | +5.77 | -4.18 to +15.71 | 52 |
| Manifold Key over Pentad Prism | flex41: current33_pentad_prism → current33_manifold_key | +5.77 | -0.63 to +12.17 | 52 |
| Plains over Basalt Monolith | flex41: current33_pentad_prism → current_basalt_to_pentad_prism | +5.77 | -2.59 to +14.13 | 52 |
| Voltaic Key over Pentad Prism | flex41: full35_minus_voltaic_key → full35_minus_pentad_prism | +5.77 | -0.63 to +12.17 | 52 |
| Giant's Boulder over World Map | flex41: full35_minus_giants_boulder → full35_minus_world_map | +5.77 | -4.18 to +15.71 | 52 |
| Plains over Voltaic Key | flex41: safe35_minus_giants_boulder → safe36_no_key_boulder | +5.77 | -0.63 to +12.17 | 52 |
| Basalt Monolith over Plains | flex41: safe35_minus_giants_boulder → safe_boulder_to_basalt | +5.77 | -2.59 to +14.13 | 52 |
| Manifold Key over Candelabra of Tawnos | flex41: current_basalt_to_candelabra_of_tawnos → current_basalt_to_manifold_key | +5.77 | -2.59 to +14.13 | 52 |
| Manifold Key over Plains | flex41: current → current33_manifold_key | +3.85 | -1.43 to +9.12 | 52 |
| Plains over World Map | flex41: current → current35_minus_world_map | +3.85 | -5.42 to +13.11 | 52 |
| Pentad Prism over Basalt Monolith | flex41: current → current_basalt_to_pentad_prism | +3.85 | -6.87 to +14.56 | 52 |
| Giant's Boulder over World Map | flex41: full_double_keys → full_map_to_manifold_key | +3.85 | -3.69 to +11.38 | 52 |
| Plains over World Map | flex41: full33_manifold_key → full_map_to_manifold_key | +3.85 | -5.42 to +13.11 | 52 |
| Plains over Giant's Boulder | flex41: safe33_manifold_key → safe_boulder_to_manifold | +3.85 | -6.87 to +14.56 | 52 |
| Plains over Basalt Monolith | flex41: current33_voltaic_key → current_basalt_to_voltaic_key | +3.85 | -5.42 to +13.11 | 52 |
| Voltaic Key over World Map | flex41: full35_minus_voltaic_key → full35_minus_world_map | +3.85 | -1.43 to +9.12 | 52 |
| Basalt Monolith over Candelabra of Tawnos | flex41: full_map_to_candelabra_of_tawnos → full_map_to_basalt_monolith | +3.85 | -1.43 to +9.12 | 52 |
| Basalt Monolith over Manifold Key | flex41: safe_map_to_manifold_key → safe_map_to_basalt_monolith | +3.85 | -3.69 to +11.38 | 52 |
| Giant's Boulder over Tooth of Ramos | screen20: full_2keys_instead_boulder → full_3keys_instead_tooth | +2.94 | -1.12 to +7.01 | 204 |
| Lunarch Mantle over Candelabra of Tawnos | screen20: full_candelabra_instead_tooth → full_preserve_mantle | +2.94 | -1.12 to +7.01 | 204 |

## Historical controls — Standard mulligans only

- The old 256-game held-out six-arm screen had **double-Key** at 48.83% by T2 versus 45.31% for the baseline; paired difference +3.52 pp with 95% CI [-0.138, 7.169]. The interval crosses zero.
- The old 128-game Key vs Candelabra direct swap had Voltaic Key at 47.66% by T2 and Candelabra at 46.09%; also not a settled ranking.

## What's not ranked yet

Some powerful rocks are present in every test deck and consequently have no controlled 'card absent' comparator in these screens. Their omission from the rankings **does not mean they are weak**. Dedicated same-slot replacement tests are needed for: Sol Ring, Mana Vault, Grim Monolith, Lion's Eye Diamond, Chrome Mox, Mox Diamond, Mox Opal, Lotus Petal, Ancient Tomb, City of Traitors, Crystal Vein, Mishra's Workshop, Moonsilver Key, Coalition Relic, Everflowing Chalice, Jeweled Amulet, Arcane Signet, Fellwar Stone, Mind Stone, The Mind Stone.

**Promotion rule:** No deck cut is decided by this leaderboard. Identify repeatable T2-leading combinations, separately verify full combo functionality and multiplayer constraints, then run independent held-out paired tests.
