# Dack Assertive ramp-piece leaderboard

**LIVE SCREENING STATUS — not a finalized card ranking.** The provisional table only appears once at least 24 completed matched games from a screen are available. Both screens preserve the same frozen Assertive mulligan policy, and all numbers are conditional on the optimistic goldfish Dack-cast model.

| Trial | Games recovered | Completed shards | Data status |
|---|---:|---:|---|
| screen20 | 88/256 | 22/64 | Partial exploratory evidence |
| flex41 | 24/128 | 12/64 | Partial exploratory evidence |

---


**Primary metric:** probability of Dack cast by T2 under the promoted Assertive London policy, with T1 and T3 tracked as checks.

> All results are optimistic full-beam goldfish Dack-cast rates, not verified complete combo lines or multiplayer wins. Small-sample rankings are exploratory and susceptible to winner's curse.

## Live evidence status

- **screen20**: PARTIAL_88_OF_256, 20 decks × 256 matched game IDs — https://github.com/herschelruskin/urza-state-solver/actions/runs/40444150025
- **flex41**: PARTIAL_24_OF_128, 41 decks × 128 matched game IDs — https://github.com/herschelruskin/urza-state-solver/actions/runs/40445020227

## Ramp-card ranking (only controlled single-card comparisons)

| Rank | Card | Observed context-weighted T2 signal (pp) | Matched contexts | Trial sets | Positive / negative contexts |
|---:|---|---:|---:|---:|---:|
| 1 | Tooth of Ramos | +2.27 | 18 | 2 | 10 / 6 |
| 2 | Giant's Boulder | +1.32 | 32 | 2 | 17 / 6 |
| 3 | Hardlight Containment | +1.14 | 1 | 1 | 1 / 0 |
| 4 | Implements of Sacrifice | +1.14 | 1 | 1 | 1 / 0 |
| 5 | Pentad Prism | +1.02 | 22 | 2 | 9 / 7 |
| 6 | Plains | +0.58 | 52 | 2 | 20 / 19 |
| 7 | Voltaic Key | +0.46 | 27 | 2 | 12 / 10 |
| 8 | Manifold Key | +0.37 | 37 | 2 | 14 / 15 |
| 9 | Lunarch Mantle | -0.76 | 20 | 2 | 8 / 9 |
| 10 | World Map | -1.01 | 29 | 1 | 10 / 13 |
| 11 | Basalt Monolith | -2.01 | 37 | 2 | 8 / 17 |
| 12 | Candelabra of Tawnos | -2.26 | 24 | 2 | 6 / 14 |

**Interpretation:** The score averages results across the *observed replacement options and deck backgrounds*, not the intrinsic value of a card. Contexts share hands and games; the displayed score has **no valid pooled confidence interval**. Strong claims require a held-out card comparison.

## Leading one-slot head-to-head comparisons

