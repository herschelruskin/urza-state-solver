# Dack Assertive ramp-piece leaderboard

**LIVE SCREENING STATUS — not a finalized card ranking.** The provisional table only appears once at least 24 completed matched games from a screen are available. Both screens preserve the same frozen Assertive mulligan policy, and all numbers are conditional on the optimistic goldfish Dack-cast model.

| Trial | Games recovered | Completed shards | Data status |
|---|---:|---:|---|
| screen20 | 256/256 | 64/64 | Fully pooled and validated |
| flex41 | 92/128 | 46/64 | Partial exploratory evidence |

---


**Primary metric:** probability of Dack cast by T2 under the promoted Assertive London policy, with T1 and T3 tracked as checks.

> All results are optimistic full-beam goldfish Dack-cast rates, not verified complete combo lines or multiplayer wins. Small-sample rankings are exploratory and susceptible to winner's curse.

## Live evidence status

- **screen20**: VALIDATED, 20 decks × 256 matched game IDs — https://github.com/herschelruskin/urza-state-solver/actions/runs/40444150025
- **flex41**: PARTIAL_92_OF_128, 41 decks × 128 matched game IDs — https://github.com/herschelruskin/urza-state-solver/actions/runs/40445020227

## Ramp-card ranking (only controlled single-card comparisons)

| Rank | Card | Observed context-weighted T2 signal (pp) | Matched contexts | Trial sets | Positive / negative contexts |
|---:|---|---:|---:|---:|---:|
| 1 | Giant's Boulder | +1.74 | 32 | 2 | 23 / 8 |
| 2 | Hardlight Containment | +0.78 | 1 | 1 | 1 / 0 |
| 3 | Plains | +0.68 | 52 | 2 | 27 / 20 |
| 4 | Voltaic Key | +0.63 | 27 | 2 | 15 / 9 |
| 5 | Tooth of Ramos | +0.46 | 18 | 2 | 11 / 7 |
| 6 | Basalt Monolith | +0.12 | 37 | 2 | 17 / 17 |
| 7 | Manifold Key | +0.09 | 37 | 2 | 17 / 17 |
| 8 | Pentad Prism | -0.04 | 22 | 2 | 11 / 10 |
| 9 | Lunarch Mantle | -0.12 | 20 | 2 | 7 / 12 |
| 10 | World Map | -0.90 | 29 | 1 | 10 / 16 |
| 11 | Implements of Sacrifice | -1.95 | 1 | 1 | 0 / 1 |
| 12 | Candelabra of Tawnos | -3.23 | 24 | 2 | 0 / 22 |

**Interpretation:** The score averages results across the *observed replacement options and deck backgrounds*, not the intrinsic value of a card. Contexts share hands and games; the displayed score has **no valid pooled confidence interval**. Strong claims require a held-out card comparison.

## Leading one-slot head-to-head comparisons

