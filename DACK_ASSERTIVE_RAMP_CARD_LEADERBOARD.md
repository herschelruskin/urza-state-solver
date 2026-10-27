# Dack Assertive ramp-piece leaderboard

**LIVE SCREENING STATUS — not a finalized card ranking.** The provisional table only appears once at least 24 completed matched games from a screen are available. Both screens preserve the same frozen Assertive mulligan policy, and all numbers are conditional on the optimistic goldfish Dack-cast model.

| Trial | Games recovered | Completed shards | Data status |
|---|---:|---:|---|
| screen20 | 240/256 | 60/64 | Partial exploratory evidence |
| flex41 | 62/128 | 31/64 | Partial exploratory evidence |

---


**Primary metric:** probability of Dack cast by T2 under the promoted Assertive London policy, with T1 and T3 tracked as checks.

> All results are optimistic full-beam goldfish Dack-cast rates, not verified complete combo lines or multiplayer wins. Small-sample rankings are exploratory and susceptible to winner's curse.

## Live evidence status

- **screen20**: PARTIAL_240_OF_256, 20 decks × 256 matched game IDs — https://github.com/herschelruskin/urza-state-solver/actions/runs/40444150025
- **flex41**: PARTIAL_62_OF_128, 41 decks × 128 matched game IDs — https://github.com/herschelruskin/urza-state-solver/actions/runs/40445020227

## Ramp-card ranking (only controlled single-card comparisons)

| Rank | Card | Observed context-weighted T2 signal (pp) | Matched contexts | Trial sets | Positive / negative contexts |
|---:|---|---:|---:|---:|---:|
| 1 | Giant's Boulder | +1.70 | 32 | 2 | 21 / 5 |
| 2 | Plains | +1.37 | 52 | 2 | 28 / 13 |
| 3 | Hardlight Containment | +1.25 | 1 | 1 | 1 / 0 |
| 4 | Voltaic Key | +0.99 | 27 | 2 | 13 / 9 |
| 5 | Tooth of Ramos | +0.72 | 18 | 2 | 10 / 6 |
| 6 | Manifold Key | +0.25 | 37 | 2 | 17 / 14 |
| 7 | Pentad Prism | +0.00 | 22 | 2 | 9 / 10 |
| 8 | Lunarch Mantle | -0.39 | 20 | 2 | 6 / 11 |
| 9 | Basalt Monolith | -0.70 | 37 | 2 | 13 / 18 |
| 10 | World Map | -1.28 | 29 | 1 | 9 / 17 |
| 11 | Implements of Sacrifice | -2.50 | 1 | 1 | 0 / 1 |
| 12 | Candelabra of Tawnos | -3.27 | 24 | 2 | 0 / 23 |

**Interpretation:** The score averages results across the *observed replacement options and deck backgrounds*, not the intrinsic value of a card. Contexts share hands and games; the displayed score has **no valid pooled confidence interval**. Strong claims require a held-out card comparison.

## Leading one-slot head-to-head comparisons

