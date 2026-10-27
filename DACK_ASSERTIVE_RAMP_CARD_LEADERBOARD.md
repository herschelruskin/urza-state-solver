# Dack Assertive ramp-piece leaderboard

**LIVE SCREENING STATUS — not a finalized card ranking.** The provisional table only appears once at least 24 completed matched games from a screen are available. Both screens preserve the same frozen Assertive mulligan policy, and all numbers are conditional on the optimistic goldfish Dack-cast model.

| Trial | Games recovered | Completed shards | Data status |
|---|---:|---:|---|
| screen20 | 256/256 | 64/64 | Fully pooled and validated |
| flex41 | 108/128 | 54/64 | Partial exploratory evidence |

---


**Primary metric:** probability of Dack cast by T2 under the promoted Assertive London policy, with T1 and T3 tracked as checks.

> All results are optimistic full-beam goldfish Dack-cast rates, not verified complete combo lines or multiplayer wins. Small-sample rankings are exploratory and susceptible to winner's curse.

## Live evidence status

- **screen20**: VALIDATED, 20 decks × 256 matched game IDs — https://github.com/herschelruskin/urza-state-solver/actions/runs/40444150025
- **flex41**: PARTIAL_108_OF_128, 41 decks × 128 matched game IDs — https://github.com/herschelruskin/urza-state-solver/actions/runs/40445020227

## Ramp-card ranking (only controlled single-card comparisons)

| Rank | Card | Observed context-weighted T2 signal (pp) | Matched contexts | Trial sets | Positive / negative contexts |
|---:|---|---:|---:|---:|---:|
| 1 | Giant's Boulder | +1.91 | 32 | 2 | 23 / 6 |
| 2 | Plains | +0.85 | 52 | 2 | 27 / 18 |
| 3 | Hardlight Containment | +0.78 | 1 | 1 | 1 / 0 |
| 4 | Voltaic Key | +0.56 | 27 | 2 | 14 / 9 |
| 5 | Lunarch Mantle | +0.23 | 20 | 2 | 8 / 9 |
| 6 | Manifold Key | +0.16 | 37 | 2 | 20 / 16 |
| 7 | Tooth of Ramos | +0.03 | 18 | 2 | 8 / 8 |
| 8 | Basalt Monolith | -0.20 | 37 | 2 | 16 / 19 |
| 9 | Pentad Prism | -0.20 | 22 | 2 | 11 / 10 |
| 10 | World Map | -1.40 | 29 | 1 | 6 / 18 |
| 11 | Implements of Sacrifice | -1.95 | 1 | 1 | 0 / 1 |
| 12 | Candelabra of Tawnos | -2.88 | 24 | 2 | 2 / 22 |

**Interpretation:** The score averages results across the *observed replacement options and deck backgrounds*, not the intrinsic value of a card. Contexts share hands and games; the displayed score has **no valid pooled confidence interval**. Strong claims require a held-out card comparison.

## Leading one-slot head-to-head comparisons