| New card over old | Background | Δ T2 (pp) | Paired 95% CI (pp) | n |
|---|---|---:|---|---:|
| Plains over World Map | flex41: current → current35_minus_world_map | +12.50 | -1.02 to +26.02 | 24 |
| Pentad Prism over World Map | flex41: current → current_map_to_pentad_prism | +12.50 | -1.02 to +26.02 | 24 |
| Pentad Prism over Basalt Monolith | flex41: current → current_basalt_to_pentad_prism | +12.50 | -5.44 to +30.44 | 24 |
| Voltaic Key over Basalt Monolith | flex41: current → current_basalt_to_voltaic_key | +12.50 | -5.44 to +30.44 | 24 |
| Giant's Boulder over Plains | flex41: full_basalt_over_boulder → full33_basalt_monolith | +12.50 | -1.02 to +26.02 | 24 |
| Plains over World Map | flex41: current33_pentad_prism → current_map_to_pentad_prism | +12.50 | -1.02 to +26.02 | 24 |
| Plains over Basalt Monolith | flex41: current33_pentad_prism → current_basalt_to_pentad_prism | +12.50 | -5.44 to +30.44 | 24 |
| Voltaic Key over Pentad Prism | flex41: full35_minus_voltaic_key → full35_minus_pentad_prism | +12.50 | -1.02 to +26.02 | 24 |
| Pentad Prism over Voltaic Key | flex41: current_map_to_voltaic_key → current_map_to_pentad_prism | +12.50 | -1.02 to +26.02 | 24 |
| World Map over Basalt Monolith | flex41: current_map_to_voltaic_key → current_basalt_to_voltaic_key | +12.50 | -5.44 to +30.44 | 24 |
| Plains over Basalt Monolith | flex41: current → current35_minus_basalt_monolith | +8.33 | -11.82 to +28.48 | 24 |
| Manifold Key over Basalt Monolith | flex41: current → current_basalt_to_manifold_key | +8.33 | -8.00 to +24.67 | 24 |
| Plains over Basalt Monolith | flex41: full_basalt_over_boulder → full35_minus_giants_boulder | +8.33 | -8.00 to +24.67 | 24 |
| Giant's Boulder over World Map | flex41: full_basalt_over_boulder → full_map_to_basalt_monolith | +8.33 | -8.00 to +24.67 | 24 |
| Manifold Key over Plains | flex41: full_basalt_over_boulder → full33_manifold_boulder_to_basalt | +8.33 | -2.96 to +19.63 | 24 |
| Plains over Basalt Monolith | flex41: current33_voltaic_key → current_basalt_to_voltaic_key | +8.33 | -8.00 to +24.67 | 24 |
| Voltaic Key over Giant's Boulder | flex41: full35_minus_voltaic_key → full35_minus_giants_boulder | +8.33 | -11.82 to +28.48 | 24 |
| Voltaic Key over World Map | flex41: full35_minus_voltaic_key → full35_minus_world_map | +8.33 | -2.96 to +19.63 | 24 |
| Plains over Voltaic Key | flex41: safe35_minus_giants_boulder → safe36_no_key_boulder | +8.33 | -2.96 to +19.63 | 24 |
| Lunarch Mantle over Tooth of Ramos | flex41: full36_no_key_boulder → safe36_no_key_boulder | +8.33 | -8.00 to +24.67 | 24 |
| Manifold Key over Candelabra of Tawnos | flex41: current_basalt_to_candelabra_of_tawnos → current_basalt_to_manifold_key | +8.33 | -8.00 to +24.67 | 24 |
| Lunarch Mantle over Candelabra of Tawnos | screen20: full_candelabra_instead_tooth → full_preserve_mantle | +4.55 | -0.86 to +9.95 | 88 |
| Voltaic Key over Plains | flex41: current → current33_voltaic_key | +4.17 | -4.00 to +12.33 | 24 |
| Manifold Key over Plains | flex41: current → current33_manifold_key | +4.17 | -4.00 to +12.33 | 24 |
| Basalt Monolith over World Map | flex41: full_preserve_mantle → safe_map_to_basalt_monolith | +4.17 | -10.18 to +18.52 | 24 |
| Giant's Boulder over Plains | flex41: full_double_keys → full33_manifold_key | +4.17 | -10.18 to +18.52 | 24 |
| Plains over Manifold Key | flex41: full_double_keys → full35_minus_giants_boulder | +4.17 | -4.00 to +12.33 | 24 |
| Giant's Boulder over World Map | flex41: full_double_keys → full_map_to_manifold_key | +4.17 | -10.18 to +18.52 | 24 |
| Basalt Monolith over Plains | flex41: full_double_keys → full33_manifold_boulder_to_basalt | +4.17 | -10.18 to +18.52 | 24 |
| Lunarch Mantle over Tooth of Ramos | flex41: full_basalt_over_boulder → safe_boulder_to_basalt | +4.17 | -14.41 to +22.74 | 24 |

## Historical controls — Standard mulligans only

- The old 256-game held-out six-arm screen had **double-Key** at 48.83% by T2 versus 45.31% for the baseline; paired difference +3.52 pp with 95% CI [-0.138, 7.169]. The interval crosses zero.
- The old 128-game Key vs Candelabra direct swap had Voltaic Key at 47.66% by T2 and Candelabra at 46.09%; also not a settled ranking.

## What's not ranked yet

Some powerful rocks are present in every test deck and consequently have no controlled 'card absent' comparator in these screens. Their omission from the rankings **does not mean they are weak**. Dedicated same-slot replacement tests are needed for: Sol Ring, Mana Vault, Grim Monolith, Lion's Eye Diamond, Chrome Mox, Mox Diamond, Mox Opal, Lotus Petal, Ancient Tomb, City of Traitors, Crystal Vein, Mishra's Workshop, Moonsilver Key, Coalition Relic, Everflowing Chalice, Jeweled Amulet, Arcane Signet, Fellwar Stone, Mind Stone, The Mind Stone.

**Promotion rule:** No deck cut is decided by this leaderboard. Identify repeatable T2-leading combinations, separately verify full combo functionality and multiplayer constraints, then run independent held-out paired tests.
