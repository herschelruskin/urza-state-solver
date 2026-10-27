# Dack Assertive ramp-piece leaderboard

**LIVE SCREENING STATUS — not a finalized card ranking.** The provisional table only appears once at least 24 completed matched games from a screen are available. Both screens preserve the same frozen Assertive mulligan policy, and all numbers are conditional on the optimistic goldfish Dack-cast model.

| Trial | Games recovered | Completed shards | Data status |
|---|---:|---:|---|
| screen20 | 112/256 | 28/64 | Partial exploratory evidence |
| flex41 | 38/128 | 19/64 | Partial exploratory evidence |

---


**Primary metric:** probability of Dack cast by T2 under the promoted Assertive London policy, with T1 and T3 tracked as checks.

> All results are optimistic full-beam goldfish Dack-cast rates, not verified complete combo lines or multiplayer wins. Small-sample rankings are exploratory and susceptible to winner's curse.

## Live evidence status

- **screen20**: PARTIAL_112_OF_256, 20 decks × 256 matched game IDs — https://github.com/herschelruskin/urza-state-solver/actions/runs/40444150025
- **flex41**: PARTIAL_38_OF_128, 41 decks × 128 matched game IDs — https://github.com/herschelruskin/urza-state-solver/actions/runs/40445020227

## Ramp-card ranking (only controlled single-card comparisons)

| Rank | Card | Observed context-weighted T2 signal (pp) | Matched contexts | Trial sets | Positive / negative contexts |
|---:|---|---:|---:|---:|---:|
| 1 | Tooth of Ramos | +2.08 | 18 | 2 | 11 / 5 |
| 2 | Giant's Boulder | +1.67 | 32 | 2 | 18 / 7 |
| 3 | Plains | +1.08 | 52 | 2 | 24 / 17 |
| 4 | Hardlight Containment | +0.89 | 1 | 1 | 1 / 0 |
| 5 | Manifold Key | +0.73 | 37 | 2 | 19 / 10 |
| 6 | Implements of Sacrifice | +0.00 | 1 | 1 | 0 / 0 |
| 7 | Pentad Prism | -0.09 | 22 | 2 | 6 / 8 |
| 8 | Voltaic Key | -0.65 | 27 | 2 | 8 / 13 |
| 9 | World Map | -0.82 | 29 | 1 | 11 / 11 |
| 10 | Lunarch Mantle | -0.91 | 20 | 2 | 7 / 10 |
| 11 | Basalt Monolith | -1.12 | 37 | 2 | 10 / 18 |
| 12 | Candelabra of Tawnos | -2.53 | 24 | 2 | 3 / 19 |

**Interpretation:** The score averages results across the *observed replacement options and deck backgrounds*, not the intrinsic value of a card. Contexts share hands and games; the displayed score has **no valid pooled confidence interval**. Strong claims require a held-out card comparison.

## Leading one-slot head-to-head comparisons

