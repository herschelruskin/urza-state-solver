# Dack Assertive ramp-piece leaderboard

**LIVE SCREENING STATUS — not a finalized card ranking.** The provisional table only appears once at least 24 completed matched games from a screen are available. Both screens preserve the same frozen Assertive mulligan policy, and all numbers are conditional on the optimistic goldfish Dack-cast model.

| Trial | Games recovered | Completed shards | Data status |
|---|---:|---:|---|
| screen20 | 256/256 | 64/64 | Fully pooled and validated |
| flex41 | 78/128 | 39/64 | Partial exploratory evidence |

---


**Primary metric:** probability of Dack cast by T2 under the promoted Assertive London policy, with T1 and T3 tracked as checks.

> All results are optimistic full-beam goldfish Dack-cast rates, not verified complete combo lines or multiplayer wins. Small-sample rankings are exploratory and susceptible to winner's curse.

## Live evidence status

- **screen20**: VALIDATED, 20 decks × 256 matched game IDs — https://github.com/herschelruskin/urza-state-solver/actions/runs/40444150025
- **flex41**: PARTIAL_78_OF_128, 41 decks × 128 matched game IDs — https://github.com/herschelruskin/urza-state-solver/actions/runs/40445020227

## Ramp-card ranking (only controlled single-card comparisons)

| Rank | Card | Observed context-weighted T2 signal (pp) | Matched contexts | Trial sets | Positive / negative contexts |
|---:|---|---:|---:|---:|---:|
| 1 | Giant's Boulder | +1.50 | 32 | 2 | 21 / 8 |
| 2 | Plains | +0.79 | 52 | 2 | 28 / 18 |
| 3 | Hardlight Containment | +0.78 | 1 | 1 | 1 / 0 |
| 4 | Voltaic Key | +0.78 | 27 | 2 | 14 / 8 |
| 5 | Tooth of Ramos | +0.49 | 18 | 2 | 11 / 7 |
| 6 | Basalt Monolith | +0.36 | 37 | 2 | 19 / 16 |
| 7 | Pentad Prism | +0.16 | 22 | 2 | 10 / 9 |
| 8 | Manifold Key | +0.02 | 37 | 2 | 16 / 17 |
| 9 | Lunarch Mantle | -0.13 | 20 | 2 | 7 / 12 |
| 10 | World Map | -1.28 | 29 | 1 | 8 / 17 |
| 11 | Implements of Sacrifice | -1.95 | 1 | 1 | 0 / 1 |
| 12 | Candelabra of Tawnos | -3.22 | 24 | 2 | 0 / 22 |

**Interpretation:** The score averages results across the *observed replacement options and deck backgrounds*, not the intrinsic value of a card. Contexts share hands and games; the displayed score has **no valid pooled confidence interval**. Strong claims require a held-out card comparison.

## Leading one-slot head-to-head comparisons