| New card over old | Background | Δ T2 (pp) | Paired 95% CI (pp) | n |
|---|---|---:|---|---:|
| Manifold Key over Pentad Prism | flex41: current33_pentad_prism → current33_manifold_key | +6.45 | +0.29 to +12.62 | 62 |
| Plains over World Map | flex41: current33_pentad_prism → current_map_to_pentad_prism | +6.45 | +0.29 to +12.62 | 62 |
| Giant's Boulder over Pentad Prism | flex41: full35_minus_giants_boulder → full35_minus_pentad_prism | +6.45 | -1.19 to +14.09 | 62 |
| Manifold Key over Plains | flex41: current → current33_manifold_key | +4.84 | -0.55 to +10.22 | 62 |
| Plains over Basalt Monolith | flex41: current → current35_minus_basalt_monolith | +4.84 | -3.51 to +13.18 | 62 |
| Pentad Prism over World Map | flex41: current → current_map_to_pentad_prism | +4.84 | -2.18 to +11.86 | 62 |
| Voltaic Key over Basalt Monolith | flex41: current → current_basalt_to_voltaic_key | +4.84 | -3.51 to +13.18 | 62 |
| Manifold Key over Basalt Monolith | flex41: current → current_basalt_to_manifold_key | +4.84 | -2.18 to +11.86 | 62 |
| Giant's Boulder over World Map | flex41: full_double_keys → full_map_to_manifold_key | +4.84 | -2.18 to +11.86 | 62 |
| Plains over World Map | flex41: full33_candelabra_of_tawnos → full_map_to_candelabra_of_tawnos | +4.84 | -4.65 to +14.32 | 62 |
| Plains over World Map | flex41: full33_basalt_monolith → full_map_to_basalt_monolith | +4.84 | -4.65 to +14.32 | 62 |
| Plains over Basalt Monolith | flex41: current33_pentad_prism → current_basalt_to_pentad_prism | +4.84 | -2.18 to +11.86 | 62 |
| Voltaic Key over Pentad Prism | flex41: full35_minus_voltaic_key → full35_minus_pentad_prism | +4.84 | -0.55 to +10.22 | 62 |
| Giant's Boulder over World Map | flex41: full35_minus_giants_boulder → full35_minus_world_map | +4.84 | -3.51 to +13.18 | 62 |
| Plains over Voltaic Key | flex41: safe35_minus_giants_boulder → safe36_no_key_boulder | +4.84 | -0.55 to +10.22 | 62 |
| Basalt Monolith over Plains | flex41: safe35_minus_giants_boulder → safe_boulder_to_basalt | +4.84 | -2.18 to +11.86 | 62 |
| Pentad Prism over Voltaic Key | flex41: current_map_to_voltaic_key → current_map_to_pentad_prism | +4.84 | -3.51 to +13.18 | 62 |
| World Map over Basalt Monolith | flex41: current_map_to_voltaic_key → current_basalt_to_voltaic_key | +4.84 | -5.66 to +15.34 | 62 |
| Manifold Key over Candelabra of Tawnos | flex41: current_basalt_to_candelabra_of_tawnos → current_basalt_to_manifold_key | +4.84 | -2.18 to +11.86 | 62 |
| Lunarch Mantle over Candelabra of Tawnos | screen20: full_candelabra_instead_tooth → full_preserve_mantle | +4.17 | +0.19 to +8.14 | 240 |
| Giant's Boulder over Tooth of Ramos | screen20: full_2keys_instead_boulder → full_3keys_instead_tooth | +3.33 | -0.82 to +7.48 | 240 |
| Voltaic Key over Plains | flex41: current → current33_voltaic_key | +3.23 | -3.10 to +9.55 | 62 |
| Plains over World Map | flex41: current → current35_minus_world_map | +3.23 | -4.54 to +10.99 | 62 |
| Pentad Prism over Basalt Monolith | flex41: current → current_basalt_to_pentad_prism | +3.23 | -5.75 to +12.20 | 62 |
| Basalt Monolith over World Map | flex41: full_double_keys → full_map_to_basalt_boulder_to_manifold | +3.23 | -5.75 to +12.20 | 62 |
| Giant's Boulder over World Map | flex41: full_basalt_over_boulder → full_map_to_basalt_monolith | +3.23 | -4.54 to +10.99 | 62 |
| Plains over World Map | flex41: full33_manifold_key → full_map_to_manifold_key | +3.23 | -4.54 to +10.99 | 62 |
| Plains over World Map | flex41: safe33_manifold_key → safe_map_to_manifold_key | +3.23 | -6.82 to +13.27 | 62 |
| Plains over Giant's Boulder | flex41: safe33_manifold_key → safe_boulder_to_manifold | +3.23 | -5.75 to +12.20 | 62 |
| Voltaic Key over World Map | flex41: full35_minus_voltaic_key → full35_minus_world_map | +3.23 | -1.21 to +7.66 | 62 |

## Historical controls — Standard mulligans only

- The old 256-game held-out six-arm screen had **double-Key** at 48.83% by T2 versus 45.31% for the baseline; paired difference +3.52 pp with 95% CI [-0.138, 7.169]. The interval crosses zero.
- The old 128-game Key vs Candelabra direct swap had Voltaic Key at 47.66% by T2 and Candelabra at 46.09%; also not a settled ranking.

## What's not ranked yet

Some powerful rocks are present in every test deck and consequently have no controlled 'card absent' comparator in these screens. Their omission from the rankings **does not mean they are weak**. Dedicated same-slot replacement tests are needed for: Sol Ring, Mana Vault, Grim Monolith, Lion's Eye Diamond, Chrome Mox, Mox Diamond, Mox Opal, Lotus Petal, Ancient Tomb, City of Traitors, Crystal Vein, Mishra's Workshop, Moonsilver Key, Coalition Relic, Everflowing Chalice, Jeweled Amulet, Arcane Signet, Fellwar Stone, Mind Stone, The Mind Stone.

**Promotion rule:** No deck cut is decided by this leaderboard. Identify repeatable T2-leading combinations, separately verify full combo functionality and multiplayer constraints, then run independent held-out paired tests.