| New card over old | Background | Δ T2 (pp) | Paired 95% CI (pp) | n |
|---|---|---:|---|---:|
| Plains over Voltaic Key | flex41: safe35_minus_giants_boulder → safe36_no_key_boulder | +8.70 | +2.91 to +14.48 | 92 |
| Basalt Monolith over Plains | flex41: safe35_minus_giants_boulder → safe_boulder_to_basalt | +8.70 | +2.16 to +15.23 | 92 |
| Manifold Key over Pentad Prism | flex41: current33_pentad_prism → current33_manifold_key | +7.61 | +2.16 to +13.06 | 92 |
| Voltaic Key over Pentad Prism | flex41: full35_minus_voltaic_key → full35_minus_pentad_prism | +7.61 | +1.38 to +13.84 | 92 |
| Lunarch Mantle over Tooth of Ramos | flex41: full36_no_key_boulder → safe36_no_key_boulder | +6.52 | -0.12 to +13.16 | 92 |
| Manifold Key over Plains | flex41: current → current33_manifold_key | +5.43 | +0.78 to +10.09 | 92 |
| Giant's Boulder over World Map | flex41: full_double_keys → full_map_to_manifold_key | +5.43 | -0.89 to +11.76 | 92 |
| Plains over World Map | flex41: full33_candelabra_of_tawnos → full_map_to_candelabra_of_tawnos | +5.43 | -2.21 to +13.08 | 92 |
| Plains over World Map | flex41: current33_pentad_prism → current_map_to_pentad_prism | +5.43 | +0.78 to +10.09 | 92 |
| Plains over Basalt Monolith | flex41: current33_pentad_prism → current_basalt_to_pentad_prism | +5.43 | -0.12 to +10.99 | 92 |
| Lunarch Mantle over Tooth of Ramos | flex41: full35_minus_voltaic_key → safe35_minus_voltaic_key | +5.43 | +0.78 to +10.09 | 92 |
| Giant's Boulder over Pentad Prism | flex41: full35_minus_giants_boulder → full35_minus_pentad_prism | +5.43 | -0.12 to +10.99 | 92 |
| Plains over Basalt Monolith | flex41: current → current35_minus_basalt_monolith | +4.35 | -1.64 to +10.34 | 92 |
| Plains over Voltaic Key | flex41: full_preserve_mantle → safe35_minus_voltaic_key | +4.35 | -0.82 to +9.52 | 92 |
| Basalt Monolith over Giant's Boulder | flex41: full_preserve_mantle → safe_boulder_to_basalt | +4.35 | +0.16 to +8.54 | 92 |
| Giant's Boulder over Plains | flex41: full_double_keys → full33_manifold_key | +4.35 | -2.37 to +11.06 | 92 |
| Basalt Monolith over Candelabra of Tawnos | flex41: full33_candelabra_of_tawnos → full33_basalt_monolith | +4.35 | -0.82 to +9.52 | 92 |
| Manifold Key over Voltaic Key | flex41: current33_voltaic_key → current33_manifold_key | +4.35 | -0.82 to +9.52 | 92 |
| Pentad Prism over Voltaic Key | flex41: current_map_to_voltaic_key → current_map_to_pentad_prism | +4.35 | -1.64 to +10.34 | 92 |
| World Map over Basalt Monolith | flex41: current_map_to_voltaic_key → current_basalt_to_voltaic_key | +4.35 | -3.62 to +12.31 | 92 |
| Lunarch Mantle over Candelabra of Tawnos | screen20: full_candelabra_instead_tooth → full_preserve_mantle | +4.30 | +0.50 to +8.10 | 256 |
| Giant's Boulder over Tooth of Ramos | screen20: full_2keys_instead_boulder → full_3keys_instead_tooth | +3.52 | -0.45 to +7.48 | 256 |
| Pentad Prism over World Map | flex41: current → current_map_to_pentad_prism | +3.26 | -1.48 to +8.00 | 92 |
| Pentad Prism over Basalt Monolith | flex41: current → current_basalt_to_pentad_prism | +3.26 | -3.13 to +9.65 | 92 |
| Voltaic Key over Basalt Monolith | flex41: current → current_basalt_to_voltaic_key | +3.26 | -3.13 to +9.65 | 92 |
| Basalt Monolith over World Map | flex41: full_preserve_mantle → safe_map_to_basalt_monolith | +3.26 | -3.13 to +9.65 | 92 |
| Basalt Monolith over Manifold Key | flex41: full_double_keys → full_basalt_over_boulder | +3.26 | -2.37 to +8.89 | 92 |
| Basalt Monolith over World Map | flex41: full_double_keys → full_map_to_basalt_boulder_to_manifold | +3.26 | -3.81 to +10.33 | 92 |
| Basalt Monolith over Plains | flex41: full_double_keys → full33_manifold_boulder_to_basalt | +3.26 | -3.81 to +10.33 | 92 |
| Plains over World Map | flex41: full33_basalt_monolith → full_map_to_basalt_monolith | +3.26 | -3.81 to +10.33 | 92 |

## Historical controls — Standard mulligans only

- The old 256-game held-out six-arm screen had **double-Key** at 48.83% by T2 versus 45.31% for the baseline; paired difference +3.52 pp with 95% CI [-0.138, 7.169]. The interval crosses zero.
- The old 128-game Key vs Candelabra direct swap had Voltaic Key at 47.66% by T2 and Candelabra at 46.09%; also not a settled ranking.

## What's not ranked yet

Some powerful rocks are present in every test deck and consequently have no controlled 'card absent' comparator in these screens. Their omission from the rankings **does not mean they are weak**. Dedicated same-slot replacement tests are needed for: Sol Ring, Mana Vault, Grim Monolith, Lion's Eye Diamond, Chrome Mox, Mox Diamond, Mox Opal, Lotus Petal, Ancient Tomb, City of Traitors, Crystal Vein, Mishra's Workshop, Moonsilver Key, Coalition Relic, Everflowing Chalice, Jeweled Amulet, Arcane Signet, Fellwar Stone, Mind Stone, The Mind Stone.

**Promotion rule:** No deck cut is decided by this leaderboard. Identify repeatable T2-leading combinations, separately verify full combo functionality and multiplayer constraints, then run independent held-out paired tests.