| New card over old | Background | Δ T2 (pp) | Paired 95% CI (pp) | n |
|---|---|---:|---|---:|
| Basalt Monolith over Plains | flex41: safe35_minus_giants_boulder → safe_boulder_to_basalt | +8.97 | +1.66 to +16.29 | 78 |
| Plains over World Map | flex41: full33_candelabra_of_tawnos → full_map_to_candelabra_of_tawnos | +6.41 | -2.60 to +15.42 | 78 |
| Manifold Key over Pentad Prism | flex41: current33_pentad_prism → current33_manifold_key | +6.41 | +0.94 to +11.88 | 78 |
| Voltaic Key over Pentad Prism | flex41: full35_minus_voltaic_key → full35_minus_pentad_prism | +6.41 | -0.13 to +12.95 | 78 |
| Plains over Voltaic Key | flex41: safe35_minus_giants_boulder → safe36_no_key_boulder | +6.41 | +0.94 to +11.88 | 78 |
| Manifold Key over Plains | flex41: current → current33_manifold_key | +5.13 | +0.20 to +10.05 | 78 |
| Basalt Monolith over Giant's Boulder | flex41: full_preserve_mantle → safe_boulder_to_basalt | +5.13 | +0.20 to +10.05 | 78 |
| Giant's Boulder over World Map | flex41: full_double_keys → full_map_to_manifold_key | +5.13 | -1.93 to +12.19 | 78 |
| Plains over World Map | flex41: full33_basalt_monolith → full_map_to_basalt_monolith | +5.13 | -2.79 to +13.04 | 78 |
| Plains over World Map | flex41: current33_pentad_prism → current_map_to_pentad_prism | +5.13 | +0.20 to +10.05 | 78 |
| Giant's Boulder over Pentad Prism | flex41: full35_minus_giants_boulder → full35_minus_pentad_prism | +5.13 | -0.96 to +11.22 | 78 |
| Lunarch Mantle over Candelabra of Tawnos | screen20: full_candelabra_instead_tooth → full_preserve_mantle | +4.30 | +0.50 to +8.10 | 256 |
| Plains over Basalt Monolith | flex41: current → current35_minus_basalt_monolith | +3.85 | -2.79 to +10.48 | 78 |
| Pentad Prism over World Map | flex41: current → current_map_to_pentad_prism | +3.85 | -1.74 to +9.44 | 78 |
| Basalt Monolith over Manifold Key | flex41: full_double_keys → full_basalt_over_boulder | +3.85 | -2.79 to +10.48 | 78 |
| Giant's Boulder over Plains | flex41: full_double_keys → full33_manifold_key | +3.85 | -3.69 to +11.38 | 78 |
| Basalt Monolith over World Map | flex41: full_double_keys → full_map_to_basalt_boulder_to_manifold | +3.85 | -4.50 to +12.19 | 78 |
| Basalt Monolith over Candelabra of Tawnos | flex41: full33_candelabra_of_tawnos → full33_basalt_monolith | +3.85 | -1.74 to +9.44 | 78 |
| Manifold Key over Voltaic Key | flex41: current33_voltaic_key → current33_manifold_key | +3.85 | -1.74 to +9.44 | 78 |
| Plains over Basalt Monolith | flex41: current33_pentad_prism → current_basalt_to_pentad_prism | +3.85 | -1.74 to +9.44 | 78 |
| Voltaic Key over World Map | flex41: full35_minus_voltaic_key → full35_minus_world_map | +3.85 | -0.45 to +8.14 | 78 |
| Lunarch Mantle over Tooth of Ramos | flex41: full35_minus_voltaic_key → safe35_minus_voltaic_key | +3.85 | -0.45 to +8.14 | 78 |
| Lunarch Mantle over Tooth of Ramos | flex41: full36_no_key_boulder → safe36_no_key_boulder | +3.85 | -2.79 to +10.48 | 78 |
| Pentad Prism over Voltaic Key | flex41: current_map_to_voltaic_key → current_map_to_pentad_prism | +3.85 | -2.79 to +10.48 | 78 |
| Giant's Boulder over Tooth of Ramos | screen20: full_2keys_instead_boulder → full_3keys_instead_tooth | +3.52 | -0.45 to +7.48 | 256 |
| Plains over Candelabra of Tawnos | screen20: full_prism_candelabra_boulder → full_35lands_instead_voltaic | +2.73 | -0.41 to +5.88 | 256 |
| Plains over World Map | flex41: current → current35_minus_world_map | +2.56 | -3.60 to +8.73 | 78 |
| Pentad Prism over Basalt Monolith | flex41: current → current_basalt_to_pentad_prism | +2.56 | -4.57 to +9.69 | 78 |
| Voltaic Key over Basalt Monolith | flex41: current → current_basalt_to_voltaic_key | +2.56 | -4.57 to +9.69 | 78 |
| Manifold Key over Basalt Monolith | flex41: current → current_basalt_to_manifold_key | +2.56 | -3.60 to +8.73 | 78 |

## Historical controls — Standard mulligans only

- The old 256-game held-out six-arm screen had **double-Key** at 48.83% by T2 versus 45.31% for the baseline; paired difference +3.52 pp with 95% CI [-0.138, 7.169]. The interval crosses zero.
- The old 128-game Key vs Candelabra direct swap had Voltaic Key at 47.66% by T2 and Candelabra at 46.09%; also not a settled ranking.

## What's not ranked yet

Some powerful rocks are present in every test deck and consequently have no controlled 'card absent' comparator in these screens. Their omission from the rankings **does not mean they are weak**. Dedicated same-slot replacement tests are needed for: Sol Ring, Mana Vault, Grim Monolith, Lion's Eye Diamond, Chrome Mox, Mox Diamond, Mox Opal, Lotus Petal, Ancient Tomb, City of Traitors, Crystal Vein, Mishra's Workshop, Moonsilver Key, Coalition Relic, Everflowing Chalice, Jeweled Amulet, Arcane Signet, Fellwar Stone, Mind Stone, The Mind Stone.

**Promotion rule:** No deck cut is decided by this leaderboard. Identify repeatable T2-leading combinations, separately verify full combo functionality and multiplayer constraints, then run independent held-out paired tests.
