# Dack Assertive ramp-piece leaderboard

**LIVE SCREENING STATUS — not a finalized card ranking.** The provisional table only appears once at least 24 completed matched games from a screen are available. Both screens preserve the same frozen Assertive mulligan policy, and all numbers are conditional on the optimistic goldfish Dack-cast model.

| Trial | Games recovered | Completed shards | Data status |
|---|---:|---:|---|
| screen20 | 180/256 | 45/64 | Partial exploratory evidence |
| flex41 | 46/128 | 23/64 | Partial exploratory evidence |

---


**Primary metric:** probability of Dack cast by T2 under the promoted Assertive London policy, with T1 and T3 tracked as checks.

> All results are optimistic full-beam goldfish Dack-cast rates, not verified complete combo lines or multiplayer wins. Small-sample rankings are exploratory and susceptible to winner's curse.

## Live evidence status

- **screen20**: PARTIAL_180_OF_256, 20 decks × 256 matched game IDs — https://github.com/herschelruskin/urza-state-solver/actions/runs/40444150025
- **flex41**: PARTIAL_46_OF_128, 41 decks × 128 matched game IDs — https://github.com/herschelruskin/urza-state-solver/actions/runs/40445020227

## Ramp-card ranking (only controlled single-card comparisons)

| Rank | Card | Observed context-weighted T2 signal (pp) | Matched contexts | Trial sets | Positive / negative contexts |
|---:|---|---:|---:|---:|---:|
| 1 | Hardlight Containment | +1.67 | 1 | 1 | 1 / 0 |
| 2 | Plains | +1.43 | 52 | 2 | 25 / 13 |
| 3 | Tooth of Ramos | +1.36 | 18 | 2 | 13 / 5 |
| 4 | Giant's Boulder | +1.24 | 32 | 2 | 18 / 9 |
| 5 | Manifold Key | +0.83 | 37 | 2 | 18 / 10 |
| 6 | Pentad Prism | +0.58 | 22 | 2 | 8 / 6 |
| 7 | Voltaic Key | +0.50 | 27 | 2 | 13 / 9 |
| 8 | World Map | -0.82 | 29 | 1 | 11 / 11 |
| 9 | Lunarch Mantle | -1.27 | 20 | 2 | 5 / 15 |
| 10 | Basalt Monolith | -1.34 | 37 | 2 | 8 / 19 |
| 11 | Candelabra of Tawnos | -2.73 | 24 | 2 | 0 / 22 |
| 12 | Implements of Sacrifice | -3.33 | 1 | 1 | 0 / 1 |

**Interpretation:** The score averages results across the *observed replacement options and deck backgrounds*, not the intrinsic value of a card. Contexts share hands and games; the displayed score has **no valid pooled confidence interval**. Strong claims require a held-out card comparison.

## Leading one-slot head-to-head comparisons