| New card over old | Background | Δ T2 (pp) | Paired 95% CI (pp) | n |
|---|---|---:|---|---:|
| Plains over World Map | flex41: current33_pentad_prism → current_map_to_pentad_prism | +10.53 | +0.64 to +20.42 | 38 |
| Giant's Boulder over Pentad Prism | flex41: full35_minus_giants_boulder → full35_minus_pentad_prism | +10.53 | -1.82 to +22.87 | 38 |
| Pentad Prism over Voltaic Key | flex41: current_map_to_voltaic_key → current_map_to_pentad_prism | +10.53 | +0.64 to +20.42 | 38 |
| Pentad Prism over World Map | flex41: current → current_map_to_pentad_prism | +7.89 | -0.79 to +16.58 | 38 |
| Plains over Basalt Monolith | flex41: current33_pentad_prism → current_basalt_to_pentad_prism | +7.89 | -3.51 to +19.30 | 38 |
| Voltaic Key over Pentad Prism | flex41: full35_minus_voltaic_key → full35_minus_pentad_prism | +7.89 | -0.79 to +16.58 | 38 |
| Giant's Boulder over World Map | flex41: full35_minus_giants_boulder → full35_minus_world_map | +7.89 | -5.70 to +21.49 | 38 |
| Plains over Voltaic Key | flex41: safe35_minus_giants_boulder → safe36_no_key_boulder | +7.89 | -0.79 to +16.58 | 38 |
| Basalt Monolith over Plains | flex41: safe35_minus_giants_boulder → safe_boulder_to_basalt | +7.89 | -3.51 to +19.30 | 38 |
| World Map over Basalt Monolith | flex41: current_map_to_voltaic_key → current_basalt_to_voltaic_key | +7.89 | -5.70 to +21.49 | 38 |
| Manifold Key over Candelabra of Tawnos | flex41: current_basalt_to_candelabra_of_tawnos → current_basalt_to_manifold_key | +7.89 | -3.51 to +19.30 | 38 |
| Plains over World Map | flex41: current → current35_minus_world_map | +5.26 | -5.05 to +15.58 | 38 |
| Plains over Basalt Monolith | flex41: current → current35_minus_basalt_monolith | +5.26 | -7.43 to +17.95 | 38 |
| Pentad Prism over Basalt Monolith | flex41: current → current_basalt_to_pentad_prism | +5.26 | -7.43 to +17.95 | 38 |
| Voltaic Key over Basalt Monolith | flex41: current → current_basalt_to_voltaic_key | +5.26 | -7.43 to +17.95 | 38 |
| Manifold Key over Basalt Monolith | flex41: current → current_basalt_to_manifold_key | +5.26 | -5.05 to +15.58 | 38 |
| Giant's Boulder over World Map | flex41: full_double_keys → full_map_to_manifold_key | +5.26 | -5.05 to +15.58 | 38 |
| Giant's Boulder over World Map | flex41: full_basalt_over_boulder → full_map_to_basalt_monolith | +5.26 | -5.05 to +15.58 | 38 |
| Plains over World Map | flex41: full33_candelabra_of_tawnos → full_map_to_candelabra_of_tawnos | +5.26 | -7.43 to +17.95 | 38 |
| Plains over World Map | flex41: full33_basalt_monolith → full_map_to_basalt_monolith | +5.26 | -7.43 to +17.95 | 38 |
| Manifold Key over Pentad Prism | flex41: current33_pentad_prism → current33_manifold_key | +5.26 | -1.93 to +12.46 | 38 |
| Voltaic Key over World Map | flex41: full35_minus_voltaic_key → full35_minus_world_map | +5.26 | -1.93 to +12.46 | 38 |
| Lunarch Mantle over Candelabra of Tawnos | screen20: full_candelabra_instead_tooth → full_preserve_mantle | +2.68 | -1.95 to +7.30 | 112 |
| Voltaic Key over Plains | flex41: current → current33_voltaic_key | +2.63 | -2.53 to +7.79 | 38 |
| Manifold Key over Plains | flex41: current → current33_manifold_key | +2.63 | -2.53 to +7.79 | 38 |
| Plains over Voltaic Key | flex41: full_preserve_mantle → safe35_minus_voltaic_key | +2.63 | -6.38 to +11.65 | 38 |
| Basalt Monolith over Giant's Boulder | flex41: full_preserve_mantle → safe_boulder_to_basalt | +2.63 | -2.53 to +7.79 | 38 |
| Giant's Boulder over Plains | flex41: full_double_keys → full33_manifold_key | +2.63 | -9.03 to +14.29 | 38 |
| Basalt Monolith over Plains | flex41: full_double_keys → full33_manifold_boulder_to_basalt | +2.63 | -9.03 to +14.29 | 38 |
| Lunarch Mantle over Tooth of Ramos | flex41: full_basalt_over_boulder → safe_boulder_to_basalt | +2.63 | -9.03 to +14.29 | 38 |

## Historical controls — Standard mulligans only

- The old 256-game held-out six-arm screen had **double-Key** at 48.83% by T2 versus 45.31% for the baseline; paired difference +3.52 pp with 95% CI [-0.138, 7.169]. The interval crosses zero.
- The old 128-game Key vs Candelabra direct swap had Voltaic Key at 47.66% by T2 and Candelabra at 46.09%; also not a settled ranking.

## What's not ranked yet

Some powerful rocks are present in every test deck and consequently have no controlled 'card absent' comparator in these screens. Their omission from the rankings **does not mean they are weak**. Dedicated same-slot replacement tests are needed for: Sol Ring, Mana Vault, Grim Monolith, Lion's Eye Diamond, Chrome Mox, Mox Diamond, Mox Opal, Lotus Petal, Ancient Tomb, City of Traitors, Crystal Vein, Mishra's Workshop, Moonsilver Key, Coalition Relic, Everflowing Chalice, Jeweled Amulet, Arcane Signet, Fellwar Stone, Mind Stone, The Mind Stone.

**Promotion rule:** No deck cut is decided by this leaderboard. Identify repeatable T2-leading combinations, separately verify full combo functionality and multiplayer constraints, then run independent held-out paired tests.
