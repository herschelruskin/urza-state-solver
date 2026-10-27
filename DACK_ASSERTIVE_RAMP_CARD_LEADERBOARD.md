# Dack Assertive ramp-piece leaderboard

**LIVE SCREENING STATUS — not a finalized card ranking.** The provisional table only appears once at least 24 completed matched games from a screen are available. Both screens preserve the same frozen Assertive mulligan policy, and all numbers are conditional on the optimistic goldfish Dack-cast model.

| Trial | Games recovered | Completed shards | Data status |
|---|---:|---:|---|
| screen20 | 164/256 | 41/64 | Partial exploratory evidence |
| flex41 | 40/128 | 20/64 | Partial exploratory evidence |

---


**Primary metric:** probability of Dack cast by T2 under the promoted Assertive London policy, with T1 and T3 tracked as checks.

> All results are optimistic full-beam goldfish Dack-cast rates, not verified complete combo lines or multiplayer wins. Small-sample rankings are exploratory and susceptible to winner's curse.

## Live evidence status

- **screen20**: PARTIAL_164_OF_256, 20 decks × 256 matched game IDs — https://github.com/herschelruskin/urza-state-solver/actions/runs/40444150025
- **flex41**: PARTIAL_40_OF_128, 41 decks × 128 matched game IDs — https://github.com/herschelruskin/urza-state-solver/actions/runs/40445020227

## Ramp-card ranking (only controlled single-card comparisons)

| Rank | Card | Observed context-weighted T2 signal (pp) | Matched contexts | Trial sets | Positive / negative contexts |
|---:|---|---:|---:|---:|---:|
| 1 | Hardlight Containment | +1.83 | 1 | 1 | 1 / 0 |
| 2 | Giant's Boulder | +1.35 | 32 | 2 | 18 / 8 |
| 3 | Plains | +1.12 | 52 | 2 | 25 / 16 |
| 4 | Tooth of Ramos | +1.07 | 18 | 2 | 11 / 6 |
| 5 | Manifold Key | +0.98 | 37 | 2 | 19 / 10 |
| 6 | Pentad Prism | +0.51 | 22 | 2 | 9 / 7 |
| 7 | Voltaic Key | +0.21 | 27 | 2 | 10 / 10 |
| 8 | Lunarch Mantle | -0.68 | 20 | 2 | 6 / 11 |
| 9 | World Map | -0.78 | 29 | 1 | 11 / 11 |
| 10 | Basalt Monolith | -0.86 | 37 | 2 | 11 / 18 |
| 11 | Candelabra of Tawnos | -3.08 | 24 | 2 | 0 / 23 |
| 12 | Implements of Sacrifice | -3.66 | 1 | 1 | 0 / 1 |

**Interpretation:** The score averages results across the *observed replacement options and deck backgrounds*, not the intrinsic value of a card. Contexts share hands and games; the displayed score has **no valid pooled confidence interval**. Strong claims require a held-out card comparison.

## Leading one-slot head-to-head comparisons