| New card over old | Background | Δ T2 (pp) | Paired 95% CI (pp) | n |
|---|---|---:|---|---:|
| Manifold Key over Pentad Prism | flex41: current33_pentad_prism → current33_manifold_key | +7.41 | +2.45 to +12.37 | 108 |
| Plains over Voltaic Key | flex41: safe35_minus_giants_boulder → safe36_no_key_boulder | +7.41 | +2.45 to +12.37 | 108 |
| Giant's Boulder over World Map | flex41: full_double_keys → full_map_to_manifold_key | +6.48 | +0.56 to +12.40 | 108 |
| Basalt Monolith over Plains | flex41: safe35_minus_giants_boulder → safe_boulder_to_basalt | +6.48 | +0.56 to +12.40 | 108 |
| Plains over World Map | flex41: current33_pentad_prism → current_map_to_pentad_prism | +5.56 | +0.51 to +10.60 | 108 |
| Plains over Basalt Monolith | flex41: current33_pentad_prism → current_basalt_to_pentad_prism | +5.56 | -0.11 to +11.22 | 108 |
| Voltaic Key over Pentad Prism | flex41: full35_minus_voltaic_key → full35_minus_pentad_prism | +5.56 | -0.67 to +11.78 | 108 |
| Lunarch Mantle over Tooth of Ramos | flex41: full35_minus_voltaic_key → safe35_minus_voltaic_key | +5.56 | +1.22 to +9.90 | 108 |
| Lunarch Mantle over Tooth of Ramos | flex41: full36_no_key_boulder → safe36_no_key_boulder | +5.56 | -0.67 to +11.78 | 108 |
| Manifold Key over Plains | flex41: current → current33_manifold_key | +4.63 | -0.11 to +9.37 | 108 |
| Plains over Basalt Monolith | flex41: current → current35_minus_basalt_monolith | +4.63 | -0.77 to +10.03 | 108 |
| Giant's Boulder over Plains | flex41: full_double_keys → full33_manifold_key | +4.63 | -1.35 to +10.61 | 108 |
| Plains over World Map | flex41: full33_candelabra_of_tawnos → full_map_to_candelabra_of_tawnos | +4.63 | -1.89 to +11.14 | 108 |
| Manifold Key over Voltaic Key | flex41: current33_voltaic_key → current33_manifold_key | +4.63 | -0.11 to +9.37 | 108 |
| Giant's Boulder over Pentad Prism | flex41: full35_minus_giants_boulder → full35_minus_pentad_prism | +4.63 | -0.77 to +10.03 | 108 |
| Lunarch Mantle over Candelabra of Tawnos | screen20: full_candelabra_instead_tooth → full_preserve_mantle | +4.30 | +0.50 to +8.10 | 256 |
| Voltaic Key over Basalt Monolith | flex41: current → current_basalt_to_voltaic_key | +3.70 | -2.02 to +9.43 | 108 |
| Plains over Voltaic Key | flex41: full_preserve_mantle → safe35_minus_voltaic_key | +3.70 | -0.71 to +8.11 | 108 |
| Basalt Monolith over World Map | flex41: full_preserve_mantle → safe_map_to_basalt_monolith | +3.70 | -2.02 to +9.43 | 108 |
| Basalt Monolith over World Map | flex41: full_double_keys → full_map_to_basalt_boulder_to_manifold | +3.70 | -2.57 to +9.98 | 108 |
| Basalt Monolith over Plains | flex41: full_double_keys → full33_manifold_boulder_to_basalt | +3.70 | -2.57 to +9.98 | 108 |
| Plains over World Map | flex41: full33_basalt_monolith → full_map_to_basalt_monolith | +3.70 | -2.57 to +9.98 | 108 |
| Plains over Basalt Monolith | flex41: current33_voltaic_key → current_basalt_to_voltaic_key | +3.70 | -2.57 to +9.98 | 108 |
| Voltaic Key over World Map | flex41: full35_minus_voltaic_key → full35_minus_world_map | +3.70 | +0.13 to +7.28 | 108 |
| World Map over Basalt Monolith | flex41: current_map_to_voltaic_key → current_basalt_to_voltaic_key | +3.70 | -3.08 to +10.49 | 108 |
| Giant's Boulder over Tooth of Ramos | screen20: full_2keys_instead_boulder → full_3keys_instead_tooth | +3.52 | -0.45 to +7.48 | 256 |
| Pentad Prism over World Map | flex41: current → current_map_to_pentad_prism | +2.78 | -2.02 to +7.57 | 108 |
| Pentad Prism over Basalt Monolith | flex41: current → current_basalt_to_pentad_prism | +2.78 | -3.25 to +8.80 | 108 |
| Basalt Monolith over Giant's Boulder | flex41: full_preserve_mantle → safe_boulder_to_basalt | +2.78 | -1.27 to +6.82 | 108 |
| Basalt Monolith over Manifold Key | flex41: full_double_keys → full_basalt_over_boulder | +2.78 | -2.67 to +8.22 | 108 |

## Historical controls — Standard mulligans only

- The old 256-game held-out six-arm screen had **double-Key** at 48.83% by T2 versus 45.31% for the baseline; paired difference +3.52 pp with 95% CI [-0.138, 7.169]. The interval crosses zero.
- The old 128-game Key vs Candelabra direct swap had Voltaic Key at 47.66% by T2 and Candelabra at 46.09%; also not a settled ranking.

## What's not ranked yet

Some powerful rocks are present in every test deck and consequently have no controlled 'card absent' comparator in these screens. Their omission from the rankings **does not mean they are weak**. Dedicated same-slot replacement tests are needed for: Sol Ring, Mana Vault, Grim Monolith, Lion's Eye Diamond, Chrome Mox, Mox Diamond, Mox Opal, Lotus Petal, Ancient Tomb, City of Traitors, Crystal Vein, Mishra's Workshop, Moonsilver Key, Coalition Relic, Everflowing Chalice, Jeweled Amulet, Arcane Signet, Fellwar Stone, Mind Stone, The Mind Stone.

**Promotion rule:** No deck cut is decided by this leaderboard. Identify repeatable T2-leading combinations, separately verify full combo functionality and multiplayer constraints, then run independent held-out paired tests.