| New card over old | Background | Δ T2 (pp) | Paired 95% CI (pp) | n |
|---|---|---:|---|---:|
| Pentad Prism over Voltaic Key | flex41: current_map_to_voltaic_key → current_map_to_pentad_prism | +10.87 | +1.78 to +19.96 | 46 |
| Pentad Prism over World Map | flex41: current → current_map_to_pentad_prism | +8.70 | +0.46 to +16.93 | 46 |
| Plains over World Map | flex41: current33_pentad_prism → current_map_to_pentad_prism | +8.70 | +0.46 to +16.93 | 46 |
| Giant's Boulder over Pentad Prism | flex41: full35_minus_giants_boulder → full35_minus_pentad_prism | +8.70 | -1.55 to +18.94 | 46 |
| World Map over Basalt Monolith | flex41: current_map_to_voltaic_key → current_basalt_to_voltaic_key | +8.70 | -3.22 to +20.61 | 46 |
| Plains over World Map | flex41: current → current35_minus_world_map | +6.52 | -2.92 to +15.96 | 46 |
| Plains over Basalt Monolith | flex41: current → current35_minus_basalt_monolith | +6.52 | -4.72 to +17.76 | 46 |
| Pentad Prism over Basalt Monolith | flex41: current → current_basalt_to_pentad_prism | +6.52 | -4.72 to +17.76 | 46 |
| Voltaic Key over Basalt Monolith | flex41: current → current_basalt_to_voltaic_key | +6.52 | -4.72 to +17.76 | 46 |
| Manifold Key over Basalt Monolith | flex41: current → current_basalt_to_manifold_key | +6.52 | -2.92 to +15.96 | 46 |
| Plains over World Map | flex41: full33_candelabra_of_tawnos → full_map_to_candelabra_of_tawnos | +6.52 | -4.72 to +17.76 | 46 |
| Plains over World Map | flex41: full33_basalt_monolith → full_map_to_basalt_monolith | +6.52 | -4.72 to +17.76 | 46 |
| Plains over Basalt Monolith | flex41: current33_pentad_prism → current_basalt_to_pentad_prism | +6.52 | -2.92 to +15.96 | 46 |
| Voltaic Key over Pentad Prism | flex41: full35_minus_voltaic_key → full35_minus_pentad_prism | +6.52 | -0.69 to +13.74 | 46 |
| Giant's Boulder over World Map | flex41: full35_minus_giants_boulder → full35_minus_world_map | +6.52 | -4.72 to +17.76 | 46 |
| Plains over Voltaic Key | flex41: safe35_minus_giants_boulder → safe36_no_key_boulder | +6.52 | -0.69 to +13.74 | 46 |
| Basalt Monolith over Plains | flex41: safe35_minus_giants_boulder → safe_boulder_to_basalt | +6.52 | -2.92 to +15.96 | 46 |
| Manifold Key over Candelabra of Tawnos | flex41: current_basalt_to_candelabra_of_tawnos → current_basalt_to_manifold_key | +6.52 | -2.92 to +15.96 | 46 |
| Voltaic Key over Plains | flex41: current → current33_voltaic_key | +4.35 | -1.61 to +10.31 | 46 |
| Manifold Key over Plains | flex41: current → current33_manifold_key | +4.35 | -1.61 to +10.31 | 46 |
| Giant's Boulder over World Map | flex41: full_double_keys → full_map_to_manifold_key | +4.35 | -4.17 to +12.87 | 46 |
| Giant's Boulder over World Map | flex41: full_basalt_over_boulder → full_map_to_basalt_monolith | +4.35 | -4.17 to +12.87 | 46 |
| Plains over World Map | flex41: full33_manifold_key → full_map_to_manifold_key | +4.35 | -6.13 to +14.82 | 46 |
| Manifold Key over Pentad Prism | flex41: current33_pentad_prism → current33_manifold_key | +4.35 | -1.61 to +10.31 | 46 |
| Voltaic Key over World Map | flex41: full35_minus_voltaic_key → full35_minus_world_map | +4.35 | -1.61 to +10.31 | 46 |
| Basalt Monolith over Manifold Key | flex41: safe_map_to_manifold_key → safe_map_to_basalt_monolith | +4.35 | -4.17 to +12.87 | 46 |
| Pentad Prism over Implements of Sacrifice | screen20: current → prism_only | +3.33 | -0.08 to +6.75 | 180 |
| Plains over Voltaic Key | flex41: full_preserve_mantle → safe35_minus_voltaic_key | +2.17 | -5.26 to +9.61 | 46 |
| Basalt Monolith over Giant's Boulder | flex41: full_preserve_mantle → safe_boulder_to_basalt | +2.17 | -2.09 to +6.43 | 46 |
| Lunarch Mantle over Tooth of Ramos | flex41: full_basalt_over_boulder → safe_boulder_to_basalt | +2.17 | -7.44 to +11.79 | 46 |

## Historical controls — Standard mulligans only

- The old 256-game held-out six-arm screen had **double-Key** at 48.83% by T2 versus 45.31% for the baseline; paired difference +3.52 pp with 95% CI [-0.138, 7.169]. The interval crosses zero.
- The old 128-game Key vs Candelabra direct swap had Voltaic Key at 47.66% by T2 and Candelabra at 46.09%; also not a settled ranking.

## What's not ranked yet

Some powerful rocks are present in every test deck and consequently have no controlled 'card absent' comparator in these screens. Their omission from the rankings **does not mean they are weak**. Dedicated same-slot replacement tests are needed for: Sol Ring, Mana Vault, Grim Monolith, Lion's Eye Diamond, Chrome Mox, Mox Diamond, Mox Opal, Lotus Petal, Ancient Tomb, City of Traitors, Crystal Vein, Mishra's Workshop, Moonsilver Key, Coalition Relic, Everflowing Chalice, Jeweled Amulet, Arcane Signet, Fellwar Stone, Mind Stone, The Mind Stone.

**Promotion rule:** No deck cut is decided by this leaderboard. Identify repeatable T2-leading combinations, separately verify full combo functionality and multiplayer constraints, then run independent held-out paired tests.