| New card over old | Background | Δ T2 (pp) | Paired 95% CI (pp) | n |
|---|---|---:|---|---:|
| Plains over World Map | flex41: current33_pentad_prism → current_map_to_pentad_prism | +10.00 | +0.58 to +19.42 | 40 |
| Giant's Boulder over Pentad Prism | flex41: full35_minus_giants_boulder → full35_minus_pentad_prism | +10.00 | -1.74 to +21.74 | 40 |
| Pentad Prism over Voltaic Key | flex41: current_map_to_voltaic_key → current_map_to_pentad_prism | +10.00 | +0.58 to +19.42 | 40 |
| Pentad Prism over World Map | flex41: current → current_map_to_pentad_prism | +7.50 | -0.77 to +15.77 | 40 |
| Plains over Basalt Monolith | flex41: current33_pentad_prism → current_basalt_to_pentad_prism | +7.50 | -3.34 to +18.34 | 40 |
| Voltaic Key over Pentad Prism | flex41: full35_minus_voltaic_key → full35_minus_pentad_prism | +7.50 | -0.77 to +15.77 | 40 |
| Giant's Boulder over World Map | flex41: full35_minus_giants_boulder → full35_minus_world_map | +7.50 | -5.42 to +20.42 | 40 |
| Plains over Voltaic Key | flex41: safe35_minus_giants_boulder → safe36_no_key_boulder | +7.50 | -0.77 to +15.77 | 40 |
| Basalt Monolith over Plains | flex41: safe35_minus_giants_boulder → safe_boulder_to_basalt | +7.50 | -3.34 to +18.34 | 40 |
| World Map over Basalt Monolith | flex41: current_map_to_voltaic_key → current_basalt_to_voltaic_key | +7.50 | -5.42 to +20.42 | 40 |
| Manifold Key over Candelabra of Tawnos | flex41: current_basalt_to_candelabra_of_tawnos → current_basalt_to_manifold_key | +7.50 | -3.34 to +18.34 | 40 |
| Plains over World Map | flex41: current → current35_minus_world_map | +5.00 | -4.80 to +14.80 | 40 |
| Plains over Basalt Monolith | flex41: current → current35_minus_basalt_monolith | +5.00 | -7.05 to +17.05 | 40 |
| Pentad Prism over Basalt Monolith | flex41: current → current_basalt_to_pentad_prism | +5.00 | -7.05 to +17.05 | 40 |
| Voltaic Key over Basalt Monolith | flex41: current → current_basalt_to_voltaic_key | +5.00 | -7.05 to +17.05 | 40 |
| Manifold Key over Basalt Monolith | flex41: current → current_basalt_to_manifold_key | +5.00 | -4.80 to +14.80 | 40 |
| Giant's Boulder over World Map | flex41: full_double_keys → full_map_to_manifold_key | +5.00 | -4.80 to +14.80 | 40 |
| Giant's Boulder over World Map | flex41: full_basalt_over_boulder → full_map_to_basalt_monolith | +5.00 | -4.80 to +14.80 | 40 |
| Plains over World Map | flex41: full33_candelabra_of_tawnos → full_map_to_candelabra_of_tawnos | +5.00 | -7.05 to +17.05 | 40 |
| Plains over World Map | flex41: full33_basalt_monolith → full_map_to_basalt_monolith | +5.00 | -7.05 to +17.05 | 40 |
| Manifold Key over Pentad Prism | flex41: current33_pentad_prism → current33_manifold_key | +5.00 | -1.84 to +11.84 | 40 |
| Voltaic Key over World Map | flex41: full35_minus_voltaic_key → full35_minus_world_map | +5.00 | -1.84 to +11.84 | 40 |
| Pentad Prism over Implements of Sacrifice | screen20: current → prism_only | +3.66 | -0.09 to +7.41 | 164 |
| Lunarch Mantle over Candelabra of Tawnos | screen20: full_candelabra_instead_tooth → full_preserve_mantle | +3.05 | -1.25 to +7.35 | 164 |
| Voltaic Key over Plains | flex41: current → current33_voltaic_key | +2.50 | -2.40 to +7.40 | 40 |
| Manifold Key over Plains | flex41: current → current33_manifold_key | +2.50 | -2.40 to +7.40 | 40 |
| Plains over Voltaic Key | flex41: full_preserve_mantle → safe35_minus_voltaic_key | +2.50 | -6.06 to +11.06 | 40 |
| Basalt Monolith over Giant's Boulder | flex41: full_preserve_mantle → safe_boulder_to_basalt | +2.50 | -2.40 to +7.40 | 40 |
| Giant's Boulder over Plains | flex41: full_double_keys → full33_manifold_key | +2.50 | -8.57 to +13.57 | 40 |
| Basalt Monolith over Plains | flex41: full_double_keys → full33_manifold_boulder_to_basalt | +2.50 | -8.57 to +13.57 | 40 |

## Historical controls — Standard mulligans only

- The old 256-game held-out six-arm screen had **double-Key** at 48.83% by T2 versus 45.31% for the baseline; paired difference +3.52 pp with 95% CI [-0.138, 7.169]. The interval crosses zero.
- The old 128-game Key vs Candelabra direct swap had Voltaic Key at 47.66% by T2 and Candelabra at 46.09%; also not a settled ranking.

## What's not ranked yet

Some powerful rocks are present in every test deck and consequently have no controlled 'card absent' comparator in these screens. Their omission from the rankings **does not mean they are weak**. Dedicated same-slot replacement tests are needed for: Sol Ring, Mana Vault, Grim Monolith, Lion's Eye Diamond, Chrome Mox, Mox Diamond, Mox Opal, Lotus Petal, Ancient Tomb, City of Traitors, Crystal Vein, Mishra's Workshop, Moonsilver Key, Coalition Relic, Everflowing Chalice, Jeweled Amulet, Arcane Signet, Fellwar Stone, Mind Stone, The Mind Stone.

**Promotion rule:** No deck cut is decided by this leaderboard. Identify repeatable T2-leading combinations, separately verify full combo functionality and multiplayer constraints, then run independent held-out paired tests.
