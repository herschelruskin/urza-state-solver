# Dack Assertive — Ramp and Flex-Slot Evidence Tracker

**Status:** AWAITING_SCREEN_RESULTS. **Objective:** fastest T1/T2 Dack cast, secondary T3 reliability. This is an *optimistic goldfish cast proxy*, not confirmed full-combo or multiplayer win rate.

## Sources

- **core20** — 20 deck variants, 256 paired seeds; AWAITING VERIFIED POOL; [GitHub run](https://github.com/herschelruskin/urza-state-solver/actions/runs/40444150025)
- **flex41** — 41 deck variants, 128 paired seeds; AWAITING VERIFIED POOL; [GitHub run](https://github.com/herschelruskin/urza-state-solver/actions/runs/40445020227)

## Direct-swap card leaderboard (conditional effects)

A card appears here only when there is a controlled comparison where one card replaces exactly one other card. A positive number means the card improved **T2** relative to its stated replacement in those contexts. Effects from different contexts reuse games and **must not be treated as independent**. The median is a descriptive sorting key, not a causal global value or valid pooled confidence interval.

| Card | Class | Matched contexts | Median ΔT2 (pp) | Range (pp) | Direction |
|---|---|---:|---:|---:|---|
| Ancient Tomb | core_land | 0 | — | — | NOT_TESTED |
| Basalt Monolith | ramp_flex | 0 | — | — | NOT_TESTED |
| Bucknard's Everfull Purse | ramp_flex | 0 | — | — | NOT_TESTED |
| Candelabra of Tawnos | untapper | 0 | — | — | NOT_TESTED |
| Chrome Mox | core_mana | 0 | — | — | NOT_TESTED |
| City of Brass | rainbow_land | 0 | — | — | NOT_TESTED |
| City of Traitors | core_land | 0 | — | — | NOT_TESTED |
| Coalition Relic | ramp_flex | 0 | — | — | NOT_TESTED |
| Command Tower | rainbow_land | 0 | — | — | NOT_TESTED |
| Crystal Vein | core_land | 0 | — | — | NOT_TESTED |
| Everflowing Chalice | ramp_flex | 0 | — | — | NOT_TESTED |
| Gemstone Mine | rainbow_land | 0 | — | — | NOT_TESTED |
| Giant's Boulder | ramp_flex | 0 | — | — | NOT_TESTED |
| Grim Monolith | core_mana | 0 | — | — | NOT_TESTED |
| Hardlight Containment | combo_flex | 0 | — | — | NOT_TESTED |
| Implements of Sacrifice | ramp_flex | 0 | — | — | NOT_TESTED |
| Lion's Eye Diamond | core_mana | 0 | — | — | NOT_TESTED |
| Lotus Petal | core_mana | 0 | — | — | NOT_TESTED |
| Lunarch Mantle | combo_flex | 0 | — | — | NOT_TESTED |
| Mana Confluence | rainbow_land | 0 | — | — | NOT_TESTED |
| Mana Vault | core_mana | 0 | — | — | NOT_TESTED |
| Manifold Key | untapper | 0 | — | — | NOT_TESTED |
| Mind Stone | ramp_flex | 0 | — | — | NOT_TESTED |
| Mishra's Workshop | core_land | 0 | — | — | NOT_TESTED |
| Mox Diamond | core_mana | 0 | — | — | NOT_TESTED |
| Mox Opal | core_mana | 0 | — | — | NOT_TESTED |
| Pentad Prism | ramp_flex | 0 | — | — | NOT_TESTED |
| Plains | land | 0 | — | — | NOT_TESTED |
| Prismatic Lens | ramp_flex | 0 | — | — | NOT_TESTED |
| Sol Ring | core_mana | 0 | — | — | NOT_TESTED |
| The Mind Stone | ramp_flex | 0 | — | — | NOT_TESTED |
| Tooth of Ramos | ramp_flex | 0 | — | — | NOT_TESTED |
| Voltaic Key | untapper | 0 | — | — | NOT_TESTED |
| World Map | tutor_flex | 0 | — | — | NOT_TESTED |

## Strongest one-card replacement results (exploratory)

| Test | Swap | Δ by T2 (pp) | Paired 95% CI (pp) | Δ by T3 (pp) |
|---|---|---:|---:|---:|
| No complete screen data yet | — | — | — | — |

## Interpretation / safeguards

- **NOT_TESTED does not mean bad.** It usually means the piece was held constant. Sol Ring, Mana Vault, LED and similar essentials aren't ranked from deck-level correlations.
- **A card's value depends on the replaced slot and neighbors.** Pentad Prism with rainbow lands can differ from Prism in a white-heavy list.
- **Lunarch Mantle and World Map are not fungible ramp only.** A cast-only test does not price downstream Boonweaver combo functionality, tutoring, or protection.
- **Multiple testing warning:** dozens of overlapping contrasts at n=128/256 are discovery signals, not proof; shortlist top few and confirm on fresh n≥1,024 paired seeds.
- **Do not merge seeds across suites as if they were paired.** Each 20- or 41-arm run has its own matched-randomness comparison space.

