# DACK v0.64 repaired engine + land audit

## Repairs

- Campfire: {2}, {T}, exile now shuffles the graveyard into the library when a required combo creature is stranded there; LED contaminated-hand lines are allowed when Campfire is actually reachable within the T3 horizon. Grave contamination also makes artifact tutor policy prefer Campfire.
- Giant's Boulder: scry 2 now includes all six strategically distinct two-card outcomes, including keep-one/bottom-one.
- Jeweled Amulet: unrestricted colored mana may now be chosen as white when charging the Amulet.
- Mycosynth Gardens copies of Brainstone/Campfire now use the copied repair ability through effective-name handling.

All historical audits plus `v064_repair_smoothing_audit` pass.

## Calibration impact

The repaired cards barely changed the mature London thresholds. 125 old calibration states were re-evaluated, including all directly affected k4/k5 states and most affected k6 states. The resulting threshold changes were roughly 0.0003–0.0013, so v0.64 uses the following balanced thresholds:

`V1=.06172, V2=.19234, V3=.31419, V4=.42268, V5=.51025, V6=.55603`

## Matched land-vs-Plains screen

For every k4–k6 calibration seven containing the land, that land was replaced with an additional Plains and the balanced keep utility was re-evaluated. Positive delta means the tested land improved speed utility relative to Plains in those matched states. This is a much stronger screen than observational win-when-kept correlations, though sample counts per land remain modest.

| Land | n | Mean Δ utility vs Plains | + / − / tie |
|---|---:|---:|---:|
| Spire of Industry | 7 | -0.064 | 0 / 1 / 6 |
| Cavern of Souls | 12 | -0.060 | 0 / 7 / 5 |
| Command Beacon | 14 | -0.025 | 0 / 3 / 11 |
| Urza's Cave | 13 | -0.019 | 0 / 2 / 11 |
| Great Hall of the Citadel | 15 | -0.017 | 1 / 3 / 11 |
| The Mycosynth Gardens | 12 | -0.016 | 7 / 3 / 2 |
| Gemstone Mine | 10 | -0.015 | 0 / 3 / 7 |
| Talon Gates of Madara | 17 | -0.009 | 1 / 3 / 13 |
| City of Brass | 18 | -0.006 | 0 / 2 / 16 |
| Starting Town | 9 | -0.006 | 0 / 1 / 8 |
| Tarnished Citadel | 9 | -0.004 | 1 / 1 / 7 |
| Eiganjo, Seat of the Empire | 8 | +0.000 | 0 / 0 / 8 |
| Shefet Dunes | 11 | +0.000 | 0 / 0 / 11 |
| Mana Confluence | 16 | +0.003 | 1 / 0 / 15 |
| Untaidake, the Cloud Keeper | 9 | +0.004 | 2 / 2 / 5 |
| Ancient Den | 7 | +0.014 | 2 / 0 / 5 |
| Mishra's Workshop | 9 | +0.017 | 3 / 1 / 5 |
| Crystal Vein | 10 | +0.035 | 6 / 1 / 3 |
| Gemstone Caverns | 13 | +0.058 | 6 / 4 / 3 |
| Ruins of Trokair | 11 | +0.076 | 4 / 0 / 7 |
| Remote Farm | 13 | +0.093 | 10 / 1 / 2 |
| Urza's Saga | 7 | +0.114 | 6 / 1 / 0 |
| City of Traitors | 9 | +0.139 | 7 / 0 / 2 |
| Ancient Tomb | 12 | +0.224 | 10 / 1 / 1 |

### Speed interpretation

- Clear positive acceleration: Ancient Tomb, City of Traitors, Urza's Saga, Remote Farm, Ruins of Trokair, Gemstone Caverns, Crystal Vein.
- Small/neutral in this screen: Ancient Den, Mishra's Workshop, Mana Confluence, Eiganjo, Shefet Dunes, Untaidake, Tarnished Citadel, Starting Town, City of Brass.
- Speed-negative candidates versus Plains: Cavern of Souls, Command Beacon, Urza's Cave, Great Hall of the Citadel, Talon Gates of Madara. Spire of Industry has a negative mean driven by one severe case and only n=7; treat as unresolved rather than a cut.
- The Mycosynth Gardens is highly context-dependent: 7 positive, 3 negative, 2 ties; its slightly negative mean is driven by two large white-mana failures despite several meaningful copy-engine wins.

Protection/interaction caveat: Cavern of Souls, Command Beacon, Talon Gates, and Eiganjo have gameplay value outside this speed-only goldfish. Their speed delta should not be read as an overall cEDH cut recommendation.
